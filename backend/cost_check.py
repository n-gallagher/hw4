"""Score one model/effort setting on a fixed, graded question set: pass rate + estimated cost.

    python cost_check.py --model claude-sonnet-5-5
    python cost_check.py --model claude-haiku-5-5 --effort low
    python cost_check.py --model claude-sonnet-5-5 --no-cache      # caching off, for comparison

Spends real API money (cents per run) and stops early if --max-spend is reached.
Right answers are computed from data/campus_customs.db at run time, not hard-coded.
Each run appends a summary + every answer to output/cost_check.json; per-question usage
goes to output/cost_check_usage.json (not the app's usage_log.json).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--model", default="claude-sonnet-5-5")
parser.add_argument("--effort", default="", help="low | medium | high (blank = model default)")
parser.add_argument("--no-cache", action="store_true", help="turn prompt caching off (comparison only)")
parser.add_argument("--max-spend", type=float, default=0.50, help="stop this run if estimated spend passes this ($)")
parser.add_argument("--only", default="", help="comma-separated question numbers to run, e.g. 3,7")
parser.add_argument("--label", default="", help="free-text note stored with the run")
args = parser.parse_args()

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "output"
os.environ.update(
    MODEL_PROVIDER="anthropic",
    ANTHROPIC_MODEL=args.model,
    ANTHROPIC_EFFORT=args.effort,
    PROMPT_CACHE="off" if args.no_cache else "on",
    USAGE_LOG=str(OUT / "cost_check_usage.json"),
    AUDIT_TRAIL=str(OUT / "cost_check_audit.json"),  # keep test runs out of the app's audit trail
)
sys.path.insert(0, str(HERE))

import tools  # noqa: E402  (env must be set first)
from agent import run_chat  # noqa: E402

DB = tools.DB_PATH


# ---------- Ground truth, read from the database ----------

def qty(product_id: str, size: str) -> int:
    return next(s.quantity for s in tools.get_product_detail(product_id, DB).sizes if s.size == size)


PRICE_BASIC_HOODIE = tools.get_product_detail("basic-hoodie-big-yale", DB).price  # 68
QTY_TEE_M = qty("2025-yale-vs-harvard-t-shirt", "M")  # 20
QTY_HOODIE_XL = qty("basic-hoodie-big-yale", "XL")  # 2 (low stock)
QTY_BASEBALL_XS = qty("baseball-left-chest-crewneck", "XS")  # 0 (sold out)

# Hardest case: gray hoodies at or under $70 -> the one with the most units in XL.
GRAY_HOODIES = [
    p for p in tools.list_products(db_path=DB)
    if p.category == "Hoodies" and p.price <= 70 and any("gray" in c.lower() for c in p.colors)
]
XL_UNITS = sorted(((qty(p.product_id, "XL"), p) for p in GRAY_HOODIES), key=lambda x: -x[0])
assert XL_UNITS[0][0] > XL_UNITS[1][0], "hardest case needs a unique winner"
BEST_XL_QTY, BEST_XL = XL_UNITS[0]  # 25, Yale Sports Hoodie Hockey

# "Navy tee" = a T-shirt whose own (main, first-listed) color is navy, not a gray tee with navy graphics.
NAVY_TEES_UNDER_40 = {
    p.product_id for p in tools.list_products(db_path=DB)
    if p.category == "T-Shirts" and p.price <= 40 and p.colors and "navy" in p.colors[0].lower()
}

NEGATIVE = r"sold out|out of stock|don.t have|do not have|not available|unavailable|none left|0 left|no longer"
NOT_FOUND = r"couldn.t find|could not find|can.t find|don.t (carry|have|sell|see)|do not (carry|have|sell)|not (in|part of) (our|the)|no .{0,20}jersey|isn.t (in|part of|something)|doesn.t (appear|exist|look)"


COLOR = r"(navy|white|red|gray|grey|heather gray|black|blue|cream|ivory|gold|green)"
# Applied to every answer: no talking about a previous message, and no describing design colors as options
META_TALK = r"\bmy (last|previous|earlier) (reply|message|answer)\b|here is the full answer"
FAKE_COLOR_OPTIONS = rf"\b(comes in|available in|also in|in) {COLOR}( blue)?(, {COLOR}( blue)?)*,? (and|or) {COLOR}\b"


def global_problems(reply: str) -> list[str]:
    out = []
    if re.search(META_TALK, reply.lower()):
        out.append("meta-talk about an earlier message")
    if re.search(FAKE_COLOR_OPTIONS, reply.lower()):
        out.append("describes design colors as color options")
    return out


def has_num(text: str, n: int) -> bool:
    words = {2: "two", 20: "twenty", 25: "twenty-five"}
    return re.search(rf"(?<![\d$.]){n}(?![\d])", text) is not None or (n in words and words[n] in text.lower())


def used(calls: list[str], tool: str) -> bool:
    return any(c.startswith(tool + "(") for c in calls)


# (question, short label, pass rule text, grader(reply, product_ids, tool_calls) -> bool)
CASES = [
    (
        "How much is the Basic Hoodie Big Yale?",
        "Price lookup",
        f"Reply states ${PRICE_BASIC_HOODIE:.0f} and a tool was called.",
        lambda r, ids, c: f"${PRICE_BASIC_HOODIE:.0f}" in r and len(c) > 0,
    ),
    (
        "What's printed on the Baseball Left Chest Crewneck, and what colors does it come in?",
        "Description",
        "Reply mentions the YALE BASEBALL wordmark, the left chest, and both colors (navy, white); a tool was called.",
        lambda r, ids, c: all(w in r.lower() for w in ("baseball", "left chest", "navy", "white")) and len(c) > 0,
    ),
    (
        "Do you have the Baseball Left Chest Crewneck in XS?",
        "Sold-out size",
        f"Database has {QTY_BASEBALL_XS} in XS: reply must say sold out / not available, and check_stock was called.",
        lambda r, ids, c: re.search(NEGATIVE, r.lower()) is not None and used(c, "check_stock"),
    ),
    (
        "How many mediums are left of the 2025 Yale vs Harvard T-shirt?",
        "Exact count",
        f"Reply contains the exact count {QTY_TEE_M} and check_stock was called.",
        lambda r, ids, c: has_num(r, QTY_TEE_M) and used(c, "check_stock"),
    ),
    (
        "Is the Basic Hoodie Big Yale available in extra large?",
        "Low stock",
        f"Database has {QTY_HOODIE_XL} in XL: reply gives that exact number and does not call it sold out.",
        lambda r, ids, c: has_num(r, QTY_HOODIE_XL) and "sold out" not in r.lower(),
    ),
    (
        "How much is the Yale hockey jersey, and do you have it in medium?",
        "TRAP: product doesn't exist",
        "No jersey exists: reply must say it couldn't find / doesn't carry it, after searching, and quote no jersey price.",
        lambda r, ids, c: re.search(NOT_FOUND, r.lower()) is not None
        and len(c) > 0
        and re.search(r"jersey[^.]{0,40}\$\d", r.lower()) is None,
    ),
    (
        "I want a grey hoodie for $70 or less. Which one has the most left in XL, and how many?",
        "HARDEST: multi-filter + max",
        f"Reply names the {BEST_XL.name} as the one with the most XL units and gives {BEST_XL_QTY}.",
        lambda r, ids, c: BEST_XL.name.lower().replace("yale sports hoodie ", "") in r.lower()
        and has_num(r, BEST_XL_QTY),
    ),
    (
        "Do you have any navy tees under $40?",
        "Search + cards",
        f"At least 2 product cards, all T-shirts whose main color is navy, priced at or under $40 ({len(NAVY_TEES_UNDER_40)} qualify).",
        lambda r, ids, c: len(ids) >= 2 and set(ids) <= NAVY_TEES_UNDER_40,
    ),
]


# ---------- Run ----------

async def main() -> None:
    selected = {int(x) for x in args.only.split(",") if x.strip()} if args.only else None
    rows, spend, passed, ran = [], 0.0, 0, 0
    for i, (question, label, rule, grade) in enumerate(CASES, start=1):
        if selected and i not in selected:
            continue
        if spend >= args.max_spend:
            print(f"Q{i} SKIPPED: spend cap ${args.max_spend:.2f} reached")
            rows.append({"q": i, "question": question, "result": "skipped"})
            continue
        try:
            run = await run_chat(question, [])
        except Exception as e:  # recorded, never graded as a pass
            print(f"Q{i} ERROR {type(e).__name__}: {str(e)[:200]}")
            rows.append({"q": i, "question": question, "result": "error", "error": f"{type(e).__name__}: {str(e)[:500]}"})
            ran += 1
            continue
        reply, ids = run.output.reply, run.output.product_ids
        problems = global_problems(reply)
        ok = bool(grade(reply, ids, run.tool_calls)) and not problems
        passed += ok
        ran += 1
        spend += run.usage.est_cost_usd
        rows.append({
            "q": i, "question": question, "result": "pass" if ok else "fail",
            "cost": run.usage.est_cost_usd, "secs": run.seconds, "usage": run.usage.model_dump(),
            "tool_calls": run.tool_calls, "reply": reply, "product_ids": ids, "problems": problems,
        })
        print(f"Q{i} {'PASS' if ok else 'FAIL'}  ${run.usage.est_cost_usd:.4f}  {run.seconds:>5}s  "
              f"req={run.usage.requests} tools={len(run.tool_calls)}  {label}" + (f"  {problems}" if problems else ""))

    config = f"{args.model} effort={args.effort or 'default'} cache={'off' if args.no_cache else 'on'}"
    print(f"\n{config}: {passed}/{ran} passed, ${spend:.4f} total, ${spend / max(ran, 1):.4f} per question")

    log = OUT / "cost_check.json"
    history = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    history.append({
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "config": config, "label": args.label,
        "passed": passed, "total": ran, "cost_usd": round(spend, 5), "cases": rows,
    })
    OUT.mkdir(exist_ok=True)
    log.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
