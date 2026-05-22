#!/bin/bash
set -e

cd "$(dirname "$0")"

VENV_DIR="$(pwd)/.venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "📦  Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
  echo "📦  Installing Python dependencies..."
  PIP_CONFIG_FILE=/dev/null "$VENV_DIR/bin/python" -m pip install -r requirements.txt -q
fi

mkdir -p data/chroma data/uploads

echo "🚀  Starting Naseh AI backend on port 9000..."
exec "$VENV_DIR/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 9000
