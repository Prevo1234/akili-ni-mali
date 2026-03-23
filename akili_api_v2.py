"""
╔══════════════════════════════════════════════════════════════╗
║      AKILI NI MALI — API Server v2.0                         ║
║      Phase 2: Connected to Intelligence Engine v2            ║
║                                                              ║
║  Endpoints:                                                  ║
║   GET  /health          → Server status                      ║
║   GET  /                → API info                           ║
║   POST /analyze         → Full Phase 2 analysis              ║
║   POST /analyze/demo    → Demo with generated data           ║
║   GET  /docs            → Documentation                      ║
╚══════════════════════════════════════════════════════════════╝
"""

from flask import Flask, request, jsonify, render_template
from datetime import datetime, timedelta
from akili_engine_v2 import FinancialProfileV2
import random, re, json

app = Flask(__name__)

# ── Engine ya Phase 2 ──────────────────────────────────────────
engine = FinancialProfileV2()

# ── CORS ───────────────────────────────────────────────────────
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

@app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return jsonify({}), 200


# ══════════════════════════════════════════════════════════════
#  VALIDATION
# ══════════════════════════════════════════════════════════════

def validate_transaction(tx):
    errors = []
    if "type" not in tx:
        errors.append("Kila muamala unahitaji 'type' (credit/debit)")
    elif tx["type"] not in ["credit", "debit"]:
        errors.append(f"'type' lazima iwe 'credit' au 'debit' — si '{tx.get('type')}'")
    if "amount" not in tx:
        errors.append("Kila muamala unahitaji 'amount'")
    elif not isinstance(tx["amount"], (int, float)) or tx["amount"] < 0:
        errors.append("'amount' lazima iwe nambari chanya")
    if "date" not in tx:
        errors.append("Kila muamala unahitaji 'date' (YYYY-MM-DD)")
    return errors


# ══════════════════════════════════════════════════════════════
#  SMS PARSER — parse raw SMS messages
# ══════════════════════════════════════════════════════════════

def parse_sms(sms_text):
    lines = sms_text.strip().split('\n')
    transactions = []
    for line in lines:
        line = line.strip()
        if not line: continue
        lower = line.lower()
        tx_type = None
        if any(w in lower for w in ["umepokea","received","imeingia","credit","pesa zimetumwa kwako"]):
            tx_type = "credit"
        elif any(w in lower for w in ["umetuma","sent","imetoka","debit","umelipa","ulilipa"]):
            tx_type = "debit"
        else:
            continue
        amt_match = re.search(r'TZS\s*([\d,]+)', line, re.I) or re.search(r'([\d,]+)\s*TZS', line, re.I)
        if not amt_match: continue
        amount = int(amt_match.group(1).replace(',',''))
        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
        if date_match:
            p = date_match.group(1).split('/')
            date = f"{p[2]}-{p[1].zfill(2)}-{p[0].zfill(2)}"
        else:
            date = datetime.now().strftime("%Y-%m-%d")
        desc = "Malipo ya mteja" if tx_type=="credit" else "Malipo ya nje"
        for kw, cat in [("kodi","Kodi ya nyumba"),("rent","Kodi ya nyumba"),
                         ("luku","LUKU umeme"),("tanesco","Bili ya umeme TANESCO"),
                         ("mishahara","Mishahara ya wafanyakazi"),
                         ("wasambazaji","Malipo ya wasambazaji"),
                         ("supplier","Malipo ya wasambazaji")]:
            if kw in lower: desc = cat; break
        transactions.append({"type":tx_type,"amount":amount,"date":date,"description":desc})
    return transactions


# ══════════════════════════════════════════════════════════════
#  DEMO DATA GENERATOR — Tanzania-realistic
# ══════════════════════════════════════════════════════════════

