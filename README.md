# Campus Customs Shop + Chatbot (Homework 4)

A Campus Customs storefront for officially licensed Yale apparel: a **React + Vite + TypeScript** front end and a **Python FastAPI** back end whose brain is a **PydanticAI agent**, *Handsome Dan*, the bulldog concierge. Shoppers can browse products, create an account, chat about merch, see matching items appear on the page as product cards, and get honest price and stock answers straight from the local database.

**Highlights:** chat search that puts product cards on the page · per-size stock answers checked by a price & stock fact-checker · saved chat history for logged-in shoppers · page-aware chat ("do you have *this* in pink?") · shopping bag the agent can add to · "Shop my size" mode · append-only audit trail · "Varsity Heritage" design.

---

## 1. Put the data pack in place (not in git)

The database and product photos are **not** in this repo. Unzip the course `data.zip` so this folder contains:

```
hw4/
└── data/
    ├── campus_customs.db     # SQLite: catalogue, inventory, users, chat_messages
    └── products/             # product images referenced by the catalogue
```

## 2. Add your keys

```bash
copy .env.example .env        # macOS/Linux: cp .env.example .env
```

Edit `.env`:
- `SESSION_SECRET`: any long random string (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- `ANTHROPIC_API_KEY`: your Anthropic key (the agent uses `claude-haiku-5-5` by default)
- *or* set `MODEL_PROVIDER=portkey` and `PORTKEY_API_KEY` to use OpenAI 5.6/6-series models through Portkey

`.env` is gitignored, so keys are never committed.

## 3. Run the back end (FastAPI)

Requires Python 3.12+.

```bash
# from hw4/  (one time)
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# every time: run from the backend/ folder
cd backend
uvicorn main:app --reload --port 8000
```

Check it: <http://localhost:8000/api/health> should show `"database": true`. On first start the back end also makes white-background copies of the product photos in `data/products_clean/` (about a minute, in the background).

## 4. Run the front end (React + Vite)

Requires Node 20+. In a second terminal:

```bash
# from hw4/
cd frontend
npm install        # one time
npm run dev
```

Open the URL Vite prints (normally <http://localhost:5173>). The dev server forwards `/api` and `/images` to the back end on port 8000 (see `frontend/vite.config.ts`).

**Try it:** log in with the seed test account `test@campuscustoms.yale.edu` / `password` (or create an account), then click Handsome Dan (bottom right) and ask *"What crewnecks do you have?"*, *"Is the Baseball Left Chest Crewneck in XS?"*, or on a product page *"Add this in medium to my bag."*

---

## Project layout

```
hw4/
├── AI_prompts.md          # every prompt used to build this, per problem
├── README.md
├── requirements.txt       # back-end Python packages
├── .env.example           # placeholders only (copy to .env)
├── .gitignore             # keeps .env, data/, the database and images out of git
├── COST_CHECK_REPORT.md   # graded question set + model/cost choice (Haiku 5.5)
├── frontend/              # Vite React TypeScript app
├── backend/
│   ├── main.py            # FastAPI app: run with  uvicorn main:app --reload --port 8000
│   ├── agent.py           # ┐
│   ├── tools.py           # │ the agent: four files
│   ├── models.py          # │
│   ├── prompts/prompt.md  # ┘
│   ├── auth.py            # sign-up / login / sessions
│   ├── history.py         # saved chat history for logged-in shoppers
│   ├── images.py          # white-background copies of product photos
│   └── cost_check.py, build_cost_report.py   # graded test set + report (optional)
└── output/
    ├── harness.md         # full system description: models, tools, safety, specs
    ├── design.md          # design choices
    ├── usability.md       # usability improvements
    ├── app_check.html     # live-site test with screenshots (double-click to open)
    ├── app_check_images/  # screenshots linked from app_check.html
    └── audit_trail.json   # append-only agent-loop audit trail
```

**The agent is four files** under `backend/`: `prompts/prompt.md` (system prompt + safety rules), `agent.py` (wiring, fact-checker, audit trail), `tools.py` (database tools), and `models.py` (Pydantic types). The full explanation is in [`output/harness.md`](output/harness.md).

## Troubleshooting

- **Chat says "having trouble right now":** check `ANTHROPIC_API_KEY` in `.env` and that the account has credits; the back-end terminal shows the error.
- **No products / images:** make sure `data/campus_customs.db` and `data/products/` are in `hw4/data/` (step 1).
- **Port 8000 already in use:** run Uvicorn on another port (e.g. `--port 8040`) and create `frontend/.env.local` with `API_PORT=8040`.
- **Backend edits not picked up (Windows):** Uvicorn's `--reload` occasionally stalls; stop it (Ctrl+C) and start it again.
