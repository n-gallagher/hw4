"""Pydantic / PydanticAI structured types for the Campus Customs backend.

Grouped as:
  - Catalogue types   (what the API and agent tools return about products)
  - Chat API types    (what the website sends / receives)
  - Agent types       (the agent's structured output + its run-time dependencies)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

StockStatus = Literal["in_stock", "low", "sold_out"]  # low = 1–5 units


# ---------- Catalogue types ----------

class SizeStock(BaseModel):
    size: str
    quantity: int
    status: StockStatus


class ProductSummary(BaseModel):
    """One product card: what the Products page and chat product cards show."""

    product_id: str
    name: str
    garment_type: str
    category: str
    short_description: str
    price: float
    colors: list[str]
    image_url: str
    total_stock: int
    sizes_in_stock: int
    sizes_total: int
    stock_by_size: dict[str, int] = Field(default_factory=dict, description='Units per size, e.g. {"XS": 0, "M": 12}')


class ProductDetail(ProductSummary):
    """Full single-item page data, including stock for every size."""

    description: str
    search_tags: list[str]
    sizes: list[SizeStock]


# ---------- Agent tool return types (Problem 6) ----------
# Each lookup tool returns one of these, so the model gets a small, typed,
# predictable set of facts straight from campus_customs.db.

class ProductMatch(BaseModel):
    """One row of a search result: enough to pick a product, not the full detail."""

    product_id: str
    name: str
    category: str
    price: float
    main_color: str | None = Field(None, description="The garment's own color (each product is one colorway)")
    colors: list[str] = Field(description="Every color in the design (garment + lettering/graphics), NOT separate color options")
    sizes_in_stock: list[str] = Field(description="Sizes with at least 1 unit, in XS→XXL order")
    units_in_requested_size: int | None = Field(
        None, description="Units left in the size_in_stock size the search filtered on (results are sorted by this, most first)"
    )


class ProductSearchResult(BaseModel):
    total_matches: int = Field(description="How many products matched (may exceed the number shown)")
    products: list[ProductMatch]
    note: str | None = None


class ProductInfo(BaseModel):
    """get_product_info: description and price facts for one product."""

    product_id: str
    name: str
    garment_type: str
    price: float = Field(description="Price in US dollars, exactly as stored in the catalogue")
    main_color: str | None = Field(None, description="The garment's own color (each product is one colorway)")
    colors: list[str] = Field(description="Every color in the design (garment + lettering/graphics), NOT separate color options")
    description: str


SizeName = Literal["XS", "S", "M", "L", "XL", "XXL"]


class StockCheck(BaseModel):
    """check_stock: units on hand by size, plus a direct answer for one requested size."""

    product_id: str
    name: str
    price: float
    stock_by_size: list[SizeStock] = Field(description="Every size XS→XXL with quantity and status")
    in_stock_sizes: list[str]
    sold_out_sizes: list[str]
    total_units: int
    requested_size: str | None = Field(None, description="The size asked about, normalized (e.g. 'medium' → 'M')")
    requested_size_quantity: int | None = None
    requested_size_status: Literal["in_stock", "low", "sold_out", "not_offered"] | None = None
    answer: str = Field(description="One plain sentence stating the stock fact to relay to the shopper")


class ShownCard(BaseModel):
    product_id: str
    name: str
    price: float


class ShownProducts(BaseModel):
    """show_products: which cards will appear on the page, and which ids were rejected."""

    shown: list[ShownCard]
    rejected_ids: list[str] = Field(default_factory=list, description="Unknown ids that were dropped")


class LookupMiss(BaseModel):
    """Returned instead of ProductInfo / StockCheck when the product can't be identified."""

    error: str
    did_you_mean: list[ProductMatch] = []


# ---------- Shopping bag + fact check (Problem 9) ----------

SizeCode = Literal["XS", "S", "M", "L", "XL", "XXL"]


class BagLine(BaseModel):
    """One line in the shopper's bag (the bag itself lives in the browser and is sent with each chat message)."""

    product_id: str = Field(max_length=200)
    size: SizeCode
    quantity: int = Field(ge=1, le=10)


class BagAddition(BaseModel):
    """A line the agent added with add_to_bag, with the product card so the website can show it."""

    product: ProductSummary
    size: SizeCode
    quantity: int


class AddToBagResult(BaseModel):
    """add_to_bag: what happened, with the numbers to quote (all from the database)."""

    added: bool
    message: str = Field(description="One sentence to relay to the shopper")
    product_id: str | None = None
    name: str | None = None
    size: str | None = None
    quantity_added: int = 0
    unit_price: float | None = None
    units_in_stock: int | None = Field(None, description="Units of this size in stock right now")
    now_in_bag: int = Field(0, description="Units of this product+size in the bag after this call")
    bag_items: int = Field(0, description="Total units in the bag after this call")
    bag_subtotal: float = Field(0, description="Bag subtotal in dollars after this call, at current prices")


