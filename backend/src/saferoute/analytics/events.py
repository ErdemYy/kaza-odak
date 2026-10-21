"""Olay deposu: kümelemeye uygun 2 milyon olayın filtre sütunları bellekte (NumPy) tutulur.

Tasarım:
* Olay sırası Faz 2 ``crashes_processed.parquet`` içindeki uygun olay sırasıdır (Faz 3
  ``EventData`` ve etiket dosyalarındaki ``event_index`` ile aynı). Bu sayede kayıtlı deney
  etiketleri bu depoya doğrudan bağlanır.
* Koordinatlar konum düzeyinde tutulur (olay koordinatı = konum koordinatı; Faz 3 hizalama
  denetimi ``event_coords_equal_location_coords``).
* Mevcut model etiketleri Faz 4 ``locations_layer.parquet``'ten konum başına okunur. Filtre
  uygulamak bu etiketleri değiştirmez; filtrelenmiş kayıtlar tam veri kümelerinde gösterilir.
* Maske hesapları LRU önbelleğindedir; tüm toplamlar ``np.bincount`` ile yapılır.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from saferoute.analytics.filters import (
    BOROUGH_CODES, UNKNOWN_BOROUGH, VEHICLE_CATEGORIES, FilterSpec, build_mask, days_to_date,
)

FACTOR_COLUMNS = [f"contributing_factor_vehicle_{i}" for i in range(1, 6)]
INVOLVES_COLUMNS = [f"involves_{v.lower()}" for v in VEHICLE_CATEGORIES]
EVENT_COLUMNS = ["collision_id", "location_id", "eligible_for_spatial_clustering", "days_since_epoch", "crash_year",
                 "crash_month", "day_of_week", "crash_hour", "borough_final", "midnight_suspect_flag",
                 "has_reported_injury", "has_reported_fatality", "number_of_persons_injured",
                 "number_of_persons_killed", *FACTOR_COLUMNS, *INVOLVES_COLUMNS]
MASK_CACHE_SIZE = 48


@dataclass
class EventColumns:
    """Bellekteki olay sütunları (uygun olaylar, Faz 2 sırası)."""

    collision_id: np.ndarray
    location: np.ndarray       # int32 konum indeksi
    days: np.ndarray           # int32, 1970'ten gün
    year: np.ndarray
    month: np.ndarray
    dow: np.ndarray            # 0 = Pazartesi
    hour: np.ndarray
    borough: np.ndarray        # int8 BOROUGH_CODES indeksi; UNKNOWN_BOROUGH = bilinmiyor
    midnight: np.ndarray
    injury: np.ndarray
    fatal: np.ndarray
    persons_injured: np.ndarray
    persons_killed: np.ndarray
    vehicle_bits: np.ndarray   # uint16, VEHICLE_CATEGORIES bit sırası
    factors: np.ndarray        # (n, 5) int16; −1 = boş
    factor_names: list[str]

    def as_mapping(self) -> dict[str, np.ndarray]:
        return {"borough": self.borough, "days": self.days, "year": self.year, "month": self.month, "dow": self.dow,
                "hour": self.hour, "vehicle_bits": self.vehicle_bits, "factors": self.factors, "injury": self.injury,
                "fatal": self.fatal, "midnight": self.midnight}


def columns_from_frame(df: pd.DataFrame) -> EventColumns:
    """İşlenmiş kayıt tablosundan (yalnızca uygun olaylar) bellek sütunları üretir."""
    e = df[df["eligible_for_spatial_clustering"].astype(bool)] if "eligible_for_spatial_clustering" in df else df
    # Kategorik kodlama: satır başına Python dizesi oluşturulmaz (bellek), kodlar ortak sözlüğe eşlenir.
    bcat = e["borough_final"].astype("category")
    blut = np.array([BOROUGH_CODES.index(b) if b in BOROUGH_CODES else UNKNOWN_BOROUGH
                     for b in bcat.cat.categories] + [UNKNOWN_BOROUGH], dtype=np.int8)
    borough = blut[bcat.cat.codes.to_numpy()]  # kod −1 (eksik) → son eleman = bilinmiyor
    # Etken kodları: beş sütunun ortak sözlüğü (veri kümesindeki gerçek NYPD metinleri)
    cats = [e[c].astype("category") for c in FACTOR_COLUMNS]
    uniques = sorted({str(v) for cat in cats for v in cat.cat.categories})
    index = {v: i for i, v in enumerate(uniques)}
    factors = np.empty((len(e), len(FACTOR_COLUMNS)), dtype=np.int16)
    for j, cat in enumerate(cats):
        lut = np.array([index[str(v)] for v in cat.cat.categories] + [-1], dtype=np.int16)
        factors[:, j] = lut[cat.cat.codes.to_numpy()]
    bits = np.zeros(len(e), dtype=np.uint16)
    for i, c in enumerate(INVOLVES_COLUMNS):
        if c in e:
            bits |= (e[c].fillna(False).to_numpy(bool).astype(np.uint16) << i)

    def ints(c: str, dtype: Any) -> np.ndarray:
        return e[c].fillna(0).to_numpy().astype(dtype)

    return EventColumns(
        collision_id=e["collision_id"].to_numpy(dtype=np.int64), location=e["location_id"].to_numpy().astype(np.int32),
        days=ints("days_since_epoch", np.int32), year=ints("crash_year", np.int16), month=ints("crash_month", np.int8),
        dow=ints("day_of_week", np.int8), hour=ints("crash_hour", np.int8), borough=borough,
        midnight=e["midnight_suspect_flag"].fillna(False).to_numpy(bool),
        injury=e["has_reported_injury"].fillna(False).to_numpy(bool),
        fatal=e["has_reported_fatality"].fillna(False).to_numpy(bool),
        persons_injured=ints("number_of_persons_injured", np.int32),
        persons_killed=ints("number_of_persons_killed", np.int32),
        vehicle_bits=bits, factors=factors, factor_names=uniques,
    )


class EventStore:
    """Filtrelenebilir olay deposu + konum tablosu + mevcut modelin konum etiketleri."""

    def __init__(self, cols: EventColumns, locations: pd.DataFrame, location_cluster: np.ndarray,
                 experiment_id: str, cell_index: dict[int, np.ndarray] | None = None,
                 cell_centers: dict[int, np.ndarray] | None = None):
        self.c = cols
        self.n_events = len(cols.days)
        self.loc_lon = locations["longitude"].to_numpy(float)
        self.loc_lat = locations["latitude"].to_numpy(float)
        self.loc_x = locations["x_m"].to_numpy(float)
        self.loc_y = locations["y_m"].to_numpy(float)
        self.loc_rad = ((locations["lat_rad"].to_numpy(float), locations["lon_rad"].to_numpy(float))
                        if "lat_rad" in locations else None)
        self.n_locations = len(self.loc_lon)
        if len(location_cluster) != self.n_locations:
            raise ValueError("Konum etiketi sayısı konum tablosuyla aynı değil.")
        self.loc_cluster = location_cluster.astype(np.int32)
        self.experiment_id = experiment_id
        self.factor_lookup = {name: i for i, name in enumerate(cols.factor_names)}
        self._masks: OrderedDict[str, np.ndarray] = OrderedDict()
        self._summaries: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._options: dict[str, Any] | None = None
        self._lock = threading.Lock()
        self.cell_index = cell_index or {}
        self.cell_centers = cell_centers or {}
        n_clusters = int(self.loc_cluster.max()) + 1 if (self.loc_cluster >= 0).any() else 0
        self.n_clusters = n_clusters
        self.event_cluster = self.loc_cluster[cols.location]

    # ------------------------------------------------------------------ yükleme
    @classmethod
    def from_processed(cls, pdir: Path, layers_dir: Path, experiment_id: str) -> "EventStore":
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pq.read_table(Path(pdir) / "crashes_processed.parquet", columns=EVENT_COLUMNS,
                              read_dictionary=[*FACTOR_COLUMNS, "borough_final"])
        df = table.to_pandas()
        del table
        cols = columns_from_frame(df)
        del df
        pa.default_memory_pool().release_unused()
        lpath = Path(pdir) / "locations.parquet"
        want = ["location_id", "latitude", "longitude", "x_m", "y_m", "lat_rad", "lon_rad", "weight"]
        have = set(pq.read_schema(lpath).names)
        locs = pd.read_parquet(lpath, columns=[c for c in want if c in have])
        if not np.array_equal(locs["location_id"].to_numpy(), np.arange(len(locs))):
            raise ValueError("Konum kimlikleri ardışık değil; olay → konum eşlemesi güvenilmez.")
        if not np.array_equal(np.bincount(cols.location, minlength=len(locs)), locs["weight"].to_numpy()):
            raise ValueError("Olay sayıları konum ağırlıklarıyla uyuşmuyor (Faz 2 hizalaması bozuk).")
        layer = pd.read_parquet(Path(layers_dir) / "locations_layer.parquet", columns=["location_id", "cluster_id"])
        lc = np.full(len(locs), -1, dtype=np.int32)
        lc[layer["location_id"].to_numpy()] = layer["cluster_id"].to_numpy()
        cells, centers = {}, {}
        for cell in (1000, 250):
            p = Path(layers_dir) / f"density_{cell}m.parquet"
            if p.exists():
                cells[cell], centers[cell] = density_cells(locs["x_m"].to_numpy(), locs["y_m"].to_numpy(),
                                                           pd.read_parquet(p), cell)
        return cls(cols, locs, lc, experiment_id, cells, centers)

    # ------------------------------------------------------------------ maske
    def mask(self, spec: FilterSpec) -> np.ndarray:
        key = spec.key()
        with self._lock:
            if key in self._masks:
                self._masks.move_to_end(key)
                return self._masks[key]
        code = self.factor_lookup.get(spec.factor) if spec.factor else None
        m = build_mask(self.c.as_mapping(), spec, code)
        m.setflags(write=False)
        with self._lock:
            self._masks[key] = m
            while len(self._masks) > MASK_CACHE_SIZE:
                self._masks.popitem(last=False)
        return m

    # ------------------------------------------------------------------ seçenekler
    def options(self) -> dict[str, Any]:
        """Filtre seçenekleri ve kayıt sayıları (değişmez veri: bir kez hesaplanır)."""
        if self._options is None:
            self._options = self._compute_options()
        return self._options

    def _compute_options(self) -> dict[str, Any]:
        c = self.c
        years = np.bincount(c.year - c.year.min(), minlength=1)
        y0 = int(c.year.min())
        flat = c.factors[c.factors >= 0]
        fcount = np.bincount(flat, minlength=len(c.factor_names))
        factors = sorted(({"value": c.factor_names[i], "count": int(fcount[i])} for i in range(len(c.factor_names))),
                         key=lambda r: -r["count"])
        return {
            "date_min": days_to_date(int(c.days.min())), "date_max": days_to_date(int(c.days.max())),
            "years": [{"year": y0 + i, "count": int(v)} for i, v in enumerate(years) if v],
            "boroughs": [{"value": b, "count": int((c.borough == i).sum())} for i, b in enumerate(BOROUGH_CODES)],
            "borough_unknown": int((c.borough == UNKNOWN_BOROUGH).sum()),
            "vehicles": [{"value": v, "count": int(((c.vehicle_bits >> i) & 1).sum())}
                         for i, v in enumerate(VEHICLE_CATEGORIES)],
            "factors": factors, "midnight_suspect": int(c.midnight.sum()), "n_events": self.n_events,
            "factor_count_unit": "Beş araç etken alanında geçme sayısı (bir kazada birden fazla olabilir)",
        }

    # ------------------------------------------------------------------ özet
    def summary(self, spec: FilterSpec) -> dict[str, Any]:
        """Filtrelenmiş GERÇEK kayıtların özeti; küme etiketleri mevcut modelden (yeniden kümeleme yok).
        Veri değişmez olduğundan sonuç filtre anahtarıyla önbelleğe alınır."""
        key = spec.key()
        with self._lock:
            hit = self._summaries.get(key)
        if hit is not None:
            return hit
        out = self._summary(spec)
        with self._lock:
            self._summaries[key] = out
            while len(self._summaries) > MASK_CACHE_SIZE:
                self._summaries.popitem(last=False)
        return out

    def _summary(self, spec: FilterSpec) -> dict[str, Any]:
        m = self.mask(spec)
        c = self.c
        n = int(m.sum())
        y0 = int(c.year.min())
        ec = self.event_cluster[m]
        clustered = int((ec >= 0).sum())
        out: dict[str, Any] = {
            "filters": spec.to_dict(), "filters_tr": spec.describe_tr(), "denominator": "kümelemeye uygun olaylar",
            "n_events_total": self.n_events, "n_events": n, "share_of_total": n / self.n_events if self.n_events else None,
            "injury_crashes": int(c.injury[m].sum()), "fatal_crashes": int(c.fatal[m].sum()),
            "persons_injured": int(c.persons_injured[m].sum()), "persons_killed": int(c.persons_killed[m].sum()),
            "midnight_suspect": int(c.midnight[m].sum()),
            "date_min": days_to_date(int(c.days[m].min())) if n else None,
            "date_max": days_to_date(int(c.days[m].max())) if n else None,
            "model": {"experiment_id": self.experiment_id, "label_source": "tam veri modeli (yeniden kümeleme yok)",
                      "events_in_clusters": clustered, "events_noise": n - clustered,
                      "clusters_with_events": int(len(np.unique(ec[ec >= 0]))), "clusters_total": self.n_clusters},
            "by_year": [{"year": y0 + i, "count": int(v)} for i, v in enumerate(np.bincount(c.year[m] - y0, minlength=int(c.year.max()) - y0 + 1))],
            "by_month": [int(v) for v in np.bincount(c.month[m], minlength=13)[1:13]],
            "by_dow": [int(v) for v in np.bincount(c.dow[m], minlength=7)[:7]],
            "by_hour": [int(v) for v in np.bincount(c.hour[m], minlength=24)[:24]],
            "by_borough": self._by_borough(m),
            "by_vehicle": [{"value": v, "count": int((((c.vehicle_bits[m] >> i) & 1)).sum())}
                           for i, v in enumerate(VEHICLE_CATEGORIES)],
            "top_factors": self._top_factors(m, 12), "factor_unspecified_share": self.factor_unspecified_share(m),
            "factor_definition": "Kaza başına: etken beş araç alanından herhangi birinde geçiyorsa bir kez sayılır; "
                                 "'Unspecified' sıralamada yok, araç 1 için payı ayrıca verilir.",
        }
        return out

    def _by_borough(self, m: np.ndarray) -> list[dict[str, Any]]:
        c = self.c
        b = c.borough[m]
        k = UNKNOWN_BOROUGH + 1
        ev = np.bincount(b, minlength=k)
        inj = np.bincount(b, weights=c.injury[m], minlength=k)
        fat = np.bincount(b, weights=c.fatal[m], minlength=k)
        pin = np.bincount(b, weights=c.persons_injured[m], minlength=k)
        pki = np.bincount(b, weights=c.persons_killed[m], minlength=k)
        clu = np.bincount(b, weights=self.event_cluster[m] >= 0, minlength=k)
        names = [*BOROUGH_CODES, "UNKNOWN"]
        return [{"borough": names[i], "events": int(ev[i]), "injury_crashes": int(inj[i]), "fatal_crashes": int(fat[i]),
                 "persons_injured": int(pin[i]), "persons_killed": int(pki[i]), "events_in_clusters": int(clu[i])}
                for i in range(k)]

    def _top_factors(self, m: np.ndarray, top: int) -> list[dict[str, Any]]:
        """Kaza başına etken: beş araç etken alanından herhangi birinde geçen kaza bir kez sayılır.
        'Unspecified' (belirtilmemiş) sıralamaya alınmaz; oranı ``factor_unspecified_share`` ile verilir."""
        f = np.sort(self.c.factors[m], axis=1)  # satır içi sıralama: aynı etkenin tekrarları yan yana
        n = int(m.sum())
        keep = f >= 0
        keep[:, 1:] &= f[:, 1:] != f[:, :-1]
        counts = np.bincount(f[keep], minlength=len(self.c.factor_names)).astype(np.int64)
        unspec = self.factor_lookup.get("Unspecified")
        if unspec is not None:
            counts[unspec] = 0
        order = np.argsort(-counts, kind="stable")[:top]
        return [{"value": self.c.factor_names[i], "crashes": int(counts[i]), "share": float(counts[i] / n) if n else None}
                for i in order if counts[i] > 0]

    def factor_unspecified_share(self, m: np.ndarray) -> float | None:
        """Araç 1 etkeni 'Unspecified' olan kazaların payı; payda araç 1 etkeni dolu kazalar
        (Faz 3 ``factor_unspecified_share`` tanımı)."""
        unspec = self.factor_lookup.get("Unspecified")
        f1 = self.c.factors[m, 0]
        n = int((f1 >= 0).sum())
        if unspec is None or not n:
            return None
        return float((f1 == unspec).sum() / n)

    # ------------------------------------------------------------------ zaman çizelgesi
    def timeline(self, spec: FilterSpec, granularity: str) -> dict[str, Any]:
        out = self.timeline_mask(self.mask(spec), granularity)
        return {**out, "filters": spec.to_dict()}

    def timeline_mask(self, m: np.ndarray, granularity: str) -> dict[str, Any]:
        """Verilen olay maskesinin zaman kovaları (filtre veya bir sonucun olay kapsamı)."""
        c = self.c
        if granularity == "year":
            y0 = int(c.year.min())
            v = np.bincount(c.year[m] - y0, minlength=int(c.year.max()) - y0 + 1)
            buckets = [{"key": str(y0 + i), "count": int(x)} for i, x in enumerate(v)]
        elif granularity == "month":
            ym = (c.year.astype(np.int32) * 12 + c.month.astype(np.int32) - 1)
            lo, hi = int(ym.min()), int(ym.max())
            v = np.bincount(ym[m] - lo, minlength=hi - lo + 1)
            buckets = [{"key": f"{(lo + i) // 12}-{(lo + i) % 12 + 1:02d}", "count": int(x)} for i, x in enumerate(v)]
        elif granularity == "hour":
            buckets = [{"key": f"{h:02d}", "count": int(x)} for h, x in enumerate(np.bincount(c.hour[m], minlength=24)[:24])]
        elif granularity == "dow":
            buckets = [{"key": str(d), "count": int(x)} for d, x in enumerate(np.bincount(c.dow[m], minlength=7)[:7])]
        else:
            raise ValueError("granularity: year, month, hour veya dow olmalı")
        return {"granularity": granularity, "n_events": int(m.sum()), "buckets": buckets}

    # ------------------------------------------------------------------ harita katmanları
    def location_counts(self, m: np.ndarray) -> np.ndarray:
        return np.bincount(self.c.location[m], minlength=self.n_locations)

    def density(self, spec: FilterSpec, cell: int) -> dict[str, Any]:
        if cell not in self.cell_index:
            raise KeyError(cell)
        m = self.mask(spec)
        idx = self.cell_index[cell]
        loc_ev = self.location_counts(m)
        k = len(self.cell_centers[cell])
        ev = np.bincount(idx, weights=loc_ev, minlength=k)
        cl = np.bincount(idx, weights=loc_ev * (self.loc_cluster >= 0), minlength=k)
        nz = np.flatnonzero(ev > 0)
        ctr = self.cell_centers[cell]
        feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(float(ctr[i, 0]), 6), round(float(ctr[i, 1]), 6)]},
                  "properties": {"events": int(ev[i]), "clustered": int(cl[i]), "noise": int(ev[i] - cl[i])}} for i in nz]
        return {"type": "FeatureCollection", "cell_m": cell, "total_events": int(ev.sum()),
                "max_events_per_cell": int(ev.max()) if len(nz) else 0, "filters": spec.to_dict(), "features": feats}

    def points(self, spec: FilterSpec, bbox: tuple[float, float, float, float], kind: str, limit: int,
               offset: int = 0) -> dict[str, Any]:
        """Görünen alandaki benzersiz konumlar; olay sayısı FİLTRELENMİŞ olay sayısıdır."""
        m = self.mask(spec)
        w, s, e, n = bbox
        inb = (self.loc_lon >= w) & (self.loc_lon <= e) & (self.loc_lat >= s) & (self.loc_lat <= n)
        cand = np.flatnonzero(inb)
        loc_ev = np.bincount(self.c.location[m], minlength=self.n_locations)[cand] if len(cand) else np.array([], int)
        keep = loc_ev > 0
        cand, loc_ev = cand[keep], loc_ev[keep]
        lab = self.loc_cluster[cand]
        if kind == "clustered":
            sel = lab >= 0
        elif kind == "noise":
            sel = lab < 0
        else:
            sel = np.ones(len(cand), dtype=bool)
        cand, loc_ev, lab = cand[sel], loc_ev[sel], lab[sel]
        total_loc, total_ev = int(len(cand)), int(loc_ev.sum())
        order = np.lexsort((cand, -loc_ev))[offset:offset + limit]
        cand, loc_ev, lab = cand[order], loc_ev[order], lab[order]
        feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(self.loc_lon[i]), float(self.loc_lat[i])]},
                  "properties": {"location_id": int(i), "cluster_id": int(l), "n_events": int(v), "noise": bool(l < 0)}}
                 for i, v, l in zip(cand, loc_ev, lab)]
        return {"type": "FeatureCollection", "experiment_id": self.experiment_id, "kind": kind, "bbox": bbox,
                "filters": spec.to_dict(), "total_locations": total_loc, "total_events": total_ev,
                "returned_locations": len(feats), "returned_events": int(loc_ev.sum()), "truncated": len(feats) < total_loc,
                "limit": limit, "offset": offset,
                "next_offset": offset + len(feats) if offset + len(feats) < total_loc else None,
                "order": "filtrelenmiş olay sayısı azalan, sonra konum kimliği", "features": feats}

    def cluster_counts(self, spec: FilterSpec) -> np.ndarray:
        """Mevcut modelin her kümesindeki filtrelenmiş olay sayısı (uzunluk = küme sayısı)."""
        m = self.mask(spec)
        ec = self.event_cluster[m]
        return np.bincount(ec[ec >= 0], minlength=self.n_clusters)

    def cluster_filtered_detail(self, spec: FilterSpec, cluster_id: int) -> dict[str, Any]:
        """Tek kümenin filtrelenmiş kayıt profili (filtre boşsa tam küme)."""
        m = self.mask(spec) & (self.event_cluster == cluster_id)
        c = self.c
        n = int(m.sum())
        return {"cluster_id": cluster_id, "experiment_id": self.experiment_id, "filters": spec.to_dict(),
                "n_events": n, "injury_crashes": int(c.injury[m].sum()), "fatal_crashes": int(c.fatal[m].sum()),
                "persons_injured": int(c.persons_injured[m].sum()), "persons_killed": int(c.persons_killed[m].sum()),
                "n_unique_locations": int(len(np.unique(c.location[m]))),
                "date_min": days_to_date(int(c.days[m].min())) if n else None,
                "date_max": days_to_date(int(c.days[m].max())) if n else None,
                "by_hour": [int(v) for v in np.bincount(c.hour[m], minlength=24)[:24]],
                "by_vehicle": [{"value": v, "count": int(((c.vehicle_bits[m] >> i) & 1).sum())}
                               for i, v in enumerate(VEHICLE_CATEGORIES)],
                "top_factors": self._top_factors(m, 6), "factor_unspecified_share": self.factor_unspecified_share(m),
                "midnight_suspect": int(c.midnight[m].sum()),
                "boroughs": [{"value": (BOROUGH_CODES[i] if i < len(BOROUGH_CODES) else "UNKNOWN"), "count": int(v)}
                             for i, v in enumerate(np.bincount(c.borough[m], minlength=UNKNOWN_BOROUGH + 1)) if v]}


def density_cells(x: np.ndarray, y: np.ndarray, grid: pd.DataFrame, cell: int) -> tuple[np.ndarray, np.ndarray]:
    """Her konumun Faz 4 yoğunluk ızgarasındaki hücre satırı ve hücre merkezleri [boylam, enlem].

    Hücre tanımı Faz 4 ile aynıdır (UTM EPSG:32618, ``floor(x/cell)``); tüm konumların ızgarada
    bir hücresi olmalıdır (Faz 4 ızgarası tüm olaylardan üretildi)."""
    cx = np.floor(x / cell).astype(np.int64)
    cy = np.floor(y / cell).astype(np.int64)
    key = cx * 10_000_000 + cy
    gkey = grid["cx"].to_numpy(np.int64) * 10_000_000 + grid["cy"].to_numpy(np.int64)
    order = np.argsort(gkey)
    pos = np.searchsorted(gkey[order], key)
    pos = np.clip(pos, 0, len(order) - 1)
    if not np.array_equal(gkey[order][pos], key):
        raise ValueError(f"{cell} m ızgarasında hücresi olmayan konum var; Faz 4 katmanları güncel değil.")
    return order[pos].astype(np.int32), grid[["longitude", "latitude"]].to_numpy(float)
