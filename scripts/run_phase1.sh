#!/usr/bin/env bash
# Faz 1 hattını uçtan uca çalıştırır: kaynak kontrolü -> indirme -> doğrulama -> kayıt
# -> Parquet -> EDA -> defter -> testler. Depo kökünden çalıştırın.
# Mevcut tam bir anlık görüntü varsa indirme atlanır (SKIP_DOWNLOAD=0 ile zorlanabilir).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -x backend/.venv/Scripts/python.exe ]; then BIN=backend/.venv/Scripts; else BIN=backend/.venv/bin; fi
PY="$BIN/python"
SR="$BIN/saferoute"
export PYTHONIOENCODING=utf-8

"$SR" check-source || echo "UYARI: kaynak erişilemedi; mevcut anlık görüntüyle devam ediliyor."

if [ "${SKIP_DOWNLOAD:-auto}" = "0" ] || ! ls data/raw/h9gi-nx95/snapshot_*/manifest.json >/dev/null 2>&1; then
  "$SR" download
fi

"$SR" verify
"$SR" record
"$SR" parquet
"$SR" eda
"$PY" scripts/execute_notebook.py notebooks/01_dataset_exploration.ipynb
(cd backend && ".venv/${BIN#backend/.venv/}/python" -m pytest -q)
