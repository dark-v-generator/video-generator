#!/usr/bin/env bash
# Server-side helper invoked by `just prod-tiktok-bootstrap-vnc`.
#
# Starts Xvfb on display :99, exposes it via x11vnc bound to localhost
# (so it's only reachable through the SSH tunnel that the just target
# opens), then runs the TikTok publisher against that display so you
# can drag the captcha slider over VNC.
#
# Tears Xvfb + x11vnc down on exit.
#
# Forwards all arguments to scripts/publish_tiktok.py.

set -uo pipefail

cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"

DISPLAY_NUM="${DISPLAY_NUM:-99}"
VNC_LOG="/tmp/x11vnc-${DISPLAY_NUM}.log"
XVFB_LOG="/tmp/xvfb-${DISPLAY_NUM}.log"

XVFB_PID=""
X11VNC_PID=""

cleanup() {
  echo ""
  echo "==> Tearing down VNC + Xvfb..."
  if [[ -n "$X11VNC_PID" ]]; then
    kill "$X11VNC_PID" 2>/dev/null || true
  fi
  if [[ -n "$XVFB_PID" ]]; then
    kill "$XVFB_PID" 2>/dev/null || true
  fi
  # pgrep + kill is safer than pkill -f because it can't match the
  # current shell's own command line and kill the parent.
  pgrep -x x11vnc 2>/dev/null | xargs -r kill 2>/dev/null || true
  pgrep -f "^Xvfb :${DISPLAY_NUM}" 2>/dev/null | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if ! command -v Xvfb >/dev/null 2>&1; then
  echo "ERROR: Xvfb not installed. Run: just prod-tiktok-setup" >&2
  exit 1
fi

if ! command -v x11vnc >/dev/null 2>&1; then
  echo "ERROR: x11vnc not installed. Run: just prod-tiktok-setup" >&2
  exit 1
fi

# Clean up any stragglers from a previous botched run before we start
pgrep -x x11vnc 2>/dev/null | xargs -r kill 2>/dev/null || true
pgrep -f "^Xvfb :${DISPLAY_NUM}" 2>/dev/null | xargs -r kill 2>/dev/null || true
sleep 1

echo "==> Starting Xvfb :${DISPLAY_NUM} (1920x1080x24)..."
Xvfb ":${DISPLAY_NUM}" -screen 0 1920x1080x24 -nolisten tcp >"$XVFB_LOG" 2>&1 &
XVFB_PID=$!
sleep 2

if ! kill -0 "$XVFB_PID" 2>/dev/null; then
  echo "ERROR: Xvfb failed to start (see $XVFB_LOG)" >&2
  exit 1
fi

# macOS Screen Sharing refuses the "no auth" RFB security type, so we
# always set a per-session VNC password. The connection is already
# locked behind the SSH tunnel + -localhost, so the password is just
# protocol theatre — it changes every run and disappears on exit.
VNC_PASS=$(head -c 9 /dev/urandom | base64 | tr -d '+/=\n' | cut -c1-8)

echo "==> Starting x11vnc bound to localhost..."
x11vnc -display ":${DISPLAY_NUM}" \
       -localhost \
       -passwd "$VNC_PASS" \
       -forever \
       -shared \
       -quiet \
       -o "$VNC_LOG" \
       >/dev/null 2>&1 &
X11VNC_PID=$!
sleep 2

if ! kill -0 "$X11VNC_PID" 2>/dev/null; then
  echo "ERROR: x11vnc failed to start (see $VNC_LOG)" >&2
  exit 1
fi

echo ""
echo "=================================================================="
echo "==> VNC READY"
echo "==> URL:      vnc://localhost:5900"
echo "==> Password: ${VNC_PASS}"
echo "==> macOS:    Finder -> Cmd+K, paste URL, then paste password"
echo "==> Drag the captcha slider when it appears (agent waits ~2 min)."
echo "=================================================================="
echo ""

DISPLAY=":${DISPLAY_NUM}" uv run python scripts/publish_tiktok.py "$@"
