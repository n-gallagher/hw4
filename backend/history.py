"""Customer memory (Problem 8): saved chat history for logged-in shoppers.

Stored in the existing `chat_messages` table, one row per message:
    id, user_id -> users.id, role ('user' | 'assistant'), content,
    products_json (cards shown with an assistant reply), created_at,
    page_path (added here: the page a shopper message was sent from, e.g. /products/<id>)

Guests are never saved; their history lives only in the browser tab.
"""

from __future__ import annotations

import json
import sqlite3

import tools
from models import ChatTurn, HistoryMessage, PageContext

AGENT_HISTORY_MESSAGES = 20  # earlier messages the agent sees (10 exchanges): enough memory, bounded cost
PAGE_HISTORY_MESSAGES = 50  # messages restored into the chat panel when a shopper returns


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(tools.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema() -> None:
    """Safe to run every startup: add the page_path column (once) and an index for
    fast "latest messages for this user" lookups. Existing rows are untouched."""
    with _connect() as conn:
        columns = {r[1] for r in conn.execute("PRAGMA table_info(chat_messages)")}
        if "page_path" not in columns:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN page_path TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages(user_id, id)")


def _page_note(page_path: str | None) -> str:
    """'(asked on the product page for "X")' so old questions about "this" keep their meaning."""
    if not page_path:
        return ""
    if page_path.startswith("/products/"):
        product = tools.get_product_detail(page_path.removeprefix("/products/"))
        if product:
            return f'(asked on the product page for "{product.name}", product_id {product.product_id}) '
    return f"(asked on {page_path}) "


def _product_ids(products_json: str | None) -> list[str]:
    if not products_json:
        return []
    try:
        return [p["product_id"] for p in json.loads(products_json) if isinstance(p, dict) and "product_id" in p]
    except (ValueError, TypeError):
        return []


def _latest(user_id: int, limit: int) -> list[sqlite3.Row]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, role, content, products_json, page_path, created_at FROM chat_messages "
            "WHERE user_id = ? AND role IN ('user', 'assistant') ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return list(reversed(rows))


def load_for_agent(user_id: int) -> list[ChatTurn]:
    """Recent turns for the agent's message history. Product ids shown earlier are noted so
    follow-ups like "is the first one in medium?" still resolve."""
    turns = []
    for r in _latest(user_id, AGENT_HISTORY_MESSAGES):
        content = r["content"]
        ids = _product_ids(r["products_json"])
        if r["role"] == "user":
            content = _page_note(r["page_path"]) + content
        elif ids:
            content += f"\n[Products shown: {', '.join(ids)}]"
        turns.append(ChatTurn(role=r["role"], content=content[:4000]))
    # message history must start with the shopper speaking
    while turns and turns[0].role != "user":
        turns.pop(0)
    return turns


def load_for_page(user_id: int) -> list[HistoryMessage]:
    """Messages for the chat panel; cards are rebuilt from the catalogue so prices and stock are current."""
    rows = _latest(user_id, PAGE_HISTORY_MESSAGES)
    all_ids = list(dict.fromkeys(pid for r in rows for pid in _product_ids(r["products_json"])))
    cards = {p.product_id: p for p in tools.get_products_by_ids(all_ids)}
    return [
        HistoryMessage(
            role=r["role"],
            content=r["content"],
            products=[cards[pid] for pid in _product_ids(r["products_json"]) if pid in cards],
            created_at=r["created_at"],
        )
        for r in rows
    ]


def save_exchange(user_id: int, question: str, reply: str, product_ids: list[str], page: PageContext | None) -> None:
    """Save one shopper message (with the page it was sent from) and the assistant's reply (with its cards)."""
    cards = tools.get_products_by_ids(product_ids)
    snapshot = json.dumps([{"product_id": p.product_id, "name": p.name, "price": p.price} for p in cards]) if cards else None
    with _connect() as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, page_path) VALUES (?, 'user', ?, ?)",
            (user_id, question, page.path if page else None),
        )
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, 'assistant', ?, ?)",
            (user_id, reply, snapshot),
        )


def message_count(user_id: int) -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM chat_messages WHERE user_id = ?", (user_id,)).fetchone()[0]
