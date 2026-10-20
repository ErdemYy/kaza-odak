"""Olay düzeyi etiketlerden (kayıtlı Faz 3 deneyi veya dinamik iş) küme tablosu, harita katmanı ve
küme profili. Kayıtlı ve dinamik sonuçlar AYNI kodla özetlenir; böylece aynı konfigürasyonun iki yolu
karşılaştırılabilir.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from saferoute.analytics.events import EventStore
from saferoute.analytics.filters import BOROUGH_CODES, UNKNOWN_BOROUGH, VEHICLE_CATEGORIES, days_to_date

BOROUGH_NAMES = [*BOROUGH_CODES, None]


class LabelResult:
    """Bir sonucun olay → küme eşlemesi ve türetilmiş yapılar (bellekte)."""

    def __init__(self, store: EventStore, event_index: np.ndarray, labels: np.ndarray, algorithm: str,
                 result_id: str):
        if len(event_index) != len(labels):
            raise ValueError("Etiket ve olay indeksi uzunlukları farklı")
        self.store = store
        self.result_id = result_id
        self.algorithm = algorithm
        self.event_index = event_index.astype(np.int64)
        uniq = np.unique(labels[labels >= 0])
        # Küme kimlikleri korunur (yalnızca sayım için yoğun indeks kullanılır)
        self.cluster_ids = uniq.astype(np.int32)
        self.labels = labels.astype(np.int32)
        self.dense = np.full(len(labels), -1, dtype=np.int64)
        pos = labels >= 0
        self.dense[pos] = np.searchsorted(uniq, labels[pos])
        self.n_clusters = int(len(uniq))
        self._table: dict[str, np.ndarray] | None = None
        self._loc: dict[str, np.ndarray] | None = None

    # ------------------------------------------------------------------ özet
    def table(self) -> dict[str, np.ndarray]:
        if self._table is not None:
            return self._table
        s, c = self.store, self.store.c
        ev = self.event_index
        d = self.dense
        k = self.n_clusters
        sel = d >= 0
        ev_c, d_c = ev[sel], d[sel]
        loc = c.location[ev_c]
        n = np.bincount(d_c, minlength=k)
        # Faz 3 profilleriyle aynı tanım: merkez UTM (EPSG:32618) ortalaması, WGS84'e dönüştürülür;
        # yarıçap = olayların merkeze uzaklığının doğrusal enterpolasyonlu 90. yüzdeliği.
        cx = np.bincount(d_c, weights=s.loc_x[loc], minlength=k) / np.maximum(n, 1)
        cy = np.bincount(d_c, weights=s.loc_y[loc], minlength=k) / np.maximum(n, 1)
        lon, lat = utm_to_wgs84(cx, cy)
        dist = np.hypot(s.loc_x[loc] - cx[d_c], s.loc_y[loc] - cy[d_c])
        order = np.lexsort((dist, d_c))
        starts = np.concatenate([[0], np.cumsum(n)[:-1]]) if k else np.array([], dtype=np.int64)
        p90 = group_quantile(dist[order], starts, n, 0.9) if k else np.array([])
        pair = np.unique(d_c.astype(np.int64) * s.n_locations + loc)
        n_loc = np.bincount((pair // s.n_locations).astype(np.int64), minlength=k)
        days = c.days[ev_c]
        dsorted = days[np.lexsort((days, d_c))]
        dmin = dsorted[starts] if k else np.array([])
        dmax = dsorted[starts + n - 1] if k else np.array([])
        bor = np.bincount(d_c.astype(np.int64) * (UNKNOWN_BOROUGH + 1) + c.borough[ev_c], minlength=k * (UNKNOWN_BOROUGH + 1))
        bor = bor.reshape(k, UNKNOWN_BOROUGH + 1)
        hours = np.bincount(d_c.astype(np.int64) * 24 + c.hour[ev_c], minlength=k * 24).reshape(k, 24)
        self._table = {
            "cluster_id": self.cluster_ids, "n_events": n, "n_unique_locations": n_loc, "centroid_lon": lon,
            "centroid_lat": lat, "radius_p90_m": p90,
            "injury_crashes": np.bincount(d_c, weights=c.injury[ev_c], minlength=k).astype(np.int64),
            "fatal_crashes": np.bincount(d_c, weights=c.fatal[ev_c], minlength=k).astype(np.int64),
            "persons_injured": np.bincount(d_c, weights=c.persons_injured[ev_c], minlength=k).astype(np.int64),
            "persons_killed": np.bincount(d_c, weights=c.persons_killed[ev_c], minlength=k).astype(np.int64),
            "date_min": dmin, "date_max": dmax, "dominant_borough": bor.argmax(axis=1) if k else np.array([], int),
            "dominant_borough_share": (bor.max(axis=1) / np.maximum(n, 1)) if k else np.array([]),
            "peak_hour": hours.argmax(axis=1) if k else np.array([], int),
        }
        return self._table

    def summary(self) -> dict[str, Any]:
        t = self.table()
        n_ev = int(len(self.labels))
        noise = int((self.labels < 0).sum())
        sizes = t["n_events"]
        kmeans = self.algorithm == "kmeans"
        q = (lambda p: float(np.percentile(sizes, p))) if len(sizes) else (lambda p: None)
        return {
            "n_events": n_ev, "n_clusters": self.n_clusters,
            "noise_events": None if kmeans else noise, "noise_ratio": None if kmeans else (noise / n_ev if n_ev else None),
            "noise_applicable": not kmeans,
            "clustered_events": n_ev - noise,
            "largest_cluster_share": float(sizes.max() / n_ev) if len(sizes) and n_ev else None,
            "cluster_size": {"min": int(sizes.min()) if len(sizes) else None, "p25": q(25), "median": q(50), "p75": q(75),
                             "p90": q(90), "max": int(sizes.max()) if len(sizes) else None},
            "size_histogram": size_histogram(sizes),
        }

    def cluster_rows(self, limit: int = 50, offset: int = 0, sort: str = "n_events") -> dict[str, Any]:
        t = self.table()
        key = t.get(sort, t["n_events"])
        order = np.lexsort((t["cluster_id"], -np.asarray(key, dtype=float)))
        page = order[offset:offset + limit]
        rows = [self._row(i, rank=int(np.flatnonzero(order == i)[0]) + 1) for i in page]
        return {"total": self.n_clusters, "offset": offset, "limit": limit, "sort": sort, "rows": rows}

    def _row(self, i: int, rank: int | None = None) -> dict[str, Any]:
        t = self.table()
        b = int(t["dominant_borough"][i])
        return {"cluster_id": int(t["cluster_id"][i]), "rank_by_events": rank, "n_events": int(t["n_events"][i]),
                "n_unique_locations": int(t["n_unique_locations"][i]),
                "centroid_lon": float(t["centroid_lon"][i]), "centroid_lat": float(t["centroid_lat"][i]),
                "radius_p90_m": float(t["radius_p90_m"][i]), "injury_crashes": int(t["injury_crashes"][i]),
                "fatal_crashes": int(t["fatal_crashes"][i]), "persons_injured": int(t["persons_injured"][i]),
                "persons_killed": int(t["persons_killed"][i]), "date_min": days_to_date(int(t["date_min"][i])),
                "date_max": days_to_date(int(t["date_max"][i])), "dominant_borough": BOROUGH_NAMES[b],
                "dominant_borough_share": float(t["dominant_borough_share"][i]), "peak_hour": int(t["peak_hour"][i])}

    def centroids(self, limit: int = 40000) -> dict[str, Any]:
        t = self.table()
        order = np.lexsort((t["cluster_id"], -t["n_events"]))
        rank = np.empty(len(order), dtype=np.int64)
        rank[order] = np.arange(1, len(order) + 1)
        take = order[:limit]
        feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(float(t["centroid_lon"][i]), 6),
                                                                                   round(float(t["centroid_lat"][i]), 6)]},
                  "properties": {"cluster_id": int(t["cluster_id"][i]), "experiment_id": self.result_id,
                                 "n_events": int(t["n_events"][i]), "rank": int(rank[i]),
                                 "borough": BOROUGH_NAMES[int(t["dominant_borough"][i])],
                                 "injury_crashes": int(t["injury_crashes"][i]), "fatal_crashes": int(t["fatal_crashes"][i])}}
                 for i in take]
        return {"type": "FeatureCollection", "experiment_id": self.result_id, "total_clusters": self.n_clusters,
                "returned": len(feats), "truncated": len(feats) < self.n_clusters, "features": feats}

    # ------------------------------------------------------------------ konum katmanı
    def locations(self) -> dict[str, np.ndarray]:
        """Konum başına baskın etiket ve olay sayısı (kayıt düzeyi algoritmalarda bir konumda birden
        fazla etiket olabilir; ``n_labels`` bunu gösterir)."""
        if self._loc is not None:
            return self._loc
        s = self.store
        loc = s.c.location[self.event_index].astype(np.int64)
        lab = self.labels.astype(np.int64)
        key = loc * (int(lab.max()) + 2 if len(lab) else 1) + (lab + 1)
        uk, cnt = np.unique(key, return_counts=True)
        base = int(lab.max()) + 2 if len(lab) else 1
        uloc, ulab = uk // base, uk % base - 1
        order = np.lexsort((ulab, -cnt, uloc))
        uloc, ulab, cnt = uloc[order], ulab[order], cnt[order]
        first = np.concatenate([[True], uloc[1:] != uloc[:-1]]) if len(uloc) else np.array([], bool)
        loc_ids = uloc[first]
        tot = np.bincount(loc, minlength=s.n_locations)[loc_ids]
        nl = np.diff(np.concatenate([np.flatnonzero(first), [len(uloc)]]))
        self._loc = {"location": loc_ids, "label": ulab[first].astype(np.int32), "events": tot, "n_labels": nl}
        return self._loc

    def points(self, bbox: tuple[float, float, float, float], limit: int) -> dict[str, Any]:
        s = self.store
        L = self.locations()
        w, so, e, n = bbox
        lon, lat = s.loc_lon[L["location"]], s.loc_lat[L["location"]]
        sel = np.flatnonzero((lon >= w) & (lon <= e) & (lat >= so) & (lat <= n))
        total_loc, total_ev = int(len(sel)), int(L["events"][sel].sum())
        if len(sel) > limit:
            sel = sel[np.lexsort((L["location"][sel], -L["events"][sel]))[:limit]]
        feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(lon[i]), float(lat[i])]},
                  "properties": {"location_id": int(L["location"][i]), "cluster_id": int(L["label"][i]),
                                 "n_events": int(L["events"][i]), "noise": bool(L["label"][i] < 0),
                                 "n_labels": int(L["n_labels"][i])}} for i in sel]
        return {"type": "FeatureCollection", "experiment_id": self.result_id, "bbox": bbox, "total_locations": total_loc,
                "total_events": total_ev, "returned_locations": len(feats),
                "returned_events": int(sum(f["properties"]["n_events"] for f in feats)),
                "truncated": len(feats) < total_loc, "features": feats}

    def cluster_detail(self, cluster_id: int) -> dict[str, Any] | None:
        hit = np.flatnonzero(self.cluster_ids == cluster_id)
        if not len(hit):
            return None
        i = int(hit[0])
        t = self.table()
        order = np.lexsort((t["cluster_id"], -t["n_events"]))
        row = self._row(i, rank=int(np.flatnonzero(order == i)[0]) + 1)
        ev = self.event_index[self.labels == cluster_id]
        row.update(profile(self.store, ev))
        row["experiment_id"] = self.result_id
        return row

    def export_rows(self) -> list[dict[str, Any]]:
        t = self.table()
        order = np.lexsort((t["cluster_id"], -t["n_events"]))
        return [self._row(int(i), rank=r + 1) for r, i in enumerate(order)]


def utm_to_wgs84(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    from pyproj import Transformer

    if not len(x):
        return np.array([]), np.array([])
    lon, lat = Transformer.from_crs("EPSG:32618", "EPSG:4326", always_xy=True).transform(x, y)
    return np.asarray(lon), np.asarray(lat)


def group_quantile(sorted_vals: np.ndarray, starts: np.ndarray, n: np.ndarray, q: float) -> np.ndarray:
    """Gruplara göre sıralı dizide doğrusal enterpolasyonlu yüzdelik (pandas quantile ile aynı)."""
    pos = q * (n - 1)
    lo = np.floor(pos).astype(np.int64)
    hi = np.ceil(pos).astype(np.int64)
    a, b = sorted_vals[starts + lo], sorted_vals[starts + hi]
    return a + (b - a) * (pos - lo)


def size_histogram(sizes: np.ndarray) -> list[dict[str, Any]]:
    edges = [1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000, 10**9]
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        out.append({"from": lo, "to": hi - 1 if hi < 10**9 else None, "clusters": int(((sizes >= lo) & (sizes < hi)).sum())})
    return out


def profile(store: EventStore, ev: np.ndarray) -> dict[str, Any]:
    """Bir olay kümesinin profili: saat, araç, etken, yaralanma, tarih (gerçek kayıtlardan)."""
    c = store.c
    n = int(len(ev))
    m = np.zeros(store.n_events, dtype=bool)
    m[ev] = True
    return {
        "hour_histogram": [int(v) for v in np.bincount(c.hour[ev], minlength=24)[:24]],
        "vehicles": [{"value": v, "count": int(((c.vehicle_bits[ev] >> i) & 1).sum()),
                      "share": float(((c.vehicle_bits[ev] >> i) & 1).sum() / n) if n else None}
                     for i, v in enumerate(VEHICLE_CATEGORIES)],
        "top_factors": store._top_factors(m, 8), "factor_unspecified_share": store.factor_unspecified_share(m),
        "midnight_suspect": int(c.midnight[ev].sum()),
        "boroughs": [{"value": BOROUGH_NAMES[b] or "UNKNOWN", "count": int(v)}
                     for b, v in enumerate(np.bincount(c.borough[ev], minlength=UNKNOWN_BOROUGH + 1)) if v],
        "years": [{"year": int(y), "count": int(v)} for y, v in zip(*np.unique(c.year[ev], return_counts=True))],
    }
