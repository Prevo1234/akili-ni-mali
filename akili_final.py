"""
╔══════════════════════════════════════════════════════════════╗
║      AKILI NI MALI — Production API v3.0                     ║
║      Phase 5: Deploy-Ready with ML + Database + 3-Context    ║
║                                                              ║
║  Ready for: Railway, Render, Heroku, DigitalOcean            ║
╚══════════════════════════════════════════════════════════════╝
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import random, re, json, os

app = Flask(__name__)

# ── Environment config ─────────────────────────────────────────
PORT     = int(os.environ.get("PORT", 5000))
ENV      = os.environ.get("FLASK_ENV", "production")
DB_PATH  = os.environ.get("DB_PATH", "akili_data.db")

# ── Import our modules ─────────────────────────────────────────
try:
    from akili_engine_v2 import FinancialProfileV2
    engine = FinancialProfileV2()
    ENGINE_OK = True
except Exception as e:
    ENGINE_OK = False
    print(f"⚠️  Engine import failed: {e}")

try:
    from akili_database import DatabaseManager, IntelligenceContextEngine
    db  = DatabaseManager(DB_PATH)
    ctx = IntelligenceContextEngine(db)
    DB_OK = True
except Exception as e:
    DB_OK = False
    print(f"⚠️  Database import failed: {e}")

try:
    from akili_ml_v4 import TanzaniaDataGenerator, CreditScoringModel, CreditIntelligence
    print("  Training ML model on startup (5,000 Tanzania businesses)...")
    _gen  = TanzaniaDataGenerator(seed=42)
    _data = _gen.generate_dataset(n=5000, verbose=False)
    _ml   = CreditScoringModel()
    _ml.train(_data, verbose=True)
    ci    = CreditIntelligence(_ml)
    ML_OK = True
    _ml_accuracy = round(_ml.metrics.get("best_cv", 0) * 100, 1)
    _ml_model    = _ml.metrics.get("best_model", "RandomForest")
    _ml_features = list(_ml.metrics.get("feature_importance", {}).keys())
    _ml_trained  = _ml.metrics.get("training_size", 0)
    _ml_models   = _ml.metrics.get("models", {})
    print(f"  ML model ready: {_ml_model} — {_ml_accuracy}% accuracy")
except Exception as e:
    ML_OK = False
    _ml_accuracy = 0
    _ml_model    = "unavailable"
    _ml_features = []
    _ml_trained  = 0
    _ml_models   = {}
    ci           = None
    print(f"  ML failed: {e}")
    ci    = None
    print(f"⚠️  ML import failed: {e}")

# ── CORS ───────────────────────────────────────────────────────
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

@app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return jsonify({}), 200

# ── HELPERS ────────────────────────────────────────────────────
VALID_SECTORS = ["retail","food","agri","transport","wholesale","services","general"]

def validate_transaction(tx):
    errors = []
    if "type" not in tx or tx["type"] not in ["credit","debit"]:
        errors.append("'type' lazima iwe 'credit' au 'debit'")
    if "amount" not in tx or not isinstance(tx["amount"],(int,float)) or tx["amount"]<0:
        errors.append("'amount' lazima iwe nambari chanya")
    if "date" not in tx:
        errors.append("'date' inahitajika (YYYY-MM-DD)")
    return errors

def parse_sms(text):
    lines = text.strip().split('\n')
    txns  = []
    for line in lines:
        lower = line.lower().strip()
        if not lower: continue
        if any(w in lower for w in ["umepokea","received","imeingia","credit"]):
            tx_type = "credit"
        elif any(w in lower for w in ["umetuma","sent","imetoka","debit","umelipa"]):
            tx_type = "debit"
        else:
            continue
        amt = re.search(r'TZS\s*([\d,]+)', line, re.I)
        if not amt: continue
        amount = int(amt.group(1).replace(',',''))
        dm = re.search(r'(\d{2}/\d{2}/\d{4})', line)
        date = f"{dm.group(1).split('/')[2]}-{dm.group(1).split('/')[1].zfill(2)}-{dm.group(1).split('/')[0].zfill(2)}" \
               if dm else datetime.now().strftime("%Y-%m-%d")
        desc = "Malipo ya mteja" if tx_type=="credit" else "Malipo ya nje"
        for kw,cat in [("kodi","Kodi ya nyumba"),("luku","LUKU umeme"),
                        ("tanesco","Bili ya umeme"),("mishahara","Mishahara"),
                        ("wasambazaji","Malipo ya wasambazaji")]:
            if kw in lower: desc=cat; break
        txns.append({"type":tx_type,"amount":amount,"date":date,"description":desc})
    return txns

def generate_demo(btype="duka"):
    configs = {
        "duka":{"name":"Duka la Mama Fatuma — Dar es Salaam",
            "daily_min":50000,"daily_max":180000,"daily_count":(3,7),
            "supplier":(120000,280000),"rent":180000,"elec":42000,"workers":100000},
        "msisitizo":{"name":"Biashara ya Hassan Spices — Zanzibar",
            "daily_min":15000,"daily_max":600000,"daily_count":(1,4),
            "supplier":(150000,500000),"rent":120000,"elec":28000,"workers":70000},
        "mapambano":{"name":"Mgahawa wa Juma — Mwanza",
            "daily_min":12000,"daily_max":65000,"daily_count":(1,3),
            "supplier":(80000,200000),"rent":250000,"elec":75000,"workers":180000},
    }
    cfg   = configs.get(btype, configs["duka"])
    txns  = []
    base  = datetime(2026,1,1)
    phones = [f"07{p}{random.randint(1000000,9999999)}"
              for p in ["12","54","55","69","88"] for _ in range(6)]
    for off in range(90):
        d = base + timedelta(days=off)
        if d.weekday()==6 and random.random()>0.35: continue
        for _ in range(random.randint(*cfg["daily_count"])):
            amt = round(random.randint(cfg["daily_min"],cfg["daily_max"])/500)*500
            txns.append({"type":"credit","amount":amt,
                "date":d.strftime("%Y-%m-%d"),"description":"Malipo ya mteja",
                "phone":random.choice(phones)})
        if d.weekday() in [0,3] and random.random()>0.35:
            sup = round(random.randint(*cfg["supplier"])/1000)*1000
            txns.append({"type":"debit","amount":sup,
                "date":d.strftime("%Y-%m-%d"),"description":"Malipo ya wasambazaji"})
        if d.day==1:
            txns.append({"type":"debit","amount":cfg["rent"],
                "date":d.strftime("%Y-%m-%d"),"description":"Kodi ya nyumba"})
        if d.day==15:
            txns.append({"type":"debit","amount":cfg["elec"],
                "date":d.strftime("%Y-%m-%d"),"description":"LUKU umeme TANESCO"})
        if d.day==28:
            txns.append({"type":"debit","amount":cfg["workers"],
                "date":d.strftime("%Y-%m-%d"),"description":"Mishahara ya wafanyakazi"})
    return cfg["name"], txns

# ══════════════════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "jina":    "Akili ni Mali API",
        "kauli":   "Akili ni Mali — Ujuzi ni Utajiri / Knowledge is Wealth",
        "toleo":   "3.0.0",
        "hali": {
            "engine":   "✅ Active" if ENGINE_OK else "❌ Failed",
            "database": "✅ Connected" if DB_OK    else "❌ Failed",
            "ml_model": f"✅ Ready ({_ml.metrics.get('best_cv','?')} accuracy)" if ML_OK else "⚠️  Rule-based mode",
        },
        "vituo": {
            "GET  /":              "API info",
            "GET  /portal":        "Bank lender portal — OPEN IN BROWSER",
            "GET  /dashboard-ui":  "Analyst dashboard UI",
            "GET  /health":        "Server health",
            "POST /analyze":       "Analyze + 3-context + ML score",
            "POST /analyze/demo":  "Demo analysis",
            "GET  /history":       "Saved analyses",
            "GET  /sector/<n>":    "Sector benchmark",
            "GET  /ecosystem":     "Ecosystem events",
            "GET  /dashboard":     "Loan officer summary",
        },
        "sectors": VALID_SECTORS,
    }), 200


@app.route("/health", methods=["GET"])
def health():
    db_count = 0
    if DB_OK:
        try:
            stats    = ctx.get_dashboard_stats()
            db_count = stats.get("total_analyses", 0)
        except:
            pass
    return jsonify({
        "hali":    "SAWA",
        "status":  "OK",
        "toleo":   "3.0.0",
        "engine":  ENGINE_OK,
        "database": DB_OK,
        "ml_ready": ML_OK,
        "total_analyses": db_count,
        "wakati":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }), 200


@app.route("/analyze", methods=["POST"])
def analyze():
    if not ENGINE_OK:
        return jsonify({"error":"Engine haipatikani / Engine unavailable"}), 503
    try:
        data = request.get_json(force=True)
    except:
        return jsonify({"error":"JSON si sahihi"}), 400
    if not data:
        return jsonify({"error":"Mwili wa ombi ni tupu"}), 400

    business_name = data.get("business_name","Biashara")
    sector        = data.get("sector","general")
    region        = data.get("region","Tanzania")
    if sector not in VALID_SECTORS: sector = "general"

    transactions = []
    if "transactions" in data:
        raw = data["transactions"]
        if not isinstance(raw,list) or not raw:
            return jsonify({"error":"'transactions' lazima iwe orodha"}), 400
        errors = []
        for i,tx in enumerate(raw):
            for e in validate_transaction(tx):
                errors.append(f"Muamala {i+1}: {e}")
        if errors:
            return jsonify({"error":"Validation failed","makosa":errors}), 422
        transactions = raw
    elif "sms_messages" in data:
        sms = data["sms_messages"]
        if not isinstance(sms,list): return jsonify({"error":"'sms_messages' lazima iwe orodha"}), 400
        transactions = parse_sms("\n".join(str(s) for s in sms))
        if not transactions: return jsonify({"error":"Hakuna ujumbe ulioweza kusomwa"}), 422
    else:
        return jsonify({"error":"Tuma 'transactions' au 'sms_messages'","mfano":{
            "business_name":"Duka la Fatuma","sector":"retail",
            "transactions":[
                {"type":"credit","amount":150000,"date":"2026-01-10","description":"Malipo ya mteja"},
                {"type":"debit","amount":200000,"date":"2026-01-01","description":"Kodi ya nyumba"},
            ]}}), 400

    try:
        result = engine.analyze(transactions, business_name)

        # Add ML scoring
        if ML_OK and ci:
            ml_score = ci.score(result)
            result["ml_scoring"] = ml_score

        # Add 3-context (database)
        if DB_OK:
            enriched = ctx.analyze_with_context(result, sector, region)
        else:
            enriched = result
            enriched["analysis_id"] = None

        return jsonify(enriched), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/analyze/demo", methods=["GET","POST"])
def analyze_demo():
    if not ENGINE_OK:
        return jsonify({"error":"Engine haipatikani"}), 503
    try:
        body = request.get_json(force=True, silent=True) or {}
    except:
        body = {}
    btype  = body.get("business_type","duka")
    sector = body.get("sector","retail")
    if btype  not in ["duka","msisitizo","mapambano"]: btype  = "duka"
    if sector not in VALID_SECTORS:                    sector = "retail"

    bname, txns = generate_demo(btype)
    try:
        result = engine.analyze(txns, bname)
        if ML_OK and ci:
            result["ml_scoring"] = ci.score(result)
        if DB_OK:
            enriched = ctx.analyze_with_context(result, sector)
        else:
            enriched = result
        enriched["demo"]      = True
        enriched["demo_type"] = btype
        return jsonify(enriched), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/history", methods=["GET"])
def history():
    if not DB_OK:
        return jsonify({"error":"Database haipatikani","analyses":[]}), 200
    sector = request.args.get("sector")
    biz    = request.args.get("business")
    limit  = min(int(request.args.get("limit",20)), 100)
    analyses = ctx.store.get_history(business_name=biz, sector=sector, limit=limit)
    return jsonify({"count":len(analyses),"analyses":analyses}), 200


@app.route("/history/<int:analysis_id>", methods=["GET"])
def history_by_id(analysis_id):
    if not DB_OK:
        return jsonify({"error":"Database haipatikani"}), 503
    result = ctx.store.get_by_id(analysis_id)
    if not result:
        return jsonify({"error":f"#{analysis_id} haupatikani"}), 404
    return jsonify(result), 200


@app.route("/sector/<sector_name>", methods=["GET"])
def sector_benchmark(sector_name):
    if not DB_OK:
        return jsonify({"error":"Database haipatikani"}), 503
    if sector_name not in VALID_SECTORS:
        return jsonify({"error":f"Sekta '{sector_name}' haijulikani","valid":VALID_SECTORS}), 400
    region = request.args.get("region","Tanzania")
    bench  = ctx.sector.compute_benchmarks(sector_name, region)
    return jsonify(bench), 200


@app.route("/ecosystem", methods=["GET"])
def ecosystem():
    if not DB_OK:
        return jsonify({"active_events":[],"ecosystem_clear":True,"ujumbe":"Database haipatikani"}), 200
    events = ctx.eco.get_active_events()
    scan   = ctx.eco.scan()
    return jsonify({
        "active_events":   events,
        "new_detections":  scan,
        "ecosystem_clear": len(events)==0,
        "ujumbe": "Mfumo ni sawa / Ecosystem clear" if not events
                  else f"Matukio {len(events)} yanafanya kazi",
    }), 200


@app.route("/dashboard", methods=["GET"])
def dashboard():
    if not DB_OK:
        return jsonify({"error":"Database haipatikani","total_analyses":0}), 200
    stats = ctx.get_dashboard_stats()
    eco   = ctx.eco.get_active_events()
    stats["ecosystem_events_active"] = eco
    stats["ml_ready"]  = ML_OK
    stats["ml_accuracy"] = round(_ml.metrics.get("best_cv",0)*100,1) if ML_OK else None
    return jsonify(stats), 200


@app.route("/ml/info", methods=["GET"])
def ml_info():
    if not ML_OK:
        return jsonify({"ready":False,"mode":"rule-based","message":"scikit-learn haipo"}), 200
    return jsonify({
        "ready":        True,
        "model":        _ml_model,
        "accuracy":     _ml_accuracy,
        "accuracy_pct": f"{_ml_accuracy}%",
        "trained_on":   _ml_trained,
        "features":     _ml_features[:5],
        "models":       _ml_models,
        "note":         "Trained on 5,000 synthetic Tanzania business profiles",
    }), 200


@app.route("/portal", methods=["GET"])
def portal():
    from flask import make_response
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Akili ni Mali — Bank Lender Portal</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=Instrument+Sans:wght@300;400;500;600&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
:root{
  --ink:    #0D1117;
  --ink2:   #161B22;
  --ink3:   #1C2333;
  --border: rgba(255,255,255,.06);
  --border2:rgba(255,255,255,.12);
  --gold:   #C9A84C;
  --gold2:  #E8C97A;
  --green:  #3FB950;
  --red:    #F85149;
  --amber:  #E3B341;
  --blue:   #58A6FF;
  --purple: #BC8CFF;
  --muted:  #8B949E;
  --text:   #C9D1D9;
  --white:  #F0F6FC;
}
html{scroll-behavior:smooth;}
body{background:var(--ink);font-family:'Instrument Sans',sans-serif;color:var(--text);min-height:100vh;overflow-x:hidden;}

/* ── SIDEBAR ── */
.sidebar{position:fixed;left:0;top:0;bottom:0;width:220px;background:var(--ink2);border-right:1px solid var(--border);display:flex;flex-direction:column;z-index:100;}
.sb-brand{padding:24px 20px 20px;border-bottom:1px solid var(--border);}
.sb-logo{font-family:'Syne',sans-serif;font-size:15px;font-weight:700;color:var(--white);letter-spacing:.04em;}
.sb-logo span{color:var(--gold);}
.sb-tag{font-size:9px;letter-spacing:.2em;text-transform:uppercase;color:var(--muted);margin-top:3px;}
.sb-nav{flex:1;padding:16px 0;overflow-y:auto;}
.sb-section{font-size:9px;letter-spacing:.22em;text-transform:uppercase;color:var(--muted);padding:12px 20px 6px;margin-top:4px;}
.sb-item{display:flex;align-items:center;gap:10px;padding:9px 20px;font-size:13px;color:var(--muted);cursor:pointer;transition:all .2s;border-left:2px solid transparent;text-decoration:none;}
.sb-item:hover{color:var(--text);background:rgba(255,255,255,.03);}
.sb-item.active{color:var(--white);background:rgba(201,168,76,.08);border-left-color:var(--gold);}
.sb-item .icon{font-size:15px;width:18px;text-align:center;}
.sb-item .badge{margin-left:auto;background:var(--gold);color:var(--ink);font-size:9px;font-weight:700;padding:2px 6px;border-radius:10px;}
.sb-bottom{padding:16px 20px;border-top:1px solid var(--border);}
.sb-user{display:flex;align-items:center;gap:10px;}
.sb-avatar{width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,var(--gold),var(--ink3));display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:var(--ink);font-family:'Syne',sans-serif;}
.sb-uname{font-size:12px;font-weight:600;color:var(--text);}
.sb-urole{font-size:10px;color:var(--muted);}
.sb-dot{width:7px;height:7px;border-radius:50%;background:var(--green);margin-left:auto;box-shadow:0 0 6px rgba(63,185,80,.5);}

/* ── MAIN ── */
.main{margin-left:220px;min-height:100vh;display:flex;flex-direction:column;}
.topbar{height:56px;background:var(--ink2);border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;padding:0 32px;position:sticky;top:0;z-index:50;}
.tb-page{font-family:'Syne',sans-serif;font-size:14px;font-weight:600;color:var(--white);}
.tb-right{display:flex;align-items:center;gap:16px;}
.tb-api{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--muted);}
.api-dot{width:6px;height:6px;border-radius:50%;background:var(--green);animation:pulse 2s ease-in-out infinite;}
@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(63,185,80,.4);}50%{opacity:.8;box-shadow:0 0 0 4px rgba(63,185,80,0);}}
.tb-btn{font-size:12px;font-weight:600;padding:7px 16px;border-radius:6px;border:none;cursor:pointer;font-family:'Instrument Sans',sans-serif;transition:all .2s;}
.btn-primary{background:var(--gold);color:var(--ink);}
.btn-primary:hover{background:var(--gold2);}
.btn-ghost{background:transparent;color:var(--text);border:1px solid var(--border2);}
.btn-ghost:hover{border-color:var(--gold);color:var(--gold);}

.content{flex:1;padding:32px;}

/* ── PAGES ── */
.page{display:none;}
.page.active{display:block;animation:fadeIn .3s ease;}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px);}to{opacity:1;transform:translateY(0);}}

/* ── KPI STRIP ── */
.kpi-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px;}
.kpi-card{background:var(--ink2);border:1px solid var(--border);border-radius:10px;padding:20px;position:relative;overflow:hidden;transition:border .3s;}
.kpi-card:hover{border-color:var(--border2);}
.kpi-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;}
.kpi-card.g::before{background:var(--green);}
.kpi-card.a::before{background:var(--amber);}
.kpi-card.r::before{background:var(--red);}
.kpi-card.b::before{background:var(--blue);}
.kpi-label{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);margin-bottom:10px;}
.kpi-val{font-family:'Syne',sans-serif;font-size:28px;font-weight:700;color:var(--white);line-height:1;}
.kpi-sub{font-size:11px;color:var(--muted);margin-top:6px;}
.kpi-trend{position:absolute;top:16px;right:16px;font-size:12px;font-weight:600;}

/* ── SECTION HEADERS ── */
.sec-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;}
.sec-title{font-family:'Syne',sans-serif;font-size:14px;font-weight:600;color:var(--white);}
.sec-sub{font-size:11px;color:var(--muted);}

/* ── APPLICATIONS TABLE ── */
.app-table{width:100%;border-collapse:collapse;background:var(--ink2);border-radius:10px;overflow:hidden;border:1px solid var(--border);}
.app-table th{font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);padding:12px 16px;text-align:left;border-bottom:1px solid var(--border);background:var(--ink3);}
.app-table td{padding:14px 16px;font-size:13px;color:var(--text);border-bottom:1px solid rgba(255,255,255,.03);}
.app-table tr:last-child td{border:none;}
.app-table tr:hover td{background:rgba(255,255,255,.02);cursor:pointer;}
.score-pill{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;}
.score-high{background:rgba(63,185,80,.12);color:var(--green);border:1px solid rgba(63,185,80,.25);}
.score-med{background:rgba(227,179,65,.12);color:var(--amber);border:1px solid rgba(227,179,65,.25);}
.score-low{background:rgba(248,81,73,.12);color:var(--red);border:1px solid rgba(248,81,73,.25);}
.dec-badge{font-size:10px;font-weight:700;letter-spacing:.08em;padding:4px 10px;border-radius:4px;text-transform:uppercase;}
.dec-approve{background:rgba(63,185,80,.1);color:var(--green);}
.dec-review{background:rgba(227,179,65,.1);color:var(--amber);}
.dec-decline{background:rgba(248,81,73,.1);color:var(--red);}
.biz-cell{display:flex;align-items:center;gap:10px;}
.biz-icon{width:34px;height:34px;border-radius:8px;background:rgba(201,168,76,.12);border:1px solid rgba(201,168,76,.2);display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;}
.biz-name{font-weight:600;color:var(--white);font-size:13px;}
.biz-type{font-size:10px;color:var(--muted);}

/* ── DETAIL PANEL ── */
.detail-panel{background:var(--ink2);border:1px solid var(--border);border-radius:12px;padding:28px;display:none;}
.detail-panel.open{display:block;animation:fadeIn .3s ease;}
.dp-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px;padding-bottom:20px;border-bottom:1px solid var(--border);}
.dp-biz{font-family:'Syne',sans-serif;font-size:20px;font-weight:700;color:var(--white);}
.dp-meta{font-size:12px;color:var(--muted);margin-top:4px;}
.dp-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:20px;}
.dp-metric{background:var(--ink3);border-radius:8px;padding:16px;border:1px solid var(--border);}
.dp-mlabel{font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-bottom:8px;}
.dp-mval{font-family:'Syne',sans-serif;font-size:22px;font-weight:700;color:var(--white);}
.dp-msub{font-size:11px;color:var(--muted);margin-top:4px;}
.score-ring{position:relative;width:110px;height:110px;margin:0 auto 16px;}
.score-ring svg{transform:rotate(-90deg);}
.score-center{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center;}
.score-num{font-family:'Syne',sans-serif;font-size:24px;font-weight:800;color:var(--white);}
.score-lbl{font-size:9px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);}
.reasons-list{list-style:none;}
.reasons-list li{display:flex;gap:8px;font-size:12px;color:var(--text);padding:7px 0;border-bottom:1px solid rgba(255,255,255,.03);line-height:1.5;}
.reasons-list li:last-child{border:none;}
.reasons-list .arr{color:var(--gold);flex-shrink:0;}
.action-row{display:flex;gap:12px;margin-top:20px;padding-top:20px;border-top:1px solid var(--border);}
.act-btn{flex:1;padding:12px;border-radius:8px;font-size:13px;font-weight:600;border:none;cursor:pointer;font-family:'Instrument Sans',sans-serif;transition:all .2s;display:flex;align-items:center;justify-content:center;gap:8px;}
.act-approve{background:rgba(63,185,80,.15);color:var(--green);border:1px solid rgba(63,185,80,.3);}
.act-approve:hover{background:rgba(63,185,80,.25);}
.act-review{background:rgba(227,179,65,.15);color:var(--amber);border:1px solid rgba(227,179,65,.3);}
.act-review:hover{background:rgba(227,179,65,.25);}
.act-decline{background:rgba(248,81,73,.15);color:var(--red);border:1px solid rgba(248,81,73,.3);}
.act-decline:hover{background:rgba(248,81,73,.25);}
.notes-area{width:100%;background:var(--ink3);border:1px solid var(--border);border-radius:8px;padding:12px;color:var(--text);font-family:'Instrument Sans',sans-serif;font-size:13px;resize:vertical;min-height:80px;outline:none;margin-top:12px;transition:border .2s;}
.notes-area:focus{border-color:rgba(201,168,76,.4);}

/* ── UPLOAD SECTION ── */
.upload-area{border:2px dashed rgba(201,168,76,.25);border-radius:12px;padding:48px;text-align:center;cursor:pointer;transition:all .3s;background:rgba(201,168,76,.02);}
.upload-area:hover,.upload-area.drag{border-color:rgba(201,168,76,.5);background:rgba(201,168,76,.04);}
.upload-icon{font-size:40px;margin-bottom:14px;display:block;}
.upload-title{font-family:'Syne',sans-serif;font-size:16px;font-weight:600;color:var(--white);margin-bottom:8px;}
.upload-sub{font-size:13px;color:var(--muted);}
.upload-formats{display:flex;gap:8px;justify-content:center;margin-top:16px;}
.fmt{font-size:10px;letter-spacing:.1em;text-transform:uppercase;padding:4px 10px;border-radius:4px;border:1px solid var(--border2);color:var(--muted);}
.sms-box{background:var(--ink2);border:1px solid var(--border);border-radius:12px;padding:24px;margin-top:16px;}
.sms-title{font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:var(--gold);margin-bottom:12px;}
.sms-ta{width:100%;background:var(--ink3);border:1px solid var(--border);border-radius:8px;padding:14px;color:var(--text);font-family:'DM Mono',monospace;font-size:12px;line-height:1.8;resize:vertical;min-height:130px;outline:none;transition:border .2s;}
.sms-ta:focus{border-color:rgba(201,168,76,.4);}
.field-row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:20px;}
.field-wrap label{font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);display:block;margin-bottom:7px;}
.field-input{width:100%;background:var(--ink3);border:1px solid var(--border);border-radius:8px;padding:11px 14px;color:var(--text);font-family:'Instrument Sans',sans-serif;font-size:13px;outline:none;transition:border .2s;}
.field-input:focus{border-color:rgba(201,168,76,.4);}
select.field-input option{background:var(--ink3);}

/* ── PORTFOLIO CHARTS ── */
.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px;}
.chart-card{background:var(--ink2);border:1px solid var(--border);border-radius:10px;padding:24px;}
.chart-title{font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-bottom:18px;}
.bar-chart{display:flex;align-items:flex-end;gap:8px;height:100px;}
.bar-wrap{flex:1;display:flex;flex-direction:column;align-items:center;gap:6px;}
.bar{width:100%;border-radius:4px 4px 0 0;min-height:4px;transition:height .8s ease;}
.bar-lbl{font-size:9px;color:var(--muted);text-align:center;}
.bar-val{font-size:10px;font-weight:600;color:var(--text);}
.donut-wrap{display:flex;align-items:center;gap:24px;}
.donut-legend{display:flex;flex-direction:column;gap:10px;flex:1;}
.leg-row{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text);}
.leg-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;}

/* ── LOADING ── */
.loader{display:flex;align-items:center;justify-content:center;gap:12px;padding:40px;color:var(--muted);font-size:13px;}
.spin{width:22px;height:22px;border:2px solid var(--border2);border-top-color:var(--gold);border-radius:50%;animation:spin .7s linear infinite;}
@keyframes spin{to{transform:rotate(360deg);}}

/* ── EMPTY STATE ── */
.empty{text-align:center;padding:60px 20px;color:var(--muted);}
.empty-icon{font-size:40px;display:block;margin-bottom:14px;opacity:.5;}
.empty-text{font-size:14px;margin-bottom:6px;color:var(--text);}
.empty-sub{font-size:12px;}

/* ── TOAST ── */
.toast{position:fixed;bottom:24px;right:24px;background:var(--ink2);border:1px solid var(--border2);border-radius:8px;padding:14px 20px;font-size:13px;color:var(--white);z-index:9999;display:flex;align-items:center;gap:10px;box-shadow:0 8px 24px rgba(0,0,0,.4);transform:translateY(80px);opacity:0;transition:all .3s;}
.toast.show{transform:translateY(0);opacity:1;}
.toast.success{border-color:rgba(63,185,80,.4);}
.toast.error{border-color:rgba(248,81,73,.4);}

/* ── RESPONSIVE ── */
@media(max-width:900px){
  .sidebar{width:60px;}
  .sb-item span:not(.icon){display:none;}
  .sb-brand .sb-tag,.sb-logo{display:none;}
  .sb-section{display:none;}
  .sb-user .sb-uname,.sb-urole{display:none;}
  .main{margin-left:60px;}
  .kpi-strip{grid-template-columns:1fr 1fr;}
  .dp-grid,.field-row,.chart-grid{grid-template-columns:1fr;}
}

::-webkit-scrollbar{width:4px;}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:2px;}
input[type=file]{display:none;}
</style>
</head>
<body>

<!-- SIDEBAR -->
<aside class="sidebar">
  <div class="sb-brand">
    <div class="sb-logo">Akili <span>ni</span> Mali</div>
    <div class="sb-tag">Lender Portal</div>
  </div>
  <nav class="sb-nav">
    <div class="sb-section">Main</div>
    <a class="sb-item active" onclick="showPage('dashboard',this)">
      <span class="icon">📊</span><span>Dashboard</span>
    </a>
    <a class="sb-item" onclick="showPage('applications',this)">
      <span class="icon">📋</span><span>Applications</span>
      <span class="badge" id="app-badge">0</span>
    </a>
    <a class="sb-item" onclick="showPage('new-analysis',this)">
      <span class="icon">⚡</span><span>New Analysis</span>
    </a>
    <div class="sb-section">Intelligence</div>
    <a class="sb-item" onclick="showPage('portfolio',this)">
      <span class="icon">💼</span><span>Portfolio</span>
    </a>
    <a class="sb-item" onclick="showPage('ecosystem',this)">
      <span class="icon">🌍</span><span>Ecosystem</span>
    </a>
    <div class="sb-section">System</div>
    <a class="sb-item" onclick="showPage('settings',this)">
      <span class="icon">⚙️</span><span>Settings</span>
    </a>
  </nav>
  <div class="sb-bottom">
    <div class="sb-user">
      <div class="sb-avatar">LO</div>
      <div>
        <div class="sb-uname">Loan Officer</div>
        <div class="sb-urole">Senior Analyst</div>
      </div>
      <div class="sb-dot"></div>
    </div>
  </div>
</aside>

<!-- MAIN -->
<div class="main">
  <div class="topbar">
    <div class="tb-page" id="page-title">Dashboard</div>
    <div class="tb-right">
      <div class="tb-api">
        <div class="api-dot" id="api-indicator"></div>
        <span id="api-status-text">Connecting...</span>
      </div>
      <button class="tb-btn btn-ghost" onclick="refreshAll()">↻ Refresh</button>
      <button class="tb-btn btn-primary" onclick="showPage('new-analysis',null)">+ New Analysis</button>
    </div>
  </div>

  <div class="content">

    <!-- ═══════════════════════════════════════════════════
         PAGE: DASHBOARD
    ════════════════════════════════════════════════════ -->
    <div class="page active" id="page-dashboard">
      <div class="kpi-strip">
        <div class="kpi-card g">
          <div class="kpi-label">Total Analyses</div>
          <div class="kpi-val" id="kpi-total">—</div>
          <div class="kpi-sub">All time</div>
          <div class="kpi-trend" style="color:var(--green)">↑</div>
        </div>
        <div class="kpi-card g">
          <div class="kpi-label">Approved</div>
          <div class="kpi-val" id="kpi-approved">—</div>
          <div class="kpi-sub" id="kpi-approve-rate">—% rate</div>
        </div>
        <div class="kpi-card a">
          <div class="kpi-label">Under Review</div>
          <div class="kpi-val" id="kpi-review">—</div>
          <div class="kpi-sub">Needs attention</div>
        </div>
        <div class="kpi-card r">
          <div class="kpi-label">Declined</div>
          <div class="kpi-val" id="kpi-declined">—</div>
          <div class="kpi-sub">High risk</div>
        </div>
      </div>

      <!-- Recent analyses -->
      <div class="sec-hdr">
        <div>
          <div class="sec-title">Recent Analyses</div>
          <div class="sec-sub">Latest loan applications processed by Akili ni Mali AI</div>
        </div>
        <button class="tb-btn btn-ghost" onclick="showPage('applications',null)">View all →</button>
      </div>
      <div id="recent-table-wrap">
        <div class="loader"><div class="spin"></div>Loading analyses...</div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════
         PAGE: APPLICATIONS
    ════════════════════════════════════════════════════ -->
    <div class="page" id="page-applications">
      <div class="sec-hdr" style="margin-bottom:20px">
        <div>
          <div class="sec-title">All Applications</div>
          <div class="sec-sub">Complete loan application history with AI scoring</div>
        </div>
        <div style="display:flex;gap:10px">
          <select id="filter-decision" onchange="filterApplications()" style="background:var(--ink2);border:1px solid var(--border2);color:var(--text);padding:8px 12px;border-radius:6px;font-size:12px;font-family:'Instrument Sans',sans-serif;outline:none;">
            <option value="">All Decisions</option>
            <option value="APPROVE">Approved</option>
            <option value="REVIEW">Review</option>
            <option value="DECLINE">Declined</option>
          </select>
        </div>
      </div>
      <div id="all-apps-wrap">
        <div class="loader"><div class="spin"></div>Loading...</div>
      </div>

      <!-- Detail Panel -->
      <div class="detail-panel" id="detail-panel" style="margin-top:20px">
        <div class="dp-header">
          <div>
            <div class="dp-biz" id="dp-name">—</div>
            <div class="dp-meta" id="dp-meta">—</div>
          </div>
          <div id="dp-decision-badge" class="dec-badge dec-approve">—</div>
        </div>

        <!-- Score ring + metrics -->
        <div style="display:grid;grid-template-columns:140px 1fr;gap:24px;margin-bottom:20px;align-items:start">
          <div style="text-align:center">
            <div class="score-ring">
              <svg width="110" height="110" viewBox="0 0 110 110">
                <circle cx="55" cy="55" r="45" fill="none" stroke="rgba(255,255,255,.06)" stroke-width="8"/>
                <circle cx="55" cy="55" r="45" fill="none" stroke="var(--gold)" stroke-width="8"
                  stroke-linecap="round" stroke-dasharray="283" id="score-arc" stroke-dashoffset="283"/>
              </svg>
              <div class="score-center">
                <div class="score-num" id="dp-score">—</div>
                <div class="score-lbl">Score</div>
              </div>
            </div>
            <div id="dp-health" style="font-size:12px;font-weight:600;margin-top:4px">—</div>
          </div>
          <div class="dp-grid" style="grid-template-columns:1fr 1fr 1fr">
            <div class="dp-metric">
              <div class="dp-mlabel">Revenue</div>
              <div class="dp-mval" id="dp-revenue">—</div>
              <div class="dp-msub">TZS / month</div>
            </div>
            <div class="dp-metric">
              <div class="dp-mlabel">Net Flow</div>
              <div class="dp-mval" id="dp-netflow">—</div>
              <div class="dp-msub">TZS / month</div>
            </div>
            <div class="dp-metric">
              <div class="dp-mlabel">Max Loan</div>
              <div class="dp-mval" id="dp-loan">—</div>
              <div class="dp-msub">TZS recommended</div>
            </div>
          </div>
        </div>

        <!-- Reasoning -->
        <div style="background:var(--ink3);border-radius:8px;padding:18px;border-left:3px solid var(--gold);margin-bottom:16px">
          <div style="font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--gold);margin-bottom:12px">AI Reasoning — Loan Officer Notes</div>
          <ul class="reasons-list" id="dp-reasons"></ul>
        </div>

        <!-- Anomalies -->
        <div id="dp-anomalies-wrap" style="display:none;margin-bottom:16px">
          <div style="font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--amber);margin-bottom:10px">⚠️ Anomalies Detected</div>
          <div id="dp-anomalies"></div>
        </div>

        <!-- Officer notes + actions -->
        <div style="font-size:11px;color:var(--muted);margin-bottom:6px">Officer Notes (optional)</div>
        <textarea class="notes-area" id="dp-notes" placeholder="Add your assessment notes here..."></textarea>

        <div class="action-row">
          <button class="act-btn act-approve" onclick="makeDecision('APPROVE')">✓ Approve Loan</button>
          <button class="act-btn act-review" onclick="makeDecision('REVIEW')">◎ Request More Info</button>
          <button class="act-btn act-decline" onclick="makeDecision('DECLINE')">✗ Decline</button>
        </div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════
         PAGE: NEW ANALYSIS
    ════════════════════════════════════════════════════ -->
    <div class="page" id="page-new-analysis">
      <div class="sec-hdr" style="margin-bottom:24px">
        <div>
          <div class="sec-title">New Loan Application Analysis</div>
          <div class="sec-sub">Upload mobile money statement or paste SMS messages for instant AI assessment</div>
        </div>
      </div>

      <div class="field-row">
        <div class="field-wrap">
          <label>Business Name / Jina la Biashara</label>
          <input type="text" class="field-input" id="new-biz-name" placeholder="e.g. Duka la Fatuma">
        </div>
        <div class="field-wrap">
          <label>Business Sector / Sekta</label>
          <select class="field-input" id="new-sector">
            <option value="general">General Business</option>
            <option value="retail">Retail / Maduka</option>
            <option value="food">Food & Restaurant / Chakula</option>
            <option value="agri">Agriculture / Kilimo</option>
            <option value="transport">Transport / Usafiri</option>
            <option value="wholesale">Wholesale / Biashara Kubwa</option>
            <option value="services">Services / Huduma</option>
          </select>
        </div>
        <div class="field-wrap">
          <label>Region / Mkoa</label>
          <input type="text" class="field-input" id="new-region" placeholder="e.g. Dar es Salaam">
        </div>
      </div>

      <!-- Upload zone -->
      <div class="upload-area" id="upload-zone" onclick="document.getElementById('csv-file').click()">
        <span class="upload-icon">📂</span>
        <div class="upload-title">Upload Mobile Money Statement</div>
        <div class="upload-sub">Drag & drop CSV file or click to browse</div>
        <div class="upload-formats">
          <span class="fmt">CSV</span>
          <span class="fmt">TXT</span>
          <span class="fmt">M-Pesa</span>
          <span class="fmt">Airtel</span>
          <span class="fmt">Tigo</span>
        </div>
        <input type="file" id="csv-file" accept=".csv,.txt" onchange="handleCSV(this)">
      </div>

      <div style="text-align:center;margin:16px 0;font-size:12px;color:var(--muted)">— or paste raw SMS messages —</div>

      <div class="sms-box">
        <div class="sms-title">📱 Paste SMS Transaction Messages</div>
        <textarea class="sms-ta" id="new-sms" placeholder="Umepokea TZS 50,000 kutoka 0712345678 tarehe 10/01/2026&#10;Umetuma TZS 200,000 kwa Landlord tarehe 01/01/2026&#10;You have received TZS 85,000 from 0754987654..."></textarea>
        <div style="font-size:11px;color:var(--muted);margin-top:8px">Supports M-Pesa, Airtel Money, Tigo Pesa — Swahili or English</div>
      </div>

      <div style="display:flex;gap:12px;margin-top:20px;flex-wrap:wrap">
        <button class="tb-btn btn-ghost" onclick="loadDemoData('duka')" style="padding:10px 20px">Demo: Duka (Stable)</button>
        <button class="tb-btn btn-ghost" onclick="loadDemoData('msisitizo')" style="padding:10px 20px">Demo: Seasonal</button>
        <button class="tb-btn btn-ghost" onclick="loadDemoData('mapambano')" style="padding:10px 20px">Demo: Struggling</button>
        <button class="tb-btn btn-primary" onclick="runNewAnalysis()" style="padding:10px 28px;margin-left:auto">⚡ Run AI Analysis →</button>
      </div>

      <!-- Result -->
      <div id="new-result" style="margin-top:24px;display:none">
        <div style="height:1px;background:var(--border);margin-bottom:24px"></div>
        <div class="sec-title" style="margin-bottom:16px">Analysis Result</div>
        <div id="new-result-content"></div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════
         PAGE: PORTFOLIO
    ════════════════════════════════════════════════════ -->
    <div class="page" id="page-portfolio">
      <div class="sec-hdr" style="margin-bottom:24px">
        <div>
          <div class="sec-title">Portfolio Overview</div>
          <div class="sec-sub">Sector distribution and performance metrics</div>
        </div>
      </div>
      <div class="chart-grid" id="portfolio-charts">
        <div class="loader"><div class="spin"></div>Loading portfolio...</div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════
         PAGE: ECOSYSTEM
    ════════════════════════════════════════════════════ -->
    <div class="page" id="page-ecosystem">
      <div class="sec-hdr" style="margin-bottom:24px">
        <div>
          <div class="sec-title">Ecosystem Intelligence</div>
          <div class="sec-sub">System-wide event detection — Layer 3 Analysis</div>
        </div>
      </div>
      <div id="eco-content">
        <div class="loader"><div class="spin"></div>Scanning ecosystem...</div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════════
         PAGE: SETTINGS
    ════════════════════════════════════════════════════ -->
    <div class="page" id="page-settings">
      <div class="sec-title" style="margin-bottom:20px">Settings</div>
      <div style="background:var(--ink2);border:1px solid var(--border);border-radius:10px;padding:24px">
        <div style="font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-bottom:16px">API Configuration</div>
        <div class="field-wrap" style="margin-bottom:14px">
          <label>API Endpoint</label>
          <input type="text" class="field-input" id="api-url-input" value="http://127.0.0.1:5000" placeholder="http://127.0.0.1:5000">
        </div>
        <button class="tb-btn btn-primary" onclick="saveSettings()">Save Settings</button>
        <div style="margin-top:20px;padding-top:20px;border-top:1px solid var(--border)">
          <div style="font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-bottom:12px">System Status</div>
          <div id="sys-status" style="font-size:13px;color:var(--muted)">Loading...</div>
        </div>
      </div>
    </div>

  </div><!-- /content -->
</div><!-- /main -->

<!-- TOAST -->
<div class="toast" id="toast"></div>

<script>
// ═══════════════════════════════════════════════════════
//  CONFIG
// ═══════════════════════════════════════════════════════
let API = localStorage.getItem('akili_api') || 'http://127.0.0.1:5000';
let allAnalyses = [];
let currentAnalysis = null;
let demoMode = null;

// ── API CHECK ──────────────────────────────────────────
async function checkAPI(){
  try{
    const r = await fetch(`${API}/health`, {signal: AbortSignal.timeout(4000)});
    const d = await r.json();
    if(d.status==='OK'){
      document.getElementById('api-status-text').textContent = `API v${d.toleo||'3'} Connected`;
      document.getElementById('api-indicator').style.background = 'var(--green)';
      return true;
    }
  } catch(e){
    document.getElementById('api-status-text').textContent = 'API Offline';
    document.getElementById('api-indicator').style.background = 'var(--red)';
  }
  return false;
}

// ── NAVIGATION ─────────────────────────────────────────
const pageTitles = {
  'dashboard':    'Dashboard',
  'applications': 'Loan Applications',
  'new-analysis': 'New Analysis',
  'portfolio':    'Portfolio',
  'ecosystem':    'Ecosystem Intelligence',
  'settings':     'Settings',
};

function showPage(id, el){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.sb-item').forEach(i=>i.classList.remove('active'));
  document.getElementById(`page-${id}`).classList.add('active');
  if(el) el.classList.add('active');
  document.getElementById('page-title').textContent = pageTitles[id] || id;
  if(id==='dashboard')    loadDashboard();
  if(id==='applications') loadApplications();
  if(id==='portfolio')    loadPortfolio();
  if(id==='ecosystem')    loadEcosystem();
  if(id==='settings')     loadSettings();
}

// ── FORMAT HELPERS ─────────────────────────────────────
function fmtM(n){
  n = n||0;
  if(n>=1000000) return (n/1000000).toFixed(1)+'M';
  if(n>=1000)    return (n/1000).toFixed(0)+'K';
  return Math.round(n).toString();
}
function fmtTZS(n){return new Intl.NumberFormat('en-TZ').format(Math.round(n||0));}
function decClass(d){return d==='APPROVE'?'dec-approve':d==='REVIEW'?'dec-review':'dec-decline';}
function scoreClass(s){return s>=70?'score-high':s>=50?'score-med':'score-low';}

// ── TOAST ──────────────────────────────────────────────
function toast(msg, type='success'){
  const t = document.getElementById('toast');
  t.textContent = (type==='success'?'✓ ':type==='error'?'✗ ':'ℹ ') + msg;
  t.className = `toast show ${type}`;
  setTimeout(()=>t.classList.remove('show'), 3000);
}

// ── BUILD ANALYSIS TABLE ───────────────────────────────
function buildTable(analyses, containerId, clickable=true){
  const el = document.getElementById(containerId);
  if(!analyses || analyses.length===0){
    el.innerHTML = `<div class="empty"><span class="empty-icon">📋</span><div class="empty-text">No analyses yet</div><div class="empty-sub">Run a new analysis to get started</div></div>`;
    return;
  }
  const icons = {retail:'🏪',food:'🍽️',agri:'🌾',transport:'🚗',wholesale:'📦',services:'✂️',general:'💼'};
  el.innerHTML = `<table class="app-table">
    <thead><tr>
      <th>Business / Biashara</th>
      <th>Score</th>
      <th>Revenue</th>
      <th>Decision</th>
      <th>Date</th>
    </tr></thead>
    <tbody>${analyses.map(a => `
      <tr ${clickable?`onclick="openDetail(${a.id||0})"`:''}  data-dec="${a.decision||''}">
        <td><div class="biz-cell">
          <div class="biz-icon">${icons[a.sector]||'💼'}</div>
          <div><div class="biz-name">${a.business_name||'—'}</div>
          <div class="biz-type">${a.sector||'general'} · ${a.region||'Tanzania'}</div></div>
        </div></td>
        <td><span class="score-pill ${scoreClass(a.stability_score||0)}">${a.stability_score||0}/100</span></td>
        <td style="font-family:'DM Mono',monospace;font-size:12px">TZS ${fmtM(a.true_avg_revenue)}/mo</td>
        <td><span class="dec-badge ${decClass(a.decision)}">${a.decision||'—'}</span></td>
        <td style="font-size:11px;color:var(--muted)">${(a.analyzed_at||'').slice(0,16).replace('T',' ')}</td>
      </tr>`).join('')}
    </tbody></table>`;
}

// ══════════════════════════════════════════════════════
//  LOAD DASHBOARD
// ══════════════════════════════════════════════════════
async function loadDashboard(){
  try{
    const r = await fetch(`${API}/dashboard`);
    const d = await r.json();
    document.getElementById('kpi-total').textContent    = d.total_analyses||0;
    document.getElementById('kpi-approved').textContent = d.approved||0;
    document.getElementById('kpi-review').textContent   = d.review||0;
    document.getElementById('kpi-declined').textContent = d.declined||0;
    document.getElementById('kpi-approve-rate').textContent = `${d.approve_rate_pct||0}% rate`;
    document.getElementById('app-badge').textContent    = d.review||0;
    const recent = (d.recent_analyses||d.hivi_karibuni||[]).slice(0,8);
    buildTable(recent, 'recent-table-wrap', true);
  } catch(e){
    document.getElementById('recent-table-wrap').innerHTML =
      `<div class="empty"><span class="empty-icon">⚡</span><div class="empty-text">Make sure akili_api_v3.py is running</div><div class="empty-sub">Then refresh this page</div></div>`;
  }
}

// ══════════════════════════════════════════════════════
//  LOAD APPLICATIONS
// ══════════════════════════════════════════════════════
async function loadApplications(){
  try{
    const r = await fetch(`${API}/history?limit=50`);
    const d = await r.json();
    allAnalyses = d.analyses || [];
    buildTable(allAnalyses, 'all-apps-wrap', true);
  } catch(e){
    document.getElementById('all-apps-wrap').innerHTML =
      `<div class="empty"><span class="empty-icon">⚠️</span><div class="empty-text">Could not load applications</div></div>`;
  }
}

function filterApplications(){
  const filter = document.getElementById('filter-decision').value;
  const filtered = filter ? allAnalyses.filter(a=>a.decision===filter) : allAnalyses;
  buildTable(filtered, 'all-apps-wrap', true);
}

// ══════════════════════════════════════════════════════
//  OPEN DETAIL
// ══════════════════════════════════════════════════════
async function openDetail(id){
  const panel = document.getElementById('detail-panel');
  panel.classList.add('open');
  panel.scrollIntoView({behavior:'smooth', block:'start'});

  try{
    const r = await fetch(`${API}/history/${id}`);
    const d = await r.json();
    currentAnalysis = d;
    const result = d.full_result || {};
    const f = result.fedha || {};
    const t = result.tathmini || {};
    const u = result.uamuzi_mkopo || {};
    const b = result.biashara || {};
    const anomalies = result.anomalies || [];

    document.getElementById('dp-name').textContent    = d.business_name || '—';
    document.getElementById('dp-meta').textContent    = `${b.total_transactions||0} transactions · ${b.months_analyzed||0} months · ${d.sector||'general'} · ${d.region||'Tanzania'} · Analysis #${id}`;
    document.getElementById('dp-revenue').textContent = fmtM(f.true_avg_monthly_revenue || f.avg_monthly_revenue_tzs);
    document.getElementById('dp-netflow').textContent = fmtM(f.avg_net_cash_flow_tzs);
    document.getElementById('dp-loan').textContent    = fmtM(u.max_loan_amount_tzs);

    const score = t.stability_score || 0;
    document.getElementById('dp-score').textContent   = score;
    const scoreColor = score>=70?'var(--green)':score>=50?'var(--amber)':'var(--red)';
    document.getElementById('score-arc').style.stroke = scoreColor;
    const offset = 283 - (283 * score / 100);
    setTimeout(()=>{ document.getElementById('score-arc').style.strokeDashoffset = offset; }, 100);
    document.getElementById('dp-health').textContent  = t.business_health || '';
    document.getElementById('dp-health').style.color  = scoreColor;

    const dec = u.decision || d.decision || 'REVIEW';
    const badge = document.getElementById('dp-decision-badge');
    badge.textContent  = `${dec} — ${u.pendekezo||dec}`;
    badge.className    = `dec-badge ${decClass(dec)}`;

    // Reasoning
    const reasons = t.reasoning || [];
    document.getElementById('dp-reasons').innerHTML = reasons.length > 0
      ? reasons.map(r=>`<li><span class="arr">→</span>${r}</li>`).join('')
      : `<li><span class="arr">→</span>Score: ${score}/100 — ${t.business_health||'Moderate'}</li>`;

    // Anomalies
    const aWrap = document.getElementById('dp-anomalies-wrap');
    if(anomalies.length > 0){
      aWrap.style.display = 'block';
      document.getElementById('dp-anomalies').innerHTML = anomalies.map(a=>
        `<div style="display:flex;gap:8px;padding:8px;background:rgba(248,81,73,.05);border-radius:6px;margin-bottom:6px;font-size:12px">
          <span>${a.icon||'⚠️'}</span>
          <div><strong style="color:var(--amber)">${a.code}</strong><br><span style="color:var(--muted)">${a.message}</span></div>
        </div>`
      ).join('');
    } else {
      aWrap.style.display = 'none';
    }

  } catch(e){
    document.getElementById('dp-name').textContent = `Could not load analysis #${id}`;
  }
}

function makeDecision(decision){
  if(!currentAnalysis){ toast('No application selected','error'); return; }
  const notes = document.getElementById('dp-notes').value;
  const colors = {APPROVE:'var(--green)',REVIEW:'var(--amber)',DECLINE:'var(--red)'};
  toast(`Decision recorded: ${decision}${notes?' — "'+notes.slice(0,40)+'"':''}`, 'success');
  // In production: POST to /decisions endpoint
}

// ══════════════════════════════════════════════════════
//  NEW ANALYSIS
// ══════════════════════════════════════════════════════
let uploadedTxns = null;

function handleCSV(input){
  const file = input.files[0];
  if(!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    const lines = e.target.result.trim().split('\\n');
    const txns = [];
    const header = lines[0].toLowerCase();
    const hasHeader = header.includes('type') || header.includes('amount');
    for(let i = hasHeader?1:0; i<lines.length; i++){
      const parts = lines[i].split(',').map(p=>p.trim().replace(/"/g,''));
      if(parts.length < 3) continue;
      const cols = hasHeader ? header.split(',').map(c=>c.trim()) : null;
      const idx = cols ? {} : null;
      if(cols) cols.forEach((c,i)=>idx[c]=i);
      const type   = cols ? parts[idx['type']||0] : parts[0];
      const amount = parseFloat((cols ? parts[idx['amount']||1] : parts[1]).replace(/[^0-9.]/g,''));
      const date   = cols ? parts[idx['date']||2] : parts[2];
      const desc   = cols ? (parts[idx['description']||3]||'') : (parts[3]||'');
      if(!type || !amount || amount<=0) continue;
      const t = (type.toLowerCase().includes('credit')||type.toLowerCase().includes('mapato')) ? 'credit' : 'debit';
      txns.push({type:t, amount, date, description:desc});
    }
    if(txns.length > 0){
      uploadedTxns = txns;
      const uz = document.getElementById('upload-zone');
      uz.style.borderColor = 'var(--green)';
      uz.querySelector('.upload-title').textContent = `✓ ${file.name} — ${txns.length} transactions loaded`;
      toast(`${txns.length} transactions loaded from ${file.name}`);
    } else {
      toast('Could not parse CSV — check format','error');
    }
  };
  reader.readAsText(file);
}

// Drag & drop
const dz = document.getElementById('upload-zone');
dz.addEventListener('dragover', e=>{e.preventDefault();dz.classList.add('drag');});
dz.addEventListener('dragleave', ()=>dz.classList.remove('drag'));
dz.addEventListener('drop', e=>{
  e.preventDefault(); dz.classList.remove('drag');
  const file = e.dataTransfer.files[0];
  if(file) handleCSV({files:[file]});
});

function loadDemoData(type){
  demoMode = type;
  uploadedTxns = null;
  document.getElementById('new-sms').value = '';
  document.getElementById('new-biz-name').value = '';
  const names = {duka:'Duka la Mama Fatuma',msisitizo:'Hassan Spices Trade',mapambano:'Mgahawa wa Juma'};
  document.getElementById('new-biz-name').value = names[type];
  document.getElementById('new-sector').value = 'retail';
  toast(`Demo data loaded: ${names[type]}`);
}

async function runNewAnalysis(){
  const bizName = document.getElementById('new-biz-name').value || 'Biashara';
  const sector  = document.getElementById('new-sector').value;
  const region  = document.getElementById('new-region').value || 'Tanzania';
  const smsText = document.getElementById('new-sms').value.trim();

  const resultDiv = document.getElementById('new-result');
  const resultContent = document.getElementById('new-result-content');
  resultContent.innerHTML = `<div class="loader"><div class="spin"></div>Running AI analysis...</div>`;
  resultDiv.style.display = 'block';

  try{
    let body, result;

    if(demoMode){
      const r = await fetch(`${API}/analyze/demo`, {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({business_type:demoMode, sector})});
      result = await r.json();
      demoMode = null;
    } else if(uploadedTxns){
      const r = await fetch(`${API}/analyze`, {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({business_name:bizName, sector, region, transactions:uploadedTxns})});
      result = await r.json();
    } else if(smsText){
      const lines = smsText.split('\\n').filter(l=>l.trim());
      const r = await fetch(`${API}/analyze`, {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({business_name:bizName, sector, region, sms_messages:lines})});
      result = await r.json();
    } else {
      resultContent.innerHTML = `<div class="empty"><span class="empty-icon">⚠️</span><div class="empty-text">Please upload CSV, paste SMS, or click Demo</div></div>`;
      return;
    }

    if(result.error){
      resultContent.innerHTML = `<div class="empty"><span class="empty-icon">❌</span><div class="empty-text">${result.error}</div></div>`;
      return;
    }

    renderInlineResult(result, resultContent);
    toast(`Analysis complete — ${result.uamuzi_mkopo?.decision||'done'}`,'success');
    loadDashboard();
  } catch(e){
    resultContent.innerHTML = `<div class="empty"><span class="empty-icon">❌</span><div class="empty-text">Analysis failed — is the API running?</div><div class="empty-sub">${e.message}</div></div>`;
  }
}

function renderInlineResult(d, el){
  const f = d.fedha||{}, t = d.tathmini||{}, u = d.uamuzi_mkopo||{};
  const b = d.biashara||{}, anomalies = d.anomalies||[];
  const score = t.stability_score||0;
  const dec   = u.decision||'REVIEW';
  const scoreColor = score>=70?'var(--green)':score>=50?'var(--amber)':'var(--red)';
  const ml = d.ml_scoring||{};

  el.innerHTML = `
  <div style="background:var(--ink2);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:16px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
      <div>
        <div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:700;color:var(--white)">${b.jina||b.name||'—'}</div>
        <div style="font-size:12px;color:var(--muted);margin-top:3px">${b.total_transactions||0} transactions · ${b.months_analyzed||0} months analyzed${d.analysis_id?` · Saved as #${d.analysis_id}`:''}</div>
      </div>
      <span class="dec-badge ${decClass(dec)}" style="font-size:14px;padding:8px 18px">${dec} — ${u.pendekezo||dec}</span>
    </div>

    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px">
      ${[
        {l:'Revenue',v:'TZS '+fmtM(f.true_avg_monthly_revenue||f.avg_monthly_revenue_tzs)+'/mo',c:'var(--green)'},
        {l:'Net Flow',v:'TZS '+fmtM(f.avg_net_cash_flow_tzs)+'/mo',c:f.avg_net_cash_flow_tzs>=0?'var(--green)':'var(--red)'},
        {l:'AI Score',v:score+'/100',c:scoreColor},
        {l:'Max Loan',v:'TZS '+fmtM(u.max_loan_amount_tzs),c:'var(--gold)'},
      ].map(m=>`
        <div style="background:var(--ink3);border-radius:8px;padding:14px;border:1px solid var(--border)">
          <div style="font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-bottom:6px">${m.l}</div>
          <div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:700;color:${m.c}">${m.v}</div>
        </div>`).join('')}
    </div>

    ${ml.ml_credit_score ? `
    <div style="background:rgba(88,166,255,.06);border:1px solid rgba(88,166,255,.2);border-radius:8px;padding:14px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center">
      <div style="font-size:12px;color:var(--text)">🧠 ML Credit Score (${ml.model_source||'model'})</div>
      <div style="font-family:'Syne',sans-serif;font-size:20px;font-weight:700;color:var(--blue)">${ml.ml_credit_score}/100</div>
      <div style="font-size:11px;color:var(--muted)">Default probability: ${ml.default_probability}%</div>
    </div>` : ''}

    ${(t.reasoning||[]).length > 0 ? `
    <div style="background:var(--ink3);border-left:3px solid var(--gold);border-radius:0 8px 8px 0;padding:16px;margin-bottom:16px">
      <div style="font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:var(--gold);margin-bottom:10px">AI Reasoning</div>
      ${(t.reasoning||[]).map(r=>`<div style="font-size:12px;color:var(--text);padding:4px 0;display:flex;gap:8px"><span style="color:var(--gold)">→</span>${r}</div>`).join('')}
    </div>` : ''}

    ${anomalies.length > 0 ? `
    <div style="margin-bottom:16px">
      <div style="font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:var(--amber);margin-bottom:10px">⚠️ ${anomalies.length} Anomal${anomalies.length===1?'y':'ies'} Detected</div>
      ${anomalies.map(a=>`<div style="display:flex;gap:8px;padding:8px;background:rgba(248,81,73,.05);border-radius:6px;margin-bottom:6px;font-size:12px">
        <span>${a.icon||'⚠️'}</span><div><strong style="color:var(--amber)">[${a.severity}]</strong> ${a.message}</div>
      </div>`).join('')}
    </div>` : ''}

    <div style="display:flex;gap:10px;margin-top:16px">
      <button class="act-btn act-approve" onclick="toast('Approved! Saved to portfolio','success')">✓ Approve</button>
      <button class="act-btn act-review" onclick="toast('Flagged for review','success')">◎ Flag Review</button>
      <button class="act-btn act-decline" onclick="toast('Declined. Reason noted.','success')">✗ Decline</button>
    </div>
  </div>`;
}

// ══════════════════════════════════════════════════════
//  PORTFOLIO
// ══════════════════════════════════════════════════════
async function loadPortfolio(){
  try{
    const r = await fetch(`${API}/dashboard`);
    const d = await r.json();
    const sectors = d.sectors || d.sekta || [];
    const total   = d.total_analyses || 1;
    const el = document.getElementById('portfolio-charts');

    if(sectors.length === 0){
      el.innerHTML = `<div class="empty" style="grid-column:1/-1"><span class="empty-icon">📊</span><div class="empty-text">No portfolio data yet</div><div class="empty-sub">Run some analyses to see portfolio breakdown</div></div>`;
      return;
    }

    const colors = ['var(--gold)','var(--green)','var(--blue)','var(--purple)','var(--amber)','var(--red)'];
    const maxN = Math.max(...sectors.map(s=>s.n||s.count||0));

    el.innerHTML = `
    <div class="chart-card">
      <div class="chart-title">Sector Distribution</div>
      <div class="bar-chart" style="height:120px">
        ${sectors.slice(0,6).map((s,i)=>{
          const n = s.n||s.count||0;
          const h = Math.round((n/maxN)*110);
          return `<div class="bar-wrap">
            <div class="bar-val">${n}</div>
            <div class="bar" style="height:${h}px;background:${colors[i%colors.length]}"></div>
            <div class="bar-lbl">${(s.sector||'').slice(0,6)}</div>
          </div>`;
        }).join('')}
      </div>
    </div>

    <div class="chart-card">
      <div class="chart-title">Decision Breakdown</div>
      <div class="donut-wrap">
        <svg width="100" height="100" viewBox="0 0 100 100" style="flex-shrink:0">
          <circle cx="50" cy="50" r="35" fill="none" stroke="var(--ink3)" stroke-width="16"/>
          <circle cx="50" cy="50" r="35" fill="none" stroke="var(--green)" stroke-width="16"
            stroke-dasharray="${220*((d.approved||0)/total)} 220"
            stroke-dashoffset="55" transform="rotate(-90 50 50)"/>
          <circle cx="50" cy="50" r="35" fill="none" stroke="var(--amber)" stroke-width="16"
            stroke-dasharray="${220*((d.review||0)/total)} 220"
            stroke-dashoffset="${55 - 220*((d.approved||0)/total)}" transform="rotate(-90 50 50)"/>
          <text x="50" y="46" text-anchor="middle" fill="var(--white)" font-size="14" font-weight="bold" font-family="Syne">${d.approve_rate_pct||0}%</text>
          <text x="50" y="58" text-anchor="middle" fill="var(--muted)" font-size="8">approved</text>
        </svg>
        <div class="donut-legend">
          <div class="leg-row"><div class="leg-dot" style="background:var(--green)"></div>Approved: ${d.approved||0}</div>
          <div class="leg-row"><div class="leg-dot" style="background:var(--amber)"></div>Review: ${d.review||0}</div>
          <div class="leg-row"><div class="leg-dot" style="background:var(--red)"></div>Declined: ${d.declined||0}</div>
          <div class="leg-row"><div class="leg-dot" style="background:var(--muted)"></div>Total: ${total}</div>
        </div>
      </div>
    </div>`;
  } catch(e){
    document.getElementById('portfolio-charts').innerHTML =
      `<div class="empty" style="grid-column:1/-1"><span class="empty-icon">⚠️</span><div class="empty-text">Could not load portfolio</div></div>`;
  }
}

// ══════════════════════════════════════════════════════
//  ECOSYSTEM
// ══════════════════════════════════════════════════════
async function loadEcosystem(){
  const el = document.getElementById('eco-content');
  try{
    const r = await fetch(`${API}/ecosystem`);
    const d = await r.json();
    const events = d.active_events || [];

    if(events.length === 0){
      el.innerHTML = `
      <div style="background:var(--ink2);border:1px solid rgba(63,185,80,.2);border-radius:12px;padding:32px;text-align:center">
        <div style="font-size:40px;margin-bottom:12px">🟢</div>
        <div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:700;color:var(--green);margin-bottom:8px">Ecosystem Clear</div>
        <div style="font-size:13px;color:var(--muted)">Hakuna matukio ya mfumo yanayoonekana / No system-wide events detected</div>
        <div style="font-size:11px;color:var(--muted);margin-top:12px">Layer 3 Analysis — 40% threshold monitoring active</div>
      </div>`;
    } else {
      el.innerHTML = `
      <div style="margin-bottom:16px">
        <div style="font-size:14px;font-weight:600;color:var(--amber);margin-bottom:12px">⚠️ ${events.length} Active Event${events.length>1?'s':''}</div>
        ${events.map(ev=>`
        <div style="background:var(--ink2);border:1px solid rgba(248,81,73,.25);border-radius:10px;padding:20px;margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px">
            <div style="font-family:'Syne',sans-serif;font-size:15px;font-weight:600;color:var(--white)">${ev.title_en||ev.event_type}</div>
            <span style="font-size:10px;font-weight:700;padding:4px 10px;background:rgba(248,81,73,.1);color:var(--red);border-radius:4px">${ev.severity}</span>
          </div>
          <div style="font-size:13px;color:var(--text);margin-bottom:10px">${ev.affected_pct||0}% of analyzed businesses affected</div>
          <div style="font-size:12px;color:var(--amber)">→ ${ev.recommendation||''}</div>
        </div>`).join('')}
      </div>`;
    }
  } catch(e){
    el.innerHTML = `<div class="empty"><span class="empty-icon">⚠️</span><div class="empty-text">Could not load ecosystem data</div></div>`;
  }
}

// ══════════════════════════════════════════════════════
//  SETTINGS
// ══════════════════════════════════════════════════════
async function loadSettings(){
  document.getElementById('api-url-input').value = API;
  try{
    const r = await fetch(`${API}/health`);
    const d = await r.json();
    document.getElementById('sys-status').innerHTML = `
      <div style="display:flex;flex-direction:column;gap:8px">
        <div style="display:flex;gap:8px;align-items:center"><span style="color:var(--green)">✓</span> Engine: ${d.engine?'Active':'Inactive'}</div>
        <div style="display:flex;gap:8px;align-items:center"><span style="color:var(--green)">✓</span> Database: ${d.database?'Connected':'Disconnected'}</div>
        <div style="display:flex;gap:8px;align-items:center"><span style="color:var(--${d.ml_ready?'green':'amber')}">✓</span> ML Model: ${d.ml_ready?'Ready':'Rule-based mode'}</div>
        <div style="display:flex;gap:8px;align-items:center"><span style="color:var(--muted)">ℹ</span> Total analyses: ${d.total_analyses||0}</div>
      </div>`;
  } catch(e){
    document.getElementById('sys-status').innerHTML = `<span style="color:var(--red)">✗ Cannot reach API at ${API}</span>`;
  }
}

function saveSettings(){
  API = document.getElementById('api-url-input').value.trim();
  localStorage.setItem('akili_api', API);
  checkAPI();
  toast('Settings saved');
  loadSettings();
}

function refreshAll(){
  checkAPI();
  const active = document.querySelector('.page.active');
  if(active){
    const id = active.id.replace('page-','');
    if(id==='dashboard') loadDashboard();
    if(id==='applications') loadApplications();
    if(id==='portfolio') loadPortfolio();
    if(id==='ecosystem') loadEcosystem();
  }
  toast('Refreshed');
}

// ══════════════════════════════════════════════════════
//  INIT
// ══════════════════════════════════════════════════════
checkAPI();
loadDashboard();
setInterval(checkAPI, 30000);
</script>
</body>
</html>
"""
    resp = make_response(html)
    resp.headers['Content-Type'] = 'text/html'
    return resp

