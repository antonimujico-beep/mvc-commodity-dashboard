#!/usr/bin/env python3
"""
Antoni's Agent Dashboard v2 — Company-first structure
Run: python3 ~/.noeai/dashboard/app.py
Open: http://localhost:5555
"""

from flask import Flask, jsonify, request, send_from_directory, send_file
import json, os, uuid, re, time
from datetime import datetime
try:
    import urllib.request
except ImportError:
    pass

app = Flask(__name__, static_folder=".")
TASKS_FILE   = os.path.join(os.path.dirname(__file__), "tasks.json")
PRICES_FILE  = os.path.join(os.path.dirname(__file__), "latest_prices.json")
COMMODITY_HTML = os.path.join(os.path.dirname(__file__), "commodity.html")

# ── Price cache (avoid hammering Yahoo Finance) ──────────────────────────────
_price_cache = {"data": None, "ts": 0}
CACHE_TTL    = 300   # 5 minutes

def _yahoo_fetch(ticker: str):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    return float(data["chart"]["result"][0]["meta"]["regularMarketPrice"])

def _build_prices():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    out = {"updated_at": now, "commodities": {}}
    try:
        cocoa_raw  = _yahoo_fetch("CC=F")
        cocoa_sell = cocoa_raw - 300
        out["commodities"]["cocoa"] = {
            "ticker": "CC=F", "futures": round(cocoa_raw, 2),
            "differential": -300, "sell": round(cocoa_sell, 2),
            "farmer_5pct":  round(cocoa_sell - 150 - 150 - cocoa_sell*0.05, 2),
            "farmer_10pct": round(cocoa_sell - 150 - 150 - cocoa_sell*0.10, 2),
            "unit": "MT", "fob_mid": 150, "fees": 150,
        }
    except Exception as e:
        out["commodities"]["cocoa"] = {"error": str(e)}
    try:
        coffee_raw  = _yahoo_fetch("KC=F")   # cents/lb = USD/quintal
        coffee_sell = coffee_raw - 13.61
        out["commodities"]["coffee"] = {
            "ticker": "KC=F", "futures": round(coffee_raw, 2),
            "differential": -13.61, "sell": round(coffee_sell, 2),
            "farmer_5pct":  round(coffee_sell - 6.80 - 6.80 - coffee_sell*0.05, 2),
            "farmer_10pct": round(coffee_sell - 6.80 - 6.80 - coffee_sell*0.10, 2),
            "unit": "quintal", "fob_mid": 6.80, "fees": 6.80,
        }
    except Exception as e:
        out["commodities"]["coffee"] = {"error": str(e)}
    # Persist to file for offline use
    try:
        with open(PRICES_FILE, "w") as f:
            json.dump(out, f, indent=2)
    except Exception:
        pass
    return out

def load():
    with open(TASKS_FILE) as f:
        return json.load(f)

