"""Faz 6 coğrafi veri sunumu karşılaştırması (çalışan sunucuya karşı GERÇEK HTTP ölçümü).

Karşılaştırılan yaklaşımlar:
  A) Mevcut: zoom'a duyarlı bbox API'si (/api/points, /api/records/points, /api/results/{id}/points) — ölçülür.
  B) Tek statik dosya: tüm benzersiz konumları içeren GeoJSON — gerçek boyut, gzip boyutu ve ayrıştırma süresi ölçülür.
  C) Vektör karo (PMTiles/MVT): prototip KURULMADI. z14 karo sayısı ve karo başına nokta dağılımı gerçek konum
     verisinden sayılır; bayt boyutu yalnızca açıkça işaretlenmiş bir TAHMİNDİR.

Kullanım (depo kökünden, sunucu çalışırken):
  backend\\.venv\\Scripts\\python.exe scripts\\phase6_geo_benchmark.py [--url http://127.0.0.1:8000]
Çıktı: reports/phase6/geo_benchmark.json
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import statistics
import time
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def fetch(url: str) -> tuple[float, int, int, dict]:
    req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        enc = r.headers.get("Content-Encoding")
    ms = (time.perf_counter() - t0) * 1000
    body = gzip.decompress(raw) if enc == "gzip" else raw
    return ms, len(raw), len(body), json.loads(body)


def tile_xy(lon: np.ndarray, lat: np.ndarray, z: int) -> tuple[np.ndarray, np.ndarray]:
    n = 2 ** z
    x = np.floor((lon + 180) / 360 * n).astype(np.int64)
    lr = np.radians(lat)
    y = np.floor((1 - np.log(np.tan(lr) + 1 / np.cos(lr)) / math.pi) / 2 * n).astype(np.int64)
    return x, y


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--repeats", type=int, default=5)
    args = ap.parse_args()

    from saferoute.clustering.data import processed_dir
    from saferoute.viz.api import LayerStore

    store = LayerStore(processed_dir() / "phase4", verify=False)
    rng = np.random.default_rng(42)
    # Gerçek kullanıcı görünümlerine benzer: kaza olan konumların çevresinde zoom ~14 görünümü (0,04° × 0,025°)
    centers = rng.choice(len(store.lon), size=20, replace=False)
    boxes = [(float(store.lon[i]) - 0.02, float(store.lat[i]) - 0.0125, float(store.lon[i]) + 0.02, float(store.lat[i]) + 0.0125)
             for i in centers]
    sel = json.loads(urllib.request.urlopen(f"{args.url}/api/experiments", timeout=60).read())["selected"]
    endpoints = {
        "faz4_model_noktalar": "/api/points?bbox={b}&limit=8000",
        "filtreli_kayit_noktalari_bisiklet": "/api/records/points?bbox={b}&limit=8000&vehicles=BICYCLE",
        "kayitli_hdbscan_noktalari": f"/api/results/{sel['hdbscan']['experiment_id']}/points?bbox={{b}}&limit=8000",
        "kayitli_hdbscan_2019_dilimi": f"/api/results/{sel['hdbscan']['experiment_id']}/points?bbox={{b}}&limit=8000&years=2019",
    }
    out: dict = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "server": args.url, "viewports": len(boxes),
                 "viewport_size_deg": [0.04, 0.025], "repeats": args.repeats, "A_bbox_api": {}}
    for name, tpl in endpoints.items():
        lat, wire, raw, ret, tot, trunc = [], [], [], [], [], 0
        for b in boxes:
            url = args.url + tpl.format(b=",".join(f"{v:.6f}" for v in b))
            fetch(url)  # ısınma (maske/önbellek)
            ms = [fetch(url)[0] for _ in range(args.repeats)]
            _, w, r, body = fetch(url)
            lat.append(statistics.median(ms))
            wire.append(w)
            raw.append(r)
            ret.append(body["returned_locations"])
            tot.append(body["total_locations"])
            trunc += int(body["truncated"])
        out["A_bbox_api"][name] = {
            "median_ms": round(statistics.median(lat), 1), "p95_ms": round(float(np.percentile(lat, 95)), 1),
            "median_gzip_bytes": int(statistics.median(wire)), "max_gzip_bytes": int(max(wire)),
            "median_json_bytes": int(statistics.median(raw)), "median_returned_locations": int(statistics.median(ret)),
            "max_total_locations": int(max(tot)), "truncated_viewports": trunc,
        }

    # B) Tek statik GeoJSON (tüm benzersiz konumlar; model etiketi + olay sayısı)
    feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(float(x), 6), round(float(y), 6)]},
              "properties": {"location_id": int(i), "cluster_id": int(c), "n_events": int(n)}}
             for x, y, i, c, n in zip(store.lon, store.lat, store.loc_id, store.cluster, store.n)]
    blob = json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")).encode()
    t0 = time.perf_counter()
    json.loads(blob)
    parse_ms = (time.perf_counter() - t0) * 1000
    out["B_single_static_geojson"] = {
        "locations": len(feats), "json_bytes": len(blob), "gzip_bytes": len(gzip.compress(blob, 6)),
        "python_parse_ms": round(parse_ms, 1),
        "note": "Yalnızca TEK model ve filtresiz durum için geçerlidir; her filtre/deney/zaman dilimi için ayrı dosya gerekir.",
    }

    # C) Vektör karo: z14 karo sayısı ve karo başına nokta (gerçek); bayt boyutu TAHMİN
    tiles = {}
    for z in (12, 14, 16):
        x, y = tile_xy(store.lon, store.lat, z)
        key = x * (2 ** z) + y
        _, counts = np.unique(key, return_counts=True)
        tiles[f"z{z}"] = {"tiles_with_points": int(len(counts)), "points_per_tile_median": int(np.median(counts)),
                          "points_per_tile_p95": int(np.percentile(counts, 95)), "points_per_tile_max": int(counts.max())}
    est_bytes_per_point = 12  # MVT nokta geometrisi (~3–5 B) + iki tamsayı öznitelik (~4–8 B); gzip öncesi kaba tahmin
    tiles["estimate"] = {
        "assumption_bytes_per_point": est_bytes_per_point,
        "z14_median_tile_bytes_estimate": tiles["z14"]["points_per_tile_median"] * est_bytes_per_point,
        "label": "TAHMİN — prototip üretilmedi; ölçüm değildir",
    }
    out["C_vector_tiles_estimate"] = tiles
    out["conclusion"] = (
        "Mevcut bbox API'si filtreli/kayıtlı/dinamik/zaman dilimli görünümlerin tamamını tek uç noktayla sunar; "
        "önceden üretilmiş PMTiles yalnızca tek bir sabit katmanı (filtresiz, tek model) hızlandırabilir. "
        "Ölçülen bbox yanıtları zaten onlarca milisaniye ve birkaç kilobayt düzeyinde olduğundan format değişikliği "
        "belirgin bir kazanç sağlamaz; mimari değiştirilmedi.")
    dest = ROOT / "reports" / "phase6" / "geo_benchmark.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "C_vector_tiles_estimate"}, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
