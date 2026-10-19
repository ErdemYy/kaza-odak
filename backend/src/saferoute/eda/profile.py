"""Ham çarpışma verisi için keşifsel veri analizi (EDA) profilleri.

Buradaki fonksiyonlar veriyi DEĞİŞTİRMEZ ve hiçbir eksik değeri doldurmaz; yalnızca
ölçer. Her fonksiyon JSON'a yazılabilir bir sözlük döndürür. Sayımlar ham metin
sütunları üzerinden yapılır: "eksik" = boş alan, "boşluk" = yalnızca boşluk karakteri,
"ayrıştırılamaz" = dolu ama beklenen türe dönüştürülemeyen değer.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from saferoute import config
from saferoute.data.validate import (
    borough_status,
    null_percentage,
    parse_crash_date,
    parse_crash_time,
    require_columns,
)

CASUALTY_COLUMNS = [
    "number_of_persons_injured",
    "number_of_persons_killed",
    "number_of_pedestrians_injured",
    "number_of_pedestrians_killed",
    "number_of_cyclist_injured",
    "number_of_cyclist_killed",
    "number_of_motorist_injured",
    "number_of_motorist_killed",
]
FACTOR_COLUMNS = [f"contributing_factor_vehicle_{i}" for i in range(1, 6)]
VEHICLE_COLUMNS = [
    "vehicle_type_code1",
    "vehicle_type_code2",
    "vehicle_type_code_3",
    "vehicle_type_code_4",
    "vehicle_type_code_5",
]
COORD_CLASSES = ("missing", "unparseable", "zero", "outside_nyc_bbox", "valid_in_bbox")


def _int(x: Any) -> int:
    return int(x)


_pct = null_percentage


def _as_text(s: pd.Series) -> pd.Series:
    return s.astype("string[pyarrow]")


def _blank_mask(s: pd.Series) -> pd.Series:
    """Dolu ama yalnızca boşluk içeren hücreler."""
    t = _as_text(s)
    return (t.notna() & (t.str.strip() == "")).fillna(False).astype(bool)


def _present_mask(s: pd.Series) -> pd.Series:
    t = _as_text(s)
    return (t.notna() & (t.str.strip() != "")).fillna(False).astype(bool)


def _numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(_as_text(s).str.strip().astype(object), errors="coerce").astype("float64")


def _value_counts(s: pd.Series, top_n: int | None = None) -> dict[str, int]:
    vc = _as_text(s).value_counts(dropna=True)
    if top_n is not None:
        vc = vc.head(top_n)
    return {str(k): _int(v) for k, v in vc.items()}


def schema_summary(df: pd.DataFrame) -> dict[str, Any]:
    return {"row_count": _int(len(df)), "column_count": _int(df.shape[1]), "columns": list(df.columns)}


def infer_type(values: pd.Series) -> str:
    """Dolu (boş olmayan) değerlerin tamamına uyan en dar türü döndürür.

    Sıra: integer -> float -> datetime -> time -> text. Hiç dolu değer yoksa "empty".
    Benzersiz değerler üzerinde çalışır; satır sayısından bağımsız olarak hızlıdır.
    """
    text = _as_text(values).dropna().str.strip()
    text = text[text != ""].drop_duplicates()
    if text.empty:
        return "empty"
    num = pd.to_numeric(text.astype(object), errors="coerce")
    if num.notna().all():
        return "integer" if (num % 1 == 0).all() else "float"
    if parse_crash_date(text).notna().all():
        return "datetime"
    if parse_crash_time(text)["valid"].all():
        return "time"
    return "text"


def column_overview(df: pd.DataFrame, source_types: dict[str, str] | None = None) -> dict[str, Any]:
    """Her sütun için kaynak türü, çıkarılan tür, eksik sayısı/oranı, benzersiz değer sayısı.

    ``candidate_identifier``: tüm satırlarda dolu ve tüm değerleri farklı olan sütun.
    """
    source_types = source_types or {}
    total = len(df)
    out: dict[str, Any] = {}
    for col in df.columns:
        present = _present_mask(df[col])
        missing = _int((~present).sum())
        unique = _int(_as_text(df.loc[present, col]).nunique())
        out[col] = {
            "source_type": source_types.get(col),
            "inferred_type": infer_type(df[col]),
            "missing": missing,
            "missing_pct": _pct(missing, total),
            "unique_non_missing": unique,
            "candidate_identifier": bool(total) and missing == 0 and unique == total,
        }
    return out


def missing_values(df: pd.DataFrame) -> dict[str, Any]:
    """Her sütun için boş (null) ve yalnızca-boşluk hücre sayıları."""
    total = len(df)
    out = {}
    for col in df.columns:
        nulls = _int(df[col].isna().sum())
        blanks = _int(_blank_mask(df[col]).sum())
        out[col] = {
            "null": nulls,
            "blank": blanks,
            "missing_total": nulls + blanks,
            "missing_pct": _pct(nulls + blanks, total),
        }
    return out


def duplicates(df: pd.DataFrame) -> dict[str, Any]:
    """collision_id benzersizliği ve tam satır tekrarları."""
    ids = _as_text(df["collision_id"])
    present = _present_mask(ids)
    numeric = _numeric(ids)
    non_integer = present & (numeric.isna() | (numeric % 1 != 0))
    vc = ids[present].value_counts()
    dup_ids = vc[vc > 1]
    return {
        "collision_id_missing": _int((~present).sum()),
        "collision_id_non_integer": _int(non_integer.sum()),
        "collision_id_unique_values": _int(len(vc)),
        "duplicated_collision_ids": _int(len(dup_ids)),
        "rows_with_duplicated_collision_id": _int(dup_ids.sum()),
        "exact_duplicate_rows": _int(df.duplicated(keep="first").sum()) if len(df) else 0,
        "duplicated_collision_id_examples": [str(x) for x in dup_ids.index[:10]],
    }


def temporal(df: pd.DataFrame) -> dict[str, Any]:
    """crash_date / crash_time ayrıştırma, kapsam ve zamansal dağılımlar."""
    total = len(df)
    date_present = _present_mask(df["crash_date"])
    dates = parse_crash_date(df["crash_date"])
    date_unparseable = date_present & dates.isna()

    time_present = _present_mask(df["crash_time"])
    t = parse_crash_time(df["crash_time"])
    time_valid = t["valid"]
    midnight = time_valid & (t["hour"] == 0) & (t["minute"] == 0)

    valid_dates = dates.dropna()
    year_counts = valid_dates.dt.year.value_counts().sort_index()
    month_counts = valid_dates.dt.to_period("M").astype(str).value_counts().sort_index()
    weekday_counts = valid_dates.dt.dayofweek.value_counts().sort_index()
    hour_counts = t.loc[time_valid, "hour"].astype(int).value_counts().sort_index()

    has_dates = len(valid_dates) > 0
    return {
        "crash_date_missing": _int((~date_present).sum()),
        "crash_date_unparseable": _int(date_unparseable.sum()),
        "crash_date_min": valid_dates.min().date().isoformat() if has_dates else None,
        "crash_date_max": valid_dates.max().date().isoformat() if has_dates else None,
        "crash_date_has_nonzero_time_component": _int(
            ((valid_dates.dt.hour != 0) | (valid_dates.dt.minute != 0)).sum()
        ),
        "crash_time_missing": _int((~time_present).sum()),
        "crash_time_invalid": _int((time_present & ~time_valid).sum()),
        "crash_time_exact_midnight": _int(midnight.sum()),
        "crash_time_exact_midnight_pct": _pct(_int(midnight.sum()), total),
        "rows_per_year": {str(k): _int(v) for k, v in year_counts.items()},
        "rows_per_month": {str(k): _int(v) for k, v in month_counts.items()},
        "rows_per_weekday": {str(k): _int(v) for k, v in weekday_counts.items()},  # 0=Pazartesi
        "rows_per_hour": {str(k): _int(v) for k, v in hour_counts.items()},
    }


def coordinate_class(df: pd.DataFrame, bbox: dict[str, float] | None = None) -> pd.Series:
    """Her satırı birbirini dışlayan bir koordinat kalite sınıfına atar.

    Öncelik sırası: eksik -> ayrıştırılamaz -> sıfır -> NYC kutusu dışı -> geçerli.
    Kutu yalnızca kaba bir geçerlilik testidir; ilçe ataması için KULLANILMAZ.
    """
    bbox = bbox or config.NYC_BBOX
    lat_present, lon_present = _present_mask(df["latitude"]), _present_mask(df["longitude"])
    lat, lon = _numeric(df["latitude"]), _numeric(df["longitude"])
    missing = ~(lat_present & lon_present)
    unparseable = ~missing & (lat.isna() | lon.isna())
    zero = ~missing & ~unparseable & ((lat == 0) | (lon == 0))
    inside = (lat.between(bbox["min_lat"], bbox["max_lat"]) & lon.between(bbox["min_lon"], bbox["max_lon"]))
    out = pd.Series("valid_in_bbox", index=df.index, dtype="object")
    out[~inside.fillna(False).astype(bool)] = "outside_nyc_bbox"
    out[zero] = "zero"
    out[unparseable] = "unparseable"
    out[missing] = "missing"
    return out


def coordinate_validity_mask(df: pd.DataFrame, bbox: dict[str, float] | None = None) -> pd.Series:
    """NYC kutusu içinde geçerli koordinatlı satırlar."""
    return coordinate_class(df, bbox) == "valid_in_bbox"


def coordinates(df: pd.DataFrame, bbox: dict[str, float] | None = None) -> dict[str, Any]:
    """Koordinat kalite sınıfları ve ilçe alanıyla ilişkisi."""
    bbox = bbox or config.NYC_BBOX
    total = len(df)
    cls = coordinate_class(df, bbox)
    counts = cls.value_counts()
    classes = {k: _int(counts.get(k, 0)) for k in COORD_CLASSES}
    assert sum(classes.values()) == total, "koordinat sınıfları toplamı satır sayısına eşit olmalı"

    valid = cls == "valid_in_bbox"
    missing = cls == "missing"
    lat, lon = _numeric(df["latitude"]), _numeric(df["longitude"])
    borough_present = _present_mask(df["borough"])
    location_present = _present_mask(df["location"])
    valid_lat, valid_lon = lat[valid], lon[valid]
    any_valid = bool(valid.any())
    return {
        "classes": classes,
        "classes_pct": {k: _pct(v, total) for k, v in classes.items()},
        "bbox": bbox,
        "valid_but_borough_missing": _int((valid & ~borough_present).sum()),
        "borough_present_but_coords_unusable": _int((~valid & borough_present).sum()),
        "location_present_latlon_missing": _int((location_present & missing).sum()),
        "latlon_present_location_missing": _int((~location_present & ~missing).sum()),
        "valid_extent": {
            "min_lat": float(valid_lat.min()) if any_valid else None,
            "max_lat": float(valid_lat.max()) if any_valid else None,
            "min_lon": float(valid_lon.min()) if any_valid else None,
            "max_lon": float(valid_lon.max()) if any_valid else None,
        },
        "distinct_valid_locations": _int(pd.DataFrame({"a": valid_lat, "b": valid_lon}).drop_duplicates().shape[0]),
    }


def boroughs(df: pd.DataFrame) -> dict[str, Any]:
    """Kaydedilmiş ilçe etiketleri; eksik ve beklenmeyen etiketler ayrı raporlanır."""
    total = len(df)
    status = borough_status(df["borough"])
    counts = _value_counts(_as_text(df.loc[status == "valid", "borough"]).str.strip().str.upper())
    unexpected = _value_counts(df.loc[status == "unexpected", "borough"])
    missing = _int((status == "missing").sum())
    return {
        "counts": {b: counts.get(b, 0) for b in config.BOROUGHS},
        "missing": missing,
        "missing_pct": _pct(missing, total),
        "unexpected_values": sorted(unexpected),
        "unexpected_rows": _int(sum(unexpected.values())),
    }


def borough_by_coordinate_class(df: pd.DataFrame, bbox: dict[str, float] | None = None) -> dict[str, Any]:
    """Kaydedilmiş ilçe (veya eksik/beklenmeyen) × koordinat sınıfı çapraz tablosu."""
    status = borough_status(df["borough"])
    label = _as_text(df["borough"]).str.strip().str.upper().astype(object)
    row_key = label.where(status == "valid", status.str.upper())
    table = pd.crosstab(row_key, coordinate_class(df, bbox))
    out: dict[str, Any] = {}
    for key in [*config.BOROUGHS, "MISSING", "UNEXPECTED"]:
        if key in table.index:
            out[key] = {c: _int(table.loc[key].get(c, 0)) for c in COORD_CLASSES}
    return out


def by_year_quality(df: pd.DataFrame, bbox: dict[str, float] | None = None) -> dict[str, Any]:
    """Yıllara göre koordinat ve ilçe eksikliği oranı (veri kalitesinin zamanla değişimi)."""
    frame = pd.DataFrame({
        "year": parse_crash_date(df["crash_date"]).dt.year,
        "coord_valid": coordinate_validity_mask(df, bbox),
        "borough_present": _present_mask(df["borough"]),
    }).dropna(subset=["year"])
    grouped = frame.groupby("year").agg(
        rows=("coord_valid", "size"), coord_valid=("coord_valid", "sum"), borough_present=("borough_present", "sum")
    )
    return {
        str(int(y)): {
            "rows": _int(r.rows),
            "coord_valid_pct": _pct(_int(r.coord_valid), _int(r.rows)),
            "borough_present_pct": _pct(_int(r.borough_present), _int(r.rows)),
        }
        for y, r in grouped.iterrows()
    }


def casualties(df: pd.DataFrame) -> dict[str, Any]:
    """Yaralı/ölü sütunlarının geçerliliği, toplamları ve iç tutarlılığı."""
    cols: dict[str, Any] = {}
    values: dict[str, pd.Series] = {}
    for col in CASUALTY_COLUMNS:
        present = _present_mask(df[col])
        v = _numeric(df[col])
        values[col] = v
        cols[col] = {
            "missing": _int((~present).sum()),
            "unparseable": _int((present & v.isna()).sum()),
            "negative": _int((v < 0).sum()),
            "non_integer": _int((v.notna() & (v % 1 != 0)).sum()),
            "sum": _int(v.fillna(0).clip(lower=0).sum()),
            "max": float(v.max()) if v.notna().any() else None,
            "rows_gt_zero": _int((v > 0).sum()),
        }

    def consistency(kind: str) -> dict[str, int]:
        total = values[f"number_of_persons_{kind}"]
        parts = (
            values[f"number_of_pedestrians_{kind}"]
            + values[f"number_of_cyclist_{kind}"]
            + values[f"number_of_motorist_{kind}"]
        )
        both = total.notna() & parts.notna()
        return {
            "comparable_rows": _int(both.sum()),
            "persons_equals_sum": _int((both & (total == parts)).sum()),
            "persons_greater_than_sum": _int((both & (total > parts)).sum()),
            "persons_less_than_sum": _int((both & (total < parts)).sum()),
        }

    injured, killed = values["number_of_persons_injured"], values["number_of_persons_killed"]
    return {
        "columns": cols,
        "consistency_injured": consistency("injured"),
        "consistency_killed": consistency("killed"),
        "rows_with_any_injury": _int((injured > 0).sum()),
        "rows_with_any_fatality": _int((killed > 0).sum()),
        "rows_with_injury_or_fatality": _int(((injured > 0) | (killed > 0)).sum()),
    }


def categoricals(df: pd.DataFrame, top_n: int = 20) -> dict[str, Any]:
    """Katkıda bulunan faktörler ve araç türleri: çeşitlilik, en sık değerler, araç sayısı."""
    factor1 = _as_text(df["contributing_factor_vehicle_1"])
    all_factors = pd.concat([_as_text(df[c]) for c in FACTOR_COLUMNS]).dropna()
    vt1 = _as_text(df["vehicle_type_code1"])
    all_vehicle = pd.concat([_as_text(df[c]) for c in VEHICLE_COLUMNS]).dropna()
    normalized_vehicle = all_vehicle.str.strip().str.upper()
    vehicles_per_row = sum((_present_mask(df[c]).astype(int) for c in VEHICLE_COLUMNS),
                           pd.Series(0, index=df.index))
    total = len(df)
    unspecified = _int((factor1.str.strip().str.lower() == "unspecified").fillna(False).sum())
    return {
        "contributing_factor_1_top": _value_counts(factor1, top_n),
        "contributing_factor_1_missing": _int((~_present_mask(factor1)).sum()),
        "contributing_factor_1_unspecified": unspecified,
        "contributing_factor_1_unspecified_pct": _pct(unspecified, total),
        "contributing_factor_distinct_all_columns": _int(all_factors.nunique()),
        "vehicle_type_1_top": _value_counts(vt1, top_n),
        "vehicle_type_1_top_normalized": _value_counts(vt1.str.strip().str.upper(), top_n),
        "vehicle_type_1_missing": _int((~_present_mask(vt1)).sum()),
        "vehicle_type_distinct_raw": _int(all_vehicle.nunique()),
        "vehicle_type_distinct_normalized": _int(normalized_vehicle.nunique()),
        "vehicle_type_codes_present_per_row": {
            str(k): _int(v) for k, v in vehicles_per_row.value_counts().sort_index().items()
        },
    }


def text_fields(df: pd.DataFrame) -> dict[str, Any]:
    """Posta kodu biçimi ve sokak adlarında doldurma boşlukları."""
    zip_text = _as_text(df["zip_code"]).str.strip()
    zip_present = _present_mask(df["zip_code"])
    zip_ok = zip_text.str.fullmatch(r"\d{5}").fillna(False).astype(bool)
    out: dict[str, Any] = {
        "zip_code_missing": _int((~zip_present).sum()),
        "zip_code_invalid_format": _int((zip_present & ~zip_ok).sum()),
    }
    for col in ("on_street_name", "off_street_name", "cross_street_name"):
        t = _as_text(df[col])
        padded = (t.notna() & (t != t.str.strip())).fillna(False).astype(bool)
        out[f"{col}_whitespace_padded"] = _int(padded.sum())
        out[f"{col}_distinct_raw"] = _int(t.nunique())
        out[f"{col}_distinct_stripped_upper"] = _int(t.str.strip().str.upper().nunique())
    return out


def build_profile(df: pd.DataFrame, source_types: dict[str, str] | None = None) -> dict[str, Any]:
    """Tüm EDA bölümlerini tek bir sözlükte toplar. Eksik zorunlu sütunda ``SchemaError`` fırlatır."""
    schema = require_columns(df)
    return {
        "schema": {**schema_summary(df), "validation": schema.as_dict()},
        "column_overview": column_overview(df, source_types),
        "missing_values": missing_values(df),
        "duplicates": duplicates(df),
        "temporal": temporal(df),
        "coordinates": coordinates(df),
        "boroughs": boroughs(df),
        "borough_by_coordinate_class": borough_by_coordinate_class(df),
        "quality_by_year": by_year_quality(df),
        "casualties": casualties(df),
        "categoricals": categoricals(df),
        "text_fields": text_fields(df),
    }
