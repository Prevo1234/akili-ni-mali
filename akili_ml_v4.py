"""
╔══════════════════════════════════════════════════════════════════╗
║     AKILI NI MALI — ML Credit Scoring v4.0                       ║
║     Phase 4: Synthetic Data + scikit-learn + XAI                 ║
║                                                                  ║
║  Pipeline:                                                       ║
║   1. TanzaniaDataGenerator  → 10,000 realistic businesses        ║
║   2. FeatureEngineer        → Extract ML features                ║
║   3. CreditScoringModel     → Train RandomForest + LogReg        ║
║   4. ModelExplainer         → XAI for loan officers              ║
║   5. CreditIntelligence     → Final scoring system               ║
╚══════════════════════════════════════════════════════════════════╝
"""

import random
import math
import json
from datetime import datetime
from collections import defaultdict

# ── Try importing ML libraries ────────────────────────────────
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import classification_report, accuracy_score
    import numpy as np
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("⚠️  scikit-learn haipo — tumia: pip install scikit-learn numpy")
    print("   Mfumo utafanya kazi na rule-based scoring tu")


# ════════════════════════════════════════════════════════════════
#  MODULE 1: TANZANIA DATA GENERATOR
#  Tengeneza biashara 10,000 za kweli kimuundo
# ════════════════════════════════════════════════════════════════

