## Multi-stage build for Video Generator
## 1) Build frontend with Node
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Install deps
COPY frontend/package*.json ./
RUN npm ci

# Copy source and build
COPY frontend/ .
# Ensure Vite uses relative API paths in production as in Makefile
ENV VITE_BACKEND_URL=""
RUN npm run build


## 2) Runtime image with Python and system deps
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=1 \
  FILE_STORAGE_BASE_PATH=/app/.storage \
  API_HOST=0.0.0.0 \
  API_PORT=8000 \
  ENVIRONMENT=production \
  DEBUG=false \
  FFMPEG_PATH=/usr/bin/ffmpeg

WORKDIR /app

# System deps: ffmpeg for video, and build essentials for some wheels
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
  ffmpeg \
  libsndfile1 \
  build-essential \
  gcc \
  g++ \
  make \
  python3-dev \
  pkg-config \
  rustc \
  cargo \
  curl \
  ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Copy backend code and python project files
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY main.py  ./
COPY default_font.ttf ./
COPY web ./web

# Copy frontend build artifacts from stage 1 into FastAPI's expected dirs
COPY --from=frontend-builder /app/frontend/dist /app/web/static
RUN mkdir -p /app/web/templates \
  && cp /app/web/static/index.html /app/web/templates/index.html || true

# Install uv for faster installs, then sync runtime deps
RUN pip install --no-cache-dir uv
RUN uv sync --frozen

# Install Playwright browser dependencies for Debian
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
  libnss3 \
  libatk-bridge2.0-0 \
  libgtk-3-0 \
  libxkbcommon0 \
  libx11-xcb1 \
  libdrm2 \
  libgbm1 \
  libxshmfence1 \
  libasound2 \
  libxrandr2 \
  libxdamage1 \
  libxcomposite1 \
  fonts-liberation \
  fonts-dejavu-core \
  && rm -rf /var/lib/apt/lists/*

# Install Playwright Chromium browser
RUN uv run playwright install chromium

EXPOSE 8000

# Healthcheck (basic): check that root returns 200
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/ || exit 1

# Start FastAPI
CMD ["uv", "run", "python", "-m", "uvicorn", "src.main_fastapi:app", "--host", "0.0.0.0", "--port", "8000"]


