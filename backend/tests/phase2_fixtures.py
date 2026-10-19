"""Faz 2 testleri için SENTETİK ilçe kareleri ve kayıtlar (yalnızca testlerde kullanılır).

Beş kare, NYC derece aralığı içinde yan yana dizilmiştir; Manhattan–Brooklyn ortak
kenarı boylam -73.98'dedir. Gerçek ilçe sınırlarını TEMSİL ETMEZ.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import MultiPolygon, box

from conftest import make_row
from saferoute.preprocess.boundaries import validate_boundaries

SQUARES = {
    ("1", "MANHATTAN"): (-74.00, 40.70, -73.98, 40.72),
    ("3", "BROOKLYN"): (-73.98, 40.70, -73.96, 40.72),
    ("4", "QUEENS"): (-73.96, 40.70, -73.94, 40.72),
    ("2", "BRONX"): (-73.94, 40.70, -73.92, 40.72),
    ("5", "STATEN ISLAND"): (-74.10, 40.70, -74.08, 40.72),
}


def synthetic_boroughs() -> gpd.GeoDataFrame:
    rows = [{"borocode": c, "borough": n, "geometry": MultiPolygon([box(*b)])} for (c, n), b in SQUARES.items()]
    return gpd.GeoDataFrame(rows, crs="EPSG:4326").sort_values("borocode").reset_index(drop=True)


def write_boundaries_snapshot(root: Path) -> Path:
    snap = root / "gthc-hcne" / "snapshot_20260101T000000Z"
    snap.mkdir(parents=True)
    gdf = synthetic_boroughs().rename(columns={"borough": "boroname"})
    gdf["boroname"] = gdf["boroname"].str.title()
    gdf.to_file(snap / "borough_boundaries.geojson", driver="GeoJSON")
    body = (snap / "borough_boundaries.geojson").read_bytes()
    manifest = {
        "dataset_id": "gthc-hcne", "source_version": "test", "publication_date": None, "rows_updated_at": None,
        "declared_crs": "EPSG:4326", "file": "borough_boundaries.geojson", "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(), "retrieved_at": "2026-01-01T00:00:00+00:00",
        "validation": validate_boundaries(synthetic_boroughs()),
    }
    (snap / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return snap


def d(day: str) -> str:
    return f"{day}T00:00:00.000"


def pipeline_rows() -> list[dict]:
    """Her coğrafi durumu ve ilçe senaryosunu içeren 12 sentetik kayıt."""
    base = dict(crash_date=d("2021-03-01"), crash_time="10:00")
    return [
        make_row(collision_id="1", latitude="40.71", longitude="-73.99", borough="MANHATTAN", **base),   # içeride
        make_row(collision_id="2", latitude="40.71", longitude="-73.99", borough=None, **base),          # tekrar, ilçe kurtarılır
        make_row(collision_id="3", latitude="40.71", longitude="-73.97", borough="QUEENS", **base),      # çelişki (poligon BROOKLYN)
        make_row(collision_id="4", latitude="40.71", longitude="-73.98", borough=None, **base),          # ortak sınır -> belirsiz
        make_row(collision_id="5", latitude="40.699", longitude="-73.99", borough=None, **base),         # ~111 m dışarıda -> kıyı
        make_row(collision_id="6", latitude="40.65", longitude="-73.99", borough="BROOKLYN", **base),    # ~5,5 km -> uzak
        make_row(collision_id="7", latitude="0", longitude="0", borough="BRONX", **base),                # sıfır
        make_row(collision_id="8", latitude=None, longitude=None, borough="QUEENS", **base),             # eksik
        make_row(collision_id="9", latitude="95", longitude="-73.99", **base),                           # geçersiz aralık
        make_row(collision_id="10", latitude="abc", longitude="-73.99", **base),                         # ayrıştırılamaz
        make_row(collision_id="11", latitude="inf", longitude="-73.99", **base),                         # sonlu değil
        make_row(collision_id="12", latitude="40.70", longitude="-73.99", borough="MANHATTAN",
                 crash_date=d("2021-03-07"), crash_time="0:00", vehicle_type_code1="E-Bike",
                 number_of_persons_injured="2", number_of_cyclist_injured="1"),                         # dış kenar, 00:00
    ]
