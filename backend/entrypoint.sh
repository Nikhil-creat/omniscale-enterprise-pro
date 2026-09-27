#!/usr/bin/env bash
# OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
#
# Deploy-time automation: waits for Postgres to accept connections, applies
# any pending Alembic migrations automatically, then hands off to the real
# command (uvicorn). Without this, a fresh container boots against a schema
# that doesn't exist yet, or a rolling deploy can serve traffic against an
# out-of-date schema.
set -euo pipefail

echo "[entrypoint] waiting for postgres..."
python - <<'PYEOF'
import sys
import time
import psycopg2
import os

url = os.environ.get("DATABASE_URL", "").replace("postgresql+asyncpg", "postgresql")
for attempt in range(30):
    try:
        conn = psycopg2.connect(url)
        conn.close()
        print("[entrypoint] postgres is ready")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"[entrypoint] postgres not ready yet ({attempt + 1}/30): {exc}")
        time.sleep(2)
print("[entrypoint] postgres never became ready — exiting")
sys.exit(1)
PYEOF

echo "[entrypoint] applying database migrations..."
alembic upgrade head

echo "[entrypoint] starting: $*"
exec "$@"
