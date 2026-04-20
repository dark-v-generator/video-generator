# Justfile for video-generator

PROD_HOST := "gustavo@192.168.1.100"
PROD_DIR  := "~/video-generator"

# Generate a two part reddit video
generate-reddit url output_dir="output":
    .venv/bin/python scripts/reddit_two_part_history.py {{url}} --output-dir {{output_dir}}

# Generate a two part reddit video in low quality (fast)
generate-reddit-fast url output_dir="output":
    .venv/bin/python scripts/reddit_two_part_history.py {{url}} --output-dir {{output_dir}} --low-quality

# Format code
fmt:
    .venv/bin/black src scripts tests

# Deploy to prod server: sync files, install deps, restart bot
deploy:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "==> Syncing files to {{PROD_HOST}}:{{PROD_DIR}}..."
    rsync -avz --delete \
        --exclude '.venv/' \
        --exclude '__pycache__/' \
        --exclude '.env' \
        --exclude 'output/' \
        --exclude '.storage/' \
        --exclude '.DS_Store' \
        --exclude '.git/' \
        --exclude '*.mp4' \
        ./ {{PROD_HOST}}:{{PROD_DIR}}/

    echo "==> Ensuring uv is installed on server..."
    ssh {{PROD_HOST}} 'command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh'

    echo "==> Installing dependencies on server..."
    ssh {{PROD_HOST}} 'cd {{PROD_DIR}} && export PATH="$HOME/.local/bin:$PATH" && uv sync --frozen --no-dev'

    echo "==> Installing Playwright browsers..."
    ssh -t {{PROD_HOST}} 'cd {{PROD_DIR}} && export PATH="$HOME/.local/bin:$PATH" && sudo env PATH="$HOME/.local/bin:$PATH" uv run playwright install --with-deps chrome'

    echo "==> Restarting bot service..."
    ssh {{PROD_HOST}} 'systemctl --user daemon-reload && systemctl --user restart video-bot.service'
    sleep 2

    echo "==> Done!"
    ssh {{PROD_HOST}} 'systemctl --user status video-bot.service --no-pager'

# One-time: install Playwright system deps (needs sudo)
prod-setup-deps:
    ssh -t {{PROD_HOST}} 'cd {{PROD_DIR}} && sudo env PATH="$HOME/.local/bin:$PATH" uv run playwright install-deps'

# Start prod bot (without deploying)
prod-start:
    ssh {{PROD_HOST}} 'systemctl --user start video-bot.service'
    ssh {{PROD_HOST}} 'systemctl --user status video-bot.service --no-pager'

# Check prod bot status
prod-status:
    ssh {{PROD_HOST}} 'systemctl --user status video-bot.service --no-pager'

# Tail prod logs
prod-logs:
    ssh {{PROD_HOST}} 'journalctl --user -u video-bot.service -f'

# Stop prod bot
prod-stop:
    ssh {{PROD_HOST}} 'systemctl --user stop video-bot.service'