@app.route("/dashboard-ui", methods=["GET"])
def dashboard_ui():
    from flask import send_file
    import os
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "akili_dashboard.html")
    if os.path.exists(html_path):
        return send_file(html_path)
    return jsonify({"error": "Dashboard file not found"}), 404

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error":"404 — Endpoint haipatikani",
        "vituo":["GET /","GET /health","POST /analyze",
                 "GET /history","GET /sector/<n>",
                 "GET /ecosystem","GET /dashboard","GET /ml/info"]}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error":f"500 — {str(e)}"}), 500


# ══════════════════════════════════════════════════════════════
#  START
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    debug = ENV != "production"
    print(f"""
  ╔════════════════════════════════════════════════════════╗
  ║                                                        ║
  ║      🌍  AKILI NI MALI — Production API  🌍           ║
  ║                                                        ║
  ║   Engine:   {'✅ Ready' if ENGINE_OK else '❌ Failed'}                              ║
  ║   Database: {'✅ Ready' if DB_OK    else '❌ Failed'}                              ║
  ║   ML Model: {'✅ Ready' if ML_OK    else '⚠️  Rule-based'}                         ║
  ║                                                        ║
  ║   URL: http://localhost:{PORT}                          ║
  ║   Env: {ENV}                                     ║
  ║                                                        ║
  ╚════════════════════════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=PORT, debug=debug, use_reloader=False)
