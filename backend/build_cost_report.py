"""Build COST_CHECK_REPORT.md from output/cost_check.json (no API calls).

    python build_cost_report.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.argv = [sys.argv[0]]  # cost_check parses argv on import
sys.path.insert(0, str(HERE))
import cost_check as cc  # noqa: E402  (graders + questions; importing makes no API calls)

RUNS = json.loads((ROOT / "output" / "cost_check.json").read_text(encoding="utf-8"))
UNLOGGED_EST = 0.48  # looping runs that errored before logging (see "Cost breakdown")

# Which code each run tested
ROUND = {1: "A"} | {i: "B" for i in range(2, 11)} | {i: "C" for i in range(11, 16)} | {i: "D" for i in range(16, 100)}
ROUND_TEXT = {
    "A": "Round A: JSON-only structured output (`PromptedOutput`). The agent looped on tool calls.",
    "B": "Round B: plain-text reply + `show_products` tool, search fixes, caching. Graded with the original rules.",
    "C": "Round C: + one-colorway `main_color`, answer kept from the `show_products` step, stricter graders.",
    "D": "Round D: regression checks on later code: run 16 after Problems 7–8 (on-page cards, customer memory, page context), run 17 after Problem 9 (add_to_bag tool + price & stock fact-checker), run 18 after the Problem 11 fact-checker fix, run 19 after the Handsome Dan persona + no-checkout rule, run 20 after the Problem 12 safety rules + audit trail.",
}


def short(cfg: str) -> str:
    return cfg.replace("claude-", "").replace(" effort=", " · effort ").replace(" cache=", " · cache ")


def regrade(case: dict) -> str:
    """Grade an earlier answer with the final (round C) rules."""
    if case["result"] in ("error", "skipped"):
        return "ERR"
    q = case["q"]
    _, _, _, grade = cc.CASES[q - 1]
    ok = grade(case["reply"], case.get("product_ids", []), case.get("tool_calls", [])) and not cc.global_problems(case["reply"])
    return "pass" if ok else "FAIL"


lines: list[str] = []
w = lines.append

n_answers = sum(len(r["cases"]) for r in RUNS)
logged = sum(r["cost_usd"] for r in RUNS)
w("# Cost check report: Campus Customs shop agent")
w("")
w(f"Generated from `output/cost_check.json` by `backend/build_cost_report.py`. {len(RUNS)} runs × 8 questions = "
  f"{n_answers} graded answers, run on {RUNS[0]['time'][:10]} between {RUNS[0]['time'][11:16]} and {RUNS[-1]['time'][11:16]}. "
  f"Graded-run spend: **${logged:.2f}**; with debugging calls, about **${logged + 0.07 + UNLOGGED_EST:.2f}** in total.")
w("")

# ---------------- Decision
w("## Decision")
w("")
w("- **Default now:** `claude-haiku-5-5`, model-default effort, prompt caching on.")
w("- **Why:** cheapest setting that passed every graded question under the final rules: 9 runs, 72/72 (runs 12–15, "
  "plus regression runs 16–20 on the code after Problems 7–12). "
  "Haiku at low effort also passed (run 13) but saved under 10% of an already tiny cost, so default effort is kept.")
w("- **Cost:** about **$0.0005 per question**, vs **$0.0325** for the setup at the start of this check "
  "(Sonnet 5.5, no caching): about **98% less**. Sonnet with caching (the best Sonnet setting) is about $0.0098.")
w("- **Caveats:** 8 single-turn questions; multi-turn follow-ups were not graded. The assignment suggests a smarter model "
  "for harder steps. The hardest case here (multi-filter + max) passed on Haiku every time, but if new hard cases fail, "
  "set `ANTHROPIC_MODEL=claude-sonnet-5-5` in `.env` (no code change).")
w("")

# ---------------- Summary
w("## Summary of every run")
w("")
w("| # | Round | Model | Effort | Caching | Passed (as graded) | Re-graded with final rules | Cost (8 Qs) | Per question | Note |")
w("|---|---|---|---|---|---|---|---|---|---|")
for i, r in enumerate(RUNS, 1):
    cfg = r["config"]
    model = cfg.split(" effort=")[0].replace("claude-", "")
    effort = cfg.split(" effort=")[1].split(" cache=")[0]
    cache = cfg.split(" cache=")[1]
    rg = [regrade(c) for c in r["cases"]]
    rg_text = f"{rg.count('pass')}/{len(rg)}"
    errs = sum(c["result"] == "error" for c in r["cases"])
    note = f"{errs} answers hit the 10-request cap (looping)" if errs else ""
    w(f"| {i} | {ROUND[i]} | {model} | {effort} | {cache} | {r['passed']}/{len(r['cases'])} | {rg_text} | "
      f"${r['cost_usd']:.4f} | ${r['cost_usd'] / max(1, sum(c['result'] in ('pass', 'fail') for c in r['cases'])):.4f} | {note} |")
w("")
for k, v in ROUND_TEXT.items():
    w(f"- **{k}** = {v}")
w("")

# ---------------- Pass/fail by question
w("## Pass/fail by question")
w("")
w("As graded at the time. For rounds A/B, the row below each run shows the same answers re-graded with the final rules.")
w("")
w("| # | Config | " + " | ".join(f"Q{q}" for q in range(1, 9)) + " |")
w("|---|---|" + "---|" * 8)
for i, r in enumerate(RUNS, 1):
    cells = {c["q"]: c["result"] for c in r["cases"]}
    fmt = lambda x: {"pass": "pass", "fail": "**FAIL**", "error": "ERR"}.get(x, x)  # noqa: E731
    w(f"| {i} ({ROUND[i]}) | {short(r['config'])} | " + " | ".join(fmt(cells.get(q, '-')) for q in range(1, 9)) + " |")
    if ROUND[i] in ("A", "B"):
        rg = {c["q"]: regrade(c) for c in r["cases"]}
        w(f"| ↳ re-graded | final rules | " + " | ".join(("**FAIL**" if rg[q] == "FAIL" else rg[q]) for q in range(1, 9)) + " |")
w("")
for q, (question, label, _, _) in enumerate(cc.CASES, 1):
    w(f"- **Q{q}** ({label}): {question}")
w("")

# ---------------- Questions + rules
w("## The questions and how each is graded")
w("")
w("Right answers are read from `data/campus_customs.db` when the check runs (nothing is hard-coded).")
w("")
w("| # | Question | Pass rule |")
w("|---|---|---|")
for q, (question, label, rule, _) in enumerate(cc.CASES, 1):
    w(f"| Q{q} | {question} | {rule} |")
w("")
w("**Applied to every answer (added in round C):** fail if the reply talks about \"my last/previous message\" "
  "(a sign the real answer was lost), or describes design colors as color options "
  "(\"comes in navy and white\"; each product is one colorway).")
w("")

# ---------------- Failures
w("## What the failures were")
w("")
w("- **Tool-call loop (round A, run 1: Q4, Q6, Q8 errored; Q2/Q3/Q5 passed but used 7–10 requests).** "
  "With JSON-only output (`PromptedOutput`) Claude Sonnet 5.5 kept calling the same tool (e.g. "
  "`get_product_info` on the same hoodie 7 times) and even a non-existent tool `x()`, instead of finishing. "
  "Not a grader problem and not a knowledge problem: the model could not end its turn in that output mode "
  "(`NativeOutput` had looped to a 50-request cap earlier the same day). Ruled out with traced runs: caching "
  "(looped with caching off), `max_tokens` (looped without it). Moving the per-shopper context into the message made "
  "it worse (looped every time) and was reverted. **Fix:** plain-text reply + a `show_products(product_ids)` tool for "
  "the cards. Requests per question fell from 7–10 to 3–4.")
w("- **Lost answer / meta-talk (round B, Haiku only, 6 of 48 Haiku answers).** Haiku sometimes wrote its full answer in "
  "the same step as `show_products`, then a second message about it (\"My last reply went through: six navy tees…\"). "
  "Only the last message reached the shopper. The original graders passed these because the facts and cards were "
  "right; reading the answers caught it. **Fix:** `pick_reply()` keeps the answer written with `show_products`, and the "
  "prompt says to call `show_products` first and answer once. Never seen again in round C.")
w("- **Colors read as options (rounds A/B, both models).** \"It also comes in white\" for a navy hoodie with white "
  "lettering. The tool returned the design's colors in a field called `colors` with no explanation: a **tool/data "
  "problem**, not a model one. **Fix:** tools now return `main_color` (the garment color) and describe `colors` as "
  "design colors; the color filter matches the main color; the prompt explains one colorway per product.")
w("- **Grader problem (Q8, rounds A/B).** \"Navy tees\" counted any tee with navy anywhere in the design (19), including a "
  "heather-gray tee with navy helmets. Fixed to main color navy (5 tees). Answers in rounds A/B that showed gray tees "
  "fail on re-grade.")
w("- **Search bugs found while measuring (fixed before any graded run):** \"grey\" found 0 products (catalogue says "
  "gray); \"tee\" found 6 of 25 T-shirts; \"tshirt\" matched 59 items because \"swea**tshirt**\" contains it. Fixed "
  "with word-start matching and a small synonym list. Search also returns units in the requested size, sorted, so "
  "\"which has the most left in XL?\" takes one call instead of ~9.")
w("- **Not failures:** a catalogue name typo (\"Yale Sports Creqneck Field Hockey\") is in the data, not the model; "
  "no setting ever invented a price, a quantity, or the hockey jersey (Q6 trap passed in every graded answer).")
w("")

# ---------------- Cost breakdown
w("## Cost breakdown")
w("")
w("Prices used ($ per million tokens: input / output / cache read; cache writes bill at 1.25× input):")
w("")
w("| Model | Input | Output | Cache read |")
w("|---|---|---|---|")
w("| claude-sonnet-5-5 | $2.00 | $10.00 | $0.20 |")
w("| claude-haiku-5-5 | $0.10 | $0.50 | $0.01 |")
w("")
w("Average cost per question:")
w("")
cols = [("Sonnet, no cache (B)", [2]), ("Sonnet, cached (C)", [11]), ("Haiku (C)", [12, 14, 15]), ("Haiku low (C)", [13])]
w("| Question | " + " | ".join(c for c, _ in cols) + " |")
w("|---|" + "---|" * len(cols))
for q, (question, *_rest) in enumerate(cc.CASES, 1):
    cells = []
    for _, runs in cols:
        costs = [c["cost"] for i in runs for c in RUNS[i - 1]["cases"] if c["q"] == q and "cost" in c]
        cells.append(f"${sum(costs) / len(costs):.4f}" if costs else "-")
    w(f"| Q{q} {question} | " + " | ".join(cells) + " |")
tot = []
for _, runs in cols:
    tot.append(f"**${sum(RUNS[i - 1]['cost_usd'] for i in runs) / len(runs) / 8:.4f}**")
w("| **Average** | " + " | ".join(tot) + " |")
w("")
avg_tok = defaultdict(list)
for i in (2, 11, 12):
    for c in RUNS[i - 1]["cases"]:
        u = c["usage"]
        avg_tok[i].append((u["input_tokens"], u["cache_read_tokens"], u["cache_write_tokens"], u["output_tokens"]))
w("Where the tokens go (average per question): ")
w("")
w("| Run | Uncached input | Cache read | Cache write | Output |")
w("|---|---|---|---|---|")
for i, rows in avg_tok.items():
    n = len(rows)
    w(f"| {i} {short(RUNS[i - 1]['config'])} | " + " | ".join(f"{sum(r[k] for r in rows) / n:,.0f}" for k in range(4)) + " |")
w("")
w("A question takes about 3–4 model requests (tool calls, then the answer), and each request re-sends the system prompt "
  "and tool definitions: measured at about 14,500 input tokens per question, roughly 4,000 per request, while tool "
  "results are only ~70–420 tokens each. Caching turns that repeated block into cache reads (10× cheaper), cutting "
  "Sonnet from $0.0325 to about $0.008–0.010 per question. Haiku's base price is 20× lower again.")
w("")
w(f"**Total spend for this check:** ${logged:.2f} in graded runs (above) + about $0.07 in logged diagnostic runs + "
  f"about ${UNLOGGED_EST:.2f} not logged (runs that looped into the request cap and raised before logging: three in "
  "run 1 and three diagnostic traces). About **$1.40** overall, against an estimate of $0.50–0.80 made before the loop "
  "bug was found.")
w("")

# ---------------- Changes
w("## Changes made to the app")
w("")
w("1. **Usage logging:** every chat appends model, effort, requests, tool calls, uncached / cache-read / cache-write / "
  "output tokens, seconds and estimated cost to `output/usage_log.json` (`agent.log_usage`).")
w("2. **Prompt caching:** `anthropic_cache_instructions` + `anthropic_cache_messages` (system prompt + tools, and the "
  "conversation inside one tool loop). `PROMPT_CACHE=off` exists only for comparisons.")
w("3. **Reply format:** plain-text reply + `show_products` tool instead of JSON-only output (fixed the tool-call loop); "
  "`pick_reply()` keeps the real answer if the model writes it alongside `show_products`.")
w("4. **Smaller tool results:** search returns 6 rows (the card limit) instead of 8.")
w("5. **Tool fixes:** word-start keyword matching + synonyms (grey/gray, tee/t-shirt, hoodies…); `main_color` field and "
  "main-color filtering; `units_in_requested_size` with sorting for size searches.")
w("6. **Model choice:** `claude-haiku-5-5`, default effort (from the runs above). Settings live in `.env` "
  "(see `.env.example`): `ANTHROPIC_MODEL`, `ANTHROPIC_EFFORT`.")
w("")

# ---------------- How to re-run
w("## How to re-run")
w("")
w("From `hw4/backend` (spends real API money: under 1¢ per Haiku run, about 8¢ per Sonnet run):")
w("")
w("```bash")
w("../.venv/Scripts/python cost_check.py --model claude-haiku-5-5")
w("```")
w("")
w("Options: `--model`, `--effort low|medium|high`, `--no-cache`, `--only 3,7`, `--max-spend 0.50`, `--label`. Each run "
  "appends to `output/cost_check.json`; per-question usage goes to `output/cost_check_usage.json`. Rebuild this "
  "report with `../.venv/Scripts/python build_cost_report.py`.")
w("")

# ---------------- Every answer
w("## Every answer, run by run")
w("")
for i, r in enumerate(RUNS, 1):
    w(f"### Run {i}: {short(r['config'])} (Round {ROUND[i]})")
    w("")
    w(f"{r['time']} · {r['passed']}/{len(r['cases'])} passed as graded · ${r['cost_usd']:.4f}")
    w("")
    w("| Q | Result | Re-graded | Cost | Secs | Requests | Uncached in | Cache read | Cache write | Output | Tools called |")
    w("|---|---|---|---|---|---|---|---|---|---|---|")
    for c in r["cases"]:
        if c["result"] == "error":
            w(f"| Q{c['q']} | ERR | ERR | - | - | - | - | - | - | - | {c['error'][:90]} |")
            continue
        u = c["usage"]
        res = "pass" if c["result"] == "pass" else "**FAIL**"
        rg = regrade(c)
        w(f"| Q{c['q']} | {res} | {'**FAIL**' if rg == 'FAIL' else rg} | ${c['cost']:.4f} | {c['secs']} | {u['requests']} | "
          f"{u['input_tokens']} | {u['cache_read_tokens']} | {u['cache_write_tokens']} | {u['output_tokens']} | "
          f"{'; '.join(c['tool_calls']).replace('|', '/')} |")
    w("")
    for c in r["cases"]:
        if c["result"] == "error":
            continue
        q, label = c["q"], cc.CASES[c["q"] - 1][1]
        tag = "PASS" if c["result"] == "pass" else "FAIL"
        probs = cc.global_problems(c["reply"])
        extra = f" (re-graded: {', '.join(probs)})" if probs and ROUND[i] in ("A", "B") else ""
        w(f"<details><summary>Q{q} {tag}{extra}: {c['question']}</summary>")
        w("")
        w(c["reply"])
        w("")
        w(f"*Cards:* {', '.join(c.get('product_ids') or []) or 'none'}")
        w("")
        w("</details>")
        w("")

(ROOT / "COST_CHECK_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
print(f"wrote COST_CHECK_REPORT.md ({len(lines)} lines)")
