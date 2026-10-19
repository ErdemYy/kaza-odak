"""Küme profilleri ve görselleştirme geometrileri.

Profiller BETİMLEYİCİDİR: yaralanma/ölüm, araç ve faktör alanları kümeleme girdisi değildir,
yalnızca bulunan kümeleri tanımlar. Bir kümenin çok kayıt içermesi, maruziyet (trafik hacmi,
yaya sayısı) bilinmeden "en yüksek risk" anlamına gelmez.

Geometri: her küme için üye BENZERSİZ konumların dışbükey zarfı (EPSG:32618'de hesaplanıp
WGS84'e dönüştürülür). Bu bir GÖRSELLEŞTİRME sınırıdır; istatistiksel bir yoğunluk konturu veya
güven bölgesi değildir. Tek noktalı/doğrusal kümeler küçük bir tamponla görünür kılınır ve
``geometry_kind`` alanında belirtilir.
"""

from __future__ import annotations

import json
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

PROFILE_COLUMNS = [
    "borough_final", "crash_date", "crash_hour", "time_period", "has_reported_injury", "has_reported_fatality",
    "number_of_persons_injured", "number_of_persons_killed", "vehicle_category_1",
    "contributing_factor_vehicle_1", "on_street_name",
]


def load_profile_columns(processed_path, eligible_only: bool = True) -> pd.DataFrame:
    cols = PROFILE_COLUMNS + ["eligible_for_spatial_clustering"]
    df = pd.read_parquet(processed_path, columns=cols)
    if eligible_only:
        df = df[df["eligible_for_spatial_clustering"]].reset_index(drop=True)
    return df.drop(columns=["eligible_for_spatial_clustering"])


def _top(series: pd.Series, labels: np.ndarray, n: int = 3, exclude: tuple[str, ...] = ()) -> dict[int, list]:
    frame = pd.DataFrame({"c": labels, "v": series.astype(object).to_numpy()})
    frame = frame[(frame["c"] >= 0) & frame["v"].notna() & ~frame["v"].isin(exclude)]
    counts = frame.groupby(["c", "v"]).size().rename("n").reset_index()
    totals = frame.groupby("c").size()
    counts = counts.sort_values(["c", "n"], ascending=[True, False]).groupby("c").head(n)
    out: dict[int, list] = {}
    for c, g in counts.groupby("c"):
        out[int(c)] = [{"value": str(v), "count": int(k), "share": round(k / totals[c], 4)} for v, k in zip(g["v"], g["n"])]
    return out


