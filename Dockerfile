# UrbanHeat Analytics — Production Dockerfile
# Works locally (from zip) and on any container platform (Render, Railway, Fly.io, Cloud Run)

FROM python:3.13-slim

# Metadata
LABEL org.opencontainers.image.title="UrbanHeat Analytics"
LABEL org.opencontainers.image.description="Urban heat research dashboard for Mumbai — Streamlit app"

# --- System deps ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# --- App directory ---
WORKDIR /app

# Install Python deps first (layer-cached unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only what the app needs (no node/pnpm/test artefacts)
COPY app.py .
COPY analysis.py .

# Streamlit config — bake in the project config
RUN mkdir -p .streamlit
COPY .streamlit/config.toml .streamlit/config.toml

EXPOSE 8501

# Healthcheck (Streamlit exposes /_stcore/health since v1.28)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["python", "-m", "streamlit", "run", "app.py", \
            "--server.port=8501", \
            "--server.address=0.0.0.0", \
            "--server.headless=true", \
            "--browser.gatherUsageStats=false"]
