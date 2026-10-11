# Campus Customs — Design (Problem 10)

**Direction: "Varsity Heritage."** A century-old campus shop reimagined: Yale navy + old gold + warm ivory paper, collegiate block lettering, stitched and chenille-patch details. The goal is a site that feels like *the* Yale store, not a template, and turns browsing into buying with fewer clicks.

| Area | What we changed | Why it helps customers stick around and buy |
|---|---|---|
| **Fonts** | **Graduate** varsity lettering for headlines and prices; **Inter** for body text. | Instantly reads "Yale athletics"; Inter keeps text and prices easy to scan. |
| **Color & texture** | Navy, old gold, ivory paper with a faint grain; gold only on actions (Shop, Add, Send). | Warm and premium; one action color teaches the eye where to click. |
| **Hierarchy** | Block headlines, gold eyebrows, an "EST. NEW HAVEN · 57 BROADWAY" stamp, varsity stripe under the nav. | Clear reading order, and heritage cues build trust that this is the official local shop. |
| **Product-led home hero** | Three **real products fanned** like cards, a faded collegiate "Y", a gold **★ Shop the collection** button. | The home page went from zero products to merchandise first, each one click from its page. |
| **Shop-by-category patches** | Six chenille-patch tiles with **live counts and starting prices** ("27 styles · from $45") that deep-link to the filtered grid. | One click to the right aisle, with real numbers that set price expectations. |
| **Product cards** | Photo zoom, stitched gold outline, and a **Quick add** size row on hover (sold-out sizes crossed out). | Add to bag **without leaving the grid**; sold-out sizes are never a surprise. |
| **Clean white photos** | 76 of 102 photos had black backgrounds; the site now serves white-background copies. | A uniform grid looks premium and keeps the eye on the product. |
| **Product page** | **Hover magnifier** (2× zoom follows the cursor), collegiate title and price, gold ring on the selected size. | Shoppers can inspect stitching and logos up close, which matters most for apparel online. |
| **Handsome Dan concierge** | Yale's bulldog **is the chat button** on every page ("Woof! Need a paw?"), with **page-aware quick replies** and playful animations. | A mascot shoppers love gets used more than a support box, and one-tap chips turn the next question into a sale. |
| **Motion** | Page fade-ins, scroll reveals, staggered cards, bag badge pop; all off for "reduce motion" users. | Feels alive and guides attention to new cards, bag items and replies. |
| **Pennant footer** | Gold/white/navy stripe, a navy pennant, Visit / Shop / Promise columns. | Ends every page on brand and trust, with quick links back into the shop. |

## Details

- **Fonts:** both self-hosted, so pages don't wait on Google.
- **Colors:** navy `#00356b`, old gold `#c9a227`, ivory paper `#f7f2e7`. The active nav link gets a gold underline, and stitched seams divide sections.
- **Hero:** the fanned cards float gently and straighten on hover.
- **Category patches:** navy felt with gold stitching; they link to `/products?category=Hoodies`, etc.
- **White photos:** `backend/images.py` fills only black *connected to the photo's edge*, so navy fabric and black logos are untouched. A safety check keeps the original if a fill would leak into the garment. Originals are never modified; copies are made once at API start (about 50 s, `data/products_clean/`). Every result was checked by eye on before/after sheets.
- **Handsome Dan:**
  - In chat: he opens right where he sits; his avatar is on the header and every reply, with speech-bubble tails and typing dots with rotating captions. Quick replies match the page, e.g. on a product page with size M set: "Is this in stock in M?", "Add this in M to my bag".
  - Animations: he blinks, wiggles his ears, and tilts his head while thinking ("Sniffing the stockroom…"). He leaves a paw-print trail on the home page, stamps paw prints out of the bag icon on every add, guards an empty bag (sleepy Dan with a floating "z"), and looks sad on the 404 page.
  - Voice: at most one light bulldog touch per reply, with facts always first.
- **Motion:** also includes button press feedback and a chat panel scale-in. Reveals never hide content that's already on screen.

**Files:** `frontend/src/varsity.css` (design layer, loaded last), `pages/Home.tsx`, `components/ProductCard.tsx` (quick add), `components/BulldogAvatar.tsx`, `components/ChatWidget.tsx` (concierge), `components/RevealOnScroll.tsx`, `components/Footer.tsx`, `pages/ProductDetail.tsx` (magnifier), `pages/Products.tsx` (`?category=` deep links, staggered grid).

**Checked in the running app:** Graduate + Inter load; the hero shows 3 real products with images; the patches show live counts (e.g. Hoodies 27 · from $45) and link to `/products?category=Hoodies` (27 cards); quick add put a Brooks Brothers hoodie (S) in the bag without leaving the grid (badge 6 → 7, XS disabled because it's sold out); the concierge shows the avatar and page-aware chips; the magnifier follows the cursor; no console errors.
