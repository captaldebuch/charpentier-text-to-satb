#!/bin/sh
# Double-click on macOS, or run from any working directory.
set -eu
cd "$(dirname "$0")"
port="${CHARPENTIER_PORT:-8816}"
echo "Text to Charpentier: http://127.0.0.1:$port/en/text-to-charpentier/"
if [ -z "${CHARPENTIER_PYTHON:-}" ]; then
    for py in python3 python3.11 "$HOME/.pyenv/shims/python3"; do
        if "$py" -c 'import music21, verovio, numpy, uvicorn, fastapi, httpx' 2>/dev/null; then
            CHARPENTIER_PYTHON="$py"
            break
        fi
    done
fi
: "${CHARPENTIER_PYTHON:?Install the Python dependencies listed in README.md or set CHARPENTIER_PYTHON}"
exec "$CHARPENTIER_PYTHON" -m uvicorn app:app --host 127.0.0.1 --port "$port"
