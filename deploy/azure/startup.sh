#!/usr/bin/env bash
set -euo pipefail

export HELP_APP_DATA_DIR="${HELP_APP_DATA_DIR:-/home/data/trazop-pruebas}"
mkdir -p "${HELP_APP_DATA_DIR}"

exec gunicorn \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 1 \
  --threads 4 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  wsgi:app