def generate_demo(business_type="duka"):
    configs = {
        "duka": {
            "name": "Duka la Mama Fatuma — Dar es Salaam",
            "daily_min": 50000, "daily_max": 180000,
            "daily_count": (3, 7),
            "supplier": (120000, 280000),
            "rent": 180000, "electricity": 42000, "workers": 100000,
        },
        "msisitizo": {
            "name": "Biashara ya Hassan Spices — Zanzibar",
            "daily_min": 15000, "daily_max": 600000,
            "daily_count": (1, 4),
            "supplier": (150000, 500000),
            "rent": 120000, "electricity": 28000, "workers": 70000,
        },
        "mapambano": {
            "name": "Mgahawa wa Juma — Mwanza",
            "daily_min": 12000, "daily_max": 65000,
            "daily_count": (1, 3),
            "supplier": (80000, 200000),
            "rent": 250000, "electricity": 75000, "workers": 180000,
        },
    }
    cfg = configs.get(business_type, configs["duka"])
    transactions = []
    base = datetime(2026, 1, 1)
    # Phone pools — realistic Tanzanian numbers
    phones = [f"07{prefix}{random.randint(1000000,9999999)}"
              for prefix in ["12","54","55","69","88","13","16"]
              for _ in range(8)]

    for offset in range(90):
        d = base + timedelta(days=offset)
        if d.weekday() == 6 and random.random() > 0.35:
            continue
        for _ in range(random.randint(*cfg["daily_count"])):
            amt = round(random.randint(cfg["daily_min"], cfg["daily_max"]) / 500) * 500
            transactions.append({
                "type": "credit", "amount": amt,
                "date": d.strftime("%Y-%m-%d"),
                "description": "Malipo ya mteja",
                "phone": random.choice(phones),
            })
        if d.weekday() in [0, 3] and random.random() > 0.35:
            sup = round(random.randint(*cfg["supplier"]) / 1000) * 1000
            transactions.append({
                "type": "debit", "amount": sup,
                "date": d.strftime("%Y-%m-%d"),
                "description": "Malipo ya wasambazaji bidhaa",
            })
        if d.day == 1:
            transactions.append({
                "type": "debit", "amount": cfg["rent"],
                "date": d.strftime("%Y-%m-%d"),
                "description": "Kodi ya nyumba",
            })
        if d.day == 15:
            transactions.append({
                "type": "debit", "amount": cfg["electricity"],
                "date": d.strftime("%Y-%m-%d"),
                "description": "LUKU umeme TANESCO",
            })
        if d.day == 28:
            transactions.append({
                "type": "debit", "amount": cfg["workers"],
                "date": d.strftime("%Y-%m-%d"),
                "description": "Mishahara ya wafanyakazi",
            })
    return cfg["name"], transactions


# ══════════════════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/demo", methods=["GET"])
def demo_page():
    return render_template("demo.html")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "hali":    "SAWA",
        "status":  "OK",
        "toleo":   "2.0.0",
        "engine":  "Phase 2 Active",
        "ujumbe":  "Seva ya Akili ni Mali inafanya kazi vizuri",
        "wakati":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }), 200


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    POST /analyze
    Changanua miamala ya biashara kwa Phase 2 engine.

    Body:
    {
      "business_name": "Duka la Fatuma",
      "transactions": [
        {"type":"credit","amount":85000,"date":"2026-01-10","description":"..."},
        ...
      ]
    }

    Au SMS messages:
    {
      "business_name": "Biashara ya Hassan",
      "sms_messages": ["Umepokea TZS 50,000 ...","Umetuma TZS 200,000 ..."]
    }
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "JSON si sahihi / Invalid JSON"}), 400

    if not data:
        return jsonify({"error": "Mwili wa ombi ni tupu / Empty request body"}), 400

    business_name = data.get("business_name", "Biashara Isiyojulikana")
    transactions  = []

    # ── Source 1: Structured transactions ──
    if "transactions" in data:
        raw = data["transactions"]
        if not isinstance(raw, list) or len(raw) == 0:
            return jsonify({"error": "'transactions' lazima iwe orodha yenye angalau muamala 1"}), 400

        all_errors = []
        for i, tx in enumerate(raw):
            for e in validate_transaction(tx):
                all_errors.append(f"Muamala {i+1}: {e}")
        if all_errors:
            return jsonify({"error": "Validation failed", "makosa": all_errors}), 422

        transactions = raw

    # ── Source 2: Raw SMS ──
    elif "sms_messages" in data:
        sms_list = data["sms_messages"]
        if not isinstance(sms_list, list) or len(sms_list) == 0:
            return jsonify({"error": "'sms_messages' lazima iwe orodha"}), 400
        full_text = "\n".join(str(s) for s in sms_list)
        transactions = parse_sms(full_text)
        if not transactions:
            return jsonify({"error": "Hakuna ujumbe ulioweza kusomwa / No SMS could be parsed"}), 422

    else:
        return jsonify({
            "error": "Tuma 'transactions' au 'sms_messages'",
            "mfano": {
                "business_name": "Duka la Fatuma",
                "transactions": [
                    {"type":"credit","amount":85000,"date":"2026-01-10","description":"Malipo ya mteja"},
                    {"type":"debit","amount":200000,"date":"2026-01-01","description":"Kodi ya nyumba"},
                ]
            }
        }), 400

    # ── Run Phase 2 engine ──
    try:
        result = engine.analyze(transactions, business_name)
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500

    if "error" in result:
        return jsonify(result), 422

    return jsonify(result), 200


