FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --no-dev --frozen

RUN uv run playwright install --with-deps chromium

COPY . .

COPY config/tiktok_cookies.txt config/tiktok_cookies.txt

CMD ["uv", "run", "python", "bots/run_all.py"]
