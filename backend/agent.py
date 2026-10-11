"""Campus Customs shop agent: PydanticAI wiring.

The agent is built once from:
  - the system prompt in prompts/prompt.md
  - the model chosen in .env (MODEL_PROVIDER / ANTHROPIC_MODEL / OPENAI_MODEL)
  - three tools: search_products, get_product_info, check_stock (thin wrappers around tools.py)
  - plain-text replies; product cards are chosen with the show_products tool, and run_chat()
    packages both into a ShopReply (models.py)

main.py calls run_chat() for every /api/chat request. Each run's token usage and
estimated cost are appended to output/usage_log.json.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv
from pydantic_ai import Agent, ModelRetry, RunContext, capture_run_messages
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RunUsage, UsageLimits

import tools
from models import (
    AddToBagResult,
    AuditEntry,
    BagLine,
    ChatRun,
    ChatTurn,
    CustomerProfile,
    LookupMiss,
    PageContext,
    ProductInfo,
    ProductSearchResult,
    ShownProducts,
    ShopDeps,
    ShopReply,
    StockCheck,
    UsageSummary,
)

BACKEND_DIR = Path(__file__).resolve().parent
PROMPT_PATH = BACKEND_DIR / "prompts" / "prompt.md"

# Keys: hw4/.env (copy .env.example), with the parent folder's .env as an optional fallback.
load_dotenv(BACKEND_DIR.parent / ".env")
load_dotenv(BACKEND_DIR.parent.parent / ".env")

# Chosen with cost_check.py (see COST_CHECK_REPORT.md): Haiku 5.5 passed every graded question
# at ~1/20 of Sonnet 5.5's cost once caching and the tool fixes were in.
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-5-5"
DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# Guardrails on one chat turn: caps model round-trips and tool calls (cost / runaway loops).
CHAT_USAGE_LIMITS = UsageLimits(request_limit=10, tool_calls_limit=12)

# Per-run usage log (cost_check.py points this at its own file).
USAGE_LOG = Path(os.getenv("USAGE_LOG", BACKEND_DIR.parent / "output" / "usage_log.json"))
_log_lock = threading.Lock()

# $ per million tokens: (input, output, cache read). Cache writes bill at 1.25x input.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
}


def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def model_name() -> str:
    if os.getenv("MODEL_PROVIDER", "anthropic").strip().lower() == "portkey":
        return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    return os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)


def effort() -> str:
    """ANTHROPIC_EFFORT: low | medium | high, blank = the model's default."""
    return os.getenv("ANTHROPIC_EFFORT", "").strip().lower()


def model_label() -> str:
    provider = os.getenv("MODEL_PROVIDER", "anthropic").strip().lower()
    if provider == "portkey":
        return f"portkey:{os.getenv('OPENAI_MODEL', DEFAULT_OPENAI_MODEL)}"
    return f"anthropic:{os.getenv('ANTHROPIC_MODEL', DEFAULT_ANTHROPIC_MODEL)}"


def create_model() -> tuple[Model, ModelSettings | None]:
    """Anthropic by default; set MODEL_PROVIDER=portkey to use OpenAI models through Portkey."""
    provider = os.getenv("MODEL_PROVIDER", "anthropic").strip().lower()
    if provider == "portkey":
        from openai import AsyncOpenAI
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        api_key = os.getenv("PORTKEY_API_KEY")
        if not api_key:
            raise RuntimeError("PORTKEY_API_KEY is missing from .env")
        client = AsyncOpenAI(
            api_key=api_key, base_url=PORTKEY_BASE_URL, default_headers={"x-portkey-api-key": api_key}
        )
        return OpenAIChatModel(model_name(), provider=OpenAIProvider(openai_client=client)), None

    from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
    from pydantic_ai.providers.anthropic import AnthropicProvider

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is missing from .env")
    model = AnthropicModel(model_name(), provider=AnthropicProvider(api_key=api_key))
    caching = os.getenv("PROMPT_CACHE", "on").strip().lower() != "off"  # "off" only for cost comparisons
    settings = AnthropicModelSettings(
        max_tokens=2000,
        # Prompt caching: the system prompt + tool definitions, and the growing conversation
        # inside one tool loop, are billed at the cache-read rate after the first request.
        anthropic_cache_instructions=caching,
        anthropic_cache_messages=caching,
    )
    if effort():
        settings["anthropic_effort"] = effort()
    return model, settings


