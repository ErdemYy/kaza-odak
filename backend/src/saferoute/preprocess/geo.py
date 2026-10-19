"""Coğrafi doğrulama ve resmî poligonlarla ilçe çıkarımı.

Koordinat kalite durumu (birbirini dışlayan, öncelik sırasıyla):
  missing              enlem veya boylam boş
  unparseable          sayıya çevrilemiyor
  non_finite           inf / nan metni
  zero                 enlem veya boylam tam 0 ("konum bilinmiyor" yer tutucusu)
  invalid_range        |enlem| > 90 veya |boylam| > 180
  outside_nyc_far      hiçbir ilçe poligonunda değil ve en yakın NYC karasına > tampon
  outside_nyc_nearshore hiçbir poligonda değil ama tampon içinde (köprü, kıyı, su üstü sapma)
  boundary_ambiguous   birden fazla ilçe poligonuyla kesişiyor (ortak sınır çizgisi üstünde)
  valid_in_boundary    tam olarak bir ilçe poligonunun içinde veya sınırında (covered_by)

İlçe çıkarımı yalnızca ``valid_in_boundary`` noktalar için yapılır. Poligon dışındaki
noktalar (kıyıya yakın olsalar bile) hiçbir ilçeye ATANMAZ; belirsiz sınır noktaları da
atanmaz.

Performans: işlem benzersiz (enlem, boylam) çiftleri üzerinde yapılır ve sonuç satırlara
yayılır; ilçe testi hazırlanmış (prepared) poligonlarla vektörel ``contains_xy`` /
``intersects_xy`` kullanır (ikili uzaklık matrisi kurulmaz).
"""

from __future__ import annotations

from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from saferoute.preprocess.boundaries import assert_geographic_nyc, ensure_same_crs
from saferoute.preprocess.settings import PreprocessConfig

COORD_STATUSES = (
    "missing", "unparseable", "non_finite", "zero", "invalid_range",
    "outside_nyc_far", "outside_nyc_nearshore", "boundary_ambiguous", "valid_in_boundary",
)
VALID_GEOGRAPHIC = ("valid_in_boundary", "boundary_ambiguous", "outside_nyc_nearshore")


def _unique_points(lat: np.ndarray, lon: np.ndarray, mask: np.ndarray) -> tuple[pd.DataFrame, np.ndarray]:
    """Maskeli satırların benzersiz (lat, lon) tablosu ve her satırın tablo indeksi (-1 = yok)."""
    pairs = np.column_stack([lat[mask], lon[mask]])
    if len(pairs) == 0:
        return pd.DataFrame({"lat": [], "lon": []}, dtype="float64"), np.full(len(lat), -1, dtype=np.int64)
    uniques, codes = np.unique(pairs, axis=0, return_inverse=True)  # sıralı -> deterministik
    table = pd.DataFrame(uniques, columns=["lat", "lon"])
    row_index = np.full(len(lat), -1, dtype=np.int64)
    row_index[mask] = codes.ravel()
    return table, row_index


