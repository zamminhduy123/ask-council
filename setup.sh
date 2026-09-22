#!/usr/bin/env bash
# Ask-Council one-command setup: venv + deps + Chrome detect + .env scaffold.
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found (need 3.10+)." >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "→ creating .venv"
  python3 -m venv .venv
fi
.venv/bin/pip install -U pip >/dev/null
echo "→ installing requirements"
.venv/bin/pip install -r requirements.txt

# Chrome detection (informational; drivers also auto-detect at runtime)
FOUND=""
if [ -n "${BROWSER_PATH:-}" ] && [ -f "$BROWSER_PATH" ]; then
  FOUND="$BROWSER_PATH (from env)"
elif [ -f "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
  FOUND="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
elif command -v google-chrome >/dev/null 2>&1; then
  FOUND="$(command -v google-chrome)"
elif command -v chromium >/dev/null 2>&1; then
  FOUND="$(command -v chromium)"
elif [ -f .browsers/chrome-linux64/chrome ]; then
  FOUND=".browsers/chrome-linux64/chrome"
fi
if [ -n "$FOUND" ]; then
  echo "→ Chrome found: $FOUND"
else
  echo "WARN: no Chrome found. Set BROWSER_PATH or install Google Chrome." >&2
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "→ created .env from .env.example (fill tokens next)"
else
  echo "→ .env exists, leaving untouched"
fi

echo ""
echo "Next:"
echo "  1. Fill .env (see README token table)"
echo "  2. source .venv/bin/activate"
echo "  3. python pipeline/ask_council.py --check"
echo "  4. python pipeline/ask_council.py \"Your question\" --out opinions.md"
