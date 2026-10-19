"""Faz 4 coğrafi katman API'si (FastAPI).

İlke: 2 milyonu aşan olay tarayıcıya hiçbir zaman tek seferde gönderilmez.

* Düşük zoom: küme merkezleri (4.179 kayıt) ve sunucu tarafında özetlenmiş yoğunluk ızgarası.
* Yüksek zoom: yalnızca görünen sınırlayıcı kutu (bbox) içindeki benzersiz konumlar; kutu boyutu
  ve dönen kayıt sayısı sınırlıdır. Kesilen yanıtlarda gerçek toplamlar ayrıca döndürülür.

Tüm sayılar ``layer_manifest.json`` ve doğrulanmış katman dosyalarından gelir.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from saferoute.viz.layers import sha256_file

# Nokta sorgusunda izin verilen en büyük kutu (derece). ~0,05° ≈ 4–5 km: zoom ≥ ~13.
MAX_POINT_BBOX_SPAN_DEG = 0.05
MAX_POINT_LIMIT = 20000
DEFAULT_POINT_LIMIT = 8000


class LayerStore:
    """Doğrulanmış katman dosyalarını belleğe alır (yalnızca gerekli sütunlar, NumPy dizileri)."""

    def __init__(self, layers_dir: Path, verify: bool = True):
        self.dir = Path(layers_dir)
        lm_path = self.dir / "layer_manifest.json"
        if not lm_path.exists():
            raise FileNotFoundError(f"Katman manifesti yok: {lm_path}. 'saferoute viz-build' çalıştırın.")
        self.manifest = json.loads(lm_path.read_text(encoding="utf-8"))
        if verify:
            for key, o in self.manifest["outputs"].items():
                if sha256_file(self.dir / o["file"]) != o["sha256"]:
                    raise RuntimeError(f"Katman dosyası değişmiş: {o['file']} (SHA-256 uyuşmuyor)")
        loc = pd.read_parquet(self.dir / "locations_layer.parquet",
                              columns=["location_id", "longitude", "latitude", "cluster_id", "n_events", "n_core"])
        self.lon = loc["longitude"].to_numpy()
        self.lat = loc["latitude"].to_numpy()
        self.loc_id = loc["location_id"].to_numpy()
        self.cluster = loc["cluster_id"].to_numpy()
        self.n = loc["n_events"].to_numpy()
        self.core = loc["n_core"].to_numpy()
        order = np.lexsort((self.loc_id, -self.n))  # deterministik: çok olaylı konum önce
        self.rank = np.empty_like(order)
        self.rank[order] = np.arange(len(order))
        self.density = {int(p.stem.split("_")[1][:-1]): pd.read_parquet(p)
                        for p in sorted(self.dir.glob("density_*m.parquet"))}
        c = json.loads((self.dir / "clusters.json").read_text(encoding="utf-8"))
        self.experiment_id = c["experiment_id"]
        self.clusters = {r["cluster_id"]: r for r in c["clusters"]}
        self.geometries = json.loads((self.dir / "cluster_geometries.geojson").read_text(encoding="utf-8"))
        self.geom_bbox = {cid: (r["bbox_min_lon"], r["bbox_min_lat"], r["bbox_max_lon"], r["bbox_max_lat"])
                          for cid, r in self.clusters.items()}
        bp = self.dir / "boroughs.geojson"
        self.boroughs = json.loads(bp.read_text(encoding="utf-8")) if bp.exists() else None

    def bbox_mask(self, bbox: tuple[float, float, float, float]) -> np.ndarray:
        w, s, e, n = bbox
        return (self.lon >= w) & (self.lon <= e) & (self.lat >= s) & (self.lat <= n)


def parse_bbox(bbox: str | None, max_span: float | None = None) -> tuple[float, float, float, float] | None:
    """'batı,güney,doğu,kuzey' (WGS84 derece). Geçersizse 422."""
    if bbox is None:
        return None
    try:
        w, s, e, n = (float(v) for v in bbox.split(","))
    except ValueError:
        raise HTTPException(422, "bbox biçimi 'batı,güney,doğu,kuzey' olmalı (dört sayı).") from None
    if not all(np.isfinite([w, s, e, n])):
        raise HTTPException(422, "bbox sonlu sayılardan oluşmalı.")
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise HTTPException(422, "bbox sınırları geçersiz (batı < doğu, güney < kuzey).")
    if max_span is not None and (e - w > max_span or n - s > max_span):
        raise HTTPException(413, f"Nokta sorgusu için alan çok büyük (en fazla {max_span}°). Yakınlaştırın.")
    return w, s, e, n


def _cluster_light(r: dict[str, Any]) -> dict[str, Any]:
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["centroid_lon"], r["centroid_lat"]]},
            "properties": {"cluster_id": r["cluster_id"], "experiment_id": r["experiment_id"],
                           "n_events": r["n_events"], "rank": r["rank_by_events"], "borough": r["dominant_borough"],
                           "injury_crashes": r["injury_crashes"], "fatal_crashes": r["fatal_crashes"]}}


def create_app(layers_dir: Path | None = None, frontend_dir: Path | None = None, verify: bool = True) -> FastAPI:
    if layers_dir is None:
        from saferoute.clustering.data import processed_dir

        layers_dir = processed_dir() / "phase4"
    store = LayerStore(Path(layers_dir), verify=verify)
    app = FastAPI(title="SafeRoute 3D — Faz 4 katman API'si", version=store.manifest["layer_version"])
    app.add_middleware(GZipMiddleware, minimum_size=2048)
    app.state.store = store
    cache = {"Cache-Control": "public, max-age=3600"}

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "experiment_id": store.experiment_id, "layer_version": store.manifest["layer_version"]}

    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        m = store.manifest
        return {"model": m["model"], "counts": m["counts"], "dataset_version": m["dataset_version"],
                "processing_version": m["processing_version"], "density": m["density"],
                "boroughs": m["boroughs"], "source_manifest": {"sha256": m["source_manifest"]["sha256"],
                                                               "verified_files": list(m["source_manifest"]["verified_files"])},
                "point_reduction": m["point_reduction"], "layer_version": m["layer_version"],
                "limits": {"max_point_bbox_span_deg": MAX_POINT_BBOX_SPAN_DEG, "max_point_limit": MAX_POINT_LIMIT}}

    @app.get("/api/boroughs")
    def boroughs() -> JSONResponse:
        if store.boroughs is None:
            raise HTTPException(404, "İlçe sınırı katmanı üretilmemiş.")
        return JSONResponse(store.boroughs, headers=cache)

    @app.get("/api/clusters")
    def clusters(bbox: str | None = None) -> JSONResponse:
        b = parse_bbox(bbox)
        rows = store.clusters.values()
        if b:
            w, s, e, n = b
            rows = [r for r in rows if w <= r["centroid_lon"] <= e and s <= r["centroid_lat"] <= n]
        feats = [_cluster_light(r) for r in rows]
        return JSONResponse({"type": "FeatureCollection", "experiment_id": store.experiment_id,
                             "total_clusters": len(store.clusters), "returned": len(feats), "features": feats},
                            headers=cache if b is None else None)

    @app.get("/api/clusters/geometries")
    def cluster_geometries(bbox: str | None = None) -> JSONResponse:
        b = parse_bbox(bbox)
        feats = store.geometries["features"]
        if b:
            w, s, e, n = b

            def overlaps(cid: int) -> bool:
                x0, y0, x1, y1 = store.geom_bbox[cid]
                return not (x0 > e or x1 < w or y0 > n or y1 < s)

            feats = [f for f in feats if overlaps(f["properties"]["cluster_id"])]
        return JSONResponse({"type": "FeatureCollection", "experiment_id": store.experiment_id,
                             "geometry_semantics": store.geometries.get("geometry_semantics"),
                             "returned": len(feats), "features": feats}, headers=cache if b is None else None)

    @app.get("/api/clusters/{cluster_id}")
    def cluster_detail(cluster_id: int, experiment_id: str | None = None) -> dict[str, Any]:
        if experiment_id is not None and experiment_id != store.experiment_id:
            raise HTTPException(409, f"Küme kimliği farklı bir deneye ait ({experiment_id}); bu sunucunun modeli "
                                     f"{store.experiment_id}. Farklı modellerin küme numaraları eşleştirilemez.")
        r = store.clusters.get(cluster_id)
        if r is None:
            raise HTTPException(404, f"Küme bulunamadı: {cluster_id}")
        return r

    @app.get("/api/points")
    def points(bbox: str = Query(..., description="batı,güney,doğu,kuzey"),
               kind: Literal["clustered", "noise", "all"] = "all",
               limit: int = Query(DEFAULT_POINT_LIMIT, ge=1, le=MAX_POINT_LIMIT)) -> JSONResponse:
        b = parse_bbox(bbox, MAX_POINT_BBOX_SPAN_DEG)
        m = store.bbox_mask(b)
        if kind == "clustered":
            m &= store.cluster >= 0
        elif kind == "noise":
            m &= store.cluster < 0
        idx = np.flatnonzero(m)
        total_loc, total_ev = int(len(idx)), int(store.n[idx].sum())
        if len(idx) > limit:
            idx = idx[np.argsort(store.rank[idx], kind="stable")[:limit]]
        feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(store.lon[i]),
                                                                                   float(store.lat[i])]},
                  "properties": {"location_id": int(store.loc_id[i]), "cluster_id": int(store.cluster[i]),
                                 "n_events": int(store.n[i]), "noise": bool(store.cluster[i] < 0)}}
                 for i in idx]
        return JSONResponse({"type": "FeatureCollection", "experiment_id": store.experiment_id, "kind": kind,
                             "bbox": b, "total_locations": total_loc, "total_events": total_ev,
                             "returned_locations": len(feats),
                             "returned_events": int(sum(f["properties"]["n_events"] for f in feats)),
                             "truncated": len(feats) < total_loc,
                             "order": "olay sayısı azalan, sonra konum kimliği", "features": feats})

    @app.get("/api/density")
    def density(cell: int = 1000, bbox: str | None = None) -> JSONResponse:
        if cell not in store.density:
            raise HTTPException(422, f"Geçerli hücre boyutları: {sorted(store.density)}")
        g = store.density[cell]
        b = parse_bbox(bbox)
        if b:
            w, s, e, n = b
            g = g[(g["longitude"] >= w) & (g["longitude"] <= e) & (g["latitude"] >= s) & (g["latitude"] <= n)]
        feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                  "properties": {"events": ev, "clustered": cl, "noise": no}}
                 for lon, lat, ev, cl, no in zip(g["longitude"].round(6).tolist(), g["latitude"].round(6).tolist(),
                                                 g["events"].tolist(), g["clustered"].tolist(), g["noise"].tolist())]
        return JSONResponse({"type": "FeatureCollection", "cell_m": cell, "total_events": int(g["events"].sum()),
                             "features": feats}, headers=cache if b is None else None)

    if frontend_dir is not None and Path(frontend_dir).exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    return app
