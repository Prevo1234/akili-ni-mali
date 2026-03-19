import re, math, json
from datetime import datetime
from collections import defaultdict

class TransactionClassifier:
    INCOME_KEYWORDS = {
        "loan_received":   ["loan","mkopo","advance","borrow","m-shwari","mshwari","kcb mpesa","tala","branch","zenka","timiza","fulfiza"],
        "owner_deposit":   ["deposit","weka","owner","capital","inject","owner deposit"],
        "refund_reversal": ["reversal","reverse","refund","rudisha","cancelled","failed","returned"],
        "agent_float_in":  ["float","wakala","agent","cash in","cashin","topup","top up"],
    }
    EXPENSE_KEYWORDS = {
        "rent":               ["kodi","rent","landlord","pango","nyumba","house","office","ofisi"],
        "utilities":          ["tanesco","luku","umeme","electricity","maji","dawasco","water","internet","wifi","data bundle","airtel data","vodacom data","tigo data","ttcl","cable"],
        "salaries":           ["mishahara","mshahara","salary","salaries","wages","wafanyakazi","worker","staff","employee"],
        "transport":          ["bodaboda","boda","pikipiki","transport","usafiri","delivery","deliver","carrier","truck","lorry","gari","fare","nauli"],
        "market_fees":        ["soko","market","ada","fee","levy","ushuru","municipal","manispaa","stall","banda"],
        "agri_inputs":        ["mbegu","seed","mbolea","fertilizer","dawa ya mimea","pesticide","kilimo","pembejeo","farm","shamba"],
        "inventory_purchase": ["bidhaa","goods","stock","inventory","purchase","nunua","order","mali"],
        "loan_repayment":     ["loan repay","kulipa mkopo","repayment","installment","fulfiza","timiza","m-shwari","kcb mpesa","tala","branch","zenka"],
        "owner_withdrawal":   ["withdraw","kuchukua","personal","binafsi"],
        "agent_float_out":    ["float","wakala","agent","cash out","cashout"],
        "chama_savings":      ["chama","vicoba","rosca","savings group","mwanachama","contribution","mchango"],
        "airtime_data":       ["airtime","simu","recharge","topup"],
    }

    def classify(self, tx, all_txns=None):
        desc = (tx.get("description","") + " " + tx.get("raw","")).lower()
        amount = float(tx.get("amount",0))
        tx_type = tx.get("type","").lower()
        result = {"category":None,"confidence":0.0,"flags":[],"is_revenue":False}

        # Layer 1: Hard rules
        if any(w in desc for w in ["reversal","reverse","refund","rudisha","cancelled","failed transaction","returned"]):
            return {"category":"refund_reversal","confidence":1.0,"is_revenue":False,"flags":["reversal"]}
        if any(w in desc for w in ["luku","tanesco","dawasco"]):
            return {"category":"utilities","confidence":0.98,"is_revenue":False,"flags":[]}
        if any(w in desc for w in ["m-shwari","mshwari","kcb mpesa","tala loan","branch loan","zenka","timiza loan","fulfiza"]):
            cat = "loan_received" if tx_type=="credit" else "loan_repayment"
            flag = ["loan_not_revenue"] if tx_type=="credit" else []
            return {"category":cat,"confidence":0.97,"is_revenue":False,"flags":flag}
        if any(w in desc for w in ["vicoba","chama","rosca"]):
            return {"category":"chama_savings","confidence":0.95,"is_revenue":False,"flags":[]}

        # Layer 2: Pattern
        if tx_type=="credit" and amount>500000:
            freq = sum(1 for t in (all_txns or []) if abs(float(t.get("amount",0))-amount)<10000 and t.get("type")=="credit")
            if freq==1:
                return {"category":"loan_received","confidence":0.72,"is_revenue":False,"flags":["large_single_credit"]}

        if tx_type=="debit" and 50000<=amount<=2000000:
            similar = [t for t in (all_txns or []) if abs(float(t.get("amount",0))-amount)<5000 and t.get("type")=="debit"]
            if len(similar)>=2:
                return {"category":"rent","confidence":0.78,"is_revenue":False,"flags":[]}

        # Layer 3: Keywords
        kw_map = self.INCOME_KEYWORDS if tx_type=="credit" else self.EXPENSE_KEYWORDS
        scores = {}
        for cat, kws in kw_map.items():
            s = sum(2 for w in kws if w in desc)
            if s>0: scores[cat]=s

        if scores:
            best = max(scores, key=scores.get)
            total = sum(scores.values())
            conf = min(0.90, scores[best]/total + 0.35)
            is_rev = best in ["retail_sales","wholesale_sales"]
            return {"category":best,"confidence":round(conf,2),"is_revenue":is_rev,"flags":[]}

        # Default
        if tx_type=="credit":
            if amount<50000:   return {"category":"retail_sales","confidence":0.55,"is_revenue":True,"flags":[]}
            if amount<500000:  return {"category":"wholesale_sales","confidence":0.50,"is_revenue":True,"flags":[]}
            return {"category":"unknown_income","confidence":0.40,"is_revenue":True,"flags":["unclassified"]}
        else:
            if amount>200000:  return {"category":"supplier_payment","confidence":0.50,"is_revenue":False,"flags":[]}
            return {"category":"unknown_expense","confidence":0.40,"is_revenue":False,"flags":[]}