class FactCheck(BaseModel):
    """Result of the price & stock fact-checker on the final reply."""

    prices_checked: int
    stock_counts_checked: int
    retries: int = Field(0, description="Times a reply was sent back because a number didn't match the database")


# ---------- Chat API types ----------

class ChatTurn(BaseModel):
    """One earlier message, sent by the website so the agent remembers the conversation."""

    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    # Guests only: earlier turns kept in the browser. Logged-in shoppers' history is read from the database.
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    page_path: str | None = Field(None, max_length=200, description="URL path the shopper is on, e.g. /products/x")
    current_product_id: str | None = Field(None, max_length=200, description="Product page the shopper is viewing")
    bag: list[BagLine] = Field(default_factory=list, max_length=30, description="What's in the shopper's bag now")
    my_size: SizeCode | None = Field(None, description="The shopper's size from 'Shop my size' mode, if set")


class HistoryMessage(BaseModel):
    """One saved message, as restored into the chat panel (cards rebuilt from the catalogue)."""

    role: Literal["user", "assistant"]
    content: str
    products: list[ProductSummary] = []
    created_at: str


class ChatHistoryResponse(BaseModel):
    logged_in: bool
    messages: list[HistoryMessage] = []


# ---------------- Agent context (Problem 8) ----------------

class CustomerProfile(BaseModel):
    """Who is chatting: the only customer fields the agent sees (never the password hash)."""

    user_id: int
    first_name: str
    last_name: str
    email: str
    member_since: str = Field(description="Account creation date, YYYY-MM-DD")
    saved_messages: int = Field(description="Messages already in this shopper's saved chat history")


class PageContext(BaseModel):
    """Where the shopper is, built on the server from the page path + the catalogue (so it can't be faked)."""

    path: str = "/"
    page_name: str = Field(description='e.g. "Home", "Products", "Product page", "About Us"')
    product_id: str | None = None
    product_name: str | None = None
    product_main_color: str | None = None
    product_colors: list[str] = []
    product_price: float | None = None


class ChatResponse(BaseModel):
    """What /api/chat returns: the reply text plus product cards to show on the page."""

    reply: str
    products: list[ProductSummary] = []
    bag_additions: list[BagAddition] = []  # items the agent put in the bag (the website adds them and opens the bag)
    verified: FactCheck | None = None  # fact-checker result, shown as a badge on the reply


# ---------- Agent types ----------

class ShopReply(BaseModel):
    """One finished agent answer: the reply text plus the products picked with show_products.

    Built by agent.run_chat() (the agent replies in plain text and chooses cards via the
    show_products tool). The agent only picks product IDs; the server turns them into cards
    with prices and stock read fresh from the database, so a card can never show a made-up price.
    """

    reply: str = Field(description="Friendly answer to the shopper, in Campus Customs voice. Plain text, no markdown tables.")
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="product_id values (from tool results) to show as cards with this reply, most relevant first. Empty if none.",
    )


class AuditEntry(BaseModel):
    """One line of output/audit_trail.json (append-only): one step of one agent run."""

    time: str = Field(description="ISO timestamp of the step")
    run_id: str = Field(description="Groups the steps of one chat turn")
    who: str = Field(description='"guest" or "customer #<id>" (no names or emails)')
    iteration: int = Field(description="Agent-loop step: 0 = run start, then 1, 2, ... per model response")
    event: Literal["run_start", "tool_call", "retry", "final_answer", "error"]
    tool: str | None = None
    args: str | None = Field(None, description="Short, redacted tool arguments")
    result: str | None = Field(None, description="Short, redacted tool result / reply / error")
    stop_reason: str | None = Field(None, description="Why this step ended, e.g. tool_call, final answer, fact-check retry, usage limit")


class UsageSummary(BaseModel):
    """Tokens and estimated cost of one chat turn (logged to output/usage_log.json)."""

    model: str
    effort: str
    requests: int
    tool_calls: int
    input_tokens: int = Field(description="Uncached input tokens")
    cache_read_tokens: int
    cache_write_tokens: int
    output_tokens: int
    est_cost_usd: float


class ChatRun(BaseModel):
    """Everything one agent run produced: the reply plus what it cost and which tools it used."""

    output: ShopReply
    usage: UsageSummary
    tool_calls: list[str] = Field(description='e.g. "check_stock(product=\'x\', size=\'M\')"')
    seconds: float
    bag_additions: list[BagLine] = []
    fact_check: FactCheck | None = None


@dataclass
class ShopDeps:
    """Run-time context handed to every agent tool."""

    db_path: Path
    customer: CustomerProfile | None = None  # None = guest
    page: PageContext | None = None
    bag: list[BagLine] = field(default_factory=list)  # the shopper's bag (Problem 9)
    my_size: str | None = None  # from "Shop my size" mode
    shown_product_ids: list[str] = field(default_factory=list)  # set by the show_products tool
    bag_additions: list[BagLine] = field(default_factory=list)  # set by the add_to_bag tool
    fact_check: FactCheck | None = None  # set by the fact-checking output validator
    fact_check_retries: int = 0
