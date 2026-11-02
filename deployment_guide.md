# UrbanHeat Analytics — Project Summary & Deployment Guide

## What This Project Is

**UrbanHeat Analytics** is a Streamlit-based research dashboard for Mumbai urban-heat data.
It lets researchers upload a CSV, document its provenance, map columns, and explore temperature,
vegetation, spatial, and temporal patterns — with no fabricated observations.

## App is Running ✅

The Streamlit app is live locally at **http://localhost:8501**

![UrbanHeat Analytics Dashboard](file:///C:/Users/Himanshu/.gemini/antigravity-ide/brain/ec1d2e82-bc52-4869-ba4e-7dbfbd9f21a3/urban_heat_analytics_dashboard_1793360310248.png)

---

## Files Created / Modified

| File | Purpose |
|------|---------|
| [`Dockerfile`](file:///c:/Users/Himanshu/OneDrive/Documents/Urja-main/Dockerfile) | Production-ready Docker image |
| [`docker-compose.yml`](file:///c:/Users/Himanshu/OneDrive/Documents/Urja-main/docker-compose.yml) | One-command local startup |
| [`.dockerignore`](file:///c:/Users/Himanshu/OneDrive/Documents/Urja-main/.dockerignore) | Keeps image lean (~no Node/Replit artifacts) |
| [`.streamlit/config.toml`](file:///c:/Users/Himanshu/OneDrive/Documents/Urja-main/.streamlit/config.toml) | Bakes green theme + disables telemetry |
| [`vercel.json`](file:///c:/Users/Himanshu/OneDrive/Documents/Urja-main/vercel.json) | Proper Vercel v2 static config |
| [`vercel-frontend/index.html`](file:///c:/Users/Himanshu/OneDrive/Documents/Urja-main/vercel-frontend/index.html) | Beautiful Vercel landing page with deploy guide |

---

## Why Streamlit Can't Run Directly on Vercel

> [!IMPORTANT]
> Streamlit uses **persistent WebSocket connections** for its UI. Vercel's serverless
> functions are stateless and time out after max 60 seconds — incompatible with Streamlit's architecture.

**The solution used here:**
- **Vercel** hosts the static landing page (`vercel-frontend/index.html`) — deployed instantly, free, custom domain supported.
- **Container platform** (Render/Railway/Fly.io/HF Spaces) runs the actual Streamlit app.
- The landing page has an iframe embed that connects to the container URL after you deploy it.

---

## Run Locally (from ZIP)

### Option A — Plain Python (already running)
```bash
python -m streamlit run app.py --server.port 8501
# → http://localhost:8501
```

### Option B — Docker (recommended for sharing)
```bash
# Build
docker build -t urbanheat .

# Run
docker run -p 8501:8501 urbanheat

# Or with Docker Compose (even easier)
docker compose up --build
```

---

## Deploy the App Continuously

### 🟢 Render (Recommended — free tier)
1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Select your repo, Runtime: **Docker**, Port: **8501**
4. Health check path: `/_stcore/health`
5. Done — auto-deploys on every `git push`

### 🚂 Railway
```bash
npm i -g @railway/cli
railway login && railway init && railway up
# Set PORT=8501 in environment variables
```

### 🤗 Hugging Face Spaces
- Create a **Docker** Space
- Upload `app.py`, `analysis.py`, `requirements.txt`, `Dockerfile`
- Change `EXPOSE 8501` → `EXPOSE 7860` and add `ENV PORT=7860`

### ☁️ Google Cloud Run
```bash
gcloud builds submit --tag gcr.io/YOUR-PROJECT/urbanheat .
gcloud run deploy urbanheat --image gcr.io/YOUR-PROJECT/urbanheat \
  --port 8501 --allow-unauthenticated
```

---

## Deploy to Vercel (Landing Page)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy from project root
vercel --prod

# That's it — the landing page goes live at your-app.vercel.app
```

After deploying the Streamlit app to Render/Railway, paste its URL into the
landing page embed input → the app loads in an iframe.

---

## Stack

- Python 3.13, Streamlit 1.64, pandas 3.x, NumPy 2.x, Plotly 7.x
- Docker (python:3.13-slim base)
- Vercel (static HTML landing page)
