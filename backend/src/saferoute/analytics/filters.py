"""Kayıt filtreleri: doğrulama, kanonik anahtar ve olay maskesi.

Filtreler yalnızca kümelemeye uygun olaylar (``eligible_for_spatial_clustering``) üzerinde çalışır ve
GERÇEK kayıtları seçer. Filtre uygulamak küme etiketlerini DEĞİŞTİRMEZ: haritada gösterilen etiketler
seçili modelin tam veri etiketleridir. Filtrelenmiş veri üzerinde yeniden kümeleme ayrı bir iştir
(``saferoute.analytics.jobs``).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Mapping

import numpy as np

BOROUGH_CODES = ("MANHATTAN", "BROOKLYN", "QUEENS", "BRONX", "STATEN ISLAND")
UNKNOWN_BOROUGH = len(BOROUGH_CODES)  # ilçe bilgisi olmayan uygun olaylar
# Faz 2 araç kategorileri (involves_<kategori> sütunlarının sırası = bit sırası)
VEHICLE_CATEGORIES = ("PASSENGER_CAR", "SUV", "TAXI_FOR_HIRE", "BUS", "VAN", "TRUCK_COMMERCIAL", "MOTORCYCLE",
                      "BICYCLE", "E_MICROMOBILITY", "EMERGENCY", "OTHER", "UNKNOWN")
EPOCH = dt.date(1970, 1, 1)


class FilterError(ValueError):
    """Geçersiz filtre parametresi (API'de 422)."""


@dataclass(frozen=True)
class FilterSpec:
    """Kayıt filtresi. Boş alan = kısıt yok. Saat aralığı [hour_from, hour_to] kapsayıcıdır;
    hour_from > hour_to gece yarısını aşan aralıktır (ör. 22–4)."""

    boroughs: tuple[str, ...] = ()
    date_from: str | None = None  # YYYY-AA-GG (dahil)
    date_to: str | None = None    # YYYY-AA-GG (dahil)
    years: tuple[int, ...] = ()
    months: tuple[int, ...] = ()   # 1–12
    dows: tuple[int, ...] = ()     # 0 = Pazartesi … 6 = Pazar
    hour_from: int | None = None
    hour_to: int | None = None
    vehicles: tuple[str, ...] = ()  # en az biri kazada varsa
    factor: str | None = None       # beş araç etkeninden herhangi biri eşitse
    injury: Literal["any", "injury", "no_injury"] = "any"
    fatal: Literal["any", "fatal", "non_fatal"] = "any"
    exclude_midnight: bool = False
    extra: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def is_empty(self) -> bool:
        return self.key() == FilterSpec().key()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("extra", None)
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in d.items()}

    def key(self) -> str:
        """Kanonik anahtar (önbellek ve deney kimliği için; değer sırası önemsiz)."""
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)

    def digest(self, n: int = 12) -> str:
        return hashlib.sha256(self.key().encode("utf-8")).hexdigest()[:n]

    def describe_tr(self) -> list[str]:
        """Rapor ve arayüz için Türkçe filtre açıklaması (boşsa 'filtre yok')."""
        out: list[str] = []
        if self.boroughs:
            out.append("İlçe: " + ", ".join(self.boroughs))
        if self.date_from or self.date_to:
            out.append(f"Tarih: {self.date_from or 'başlangıç'} → {self.date_to or 'son kayıt'}")
        if self.years:
            out.append("Yıl: " + ", ".join(map(str, self.years)))
        if self.months:
            out.append("Ay: " + ", ".join(map(str, self.months)))
        if self.dows:
            names = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
            out.append("Gün: " + ", ".join(names[d] for d in self.dows))
        if self.hour_from is not None or self.hour_to is not None:
            out.append(f"Saat: {self.hour_from if self.hour_from is not None else 0:02d}:00–"
                       f"{self.hour_to if self.hour_to is not None else 23:02d}:59")
        if self.vehicles:
            out.append("Araç türü: " + ", ".join(self.vehicles))
        if self.factor:
            out.append(f"Kayıtlı katkı faktörü: {self.factor}")
        if self.injury != "any":
            out.append("Yaralanmalı kazalar" if self.injury == "injury" else "Yaralanmasız kazalar")
        if self.fatal != "any":
            out.append("Ölümlü kazalar" if self.fatal == "fatal" else "Ölümsüz kazalar")
        if self.exclude_midnight:
            out.append("00:00 şüpheli kayıtlar hariç")
        return out or ["Filtre yok (tüm uygun kayıtlar)"]


def _split(v: Any) -> list[str]:
    if v is None or v == "":
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [s.strip() for s in str(v).split(",") if s.strip()]


def _ints(v: Any, name: str, lo: int, hi: int) -> tuple[int, ...]:
    out = []
    for s in _split(v):
        try:
            i = int(s)
        except ValueError:
            raise FilterError(f"{name} tamsayı listesi olmalı: {s!r}") from None
        if not lo <= i <= hi:
            raise FilterError(f"{name} {lo}–{hi} aralığında olmalı: {i}")
        out.append(i)
    return tuple(sorted(set(out)))


def _date(v: Any, name: str) -> str | None:
    if v in (None, ""):
        return None
    try:
        return dt.date.fromisoformat(str(v)).isoformat()
    except ValueError:
        raise FilterError(f"{name} YYYY-AA-GG biçiminde olmalı: {v!r}") from None


