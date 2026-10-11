"""Campus Customs API (FastAPI).

Routes
  /api/products, /api/products/{id}   catalogue + stock for the website   (Problem 3)
  /images/...                         product photos                      (Problem 3)
  /api/auth/...                       create account / log in             (Problem 4, auth.py)
  /api/chat                           the PydanticAI shop agent           (Problem 5, agent.py)

Run from the backend/ folder:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import history
import images
import tools
from agent import model_label, run_chat
from auth import PublicUser, current_user
from auth import router as auth_router
from models import (
    BagAddition,
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    CustomerProfile,
    PageContext,
    ProductDetail,
    ProductSummary,
)

log = logging.getLogger("campus_customs")

app = FastAPI(title="Campus Customs API", version="0.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://{host}:{port}" for host in ("127.0.0.1", "localhost") for port in (5173, 5174)],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(auth_router)
history.ensure_schema()

# Product photos: white-background copies (images.py); only files from data/products, never the database.
images.start_background_cleaning()  # white-background copies of the product photos (made once)


@app.get("/images/{name}")
def product_image(name: str):
    """Product photo: the white-background copy when ready, else the original. Only files from
    data/products can be served (bare names, no paths), never the database."""
    path = images.photo_path(name)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "database": tools.DB_PATH.exists(), "model": model_label()}


@app.get("/api/products", response_model=list[ProductSummary])
def list_products(q: str | None = Query(None, description="Search name, description, tags")):
    return tools.list_products(q)


@app.get("/api/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: str):
    product = tools.get_product_detail(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


PAGE_NAMES = {"/": "Home", "/products": "Products", "/about": "About Us", "/login": "Log in",
              "/create-account": "Create account", "/account": "My account"}


def page_context(path: str | None, product_id: str | None) -> PageContext:
    """Build the page context on the server: the product's name/colors/price come from the catalogue."""
    path = (path or "/").split("?")[0][:200]
    if product_id is None and path.startswith("/products/"):
        product_id = path.removeprefix("/products/").strip("/") or None
    product = tools.get_product_detail(product_id) if product_id else None
    if product:
        return PageContext(
            path=path,
            page_name="Product page",
            product_id=product.product_id,
            product_name=product.name,
            product_main_color=product.colors[0] if product.colors else None,
            product_colors=product.colors,
            product_price=product.price,
        )
    return PageContext(path=path, page_name=PAGE_NAMES.get(path, "Other page"))


def customer_profile(user: PublicUser) -> CustomerProfile:
    with history._connect() as conn:  # noqa: SLF001
        created = conn.execute("SELECT created_at FROM users WHERE id = ?", (user.id,)).fetchone()[0]
    return CustomerProfile(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        member_since=(created or "")[:10],
        saved_messages=history.message_count(user.id),
    )


@app.get("/api/chat/history", response_model=ChatHistoryResponse)
def chat_history(request: Request):
    """Restore a logged-in shopper's saved chat when they return. Guests get an empty history."""
    user = current_user(request)
    if user is None:
        return ChatHistoryResponse(logged_in=False)
    return ChatHistoryResponse(logged_in=True, messages=history.load_for_page(user.id))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request):
    """Run the agent with WHO is chatting and WHICH page they're on; save the exchange for logged-in shoppers."""
    user = current_user(request)
    customer = customer_profile(user) if user else None
    # Logged in: memory comes from the database (survives reloads and new devices). Guest: from the browser.
    turns = history.load_for_agent(user.id) if user else body.history
    page = page_context(body.page_path, body.current_product_id)
    try:
        run = await run_chat(body.message, turns, customer=customer, page=page, bag=body.bag, my_size=body.my_size)
    except Exception:
        log.exception("Agent run failed")
        raise HTTPException(
            status_code=503,
            detail="Sorry, the shop assistant is having trouble right now. Please try again in a moment.",
        )

    if user:
        history.save_exchange(user.id, body.message, run.output.reply, run.output.product_ids, page)

    # Cards are built from the database, not from the model's text, so prices/stock are always real.
    cards = {p.product_id: p for p in tools.get_products_by_ids([b.product_id for b in run.bag_additions])}
    return ChatResponse(
        reply=run.output.reply,
        products=tools.get_products_by_ids(run.output.product_ids),
        bag_additions=[BagAddition(product=cards[b.product_id], size=b.size, quantity=b.quantity) for b in run.bag_additions],
        verified=run.fact_check,
    )
