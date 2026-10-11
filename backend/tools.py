"""Catalogue tools for Campus Customs.

These read-only functions are used two ways:
  - main.py serves them to the website (/api/products, /api/products/{id})
  - agent.py registers search_catalogue / product_info / stock_check as the agent's tools

The database is always opened read-only here, so neither the website's catalogue
routes nor the agent can change products, stock, or users.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from models import (
    LookupMiss,
    ProductDetail,
    ProductInfo,
    ProductMatch,
    ProductSearchResult,
    ProductSummary,
    AddToBagResult,
    BagLine,
    FactCheck,
    ShownCard,
    ShownProducts,
    SizeStock,
    StockCheck,
)

BACKEND_DIR = Path(__file__).resolve().parent
ROOT = BACKEND_DIR.parent  # the hw4 project folder
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "campus_customs.db"
IMAGES_DIR = DATA_DIR / "products"

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]
LOW_STOCK = 5  # at or below this many units a size counts as "low stock"
MAX_SEARCH_RESULTS = 6  # matches the 6-card limit on a reply; keeps tool output small

CATEGORIES = ["Hoodies", "Crewnecks", "T-Shirts", "Quarter-zips", "Fleece & Jackets", "Long Sleeve"]


# ---------- Database helpers ----------

def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open the database read-only."""
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def category_for(garment_type: str) -> str:
    """Collapse the 22 inconsistent garment_type spellings into a few shop categories."""
    g = garment_type.lower()
    if "quarter-zip" in g:
        return "Quarter-zips"
    if "fleece" in g or "jacket" in g:
        return "Fleece & Jackets"
    if "hood" in g:
        return "Hoodies"
    if "crewneck" in g or "mockneck" in g:
        return "Crewnecks"
    if "long-sleeve" in g:
        return "Long Sleeve"
    if "t-shirt" in g:
        return "T-Shirts"
    return "Other"


def short_text(text: str, limit: int = 110) -> str:
    """First ~110 characters, cut on a word boundary."""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


IMAGE_VERSION = "white-bg-1"  # bump when the photos change, so browsers fetch the new versions


def image_url(image_file_path: str) -> str:
    # catalogue.image_file_path is relative to data/ (e.g. "products/x.jpg"); main.py serves the photos at /images
    return f"/images/{Path(image_file_path).name}?v={IMAGE_VERSION}"


def size_status(quantity: int) -> str:
    if quantity == 0:
        return "sold_out"
    if quantity <= LOW_STOCK:
        return "low"
    return "in_stock"


PRODUCT_QUERY = """
    SELECT c.*,
           COALESCE(SUM(i.quantity), 0)                          AS total_stock,
           COALESCE(SUM(CASE WHEN i.quantity > 0 THEN 1 END), 0) AS sizes_in_stock,
           COUNT(i.id)                                           AS sizes_total,
           GROUP_CONCAT(i.size || ':' || i.quantity)             AS stock_pairs
    FROM catalogue c
    LEFT JOIN inventory i ON i.product_id = c.product_id
"""


def summary_from_row(row: sqlite3.Row) -> ProductSummary:
    return ProductSummary(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        category=category_for(row["garment_type"]),
        short_description=short_text(row["description"]),
        price=row["price"],
        colors=json.loads(row["colors"]),
        image_url=image_url(row["image_file_path"]),
        total_stock=row["total_stock"],
        sizes_in_stock=row["sizes_in_stock"],
        sizes_total=row["sizes_total"],
        stock_by_size={
            size: int(qty)
            for size, qty in sorted(
                (pair.split(":") for pair in (row["stock_pairs"] or "").split(",") if ":" in pair),
                key=lambda sq: SIZE_ORDER.index(sq[0]) if sq[0] in SIZE_ORDER else 99,
            )
        },
    )


# ---------- Catalogue queries (website + agent) ----------

def list_products(q: str | None = None, db_path: Path = DB_PATH) -> list[ProductSummary]:
    sql, params = PRODUCT_QUERY, []
    if q:
        sql += " WHERE c.name LIKE ? OR c.description LIKE ? OR c.search_tags LIKE ? OR c.garment_type LIKE ?"
        params = [f"%{q}%"] * 4
    sql += " GROUP BY c.product_id ORDER BY c.name"
    with connect(db_path) as conn:
        return [summary_from_row(r) for r in conn.execute(sql, params).fetchall()]


