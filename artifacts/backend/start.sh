#!/bin/bash
set -e

cd "$(dirname "$0")"

# Convert DATABASE_URL to asyncpg format for both alembic and uvicorn
if [[ "$DATABASE_URL" == postgresql://* ]] || [[ "$DATABASE_URL" == postgres://* ]]; then
  export DATABASE_URL=$(echo "$DATABASE_URL" | sed 's|^postgresql://|postgresql+asyncpg://|' | sed 's|^postgres://|postgresql+asyncpg://|' | sed 's|?sslmode=.*||')
fi

export SECRET_KEY="${PYTHON_BACKEND_SECRET_KEY:-$(python3 -c 'import secrets; print(secrets.token_hex(32))')}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

# Run Alembic migrations before starting (DATABASE_URL is now asyncpg format)
echo "🔄  Running database migrations..."
python3 -m alembic upgrade head
echo "✅  Migrations complete."

exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
