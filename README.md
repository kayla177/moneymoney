# MoneyMoney

A personal, automatic spend tracker. Instead of manually logging purchases, it reads the
**bank alert emails** you already receive (RBC purchase alerts + Scotia receipts), parses
each into a transaction, auto-categorizes it, and shows monthly spending analysis in a
phone-friendly web app (PWA).

No bank connection, no aggregator — just a dedicated email inbox the app watches.

## How it works

```
RBC alert email ─┐
Scotia receipt ──┼─► Dedicated Gmail ─► Poller (~1 min) ─► parse + categorize ─► SQLite
                 │                                                                  │
                 │                                              FastAPI API + PWA ◄─┘
```

A small always-on Python backend polls the inbox over IMAP, because iOS can't reliably
poll email in the background. Your phone just views the results.

## Project layout

- `backend/` — FastAPI app, SQLite models, email parsers, poller, analysis.
- `frontend/` — React + Vite PWA (review queue, transactions, monthly analysis). _(coming)_

## Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your Gmail + app password
uvicorn app.main:app --reload
```

Visit http://localhost:8000/health to confirm it's running.

## Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

## Deployment

A multi-stage `Dockerfile` builds the PWA and runs the backend (which serves the PWA + API
and runs the poller). Deploy target: a free Oracle Cloud VM, reachable privately from your
iPhone over Tailscale (no public ports). See [`DEPLOY.md`](./DEPLOY.md) for the full
walkthrough.

## Security

- Secrets (Gmail app password, `APP_PASSWORD`) live in `.env` locally and are passed as env
  vars to the container in production — never committed.
- The API is protected by HTTP Basic auth whenever `APP_PASSWORD` is set. **Set it before any
  remote deploy** so transaction data isn't exposed. Auth is disabled locally when unset.
- All transaction data is sensitive and stays in the host-private SQLite volume.
