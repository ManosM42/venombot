# ───────────────────────── Venom Shop Bot — Dockerfile ─────────────────────────
FROM python:3.13-slim

# Don't buffer stdout/stderr — logs show up immediately in Coolify
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps needed to build some Python packages (e.g. aiohttp)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the bot
COPY . .

# Persistent data (fee_settings.json, sqlite db, etc.) — mount a Coolify volume here
RUN mkdir -p /app/bot/data
VOLUME ["/app/bot/data"]

# Run the bot exactly as you do locally
CMD ["python3", "-m", "bot.main"]