"""Proje genelindeki sabitler ve dizin yolları."""

from __future__ import annotations

import os
from pathlib import Path

# backend/src/saferoute/config.py -> depo kökü
REPO_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = Path(os.environ.get("SAFEROUTE_DATA_DIR", REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
METADATA_DIR = DATA_DIR / "metadata"  # küçük JSON kayıtları; git'te izlenir
REPORTS_DIR = REPO_ROOT / "reports"
DOCS_DIR = REPO_ROOT / "docs"

# Resmi kaynak: NYC Open Data — Motor Vehicle Collisions - Crashes
DATASET_ID = "h9gi-nx95"
DATASET_DOMAIN = "data.cityofnewyork.us"
DATASET_PAGE_URL = f"https://{DATASET_DOMAIN}/d/{DATASET_ID}"
CATALOG_URL = "https://catalog.data.gov/dataset/motor-vehicle-collisions-crashes"
METADATA_URL = f"https://{DATASET_DOMAIN}/api/views/{DATASET_ID}.json"
RESOURCE_CSV_URL = f"https://{DATASET_DOMAIN}/resource/{DATASET_ID}.csv"
RESOURCE_JSON_URL = f"https://{DATASET_DOMAIN}/resource/{DATASET_ID}.json"

# İsteğe bağlı Socrata uygulama anahtarı (yalnızca ortam değişkeninden okunur, depoya yazılmaz)
SODA_APP_TOKEN_ENV = "SODA_APP_TOKEN"

# NYC beş ilçesini kapsayan yaklaşık sınırlayıcı kutu (WGS84).
# Faz 1'de yalnızca kaba bir geçerlilik kontrolüdür; ilçe poligonlarıyla
# geometrik doğrulama sonraki fazlarda yapılır.
NYC_BBOX = {
    "min_lat": 40.4774,
    "max_lat": 40.9176,
    "min_lon": -74.2591,
    "max_lon": -73.7004,
}

BOROUGHS = ("MANHATTAN", "BROOKLYN", "QUEENS", "BRONX", "STATEN ISLAND")

# Gelecekteki geometrik ilçe zenginleştirmesi için güvenilir sınır kaynağı (Faz 2'de kullanılacak).
# NYC Department of City Planning — Borough Boundaries (su alanları hariç).
BOROUGH_BOUNDARIES_DATASET_ID = "gthc-hcne"
BOROUGH_BOUNDARIES_METADATA_URL = f"https://{DATASET_DOMAIN}/api/views/{BOROUGH_BOUNDARIES_DATASET_ID}.json"

# Yayıncının beyan ettiği sıklığa göre "güncel değil" sayılma eşiği (gün).
STALENESS_THRESHOLD_DAYS = {"Daily": 3, "Weekly": 14, "Monthly": 45}
