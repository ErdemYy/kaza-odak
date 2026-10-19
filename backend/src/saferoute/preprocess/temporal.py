"""Tarih/saat öznitelikleri ve şüpheli 00:00 bayrağı.

Orijinal ``crash_date`` ve ``crash_time`` korunur. Döngüsel kodlama:
  saat:  açı = 2π · (saat + dakika/60) / 24   -> 23:59 ile 00:01 birbirine yakın
  ay:    açı = 2π · (ay − 1) / 12             -> Aralık ile Ocak birbirine yakın
  gün:   açı = 2π · haftanın_günü / 7          (0 = Pazartesi)
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from saferoute.preprocess.settings import PreprocessConfig


def cyclical(values: np.ndarray | pd.Series, period: float) -> tuple[np.ndarray, np.ndarray]:
    """Periyodik bir değeri birim çember üzerinde (sin, cos) çiftine dönüştürür."""
    angle = 2.0 * np.pi * np.asarray(values, dtype="float64") / period
    return np.sin(angle), np.cos(angle)


def time_period(hour: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    """Saati gün dilimine çevirir (yarı açık aralıklar; NA saat -> None)."""
    starts = np.array([s for s, _ in cfg.time_periods])
    labels = np.array([lbl for _, lbl in cfg.time_periods], dtype=object)
    h = np.asarray(hour, dtype="float64")
    out = labels[np.clip(np.searchsorted(starts, np.nan_to_num(h, nan=0), side="right") - 1, 0, len(labels) - 1)]
    return np.where(np.isnan(h), None, out)


def add_temporal_features(df: pd.DataFrame, cfg: PreprocessConfig) -> pd.DataFrame:
    """Interim DataFrame'den zaman özniteliklerini üretir (yeni DataFrame döner)."""
    date = df["crash_date"]
    hour = df["crash_hour"].astype("Float64").to_numpy(dtype="float64", na_value=np.nan)
    minute = df["crash_minute"].astype("Float64").to_numpy(dtype="float64", na_value=np.nan)
    out = pd.DataFrame(index=df.index)
    out["crash_year"] = date.dt.year.astype("Int16")
    out["crash_month"] = date.dt.month.astype("Int8")
    out["crash_day"] = date.dt.day.astype("Int8")
    dow = date.dt.dayofweek
    out["day_of_week"] = dow.astype("Int8")  # 0 = Pazartesi
    out["is_weekend"] = (dow >= 5).astype("boolean").where(date.notna())
    out["time_period"] = pd.Categorical(time_period(hour, cfg), categories=[lbl for _, lbl in cfg.time_periods])
    frac_hour = hour + minute / 60.0
    out["hour_sin"], out["hour_cos"] = cyclical(frac_hour, 24.0)
    out["month_sin"], out["month_cos"] = cyclical(date.dt.month.to_numpy(dtype="float64", na_value=np.nan) - 1, 12.0)
    out["dow_sin"], out["dow_cos"] = cyclical(dow.to_numpy(dtype="float64", na_value=np.nan), 7.0)
    out["midnight_suspect_flag"] = (hour == cfg.midnight_suspect_hour) & (minute == cfg.midnight_suspect_minute)
    # Uzay-zaman deneyi için doğrusal zaman ekseni: kapsamın başından itibaren gün.
    out["days_since_epoch"] = (date - pd.Timestamp("1970-01-01")).dt.days.astype("Int32")
    return out


def minute_heaping(df: pd.DataFrame) -> dict[str, Any]:
    """Her saat için 'tam saat' (HH:00) yığılma oranı: count(HH:00) / ortalama count(HH:01..59).

    00:00'ın oranı diğer saatlerin tam-saat oranlarından belirgin biçimde büyükse, yığılma
    genel yuvarlama alışkanlığıyla açıklanamaz; şüpheli bayrağının gerekçesidir.
    """
    h = df["crash_hour"].astype("Float64").to_numpy(dtype="float64", na_value=np.nan)
    m = df["crash_minute"].astype("Float64").to_numpy(dtype="float64", na_value=np.nan)
    ok = ~np.isnan(h) & ~np.isnan(m)
    # Hiç kayıt düşmeyen dakikalar da (0 sayımla) ortalamaya girmeli.
    table = pd.crosstab(h[ok].astype(int), m[ok].astype(int)).reindex(columns=range(60), fill_value=0)
    ratios = {}
    for hour in table.index:
        row = table.loc[hour]
        others = row.drop(index=0, errors="ignore")
        mean_other = float(others.mean()) if len(others) else float("nan")
        ratios[str(int(hour))] = {
            "on_the_hour": int(row.get(0, 0)),
            "mean_other_minutes": round(mean_other, 2),
            "ratio": round(row.get(0, 0) / mean_other, 2) if mean_other else None,
        }
    other_ratios = [v["ratio"] for k, v in ratios.items() if k != "0" and v["ratio"] is not None]
    minute_totals = table.sum(axis=0)
    return {
        "per_hour": ratios,
        "midnight_ratio": ratios.get("0", {}).get("ratio"),
        "other_hours_ratio_median": float(np.median(other_ratios)) if other_ratios else None,
        "other_hours_ratio_max": float(np.max(other_ratios)) if other_ratios else None,
        "minute_of_hour_counts": {str(int(k)): int(v) for k, v in minute_totals.items()},
    }
