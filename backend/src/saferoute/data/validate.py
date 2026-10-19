"""Ham veri şeması ve alan değeri doğrulama kuralları.

Bu modül veriyi değiştirmez; yalnızca yapısal sorunları (eksik/beklenmeyen sütun, boş
girdi) ve satır düzeyi geçersizlikleri tespit eden maskeler üretir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from saferoute import config

EXPECTED_COLUMNS: tuple[str, ...] = (
    "crash_date", "crash_time", "borough", "zip_code", "latitude", "longitude", "location",
    "on_street_name", "off_street_name", "cross_street_name",
    "number_of_persons_injured", "number_of_persons_killed",
    "number_of_pedestrians_injured", "number_of_pedestrians_killed",
    "number_of_cyclist_injured", "number_of_cyclist_killed",
    "number_of_motorist_injured", "number_of_motorist_killed",
    "contributing_factor_vehicle_1", "contributing_factor_vehicle_2", "contributing_factor_vehicle_3",
    "contributing_factor_vehicle_4", "contributing_factor_vehicle_5",
    "collision_id", "vehicle_type_code1", "vehicle_type_code2", "vehicle_type_code_3",
    "vehicle_type_code_4", "vehicle_type_code_5",
)


class SchemaError(ValueError):
    """Analiz için zorunlu sütunlar eksik olduğunda fırlatılır."""


@dataclass
class SchemaReport:
    row_count: int
    missing_columns: list[str] = field(default_factory=list)
    unexpected_columns: list[str] = field(default_factory=list)
    order_matches: bool = True

    @property
    def is_valid(self) -> bool:
        return not self.missing_columns

    @property
    def is_empty(self) -> bool:
        return self.row_count == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "row_count": self.row_count,
            "missing_columns": self.missing_columns,
            "unexpected_columns": self.unexpected_columns,
            "order_matches": self.order_matches,
            "is_valid": self.is_valid,
            "is_empty": self.is_empty,
        }


def check_schema(df: pd.DataFrame, expected: tuple[str, ...] = EXPECTED_COLUMNS) -> SchemaReport:
    """Sütun kümesini beklenen şemayla karşılaştırır (hata fırlatmaz)."""
    cols = list(df.columns)
    return SchemaReport(
        row_count=len(df),
        missing_columns=[c for c in expected if c not in cols],
        unexpected_columns=[c for c in cols if c not in expected],
        order_matches=tuple(cols) == tuple(expected),
    )


def require_columns(df: pd.DataFrame, expected: tuple[str, ...] = EXPECTED_COLUMNS) -> SchemaReport:
    """Eksik sütun varsa ``SchemaError`` fırlatır; aksi hâlde raporu döndürür."""
    report = check_schema(df, expected)
    if not report.is_valid:
        raise SchemaError(f"Eksik sütun(lar): {', '.join(report.missing_columns)}")
    return report


def null_percentage(missing: int, total: int) -> float:
    """Eksik yüzdesi; boş girdide (total=0) 0.0 döner, sıfıra bölme yapılmaz."""
    if total < 0 or missing < 0 or missing > total:
        raise ValueError("Geçersiz sayım: 0 <= missing <= total olmalı")
    return round(100.0 * missing / total, 4) if total else 0.0


def parse_crash_date(s: pd.Series) -> pd.Series:
    """Socrata ``floating_timestamp`` biçimini (``YYYY-MM-DDTHH:MM:SS.fff``) ayrıştırır; geçersiz -> NaT."""
    text = s.astype("string[pyarrow]").str.strip().astype(object)
    return pd.to_datetime(text, format="%Y-%m-%dT%H:%M:%S.%f", errors="coerce")


def parse_crash_time(s: pd.Series) -> pd.DataFrame:
    """``H:MM`` / ``HH:MM`` biçimini ayrıştırır. Dönüş: ``hour``, ``minute``, ``valid`` sütunları."""
    text = s.astype("string[pyarrow]").str.strip()
    parts = text.str.extract(r"^(\d{1,2}):(\d{2})$")
    hour = pd.to_numeric(parts[0].astype(object), errors="coerce")
    minute = pd.to_numeric(parts[1].astype(object), errors="coerce")
    valid = (hour.between(0, 23) & minute.between(0, 59)).fillna(False).astype(bool)
    return pd.DataFrame({"hour": hour.where(valid), "minute": minute.where(valid), "valid": valid}, index=s.index)


def borough_status(s: pd.Series) -> pd.Series:
    """İlçe etiketini sınıflar: ``valid`` (5 resmi ilçeden biri), ``missing`` veya ``unexpected``."""
    text = s.astype("string[pyarrow]").str.strip()
    present = (text.notna() & (text != "")).fillna(False).astype(bool)
    known = text.str.upper().isin(config.BOROUGHS).fillna(False).astype(bool)
    out = pd.Series("unexpected", index=s.index, dtype="object")
    out[~present] = "missing"
    out[present & known] = "valid"
    return out