class AnomalyDetector:
    def detect(self, profile, classified_txns):
        anomalies = []
        f = profile.get("fedha",{})
        monthly = profile.get("monthly_raw",{})
        rev = f.get("true_avg_monthly_revenue",0)
        exp = f.get("avg_monthly_expenses_tzs",0)

        if rev>0:
            margin = (rev-exp)/rev
            if margin>0.70:
                anomalies.append({"code":"HIGH_PROFIT_MARGIN","severity":"WARNING","icon":"⚠️",
                    "message":f"Profit margin {round(margin*100)}% is unusually high — possible missing expense data",
                    "ujumbe":f"Margin ya faida ni {round(margin*100)}% — matumizi yanaweza kukosekana",
                    "action":"Verify all expenses are captured"})
            if margin<0:
                anomalies.append({"code":"NEGATIVE_CASHFLOW","severity":"CRITICAL","icon":"🚨",
                    "message":"Expenses exceed revenue — business may be unsustainable",
                    "ujumbe":"Matumizi yanazidi mapato — biashara iko hatarini",
                    "action":"High risk — detailed investigation required"})

        total_loans = sum(float(t.get("amount",0)) for t in classified_txns if t.get("classified",{}).get("category")=="loan_received")
        total_credits = sum(float(t.get("amount",0)) for t in classified_txns if t.get("type")=="credit")
        if total_credits>0 and total_loans/total_credits>0.30:
            anomalies.append({"code":"LOAN_INFLATION","severity":"WARNING","icon":"⚠️",
                "message":f"Loans are {round(total_loans/total_credits*100)}% of credits — revenue may be inflated",
                "ujumbe":"Mikopo inaweza kuongeza mapato bandia","action":"Separate loans from true revenue"})

        months = sorted(monthly.keys())
        if len(months)>=2:
            revenues = [monthly[m].get("true_revenue",0) for m in months]
            for i in range(1,len(revenues)):
                if revenues[i-1]>0:
                    drop = (revenues[i-1]-revenues[i])/revenues[i-1]
                    if drop>0.35:
                        anomalies.append({"code":"REVENUE_DROP","severity":"WARNING","icon":"📉",
                            "message":f"Revenue dropped {round(drop*100)}% from {months[i-1]} to {months[i]}",
                            "ujumbe":f"Mapato yalishuka {round(drop*100)}%","action":"Investigate cause of decline"})

        if rev>0 and exp==0:
            anomalies.append({"code":"NO_EXPENSES","severity":"WARNING","icon":"⚠️",
                "message":"No expenses detected — data may be incomplete",
                "ujumbe":"Hakuna matumizi — data inaweza kuwa haikamilika","action":"Request complete transaction history"})

        return anomalies