def _hour(v: Any, name: str) -> int | None:
    if v in (None, ""):
        return None
    try:
        h = int(v)
    except (TypeError, ValueError):
        raise FilterError(f"{name} 0–23 arası tamsayı olmalı: {v!r}") from None
    if not 0 <= h <= 23:
        raise FilterError(f"{name} 0–23 arası olmalı: {h}")
    return h


def _bool(v: Any) -> bool:
    return str(v).lower() in ("1", "true", "evet", "yes", "on")


def parse_filters(q: Mapping[str, Any], factors: set[str] | None = None) -> FilterSpec:
    """Sorgu parametrelerinden (veya JSON gövdesinden) doğrulanmış ``FilterSpec``."""
    boroughs = tuple(sorted({b.upper() for b in _split(q.get("boroughs"))}))
    if bad := [b for b in boroughs if b not in BOROUGH_CODES]:
        raise FilterError(f"Bilinmeyen ilçe: {bad}")
    vehicles = tuple(sorted({v.upper() for v in _split(q.get("vehicles"))}))
    if bad := [v for v in vehicles if v not in VEHICLE_CATEGORIES]:
        raise FilterError(f"Bilinmeyen araç kategorisi: {bad}")
    date_from, date_to = _date(q.get("date_from"), "date_from"), _date(q.get("date_to"), "date_to")
    if date_from and date_to and date_from > date_to:
        raise FilterError("Başlangıç tarihi bitiş tarihinden sonra olamaz.")
    hour_from, hour_to = _hour(q.get("hour_from"), "hour_from"), _hour(q.get("hour_to"), "hour_to")
    if (hour_from is None) != (hour_to is None):
        raise FilterError("Saat aralığı için hour_from ve hour_to birlikte verilmeli.")
    factor = q.get("factor") or None
    if factor is not None:
        factor = str(factor)
        if factors is not None and factor not in factors:
            raise FilterError(f"Veride bulunmayan katkı faktörü: {factor!r}")
    injury = str(q.get("injury") or "any")
    fatal = str(q.get("fatal") or "any")
    if injury not in ("any", "injury", "no_injury"):
        raise FilterError(f"injury 'any', 'injury' veya 'no_injury' olmalı: {injury!r}")
    if fatal not in ("any", "fatal", "non_fatal"):
        raise FilterError(f"fatal 'any', 'fatal' veya 'non_fatal' olmalı: {fatal!r}")
    return FilterSpec(
        boroughs=boroughs, date_from=date_from, date_to=date_to,
        years=_ints(q.get("years"), "years", 1900, 2100), months=_ints(q.get("months"), "months", 1, 12),
        dows=_ints(q.get("dows"), "dows", 0, 6), hour_from=hour_from, hour_to=hour_to, vehicles=vehicles,
        factor=factor, injury=injury, fatal=fatal,  # type: ignore[arg-type]
        exclude_midnight=_bool(q.get("exclude_midnight", False)),
    )


def date_to_days(iso: str) -> int:
    return (dt.date.fromisoformat(iso) - EPOCH).days


def days_to_date(days: int) -> str:
    return (EPOCH + dt.timedelta(days=int(days))).isoformat()


def build_mask(cols: Mapping[str, np.ndarray], spec: FilterSpec, factor_code: int | None = None) -> np.ndarray:
    """Olay maskesi. ``cols``: ``borough`` (kod), ``days``, ``year``, ``month``, ``dow``, ``hour``,
    ``vehicle_bits``, ``factors`` ((n, 5) kod), ``injury``, ``fatal``, ``midnight``."""
    n = len(cols["days"])
    m = np.ones(n, dtype=bool)
    if spec.boroughs:
        m &= np.isin(cols["borough"], [BOROUGH_CODES.index(b) for b in spec.boroughs])
    if spec.date_from:
        m &= cols["days"] >= date_to_days(spec.date_from)
    if spec.date_to:
        m &= cols["days"] <= date_to_days(spec.date_to)
    if spec.years:
        m &= np.isin(cols["year"], spec.years)
    if spec.months:
        m &= np.isin(cols["month"], spec.months)
    if spec.dows:
        m &= np.isin(cols["dow"], spec.dows)
    if spec.hour_from is not None and spec.hour_to is not None:
        h = cols["hour"]
        if spec.hour_from <= spec.hour_to:
            m &= (h >= spec.hour_from) & (h <= spec.hour_to)
        else:  # gece yarısını aşan aralık
            m &= (h >= spec.hour_from) | (h <= spec.hour_to)
    if spec.vehicles:
        bits = 0
        for v in spec.vehicles:
            bits |= 1 << VEHICLE_CATEGORIES.index(v)
        m &= (cols["vehicle_bits"] & bits) != 0
    if spec.factor is not None:
        if factor_code is None:
            m &= False
        else:
            m &= (cols["factors"] == factor_code).any(axis=1)
    if spec.injury == "injury":
        m &= cols["injury"]
    elif spec.injury == "no_injury":
        m &= ~cols["injury"]
    if spec.fatal == "fatal":
        m &= cols["fatal"]
    elif spec.fatal == "non_fatal":
        m &= ~cols["fatal"]
    if spec.exclude_midnight:
        m &= ~cols["midnight"]
    return m
