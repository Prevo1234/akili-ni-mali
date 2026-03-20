# 🚀 AKILI NI MALI — Deploy to Railway (10 minutes)

## STEP 1 — Add these 3 files to your GitHub repo

Go to https://github.com/Prevo1234/akili-ni-mali and upload:

1. `Procfile`        ← tells Railway how to start your app
2. `requirements.txt` ← updated with all packages
3. `railway.json`   ← Railway config

To add them: Click "Add file" → "Upload files" → drag all 3 → "Commit changes"

---

## STEP 2 — Create Railway account

1. Go to https://railway.app
2. Click "Login" → "Login with GitHub"
3. Authorize Railway to access your GitHub

---

## STEP 3 — Deploy your repo

1. Click "New Project"
2. Click "Deploy from GitHub repo"
3. Select "Prevo1234/akili-ni-mali"
4. Railway auto-detects Python and starts building

---

## STEP 4 — Set environment variables

In Railway dashboard → your project → "Variables" tab, add:

  ANTHROPIC_API_KEY = sk-ant-your-key-here
  FLASK_ENV = production

(Get your Anthropic API key from https://console.anthropic.com)

---

## STEP 5 — Get your live URL

1. In Railway → your project → "Settings" tab
2. Under "Networking" → click "Generate Domain"
3. You get a URL like: https://akili-ni-mali-production.up.railway.app

---

## STEP 6 — Test it

Open your URL in browser. You should see the API response.

Then open: https://your-url.up.railway.app/portal
→ This is your FULL investor demo — bank lender portal with live AI

---

## WHAT INVESTORS WILL SEE

Your live URLs to share:
- /portal       → Full bank lender dashboard with AI scoring
- /analyze/demo → Live AI demo endpoint
- /health       → Shows ML model is running (91.6% accuracy)
- /ml/info      → Shows your RandomForest model details

---

## IF SOMETHING FAILS

Check Railway logs: your project → "Deployments" → click latest → "View Logs"

Common fixes:
- "Module not found" → requirements.txt is missing a package
- "Port already in use" → Procfile PORT variable issue (already fixed)
- "ANTHROPIC_API_KEY not set" → add it in Variables tab

---

## TOTAL COST: $0
Railway free tier gives you $5 credit/month — enough for your MVP demo.
