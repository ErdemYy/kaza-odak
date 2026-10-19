#!/usr/bin/env bash
# Faz 2 hattını uçtan uca çalıştırır: ilçe sınırları (yoksa indir) -> preprocess (idempotent)
# -> raporlar -> defter -> testler. Depo kökünden çalıştırın. FORCE=1 ile yeniden üretim zorlanır.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -x backend/.venv/Scripts/python.exe ]; then BIN=backend/.venv/Scripts; else BIN=backend/.venv/bin; fi
export PYTHONIOENCODING=utf-8

if ! ls data/raw/gthc-hcne/snapshot_*/manifest.json >/dev/null 2>&1; then
  "$BIN/saferoute" boundaries
fi
if [ "${FORCE:-0}" = "1" ]; then "$BIN/saferoute" preprocess --force; else "$BIN/saferoute" preprocess; fi
"$BIN/python" scripts/execute_notebook.py notebooks/02_preprocessing_feature_engineering.ipynb
(cd backend && "../$BIN/python" -m pytest -q)
