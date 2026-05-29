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

## Deployment (Fly.io)

A multi-stage `Dockerfile` builds the PWA and runs the backend (which serves the PWA + API
and runs the poller). `fly.toml` keeps one machine always-on (so polling never stops) and
mounts a persistent volume for the SQLite file.

> Not yet built against a live Docker daemon — run `docker build .` locally once to confirm
> before first deploy.

```bash
fly launch --no-deploy                 # create the app (keep the generated app name in fly.toml)
fly volumes create moneymoney_data --size 1 --region yyz
fly secrets set \
  GMAIL_ADDRESS="your-inbox@gmail.com" \
  GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx" \
  APP_USERNAME="me" \
  APP_PASSWORD="a-long-random-password"
fly deploy
```

## Security

- Secrets (Gmail app password, `APP_PASSWORD`) live in `.env` locally and Fly **secrets** in
  production — never committed.
- The API is protected by HTTP Basic auth whenever `APP_PASSWORD` is set. **Set it before any
  public deploy** so transaction data isn't exposed. Auth is disabled locally when unset.
- All transaction data is sensitive and stays in the host-private SQLite volume.