class TanzaniaDataGenerator:
    """
    Tengeneza data bandia ya biashara za Tanzania.
    Generate realistic synthetic Tanzania business data.

    Inajumuisha / Includes:
    - Biashara za aina tofauti (retail, food, agri, etc.)
    - Mapato ya Tanzania halisi (TZS 200K - 5M/month)
    - Misimu ya Tanzania (kilimo, likizo, n.k.)
    - Matukio ya kawaida (loan misclassification, agent float)
    - Matokeo ya mkopo (repaid / default) kwa supervised ML
    """

    # Tanzania-specific business profiles
    BUSINESS_PROFILES = {
        "retail_small": {
            "label": "Duka la rejareja ndogo / Small retail shop",
            "revenue_range": (200_000, 1_500_000),
            "expense_ratio": (0.55, 0.80),
            "tx_per_month": (40, 150),
            "stability":    (0.55, 0.90),
            "seasonal_drop": 0.20,
            "default_rate": 0.18,
        },
        "retail_medium": {
            "label": "Duka la kati / Medium retail shop",
            "revenue_range": (1_500_000, 6_000_000),
            "expense_ratio": (0.50, 0.72),
            "tx_per_month": (100, 400),
            "stability":    (0.60, 0.92),
            "seasonal_drop": 0.15,
            "default_rate": 0.12,
        },
        "food_vendor": {
            "label": "Mgahawa / Food vendor",
            "revenue_range": (150_000, 800_000),
            "expense_ratio": (0.60, 0.85),
            "tx_per_month": (80, 300),
            "stability":    (0.45, 0.80),
            "seasonal_drop": 0.10,
            "default_rate": 0.25,
        },
        "agri_trader": {
            "label": "Mfanyabiashara wa kilimo / Agricultural trader",
            "revenue_range": (300_000, 4_000_000),
            "expense_ratio": (0.55, 0.78),
            "tx_per_month": (20, 80),
            "stability":    (0.30, 0.70),   # High seasonal variation
            "seasonal_drop": 0.45,           # Big seasonal drops
            "default_rate": 0.22,
        },
        "transport": {
            "label": "Usafiri / Transport business",
            "revenue_range": (400_000, 2_500_000),
            "expense_ratio": (0.58, 0.82),
            "tx_per_month": (30, 120),
            "stability":    (0.50, 0.85),
            "seasonal_drop": 0.12,
            "default_rate": 0.16,
        },
        "wholesale": {
            "label": "Biashara kubwa / Wholesale",
            "revenue_range": (2_000_000, 15_000_000),
            "expense_ratio": (0.65, 0.85),
            "tx_per_month": (15, 60),
            "stability":    (0.55, 0.88),
            "seasonal_drop": 0.20,
            "default_rate": 0.10,
        },
        "services": {
            "label": "Huduma / Services (salon, fundi, n.k.)",
            "revenue_range": (100_000, 700_000),
            "expense_ratio": (0.40, 0.70),
            "tx_per_month": (30, 100),
            "stability":    (0.50, 0.82),
            "seasonal_drop": 0.08,
            "default_rate": 0.20,
        },
    }

    # Tanzania regions
    REGIONS = [
        "Dar es Salaam", "Mwanza", "Arusha", "Dodoma",
        "Mbeya", "Morogoro", "Tanga", "Zanzibar",
        "Kigoma", "Tabora", "Shinyanga", "Mara"
    ]

    def __init__(self, seed=42):
        random.seed(seed)
        if ML_AVAILABLE:
            import numpy as np
            np.random.seed(seed)

    def generate_business(self, biz_type=None):
        """
        Tengeneza biashara moja ya Tanzania.
        Generate one Tanzania business profile.
        """
        if biz_type is None:
            # Weighted selection — retail most common
            biz_type = random.choices(
                list(self.BUSINESS_PROFILES.keys()),
                weights=[35, 20, 15, 10, 8, 7, 5]
            )[0]

        profile = self.BUSINESS_PROFILES[biz_type]
        region  = random.choice(self.REGIONS)

        # Base revenue with Tanzania-realistic distribution
        rev_min, rev_max = profile["revenue_range"]
        # Use log-normal for more realistic skew
        log_mean = math.log((rev_min + rev_max) / 2)
        log_std  = 0.4
        base_revenue = min(rev_max, max(rev_min,
            int(math.exp(random.gauss(log_mean, log_std)))
        ))
        base_revenue = round(base_revenue / 10000) * 10000

        # Expense ratio
        exp_ratio_min, exp_ratio_max = profile["expense_ratio"]
        expense_ratio = random.uniform(exp_ratio_min, exp_ratio_max)

        # Stability (coefficient of variation — lower = more stable)
        stab_min, stab_max = profile["stability"]
        stability = random.uniform(stab_min, stab_max)

        # Transaction frequency
        tx_min, tx_max = profile["tx_per_month"]
        tx_per_month = random.randint(tx_min, tx_max)

        # Customer diversity (unique customers / total transactions)
        customer_diversity = random.uniform(0.3, 0.95)

        # Monthly revenue with seasonal variation
        months = 3
        monthly_revenues = []
        for m in range(months):
            seasonal_factor = 1.0
            # Tanzania agricultural seasons affect many businesses
            if biz_type == "agri_trader":
                # Low in March-May (planting), high in July-Sept (harvest)
                seasonal_factor = random.uniform(
                    1 - profile["seasonal_drop"],
                    1 + profile["seasonal_drop"]
                )
            else:
                seasonal_factor = random.uniform(
                    1 - profile["seasonal_drop"] / 2,
                    1 + profile["seasonal_drop"] / 2
                )

            # Add noise based on stability
            noise = random.gauss(0, (1 - stability) * 0.3)
            month_rev = base_revenue * seasonal_factor * (1 + noise)
            month_rev = max(50_000, round(month_rev / 5000) * 5000)
            monthly_revenues.append(month_rev)

        avg_revenue  = sum(monthly_revenues) / len(monthly_revenues)
        avg_expenses = avg_revenue * expense_ratio
        avg_net      = avg_revenue - avg_expenses
        profit_margin = (avg_net / avg_revenue * 100) if avg_revenue > 0 else 0

        # Revenue trend
        if monthly_revenues[-1] > monthly_revenues[0] * 1.10:
            trend = "GROWING"
        elif monthly_revenues[-1] < monthly_revenues[0] * 0.90:
            trend = "DECLINING"
        else:
            trend = "STABLE"

        # Computed stability score (like our engine)
        if len(monthly_revenues) > 1:
            mean = sum(monthly_revenues) / len(monthly_revenues)
            variance = sum((r - mean)**2 for r in monthly_revenues) / len(monthly_revenues)
            cv = math.sqrt(variance) / mean if mean > 0 else 1
            stability_score = round(max(0, min(100, 100 * (1 - min(cv, 1.0)))))
        else:
            stability_score = 50

        # Loan outcome — supervised ML target
        # Based on realistic risk factors
        default_prob = profile["default_rate"]

        # Adjust based on computed features
        if stability_score < 45:         default_prob *= 1.8
        elif stability_score > 75:       default_prob *= 0.5

        if trend == "DECLINING":         default_prob *= 1.6
        elif trend == "GROWING":         default_prob *= 0.7

        if profit_margin < 10:           default_prob *= 1.5
        elif profit_margin > 30:         default_prob *= 0.7

        if customer_diversity < 0.3:     default_prob *= 1.4
        if tx_per_month < 20:            default_prob *= 1.3

        # Clamp probability
        default_prob = min(0.90, max(0.02, default_prob))
        loan_outcome = "default" if random.random() < default_prob else "repaid"

        # Some businesses have data quality issues
        has_loan_misclassification = random.random() < 0.12
        has_agent_float_issue      = random.random() < 0.08

        return {
            # Identifiers
            "biz_id":       f"SYN-{random.randint(100000,999999)}",
            "biz_type":     biz_type,
            "region":       region,
            "synthetic":    True,

            # Financial features (used for ML)
            "avg_monthly_revenue":    round(avg_revenue),
            "avg_monthly_expenses":   round(avg_expenses),
            "avg_net_cashflow":       round(avg_net),
            "profit_margin_pct":      round(profit_margin, 1),
            "stability_score":        stability_score,
            "tx_per_month":           tx_per_month,
            "customer_diversity":     round(customer_diversity, 3),
            "revenue_trend":          trend,
            "monthly_revenues":       [round(r) for r in monthly_revenues],
            "expense_ratio":          round(expense_ratio, 3),

            # Data quality flags
            "has_loan_misclassification": has_loan_misclassification,
            "has_agent_float_issue":      has_agent_float_issue,

            # ML target variable
            "loan_outcome":   loan_outcome,          # repaid / default
            "default_prob":   round(default_prob, 3),
        }

    def generate_dataset(self, n=10_000, verbose=True):
        """
        Tengeneza dataset kamili ya biashara N.
        Generate complete dataset of N businesses.
        """
        if verbose:
            print(f"\n  Kutengeneza data ya biashara {n:,}...")
            print(f"  Generating {n:,} Tanzania business profiles...")

        businesses = []
        for i in range(n):
            biz = self.generate_business()
            businesses.append(biz)
            if verbose and (i+1) % 2000 == 0:
                print(f"  ✓ {i+1:,}/{n:,} biashara zimetengenezwa")

        if verbose:
            # Stats
            repaid   = sum(1 for b in businesses if b["loan_outcome"] == "repaid")
            defaults = sum(1 for b in businesses if b["loan_outcome"] == "default")
            types    = defaultdict(int)
            for b in businesses:
                types[b["biz_type"]] += 1
            avg_rev = sum(b["avg_monthly_revenue"] for b in businesses) / n

            print(f"\n  Dataset Summary / Muhtasari wa Data:")
            print(f"  Total:          {n:,} businesses")
            print(f"  Repaid:         {repaid:,} ({repaid/n*100:.1f}%)")
            print(f"  Default:        {defaults:,} ({defaults/n*100:.1f}%)")
            print(f"  Avg Revenue:    TZS {avg_rev:,.0f}/month")
            print(f"  Business types: {dict(types)}")

        return businesses


