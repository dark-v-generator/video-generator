# Justfile for video-generator

PROD_HOST := "gustavo@192.168.1.100"
PROD_DIR  := "~/video-generator"

# Generate a two part reddit video
generate-reddit url output_dir="output":
    .venv/bin/python scripts/reddit_two_part_history.py {{url}} --output-dir {{output_dir}}

# Generate a two part reddit video in low quality (fast)
generate-reddit-fast url output_dir="output":
    .venv/bin/python scripts/reddit_two_part_history.py {{url}} --output-dir {{output_dir}} --low-quality

# Run the daily auto-publish pipeline locally (find → generate → schedule)
daily-publish count="":
    #!/usr/bin/env bash
    set -euo pipefail
    args=""
    if [ -n "{{count}}" ]; then args="--count {{count}}"; fi
    uv run python scripts/daily_auto_publish.py $args

# Generate videos only (no publishing). Saves to output/daily/.
daily-generate count="":
    #!/usr/bin/env bash
    set -euo pipefail
    args="--generate-only"
    if [ -n "{{count}}" ]; then args="$args --count {{count}}"; fi
    uv run python scripts/daily_auto_publish.py $args

# Publish pre-generated videos from a directory (no discovery/generation).
daily-publish-only dir="output/daily":
    uv run python scripts/daily_auto_publish.py --publish-only {{dir}}

# Run the full daily pipeline on the prod server.
prod-daily-publish count="":
    #!/usr/bin/env bash
    set -euo pipefail
    args=""
    if [ -n "{{count}}" ]; then args="--count {{count}}"; fi
    echo "==> Running daily auto-publish on {{PROD_HOST}}..."
    ssh -t {{PROD_HOST}} "cd {{PROD_DIR}} && export PATH=\"\$HOME/.local/bin:\$PATH\" && mkdir -p .storage/tiktok_runs && RUN_LOG=.storage/tiktok_runs/\$(date -u +%Y%m%dT%H%M%S)-daily.log && CONFIG_PATH=config.prod.yaml xvfb-run -a --server-args='-screen 0 1920x1080x24' uv run python scripts/daily_auto_publish.py $args 2>&1 | tee \$RUN_LOG"
    just sync-tiktok-runs

# Generate videos only on the prod server (saves to output/daily/).
prod-daily-generate count="":
    #!/usr/bin/env bash
    set -euo pipefail
    args="--generate-only"
    if [ -n "{{count}}" ]; then args="$args --count {{count}}"; fi
    echo "==> Generating videos on {{PROD_HOST}}..."
    ssh -t {{PROD_HOST}} "cd {{PROD_DIR}} && export PATH=\"\$HOME/.local/bin:\$PATH\" && CONFIG_PATH=config.prod.yaml uv run python scripts/daily_auto_publish.py $args 2>&1"

# Publish pre-generated videos on the prod server.
prod-daily-publish-only dir="output/daily":
    #!/usr/bin/env bash
    set -euo pipefail
    echo "==> Publishing from {{dir}} on {{PROD_HOST}}..."
    ssh -t {{PROD_HOST}} "cd {{PROD_DIR}} && export PATH=\"\$HOME/.local/bin:\$PATH\" && mkdir -p .storage/tiktok_runs && RUN_LOG=.storage/tiktok_runs/\$(date -u +%Y%m%dT%H%M%S)-publish-only.log && CONFIG_PATH=config.prod.yaml xvfb-run -a --server-args='-screen 0 1920x1080x24' uv run python scripts/daily_auto_publish.py --publish-only {{dir}} 2>&1 | tee \$RUN_LOG"
    just sync-tiktok-runs

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

    echo "==> Installing systemd service unit..."
    ssh {{PROD_HOST}} 'mkdir -p ~/.config/systemd/user && cp {{PROD_DIR}}/deploy/video-bot.service ~/.config/systemd/user/video-bot.service'

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

# ============================================================
# TikTok auto-publisher (server-only)
# ============================================================
# Architecture: bootstrap-on-server. The first login is performed
# directly on the prod server through SSH X11-forwarding (your Mac
# becomes a temporary remote screen via XQuartz). After that, all
# cookies + device fingerprint live on the server, and daily runs
# use Xvfb (in-memory display) so the agent can stay headful (best
# stealth) without needing a real monitor.

# One-time: install Xvfb (virtual display), x11vnc (so you can VNC
# into the bootstrap session from anywhere), and patchright's stealth
# Chromium build on the prod server. Idempotent and re-runnable.
#
# NOTE: the apt step needs sudo. Run this from your interactive
# terminal (it prompts for the sudo password once).
prod-tiktok-setup:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "==> Installing xvfb + x11vnc on {{PROD_HOST}} (sudo password prompt)..."
    ssh -t {{PROD_HOST}} 'sudo apt-get update && sudo apt-get install -y --no-install-recommends xvfb x11vnc'
    echo "==> Installing patchright Chromium on {{PROD_HOST}}..."
    ssh {{PROD_HOST}} 'cd {{PROD_DIR}} && export PATH="$HOME/.local/bin:$PATH" && uv run python -m patchright install chromium'
    echo "==> Verifying..."
    ssh {{PROD_HOST}} 'which xvfb-run && which x11vnc && ls ~/.cache/ms-playwright | grep chromium- | tail -3'
    echo "==> Done. Next: just prod-tiktok-bootstrap-vnc output/part1.mp4"

