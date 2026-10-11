# Campus Customs — Usability Improvements (Problem 9)

Four improvements on top of the core shop: two on the front end and two in the agent/backend. Each section says **what we added**, **why it helps a Campus Customs shopper**, **why it helps the business**, **where to see it in the running app**, and **how we checked it works**.

| # | Improvement | Type | One-line summary |
|---|---|---|---|
| 1 | 🛍 Shopping bag drawer | Front end | Pick a size → **Add to bag** → a bag slides in with sizes, quantities and a live subtotal; you can never add more than is in stock. |
| 2 | 📏 "Shop my size" mode | Front end | Set your size once; every product card shows that size's stock, sold-out items fade, and one click filters to only what you can actually buy. |
| 3 | ✅ Price & stock fact-checker | Agent / backend | Code checks every `$` price, and stock counts written in common forms ("Only 2 left", "5 are in stock", "12 in medium", "S (15)"), against the database before the shopper sees the reply; a wrong number sends it back to be fixed. |
| 4 | 🤖 Agent can add to your bag | Agent / backend | New `add_to_bag` tool: "add a large Crew Left Chest Hoodie to my bag" checks live stock and drops it into the bag. |

The four work together: the agent knows your size (2) and your bag (1), can add to the bag (4), and the prices and stock counts it quotes are checked (3).

---

## 1. 🛍 Shopping bag drawer (front end)

**What we added**
- **Product page buy box:** a quantity stepper and an **Add to bag · $X** button that shows the live total for the chosen quantity. It reads "Select a size" until a size is picked, "Sold out" for a sold-out size, and "All 5 in your bag" once you hold every unit in stock.
- **Bag drawer** (`BagDrawer.tsx`) that slides in from the right (Esc or clicking outside closes it):
  - each line shows a thumbnail, name (linking back to the product page), size, unit price, a quantity stepper, the line total and a remove button
  - a low-stock warning ("only 5 in stock") on a line when 5 or fewer are left
  - a green "✓ Added 2 × Basic Hoodie Big Yale (M) · $136" confirmation
  - a **live subtotal**
  - an **Ask the assistant about my bag** shortcut
- **Bag icon with a count badge** in the nav bar (the badge pops when it changes).
- **Stock-aware limits:** the + button stops at the units in stock for that size (capped at 10), using per-size stock now included with every product (`stock_by_size`, added to the products API).
- **Per-shopper bags:** saved on the device and kept separate per account (`cc_bag_user_{id}`) and for guests, so a bag survives page reloads and doesn't leak between people sharing a browser.
- **Honest checkout:** the checkout button says **"Checkout (coming soon)"**, because there's no payment system. We don't pretend.

**Why it helps the shopper**
- Before this, you could browse but not *collect* anything. Now you can build an order, see the running total, and change sizes and quantities in one place without losing your spot on the page.
- It never lets you put 6 in the bag when only 5 exist, so there's no "sorry, actually out of stock" surprise later.

**Why it helps the business**
- A bag is the basic step between interest and a sale; every store measures "add-to-bag rate".
- A live subtotal and "only 5 in stock" signals are proven conversion nudges.
- Stock-capped quantities mean no overselling, which avoids refunds and support emails.
- The bag sets up a future checkout with no front-end rework.

**Where to see it:** open any product (e.g. `/products/basic-hoodie-big-yale`) → pick a size → **Add to bag**. Or click the bag icon (top right).

**Verified**
| Check | Result |
|---|---|
| Add 2 × Basic Hoodie Big Yale in M | Drawer slid open: "✓ Added 2 × Basic Hoodie Big Yale (M) · $136", nav badge 2, subtotal $136. |
| Press + until it stops | Stopped at **5**, exactly the units in stock for M (database: 5); subtotal $340 = 5 × $68; product page then says "All 5 in your bag". |
| Checkout button | Disabled, labelled "Checkout (coming soon)". |

---

## 2. 📏 "Shop my size" mode (front end)

