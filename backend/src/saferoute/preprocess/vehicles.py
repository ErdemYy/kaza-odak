"""Araç türü standardizasyonu: ham etiket -> normalize etiket -> üst kategori.

Adımlar:
  1. Normalizasyon: baş/son boşluk kırpma, iç boşlukları tekleme, büyük harf.
  2. Sıralı ve açık kurallar (ilk eşleşen kazanır). Her etiketin hangi kuralla
     eşlendiği eşleme tablosunda saklanır.
  3. Hiçbir kurala uymayan etiket bir kategoriye ZORLA atanmaz: ``OTHER`` altında
     ``unmatched`` kuralıyla tutulur ve ayrıca raporlanır.

Kategori kodları İngilizce, rapor etiketleri Türkçedir.
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from saferoute.eda.profile import VEHICLE_COLUMNS

CATEGORY_LABELS_TR = {
    "PASSENGER_CAR": "Binek otomobil",
    "SUV": "SUV / station wagon",
    "TAXI_FOR_HIRE": "Taksi / kiralık araç",
    "BUS": "Otobüs",
    "VAN": "Van / minibüs",
    "TRUCK_COMMERCIAL": "Kamyon / ticari",
    "MOTORCYCLE": "Motosiklet / moped",
    "BICYCLE": "Bisiklet",
    "E_MICROMOBILITY": "Elektrikli mikromobilite",
    "EMERGENCY": "Acil durum aracı",
    "OTHER": "Diğer",
    "UNKNOWN": "Bilinmiyor",
}

# (kural adı, kategori, düzenli ifade) — SIRA ÖNEMLİDİR: özel kurallar genel kurallardan önce.
RULES: list[tuple[str, str, str]] = [
    ("unknown_tokens", "UNKNOWN", r"^(UNKNOWN( VE.*)?|UNK|UNKN|UNKNO|UNKOW|N/?A|NONE|UNSPECIFIED)$"),
    ("emergency", "EMERGENCY",
     r"AMBUL|^AMBU$|^AMB$|^EMS$|FDNY|FIRE|^POLI|POLICE|^RMP$|NYPD|NYS AMBULA"),
    ("e_micromobility", "E_MICROMOBILITY",
     r"^E[- ]?BIK|^EBIK|^E[- ]?SCO|E-SCOOTER|^ELECTRIC S|^E-SKATE|^ESKATE|^E-UNI|^ONE WHEEL"),
    ("bus", "BUS", r"\bBUS\b|^SCHOO|^MTA B"),
    ("taxi_for_hire", "TAXI_FOR_HIRE", r"TAXI|^CAB$|LIVERY|^LIMO|^YELLO|^GREEN TAXI|FOR HIRE"),
    ("motorcycle", "MOTORCYCLE",
     r"MOTORCYCLE|MOTORBIKE|^MOPE?D|MOTORSCOOT|MOTOR SCOO|^MOTOR$|MINIBIKE|MINI BIKE|DIRT BIKE|MINICYCLE|GAS SCOOT|^VESPA"),
    ("bicycle", "BICYCLE", r"^BIKE$|BICYCLE|^BICY|^BIKE "),
    ("suv", "SUV", r"SPORT UTILITY|STATION WAGON|^SUV$|^SUBN$|^SUBUR|^CARRY ALL$|^WAGON$"),
    ("passenger_car", "PASSENGER_CAR",
     r"SEDAN|PASSENGER VEHICLE|^PASSENGER$|^PASS$|^PAS$|CONVERTIBLE|^3-DOOR$|^2 DR|^4 DR|COUPE|HATCHBACK"),
    ("refrigerated_truck", "TRUCK_COMMERCIAL", r"REFRIGERATED|^REFG"),
    ("van", "VAN", r"\bVAN\b|VANETTE|^SPRIN|MINIVAN"),
    ("truck_commercial", "TRUCK_COMMERCIAL",
     r"TRUCK|^PICK|^PK$|^BOX|COM VEH|^TRACT|^TRAC$|DUMP|FLAT|GARBAGE|^GARBA|SANIT|^TOW|CHASSIS|TANK"
     r"|CONCRETE|CMIX|CEMEN|ARMORED|BEVERAGE|^TRK$|^TK$|STAKE|^STAK|^DELV|^DELIV|UTIL|USPS|^POSTA"
     r"|^US PO|POSTAL|^MAIL|^COM$|^COMM|COMMERCIAL|LIFT BOOM|OPEN BODY|FREIG|^MACK$|^HINO$|^SEMI"
     r"|SNOW PLOW|SWEEP|STREET SWE|LUNCH WAGON|^FOOD|BULK AGRIC|RACK|HOPPER|WELL DRILL"
     r"|ENCLOSED BODY|MULTI-WHEELED|^F[0-9]{3}$|U-?HAU|^LOG$|^CARGO$|^TRAIL|^TRL|^TRLR$|^TRAILOR"),
    ("other_explicit", "OTHER", r"^OTHER$"),
    ("special_equipment", "OTHER",
     r"FORK|BOBCA|BACKH|EXCAV|CRANE|BULLD|POWER SHOV|^P/SH|LOADER|^GATOR$|^UTV$|GOLF|SKATEBOARD"
     r"|HORSE|CARRIAGE|PEDICAB|MOTORIZED HOME|MOTOR HOME|^RV$"),
    ("ambiguous_scooter", "OTHER", r"^SCOOT|^SCOOTER$"),
]
_COMPILED = [(name, cat, re.compile(pat)) for name, cat, pat in RULES]


def normalize_label(label: str | None) -> str | None:
    if label is None or (isinstance(label, float) and np.isnan(label)):
        return None
    text = re.sub(r"\s+", " ", str(label)).strip().upper()
    return text or None


def categorize(normalized: str | None) -> tuple[str, str]:
    """Normalize etiketi (kategori, kural) çiftine eşler. Boş -> (UNKNOWN, missing)."""
    if normalized is None:
        return "UNKNOWN", "missing"
    for name, cat, pattern in _COMPILED:
        if pattern.search(normalized):
            return cat, name
    return "OTHER", "unmatched"


def build_mapping_table(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """Tüm araç sütunlarındaki her normalize etiket için kategori, kural ve frekans tablosu."""
    columns = columns or VEHICLE_COLUMNS
    raw = pd.concat([df[c] for c in columns], ignore_index=True).dropna().astype(str)
    raw_counts = raw.value_counts()
    norm = raw_counts.index.map(normalize_label)
    rows = (pd.DataFrame({"raw_label": raw_counts.index, "normalized": norm, "count": raw_counts.to_numpy()})
            .groupby("normalized", as_index=False)
            .agg(count=("count", "sum"), raw_variants=("raw_label", "nunique")))
    mapped = rows["normalized"].map(categorize)
    rows["category"] = [m[0] for m in mapped]
    rows["rule"] = [m[1] for m in mapped]
    rows["category_tr"] = rows["category"].map(CATEGORY_LABELS_TR)
    return rows.sort_values(["count", "normalized"], ascending=[False, True]).reset_index(drop=True)


def add_vehicle_features(df: pd.DataFrame, mapping: pd.DataFrame,
                         columns: list[str] | None = None) -> pd.DataFrame:
    """Her araç sütunu için kategori sütunu ve kaza düzeyinde 'involves_<kategori>' bayrakları."""
    columns = columns or VEHICLE_COLUMNS
    lookup = dict(zip(mapping["normalized"], mapping["category"]))
    out = pd.DataFrame(index=df.index)
    cats = list(CATEGORY_LABELS_TR)
    involved = {c: np.zeros(len(df), dtype=bool) for c in cats}
    for i, col in enumerate(columns, start=1):
        norm = df[col].astype("string").str.strip().str.replace(r"\s+", " ", regex=True).str.upper()
        cat = norm.map(lookup).astype(object)
        present = df[col].notna().to_numpy()
        cat = np.where(present, cat.to_numpy(), None)
        out[f"vehicle_category_{i}"] = pd.Categorical(cat, categories=cats)
        for c in cats:
            involved[c] |= cat == c
    for c in cats:
        out[f"involves_{c.lower()}"] = involved[c]
    out["vehicle_count_reported"] = sum(df[c].notna().astype("int8") for c in columns).astype("int8")
    return out


def mapping_summary(mapping: pd.DataFrame, raw_distinct: int) -> dict[str, Any]:
    by_cat = mapping.groupby("category")["count"].sum().sort_values(ascending=False)
    unmatched = mapping[mapping["rule"] == "unmatched"]
    total = int(mapping["count"].sum())
    return {
        "raw_distinct_labels": int(raw_distinct),
        "normalized_distinct_labels": int(len(mapping)),
        "category_count": int(mapping["category"].nunique()),
        "label_mentions": total,
        "by_category": {k: int(v) for k, v in by_cat.items()},
        "by_rule": {k: int(v) for k, v in mapping.groupby("rule")["count"].sum().sort_values(ascending=False).items()},
        "unmatched_labels": int(len(unmatched)),
        "unmatched_mentions": int(unmatched["count"].sum()),
        "unmatched_mentions_pct": round(100.0 * unmatched["count"].sum() / total, 4) if total else 0.0,
        "top_unmatched": {r.normalized: int(r.count) for r in unmatched.head(25).itertuples()},
        "rules": [{"rule": n, "category": c, "pattern": p} for n, c, p in RULES],
    }