@app.route("/analyze/demo", methods=["GET", "POST"])
def analyze_demo():
    """
    POST /analyze/demo
    Body: {"business_type": "duka" | "msisitizo" | "mapambano"}
    """
    try:
        body = request.get_json(force=True, silent=True) or {}
    except Exception:
        body = {}

    btype = body.get("business_type", "duka")
    if btype not in ["duka", "msisitizo", "mapambano"]:
        btype = "duka"

    bname, transactions = generate_demo(btype)

    try:
        result = engine.analyze(transactions, bname)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    result["demo"]       = True
    result["demo_type"]  = btype
    return jsonify(result), 200


@app.route("/docs", methods=["GET"])
def docs():
    return jsonify({
        "title": "Akili ni Mali API v2.0 — Documentation",
        "phase2_features": {
            "hybrid_classifier": "25 Tanzania-specific categories, 3-layer classification",
            "anomaly_detection": ["HIGH_PROFIT_MARGIN","NEGATIVE_CASHFLOW","LOAN_INFLATION","REVENUE_DROP","NO_EXPENSES"],
            "scoring_formula": {
                "income_stability":   "30% — Coefficient of variation of monthly revenue",
                "transaction_freq":   "25% — Average monthly transaction count",
                "customer_diversity": "20% — Unique customer ratio",
                "cashflow_health":    "15% — Net flow ratio",
                "revenue_trend":      "10% — Month-over-month growth",
            },
            "decision_overrides": ["DECLINING_REVENUE","CRITICAL_ANOMALY","MISSING_EXPENSES","LOAN_INFLATION"],
        },
        "transaction_format": {
            "type":        "string — 'credit' (mapato) or 'debit' (matumizi)",
            "amount":      "number — Amount in TZS",
            "date":        "string — YYYY-MM-DD",
            "description": "string (optional) — Transaction description",
            "phone":       "string (optional) — Counterparty phone number",
        },
        "response_fields": {
            "fedha.true_avg_monthly_revenue": "Revenue excluding loans and agent float",
            "fedha.gross_credits_total":      "All incoming credits including loans",
            "tathmini.stability_score":       "Final weighted score 0-100",
            "tathmini.score_components":      "XAI breakdown — 5 components with weights",
            "tathmini.reasoning":             "Human-readable explanation for loan officers",
            "uamuzi_mkopo.decision":          "APPROVE / REVIEW / DECLINE",
            "uamuzi_mkopo.overrides_applied": "List of override rules triggered",
            "anomalies":                      "List of detected financial anomalies",
        }
    }), 200


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error":"404 — Endpoint haipatikani",
        "vituo":["GET /","GET /health","POST /analyze","POST /analyze/demo","GET /docs"]}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": f"500 — Hitilafu ya seva: {str(e)}"}), 500


# ══════════════════════════════════════════════════════════════
#  START
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("""
  ╔══════════════════════════════════════════════════════╗
  ║                                                      ║
  ║      🌍  AKILI NI MALI — API v2.0  🌍               ║
  ║                                                      ║
  ║   Phase 2 Intelligence Engine — ACTIVE               ║
  ║                                                      ║
  ║   URL:  http://localhost:5000                        ║
  ║                                                      ║
  ║   New in v2.0:                                       ║
  ║   ✓ Loans excluded from revenue                      ║
  ║   ✓ Anomaly detection (5 checks)                     ║
  ║   ✓ Decision overrides (4 rules)                     ║
  ║   ✓ XAI score breakdown (5 components)               ║
  ║   ✓ 25 Tanzania transaction categories               ║
  ║                                                      ║
  ║   Simama / Stop: Ctrl + C                            ║
  ║                                                      ║
  ╚══════════════════════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
