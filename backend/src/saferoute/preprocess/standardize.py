"""Interim katman: ham metin sütunlarını doğrulanmış türlere dönüştürür ve standartlaştırır.

İlkeler:
  * Eksik değer doldurulmaz; ayrıştırılamayan değerler NA olur ve SAYILIR.
  * Koordinatlar için ayrıştırma durumu (missing / unparseable / non_finite / parsed)
    ayrı sütunda tutulur; böylece geçersizlik nedeni kaybolmaz.
  * ``location`` sütunu enlem/boylamın metin tekrarıdır; tutarlılığı ölçülür ve interim
    katmana taşınmaz (ham katmanda durur).
  * Büyük veri için ayrıştırma benzersiz değerler üzerinde yapılır (factorize + take).
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

from saferoute.data.validate import null_percentage, parse_crash_date, parse_crash_time, require_columns
from saferoute.eda.profile import CASUALTY_COLUMNS, FACTOR_COLUMNS, VEHICLE_COLUMNS

STREET_COLUMNS = ("on_street_name", "off_street_name", "cross_street_name")


def _clean_text(s: pd.Series, upper: bool = False) -> pd.Series:
    """Baş/son boşluğu kırpar, iç boşlukları tekler; boş metni NA yapar."""
    t = s.astype("string[pyarrow]").str.strip().str.replace(r"\s+", " ", regex=True)
    if upper:
        t = t.str.upper()
    return t.mask(t == "")


def map_uniques(s: pd.Series, parser: Callable[[pd.Series], pd.Series]) -> np.ndarray:
    """``parser``'ı yalnızca benzersiz değerlere uygular, sonucu satırlara yayar.

    NA girdiler sonuçta NA (float için NaN, datetime için NaT) olur.
    """
    codes, uniques = pd.factorize(s, use_na_sentinel=True)
    parsed = parser(pd.Series(np.asarray(uniques, dtype=object))).to_numpy()
    if len(parsed) == 0:
        dtype = parsed.dtype if parsed.dtype != object else "float64"
        return np.full(len(s), np.nan if dtype == "float64" else None, dtype=dtype)
    out = parsed[np.where(codes >= 0, codes, 0)]
    missing = codes < 0
    if missing.any():
        out = out.copy()
        out[missing] = np.datetime64("NaT") if np.issubdtype(out.dtype, np.datetime64) else np.nan
    return out


def _to_float(u: pd.Series) -> pd.Series:
    return pd.to_numeric(u.astype(str).str.strip(), errors="coerce").astype("float64")


def parse_coordinate(s: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Koordinat metnini float'a çevirir; her satır için ayrıştırma durumunu döndürür.

    Durumlar: ``missing`` (boş), ``unparseable`` (sayı değil), ``non_finite`` (inf/nan
    metni), ``parsed``.
    """
    text = s.astype("string[pyarrow]").str.strip()
    present = (text.notna() & (text != "")).fillna(False).to_numpy(bool)
    values = map_uniques(text.mask(~pd.Series(present, index=s.index)), _to_float)
    status = np.full(len(s), "parsed", dtype=object)
    status[~present] = "missing"
    # "inf", "nan" gibi metinler sayıya çevrilebilir ama sonlu değildir.
    lowered = text.str.lower().fillna("")
    nan_text = present & lowered.isin(["nan", "+nan", "-nan"]).to_numpy(bool)
    nonfinite = present & (np.isinf(values) | nan_text)
    unparseable = present & np.isnan(values) & ~nan_text
    status[unparseable] = "unparseable"
    status[nonfinite] = "non_finite"
    values = np.where(status == "parsed", values, np.nan)
    return values, status