# ════════════════════════════════════════════════════════════════
#  MODULE 2: FEATURE ENGINEER
#  Badilisha data ya biashara kuwa ML features
# ════════════════════════════════════════════════════════════════

class FeatureEngineer:
    """
    Badilisha data ya biashara kuwa features za ML.
    Transform business data into ML features.
    """

    FEATURE_NAMES = [
        "stability_score",          # 0-100
        "tx_per_month_norm",        # normalized
        "customer_diversity",       # 0-1
        "profit_margin_pct",        # %
        "expense_ratio",            # ratio
        "trend_growing",            # binary
        "trend_declining",          # binary
        "revenue_log",              # log-normalized
        "net_cashflow_ratio",       # net/revenue
        "data_quality_flag",        # 0 or 1
    ]

    def extract(self, business):
        """
        Toa features kutoka kwa biashara moja.
        Extract features from one business record.
        """
        rev  = business.get("avg_monthly_revenue", 0)
        net  = business.get("avg_net_cashflow", 0)
        trend = business.get("revenue_trend", "STABLE")

        features = [
            business.get("stability_score", 50) / 100.0,
            min(1.0, business.get("tx_per_month", 50) / 300.0),
            business.get("customer_diversity", 0.5),
            min(1.0, max(-0.5, business.get("profit_margin_pct", 20) / 100.0)),
            business.get("expense_ratio", 0.7),
            1.0 if trend == "GROWING"  else 0.0,
            1.0 if trend == "DECLINING" else 0.0,
            math.log(max(1, rev)) / math.log(10_000_000),
            net / rev if rev > 0 else 0.0,
            1.0 if (business.get("has_loan_misclassification") or
                    business.get("has_agent_float_issue")) else 0.0,
        ]
        return features

    def extract_batch(self, businesses):
        """Extract features kwa biashara nyingi."""
        return [self.extract(b) for b in businesses]

    def get_labels(self, businesses):
        """Pata labels kwa supervised learning."""
        return [1 if b["loan_outcome"] == "default" else 0
                for b in businesses]