# One-time (and any time TikTok forces re-auth): log into TikTok on
# the prod server via VNC. Works from any machine with a VNC client
# (macOS has Screen Sharing built-in: Finder -> Cmd+K -> vnc://...).
#
# Flow:
#   1. rsyncs the video to the server
#   2. opens an SSH tunnel so port 5900 on your laptop -> server
#   3. on the server: starts Xvfb :99 + x11vnc (localhost-only)
#   4. auto-opens vnc://localhost:5900 on macOS (Cmd+K on others)
#   5. runs the publisher against DISPLAY=:99 — drag the slider in
#      the VNC window when it appears
#   6. tears Xvfb + x11vnc down on exit
#
# Usage:
#   just prod-tiktok-bootstrap-vnc output/part1.mp4
#   just prod-tiktok-bootstrap-vnc output/part1.mp4 30m "Bootstrap test"
prod-tiktok-bootstrap-vnc video_path="output/part1.mp4" schedule_in="30m" description="Bootstrap login test":
    #!/usr/bin/env bash
    set -euo pipefail
    echo "==> Syncing {{video_path}} to server..."
    rsync -avz --progress {{video_path}} {{PROD_HOST}}:{{PROD_DIR}}/output/
    rsync -avz scripts/server-tiktok-vnc-bootstrap.sh {{PROD_HOST}}:{{PROD_DIR}}/scripts/
    REMOTE_VIDEO="output/$(basename {{video_path}})"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        ( sleep 8 && open "vnc://localhost:5900" ) &
        OPEN_PID=$!
        trap 'kill $OPEN_PID 2>/dev/null || true' EXIT
        echo "==> macOS detected: VNC client will auto-open in ~8s."
    else
        echo "==> Open vnc://localhost:5900 in your VNC client once Xvfb starts."
    fi
    echo "==> Opening SSH tunnel (localhost:5900 -> server) and starting bootstrap..."
    ssh -t -L 5900:localhost:5900 {{PROD_HOST}} \
        "chmod +x {{PROD_DIR}}/scripts/server-tiktok-vnc-bootstrap.sh && {{PROD_DIR}}/scripts/server-tiktok-vnc-bootstrap.sh '$REMOTE_VIDEO' --description '{{description}}' --schedule-in {{schedule_in}}"
    just sync-tiktok-runs

# Interactive REPL for testing TikTok tools against a live browser.
# Opens Chromium with the saved session and drops into a Python console
# where you can call click_by_text, run_js, set_contenteditable, etc.
tiktok-repl:
    uv run python scripts/tiktok_repl.py

# Same but on the prod server via VNC so you can watch the browser.
prod-tiktok-repl:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "$OSTYPE" == "darwin"* ]]; then
        ( sleep 10 && open "vnc://localhost:5900" ) &
        OPEN_PID=$!
        trap 'kill $OPEN_PID 2>/dev/null || true' EXIT
        echo "==> macOS detected: VNC client will auto-open in ~10s."
    else
        echo "==> Open vnc://localhost:5900 in your VNC client once Xvfb starts."
    fi
    ssh -t -L 5900:localhost:5900 {{PROD_HOST}} 'export PATH="$HOME/.local/bin:$PATH" && cd {{PROD_DIR}} && (kill $(cat /tmp/.X98-lock 2>/dev/null) 2>/dev/null || true) && rm -f /tmp/.X98-lock /tmp/.X11-unix/X98 2>/dev/null; Xvfb :98 -screen 0 1920x1080x24 -nolisten tcp & XVFB_PID=$!; sleep 1; x11vnc -display :98 -localhost -passwd tiktok -forever -shared -q & VNC_PID=$!; sleep 1; DISPLAY=:98 uv run python scripts/tiktok_repl.py; kill $VNC_PID $XVFB_PID 2>/dev/null'

# X11-forwarding alternative (requires XQuartz on macOS). Kept for
# power users; prefer prod-tiktok-bootstrap-vnc.
prod-tiktok-bootstrap-x11 video_path="output/part1.mp4" schedule_in="30m" description="Bootstrap login test":
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -z "${DISPLAY:-}" ]; then
        echo "ERROR: \$DISPLAY is not set. Install XQuartz, log out + log back in, then retry."
        echo "       Or use: just prod-tiktok-bootstrap-vnc {{video_path}}"
        exit 1
    fi
    echo "==> Syncing {{video_path}} to server..."
    rsync -avz --progress {{video_path}} {{PROD_HOST}}:{{PROD_DIR}}/output/
    REMOTE_VIDEO="output/$(basename {{video_path}})"
    echo "==> Starting headful login on server (window appears on YOUR Mac)..."
    ssh -Y {{PROD_HOST}} "cd {{PROD_DIR}} && export PATH=\"\$HOME/.local/bin:\$PATH\" && uv run python scripts/publish_tiktok.py $REMOTE_VIDEO --description '{{description}}' --schedule-in {{schedule_in}}"