class ScoringEngine:
    WEIGHTS = {"income_stability":0.30,"transaction_freq":0.25,"customer_diversity":0.20,"cashflow_health":0.15,"revenue_trend":0.10}

    def compute(self, profile, classified_txns):
        monthly = profile.get("monthly_raw",{})
        months = sorted(monthly.keys())
        if not months: return {"final_score":0,"components":{},"trend_direction":"UNKNOWN","reasoning":["Insufficient data"]}

        revenues  = [monthly[m].get("true_revenue",0) for m in months]
        expenses  = [monthly[m].get("matumizi",0) for m in months]
        tx_counts = [monthly[m].get("credit_count",0) for m in months]

        s1 = self._stability(revenues)
        s2 = self._frequency(tx_counts)
        s3 = self._diversity(classified_txns)
        s4 = self._cashflow(revenues, expenses)
        s5, trend = self._trend(revenues)

        final = round(min(100,max(0,
            s1*self.WEIGHTS["income_stability"] +
            s2*self.WEIGHTS["transaction_freq"] +
            s3*self.WEIGHTS["customer_diversity"] +
            s4*self.WEIGHTS["cashflow_health"] +
            s5*self.WEIGHTS["revenue_trend"]
        )))

        return {
            "final_score": final,
            "trend_direction": trend,
            "components": {
                "income_stability":   {"score":round(s1),"weight":"30%","label":"Uthabiti wa Mapato / Income Stability"},
                "transaction_freq":   {"score":round(s2),"weight":"25%","label":"Mzunguko wa Miamala / Transaction Frequency"},
                "customer_diversity": {"score":round(s3),"weight":"20%","label":"Utofauti wa Wateja / Customer Diversity"},
                "cashflow_health":    {"score":round(s4),"weight":"15%","label":"Afya ya Mtiririko / Cash Flow Health"},
                "revenue_trend":      {"score":round(s5),"weight":"10%","label":"Mwelekeo wa Mapato / Revenue Trend"},
            },
            "reasoning": self._reasons(final,s1,s2,s3,s4,s5,revenues,expenses,trend),
        }

    def _stability(self, revenues):
        if len(revenues)<2 or sum(revenues)==0: return 50
        mean = sum(revenues)/len(revenues)
        if mean==0: return 0
        cv = math.sqrt(sum((r-mean)**2 for r in revenues)/len(revenues))/mean
        return max(0,min(100,round(100*(1-min(cv,1.0)))))

    def _frequency(self, counts):
        if not counts: return 30
        avg = sum(counts)/len(counts)
        if avg>=60: return 100
        if avg>=30: return 80
        if avg>=15: return 65
        if avg>=8:  return 50
        if avg>=3:  return 35
        return 20

    def _diversity(self, txns):
        retail = [t for t in txns if t.get("classified",{}).get("category") in ["retail_sales","wholesale_sales"]]
        if not retail: return 40
        phones = [t.get("phone","") for t in retail if t.get("phone")]
        if not phones: return 45
        ratio = len(set(phones))/len(phones)
        if ratio>=0.8: return 95
        if ratio>=0.6: return 80
        if ratio>=0.4: return 65
        if ratio>=0.2: return 50
        return 35

    def _cashflow(self, revenues, expenses):
        if not revenues or not expenses: return 50
        total_rev = sum(revenues)
        if total_rev==0: return 0
        nr = (total_rev - sum(expenses))/total_rev
        if nr>=0.8: return 100
        if nr>=0.6: return 90
        if nr>=0.4: return 75
        if nr>=0.2: return 60
        if nr>=0.05: return 45
        if nr>=0:  return 30
        return max(0,round(30+nr*30))

    def _trend(self, revenues):
        if len(revenues)<2 or revenues[0]==0: return 50,"STABLE"
        t = (revenues[-1]-revenues[0])/revenues[0]
        if t>0.20:  return 95,"GROWING"
        if t>0.05:  return 80,"GROWING"
        if t>-0.05: return 60,"STABLE"
        if t>-0.20: return 35,"DECLINING"
        return 15,"DECLINING"

    def _reasons(self, score, s1,s2,s3,s4,s5,revenues,expenses,trend):
        r=[]
        avg_rev = sum(revenues)/len(revenues) if revenues else 0
        avg_exp = sum(expenses)/len(expenses) if expenses else 0
        if s1>=75: r.append("Revenue arrives consistently each month / Mapato yanakuja kwa utaratibu")
        elif s1>=50: r.append("Revenue shows moderate monthly variation / Mapato yana tofauti kidogo")
        else: r.append("Revenue is irregular — large monthly swings / Mapato si ya kawaida")
        if s2>=75: r.append("High transaction volume indicates active trading / Miamala mingi — biashara inafanya kazi")
        elif s2<40: r.append("Low transaction count — small business or incomplete data / Miamala michache")
        if s4>=70 and avg_rev>0:
            margin = round((avg_rev-avg_exp)/avg_rev*100)
            r.append(f"Healthy cash flow — {margin}% profit margin / Mtiririko mzuri — margin {margin}%")
        elif s4<40: r.append("Expenses close to revenue — thin margins / Matumizi karibu na mapato")
        if trend=="GROWING": r.append("Revenue is growing — business is expanding / Mapato yanaongezeka")
        elif trend=="DECLINING": r.append("CAUTION: Revenue declining — investigate / TAHADHARI: Mapato yanashuka")
        return r