def dynamic_context(ctx: RunContext[ShopDeps]) -> str:
    """Code that writes per-request context into the agent's instructions: WHO is chatting and
    WHICH page they're on (from ShopDeps). Runs before every model request.

    (Tried putting this in the shopper's message instead, to keep the system prompt identical across
    requests; that made the agent repeat tool calls in a loop, so it stays here. See COST_CHECK_REPORT.md.)
    """
    c, page = ctx.deps.customer, ctx.deps.page
    lines = ["## Current conversation context (from the website, trusted)"]
    if c:
        lines.append(
            f"- Shopper: LOGGED IN as {c.first_name} {c.last_name} (email {c.email}, customer #{c.user_id}, "
            f"member since {c.member_since}). Their chat history is saved; {c.saved_messages} earlier messages exist "
            "and the most recent ones are included above."
        )
    else:
        lines.append("- Shopper: a GUEST (not logged in). Chat history is not saved after they leave.")
    if page and page.product_id:
        lines.append(
            f"- Page: the PRODUCT PAGE for \"{page.product_name}\" (product_id {page.product_id}, "
            f"${page.product_price:.0f}, main color {page.product_main_color or 'unknown'}; "
            f"design colors {', '.join(page.product_colors) or 'not listed'}). "
            "\"This\", \"it\" or \"this one\" means this product."
        )
    elif page:
        lines.append(f"- Page: {page.page_name} ({page.path}). No specific product is open.")
    if ctx.deps.my_size:
        lines.append(f"- Shopper's size (set in 'Shop my size' mode): {ctx.deps.my_size}. Use it when they don't name a size.")
    if ctx.deps.bag:
        units, subtotal = tools.bag_subtotal(ctx.deps.bag, ctx.deps.db_path)
        names = {p.product_id: p.name for p in tools.get_products_by_ids([b.product_id for b in ctx.deps.bag], ctx.deps.db_path)}
        items = "; ".join(f"{b.quantity} x {names.get(b.product_id, b.product_id)} ({b.size})" for b in ctx.deps.bag)
        lines.append(f"- Bag: {items}. {units} item(s), subtotal ${subtotal:.2f}.")
    else:
        lines.append("- Bag: empty.")
    return "\n".join(lines)


