#!/usr/bin/env bash
# Ajaa analysaattorin. Jos .env.op löytyy, 1Password CLI injektoi avaimet
# ympäristömuuttujiksi vain tälle prosessille (op run peittää ne myös tulosteesta).
# Käyttö: ./analyze.sh peli.pgn --player tonhin --online --md
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
if [[ -f .env.op ]] && command -v op >/dev/null 2>&1; then
  exec op run --env-file=.env.op -- "$PY" -m app.analyzer "$@"
fi
exec "$PY" -m app.analyzer "$@"