def get_products_by_ids(product_ids: list[str], db_path: Path = DB_PATH) -> list[ProductSummary]:
    """Product cards for the given IDs, in the same order; unknown IDs are dropped."""
    if not product_ids:
        return []
    marks = ",".join("?" * len(product_ids))
    with connect(db_path) as conn:
        rows = conn.execute(
            PRODUCT_QUERY + f" WHERE c.product_id IN ({marks}) GROUP BY c.product_id", product_ids
        ).fetchall()
    by_id = {r["product_id"]: summary_from_row(r) for r in rows}
    return [by_id[pid] for pid in dict.fromkeys(product_ids) if pid in by_id]


def get_product_detail(product_id: str, db_path: Path = DB_PATH) -> ProductDetail | None:
    with connect(db_path) as conn:
        row = conn.execute(PRODUCT_QUERY + " WHERE c.product_id = ? GROUP BY c.product_id", (product_id,)).fetchone()
        if row is None:
            return None
        stock = conn.execute("SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)).fetchall()

    sizes = sorted(
        (SizeStock(size=s["size"], quantity=s["quantity"], status=size_status(s["quantity"])) for s in stock),
        key=lambda s: SIZE_ORDER.index(s.size) if s.size in SIZE_ORDER else len(SIZE_ORDER),
    )
    return ProductDetail(
        **summary_from_row(row).model_dump(),
        description=row["description"],
        search_tags=json.loads(row["search_tags"]),
        sizes=sizes,
    )


# ---------- Agent tool logic (Problem 6) ----------
# Each tool returns a typed model from models.py with only the facts the agent
# needs: no user data, no file paths. Every number comes straight from the database.

SIZE_ALIASES = {
    "XS": ["xs", "x-small", "x small", "xsmall", "extra small", "extra-small"],
    "S": ["s", "sm", "small"],
    "M": ["m", "med", "medium"],
    "L": ["l", "lg", "large"],
    "XL": ["xl", "x-large", "x large", "xlarge", "extra large", "extra-large"],
    "XXL": ["xxl", "2xl", "2x", "xx-large", "xx large", "xxlarge", "double xl", "extra extra large"],
}
_SIZE_LOOKUP = {alias: size for size, aliases in SIZE_ALIASES.items() for alias in aliases}


# Shopper words -> the catalogue's wording (the catalogue says "gray" and "t-shirt").
KEYWORD_SYNONYMS = {
    "grey": "gray",
    "tee": "t-shirt",
    "tees": "t-shirt",
    "tshirt": "t-shirt",
    "tshirts": "t-shirt",
    "t-shirts": "t-shirt",
    "hoody": "hoodie",
    "hoodies": "hoodie",
    "crew": "crewneck",
    "crewnecks": "crewneck",
    "quarterzip": "quarter-zip",
    "1/4": "quarter-zip",
    "sweatshirts": "sweatshirt",
}


def _keyword_patterns(keywords: str) -> list[re.Pattern]:
    """Each word must match at the START of a word in the product text, so "tshirt" can't match
    inside "sweatshirt", while "hood" still matches "hoodie" and "hoodies"."""
    words = [w for w in keywords.lower().replace(",", " ").split() if len(w) > 1]
    words = [KEYWORD_SYNONYMS.get(w, w) for w in words]
    return [re.compile(r"(?<![a-z0-9])" + re.escape(w.rstrip("s") if len(w) > 3 else w)) for w in words]


def normalize_size(size: str) -> str | None:
    """'medium' -> 'M', '2XL' -> 'XXL'. Returns None for sizes the shop doesn't carry (e.g. 3XL)."""
    return _SIZE_LOOKUP.get(" ".join(size.lower().replace("_", " ").split()))


def _sizes_in_stock(product_ids: list[str], db_path: Path) -> dict[str, list[str]]:
    if not product_ids:
        return {}
    marks = ",".join("?" * len(product_ids))
    with connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT product_id, size FROM inventory WHERE quantity > 0 AND product_id IN ({marks})", product_ids
        ).fetchall()
    out: dict[str, list[str]] = {pid: [] for pid in product_ids}
    for pid, size in rows:
        out[pid].append(size)
    return {pid: sorted(sizes, key=SIZE_ORDER.index) for pid, sizes in out.items()}


