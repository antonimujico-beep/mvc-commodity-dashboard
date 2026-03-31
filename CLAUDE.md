# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Dashboard

```bash
# Start local server
python3 ~/.noeai/dashboard/app.py
# Opens at http://localhost:5555
```

- `/` → Commodity price dashboard (`commodity.html`)
- `/agents` → Agent task dashboard (`index.html`)
- `/egd-crm` → EGD Sales CRM (`egd_crm.html`)

## Running the Automations

```bash
# Live commodity price check (ICE futures via Yahoo Finance)
python3 ~/.noeai/automations/commodity_price_check.py

# Find new B2B leads in Miami via Google Places API
python3 ~/.noeai/automations/egd/lead_finder.py [category|all]

# Generate WhatsApp + email messages for leads without them
python3 ~/.noeai/automations/egd/message_generator.py

# Send WhatsApp messages via Twilio
python3 ~/.noeai/automations/egd/whatsapp_outreach.py --test        # test to Antoni's number
python3 ~/.noeai/automations/egd/whatsapp_outreach.py --run         # all new leads
python3 ~/.noeai/automations/egd/whatsapp_outreach.py --run --limit 10
```

## Deployment

Live at: `https://mvc-commodity-dashboard.onrender.com`

```bash
cd ~/.noeai/dashboard
git add <files> && git commit -m "message" && git push
```

Render auto-deploys on push to `main`. GitHub repo: `antonimujico-beep/mvc-commodity-dashboard`.

## Architecture

### Flask app (`app.py`)
Single-file backend serving all HTML pages and APIs:
- **Price API** (`/api/prices`): fetches ICE futures from Yahoo Finance (`CC=F` cocoa, `KC=F` coffee) with 5-minute in-memory cache, falls back to `latest_prices.json`
- **Leads API** (`/api/leads`): full CRUD backed by `egd_leads.json` (index-based, not ID-based for PUT/DELETE)
- **Tasks API** (`/api/data`): read/write `tasks.json` for the agent dashboard

### Data files (JSON, git-tracked)
- `egd_leads.json` — all EGD sales leads; `LEADS_FILE` in `app.py` points to this file directly via `os.path.dirname(__file__)` (critical for Render to find it)
- `latest_prices.json` — last price check output; written by both `commodity_price_check.py` and `app.py`
- `tasks.json` — agent/task structure for the dashboard UI

### Contracts / Hedge Tracker — PostgreSQL
- **Contracts and hedges** are persisted in a PostgreSQL database (Render free tier) via SQLAlchemy.
- On startup, `_init_db()` creates the `contracts_store` table if it doesn't exist (single row, key=`contracts`, value=JSON array).
- Locally (no `DATABASE_URL` env var), SQLAlchemy falls back to `contracts.db` (SQLite).
- API endpoints: `GET/POST /api/contracts`, `DELETE /api/contracts/<ci>`, `POST /api/contracts/<ci>/hedges`, `DELETE /api/contracts/<ci>/hedges/<hi>`.
- The HTML stores contracts in `_contracts` (in-memory JS array), fetches from API on load, and calls API on every mutation — no `localStorage` involved.

### EGD Sales Pipeline (`~/.noeai/automations/egd/`)
Three-stage pipeline: **find → message → outreach**
1. `lead_finder.py` — Google Places API (New: POST to `places.googleapis.com/v1/places:searchText`). API key and categories in `config.py`. Deduplicates by `place_id`.
2. `message_generator.py` — fills `wa_message`, `email_subject`, `email_message` per lead using templates keyed by business type
3. `whatsapp_outreach.py` — Twilio sandbox (`+14155238886`); trial limit is 50 msgs/day; marks leads `contacted` after send

### Commodity Price Logic
- Cocoa: ICE CC=F → USD/MT. Differential: -$300/MT
- Coffee: ICE KC=F → cents/lb = USD/quintal (same numeric value, 1 quintal = 100 lbs). Differential: -$13.61/quintal
- Farmer sweet spot: `sell_price - fob_mid - fees - (sell_price × margin)`

### Crontab (Mac, Mon–Fri only)
```
3  8  * * 1-5  python3 ~/.noeai/automations/commodity_price_check.py
30 10  * * 1-5  python3 ~/.noeai/automations/commodity_price_check.py
30 13  * * 1-5  python3 ~/.noeai/automations/commodity_price_check.py
```

## Key Constraints
- **Twilio sandbox**: messages only reach numbers that have activated the sandbox; 50 msg/day limit on trial accounts
- **Google Places API key** in `config.py` is unrestricted — should be locked to Places API only in Google Cloud Console
- **Render PostgreSQL free tier** expires after 90 days — upgrade or migrate before then to avoid data loss
- **`openpyxl`** is in `requirements.txt` but not currently used