def locate_points(lat: np.ndarray, lon: np.ndarray, boroughs: gpd.GeoDataFrame,
                  cfg: PreprocessConfig) -> pd.DataFrame:
    """Benzersiz noktalar için ilçe ilişkilerini ve kıyı mesafesini hesaplar.

    Dönen sütunlar: ``n_intersects`` (sınır dahil kesişen ilçe sayısı), ``n_contains``
    (yalnız iç), ``borough`` (tek ilçe varsa), ``on_boundary_line``, ``distance_to_nyc_m``.
    """
    assert_geographic_nyc(boroughs, cfg.geographic_crs)
    points = gpd.GeoSeries(gpd.points_from_xy(lon, lat), crs=cfg.geographic_crs)  # x=boylam, y=enlem
    ensure_same_crs(points, boroughs)
    n = len(lat)
    n_intersects = np.zeros(n, dtype=np.int8)
    n_contains = np.zeros(n, dtype=np.int8)
    borough = np.full(n, None, dtype=object)
    for geom, name in zip(boroughs.geometry.values, boroughs["borough"]):
        shapely.prepare(geom)
        inter = shapely.intersects_xy(geom, lon, lat)
        cont = shapely.contains_xy(geom, lon, lat)
        n_intersects += inter
        n_contains += cont
        borough[inter] = np.where(borough[inter] == None, name, "__MULTI__")  # noqa: E711
    borough[n_intersects != 1] = None
    distance = np.zeros(n, dtype="float64")
    outside = n_intersects == 0
    if outside.any():
        land = shapely.union_all(boroughs.to_crs(cfg.projected_crs).geometry.values)
        shapely.prepare(land)
        pts = points[outside].to_crs(cfg.projected_crs).values
        distance[outside] = shapely.distance(land, pts)
    return pd.DataFrame({
        "n_intersects": n_intersects,
        "n_contains": n_contains,
        "borough": borough,
        "on_boundary_line": (n_intersects > 0) & (n_contains < n_intersects),
        "distance_to_nyc_m": distance,
    })


def conflict_analysis(df: pd.DataFrame, boroughs: gpd.GeoDataFrame, cfg: PreprocessConfig,
                      top_n: int = 15) -> dict[str, Any]:
    """İlçe çelişkisi olan kayıtların, BİLDİRİLEN ilçe poligonuna uzaklığı ve en sık konumları.

    Uzaklık küçükse çelişki büyük olasılıkla sınır yakınındaki kodlamadan; büyükse
    bildirilen ilçe etiketinin kendisinden (ör. idari/coğrafi ayrışma) kaynaklanır.
    """
    c = df[df["borough_conflict_flag"]]
    if c.empty:
        return {"count": 0}
    proj = boroughs.to_crs(cfg.projected_crs).set_index("borough").geometry
    pts = gpd.GeoSeries(gpd.points_from_xy(c["longitude"], c["latitude"]), crs=cfg.geographic_crs,
                        index=c.index).to_crs(cfg.projected_crs)
    dist = np.array([proj[b].distance(p) for b, p in zip(c["borough_original"], pts.values)])
    q = np.quantile(dist, [0.5, 0.9, 0.99])
    top = (c.assign(d=dist).groupby(["latitude", "longitude", "borough_original", "borough_inferred"], observed=True)
           .agg(records=("d", "size"), distance_m=("d", "first"),
                on_street=("on_street_name", lambda s: s.mode().iloc[0] if not s.dropna().empty else None),
                off_street=("off_street_name", lambda s: s.mode().iloc[0] if not s.dropna().empty else None))
           .reset_index().sort_values("records", ascending=False).head(top_n))
    return {
        "count": int(len(c)),
        "distance_to_reported_borough_m": {"p50": float(q[0]), "p90": float(q[1]), "p99": float(q[2]),
                                           "max": float(dist.max())},
        "within_m": {str(t): int((dist <= t).sum()) for t in (10, 50, 100, 250, 500, 1000)},
        "top_locations": [
            {k: (None if (isinstance(v, float) and np.isnan(v)) else (float(v) if isinstance(v, (np.floating,)) else
                 int(v) if isinstance(v, (np.integer,)) else v)) for k, v in row.items()}
            for row in top.to_dict(orient="records")
        ],
    }