def _to_matches(
    products: list[ProductSummary], db_path: Path, size_units: dict[str, int] | None = None
) -> list[ProductMatch]:
    stock = _sizes_in_stock([p.product_id for p in products], db_path)
    return [
        ProductMatch(
            product_id=p.product_id,
            name=p.name,
            category=p.category,
            price=p.price,
            main_color=p.colors[0] if p.colors else None,
            colors=p.colors,
            sizes_in_stock=stock.get(p.product_id, []),
            units_in_requested_size=size_units.get(p.product_id) if size_units else None,
        )
        for p in products
    ]


def search_catalogue(
    db_path: Path,
    keywords: str = "",
    category: str | None = None,
    color: str | None = None,
    max_price: float | None = None,
    size_in_stock: str | None = None,
) -> ProductSearchResult:
    """Filter the catalogue; every keyword must appear in name, description, tags, garment type, or colors."""
    patterns = _keyword_patterns(keywords)
    color = KEYWORD_SYNONYMS.get(color.lower(), color.lower()) if color else None
    with connect(db_path) as conn:
        extra_text = {
            r[0]: (r[1] + " " + r[2]).lower()
            for r in conn.execute("SELECT product_id, search_tags, description FROM catalogue")
        }

    matches = []
    for p in list_products(db_path=db_path):
        if category and p.category.lower() != category.lower():
            continue
        # "navy hoodie" = a hoodie that IS navy: match the garment's main color (first listed), not a logo color
        if color and not (p.colors and color in p.colors[0].lower()):
            continue
        if max_price is not None and p.price > max_price:
            continue
        text = " ".join([p.name, p.garment_type, p.category, " ".join(p.colors), extra_text[p.product_id]]).lower()
        if not all(pat.search(text) for pat in patterns):
            continue
        matches.append(p)

    if size_in_stock:
        size = normalize_size(size_in_stock)
        if size is None:
            return ProductSearchResult(
                total_matches=0,
                products=[],
                note=f"'{size_in_stock}' is not a size we carry. Sizes are XS, S, M, L, XL, XXL.",
            )
        with connect(db_path) as conn:
            size_units = {
                r[0]: r[1] for r in conn.execute("SELECT product_id, quantity FROM inventory WHERE size = ?", (size,))
            }
        # Only items with that size in stock, most units first (answers "which has the most left?" in one call).
        matches = sorted(
            (p for p in matches if size_units.get(p.product_id, 0) > 0),
            key=lambda p: -size_units[p.product_id],
        )
    else:
        size_units = None

    note = None
    if len(matches) > MAX_SEARCH_RESULTS:
        note = f"Showing the first {MAX_SEARCH_RESULTS} of {len(matches)}. Narrow with category, color, or max_price."
    elif not matches:
        note = "No products matched. Try fewer keywords or drop a filter."
    return ProductSearchResult(
        total_matches=len(matches),
        products=_to_matches(matches[:MAX_SEARCH_RESULTS], db_path, size_units),
        note=note,
    )


def resolve_product(db_path: Path, product: str) -> str | LookupMiss:
    """Accept a product_id or a product name; return the product_id, or a LookupMiss with suggestions."""
    key = product.strip()
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT product_id FROM catalogue WHERE product_id = ? OR lower(name) = lower(?)", (key, key)
        ).fetchone()
        if row:
            return row[0]
        like = conn.execute(
            "SELECT product_id FROM catalogue WHERE name LIKE ? OR product_id LIKE ?",
            (f"%{key}%", f"%{key.replace(' ', '-')}%"),
        ).fetchall()
    if len(like) == 1:
        return like[0][0]
    candidates = get_products_by_ids([r[0] for r in like[:5]], db_path)
    if not candidates:  # fall back to products whose name contains every word given
        words = [w for w in key.lower().replace("-", " ").split() if len(w) > 2]
        candidates = [p for p in list_products(db_path=db_path) if words and all(w in p.name.lower() for w in words)][:5]
    return LookupMiss(
        error=f"No exact product match for '{product}'. Use a product_id from did_you_mean or call search_products.",
        did_you_mean=_to_matches(candidates, db_path),
    )