def standardize(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Ham (tamamı metin) DataFrame'den interim DataFrame ve dönüşüm sayımlarını üretir."""
    require_columns(raw)
    n = len(raw)
    out = pd.DataFrame(index=raw.index)
    stats: dict[str, Any] = {"row_count": n}
    # Ham eksik oranı (boş veya yalnız boşluk) — öznitelik seçimi raporunda kullanılır.
    stats["raw_missing_pct"] = {
        col: null_percentage(int((~(raw[col].astype("string[pyarrow]").str.strip() != "").fillna(False)).sum()), n)
        for col in raw.columns
    }

    ids = map_uniques(raw["collision_id"].astype("string[pyarrow]").str.strip(), _to_float)
    id_ok = ~np.isnan(ids) & (np.mod(np.nan_to_num(ids), 1) == 0)
    out["collision_id"] = pd.array(np.where(id_ok, ids, np.nan), dtype="float64").astype("Int64")
    stats["collision_id_invalid"] = int((~id_ok).sum())

    out["crash_date"] = map_uniques(raw["crash_date"], parse_crash_date).astype("datetime64[ns]")
    t = parse_crash_time(raw["crash_time"])
    out["crash_time"] = _clean_text(raw["crash_time"])
    out["crash_hour"] = pd.array(t["hour"].to_numpy(), dtype="Float64").astype("Int8")
    out["crash_minute"] = pd.array(t["minute"].to_numpy(), dtype="Float64").astype("Int8")
    stats["crash_date_unparseable"] = int((raw["crash_date"].notna().to_numpy() & out["crash_date"].isna().to_numpy()).sum())
    stats["crash_time_invalid"] = int((~t["valid"]).sum())

    out["borough_original"] = _clean_text(raw["borough"], upper=True)
    out["zip_code"] = _clean_text(raw["zip_code"])

    lat, lat_status = parse_coordinate(raw["latitude"])
    lon, lon_status = parse_coordinate(raw["longitude"])
    out["latitude"] = lat
    out["longitude"] = lon
    # Satır düzeyi ayrıştırma durumu: iki koordinattan en kötüsü.
    rank = {"missing": 0, "unparseable": 1, "non_finite": 2, "parsed": 3}
    order = np.array(list(rank))
    worst = np.minimum(pd.Series(lat_status).map(rank).to_numpy(), pd.Series(lon_status).map(rank).to_numpy())
    out["coord_parse_status"] = pd.Categorical(order[worst], categories=list(rank))
    stats["coord_parse_status"] = out["coord_parse_status"].value_counts().reindex(list(rank)).astype(int).to_dict()
    stats["location_consistency"] = location_consistency(raw["location"], lat, lon)

    for col in STREET_COLUMNS:
        out[col] = _clean_text(raw[col], upper=True)
    for col in CASUALTY_COLUMNS:
        text = raw[col].astype("string[pyarrow]").str.strip()
        vals = map_uniques(text.mask(text == ""), _to_float)
        bad = text.notna().to_numpy() & (text != "").fillna(False).to_numpy() & np.isnan(vals)
        stats.setdefault("casualty_unparseable", {})[col] = int(bad.sum())
        out[col] = pd.array(vals, dtype="Float64").astype("Int32")
    for col in FACTOR_COLUMNS:
        out[col] = _clean_text(raw[col])
    for col in VEHICLE_COLUMNS:
        out[col] = _clean_text(raw[col])
    # Ham araç etiketi çeşitliliği (Faz 1 ile karşılaştırma için; dönüştürülmemiş değerler)
    stats["vehicle_raw_distinct"] = int(pd.concat([raw[c] for c in VEHICLE_COLUMNS]).dropna().nunique())
    return out, stats


def location_consistency(location: pd.Series, lat: np.ndarray, lon: np.ndarray) -> dict[str, int]:
    """``location`` metnindeki '(enlem, boylam)' çifti ile ayrı sütunların uyumunu ölçer."""
    text = location.astype("string[pyarrow]")
    # Socrata konum metni adres önekli olabilir: "\n,  \n(40.66, -73.76)"; çift metnin sonundadır.
    parts = text.str.extract(r"\(\s*([-+0-9.eE]+)\s*,\s*([-+0-9.eE]+)\s*\)\s*$")
    loc_lat = map_uniques(parts[0], _to_float)
    loc_lon = map_uniques(parts[1], _to_float)
    present = text.notna().to_numpy()
    both = present & ~np.isnan(loc_lat) & ~np.isnan(lat)
    equal = both & np.isclose(loc_lat, lat, atol=1e-9) & np.isclose(loc_lon, lon, atol=1e-9)
    return {
        "location_present": int(present.sum()),
        "location_unparseable": int((present & np.isnan(loc_lat)).sum()),
        "compared": int(both.sum()),
        "equal": int(equal.sum()),
        "different": int((both & ~equal).sum()),
    }