# ════════════════════════════════════════════════════════════════
#  MODULE 3: CREDIT SCORING MODEL
#  Mafunzo ya ML model + tathmini
# ════════════════════════════════════════════════════════════════

class CreditScoringModel:
    """
    Mfumo wa ML wa tathmini ya mkopo.
    ML-based credit scoring system.
    """

    def __init__(self):
        self.fe        = FeatureEngineer()
        self.scaler    = None
        self.model_rf  = None
        self.model_gb  = None
        self.model_lr  = None
        self.best_model = None
        self.best_name  = None
        self.trained    = False
        self.metrics    = {}

    def train(self, businesses, verbose=True):
        """
        Funza models kwenye dataset.
        Train models on dataset.
        """
        if not ML_AVAILABLE:
            print("  ❌ scikit-learn haipo — install kwanza")
            return False

        import numpy as np
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import classification_report, accuracy_score

        if verbose:
            print(f"\n  Kufunza models kwenye biashara {len(businesses):,}...")
            print(f"  Training models on {len(businesses):,} businesses...")

        # Extract features
        X = np.array(self.fe.extract_batch(businesses))
        y = np.array(self.fe.get_labels(businesses))

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.20, random_state=42, stratify=y
        )

        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled  = self.scaler.transform(X_test)

        results = {}

        # ── Model 1: Random Forest ─────────────────────────
        if verbose: print("\n  [1/3] Random Forest...")
        self.model_rf = RandomForestClassifier(
            n_estimators=200, max_depth=8,
            min_samples_leaf=10, random_state=42, n_jobs=-1
        )
        self.model_rf.fit(X_train, y_train)
        rf_pred  = self.model_rf.predict(X_test)
        rf_score = accuracy_score(y_test, rf_pred)
        rf_cv    = cross_val_score(self.model_rf, X, y, cv=5).mean()
        results["RandomForest"] = {"accuracy": rf_score, "cv": rf_cv, "model": self.model_rf}
        if verbose:
            print(f"  ✓ Accuracy: {rf_score:.3f} | CV: {rf_cv:.3f}")

        # ── Model 2: Gradient Boosting ──────────────────────
        if verbose: print("  [2/3] Gradient Boosting...")
        self.model_gb = GradientBoostingClassifier(
            n_estimators=150, max_depth=4,
            learning_rate=0.1, random_state=42
        )
        self.model_gb.fit(X_train, y_train)
        gb_pred  = self.model_gb.predict(X_test)
        gb_score = accuracy_score(y_test, gb_pred)
        gb_cv    = cross_val_score(self.model_gb, X, y, cv=5).mean()
        results["GradientBoosting"] = {"accuracy": gb_score, "cv": gb_cv, "model": self.model_gb}
        if verbose:
            print(f"  ✓ Accuracy: {gb_score:.3f} | CV: {gb_cv:.3f}")

        # ── Model 3: Logistic Regression (interpretable) ────
        if verbose: print("  [3/3] Logistic Regression (Explainable)...")
        self.model_lr = LogisticRegression(
            max_iter=1000, random_state=42, C=0.5
        )
        self.model_lr.fit(X_train_scaled, y_train)
        lr_pred  = self.model_lr.predict(X_test_scaled)
        lr_score = accuracy_score(y_test, lr_pred)
        lr_cv    = cross_val_score(
            self.model_lr,
            self.scaler.transform(X), y, cv=5
        ).mean()
        results["LogisticRegression"] = {"accuracy": lr_score, "cv": lr_cv, "model": self.model_lr}
        if verbose:
            print(f"  ✓ Accuracy: {lr_score:.3f} | CV: {lr_cv:.3f}")

        # Pick best model (prefer RF for non-linear data)
        best_name = max(results, key=lambda k: results[k]["cv"])
        self.best_model = results[best_name]["model"]
        self.best_name  = best_name
        self.trained    = True

        # Feature importance from RF
        fi = self.model_rf.feature_importances_
        feature_importance = {
            name: round(float(imp), 4)
            for name, imp in zip(FeatureEngineer.FEATURE_NAMES, fi)
        }

        self.metrics = {
            "models":             {k: {"accuracy": round(v["accuracy"],3),
                                       "cv_score":  round(v["cv"],3)}
                                   for k,v in results.items()},
            "best_model":         best_name,
            "best_cv":            round(results[best_name]["cv"], 3),
            "feature_importance": dict(sorted(feature_importance.items(),
                                              key=lambda x: x[1], reverse=True)),
            "training_size":      len(X_train),
            "test_size":          len(X_test),
            "trained_at":         datetime.now().isoformat(),
        }

        if verbose:
            print(f"\n  ══ MODEL ILIYOCHAGULIWA / BEST MODEL: {best_name} ══")
            print(f"  CV Score: {results[best_name]['cv']:.3f}")
            print(f"\n  Feature Importance (kutoka Random Forest):")
            for feat, imp in list(feature_importance.items())[:5]:
                bar = "█" * int(imp * 40)
                print(f"  {feat:<30} {bar} {imp:.4f}")

        return True

    def predict_one(self, business):
        """
        Tabiri hatari ya mkopo kwa biashara moja.
        Predict credit risk for one business.
        """
        if not self.trained or not ML_AVAILABLE:
            return self._rule_based_predict(business)

        import numpy as np
        features = np.array(self.fe.extract(business)).reshape(1, -1)

        # Get probability of default
        if self.best_name == "LogisticRegression":
            features_scaled = self.scaler.transform(features)
            proba = self.best_model.predict_proba(features_scaled)[0]
        else:
            proba = self.best_model.predict_proba(features)[0]

        default_prob = proba[1]  # probability of default

        # Also get RF probability for comparison
        rf_proba = self.model_rf.predict_proba(features)[0][1]

        # Ensemble: average of RF and best model
        if self.best_name != "RandomForest":
            ensemble_prob = (default_prob + rf_proba) / 2
        else:
            ensemble_prob = default_prob

        return self._build_result(business, ensemble_prob)

    def _rule_based_predict(self, business):
        """
        Rule-based fallback kama ML haipatikani.
        Rule-based fallback when ML is unavailable.
        """
        score = business.get("stability_score", 50)
        trend = business.get("revenue_trend", "STABLE")
        margin = business.get("profit_margin_pct", 20)
        net = business.get("avg_net_cashflow", 0)

        # Simple rule-based default probability
        prob = 0.20
        if score < 45:    prob += 0.20
        elif score > 75:  prob -= 0.10
        if trend == "DECLINING": prob += 0.15
        elif trend == "GROWING": prob -= 0.08
        if margin < 10:   prob += 0.15
        if net < 0:       prob = 0.80

        return self._build_result(business, min(0.95, max(0.02, prob)))

    def _build_result(self, business, default_prob):
        """Build prediction result with XAI explanation."""
        credit_score = round(100 * (1 - default_prob))

        # Decision thresholds
        if credit_score >= 75:
            decision    = "APPROVE"
            decision_sw = "IDHINISHA"
            risk        = "LOW"
        elif credit_score >= 55:
            decision    = "REVIEW"
            decision_sw = "KAGUA"
            risk        = "MEDIUM"
        else:
            decision    = "DECLINE"
            decision_sw = "KATAA"
            risk        = "HIGH"

        # Override rules (always apply)
        net = business.get("avg_net_cashflow", 0)
        if net < 0 and decision == "APPROVE":
            decision = "REVIEW"
            decision_sw = "KAGUA"

        trend = business.get("revenue_trend", "STABLE")
        if trend == "DECLINING" and credit_score < 70 and decision == "APPROVE":
            decision = "REVIEW"
            decision_sw = "KAGUA"

        # XAI explanation
        explanation = self._explain(business, default_prob, credit_score)

        # Loan capacity
        avg_net = business.get("avg_net_cashflow", 0)
        cap_ratio = 0.30 if decision=="APPROVE" else 0.20 if decision=="REVIEW" else 0
        monthly_cap = max(0, avg_net * cap_ratio)

        return {
            "ml_credit_score":   credit_score,
            "default_probability": round(default_prob * 100, 1),
            "decision":          decision,
            "pendekezo":         decision_sw,
            "risk_level":        risk,
            "monthly_loan_capacity_tzs": round(monthly_cap),
            "max_loan_tzs":      round(monthly_cap * 6),
            "explanation":       explanation,
            "model_used":        self.best_name if self.trained else "rule-based",
        }

    def _explain(self, business, default_prob, credit_score):
        """
        Tengeneza maelezo kwa afisa wa mkopo.
        Generate explanation for loan officer.
        """
        reasons = []
        positives = []
        negatives = []

        score    = business.get("stability_score", 50)
        trend    = business.get("revenue_trend", "STABLE")
        margin   = business.get("profit_margin_pct", 20)
        tx       = business.get("tx_per_month", 50)
        div      = business.get("customer_diversity", 0.5)
        net      = business.get("avg_net_cashflow", 0)
        rev      = business.get("avg_monthly_revenue", 0)

        # Positive signals
        if score >= 70:
            positives.append(f"Mapato thabiti — alama {score}/100 / Stable income — score {score}/100")
        if trend == "GROWING":
            positives.append("Mapato yanaongezeka — biashara inakua / Revenue growing")
        if margin >= 25:
            positives.append(f"Margin nzuri — {margin:.0f}% / Healthy margin")
        if tx >= 100:
            positives.append(f"Miamala {tx}/mwezi — biashara inafanya kazi / {tx} txns/month")
        if div >= 0.6:
            positives.append("Wateja wengi tofauti — hatari ndogo / Diverse customer base")

        # Negative signals
        if score < 50:
            negatives.append(f"Mapato si ya kawaida — alama {score}/100 / Irregular income")
        if trend == "DECLINING":
            negatives.append("Mapato yanashuka — chunguza sababu / Revenue declining")
        if margin < 15:
            negatives.append(f"Margin nyembamba — {margin:.0f}% / Thin margins")
        if net < 0:
            negatives.append("Matumizi yanazidi mapato — hatari kubwa / Expenses exceed revenue")
        if div < 0.3:
            negatives.append("Wateja wachache — mkopo wa juu ni hatari / Concentrated customers")
        if business.get("has_loan_misclassification"):
            negatives.append("Tahadhari: Mikopo inaweza kuhesabiwa kama mapato / Loans may inflate revenue")

        return {
            "credit_score":     credit_score,
            "default_prob_pct": round(default_prob * 100, 1),
            "positives":        positives,
            "negatives":        negatives,
            "summary":          f"Alama {credit_score}/100 — Uwezekano wa kulipa {100-round(default_prob*100)}%",
        }