def product_info(db_path: Path, product: str) -> ProductInfo | LookupMiss:
    pid = resolve_product(db_path, product)
    if isinstance(pid, LookupMiss):
        return pid
    d = get_product_detail(pid, db_path)
    return ProductInfo(
        product_id=d.product_id,
        name=d.name,
        garment_type=d.garment_type,
        price=d.price,
        main_color=d.colors[0] if d.colors else None,
        colors=d.colors,
        description=d.description,
    )


def stock_check(db_path: Path, product: str, size: str | None = None) -> StockCheck | LookupMiss:
    pid = resolve_product(db_path, product)
    if isinstance(pid, LookupMiss):
        return pid
    d = get_product_detail(pid, db_path)
    in_stock = [s.size for s in d.sizes if s.quantity > 0]
    sold_out = [s.size for s in d.sizes if s.quantity == 0]
    in_stock_text = ", ".join(in_stock) if in_stock else "none"

    requested = qty = status = None
    if size:
        requested = normalize_size(size)
        if requested is None:
            requested, status = size, "not_offered"
            answer = f"We don't carry size '{size}'. {d.name} comes in XS-XXL; in stock now: {in_stock_text}."
        else:
            row = next(s for s in d.sizes if s.size == requested)
            qty, status = row.quantity, row.status
            if qty == 0:
                answer = f"{d.name} is SOLD OUT in size {requested}. In stock sizes: {in_stock_text}."
            elif status == "low":
                answer = f"{d.name} has only {qty} left in size {requested} (low stock)."
            else:
                answer = f"{d.name} is in stock in size {requested}: {qty} available."
    else:
        answer = f"{d.name}: in stock in {in_stock_text}" + (
            f"; SOLD OUT in {', '.join(sold_out)}." if sold_out else "; every size is in stock."
        )

    return StockCheck(
        product_id=d.product_id,
        name=d.name,
        price=d.price,
        stock_by_size=d.sizes,
        in_stock_sizes=in_stock,
        sold_out_sizes=sold_out,
        total_units=d.total_stock,
        requested_size=requested,
        requested_size_quantity=qty,
        requested_size_status=status,
        answer=answer,
    )


MAX_CARDS = 6


def validate_card_ids(db_path: Path, product_ids: list[str]) -> ShownProducts:
    """Keep only real product_ids (in order, no repeats, at most 6) for the website's product cards."""
    wanted = list(dict.fromkeys(product_ids))
    found = {p.product_id: p for p in get_products_by_ids(wanted, db_path)}
    shown = [ShownCard(product_id=pid, name=found[pid].name, price=found[pid].price) for pid in wanted if pid in found]
    return ShownProducts(shown=shown[:MAX_CARDS], rejected_ids=[pid for pid in wanted if pid not in found])


# ---------- Shopping bag (Problem 9) ----------

MAX_PER_LINE = 10


def bag_subtotal(bag: list[BagLine], db_path: Path = DB_PATH) -> tuple[int, float]:
    """(units, subtotal) at current catalogue prices."""
    prices = {p.product_id: p.price for p in get_products_by_ids([b.product_id for b in bag], db_path)}
    units = sum(b.quantity for b in bag if b.product_id in prices)
    return units, round(sum(prices[b.product_id] * b.quantity for b in bag if b.product_id in prices), 2)