# Daily-cron-style publish on the server. No display needed:
# Xvfb provides a virtual screen for headful Chromium. Assumes the
# session was already bootstrapped (see prod-tiktok-bootstrap-vnc).
#
# Auto-pulls the run history + reflected lessons back to the local
# .storage/ dir at the end so you can inspect what the agent did.
#
# Usage:
#   just prod-tiktok-publish output/part1.mp4
#   just prod-tiktok-publish output/part1.mp4 "--schedule-in 6h --hashtag fyp"
prod-tiktok-publish video_path="output/part1.mp4" extra_args="--schedule-in 30m --description 'Test xvfb run'":
    #!/usr/bin/env bash
    set -euo pipefail
    echo "==> Syncing {{video_path}} to server..."
    rsync -avz --progress {{video_path}} {{PROD_HOST}}:{{PROD_DIR}}/output/
    REMOTE_VIDEO="output/$(basename {{video_path}})"
    echo "==> Running xvfb-run + publisher on server..."
    ssh -t {{PROD_HOST}} "cd {{PROD_DIR}} && export PATH=\"\$HOME/.local/bin:\$PATH\" && mkdir -p .storage/tiktok_runs && RUN_LOG=.storage/tiktok_runs/\$(date -u +%Y%m%dT%H%M%S)-publish.log && OPENAI_LOG=debug LITELLM_LOG=DEBUG xvfb-run -a --server-args='-screen 0 1920x1080x24' uv run python scripts/publish_tiktok.py $REMOTE_VIDEO {{extra_args}} 2>&1 | tee \$RUN_LOG"
    just sync-tiktok-runs

# Inspect the persisted TikTok session on the server.
prod-tiktok-status:
    ssh {{PROD_HOST}} 'cd {{PROD_DIR}} && ls -la .storage/tiktok_cookies* 2>&1 || echo "no session yet"'

# Wipe the persisted TikTok session on the server (forces re-login).
prod-tiktok-reset:
    ssh {{PROD_HOST}} 'cd {{PROD_DIR}} && rm -rf .storage/tiktok_cookies_userdata .storage/tiktok_cookies.json && echo "session wiped"'

# Pull the latest agent run histories + accumulated lessons from prod.
# Safe to run any time; one-way (server -> local). Excludes cookies
# and the user_data_dir so we never overwrite the server's device
# fingerprint with a Mac one.
sync-tiktok-runs:
    @mkdir -p .storage/tiktok_runs
    rsync -avz --delete-after \
        {{PROD_HOST}}:{{PROD_DIR}}/.storage/tiktok_runs/ \
        ./.storage/tiktok_runs/ 2>/dev/null || echo "(no remote runs yet)"
    rsync -avz \
        {{PROD_HOST}}:{{PROD_DIR}}/.storage/tiktok_learnings.md \
        ./.storage/tiktok_learnings.md 2>/dev/null || echo "(no remote lessons yet)"
    @echo "==> $(ls .storage/tiktok_runs 2>/dev/null | wc -l | tr -d ' ') runs cached locally"
    @echo "==> Latest:  $(ls -t .storage/tiktok_runs 2>/dev/null | head -1)"
    @echo "==> Lessons: $(wc -l < .storage/tiktok_learnings.md 2>/dev/null || echo 0) lines"

# Push manually-edited lessons back to prod (after pruning bad ones, etc).
push-tiktok-learnings:
    @test -f .storage/tiktok_learnings.md || (echo "no local lessons file" && exit 1)
    rsync -avz ./.storage/tiktok_learnings.md \
        {{PROD_HOST}}:{{PROD_DIR}}/.storage/tiktok_learnings.md
    @echo "==> pushed $(wc -l < .storage/tiktok_learnings.md) lines"

# Show the most-recent run trace (auto-syncs first). Prefers the
# human-readable .md trace over the raw .json.
tiktok-last:
    @just sync-tiktok-runs >/dev/null
    @latest_md=$(ls -t .storage/tiktok_runs/*.md 2>/dev/null | head -1); \
     latest_json=$(ls -t .storage/tiktok_runs/*.json 2>/dev/null | head -1); \
     if [ -n "$latest_md" ]; then echo "==> $latest_md"; cat "$latest_md"; \
     elif [ -n "$latest_json" ]; then echo "==> $latest_json"; cat "$latest_json"; \
     else echo "(no runs)"; fi

# Show the accumulated lessons file (auto-syncs first).
tiktok-lessons:
    @just sync-tiktok-runs >/dev/null
    @cat .storage/tiktok_learnings.md 2>/dev/null || echo "(no lessons yet)"
