#!/usr/bin/env bash
# Faz 3 kümeleme hattını çalıştırır: cluster (kayıtlı deneyler yeniden çalıştırılmaz) -> defter -> testler.
# Depo kökünden çalıştırın.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -x backend/.venv/Scripts/python.exe ]; then BIN=backend/.venv/Scripts; else BIN=backend/.venv/bin; fi
export PYTHONIOENCODING=utf-8

"$BIN/saferoute" cluster
"$BIN/python" scripts/execute_notebook.py notebooks/03_clustering_experiments.ipynb
(cd backend && "../$BIN/python" -m pytest -q)