@lru_cache(maxsize=1)
def build_agent() -> Agent[ShopDeps, str]:
    model, settings = create_model()
    agent: Agent[ShopDeps, str] = Agent(
        model=model,
        model_settings=settings,
        instructions=[load_system_prompt(), dynamic_context],
        # Plain-text output. Structured output modes misbehaved with Claude Sonnet 5.5: the forced
        # tool call is rejected by the API, and JSON-only output made the agent loop on tool calls
        # instead of finishing (see COST_CHECK_REPORT.md). Cards come from show_products instead.
        output_type=str,
        deps_type=ShopDeps,
        retries=2,
    )

    @agent.tool
    def search_products(
        ctx: RunContext[ShopDeps],
        keywords: str = "",
        category: str | None = None,
        color: str | None = None,
        max_price: float | None = None,
        size_in_stock: str | None = None,
    ) -> ProductSearchResult:
        """Find products in the Campus Customs catalogue. Returns up to 6 matches (id, name, category, price, colors, sizes in stock).

        Use this to discover products and their product_ids. For the full description use get_product_info;
        for exact unit counts use check_stock.

        Args:
            keywords: Words that must all appear in the product's name/description/tags, e.g. "baseball", "Harvard", "big yale", "tee". Empty to browse.
            category: One of Hoodies, Crewnecks, T-Shirts, Quarter-zips, Fleece & Jackets, Long Sleeve.
            color: The garment's main color, e.g. "navy", "gray", "white" (matches the item's own color, not logo colors).
            max_price: Only items at or below this price in US dollars.
            size_in_stock: Only items with this size in stock (XS, S, M, L, XL, XXL; "medium" etc. also accepted). Results then show units_in_requested_size and are sorted by it, most first.
        """
        return tools.search_catalogue(ctx.deps.db_path, keywords, category, color, max_price, size_in_stock)

    @agent.tool
    def get_product_info(ctx: RunContext[ShopDeps], product: str) -> ProductInfo | LookupMiss:
        """Look up one product's price, colors, garment type, and full description from the database.

        Use for "how much is…", "tell me about…", "what does it look like / what color is it" questions.

        Args:
            product: The product_id (preferred, e.g. "basic-hoodie-big-yale") or the product's name.
        """
        return tools.product_info(ctx.deps.db_path, product)

    @agent.tool
    def check_stock(ctx: RunContext[ShopDeps], product: str, size: str | None = None) -> StockCheck | LookupMiss:
        """Look up live inventory for one product: units in stock for every size XS–XXL.

        Use for any "is it in stock", "do you have it in…", "how many are left" question. Pass `size` when the
        shopper names one; the result then includes requested_size_status (in_stock / low / sold_out / not_offered)
        and a one-sentence `answer` to relay.

        Args:
            product: The product_id (preferred) or the product's name.
            size: Optional size the shopper asked about: XS, S, M, L, XL, XXL, or words like "medium", "2XL".
        """
        return tools.stock_check(ctx.deps.db_path, product, size)

    @agent.tool
    def show_products(ctx: RunContext[ShopDeps], product_ids: list[str]) -> ShownProducts:
        """Show these products as cards (image, name, price, short description) on the website next to your reply.

        Call this once, right before your final answer, whenever your answer recommends or discusses specific
        products. Most relevant first, at most 6. Only use product_ids that came from a tool result.

        Args:
            product_ids: product_id values, e.g. ["basic-hoodie-big-yale", "crew-left-chest-hoodie"].
        """
        result = tools.validate_card_ids(ctx.deps.db_path, product_ids)
        ctx.deps.shown_product_ids = [p.product_id for p in result.shown]
        return result

    @agent.tool
    def add_to_bag(ctx: RunContext[ShopDeps], product: str, size: str | None = None, quantity: int = 1) -> AddToBagResult:
        """Add a product to the shopper's bag after checking live stock. Only call when the shopper asks you to add/buy something.

        If they don't name a size, use their 'Shop my size' size if set; otherwise call with size=None and the
        result tells you which sizes to offer. Never add a size that is sold out. Relay `message`.

        Args:
            product: product_id (preferred) or product name.
            size: XS, S, M, L, XL, XXL (words like "medium" work).
            quantity: 1-10.
        """
        result, line = tools.add_to_bag(
            ctx.deps.db_path, [*ctx.deps.bag, *ctx.deps.bag_additions], product, size, quantity
        )
        if line:
            ctx.deps.bag_additions.append(line)
            if line.product_id not in ctx.deps.shown_product_ids:
                ctx.deps.shown_product_ids.append(line.product_id)
        return result

    @agent.output_validator
    def verify_prices_and_stock(ctx: RunContext[ShopDeps], output: str) -> str:
        """Price & stock fact-checker: every $ amount and stock count in the reply must match the database
        numbers returned by tools in this turn; otherwise the reply goes back to the model to fix."""
        check, problems = _fact_check(ctx.messages, output, ctx.prompt if isinstance(ctx.prompt, str) else "")
        if problems:
            ctx.deps.fact_check_retries += 1
            raise ModelRetry(
                "Fact check failed: " + "; ".join(problems) + ". Only quote prices and stock counts that a tool "
                "returned in this turn (call get_product_info / check_stock if needed), then rewrite your answer."
            )
        check.retries = ctx.deps.fact_check_retries
        ctx.deps.fact_check = check
        return output

    return agent


def to_message_history(history: list[ChatTurn]) -> list[ModelMessage]:
    """Rebuild earlier turns (sent by the website) as PydanticAI messages."""
    messages: list[ModelMessage] = []
    for turn in history:
        if turn.role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=turn.content)]))
        else:
            messages.append(ModelResponse(parts=[TextPart(content=turn.content)]))
    return messages


def summarize_usage(usage: RunUsage) -> UsageSummary:
    # PydanticAI's input_tokens already includes cache reads and writes; split them back out.
    read, write = usage.cache_read_tokens, usage.cache_write_tokens
    uncached = max(usage.input_tokens - read - write, 0)
    p_in, p_out, p_read = PRICES.get(model_name(), (0.0, 0.0, 0.0))
    cost = (uncached * p_in + usage.output_tokens * p_out + read * p_read + write * p_in * 1.25) / 1e6
    return UsageSummary(
        model=model_name(),
        effort=effort() or "default",
        requests=usage.requests,
        tool_calls=usage.tool_calls,
        input_tokens=uncached,
        cache_read_tokens=read,
        cache_write_tokens=write,
        output_tokens=usage.output_tokens,
        est_cost_usd=round(cost, 6),
    )


