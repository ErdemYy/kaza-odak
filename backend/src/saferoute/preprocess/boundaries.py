"""Resmî NYC ilçe sınırları (DCP Borough Boundaries, ``gthc-hcne``): indirme, doğrulama, yükleme.

İndirilen GeoJSON, ham kaza verisiyle aynı ilkelerle saklanır: zaman damgalı anlık
görüntü dizini, SHA-256'lı manifest, salt-okunur dosyalar.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import requests
import shapely
from pyproj import CRS

from saferoute import config
from saferoute.data.source import make_session

BOUNDARY_GEOJSON_URL = f"https://{config.DATASET_DOMAIN}/resource/{config.BOROUGH_BOUNDARIES_DATASET_ID}.geojson"
GEOJSON_NAME = "borough_boundaries.geojson"
MANIFEST_NAME = "manifest.json"
EXPECTED_BOROUGHS = {"1": "MANHATTAN", "2": "BRONX", "3": "BROOKLYN", "4": "QUEENS", "5": "STATEN ISLAND"}
# NYC'yi kapsayan makul coğrafi aralık (derece). Bu aralığın dışındaki sınırlar yanlış CRS'e işaret eder.
NYC_PLAUSIBLE_BOUNDS = (-74.4, 40.4, -73.6, 41.0)


class BoundaryValidationError(ValueError):
    """Sınır verisi beklenen yapıda değilse fırlatılır."""


class CRSMismatchError(ValueError):
    """Koordinat referans sistemleri uyuşmuyor veya beklenmiyorsa fırlatılır."""


def _utc(ts: Any) -> str | None:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat() if ts else None


def assert_geographic_nyc(gdf: gpd.GeoDataFrame, expected_crs: str = "EPSG:4326") -> None:
    """GeoDataFrame'in beklenen coğrafi CRS'te ve NYC civarında olduğunu doğrular.

    CRS tanımsızsa, farklıysa veya koordinatlar derece aralığında değilse (ör. veri
    aslında projeksiyonlu metre/fit değerleri içeriyorsa) ``CRSMismatchError`` fırlatır.
    """
    if gdf.crs is None:
        raise CRSMismatchError("CRS tanımsız; eşleştirme yapılamaz.")
    if not CRS(gdf.crs).equals(CRS(expected_crs)):
        raise CRSMismatchError(f"Beklenen CRS {expected_crs}, bulunan {gdf.crs.to_string()}")
    minx, miny, maxx, maxy = gdf.total_bounds
    bx0, by0, bx1, by1 = NYC_PLAUSIBLE_BOUNDS
    if not (bx0 <= minx and maxx <= bx1 and by0 <= miny and maxy <= by1):
        raise CRSMismatchError(
            f"Sınırlar NYC derece aralığında değil: {gdf.total_bounds.tolist()} — CRS etiketi hatalı olabilir."
        )


def ensure_same_crs(a: gpd.GeoDataFrame | gpd.GeoSeries, b: gpd.GeoDataFrame | gpd.GeoSeries) -> None:
    """İki geometri kümesinin CRS'leri aynı değilse eşleştirmeyi engeller."""
    if a.crs is None or b.crs is None or not CRS(a.crs).equals(CRS(b.crs)):
        raise CRSMismatchError(f"CRS uyuşmazlığı: {a.crs} ve {b.crs}")


def validate_boundaries(gdf: gpd.GeoDataFrame) -> dict[str, Any]:
    """5 ilçe, MultiPolygon/Polygon türü, CRS, geometri geçerliliği ve kapsam kontrolleri."""
    assert_geographic_nyc(gdf)
    codes = sorted(str(int(float(c))) for c in gdf["borocode"])
    if codes != sorted(EXPECTED_BOROUGHS):
        raise BoundaryValidationError(f"Beklenen ilçe kodları {sorted(EXPECTED_BOROUGHS)}, bulunan {codes}")
    names = {str(int(float(c))): str(n).upper() for c, n in zip(gdf["borocode"], gdf["borough"])}
    if names != EXPECTED_BOROUGHS:
        raise BoundaryValidationError(f"İlçe adları beklenenle uyuşmuyor: {names}")
    types = sorted(set(gdf.geom_type))
    if not set(types) <= {"MultiPolygon", "Polygon"}:
        raise BoundaryValidationError(f"Beklenmeyen geometri türleri: {types}")
    valid = shapely.is_valid(gdf.geometry.values)
    reasons = [shapely.is_valid_reason(g) for g, ok in zip(gdf.geometry.values, valid) if not ok]
    if not valid.all():
        raise BoundaryValidationError(f"Geçersiz geometri: {reasons}")
    projected = gdf.to_crs("EPSG:32618")
    pairwise = []
    geoms = list(projected.geometry)
    for i in range(len(geoms)):
        for j in range(i + 1, len(geoms)):
            pairwise.append(shapely.intersection(geoms[i], geoms[j]).area)
    return {
        "borough_count": int(len(gdf)),
        "borough_codes": names,
        "geometry_types": types,
        "crs": gdf.crs.to_string(),
        "all_valid": True,
        "empty_geometries": int(shapely.is_empty(gdf.geometry.values).sum()),
        "total_bounds": [float(v) for v in gdf.total_bounds],
        "area_km2_epsg32618": {names[str(int(float(c)))]: round(a / 1e6, 3)
                               for c, a in zip(gdf["borocode"], projected.geometry.area)},
        "max_pairwise_overlap_m2": float(max(pairwise) if pairwise else 0.0),
        "polygon_parts": int(sum(len(getattr(g, "geoms", [g])) for g in gdf.geometry)),
    }