def add_to_bag(db_path: Path, bag: list[BagLine], product: str, size: str | None, quantity: int = 1) -> tuple[AddToBagResult, BagLine | None]:
    """Validate against live stock and return (result, line to add). `bag` = current bag incl. earlier additions."""
    pid = resolve_product(db_path, product)
    if isinstance(pid, LookupMiss):
        names = ", ".join(m.name for m in pid.did_you_mean[:3])
        return AddToBagResult(added=False, message=f"I couldn't tell which product '{product}' is." + (f" Did you mean: {names}?" if names else "")), None
    d = get_product_detail(pid, db_path)
    if not size:
        return AddToBagResult(added=False, product_id=pid, name=d.name, unit_price=d.price,
                              message=f"Which size of the {d.name}? In stock: {', '.join(s.size for s in d.sizes if s.quantity) or 'none'}."), None
    code = normalize_size(size)
    if code is None:
        return AddToBagResult(added=False, product_id=pid, name=d.name, unit_price=d.price,
                              message=f"We don't carry size '{size}'. Sizes run XS-XXL."), None
    quantity = max(1, min(int(quantity), MAX_PER_LINE))
    stock = next(s.quantity for s in d.sizes if s.size == code)
    already = sum(b.quantity for b in bag if b.product_id == pid and b.size == code)
    units, subtotal = bag_subtotal(bag, db_path)
    base = dict(product_id=pid, name=d.name, size=code, unit_price=d.price, units_in_stock=stock,
                now_in_bag=already, bag_items=units, bag_subtotal=subtotal)
    if stock == 0:
        return AddToBagResult(added=False, message=f"The {d.name} is sold out in {code}, so I can't add it.", **base), None
    if already + quantity > min(stock, MAX_PER_LINE):
        room = max(min(stock, MAX_PER_LINE) - already, 0)
        return AddToBagResult(added=False, message=(
            f"Only {stock} of the {d.name} in {code} are in stock and you already have {already} in your bag"
            + (f"; I can add up to {room} more." if room else ", so I can't add more.")), **base), None
    line = BagLine(product_id=pid, size=code, quantity=quantity)
    units, subtotal = bag_subtotal([*bag, line], db_path)
    return AddToBagResult(
        added=True, quantity_added=quantity,
        message=f"Added {quantity} x {d.name} ({code}, ${d.price:.0f} each) to the bag. Bag: {units} item(s), ${subtotal:.2f}.",
        **{**base, "now_in_bag": already + quantity, "bag_items": units, "bag_subtotal": subtotal},
    ), line


# ---------- Price & stock fact-checker (Problem 9) ----------

PRICE_RE = re.compile(r"\$\s?(\d{1,5}(?:,\d{3})*(?:\.\d{1,2})?)")
STOCK_RE = re.compile(
    r"\b(\d{1,4})\s+(?:(?:units?|pieces?|of them)\s+)?(?:left|available|in stock|remaining)\b"
    r"|\bonly\s+(\d{1,4})\b"
    r"|\b(\d{1,4})\s+(?:units?\s+)?in\s+(?:size\s+)?(?:XXL|XL|XS|S|M|L)\b"
    # size-labelled counts: "S (15)", "M: 5", "L - 25" (found missing in the Problem 11 app check)
    r"|\b(?:XXL|XL|XS|S|M|L)\s*(?:\(|:|-|–)\s*(\d{1,4})\b"
)


def collect_numbers(value, out: set[float] | None = None) -> set[float]:
    """Every number inside a tool result (nested models / dicts / lists)."""
    out = set() if out is None else out
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, bool):
        return out
    if isinstance(value, (int, float)):
        out.add(round(float(value), 2))
    elif isinstance(value, dict):
        for v in value.values():
            collect_numbers(v, out)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            collect_numbers(v, out)
    elif isinstance(value, str):
        out.update(round(float(n), 2) for n in re.findall(r"\d+(?:\.\d+)?", value))
    return out


def fact_check(reply: str, tool_numbers: set[float], prices_seen: set[float], user_text: str) -> tuple[FactCheck, list[str]]:
    """Check every $ amount and stock count in the reply against numbers the tools returned this turn.

    Allowed prices: any price/total from a tool, a price x 1-10 (e.g. "two for $136"), or a number the
    shopper typed ("under $40"). Allowed stock counts: any number a tool returned this turn.
    """
    user_numbers = collect_numbers(user_text)
    allowed_prices = tool_numbers | user_numbers | {round(p * k, 2) for p in prices_seen for k in range(1, 11)}
    problems = []
    prices = [float(m.replace(",", "")) for m in PRICE_RE.findall(reply)]
    for p in prices:
        if round(p, 2) not in allowed_prices:
            problems.append(f"${p:g} does not match any price returned by your tools this turn")
    stock = [int(next(g for g in m if g)) for m in STOCK_RE.findall(reply)]
    for n in stock:
        if float(n) not in tool_numbers | user_numbers:
            problems.append(f"the stock count {n} does not match any quantity returned by your tools this turn")
    return FactCheck(prices_checked=len(prices), stock_counts_checked=len(stock)), problems
