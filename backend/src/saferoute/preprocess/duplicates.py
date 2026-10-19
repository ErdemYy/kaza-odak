"""Aynı koordinatta tekrarlanan kazaların analizi ve ağırlıklı temsil.

Aynı (enlem, boylam) noktasındaki farklı ``collision_id``'ler AYRI kaza olaylarıdır;
silinmez. Faz 3'te performans için benzersiz konumlar + ağırlık (= o konumdaki kaza
sayısı) temsili kullanılabilir:

  * scikit-learn ``DBSCAN.fit(X, sample_weight=w)``: çekirdek nokta koşulu komşuluktaki
    AĞIRLIK toplamıyla değerlendirilir; ağırlığı ``min_samples``'a ulaşan bir konum
    tek başına çekirdektir. Özdeş noktaların komşulukları da özdeş olduğundan, benzersiz
    konum + ağırlık çözümü kayıt düzeyi çözümle aynı küme yapısını vermelidir
    (Faz 3'te alt örneklemde birebir doğrulanacak).
  * ``KMeans.fit(X, sample_weight=w)``: ağırlıklı atalet, tekrarlı noktalarla aynıdır.
  * ``HDBSCAN.fit``: scikit-learn 1.9.1'de ``sample_weight`` parametresi YOKTUR;
    benzersiz konumlara indirgemek çekirdek mesafelerini değiştirir, eşdeğer değildir.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def assign_location_ids(lat: np.ndarray, lon: np.ndarray, eligible: np.ndarray) -> np.ndarray:
    """Uygun satırlara deterministik konum kimliği (sıralı benzersiz çiftler) atar; diğerlerine -1."""
    ids = np.full(len(lat), -1, dtype=np.int64)
    if eligible.any():
        pairs = np.column_stack([lat[eligible], lon[eligible]])
        _, inverse = np.unique(pairs, axis=0, return_inverse=True)
        ids[eligible] = inverse.ravel()
    return ids


def geocode_fallback_flags(df: pd.DataFrame, min_boroughs: int = 3) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Aynı koordinatta >= ``min_boroughs`` FARKLI bildirilmiş ilçe varsa konumu şüpheli işaretler.

    Gerekçe: tek bir fiziksel nokta en fazla iki ilçenin ortak sınırında olabilir; üç veya
    daha fazla ilçeden bildirilen kazaların aynı noktaya düşmesi, koordinatın gerçek konum
    değil bir yedek/varsayılan geokodlama noktası olduğuna işaret eder. Kayıtlar SİLİNMEZ ve
    uygunluktan çıkarılmaz; Faz 3'te duyarlılık analizi için bayraklanır.
    """
    sub = df.loc[df["location_id"] >= 0, ["location_id", "borough_original"]].dropna()
    n_b = sub.groupby("location_id")["borough_original"].nunique()
    counts = df["location_id"].map(n_b).fillna(0).astype("int8")
    out = pd.DataFrame({"location_reported_borough_count": counts,
                        "geocode_fallback_suspect_flag": counts >= min_boroughs}, index=df.index)
    suspect_locs = n_b[n_b >= min_boroughs]
    stats = {
        "rule": f"aynı koordinatta >= {min_boroughs} farklı bildirilmiş ilçe",
        "locations": int(len(suspect_locs)),
        "records": int(out["geocode_fallback_suspect_flag"].sum()),
        "records_by_year": {str(int(k)): int(v) for k, v in
                            df.loc[out["geocode_fallback_suspect_flag"], "crash_year"].value_counts().sort_index().items()},
    }
    return out, stats