def classify_coordinates(df: pd.DataFrame, boroughs: gpd.GeoDataFrame,
                         cfg: PreprocessConfig) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Her satır için koordinat kalite durumu, ilçe çıkarımı ve uygunluk bayrakları üretir.

    Girdi: interim DataFrame (``latitude``, ``longitude``, ``coord_parse_status``,
    ``borough_original``, ``crash_date``). Girdi değiştirilmez; yeni sütunlar döner.
    """
    lat = df["latitude"].to_numpy(dtype="float64")
    lon = df["longitude"].to_numpy(dtype="float64")
    parse = df["coord_parse_status"].astype(str).to_numpy()
    status = np.where(parse == "parsed", "", parse).astype(object)

    parsed = status == ""
    zero = parsed & ((lat == 0) | (lon == 0))
    status[zero] = "zero"
    bad_range = parsed & ~zero & ((np.abs(lat) > 90) | (np.abs(lon) > 180))
    status[bad_range] = "invalid_range"
    candidate = status == ""

    table, idx = _unique_points(lat, lon, candidate)
    located = locate_points(table["lat"].to_numpy(), table["lon"].to_numpy(), boroughs, cfg)
    take = np.where(idx >= 0, idx, 0)
    n_inter = np.where(candidate, located["n_intersects"].to_numpy()[take], 0)
    dist = np.where(candidate, located["distance_to_nyc_m"].to_numpy()[take], np.nan)
    inferred = np.where(candidate, located["borough"].to_numpy()[take], None)
    on_line = np.where(candidate, located["on_boundary_line"].to_numpy()[take], False)

    status[candidate & (n_inter == 1)] = "valid_in_boundary"
    status[candidate & (n_inter >= 2)] = "boundary_ambiguous"
    outside = candidate & (n_inter == 0)
    status[outside & (dist <= cfg.nearshore_buffer_m)] = "outside_nyc_nearshore"
    status[outside & (dist > cfg.nearshore_buffer_m)] = "outside_nyc_far"
    assert not (status == "").any(), "her satır bir koordinat durumuna atanmalı"

    out = pd.DataFrame(index=df.index)
    out["coordinate_quality_status"] = pd.Categorical(status, categories=COORD_STATUSES)
    out["on_boundary_line"] = on_line.astype(bool)
    out["distance_outside_nyc_m"] = np.where(outside, dist, np.nan)
    out["is_valid_geographic_record"] = np.isin(status, VALID_GEOGRAPHIC)
    eligible_status = VALID_GEOGRAPHIC if cfg.clustering_include_nearshore else VALID_GEOGRAPHIC[:2]
    out["eligible_for_spatial_clustering"] = np.isin(status, eligible_status) & df["crash_date"].notna().to_numpy()
    out["exclusion_reason"] = pd.Categorical(
        np.where(out["eligible_for_spatial_clustering"], "none",
                 np.where(df["crash_date"].isna().to_numpy() & np.isin(status, eligible_status),
                          "invalid_crash_date", status)),
    )

    # İlçe alanları
    original = df["borough_original"].astype(object).where(df["borough_original"].notna(), None).to_numpy()
    inferred = inferred.astype(object)
    has_orig = pd.notna(original)
    has_inf = pd.notna(inferred)
    final = np.where(has_orig, original, np.where(has_inf, inferred, None))
    source = np.where(has_orig, "original", np.where(has_inf, "inferred_polygon", "none"))
    conflict = has_orig & has_inf & (original != inferred)
    inference_status = np.where(status == "valid_in_boundary", "inferred",
                        np.where(status == "boundary_ambiguous", "ambiguous_boundary",
                        np.where(np.isin(status, ("outside_nyc_far", "outside_nyc_nearshore")), "outside_polygons",
                                 "no_valid_coordinate")))
    out["borough_inferred"] = pd.array(inferred, dtype="string")
    out["borough_final"] = pd.array(final, dtype="string")
    out["borough_source"] = pd.Categorical(source, categories=["original", "inferred_polygon", "none"])
    out["borough_conflict_flag"] = conflict.astype(bool)
    out["borough_inference_status"] = pd.Categorical(
        inference_status, categories=["inferred", "ambiguous_boundary", "outside_polygons", "no_valid_coordinate"])

    stats = {
        "unique_candidate_points": int(len(table)),
        "predicate_comparison_unique_points": {
            "intersects_or_covered_by_any": int((located["n_intersects"] > 0).sum()),
            "contains_strict_interior_any": int((located["n_contains"] > 0).sum()),
            "on_boundary_line": int(located["on_boundary_line"].sum()),
            "multiple_boroughs": int((located["n_intersects"] > 1).sum()),
        },
    }
    return out, stats