def save(data):
    with open(TASKS_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/")
def commodity():
    return send_file(COMMODITY_HTML)

@app.route("/agents")
def index():
    return send_from_directory(os.path.dirname(__file__), "index.html")

@app.route("/api/prices")
def get_prices():
    global _price_cache
    now = time.time()
    # Return cache if fresh
    if _price_cache["data"] and (now - _price_cache["ts"]) < CACHE_TTL:
        return jsonify(_price_cache["data"])
    # Try live fetch
    try:
        data = _build_prices()
        _price_cache = {"data": data, "ts": now}
        return jsonify(data)
    except Exception:
        # Fall back to saved JSON file
        if os.path.exists(PRICES_FILE):
            with open(PRICES_FILE) as f:
                return jsonify(json.load(f))
        return jsonify({"error": "Price data unavailable"}), 503

@app.route("/api/data", methods=["GET"])
def get_data():
    return jsonify(load())

# ── Companies ─────────────────────────────────────────────────────────────────

@app.route("/api/companies", methods=["POST"])
def add_company():
    data = load()
    body = request.json
    company = {
        "id": f"co-{uuid.uuid4().hex[:8]}",
        "name": body.get("name", "New Company"),
        "emoji": body.get("emoji", "🏢"),
        "color": body.get("color", "#048A81"),
        "agents": []
    }
    data["companies"].append(company)
    save(data)
    return jsonify(company), 201

@app.route("/api/companies/<co_id>", methods=["DELETE"])
def delete_company(co_id):
    data = load()
    data["companies"] = [c for c in data["companies"] if c["id"] != co_id]
    save(data)
    return jsonify({"ok": True})

# ── Agents ────────────────────────────────────────────────────────────────────

@app.route("/api/companies/<co_id>/agents", methods=["POST"])
def add_agent(co_id):
    data = load()
    body = request.json
    agent = {
        "id": f"ag-{uuid.uuid4().hex[:8]}",
        "name": body.get("name", "New Agent"),
        "emoji": body.get("emoji", "🤖"),
        "description": body.get("description", ""),
        "status": "active",
        "tasks": []
    }
    for co in data["companies"]:
        if co["id"] == co_id:
            co["agents"].append(agent)
    save(data)
    return jsonify(agent), 201

@app.route("/api/companies/<co_id>/agents/<ag_id>", methods=["DELETE"])
def delete_agent(co_id, ag_id):
    data = load()
    for co in data["companies"]:
        if co["id"] == co_id:
            co["agents"] = [a for a in co["agents"] if a["id"] != ag_id]
    save(data)
    return jsonify({"ok": True})

# ── Tasks ─────────────────────────────────────────────────────────────────────

@app.route("/api/companies/<co_id>/agents/<ag_id>/tasks", methods=["POST"])
def add_task(co_id, ag_id):
    data = load()
    body = request.json
    task = {
        "id": f"t{uuid.uuid4().hex[:6]}",
        "name": body.get("name", "New Task"),
        "schedule": body.get("schedule", "On demand"),
        "commodity": body.get("commodity", "All"),
        "status": "active",
        "last_run": "—",
        "command": body.get("command", "")
    }
    for co in data["companies"]:
        if co["id"] == co_id:
            for ag in co["agents"]:
                if ag["id"] == ag_id:
                    ag["tasks"].append(task)
    save(data)
    return jsonify(task), 201

@app.route("/api/companies/<co_id>/agents/<ag_id>/tasks/<task_id>", methods=["DELETE"])
def delete_task(co_id, ag_id, task_id):
    data = load()
    for co in data["companies"]:
        if co["id"] == co_id:
            for ag in co["agents"]:
                if ag["id"] == ag_id:
                    ag["tasks"] = [t for t in ag["tasks"] if t["id"] != task_id]
    save(data)
    return jsonify({"ok": True})

# ── NL Parser ─────────────────────────────────────────────────────────────────

@app.route("/api/parse-task", methods=["POST"])
def parse_task():
    data   = load()
    body   = request.json
    text   = body.get("text", "").lower()
    orig   = body.get("text", "")
    co_id  = body.get("company_id")   # pre-selected company from UI
    ag_id  = body.get("agent_id")     # pre-selected agent from UI (optional)

    # ── Commodity ──────────────────────────────────────────
    commodity = "All"
    if any(w in text for w in ["cocoa", "cacao"]):         commodity = "Cocoa"
    elif "coffee" in text:                                  commodity = "Coffee"
    elif any(w in text for w in ["mung", "mungo"]):         commodity = "Mung Beans"
    elif "sesame" in text:                                  commodity = "Sesame"

    # ── Schedule ───────────────────────────────────────────
    schedule = "On demand"
    hm = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', text)
    hour_str = ""
    if hm:
        h = int(hm.group(1))
        m = hm.group(2) or "00"
        mer = hm.group(3)
        if mer == "pm" and h != 12: h += 12
        if mer == "am" and h == 12: h = 0
        hour_str = f"{h:02d}:{m}"

    if any(w in text for w in ["every morning","daily morning","each morning","morning"]):
        schedule = f"Daily {hour_str or '08:00'} AM"
    elif any(w in text for w in ["midday","noon","lunch","afternoon"]):
        schedule = f"Daily {hour_str or '13:00'}"
    elif any(w in text for w in ["every evening","end of day","eod","evening"]):
        schedule = f"Daily {hour_str or '18:00'}"
    elif any(w in text for w in ["every day","daily","each day"]):
        schedule = f"Daily {hour_str}" if hour_str else "Daily"
    elif any(w in text for w in ["every hour","hourly"]):
        schedule = "Every hour"
    elif any(w in text for w in ["monday","lunes"]):
        schedule = f"Weekly Monday {hour_str or '09:00'}"
    elif any(w in text for w in ["friday","viernes"]):
        schedule = f"Weekly Friday {hour_str or '09:00'}"
    elif any(w in text for w in ["weekly","every week","once a week","semanal"]):
        schedule = f"Weekly {hour_str or '09:00'}"
    elif any(w in text for w in ["monthly","every month","mensual"]):
        schedule = "Monthly"
    elif hour_str:
        schedule = f"Daily {hour_str}"

    # ── Task name ──────────────────────────────────────────
    clean = re.sub(r'\b(every|each|daily|weekly|monthly|morning|evening|afternoon|midday|at|on demand|hourly|monday|friday|tuesday|wednesday|thursday|saturday|sunday|lunes|viernes|\d{1,2}(?::\d{2})?\s*(?:am|pm))\b', '', orig, flags=re.IGNORECASE)
    clean = re.sub(r'\b(for the|for|to the|to|in the|add|create|schedule|set up|remind me|task|agente|agent)\b', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\b(mvc|egd|price checker|outreach|research|cargill|hedge)\b', '', clean, flags=re.IGNORECASE)
    task_name = ' '.join(clean.split()).strip(' .,') or orig[:60]
    task_name = task_name[:60]
    task_name = task_name[0].upper() + task_name[1:] if task_name else orig[:60]

    # ── Agent matching (if not pre-selected) ──────────────
    if not ag_id:
        agent_kw = {
            "price":    ["price", "futures", "market", "ice", "farmer", "check"],
            "outreach": ["outreach", "email", "cold", "buyer", "prospect", "draft", "follow"],
            "cargill":  ["cargill", "hedge", "contract", "lot", "differential"],
            "research": ["research", "report", "brief", "analysis", "intelligence"],
        }
        best_score, best_key = 0, None
        for key, kws in agent_kw.items():
            score = sum(1 for k in kws if k in text)
            if score > best_score:
                best_score, best_key = score, key

        # Find matching agent in selected company
        target_co = next((c for c in data["companies"] if c["id"] == co_id), None)
        if target_co and best_key:
            for ag in target_co["agents"]:
                if best_key in ag["id"] or best_key in ag["name"].lower():
                    ag_id = ag["id"]
                    break
        # Fall back to first agent in company
        if not ag_id and target_co and target_co["agents"]:
            ag_id = target_co["agents"][0]["id"]

    if not co_id or not ag_id:
        return jsonify({"error": "Select a company and agent"}), 400

    # ── Save ───────────────────────────────────────────────
    task = {
        "id": f"t{uuid.uuid4().hex[:6]}",
        "name": task_name,
        "schedule": schedule,
        "commodity": commodity,
        "status": "active",
        "last_run": "—",
        "command": ""
    }
    agent_name = "Unknown"
    for co in data["companies"]:
        if co["id"] == co_id:
            for ag in co["agents"]:
                if ag["id"] == ag_id:
                    ag["tasks"].append(task)
                    agent_name = ag["name"]
    save(data)
    return jsonify({"task": task, "agent_name": agent_name}), 201


EGD_CRM_HTML = os.path.join(os.path.dirname(__file__), "egd_crm.html")
LEADS_FILE   = os.path.join(os.path.dirname(__file__), "egd_leads.json")

def load_leads():
    if os.path.exists(LEADS_FILE):
        with open(LEADS_FILE) as f:
            return json.load(f)
    return []

def save_leads_data(leads):
    with open(LEADS_FILE, "w") as f:
        json.dump(leads, f, indent=2)

@app.route("/egd-crm")
def egd_crm():
    return send_file(EGD_CRM_HTML)

@app.route("/api/leads", methods=["GET"])
def get_leads():
    return jsonify(load_leads())

@app.route("/api/leads", methods=["POST"])
def add_lead():
    leads = load_leads()
    body  = request.json
    lead  = {
        "id":           f"egd-{uuid.uuid4().hex[:8]}",
        "business":     body.get("business",""),
        "type":         body.get("type",""),
        "phone":        body.get("phone",""),
        "email":        body.get("email",""),
        "address":      body.get("address",""),
        "website":      body.get("website",""),
        "contact":      body.get("contact",""),
        "products":     body.get("products",[]),
        "status":       body.get("status","new"),
        "assigned_to":  body.get("assigned_to",""),
        "notes":        body.get("notes",""),
        "wa_message":   "",
        "email_subject":"",
        "email_message":"",
        "created_at":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        "contacted_at": "",
    }
    leads.append(lead)
    save_leads_data(leads)
    return jsonify(lead), 201

@app.route("/api/leads/<int:idx>", methods=["PUT"])
def update_lead(idx):
    leads = load_leads()
    if idx >= len(leads):
        return jsonify({"error": "Not found"}), 404
    body = request.json
    for k, v in body.items():
        leads[idx][k] = v
    save_leads_data(leads)
    return jsonify(leads[idx])

@app.route("/api/leads/<int:idx>", methods=["DELETE"])
def delete_lead(idx):
    leads = load_leads()
    if idx >= len(leads):
        return jsonify({"error": "Not found"}), 404
    leads.pop(idx)
    save_leads_data(leads)
    return jsonify({"ok": True})

@app.route("/api/find-leads", methods=["POST"])
def find_leads_api():
    import subprocess
    script = os.path.expanduser("~/.noeai/automations/egd/lead_finder.py")
    subprocess.Popen(["python3", script, "restaurants"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return jsonify({"ok": True, "message": "Lead finder running in background", "added": "check back in 30s"})


if __name__ == "__main__":
    print("\n" + "="*55)
    print("  🤖 ANTONI'S AGENT DASHBOARD v2")
    print("="*55)
    print("  ✅ Running at: http://localhost:5555")
    print("  Press Ctrl+C to stop")
    print("="*55 + "\n")
    app.run(port=5555, debug=False)