def log_usage(message: str, run: ChatRun) -> None:
    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "message": audit_short(message),  # redacted, like the audit trail
        "seconds": run.seconds,
        **run.usage.model_dump(),  # includes tool_calls = how many
        "tools_called": run.tool_calls,  # which ones, with arguments (kept separate so it isn't overwritten)
    }
    with _log_lock:
        USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        try:
            rows = json.loads(USAGE_LOG.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            rows = []
        rows.append(entry)
        USAGE_LOG.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def _format_call(part: ToolCallPart) -> str:
    args = part.args_as_dict() or {}
    return f"{part.tool_name}(" + ", ".join(f"{k}={v!r}" for k, v in args.items()) + ")"


def _tool_numbers(messages: list[ModelMessage]) -> tuple[set[float], set[float]]:
    """(all numbers, prices) returned by tools in these messages: the database facts for this turn."""
    numbers: set[float] = set()
    prices: set[float] = set()
    for m in messages:
        for p in getattr(m, "parts", []):
            if isinstance(p, ToolReturnPart):
                tools.collect_numbers(p.content, numbers)
                content = p.content.model_dump() if hasattr(p.content, "model_dump") else p.content
                _collect_prices(content, prices)
    return numbers, prices


def _collect_prices(value, out: set[float]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            if k in ("price", "unit_price", "product_price") and isinstance(v, (int, float)):
                out.add(float(v))
            else:
                _collect_prices(v, out)
    elif isinstance(value, list):
        for v in value:
            _collect_prices(v, out)


def _fact_check(messages: list[ModelMessage], text: str, user_text: str):
    numbers, prices = _tool_numbers(messages)
    return tools.fact_check(text, numbers, prices, user_text)


def pick_reply(messages: list[ModelMessage], final_text: str) -> str:
    """The shopper-facing answer.

    Usually the model's final text. But a model sometimes writes its full answer in the same step
    as the show_products call, then adds a second message about the first ("My last reply went
    through..."), and only that second message would reach the shopper. In that case use the
    answer written with show_products.
    """
    for m in messages:
        if isinstance(m, ModelResponse) and any(
            isinstance(p, ToolCallPart) and p.tool_name == "show_products" for p in m.parts
        ):
            text = "".join(p.content for p in m.parts if isinstance(p, TextPart)).strip()
            # only use it if it also passes the fact-checker (the final text already did)
            if len(text) > 40 and not _fact_check(messages, text, "")[1]:
                return text
    return final_text.strip()


# ======================================================================
# Audit trail (Problem 12): append-only output/audit_trail.json of agent-loop activity.
#   run_start / tool_call / retry / final_answer / error, with time (UTC), tool name,
#   short redacted args/result, and stop reason. Never wiped; written atomically.
# ======================================================================
AUDIT_PATH = Path(os.getenv("AUDIT_TRAIL", BACKEND_DIR.parent / "output" / "audit_trail.json"))
AUDIT_SHORT = 200  # max characters kept for args / results / messages
_audit_lock = threading.Lock()

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_LONG_NUMBER = re.compile(r"\b\d[\d -]{7,}\d\b")


def audit_short(value, limit: int = AUDIT_SHORT) -> str:
    """Compact, redacted one-line text."""
    if hasattr(value, "model_dump"):
        value = value.model_dump(exclude_none=True)
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = _LONG_NUMBER.sub("[number redacted]", _EMAIL.sub("[email redacted]", " ".join(text.split())))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")  # all audit times in UTC


def audit_now() -> str:
    """Public: when a run starts (so run_start is stamped before its steps)."""
    return _utc_now()


def new_run_id() -> str:
    return uuid.uuid4().hex[:8]


def audit_entries_for_run(
    run_id: str,
    message: str,
    new_messages: list[ModelMessage],
    customer: CustomerProfile | None,
    page: PageContext | None,
    model: str,
    error: Exception | None = None,
    started_at: str | None = None,
) -> list[AuditEntry]:
    who = f"customer #{customer.user_id}" if customer else "guest"
    rows = [
        AuditEntry(
            time=started_at or _utc_now(),
            run_id=run_id,
            who=who,
            iteration=0,
            event="run_start",
            args=audit_short({"message": message, "page": page.path if page else None, "model": model}),
        )
    ]

    # Tool results and retry prompts come back in the *next* request; index them by tool_call_id / step.
    returns: dict[str, str] = {}
    retries: dict[int, str] = {}
    step = 0
    for m in new_messages:
        if isinstance(m, ModelResponse):
            step += 1
        elif isinstance(m, ModelRequest):
            for p in m.parts:
                if isinstance(p, ToolReturnPart):
                    returns[p.tool_call_id] = audit_short(p.content)
                elif isinstance(p, RetryPromptPart):
                    retries[step] = audit_short(p.content if isinstance(p.content, str) else p.model_response())

    step = 0
    for m in new_messages:
        if not isinstance(m, ModelResponse):
            continue
        step += 1
        when = m.timestamp.astimezone(timezone.utc).isoformat(timespec="seconds") if m.timestamp else _utc_now()
        stop = m.finish_reason or "unknown"
        calls = [p for p in m.parts if isinstance(p, ToolCallPart)]
        text = "".join(p.content for p in m.parts if isinstance(p, TextPart)).strip()
        for c in calls:
            rows.append(AuditEntry(
                time=when, run_id=run_id, who=who, iteration=step, event="tool_call", tool=c.tool_name,
                args=audit_short(c.args_as_dict() or {}), result=returns.get(c.tool_call_id, "(no result)"),
                stop_reason=stop,
            ))
        if text and not calls:
            if step in retries:  # this reply was rejected and sent back to the model
                kind = "fact-check" if "Fact check failed" in retries[step] else "output validation"
                rows.append(AuditEntry(
                    time=when, run_id=run_id, who=who, iteration=step, event="retry",
                    result=audit_short(text), stop_reason=f"{kind} retry: {retries[step]}",
                ))
            else:
                rows.append(AuditEntry(
                    time=when, run_id=run_id, who=who, iteration=step, event="final_answer",
                    result=audit_short(text), stop_reason="final answer" if stop in ("stop", "unknown") else stop,
                ))

    if error is not None:
        name = type(error).__name__
        reason = "usage limit hit" if name == "UsageLimitExceeded" else f"error: {name}"
        rows.append(AuditEntry(
            time=_utc_now(), run_id=run_id, who=who, iteration=step + 1,
            event="error", result=audit_short(str(error)), stop_reason=reason,
        ))
    return rows


def audit_append(entries: list[AuditEntry]) -> None:
    """Append entries; never wipe what's already there."""
    with _audit_lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing: list = []
        if AUDIT_PATH.exists():
            try:
                existing = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
                if not isinstance(existing, list):
                    raise ValueError("audit trail is not a list")
            except (ValueError, json.JSONDecodeError):
                # Don't overwrite a damaged file: keep it beside the new one for inspection.
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                AUDIT_PATH.replace(AUDIT_PATH.with_name(f"audit_trail.corrupt-{stamp}.json"))
                existing = []
        existing.extend(e.model_dump(exclude_none=True) for e in entries)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(existing, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, AUDIT_PATH)  # atomic swap: a crash mid-write can't truncate the trail


async def run_chat(
    message: str,
    history: list[ChatTurn],
    customer: CustomerProfile | None = None,
    page: PageContext | None = None,
    bag: list[BagLine] | None = None,
    my_size: str | None = None,
) -> ChatRun:
    deps = ShopDeps(
        db_path=tools.DB_PATH,
        customer=customer,
        page=page,
        bag=list(bag or []),
        my_size=my_size,
    )
    started = time.perf_counter()
    earlier = to_message_history(history)
    run_id, started_at = new_run_id(), audit_now()
    # Audit trail: record every loop step, including runs that fail (e.g. the request cap is hit).
    with capture_run_messages() as captured:
        try:
            result = await build_agent().run(
                message,
                deps=deps,
                message_history=earlier,
                usage_limits=CHAT_USAGE_LIMITS,
            )
        except Exception as e:
            audit_append(audit_entries_for_run(run_id, message, captured[len(earlier):], customer, page, model_name(), e, started_at))
            raise
    audit_append(audit_entries_for_run(run_id, message, result.new_messages(), customer, page, model_name(), None, started_at))
    calls = [
        _format_call(p)
        for m in result.new_messages()
        if isinstance(m, ModelResponse)
        for p in m.parts
        if isinstance(p, ToolCallPart)
    ]
    run = ChatRun(
        output=ShopReply(reply=pick_reply(result.new_messages(), result.output), product_ids=deps.shown_product_ids),
        usage=summarize_usage(result.usage),
        tool_calls=calls,
        seconds=round(time.perf_counter() - started, 1),
        bag_additions=deps.bag_additions,
        fact_check=deps.fact_check,
    )
    log_usage(message, run)
    return run