def load_boundaries(path: Path) -> gpd.GeoDataFrame:
    """GeoJSON'u okur, ilçe adlarını kaza verisindeki yazımla (büyük harf) eşler."""
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        raise CRSMismatchError("GeoJSON CRS içermiyor.")
    # OGC CRS84 (boylam, enlem) ile EPSG:4326 aynı datumdur; eksen sırası shapely'de x=boylam.
    if CRS(gdf.crs).equals(CRS("OGC:CRS84")):
        gdf = gdf.set_crs("EPSG:4326", allow_override=True)
    gdf["borough"] = gdf["boroname"].str.upper()
    gdf["borocode"] = gdf["borocode"].astype(float).astype(int).astype(str)
    return gdf[["borocode", "borough", "geometry"]].sort_values("borocode").reset_index(drop=True)


def latest_boundaries(raw_root: Path | None = None) -> Path:
    base = Path(raw_root or config.RAW_DIR) / config.BOROUGH_BOUNDARIES_DATASET_ID
    found = sorted(p.parent for p in base.glob(f"snapshot_*/{MANIFEST_NAME}"))
    if not found:
        raise FileNotFoundError(f"{base} altında ilçe sınırı anlık görüntüsü yok. 'saferoute boundaries' çalıştırın.")
    return found[-1]


def download_boundaries(out_root: Path | None = None, session: requests.Session | None = None,
                        timeout: float = 120) -> Path:
    """Resmî ilçe sınırlarını indirir, doğrular, manifestle birlikte salt-okunur saklar."""
    session = session or make_session()
    meta_resp = session.get(config.BOROUGH_BOUNDARIES_METADATA_URL, timeout=timeout)
    meta_resp.raise_for_status()
    meta = meta_resp.json()
    resp = session.get(BOUNDARY_GEOJSON_URL, timeout=timeout)
    resp.raise_for_status()
    body = resp.content

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snap = Path(out_root or config.RAW_DIR) / config.BOROUGH_BOUNDARIES_DATASET_ID / f"snapshot_{stamp}"
    snap.mkdir(parents=True, exist_ok=False)
    path = snap / GEOJSON_NAME
    path.write_bytes(body)

    declared_crs = (json.loads(body).get("crs") or {}).get("properties", {}).get("name")
    gdf = load_boundaries(path)
    checks = validate_boundaries(gdf)
    description = meta.get("description") or ""
    version = re.search(r"Current version:\s*([0-9A-Za-z.]+)", description)
    custom = (meta.get("metadata") or {}).get("custom_fields") or {}
    manifest = {
        "dataset_id": config.BOROUGH_BOUNDARIES_DATASET_ID,
        "dataset_name": meta.get("name"),
        "publisher": meta.get("attribution"),
        "source_page_url": f"https://{config.DATASET_DOMAIN}/City-Government/Borough-Boundaries/{config.BOROUGH_BOUNDARIES_DATASET_ID}",
        "download_url": BOUNDARY_GEOJSON_URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_version": version.group(1) if version else None,
        "description": description,
        "publication_date": _utc(meta.get("publicationDate")),
        "rows_updated_at": _utc(meta.get("rowsUpdatedAt")),
        "view_last_modified": _utc(meta.get("viewLastModified")),
        "truth_last_modified": resp.headers.get("X-SODA2-Truth-Last-Modified"),
        "update_frequency": (custom.get("Update") or {}).get("Update Frequency"),
        "license": (meta.get("license") or {}).get("name"),
        "declared_crs": declared_crs,
        "file": GEOJSON_NAME,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "validation": checks,
    }
    (snap / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    for p in (path, snap / MANIFEST_NAME):
        os.chmod(p, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    return snap


def read_boundaries_snapshot(snapshot_dir: Path) -> tuple[gpd.GeoDataFrame, dict[str, Any]]:
    """Anlık görüntüyü SHA-256 doğrulamasıyla yükler."""
    snapshot_dir = Path(snapshot_dir)
    manifest = json.loads((snapshot_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    body = (snapshot_dir / manifest["file"]).read_bytes()
    if hashlib.sha256(body).hexdigest() != manifest["sha256"]:
        raise BoundaryValidationError("İlçe sınırı dosyasının SHA-256 değeri manifestle uyuşmuyor.")
    gdf = load_boundaries(snapshot_dir / manifest["file"])
    validate_boundaries(gdf)
    return gdf, manifest