class DecisionEngine:
    def decide(self, scores, anomalies, profile):
        score = scores.get("final_score",0)
        trend = scores.get("trend_direction","STABLE")
        f = profile.get("fedha",{})

        decision = "APPROVE" if score>=80 else "REVIEW" if score>=60 else "DECLINE"
        overrides, reasons = [], []

        # Override 1: Declining revenue
        if trend=="DECLINING":
            monthly = profile.get("monthly_raw",{})
            months = sorted(monthly.keys())
            if len(months)>=2:
                first = monthly[months[0]].get("true_revenue",0)
                last  = monthly[months[-1]].get("true_revenue",0)
                if first>0:
                    drop = (first-last)/first
                    if drop>0.20 and decision=="APPROVE":
                        decision="REVIEW"; overrides.append("DECLINING_REVENUE")
                        reasons.append(f"Revenue dropped {round(drop*100)}% — downgraded to REVIEW / Mapato yameshuka {round(drop*100)}%")

        # Override 2: Critical anomalies
        if any(a.get("severity")=="CRITICAL" for a in anomalies):
            decision="DECLINE"; overrides.append("CRITICAL_ANOMALY")
            reasons.append("Critical financial anomaly — cannot approve / Tatizo kubwa la fedha")

        # Override 3: Missing expenses
        if any(a["code"]=="NO_EXPENSES" for a in anomalies) and decision=="APPROVE":
            decision="REVIEW"; overrides.append("MISSING_EXPENSES")
            reasons.append("No expenses detected — investigate / Hakuna matumizi yaliyopatikana")

        # Override 4: Loan inflation
        if any(a["code"]=="LOAN_INFLATION" for a in anomalies) and decision=="APPROVE":
            decision="REVIEW"; overrides.append("LOAN_INFLATION")
            reasons.append("Revenue may be inflated by loans / Mapato yanaweza kuwa ya mikopo")

        avg_net = f.get("avg_net_cash_flow_tzs",0)
        cap_ratio = 0.30 if decision=="APPROVE" else 0.20 if decision=="REVIEW" else 0
        monthly_cap = max(0, avg_net*cap_ratio)
        max_loan = monthly_cap*6

        conf = "HIGH" if not overrides and score>=75 else "MEDIUM" if len(overrides)<=1 else "LOW"

        next_steps = []
        if decision=="APPROVE":
            next_steps=["Verify business owner identity / Thibitisha utambulisho","Request 3+ months data if available / Omba miezi 3 zaidi"]
        elif decision=="REVIEW":
            if "DECLINING_REVENUE" in overrides: next_steps.append("Ask reason for revenue decline / Uliza sababu ya kushuka")
            if "MISSING_EXPENSES" in overrides: next_steps.append("Request complete expense records / Omba taarifa kamili za matumizi")
            if "LOAN_INFLATION" in overrides: next_steps.append("Separate real revenue from loans / Tofautisha mapato na mikopo")
            next_steps.append("Conduct business owner interview / Fanya mahojiano na mmiliki")
        else:
            next_steps=["Advise owner to improve records / Shauri kuboresha rekodi","May reapply after 3 months / Weza kuomba tena baada ya miezi 3"]

        return {
            "decision": decision,
            "pendekezo": {"APPROVE":"IDHINISHA","REVIEW":"KAGUA","DECLINE":"KATAA"}[decision],
            "score": score,
            "overrides_applied": overrides,
            "override_reasons": reasons,
            "monthly_loan_capacity_tzs": round(monthly_cap),
            "max_loan_amount_tzs": round(max_loan),
            "confidence": conf,
            "next_steps": next_steps,
        }