def location_table(df: pd.DataFrame) -> pd.DataFrame:
    """Benzersiz konum tablosu: location_id, enlem, boylam, ağırlık (kaza sayısı), baskın ilçe."""
    sub = df.loc[df["location_id"] >= 0, ["location_id", "latitude", "longitude", "borough_final"]]
    g = sub.groupby("location_id", sort=True)
    table = g.agg(latitude=("latitude", "first"), longitude=("longitude", "first"),
                  weight=("latitude", "size")).reset_index()
    mode = (sub.dropna(subset=["borough_final"])
            .groupby(["location_id", "borough_final"], observed=True).size()
            .reset_index(name="n").sort_values(["location_id", "n"], ascending=[True, False])
            .drop_duplicates("location_id").set_index("location_id")["borough_final"])
    table["borough"] = table["location_id"].map(mode)
    if "geocode_fallback_suspect_flag" in df.columns:
        flag = df.loc[df["location_id"] >= 0].groupby("location_id")["geocode_fallback_suspect_flag"].any()
        table["geocode_fallback_suspect_flag"] = table["location_id"].map(flag).fillna(False).astype(bool)
    return table


def repetition_analysis(df: pd.DataFrame, locations: pd.DataFrame, top_n: int = 25,
                        min_samples_grid: tuple[int, ...] = (5, 10, 20, 50, 100)) -> dict[str, Any]:
    """Konum başına kaza sayısı dağılımı, en çok tekrarlanan konumlar ve DBSCAN etkisi."""
    w = locations["weight"].to_numpy()
    total = int(w.sum())
    bins = [1, 2, 6, 11, 51, 101, np.inf]
    labels = ["1", "2–5", "6–10", "11–50", "51–100", ">100"]
    cut = pd.cut(w, bins=bins, right=False, labels=labels)
    dist = pd.DataFrame({"bucket": cut, "w": w}).groupby("bucket", observed=False).agg(
        locations=("w", "size"), records=("w", "sum"))
    top = locations.sort_values("weight", ascending=False).head(top_n).copy()
    streets = (df.loc[df["location_id"].isin(top["location_id"]), ["location_id", "on_street_name", "off_street_name"]]
               .dropna(subset=["on_street_name"])
               .groupby("location_id")[["on_street_name", "off_street_name"]]
               .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else None))
    top = top.join(streets, on="location_id")
    repeated = locations[locations["weight"] > 1]
    return {
        "eligible_records": total,
        "unique_locations": int(len(locations)),
        "records_per_location_mean": round(total / len(locations), 3) if len(locations) else None,
        "records_per_location_median": float(np.median(w)) if len(w) else None,
        "records_per_location_max": int(w.max()) if len(w) else None,
        "single_record_locations": int((w == 1).sum()),
        "repeated_locations": int(len(repeated)),
        "records_at_repeated_locations": int(repeated["weight"].sum()),
        "records_at_repeated_locations_pct": round(100.0 * repeated["weight"].sum() / total, 2) if total else 0.0,
        "distribution": {str(k): {"locations": int(r.locations), "records": int(r.records)} for k, r in dist.iterrows()},
        "repeated_by_borough": {str(k): {"locations": int(v["locations"]), "records": int(v["records"])}
                                for k, v in repeated.assign(borough=repeated["borough"].fillna("(ilçesiz)"))
                                .groupby("borough").agg(locations=("weight", "size"), records=("weight", "sum"))
                                .iterrows()},
        # Ağırlığı >= min_samples olan konum, eps ne olursa olsun tek başına DBSCAN çekirdeğidir.
        "self_core_locations_by_min_samples": {
            str(m): {"locations": int((w >= m).sum()), "records": int(w[w >= m].sum())} for m in min_samples_grid
        },
        "top_locations": [
            {"location_id": int(r.location_id), "latitude": float(r.latitude), "longitude": float(r.longitude),
             "weight": int(r.weight), "borough": r.borough if isinstance(r.borough, str) else None,
             "on_street_name": r.on_street_name if isinstance(r.on_street_name, str) else None,
             "off_street_name": r.off_street_name if isinstance(r.off_street_name, str) else None}
            for r in top.itertuples()
        ],
    }