def cluster_profiles(labels: np.ndarray, x_m: np.ndarray, y_m: np.ndarray, location_index: np.ndarray,
                     attrs: pd.DataFrame, experiment_id: str, projected_crs: str = "EPSG:32618",
                     hull_buffer_m: float = 15.0) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Olay düzeyi etiketlerden küme özet tablosu ve GeoJSON (WGS84, [boylam, enlem]) üretir."""
    labels = np.asarray(labels)
    keep = labels >= 0
    c = labels[keep]
    df = pd.DataFrame({"cluster_id": c, "x": x_m[keep], "y": y_m[keep], "loc": location_index[keep]})
    a = attrs.loc[keep].reset_index(drop=True)
    g = df.groupby("cluster_id")
    summary = g.agg(n_events=("x", "size"), n_unique_locations=("loc", "nunique"),
                    centroid_x=("x", "mean"), centroid_y=("y", "mean"),
                    min_x=("x", "min"), max_x=("x", "max"), min_y=("y", "min"), max_y=("y", "max")).reset_index()
    to_wgs = Transformer.from_crs(projected_crs, "EPSG:4326", always_xy=True)
    summary["centroid_lon"], summary["centroid_lat"] = to_wgs.transform(summary["centroid_x"], summary["centroid_y"])
    summary["bbox_min_lon"], summary["bbox_min_lat"] = to_wgs.transform(summary["min_x"], summary["min_y"])
    summary["bbox_max_lon"], summary["bbox_max_lat"] = to_wgs.transform(summary["max_x"], summary["max_y"])
    cx = summary.set_index("cluster_id")["centroid_x"].reindex(c).to_numpy()
    cy = summary.set_index("cluster_id")["centroid_y"].reindex(c).to_numpy()
    df["r"] = np.hypot(df["x"] - cx, df["y"] - cy)
    summary["radius_p90_m"] = df.groupby("cluster_id")["r"].quantile(0.9).to_numpy()  # merkeze uzaklığın %90'ı

    # Dışbükey zarf: benzersiz konumlardan (yinelenen noktalar zarfı değiştirmez)
    uniq = df.drop_duplicates(["cluster_id", "loc"]).sort_values("cluster_id")
    ids, starts = np.unique(uniq["cluster_id"].to_numpy(), return_index=True)
    parts = shapely.multipoints(np.column_stack([uniq["x"], uniq["y"]]),
                                indices=np.searchsorted(ids, uniq["cluster_id"].to_numpy()))
    hulls = shapely.convex_hull(parts)
    degenerate = shapely.area(hulls) <= 0
    geoms = np.where(degenerate, shapely.buffer(hulls, hull_buffer_m), hulls)
    hull_area = pd.Series(np.where(degenerate, 0.0, shapely.area(hulls)) / 1e6, index=ids)
    summary["hull_area_km2"] = hull_area.reindex(summary["cluster_id"]).to_numpy()
    summary["geometry_kind"] = np.where(pd.Series(degenerate, index=ids).reindex(summary["cluster_id"]).to_numpy(),
                                        f"buffer_{int(hull_buffer_m)}m_degenerate", "convex_hull")
    area_for_density = np.maximum(summary["hull_area_km2"], np.pi * (hull_buffer_m / 1000) ** 2)
    summary["events_per_km2_hull"] = summary["n_events"] / area_for_density

    # Betimleyici öznitelikler
    a = a.assign(cluster_id=c)
    ga = a.groupby("cluster_id")
    dates = pd.to_datetime(a["crash_date"])
    summary["date_min"] = dates.groupby(c).min().reindex(summary["cluster_id"]).dt.date.astype(str).to_numpy()
    summary["date_max"] = dates.groupby(c).max().reindex(summary["cluster_id"]).dt.date.astype(str).to_numpy()
    summary["active_years"] = dates.dt.year.groupby(c).nunique().reindex(summary["cluster_id"]).to_numpy()
    summary["injury_crashes"] = ga["has_reported_injury"].sum().reindex(summary["cluster_id"]).to_numpy()
    summary["fatal_crashes"] = ga["has_reported_fatality"].sum().reindex(summary["cluster_id"]).to_numpy()
    summary["persons_injured"] = ga["number_of_persons_injured"].sum().reindex(summary["cluster_id"]).to_numpy()
    summary["persons_killed"] = ga["number_of_persons_killed"].sum().reindex(summary["cluster_id"]).to_numpy()
    summary["injury_crash_share"] = summary["injury_crashes"] / summary["n_events"]
    hours = pd.crosstab(c, a["crash_hour"].astype("Int64").fillna(-1).astype(int))
    hours = hours.reindex(columns=range(24), fill_value=0).reindex(summary["cluster_id"], fill_value=0)
    summary["hour_histogram"] = [list(map(int, r)) for r in hours.to_numpy()]
    summary["peak_hour"] = hours.to_numpy().argmax(axis=1)
    boro = _top(a["borough_final"], c, n=3)
    summary["dominant_borough"] = [boro.get(int(k), [{}])[0].get("value") for k in summary["cluster_id"]]
    summary["dominant_borough_share"] = [boro.get(int(k), [{}])[0].get("share") for k in summary["cluster_id"]]
    for col, name, excl in (("vehicle_category_1", "top_vehicle_categories", ()),
                            ("contributing_factor_vehicle_1", "top_contributing_factors", ("Unspecified",)),
                            ("time_period", "time_periods", ()), ("on_street_name", "top_streets", ())):
        tops = _top(a[col], c, n=3 if col != "time_period" else 4, exclude=excl)
        summary[name] = [json.dumps(tops.get(int(k), []), ensure_ascii=False) for k in summary["cluster_id"]]
    unspecified = (a["contributing_factor_vehicle_1"] == "Unspecified").groupby(c).mean()
    summary["factor_unspecified_share"] = unspecified.reindex(summary["cluster_id"]).to_numpy()
    summary = summary.sort_values("n_events", ascending=False).reset_index(drop=True)
    summary.insert(0, "rank_by_events", np.arange(1, len(summary) + 1))
    summary.insert(0, "experiment_id", experiment_id)
    summary = summary.drop(columns=["centroid_x", "centroid_y", "min_x", "max_x", "min_y", "max_y"])

    gdf = gpd.GeoDataFrame({"cluster_id": ids}, geometry=list(geoms), crs=projected_crs).to_crs("EPSG:4326")
    props = summary.set_index("cluster_id")[["rank_by_events", "n_events", "n_unique_locations", "dominant_borough",
                                             "injury_crashes", "fatal_crashes", "hull_area_km2", "geometry_kind"]]
    gdf = gdf.join(props, on="cluster_id")
    gdf["experiment_id"] = experiment_id
    geojson = json.loads(gdf.to_json(drop_id=True))
    geojson["crs_note"] = "WGS84 (EPSG:4326); RFC 7946 koordinat sırası [boylam, enlem]"
    geojson["geometry_semantics"] = ("Üye benzersiz konumların dışbükey zarfı (görselleştirme sınırı); "
                                     "istatistiksel yoğunluk konturu değildir.")
    return summary, geojson