**What we added**
- **My size picker** in the nav bar (Any, XS–XXL) and a matching **Shop my size** pill row on the Products page. Your choice is remembered between visits.
- **Every product card** (Products grid *and* the chat's "From your chat" cards) gets a stock badge for your size: green **"M · 20 left"**, amber **"M · only 5 left"**, or red **"M · sold out"**.
- **Sold out in your size?** The card fades and goes gray (it lights up on hover), so the eye skips it.
- **"Only show what's in stock in M"** filter, plus a highlighted stat in the summary strip: **"80/102 in stock in your size (M)"**.
- **Product page:** your size is **pre-selected** if it's in stock, and marked with a gold dot on the size buttons.
- **The chatbot knows your size** (sent with each message), so "how many are left in my size?" just works.

**Why it helps the shopper**
- Most shoppers only care about one size. Without this, they click into product after product only to find their size sold out (22 of 102 styles are sold out in M).
- Now the whole store is filtered through *their* size at a glance, and every click lands on something they can buy.

**Why it helps the business**
- Fewer dead-end clicks means fewer abandoned sessions.
- Low-stock badges in the shopper's own size create honest urgency.
- The size preference is useful demand data (which sizes shoppers want versus what's in stock) for reordering decisions.

**Where to see it:** the **My size** dropdown in the nav, or the **Shop my size** pills at the top of `/products`.

**Verified** (numbers checked against the database)
| Check | Result |
|---|---|
| Choose M | All 102 cards show an M badge, e.g. "2025 Yale Vs Harvard T Shirt → M · 20 left" (database: 20), "Basic Hoodie Big Yale → M · only 5 left" (database: 5). |
| Faded cards | 22 faded = the 22 products with 0 units in M (database). |
| Summary stat | "80/102 in stock in your size (M)". |
| "Only show what's in stock in M" | Grid drops to exactly **80** cards, none faded. |
| Product page | Size M pre-selected on the Basic Hoodie Big Yale. |
| Chat: "how many are left in my size?" (Champion Full Zip Hood) | "In your size, M, there are only 5 left" (database: 5). |

---

## 3. ✅ Price & stock fact-checker (agent / backend)

**What we added**
- A PydanticAI **output validator** (`verify_prices_and_stock` in `agent.py`, logic in `tools.fact_check`) that runs on every reply **before** the shopper sees it:
  1. It collects every number the tools returned from the database **in this turn** (prices, units per size, bag subtotals).
  2. It finds every `$` amount and every stock count written in a common form, in any capitalization ("Only 2 left", "15 available", "5 are left", "2 are in stock in XL", "25 in XXL", "12 in medium", "S (15)"). Unusual phrasings (e.g. "we're down to 2") aren't recognized, so they go unchecked; see `harness.md`, Known limitations.
  3. A price must match a database price (or a price × quantity, e.g. "two for $136", or a number the shopper typed, e.g. "under $40"). A stock count must match a database quantity.
  4. If anything doesn't match, the reply is **sent back to the model** with the exact problem ("$58 does not match any price returned by your tools this turn") and the model must fix it. The shopper never sees the wrong version.
- A green **"✓ 1 price · 1 stock count verified"** badge under each chat reply that quotes numbers (it adds "· auto-corrected 1×" if a fix was needed). Hovering explains it was checked against live inventory.
- The fact-check result is part of the chat API response (`verified`), and the prompt tells the agent its numbers are checked.

**Why it helps the shopper**
- A chatbot that quotes the wrong price or invents stock is worse than no chatbot. With this, every `$` price and every stock count in a recognized form is checked against the inventory at that moment before the shopper sees it.
- The badge makes the trust visible.

**Why it helps the business**
- Accuracy and safety: no promising a $58 price on a $68 item (a real customer-service and legal headache), and no selling stock that doesn't exist.
- It's plain code, not a second AI call: correct answers cost **$0 extra** and add no delay. The graded question set still passes 8/8 at the same $0.0005 per question and the same number of model requests (`COST_CHECK_REPORT.md`, run 17).
- It also protected us when we switched to the cheaper Haiku model: cheaper with a safety net.

**Where to see it:** ask the chat any price or stock question (e.g. "Is the Basic Hoodie Big Yale available in XL?"), and look for the green ✓ badge under the reply.

**Verified**
| Check | Result |
|---|---|
| Scripted test (no API): the model first answers "$58 and we have 7 left in XL" | Fact-checker sent it back: *"$58 does not match any price returned by your tools this turn; the stock count 7 does not match any quantity…"*. Final reply: "The Basic Hoodie Big Yale is $68, and there are only 2 left in XL." Record: `retries=1`. |
| Unit checks | Passes "$68… only 2 left in XL", "Two would be $136", "Under your $70 budget it is $68"; catches "$58" and "only 3 left in XL" (database: 2). After the final review it also catches a wrong count in "Only 99 are left in XXL", "99 are in stock in XL" and "We have 99 in medium" (these used to slip through), with no false alarms on "We carry 27 hoodies" or "3 colors and 6 sizes". |
| Live chat | Replies show "✓ 2 prices verified", "✓ 1 price · 1 stock count verified". |

---

## 4. 🤖 Agent can add to your bag (agent / backend)

**What we added**
- New agent tool **`add_to_bag(product, size, quantity)`** (`agent.py` → `tools.add_to_bag`), returning a typed `AddToBagResult` (`models.py`):
  - accepts a product id or name, and sizes like "large" or "medium"
  - checks **live stock for that size minus what's already in the bag**; refuses sold-out sizes and over-stock requests with a clear reason ("All 5 units in stock in M are already in your bag")
  - if no size is given, uses the shopper's **My size**; otherwise it asks, listing the in-stock sizes
  - returns the exact unit price, units in stock, and the new bag count and subtotal, which then pass the fact-checker
- **The agent sees the bag:** the website sends the bag with each message, and the agent's context shows its items and subtotal ("what's in my bag?" works).
- **Website wiring:** the chat API returns `bag_additions`, and the website drops them into the bag, which slides open. The reply shows a **"🛍 Added 1 to your bag"** tag.
- **Prompt rules:** only add when the shopper clearly asks; never claim an add that didn't happen (`added=false`); the agent can't check out, take payment or remove items.

**Why it helps the shopper**
- Shopping by conversation: "I'll take a large" and it's done. There's no hunting for the product page, size buttons and Add button, which is especially handy on a phone or for gift shoppers who asked the bot for ideas in the first place.

**Why it helps the business**
- It turns the chatbot from a help desk into a **sales channel**. Every recommendation is one sentence away from the bag, which shortens the path to purchase.
- The stock checks mean the bot can't oversell, and the add is validated on the server, not trusted from the model.

**Where to see it:** open the chat and type e.g. *"add a large Crew Left Chest Hoodie to my bag please"*.

**Verified (live, Claude Haiku 5.5)**
| Shopper said | Agent did | Database |
|---|---|---|
| "add a large Crew Left Chest Hoodie to my bag please" | "I added one Crew Left Chest Hoodie in size L ($68) to your bag. Your bag now has 6 items with a subtotal of $408.00." The bag slid open with both lines; badges "🛍 Added 1 to your bag" and "✓ 2 prices verified". | L = 8 in stock; 5 × $68 + $68 = $408 ✓ |
| "add one more Basic Hoodie Big Yale in medium" | Refused: "All 5 units in stock in M are already in your bag, so there are none left to add." | M = 5, all 5 already in the bag ✓ |
| "how much is the Champion Full Zip Hood and how many are left in my size?" | "$88… In your size, M, there are only 5 left." (used My size without being told) | $88, M = 5 ✓ |

---

## Files

| Area | Files |
|---|---|
| Bag + My size (front end) | `frontend/src/components/ShopContext.tsx`, `ShopProvider.tsx`, `useShop.ts`, `BagDrawer.tsx`, `NavBar.tsx`, `ProductCard.tsx`, `pages/Products.tsx`, `pages/ProductDetail.tsx`, `usability.css` |
| Fact-checker + add_to_bag (backend) | `backend/agent.py` (tool + output validator + bag/size in context), `backend/tools.py` (`add_to_bag`, `bag_subtotal`, `fact_check`), `backend/models.py` (`BagLine`, `BagAddition`, `AddToBagResult`, `FactCheck`), `backend/main.py` (`bag`, `my_size` in; `bag_additions`, `verified` out), `backend/prompts/prompt.md` |
| Chat wiring | `frontend/src/components/ChatWidget.tsx` (sends bag + size, applies additions, verified badge), `frontend/src/api.ts` |