# ════════════════════════════════════════════════════════════════
#  MODULE 4: CREDIT INTELLIGENCE (Combined Engine)
#  Inachanganya Rule-based + ML + XAI
# ════════════════════════════════════════════════════════════════

class CreditIntelligence:
    """
    Mfumo kamili wa akili ya mkopo.
    Complete credit intelligence system.

    Inajumuisha:
    - Rule-based scoring (Phase 2 engine)
    - ML credit scoring (Phase 4)
    - XAI explanation
    - Confidence measure
    """

    def __init__(self, ml_model: CreditScoringModel = None):
        self.ml = ml_model

    def score(self, analysis_result: dict) -> dict:
        """
        Hesabu mkopo kwa kutumia analysis result kutoka engine v2.
        Score credit using analysis result from engine v2.
        """
        f = analysis_result.get("fedha", {})
        t = analysis_result.get("tathmini", {})
        u = analysis_result.get("uamuzi_mkopo", {})

        # Build business profile for ML
        biz_profile = {
            "avg_monthly_revenue":  f.get("true_avg_monthly_revenue", 0),
            "avg_monthly_expenses": f.get("avg_monthly_expenses_tzs", 0),
            "avg_net_cashflow":     f.get("avg_net_cash_flow_tzs", 0),
            "profit_margin_pct":    f.get("profit_margin_pct", 0),
            "stability_score":      t.get("stability_score", 50),
            "tx_per_month":         round(analysis_result.get("biashara",{}).get(
                                    "total_transactions", 100) /
                                    max(1, analysis_result.get("biashara",{}).get(
                                    "months_analyzed", 3))),
            "customer_diversity":   0.6,  # default if not computed
            "revenue_trend":        t.get("trend_direction", t.get("revenue_trend","STABLE")),
            "expense_ratio":        (f.get("avg_monthly_expenses_tzs",0) /
                                     max(1, f.get("true_avg_monthly_revenue",1))),
            "has_loan_misclassification": any(
                a.get("code") == "LOAN_INFLATION"
                for a in analysis_result.get("anomalies", [])
            ),
            "has_agent_float_issue": any(
                a.get("code") == "AGENT_FLOAT_DETECTED"
                for a in analysis_result.get("anomalies", [])
            ),
        }

        # Get ML or rule-based prediction
        if self.ml and self.ml.trained:
            ml_result = self.ml.predict_one(biz_profile)
            source = "ml"
        else:
            ml_result = self.ml._rule_based_predict(biz_profile) if self.ml else \
                        CreditScoringModel()._rule_based_predict(biz_profile)
            source = "rule-based"

        # Combine with existing rule-based decision
        rule_decision = u.get("decision", "REVIEW")
        ml_decision   = ml_result["decision"]

        # If both agree → high confidence
        # If they disagree → use more conservative one
        if rule_decision == ml_decision:
            final_decision = rule_decision
            confidence     = "HIGH"
        else:
            # Conservative: pick worse outcome
            rank = {"APPROVE": 3, "REVIEW": 2, "DECLINE": 1}
            final_decision = min([rule_decision, ml_decision],
                                  key=lambda d: rank[d])
            confidence = "MEDIUM"

        # Build enriched result
        return {
            "ml_credit_score":        ml_result["ml_credit_score"],
            "default_probability_pct": ml_result["default_probability"],
            "rule_based_decision":    rule_decision,
            "ml_decision":            ml_decision,
            "final_decision":         final_decision,
            "final_pendekezo":        {"APPROVE":"IDHINISHA","REVIEW":"KAGUA","DECLINE":"KATAA"}[final_decision],
            "confidence":             confidence,
            "monthly_loan_capacity_tzs": ml_result["monthly_loan_capacity_tzs"],
            "max_loan_tzs":           ml_result["max_loan_tzs"],
            "explanation":            ml_result["explanation"],
            "model_source":           source,
            "agreement":              rule_decision == ml_decision,
        }


