"""
╔══════════════════════════════════════════════════════════════════╗
║     AKILI NI MALI — Database Layer v3.0                          ║
║     Phase 3: Persistent Storage + 3-Context Intelligence         ║
║                                                                  ║
║  Three Analysis Contexts:                                        ║
║   Layer 1 → Business own history                                 ║
║   Layer 2 → Sector benchmark (min 20 businesses)                 ║
║   Layer 3 → Ecosystem anomaly detection (40% rule)               ║
║                                                                  ║
║  Tables:                                                         ║
║   businesses     → registered businesses                         ║
║   analyses       → saved analysis results                        ║
║   sector_stats   → pre-computed sector benchmarks                ║
║   ecosystem_log  → system-wide event detection                   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sqlite3
import json
import math
from datetime import datetime, timedelta
from collections import defaultdict
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "akili_data.db")


# ════════════════════════════════════════════════════════════════
#  DATABASE MANAGER
# ════════════════════════════════════════════════════════════════

class DatabaseManager:
    """
    Simamia database yote ya Akili ni Mali.
    Manage the complete Akili ni Mali database.
    """

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        """Tengeneza meza zote / Create all tables."""
        with self.connect() as conn:
            conn.executescript("""

            -- ── BIASHARA / BUSINESSES ──────────────────────────
            CREATE TABLE IF NOT EXISTS businesses (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                jina            TEXT NOT NULL,
                name            TEXT NOT NULL,
                sekta           TEXT DEFAULT 'general',
                sector          TEXT DEFAULT 'general',
                eneo            TEXT DEFAULT 'Tanzania',
                region          TEXT DEFAULT 'Tanzania',
                tarehe_usajili  TEXT DEFAULT (datetime('now')),
                created_at      TEXT DEFAULT (datetime('now')),
                metadata        TEXT DEFAULT '{}'
            );

            -- ── UCHAMBUZI / ANALYSES ───────────────────────────
            CREATE TABLE IF NOT EXISTS analyses (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id         INTEGER REFERENCES businesses(id),
                business_name       TEXT NOT NULL,
                sector              TEXT DEFAULT 'general',
                region              TEXT DEFAULT 'Tanzania',
                tarehe              TEXT DEFAULT (datetime('now')),
                analyzed_at         TEXT DEFAULT (datetime('now')),

                -- Layer 1: Business own metrics
                true_avg_revenue    REAL DEFAULT 0,
                avg_expenses        REAL DEFAULT 0,
                avg_net_cashflow    REAL DEFAULT 0,
                profit_margin_pct   REAL DEFAULT 0,
                stability_score     INTEGER DEFAULT 0,
                total_transactions  INTEGER DEFAULT 0,
                months_analyzed     INTEGER DEFAULT 0,
                revenue_trend       TEXT DEFAULT 'STABLE',
                business_health     TEXT DEFAULT 'MODERATE',

                -- Decision
                decision            TEXT DEFAULT 'REVIEW',
                max_loan_tzs        REAL DEFAULT 0,
                confidence          TEXT DEFAULT 'MEDIUM',
                overrides_applied   TEXT DEFAULT '[]',

                -- Anomalies detected
                anomaly_count       INTEGER DEFAULT 0,
                anomaly_codes       TEXT DEFAULT '[]',
                has_critical        INTEGER DEFAULT 0,

                -- Full result JSON
                full_result         TEXT NOT NULL,

                -- Layer 2 context (computed later)
                sector_percentile   REAL DEFAULT NULL,
                sector_comparison   TEXT DEFAULT NULL,

                -- Layer 3 context (computed later)
                ecosystem_flags     TEXT DEFAULT '[]'
            );

            CREATE INDEX IF NOT EXISTS idx_analyses_sector
                ON analyses(sector, analyzed_at);
            CREATE INDEX IF NOT EXISTS idx_analyses_business
                ON analyses(business_id, analyzed_at);
            CREATE INDEX IF NOT EXISTS idx_analyses_date
                ON analyses(analyzed_at);

            -- ── SEKTA STATS / SECTOR BENCHMARKS ───────────────
            CREATE TABLE IF NOT EXISTS sector_stats (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                sector          TEXT NOT NULL,
                region          TEXT DEFAULT 'Tanzania',
                computed_at     TEXT DEFAULT (datetime('now')),

                -- Sample size
                business_count  INTEGER DEFAULT 0,
                confidence_tier TEXT DEFAULT 'insufficient',

                -- Median metrics (robust to outliers)
                median_revenue      REAL DEFAULT 0,
                median_expenses     REAL DEFAULT 0,
                median_margin_pct   REAL DEFAULT 0,
                median_stability    REAL DEFAULT 0,
                median_net_cashflow REAL DEFAULT 0,

                -- Distribution
                p25_revenue     REAL DEFAULT 0,
                p75_revenue     REAL DEFAULT 0,
                p25_margin      REAL DEFAULT 0,
                p75_margin      REAL DEFAULT 0,

                -- Approve rate
                approve_rate_pct REAL DEFAULT 0
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_sector_stats_unique
                ON sector_stats(sector, region);

            -- ── ECOSYSTEM LOG / SYSTEM-WIDE EVENTS ───────────
            CREATE TABLE IF NOT EXISTS ecosystem_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                detected_at     TEXT DEFAULT (datetime('now')),
                event_type      TEXT NOT NULL,
                severity        TEXT DEFAULT 'INFO',

                -- What triggered it
                affected_count  INTEGER DEFAULT 0,
                affected_pct    REAL DEFAULT 0,
                trigger_metric  TEXT NOT NULL,
                trigger_value   REAL DEFAULT 0,
                threshold_used  REAL DEFAULT 0.40,

                -- Time window
                window_start    TEXT,
                window_end      TEXT,

                -- Human readable
                title_sw        TEXT,
                title_en        TEXT,
                description_sw  TEXT,
                description_en  TEXT,
                recommendation  TEXT,

                -- Status
                is_active       INTEGER DEFAULT 1,
                resolved_at     TEXT DEFAULT NULL
            );

            -- ── HISTORY VIEW ──────────────────────────────────
            CREATE VIEW IF NOT EXISTS analysis_history AS
            SELECT
                a.id,
                a.business_name,
                a.sector,
                a.region,
                a.analyzed_at,
                a.true_avg_revenue,
                a.profit_margin_pct,
                a.stability_score,
                a.decision,
                a.max_loan_tzs,
                a.anomaly_count,
                a.has_critical,
                a.sector_percentile,
                a.confidence
            FROM analyses a
            ORDER BY a.analyzed_at DESC;

            """)


# ════════════════════════════════════════════════════════════════
#  LAYER 1: ANALYSIS STORAGE
#  Hifadhi na rejesha uchambuzi wa biashara moja
# ════════════════════════════════════════════════════════════════

class AnalysisStore:
    """
    Hifadhi uchambuzi wa biashara na uirudishe baadaye.
    Store and retrieve business analyses.
    """

    def __init__(self, db: DatabaseManager):
        self.db = db

    def save(self, result: dict, sector: str = "general",
             region: str = "Tanzania") -> int:
        """
        Hifadhi uchambuzi mpya — rudisha ID.
        Save a new analysis — return its ID.
        """
        b  = result.get("biashara", {})
        f  = result.get("fedha", {})
        t  = result.get("tathmini", {})
        u  = result.get("uamuzi_mkopo", {})
        an = result.get("anomalies", [])

        anomaly_codes = [a.get("code","") for a in an]
        has_critical  = any(a.get("severity") == "CRITICAL" for a in an)

        with self.db.connect() as conn:
            # Upsert business record
            conn.execute("""
                INSERT OR IGNORE INTO businesses
                    (jina, name, sekta, sector, eneo, region)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (b.get("jina",""), b.get("name",""),
                  sector, sector, region, region))

            cur = conn.execute(
                "SELECT id FROM businesses WHERE name=? ORDER BY id LIMIT 1",
                (b.get("name",""),)
            )
            row = cur.fetchone()
            biz_id = row["id"] if row else None

            # Insert analysis
            cur = conn.execute("""
                INSERT INTO analyses (
                    business_id, business_name, sector, region,
                    true_avg_revenue, avg_expenses, avg_net_cashflow,
                    profit_margin_pct, stability_score,
                    total_transactions, months_analyzed, revenue_trend,
                    business_health, decision, max_loan_tzs, confidence,
                    overrides_applied, anomaly_count, anomaly_codes,
                    has_critical, full_result
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                biz_id, b.get("name",""), sector, region,
                f.get("true_avg_monthly_revenue", 0),
                f.get("avg_monthly_expenses_tzs", 0),
                f.get("avg_net_cash_flow_tzs", 0),
                f.get("profit_margin_pct", 0),
                t.get("stability_score", 0),
                b.get("total_transactions", 0),
                b.get("months_analyzed", 0),
                t.get("revenue_trend", "STABLE"),
                t.get("business_health", "MODERATE"),
                u.get("decision", "REVIEW"),
                u.get("max_loan_amount_tzs", 0),
                u.get("confidence", "MEDIUM"),
                json.dumps(u.get("overrides_applied", [])),
                len(an),
                json.dumps(anomaly_codes),
                1 if has_critical else 0,
                json.dumps(result, ensure_ascii=False),
            ))
            return cur.lastrowid

    def get_by_id(self, analysis_id: int) -> dict | None:
        """Rudisha uchambuzi mmoja kwa ID."""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM analyses WHERE id=?", (analysis_id,)
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["full_result"] = json.loads(result["full_result"])
            return result

    def get_history(self, business_name: str = None,
                    sector: str = None, limit: int = 20) -> list:
        """
        Rejesha historia ya uchambuzi.
        Return analysis history with optional filters.
        """
        with self.db.connect() as conn:
            query = "SELECT * FROM analysis_history WHERE 1=1"
            params = []
            if business_name:
                query += " AND business_name LIKE ?"
                params.append(f"%{business_name}%")
            if sector:
                query += " AND sector=?"
                params.append(sector)
            query += f" ORDER BY analyzed_at DESC LIMIT {limit}"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_business_trend(self, business_name: str) -> dict:
        """
        Angalia mwelekeo wa biashara moja kwa wakati.
        Track a single business's performance over time.
        """
        with self.db.connect() as conn:
            rows = conn.execute("""
                SELECT analyzed_at, stability_score, true_avg_revenue,
                       profit_margin_pct, decision, anomaly_count
                FROM analyses
                WHERE business_name LIKE ?
                ORDER BY analyzed_at ASC
                LIMIT 12
            """, (f"%{business_name}%",)).fetchall()

            if not rows:
                return {"found": False, "message": "Biashara haijapatikana"}

            data = [dict(r) for r in rows]
            scores   = [r["stability_score"] for r in data]
            revenues = [r["true_avg_revenue"] for r in data]

            # Trend direction
            if len(scores) >= 2:
                score_trend = "IMPROVING" if scores[-1] > scores[0] else \
                              "DECLINING" if scores[-1] < scores[0] else "STABLE"
            else:
                score_trend = "INSUFFICIENT_DATA"

            return {
                "found":         True,
                "business_name": business_name,
                "analyses":      len(data),
                "score_trend":   score_trend,
                "latest_score":  scores[-1] if scores else 0,
                "first_score":   scores[0]  if scores else 0,
                "avg_revenue":   round(sum(revenues)/len(revenues)) if revenues else 0,
                "history":       data,
            }


# ════════════════════════════════════════════════════════════════
#  LAYER 2: SECTOR BENCHMARK ENGINE
#  Linganisha biashara na sekta yake
# ════════════════════════════════════════════════════════════════

class SectorBenchmarkEngine:
    """
    Hesabu na tumia vipimo vya sekta.
    Compute and apply sector benchmarks.

    Confidence tiers:
    < 20    → insufficient (hakuna comparison)
    20-49   → low
    50-99   → moderate
    100+    → high (reliable benchmark)
    """

    THRESHOLDS = {
        "insufficient": 20,
        "low":          50,
        "moderate":     100,
    }

    SECTOR_LABELS = {
        "retail":       "Maduka ya rejareja / Retail Shops",
        "food":         "Migahawa na chakula / Food & Restaurants",
        "agri":         "Kilimo na mazao / Agriculture & Produce",
        "transport":    "Usafiri na uwasiliano / Transport",
        "wholesale":    "Biashara kubwa / Wholesale Trade",
        "services":     "Huduma / Services",
        "general":      "Biashara ya jumla / General Business",
    }

    def __init__(self, db: DatabaseManager):
        self.db = db

    def compute_benchmarks(self, sector: str,
                           region: str = "Tanzania") -> dict:
        """
        Hesabu vipimo vya sekta kutoka kwa data iliyohifadhiwa.
        Compute sector benchmarks from stored analyses.
        """
        with self.db.connect() as conn:
            rows = conn.execute("""
                SELECT true_avg_revenue, avg_expenses, profit_margin_pct,
                       stability_score, avg_net_cashflow, decision
                FROM analyses
                WHERE sector=? AND region=?
                  AND has_critical=0
                ORDER BY analyzed_at DESC
                LIMIT 500
            """, (sector, region)).fetchall()

        count = len(rows)

        # Determine confidence tier
        if count < self.THRESHOLDS["insufficient"]:
            tier = "insufficient"
        elif count < self.THRESHOLDS["low"]:
            tier = "low"
        elif count < self.THRESHOLDS["moderate"]:
            tier = "moderate"
        else:
            tier = "high"

        if tier == "insufficient":
            return {
                "sector":      sector,
                "region":      region,
                "count":       count,
                "tier":        tier,
                "available":   False,
                "ujumbe":      f"Biashara {count} tu — zinahitajika angalau 20 / Only {count} businesses — minimum 20 required",
                "message":     f"Only {count} businesses in this sector. Need 20+ for comparison.",
            }

        revenues  = sorted([r["true_avg_revenue"]   for r in rows])
        margins   = sorted([r["profit_margin_pct"]   for r in rows])
        stabs     = sorted([r["stability_score"]     for r in rows])
        netflows  = sorted([r["avg_net_cashflow"]    for r in rows])
        expenses  = sorted([r["avg_expenses"]        for r in rows])
        approvals = sum(1 for r in rows if r["decision"] == "APPROVE")

        def median(lst):
            n = len(lst)
            if n == 0: return 0
            mid = n // 2
            return lst[mid] if n % 2 else (lst[mid-1] + lst[mid]) / 2

        def percentile(lst, p):
            if not lst: return 0
            idx = int(len(lst) * p / 100)
            return lst[min(idx, len(lst)-1)]

        bench = {
            "sector":               sector,
            "sector_label":         self.SECTOR_LABELS.get(sector, sector),
            "region":               region,
            "count":                count,
            "tier":                 tier,
            "available":            True,
            "median_revenue":       round(median(revenues)),
            "median_expenses":      round(median(expenses)),
            "median_margin_pct":    round(median(margins), 1),
            "median_stability":     round(median(stabs)),
            "median_net_cashflow":  round(median(netflows)),
            "p25_revenue":          round(percentile(revenues, 25)),
            "p75_revenue":          round(percentile(revenues, 75)),
            "p25_margin":           round(percentile(margins, 25)),
            "p75_margin":           round(percentile(margins, 75)),
            "approve_rate_pct":     round(approvals / count * 100, 1),
        }

        # Save to sector_stats table
        with self.db.connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sector_stats (
                    sector, region, computed_at, business_count,
                    confidence_tier, median_revenue, median_expenses,
                    median_margin_pct, median_stability, median_net_cashflow,
                    p25_revenue, p75_revenue, p25_margin, p75_margin,
                    approve_rate_pct
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                sector, region, datetime.now().isoformat(),
                count, tier,
                bench["median_revenue"], bench["median_expenses"],
                bench["median_margin_pct"], bench["median_stability"],
                bench["median_net_cashflow"],
                bench["p25_revenue"], bench["p75_revenue"],
                bench["p25_margin"], bench["p75_margin"],
                bench["approve_rate_pct"],
            ))

        return bench

    def compare_business(self, analysis_result: dict,
                         sector: str) -> dict:
        """
        Linganisha biashara na sekta yake.
        Compare a business against its sector.
        """
        bench = self.compute_benchmarks(sector)

        if not bench.get("available"):
            return {
                "available":    False,
                "tier":         bench.get("tier", "insufficient"),
                "ujumbe":       bench.get("ujumbe", ""),
                "message":      bench.get("message", ""),
                "count":        bench.get("count", 0),
            }

        f = analysis_result.get("fedha", {})
        t = analysis_result.get("tathmini", {})

        biz_revenue = f.get("true_avg_monthly_revenue", 0)
        biz_margin  = f.get("profit_margin_pct", 0)
        biz_score   = t.get("stability_score", 0)

        # Compute percentile position
        def percentile_rank(value, p25, median, p75):
            if value >= p75:   return 75 + (value - p75) / max(p75, 1) * 25
            if value >= median: return 50 + (value - median) / max(p75 - median, 1) * 25
            if value >= p25:   return 25 + (value - p25) / max(median - p25, 1) * 25
            return max(0, value / max(p25, 1) * 25)

        rev_pct = round(min(99, percentile_rank(
            biz_revenue, bench["p25_revenue"],
            bench["median_revenue"], bench["p75_revenue"]
        )))

        # Position labels
        def position_label(pct):
            if pct >= 75: return "juu ya wastani / above average"
            if pct >= 50: return "wastani / average"
            if pct >= 25: return "chini kidogo / slightly below average"
            return "chini ya wastani / below average"

        margin_vs = "juu / higher" if biz_margin > bench["median_margin_pct"] else "chini / lower"
        score_vs  = "bora / better" if biz_score  > bench["median_stability"]  else "chini / lower"

        insights = []
        if biz_revenue > bench["median_revenue"]:
            insights.append(f"Mapato ni juu ya wastani wa sekta (TZS {bench['median_revenue']:,}) / Revenue above sector median")
        else:
            insights.append(f"Mapato ni chini ya wastani wa sekta (TZS {bench['median_revenue']:,}) / Revenue below sector median")

        if abs(biz_margin - bench["median_margin_pct"]) > 20:
            insights.append(f"Margin ya {biz_margin}% ni tofauti kubwa na sekta ({bench['median_margin_pct']}%) / Margin significantly different from sector")

        if biz_score > bench["median_stability"] + 15:
            insights.append("Utulivu wa mapato ni mzuri zaidi ya sekta / Stability significantly above sector")

        return {
            "available":          True,
            "tier":               bench["tier"],
            "count":              bench["count"],
            "sector_label":       bench["sector_label"],
            "revenue_percentile": rev_pct,
            "revenue_position":   position_label(rev_pct),
            "margin_vs_sector":   margin_vs,
            "score_vs_sector":    score_vs,
            "sector_median_revenue":  bench["median_revenue"],
            "sector_median_margin":   bench["median_margin_pct"],
            "sector_median_stability": bench["median_stability"],
            "sector_approve_rate":    bench["approve_rate_pct"],
            "insights":           insights,
            "confidence_note":    {
                "low":      f"Imlinganishwa na biashara {bench['count']} — data chache / Compared with {bench['count']} businesses — low confidence",
                "moderate": f"Imlinganishwa na biashara {bench['count']} — imara / Compared with {bench['count']} businesses — moderate confidence",
                "high":     f"Imlinganishwa na biashara {bench['count']} — ya kuaminika / Compared with {bench['count']} businesses — reliable",
            }.get(bench["tier"], ""),
        }


# ════════════════════════════════════════════════════════════════
#  LAYER 3: ECOSYSTEM ANOMALY DETECTOR
#  Gundua matukio yanayoathiri biashara nyingi kwa wakati mmoja
# ════════════════════════════════════════════════════════════════

class EcosystemAnomalyDetector:
    """
    Gundua matukio ya mfumo mzima.
    Detect system-wide events affecting many businesses simultaneously.

    Rule: Kama 40%+ ya biashara zina tatizo moja ndani ya saa 48
    → Tukio la mfumo / If 40%+ of businesses show same anomaly
      within 48 hours → system-wide event
    """

    TRIGGER_THRESHOLD = 0.40   # 40% of businesses
    TIME_WINDOW_HOURS = 48     # 48-hour detection window

    EVENT_TYPES = {
        "REVENUE_DROP":      ("Kushuka kwa Mapato Mfumo Mzima", "System-wide Revenue Drop"),
        "HIGH_MARGIN":       ("Margin ya Juu kwa Wengi",        "Widespread High Margin Anomaly"),
        "NEGATIVE_CASHFLOW": ("Cashflow Hasi kwa Wengi",        "Widespread Negative Cashflow"),
        "TELECOM_OUTAGE":    ("Tatizo la Mtandao wa Simu",       "Telecom Network Disruption"),
        "SEASONAL_PATTERN":  ("Msimu wa Kawaida",               "Expected Seasonal Pattern"),
    }

    def __init__(self, db: DatabaseManager):
        self.db = db

    def scan(self, window_hours: int = None) -> list:
        """
        Changanua data ya hivi karibuni na utafute matukio.
        Scan recent data for ecosystem-wide events.
        """
        hours = window_hours or self.TIME_WINDOW_HOURS
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        events = []

        with self.db.connect() as conn:
            # Total recent analyses
            total = conn.execute(
                "SELECT COUNT(*) as n FROM analyses WHERE analyzed_at >= ?",
                (cutoff,)
            ).fetchone()["n"]

            if total < 5:
                return []  # Too few to detect patterns

            # Check 1: Revenue drop anomaly spread
            revenue_drops = conn.execute(
                """SELECT COUNT(*) as n FROM analyses
                   WHERE analyzed_at >= ?
                   AND anomaly_codes LIKE '%REVENUE_DROP%'""",
                (cutoff,)
            ).fetchone()["n"]

            if total > 0 and revenue_drops / total >= self.TRIGGER_THRESHOLD:
                events.append(self._create_event(
                    "REVENUE_DROP", revenue_drops, total,
                    revenue_drops/total, cutoff,
                    "Mapato yameshuka kwa biashara nyingi kwa wakati mmoja",
                    "Revenue dropped across many businesses simultaneously",
                    "Chunguza kama kuna tatizo la mtandao wa simu au sera mpya / Check for telecom disruption or policy change"
                ))

            # Check 2: High margin widespread
            high_margin = conn.execute(
                """SELECT COUNT(*) as n FROM analyses
                   WHERE analyzed_at >= ?
                   AND anomaly_codes LIKE '%HIGH_PROFIT_MARGIN%'""",
                (cutoff,)
            ).fetchone()["n"]

            if total > 0 and high_margin / total >= self.TRIGGER_THRESHOLD:
                events.append(self._create_event(
                    "HIGH_MARGIN", high_margin, total,
                    high_margin/total, cutoff,
                    "Margin ya juu inaonekana kwa biashara nyingi — uwezekano data haikamilika",
                    "High margin detected across many businesses — possible incomplete expense data",
                    "Kagua jinsi biashara zinavyopakia data — matumizi yanaweza kukosekana / Review data ingestion — expenses may be missing"
                ))

            # Check 3: Critical cashflow spread
            critical = conn.execute(
                """SELECT COUNT(*) as n FROM analyses
                   WHERE analyzed_at >= ?
                   AND has_critical=1""",
                (cutoff,)
            ).fetchone()["n"]

            if total > 0 and critical / total >= self.TRIGGER_THRESHOLD:
                events.append(self._create_event(
                    "NEGATIVE_CASHFLOW", critical, total,
                    critical/total, cutoff,
                    "Biashara nyingi zina cashflow hasi — inaweza kuwa msimu au tukio la nje",
                    "Many businesses show negative cashflow — may indicate seasonal shock",
                    "Linganisha na miezi ya nyuma — kagua kama ni msimu wa kawaida / Compare with previous periods — check for seasonal pattern"
                ))

        # Save new events to DB
        for event in events:
            self._save_event(event)

        return events

    def _create_event(self, event_type, affected, total, pct,
                      window_start, title_sw, title_en, recommendation):
        return {
            "event_type":     event_type,
            "severity":       "WARNING" if pct < 0.6 else "CRITICAL",
            "affected_count": affected,
            "total_analyzed": total,
            "affected_pct":   round(pct * 100, 1),
            "window_start":   window_start,
            "window_end":     datetime.now().isoformat(),
            "title_sw":       title_sw,
            "title_en":       title_en,
            "recommendation": recommendation,
            "detected_at":    datetime.now().isoformat(),
        }

    def _save_event(self, event: dict):
        with self.db.connect() as conn:
            # Don't duplicate active events
            existing = conn.execute(
                """SELECT id FROM ecosystem_log
                   WHERE event_type=? AND is_active=1
                   AND detected_at >= datetime('now', '-2 days')""",
                (event["event_type"],)
            ).fetchone()
            if existing:
                return
            conn.execute("""
                INSERT INTO ecosystem_log (
                    event_type, severity, affected_count, affected_pct,
                    trigger_metric, trigger_value, threshold_used,
                    window_start, window_end,
                    title_sw, title_en, description_sw, description_en,
                    recommendation
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                event["event_type"], event["severity"],
                event["affected_count"], event["affected_pct"],
                event["event_type"], event["affected_pct"],
                self.TRIGGER_THRESHOLD * 100,
                event["window_start"], event["window_end"],
                event["title_sw"], event["title_en"],
                event["title_sw"], event["title_en"],
                event["recommendation"],
            ))

    def get_active_events(self) -> list:
        """Rudisha matukio ya sasa / Return current active events."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM ecosystem_log WHERE is_active=1 ORDER BY detected_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]


# ════════════════════════════════════════════════════════════════
#  INTELLIGENCE CONTEXT ENGINE
#  Inachanganya layers 1, 2, na 3 pamoja
# ════════════════════════════════════════════════════════════════

class IntelligenceContextEngine:
    """
    Inachanganya layers zote tatu za uchambuzi.
    Combines all three analysis layers into one response.
    """

    def __init__(self, db: DatabaseManager):
        self.store   = AnalysisStore(db)
        self.sector  = SectorBenchmarkEngine(db)
        self.eco     = EcosystemAnomalyDetector(db)

    def analyze_with_context(self, result: dict,
                             sector: str = "general",
                             region: str = "Tanzania") -> dict:
        """
        Hifadhi uchambuzi na ongeza muktadha wa layers 2 na 3.
        Save analysis and enrich with Layer 2 + Layer 3 context.
        """
        # ── LAYER 1: Save the analysis ────────────────────────
        analysis_id = self.store.save(result, sector, region)

        # ── LAYER 2: Sector comparison ────────────────────────
        layer2 = self.sector.compare_business(result, sector)

        # ── LAYER 3: Ecosystem scan ───────────────────────────
        eco_events  = self.eco.scan()
        active_eco  = self.eco.get_active_events()

        # ── Update analysis with Layer 2 context ──────────────
        if layer2.get("available"):
            with self.store.db.connect() as conn:
                conn.execute(
                    """UPDATE analyses SET
                       sector_percentile=?, sector_comparison=?
                       WHERE id=?""",
                    (layer2.get("revenue_percentile"),
                     json.dumps(layer2),
                     analysis_id)
                )

        # ── Build enriched response ────────────────────────────
        enriched = result.copy()
        enriched["analysis_id"]   = analysis_id
        enriched["muktadha"]      = {   # context
            "layer1": {
                "title":      "Uchambuzi wa Biashara Yenyewe / Own Business Analysis",
                "saved_id":   analysis_id,
                "sector":     sector,
                "region":     region,
            },
            "layer2": {
                "title":      "Ulinganisho na Sekta / Sector Comparison",
                **layer2,
            },
            "layer3": {
                "title":        "Hali ya Mfumo Mzima / Ecosystem Status",
                "new_events":   eco_events,
                "active_events": active_eco,
                "ecosystem_clear": len(active_eco) == 0,
                "ujumbe":       "Hakuna matukio ya mfumo / No ecosystem events" if not active_eco
                                else f"Matukio {len(active_eco)} ya mfumo yanafanya kazi / {len(active_eco)} ecosystem event(s) active",
            }
        }

        return enriched

    def get_dashboard_stats(self) -> dict:
        """
        Takwimu za dashboard kwa afisa wa mkopo.
        Dashboard statistics for loan officers.
        """
        with self.store.db.connect() as conn:
            total = conn.execute("SELECT COUNT(*) as n FROM analyses").fetchone()["n"]
            today = conn.execute(
                "SELECT COUNT(*) as n FROM analyses WHERE date(analyzed_at)=date('now')"
            ).fetchone()["n"]
            approvals = conn.execute(
                "SELECT COUNT(*) as n FROM analyses WHERE decision='APPROVE'"
            ).fetchone()["n"]
            reviews = conn.execute(
                "SELECT COUNT(*) as n FROM analyses WHERE decision='REVIEW'"
            ).fetchone()["n"]
            declines = conn.execute(
                "SELECT COUNT(*) as n FROM analyses WHERE decision='DECLINE'"
            ).fetchone()["n"]
            sectors = conn.execute(
                "SELECT sector, COUNT(*) as n FROM analyses GROUP BY sector ORDER BY n DESC"
            ).fetchall()
            recent = conn.execute(
                """SELECT business_name, stability_score, decision, analyzed_at, sector
                   FROM analyses ORDER BY analyzed_at DESC LIMIT 10"""
            ).fetchall()

        return {
            "jumla_uchambuzi":    total,
            "total_analyses":     total,
            "leo":                today,
            "today":              today,
            "idhinishwa":         approvals,
            "approved":           approvals,
            "kagua":              reviews,
            "review":             reviews,
            "kataliwa":           declines,
            "declined":           declines,
            "approve_rate_pct":   round(approvals/total*100) if total>0 else 0,
            "sekta":              [dict(r) for r in sectors],
            "sectors":            [dict(r) for r in sectors],
            "hivi_karibuni":      [dict(r) for r in recent],
            "recent_analyses":    [dict(r) for r in recent],
            "ecosystem_events":   len(self.eco.get_active_events()),
        }


# ════════════════════════════════════════════════════════════════
#  QUICK TEST
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from akili_engine_v2 import FinancialProfileV2

    print("\n" + "="*62)
    print("  AKILI NI MALI v3.0 — DATABASE LAYER TEST")
    print("="*62)

    # Clean test DB
    test_db_path = "/tmp/akili_test.db"
    if os.path.exists(test_db_path): os.remove(test_db_path)

    db     = DatabaseManager(test_db_path)
    engine = FinancialProfileV2()
    ctx    = IntelligenceContextEngine(db)

    # Sample transactions
    def make_txns(base_rev, months=3):
        txns = []
        from datetime import datetime, timedelta
        base = datetime(2026, 1, 1)
        import random
        random.seed(42)
        for m in range(months):
            for d in range(25):
                amt = round(random.randint(
                    int(base_rev*0.6), int(base_rev*1.4)) / 500) * 500
                txns.append({
                    "type":"credit","amount":amt,
                    "date":(base+timedelta(days=m*30+d)).strftime("%Y-%m-%d"),
                    "description":"Malipo ya mteja",
                    "phone":f"071{random.randint(1000000,9999999)}"
                })
            txns.append({"type":"debit","amount":200000,
                "date":(base+timedelta(days=m*30)).strftime("%Y-%m-%d"),
                "description":"Kodi ya nyumba"})
            txns.append({"type":"debit","amount":50000,
                "date":(base+timedelta(days=m*30+15)).strftime("%Y-%m-%d"),
                "description":"LUKU umeme"})
            txns.append({"type":"debit","amount":int(base_rev*0.3),
                "date":(base+timedelta(days=m*30+7)).strftime("%Y-%m-%d"),
                "description":"Malipo ya wasambazaji"})
        return txns

    print("\n  [1/4] Saving 25 retail businesses to build sector benchmark...")
    import random
    random.seed(99)
    for i in range(25):
        rev = random.randint(300000, 800000)
        txns = make_txns(rev)
        result = engine.analyze(txns, f"Duka {i+1} — Dar es Salaam")
        ctx.store.save(result, sector="retail")

    print(f"  ✓ 25 retail analyses saved")

    print("\n  [2/4] Analyzing test business with 3-context intelligence...")
    test_txns = make_txns(550000)
    test_result = engine.analyze(test_txns, "Duka la Mama Grace - Arusha")
    enriched = ctx.analyze_with_context(test_result, sector="retail")

    m = enriched["muktadha"]
    f = enriched["fedha"]
    t = enriched["tathmini"]
    u = enriched["uamuzi_mkopo"]

    print(f"\n  ── LAYER 1: Own Business ──────────────────────────")
    print(f"  Analysis ID:  #{enriched['analysis_id']}")
    print(f"  Revenue:      TZS {f['true_avg_monthly_revenue']:,}/month")
    print(f"  Score:        {t['stability_score']}/100 — {t['business_health']}")
    print(f"  Decision:     {u['decision']} — {u['pendekezo']}")

    print(f"\n  ── LAYER 2: Sector Comparison ─────────────────────")
    l2 = m["layer2"]
    if l2.get("available"):
        print(f"  Sector:       {l2.get('sector_label','')}")
        print(f"  Businesses:   {l2['count']} analyzed ({l2['tier']} confidence)")
        print(f"  Revenue rank: {l2['revenue_percentile']}th percentile")
        print(f"  Position:     {l2['revenue_position']}")
        print(f"  Sector median revenue: TZS {l2['sector_median_revenue']:,}")
        print(f"  Sector approve rate:   {l2['sector_approve_rate']}%")
        for ins in l2.get("insights", []):
            print(f"  → {ins}")
    else:
        print(f"  {l2.get('message','')}")

    print(f"\n  ── LAYER 3: Ecosystem ─────────────────────────────")
    l3 = m["layer3"]
    print(f"  {l3['ujumbe']}")
    if l3["active_events"]:
        for ev in l3["active_events"]:
            print(f"  ⚠️  {ev['title_en']} ({ev['affected_pct']}% businesses)")

    print(f"\n  [3/4] Testing history retrieval...")
    history = ctx.store.get_history(limit=5)
    print(f"  ✓ {len(history)} recent analyses retrieved")

    print(f"\n  [4/4] Dashboard stats...")
    stats = ctx.get_dashboard_stats()
    print(f"  Total analyses:  {stats['total_analyses']}")
    print(f"  Approved:        {stats['approved']}")
    print(f"  Review:          {stats['review']}")
    print(f"  Declined:        {stats['declined']}")
    print(f"  Approve rate:    {stats['approve_rate_pct']}%")
    print(f"  Sectors:         {[s['sector'] for s in stats['sectors']]}")

    print(f"\n  ✅ Phase 3 Database Layer — imefanya kazi!")
    print("="*62 + "\n")
