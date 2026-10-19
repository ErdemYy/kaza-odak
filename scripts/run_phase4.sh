#!/usr/bin/env bash
# Faz 4 hattı: katmanlar -> ön yüz derleme -> birim + uçtan uca testler -> arka uç testleri.
# Depo kökünden çalıştırın. Faz 3 çıktıları mevcut olmalıdır; harita karoları için ağ gerekir.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -x backend/.venv/Scripts/python.exe ]; then BIN=backend/.venv/Scripts; else BIN=backend/.venv/bin; fi
export PYTHONIOENCODING=utf-8

"$BIN/saferoute" viz-build
(cd frontend && npm ci && npm run build && npm test && npx playwright install chromium-headless-shell && npm run e2e)
(cd backend && "../$BIN/python" -m pytest -q)
echo "Görüntüleyici: $BIN/saferoute serve  ->  http://127.0.0.1:8000"