# ════════════════════════════════════════════════════════════════
#  QUICK TEST
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*62)
    print("  AKILI NI MALI v4.0 — ML CREDIT SCORING TEST")
    print("="*62)

    # Step 1: Generate data
    gen = TanzaniaDataGenerator(seed=42)
    dataset = gen.generate_dataset(n=5000, verbose=True)

    # Step 2: Train model
    model = CreditScoringModel()

    if ML_AVAILABLE:
        model.train(dataset, verbose=True)

        print(f"\n  ══ MODEL METRICS ══════════════════════════════")
        for name, m in model.metrics["models"].items():
            bar = "█" * int(m["cv_score"] * 30)
            print(f"  {name:<22} [{bar:<30}] {m['cv_score']:.3f}")
        print(f"\n  Best: {model.metrics['best_model']} — CV: {model.metrics['best_cv']}")
    else:
        print("\n  ⚠️  scikit-learn haipo — rule-based mode")
        print("  Install: pip install scikit-learn numpy")

    # Step 3: Test predictions
    print(f"\n  ══ MAJARIBIO YA UTABIRI / PREDICTION TESTS ═══")

    test_cases = [
        {"name": "Duka thabiti / Stable shop",
         "avg_monthly_revenue":1200000,"avg_monthly_expenses":750000,
         "avg_net_cashflow":450000,"profit_margin_pct":37.5,
         "stability_score":82,"tx_per_month":120,"customer_diversity":0.75,
         "revenue_trend":"STABLE","expense_ratio":0.625,
         "has_loan_misclassification":False,"has_agent_float_issue":False},
        {"name": "Mapambano / Struggling",
         "avg_monthly_revenue":400000,"avg_monthly_expenses":420000,
         "avg_net_cashflow":-20000,"profit_margin_pct":-5,
         "stability_score":38,"tx_per_month":25,"customer_diversity":0.30,
         "revenue_trend":"DECLINING","expense_ratio":1.05,
         "has_loan_misclassification":True,"has_agent_float_issue":False},
        {"name": "Inakua / Growing business",
         "avg_monthly_revenue":2500000,"avg_monthly_expenses":1600000,
         "avg_net_cashflow":900000,"profit_margin_pct":36,
         "stability_score":74,"tx_per_month":200,"customer_diversity":0.82,
         "revenue_trend":"GROWING","expense_ratio":0.64,
         "has_loan_misclassification":False,"has_agent_float_issue":False},
    ]

    for tc in test_cases:
        name = tc.pop("name")
        result = model.predict_one(tc)
        exp = result["explanation"]
        print(f"\n  📊 {name}")
        print(f"  ML Score:   {result['ml_credit_score']}/100")
        print(f"  Default %:  {result['default_probability']}%")
        print(f"  Decision:   {result['decision']} — {result['pendekezo']}")
        print(f"  Max Loan:   TZS {result['max_loan_tzs']:,}")
        if exp["positives"]:
            print(f"  ✅ {exp['positives'][0]}")
        if exp["negatives"]:
            print(f"  ⚠️  {exp['negatives'][0]}")

    print(f"\n  ✅ Phase 4 ML Engine — imefanya kazi!")
    if not ML_AVAILABLE:
        print(f"  💡 Kwa ML kamili: pip install scikit-learn numpy")
    print("="*62 + "\n")