class FinancialProfileV2:
    def __init__(self):
        self.classifier = TransactionClassifier()
        self.anomaly    = AnomalyDetector()
        self.scorer     = ScoringEngine()
        self.decider    = DecisionEngine()

    def analyze(self, transactions, business_name="Biashara"):
        if not transactions:
            return {"error":"No transactions"}

        # Step 1: Classify
        classified = []
        for tx in transactions:
            c = tx.copy()
            c["classified"] = self.classifier.classify(c, transactions)
            classified.append(c)

        # Step 2: Monthly profile
        monthly_raw = defaultdict(lambda:{
            "true_revenue":0,"gross_credits":0,"matumizi":0,
            "credit_count":0,"debit_count":0,
            "loan_received":0,"agent_float":0,"owner_deposit":0,
        })

        for tx in classified:
            date = tx.get("date","")
            try:
                if "-" in date: mk = date[:7]
                elif "/" in date:
                    p=date.split("/")
                    mk = f"{p[2]}-{p[1].zfill(2)}" if len(p)==3 else date[:7]
                else: mk = datetime.now().strftime("%Y-%m")
            except: mk = datetime.now().strftime("%Y-%m")

            amount = float(tx.get("amount",0))
            cat    = tx["classified"].get("category","unknown")
            is_rev = tx["classified"].get("is_revenue",False)

            if tx.get("type")=="credit":
                monthly_raw[mk]["gross_credits"] += amount
                monthly_raw[mk]["credit_count"]  += 1
                if is_rev: monthly_raw[mk]["true_revenue"] += amount
                if cat=="loan_received":  monthly_raw[mk]["loan_received"] += amount
                if cat=="agent_float_in": monthly_raw[mk]["agent_float"]   += amount
            elif tx.get("type")=="debit":
                monthly_raw[mk]["matumizi"]    += amount
                monthly_raw[mk]["debit_count"] += 1

        monthly_raw = dict(monthly_raw)
        months = sorted(monthly_raw.keys())
        if not months: return {"error":"No monthly data"}

        true_revenues = [monthly_raw[m]["true_revenue"] for m in months]
        expenses      = [monthly_raw[m]["matumizi"]     for m in months]
        net_flows     = [r-e for r,e in zip(true_revenues,expenses)]
        avg_rev = sum(true_revenues)/len(true_revenues)
        avg_exp = sum(expenses)/len(expenses)
        avg_net = sum(net_flows)/len(net_flows)

        fedha = {
            "true_avg_monthly_revenue":  round(avg_rev),
            "avg_monthly_revenue_tzs":   round(avg_rev),
            "avg_monthly_expenses_tzs":  round(avg_exp),
            "avg_net_cash_flow_tzs":     round(avg_net),
            "total_true_revenue_tzs":    round(sum(true_revenues)),
            "total_expenses_tzs":        round(sum(expenses)),
            "gross_credits_total":       round(sum(monthly_raw[m]["gross_credits"] for m in months)),
            "profit_margin_pct":         round((avg_rev-avg_exp)/avg_rev*100) if avg_rev>0 else 0,
        }

        profile_base = {
            "biashara":{"jina":business_name,"name":business_name,
                "total_transactions":len(classified),"months_analyzed":len(months),"miezi":months},
            "fedha": fedha,
            "monthly_raw": monthly_raw,
        }

        # Steps 4-6
        anomalies = self.anomaly.detect(profile_base, classified)
        scores    = self.scorer.compute(profile_base, classified)
        decision  = self.decider.decide(scores, anomalies, profile_base)

        # Monthly summary
        monthly_summary = {}
        for m in months:
            d = monthly_raw[m]
            monthly_summary[m] = {
                "mapato_tzs":    round(d["true_revenue"]),
                "gross_credits": round(d["gross_credits"]),
                "matumizi_tzs":  round(d["matumizi"]),
                "faida_tzs":     round(d["true_revenue"]-d["matumizi"]),
                "credit_count":  d["credit_count"],
                "debit_count":   d["debit_count"],
                "loan_received": round(d["loan_received"]),
            }

        health = ("EXCELLENT" if scores["final_score"]>=80 else
                  "GOOD"      if scores["final_score"]>=65 else
                  "MODERATE"  if scores["final_score"]>=50 else
                  "POOR"      if scores["final_score"]>=35 else "CRITICAL")

        return {
            "akili_ni_mali":{"toleo":"2.0.0","tarehe":datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            "biashara": profile_base["biashara"],
            "fedha":    fedha,
            "tathmini": {
                "stability_score":  scores["final_score"],
                "score_components": scores["components"],
                "trend_direction":  scores["trend_direction"],
                "reasoning":        scores["reasoning"],
                "business_health":  health,
                "credit_risk":      "LOW" if decision["decision"]=="APPROVE" else "MEDIUM" if decision["decision"]=="REVIEW" else "HIGH",
            },
            "uamuzi_mkopo":       decision,
            "anomalies":          anomalies,
            "muhtasari_wa_miezi": monthly_summary,
            "success":            True,
        }
