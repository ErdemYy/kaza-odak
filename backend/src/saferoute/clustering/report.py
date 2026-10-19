"""Faz 3 şekilleri, otomatik Markdown raporu ve küçük sonuç dosyalarının ``reports/phase3`` kopyaları.

Tüm sayılar ``results.json`` ve deney kaydından okunur; elle yazılmış metrik yoktur.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from saferoute import config  # noqa: E402
from saferoute.eda.figures import HOTSPOT, MUTED, PRIMARY, WARNING, _save, _style, _thousands  # noqa: E402

ALG_TR = {"dbscan": "DBSCAN", "kmeans": "K-Means", "hdbscan": "HDBSCAN"}
ALG_COLOR = {"dbscan": PRIMARY, "kmeans": WARNING, "hdbscan": "#7C3AED"}


def _n(x: Any, d: int = 0) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "N/A"
    if d:
        return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(round(x)):,}".replace(",", ".")


def _f(x: Any, d: int = 3) -> str:
    return "N/A" if x is None else f"{x:.{d}f}".replace(".", ",")


def _pct(x: Any, d: int = 1) -> str:
    return "N/A" if x is None else f"%{100 * x:.{d}f}".replace(".", ",")


def _metric(m: dict | None) -> Any:
    return None if not m else m.get("value")


def _rows(results: dict, alg: str) -> list[dict]:
    return [r for r in results["evaluation"]["table"] if r["algorithm"] == alg]


# ----------------------------------------------------------------------------- şekiller
def fig_dbscan_grid(results: dict, cfg: dict, out: Path) -> Path:
    rows = [r for r in _rows(results, "dbscan") if r["status"] == "success"]
    eps, ms = cfg["dbscan"]["eps_m"], cfg["dbscan"]["min_samples"]
    panels = [("Küme sayısı (tam veri)", lambda r: r["full"]["n_clusters"], "{:.0f}"),
              ("Gürültü oranı (tam veri)", lambda r: r["full"]["noise_ratio"], "{:.2f}"),
              ("En büyük küme payı", lambda r: r["full"]["largest_cluster_share"], "{:.3f}"),
              ("Siluet (ortak metrik, örneklem)", lambda r: _metric(r["silhouette_common"]), "{:.2f}"),
              ("Parametre kararlılığı (komşu ARI)", lambda r: r.get("parameter_stability_ari"), "{:.2f}"),
              ("DBCV (örneklem)", lambda r: _metric(r["dbcv"]), "{:.2f}")]
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5))
    for ax, (title, fn, fmt) in zip(axes.ravel(), panels):
        grid = np.full((len(ms), len(eps)), np.nan)
        for r in rows:
            v = fn(r)
            if v is not None:
                grid[ms.index(r["params"]["min_samples"]), eps.index(r["params"]["eps_m"])] = v
        im = ax.imshow(grid, cmap="viridis", aspect="auto", origin="lower")
        ax.set_xticks(range(len(eps)), [f"{e} m" for e in eps])
        ax.set_yticks(range(len(ms)), ms)
        ax.set_xlabel("eps")
        ax.set_ylabel("min_samples")
        ax.set_title(title, fontsize=10, loc="left", fontweight="bold")
        for i in range(len(ms)):
            for j in range(len(eps)):
                if not np.isnan(grid[i, j]):
                    ax.text(j, i, fmt.format(grid[i, j]), ha="center", va="center", fontsize=8,
                            color="white" if grid[i, j] < np.nanmean(grid) else "black")
        fig.colorbar(im, ax=ax, shrink=0.8)
    sel = results["selection"]["dbscan"]
    srow = next((r for r in rows if r["experiment_id"] == sel), None)
    fig.suptitle("DBSCAN parametre duyarlılığı" + (f" — seçilen: eps={srow['params']['eps_m']} m, "
                 f"min_samples={srow['params']['min_samples']}" if srow else ""), x=0.01, ha="left", fontweight="bold")
    return _save(fig, out / "dbscan_parameter_sensitivity.png")


def fig_kmeans_elbow(results: dict, out: Path) -> Path:
    rows = sorted([r for r in _rows(results, "kmeans") if r["status"] == "success"], key=lambda r: r["params"]["k"])
    ks = [r["params"]["k"] for r in rows]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2))
    a1.plot(ks, [r["inertia"] / 1e12 for r in rows], marker="o", color=WARNING)
    elbow = results["selection"].get("kmeans_elbow_k")
    if elbow:
        a1.axvline(elbow, color=MUTED, linestyle="--", label=f"dirsek (kneedle): k={elbow}")
        a1.legend(frameon=False)
    _style(a1, "K-Means dirsek grafiği (ağırlıklı atalet)", "k", "Atalet (×10¹² m²)")
    a2.plot(ks, [_metric(r["silhouette_common"]) for r in rows], marker="o", color=PRIMARY, label="Siluet (↑)")
    a2b = a2.twinx()
    a2b.plot(ks, [_metric(r["davies_bouldin"]) for r in rows], marker="s", color=HOTSPOT, label="Davies–Bouldin (↓)")
    a2b.set_ylabel("Davies–Bouldin")
    _style(a2, "K-Means siluet ve Davies–Bouldin (ortak örneklem)", "k", "Siluet")
    h1, l1 = a2.get_legend_handles_labels()
    h2, l2 = a2b.get_legend_handles_labels()
    a2.legend(h1 + h2, l1 + l2, frameon=False, fontsize=9)
    return _save(fig, out / "kmeans_elbow_silhouette.png")


def fig_silhouette_all(results: dict, out: Path) -> Path:
    rows = [r for r in results["evaluation"]["table"] if r["status"] == "success"]
    labels, vals, colors = [], [], []
    for r in rows:
        p = r["params"]
        name = {"dbscan": f"DB e{p.get('eps_m')}/m{p.get('min_samples')}", "kmeans": f"KM k{p.get('k')}",
                "hdbscan": f"HD c{p.get('min_cluster_size')}/m{p.get('min_samples')}"}[r["algorithm"]]
        labels.append(name)
        vals.append(_metric(r["silhouette_common"]))
        colors.append(ALG_COLOR[r["algorithm"]])
    fig, ax = plt.subplots(figsize=(14, 4.8))
    x = np.arange(len(labels))
    ax.bar(x, [v if v is not None else 0 for v in vals], color=colors)
    for i, v in enumerate(vals):
        if v is None:
            ax.text(i, 0.01, "N/A", ha="center", fontsize=7, rotation=90)
    ax.axhline(0, color="black", linewidth=0.7)
    ax.set_xticks(x, labels, rotation=90, fontsize=7)
    _style(ax, "Siluet skoru — ortak metrik (UTM metre, Öklid), gürültü hariç, tabakalı örneklem", "", "Siluet")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=ALG_COLOR[a], label=ALG_TR[a]) for a in ALG_TR], frameon=False)
    return _save(fig, out / "silhouette_all_configs.png")


def fig_hdbscan(results: dict, runner, out: Path) -> Path:
    rows = [r for r in _rows(results, "hdbscan") if r["status"] == "success"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2))
    for ms in sorted({r["params"]["min_samples"] for r in rows}):
        sub = sorted([r for r in rows if r["params"]["min_samples"] == ms], key=lambda r: r["params"]["min_cluster_size"])
        a1.plot([r["params"]["min_cluster_size"] for r in sub], [r["eval_set"]["n_clusters"] for r in sub], marker="o",
                label=f"min_samples={ms}")
    a1.set_xscale("log")
    _style(a1, "HDBSCAN küme sayısı (100k olay örneklemi)", "min_cluster_size", "Küme sayısı")
    a1.legend(frameon=False, fontsize=8)
    sel = results["selection"].get("hdbscan")
    if sel:
        z = runner.load_labels(runner.registry.get(sel))
        sizes = np.bincount(z["labels"][z["labels"] >= 0])
        a2.hist(sizes, bins=np.logspace(np.log10(max(1, sizes.min())), np.log10(sizes.max() + 1), 30), color="#7C3AED")
        a2.set_xscale("log")
        p = runner.registry.get(sel)["params"]
        _style(a2, f"Seçilen HDBSCAN küme boyutları (mcs={p['min_cluster_size']}, ms={p['min_samples']})",
               "Küme boyutu (olay, log)", "Küme sayısı")
    return _save(fig, out / "hdbscan_distribution.png")


def fig_noise(results: dict, out: Path) -> Path:
    comp = results["_comparison"]
    fig, ax = plt.subplots(figsize=(7, 4))
    names = [ALG_TR[r["algorithm"]] for r in comp]
    vals = [r["eval_set_noise_ratio"] or 0 for r in comp]
    ax.bar(names, vals, color=[ALG_COLOR[r["algorithm"]] for r in comp])
    for i, v in enumerate(vals):
        ax.text(i, v, f" {v:.3f}".replace(".", ","), ha="center", va="bottom")
    _style(ax, "Gürültü oranı — seçilen konfigürasyonlar (ortak değerlendirme kümesi)", "", "Gürültü oranı")
    ax.text(0.99, 0.95, "K-Means tanımı gereği gürültü üretmez", transform=ax.transAxes, ha="right", fontsize=8)
    return _save(fig, out / "noise_ratio_comparison.png")


def fig_sizes(results: dict, runner, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for alg in ("dbscan", "hdbscan", "kmeans"):
        sel = results["selection"].get(alg)
        if not sel:
            continue
        lab = runner.full_labels(runner.registry.get(sel))
        lab = lab[lab >= 0]
        sizes = np.sort(np.bincount(lab)[np.bincount(lab) > 0])[::-1]
        ax.plot(np.arange(1, len(sizes) + 1), sizes, marker=".", color=ALG_COLOR[alg],
                label=f"{ALG_TR[alg]} ({len(sizes):,} küme)".replace(",", "."))
    ax.set_xscale("log")
    ax.set_yscale("log")
    _style(ax, "Küme boyutu dağılımı (sıra–boyut, log-log)", "Küme sırası", "Olay sayısı")
    ax.legend(frameon=False)
    ax.text(0.01, 0.02, "DBSCAN/K-Means: tam veri; HDBSCAN: 100k olay örneklemi", transform=ax.transAxes, fontsize=8)
    return _save(fig, out / "cluster_size_distribution.png")


def _exp_label(r: dict) -> str:
    p = r["params"]
    return {"dbscan": f"DB e{p.get('eps_m')}/m{p.get('min_samples')}", "kmeans": f"KM k{p.get('k')}",
            "hdbscan": f"HD c{p.get('min_cluster_size')}/m{p.get('min_samples')}"}[r["algorithm"]]


def fig_runtime_memory(results: dict, out: Path) -> tuple[Path, Path]:
    rows = [r for r in results["evaluation"]["table"] if r["status"] == "success"]
    names = [_exp_label(r) for r in rows]
    colors = [ALG_COLOR[r["algorithm"]] for r in rows]
    paths = []
    for key, title, ylabel, fname, log in (
            ("runtime_s", "Fit süresi (yalnızca algoritma; veri yükleme hariç)", "Saniye (log)", "runtime_comparison.png", True),
            ("fit_memory_mb", "Fit sırasında ek bellek (deney süreci tepe − fit öncesi)", "MB", "memory_comparison.png", False)):
        fig, ax = plt.subplots(figsize=(14, 4.6))
        vals = [r.get(key) or 0 for r in rows]
        ax.bar(range(len(rows)), vals, color=colors)
        if log:
            ax.set_yscale("log")
        ax.set_xticks(range(len(rows)), names, rotation=90, fontsize=7)
        _style(ax, title, "", ylabel)
        ax.text(0.01, 0.95, f"DBSCAN/K-Means: tam veri ({_n(results['integrity']['unique_locations'])} ağırlıklı "
                f"konum); HDBSCAN: {_n(results['evaluation']['eval_set']['n_events'])} olay örneklemi",
                transform=ax.transAxes, fontsize=8, va="top")
        paths.append(_save(fig, out / fname))
    return tuple(paths)


def fig_temporal(results: dict, out: Path) -> Path:
    t = results["temporal"]
    years = t["years"]
    ys = np.array([r["year"] for r in years])

    def series(key: str) -> np.ndarray:  # eksik değer NaN: çizgi boş yılları birleştirmez
        return np.array([np.nan if r.get(key) is None else r[key] for r in years], dtype=float)

    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(17, 4.6))
    a1.bar(ys, series("dbscan_n_clusters"), color=PRIMARY, label="(a) sabit eşik")
    a1.plot(ys, series("scaled_n_clusters"), marker="^", color="#7C3AED", label="(c) hacme ölçekli eşik")
    a1.set_yscale("symlog", linthresh=10)  # (a) 0–onlarca, (c) binlerce küme: doğrusal eksende (a) görünmez
    a1b = a1.twinx()
    a1b.plot(ys, series("n_events") / 1000, color=MUTED, linestyle="--", label="Yıllık olay (bin)")
    a1b.set_ylabel("Olay (bin)")
    a1b.set_ylim(0, None)
    _style(a1, "Yıllık küme sayısı ve olay hacmi", "Yıl", "Küme sayısı (symlog)")
    h1, l1 = a1.get_legend_handles_labels()
    h2, l2 = a1b.get_legend_handles_labels()
    a1.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8, loc="center left")
    a2.plot(ys, series("jaccard_vs_prev_year"), marker="o", color=HOTSPOT, label="(a) kapsama Jaccard")
    a2.plot(ys, series("scaled_jaccard_vs_prev_year"), marker="^", color="#7C3AED", label="(c) kapsama Jaccard")
    a2.set_ylim(0, 1)
    _style(a2, "Önceki yılla kapsama örtüşmesi (100 m hücre)", "Yıl", "Jaccard")
    a2.legend(frameon=False, fontsize=8)
    a2.text(0.01, 0.97, "(a) boş kapsamlı yıllarda tanımsız (çizgi kesik)", transform=a2.transAxes, fontsize=8,
            va="top")
    pers = t["persistence"]
    dist = pers["active_years_distribution"]
    a3.bar([int(k) for k in dist], list(dist.values()), color=PRIMARY)
    _style(a3, f"Tam veri kümelerinin etkin yıl sayısı ({years[0]['year']}–{years[-1]['year']})",
           "Etkin yıl sayısı", "Küme sayısı")
    _thousands(a3)
    return _save(fig, out / "temporal_stability.png")


def fig_kdistance(results: dict, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.3))
    for k, v in results["kdistance"]["by_k"].items():
        curve = v["sorted_curve_m"]
        ax.plot(np.linspace(0, 100, len(curve)), curve, label=f"k = {k}")
    ax.set_yscale("symlog", linthresh=1)
    _style(ax, "Ağırlıklı k-mesafe eğrileri (k'ıncı en yakın olaya uzaklık)", "Olay yüzdeliği", "Mesafe (m, symlog)")
    ax.legend(frameon=False)
    return _save(fig, out / "k_distance.png")


def fig_equivalence(results: dict, out: Path) -> Path:
    sc = [s for s in results["equivalence"]["scenarios"] if s.get("core_identical") is not None]
    names = [f"{s['scenario']}\ne{s['eps_m']}/m{s['min_samples']}" for s in sc]
    x = np.arange(len(sc))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 4.6))
    a1.bar(x - 0.2, [s["records_neighbor_pairs"] for s in sc], 0.4, color=MUTED, label="Kayıt düzeyi")
    a1.bar(x + 0.2, [s["weighted_neighbor_pairs"] for s in sc], 0.4, color=PRIMARY, label="Ağırlıklı benzersiz konum")
    a1.set_yscale("log")
    a1.set_xticks(x, names, rotation=90, fontsize=7)
    _style(a1, "Komşu çifti sayısı (bellek göstergesi)", "", "Çift (log)")
    a1.legend(frameon=False, fontsize=8)
    a2.bar(x - 0.2, [s["records_runtime_s"] for s in sc], 0.4, color=MUTED, label="Kayıt düzeyi")
    a2.bar(x + 0.2, [s["weighted_runtime_s"] for s in sc], 0.4, color=PRIMARY, label="Ağırlıklı")
    a2.set_yscale("log")
    a2.set_xticks(x, names, rotation=90, fontsize=7)
    _style(a2, "Fit süresi", "", "Saniye (log)")
    a2.legend(frameon=False, fontsize=8)
    return _save(fig, out / "weighted_equivalence.png")


def fig_sensitivity(results: dict, out: Path) -> Path:
    v = [r for r in results["sensitivity"]["variants"] if r["status"] == "success"]
    names = {"exclude_geocode_fallback": "Yedek geokodlama\nhariç", "exclude_borough_conflict": "İlçe çelişkisi\nhariç",
             "exclude_nearshore": "Kıyıya yakın\nhariç", "cap_repeated_weights": "Tekrar ağırlığı\nkırpılmış"}
    x = np.arange(len(v))
    fig, ax = plt.subplots(figsize=(9, 4.3))
    ax.bar(x - 0.27, [r["ari_vs_baseline_common_events"] for r in v], 0.27, color=PRIMARY, label="ARI (ortak olaylar)")
    ax.bar(x, [r["baseline_clusters_retained_share"] for r in v], 0.27, color=WARNING, label="Korunan temel küme payı")
    ax.bar(x + 0.27, [r["noise_status_agreement"] for r in v], 0.27, color=MUTED, label="Gürültü durumu uyumu")
    ax.set_xticks(x, [names.get(r["variant"], r["variant"]) for r in v], fontsize=8)
    ax.set_ylim(0, 1.05)
    _style(ax, "Veri kalitesi duyarlılığı — seçilen DBSCAN ile karşılaştırma", "", "Oran")
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    return _save(fig, out / "data_quality_sensitivity.png")


def fig_maps(results: dict, runner, out: Path) -> list[Path]:
    import geopandas as gpd

    from saferoute.preprocess.boundaries import latest_boundaries, read_boundaries_snapshot

    paths = []
    if "dbscan" not in getattr(runner, "_profiles", {}):
        return paths
    boroughs, _ = read_boundaries_snapshot(latest_boundaries())
    b = boroughs.to_crs("EPSG:32618")
    geo = gpd.GeoDataFrame.from_features(runner._profiles["dbscan"]["geojson"]["features"], crs="EPSG:4326").to_crs("EPSG:32618")
    summary = runner._profiles["dbscan"]["summary"]
    for name, bbox, title in (
            ("cluster_map_city.png", None, "Seçilen DBSCAN kümeleri — tüm şehir"),
            ("cluster_map_manhattan_brooklyn.png", (580000, 4500000, 592000, 4516000),
             "Seçilen DBSCAN kümeleri — Aşağı/Orta Manhattan ve Kuzey Brooklyn")):
        fig, ax = plt.subplots(figsize=(9, 9))
        b.plot(ax=ax, color="#F1F5F9", edgecolor="#94A3B8", linewidth=0.5)
        geo.plot(ax=ax, column="n_events", cmap="inferno_r", linewidth=0.1, edgecolor="black",
                 legend=True, legend_kwds={"label": "Kümedeki olay sayısı", "shrink": 0.6})
        top = summary.head(10)
        from pyproj import Transformer
        tr = Transformer.from_crs("EPSG:4326", "EPSG:32618", always_xy=True)
        tx, ty = tr.transform(top["centroid_lon"].to_numpy(), top["centroid_lat"].to_numpy())
        for i, (xx, yy) in enumerate(zip(tx, ty), 1):
            if bbox is None or (bbox[0] < xx < bbox[2] and bbox[1] < yy < bbox[3]):
                ax.annotate(str(i), (xx, yy), fontsize=8, fontweight="bold", color=HOTSPOT,
                            xytext=(3, 3), textcoords="offset points")
        if bbox:
            ax.set_xlim(bbox[0], bbox[2])
            ax.set_ylim(bbox[1], bbox[3])
        ax.set_axis_off()
        ax.set_title(title + "\n(dışbükey zarflar görselleştirme sınırıdır; numaralar olay sayısı sırası)",
                     fontsize=11, loc="left", fontweight="bold")
        paths.append(_save(fig, out / name))
    return paths


# ----------------------------------------------------------------------------- rapor
def write_reports(results: dict, runner, out_dir: Path | None = None) -> list[Path]:
    out_dir = Path(out_dir or config.REPORTS_DIR / "phase3")
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    results["_comparison"] = runner.comparison_table() if results["selection"].get("dbscan") else []
    cfg = runner.cfg
    figs = [fig_dbscan_grid(results, cfg, fig_dir), fig_kmeans_elbow(results, fig_dir),
            fig_silhouette_all(results, fig_dir), fig_hdbscan(results, runner, fig_dir),
            fig_kdistance(results, fig_dir), fig_equivalence(results, fig_dir)]
    figs += list(fig_runtime_memory(results, fig_dir))
    if results["_comparison"]:
        figs += [fig_noise(results, fig_dir), fig_sizes(results, runner, fig_dir), fig_temporal(results, fig_dir),
                 fig_sensitivity(results, fig_dir)]
        figs += fig_maps(results, runner, fig_dir)
    # Küçük sonuç dosyaları (git'te izlenir); olay düzeyi üyelikler data/ altında kalır.
    for key in ("experiments", "algorithm_comparison", "model_metadata", "phase4_manifest"):
        if key in results.get("files", {}):
            shutil.copy2(results["files"][key], out_dir / Path(results["files"][key]).name)
    for stale in ("cluster_geometries_dbscan.geojson", "cluster_summary_dbscan.csv"):
        (out_dir / stale).unlink(missing_ok=True)  # tam dosyalar data/ altında; depoda yalnızca ilk 200
    if "dbscan" in getattr(runner, "_profiles", {}):
        top_n = 200
        s = runner._profiles["dbscan"]["summary"].head(top_n).copy()
        s["hour_histogram"] = s["hour_histogram"].map(json.dumps)
        s.to_csv(out_dir / f"cluster_summary_dbscan_top{top_n}.csv", index=False, encoding="utf-8")
        geo = dict(runner._profiles["dbscan"]["geojson"])
        keep = set(s["cluster_id"].tolist())
        geo["features"] = [f for f in geo["features"] if f["properties"]["cluster_id"] in keep]
        geo["note"] = f"Olay sayısına göre ilk {top_n} küme; tüm kümeler data/processed/.../phase3/ altında."
        (out_dir / f"cluster_geometries_dbscan_top{top_n}.geojson").write_text(json.dumps(geo, ensure_ascii=False),
                                                                             encoding="utf-8")
        runner._profiles["kmeans"]["summary"].assign(
            hour_histogram=lambda f: f["hour_histogram"].map(json.dumps)).to_csv(
            out_dir / "cluster_summary_kmeans.csv", index=False, encoding="utf-8")
    write_tables(results, out_dir / "tables")
    slim = {k: v for k, v in results.items() if k not in ("_comparison",)}
    (out_dir / "results.json").write_text(json.dumps(slim, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (out_dir / "KUMELEME_RAPORU.md").write_text(render_markdown(results, runner), encoding="utf-8")
    return figs


def write_tables(results: dict, out: Path) -> list[Path]:
    """Akademik değerlendirme tabloları (CSV, ondalık nokta): tüm değerler results.json'dan."""
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    rows = []
    for x in results["evaluation"]["table"]:
        full, es = x.get("full") or {}, x.get("eval_set") or {}
        rows.append({"experiment_id": x["experiment_id"], "algorithm": x["algorithm"], **x["params"],
                     "status": x["status"], "fit_scope": x["fit_scope"],
                     "n_clusters_full": full.get("n_clusters"), "noise_ratio_full": full.get("noise_ratio"),
                     "largest_cluster_share_full": full.get("largest_cluster_share"),
                     "n_clusters_eval": es.get("n_clusters"), "noise_ratio_eval": es.get("noise_ratio"),
                     "largest_cluster_share_eval": es.get("largest_cluster_share"),
                     "silhouette_common": _metric(x.get("silhouette_common")),
                     "silhouette_haversine": _metric(x.get("silhouette_native")),
                     "davies_bouldin": _metric(x.get("davies_bouldin")), "dbcv": _metric(x.get("dbcv")),
                     "parameter_stability_ari": x.get("parameter_stability_ari"), "inertia": x.get("inertia"),
                     "runtime_s": x.get("runtime_s"), "peak_memory_mb": x.get("peak_memory_mb"),
                     "fit_memory_mb": x.get("fit_memory_mb"), "admissible": x.get("admissible"),
                     "rejection_reasons": "; ".join(x.get("rejection_reasons") or [])})
    tables = {"evaluation_all_configs.csv": rows}
    if results.get("selection_review"):
        tables["dbscan_selection_review.csv"] = [
            {"experiment_id": r["experiment_id"], **r["params"], "selected": r["selected"],
             "noise_ratio_full": r["noise_ratio_full"], "parameter_stability_ari": r["parameter_stability_ari"],
             "silhouette_common": r["silhouette_common"], "dbcv": r["dbcv"], "n_clusters": r["n_clusters"],
             "events_per_cluster_median": r["events_per_cluster"]["median"],
             "events_per_cluster_max": r["events_per_cluster"]["max"],
             "unique_locations_median": r["unique_locations_per_cluster"]["median"],
             "single_location_cluster_share": r["single_location_cluster_share"],
             "extent_diag_median_m": r["extent_diag_m"]["median"], "extent_diag_p95_m": r["extent_diag_m"]["p95"],
             "extent_diag_max_m": r["extent_diag_m"]["max"],
             "clusters_over_200m_share": r["clusters_over_threshold_share"],
             "events_in_clusters_over_200m_share": r["events_in_clusters_over_threshold_share"],
             "active_years_all_share": r["active_years"]["share_all_years"],
             "active_years_10plus_share": r["active_years"]["share_10plus_years"]}
            for r in results["selection_review"]["rows"]]
    if isinstance(results.get("temporal"), dict) and results["temporal"].get("years"):
        tables["temporal_by_year.csv"] = [
            {k: (v.get("median_m") if isinstance(v, dict) else v) for k, v in y.items()}
            for y in results["temporal"]["years"]]
    if isinstance(results.get("sensitivity"), dict) and results["sensitivity"].get("variants"):
        tables["data_quality_sensitivity.csv"] = results["sensitivity"]["variants"]
    if results.get("_comparison"):
        tables["selected_models_comparison.csv"] = [
            {**{k: v for k, v in c.items() if k not in ("silhouette_common", "silhouette_native", "davies_bouldin",
                                                       "dbcv", "parameters", "rejection_reasons")},
             "parameters": json.dumps(c["parameters"]), "silhouette_common": _metric(c["silhouette_common"]),
             "silhouette_haversine": _metric(c.get("silhouette_native")),
             "davies_bouldin": _metric(c["davies_bouldin"]), "dbcv": _metric(c["dbcv"])}
            for c in results["_comparison"]]
    for name, data in tables.items():
        p = out / name
        pd.DataFrame(data).to_csv(p, index=False, encoding="utf-8")
        paths.append(p)
    return paths


def temporal_interpretation(t: dict) -> dict[str, Any]:
    """Zamansal kararlılık ile hacim değişimini ayıran özet (dönem ortalamaları; 2020 kırılımı)."""
    years = t["years"]
    pre = [y for y in years if y["year"] < 2020]
    post = [y for y in years if y["year"] >= 2020]

    def med(rows: list[dict], key: str) -> float | None:
        v = [r[key] for r in rows if r.get(key) is not None]
        return float(np.median(v)) if v else None

    return {"events_pre_median": med(pre, "n_events"), "events_post_median": med(post, "n_events"),
            "fixed_clusters_pre_median": med(pre, "dbscan_n_clusters"),
            "fixed_clusters_post_median": med(post, "dbscan_n_clusters"),
            "fixed_noise_min": min((y["dbscan_noise_ratio"] for y in years if y.get("dbscan_noise_ratio") is not None),
                                   default=None),
            "fixed_jaccard_undefined_years": [y["year"] for y in years[1:] if y.get("jaccard_vs_prev_year") is None],
            "fixed_few_cluster_years": [y["year"] for y in years if (y.get("dbscan_n_clusters") or 0) <= 5],
            "scaled_ms_pre": sorted({y["scaled_min_samples"] for y in pre if y.get("scaled_min_samples")}),
            "scaled_ms_post": sorted({y["scaled_min_samples"] for y in post if y.get("scaled_min_samples")}),
            "scaled_clusters_pre_median": med(pre, "scaled_n_clusters"),
            "scaled_clusters_post_median": med(post, "scaled_n_clusters"),
            "scaled_jaccard_pre_median": med(pre, "scaled_jaccard_vs_prev_year"),
            "scaled_jaccard_post_median": med(post, "scaled_jaccard_vs_prev_year"),
            "scaled_noise_pre_median": med(pre, "scaled_noise_ratio"),
            "scaled_noise_post_median": med(post, "scaled_noise_ratio")}


def render_markdown(r: dict, runner) -> str:
    L: list[str] = []
    w = L.append
    integ = r["integrity"]
    w("# Faz 3 — Otomatik Kümeleme Deney Raporu")
    w("")
    w("> `saferoute cluster` ile üretilmiştir; tüm değerler deney kaydından ve `results.json`'dan okunmuştur.")
    w("")
    m = r["meta"]
    w(f"- Veri sürümü: `{m['dataset_version']}` · İşlem sürümü: `{m['processing_version']}`")
    total_s = sum(v for v in (r.get("stage_seconds") or {}).values() if v)
    w(f"- Deney sayısı: {m['n_experiments']} — durumlar: {m['status_counts']} · Aşama süreleri toplamı: {_n(total_s, 1)} sn "
      f"(kontrol noktalı parçalar hâlinde çalıştırıldı)")
    w(f"- Yazılım: scikit-learn {m['software'].get('scikit-learn')}, hdbscan {m['software'].get('hdbscan')}, "
      f"numpy {m['software'].get('numpy')}, Python {m['software'].get('python')}")
    w("")
    w("## 1. Veri ve matris bütünlüğü")
    w("")
    w(f"Ham {_n(integ['raw_rows'])} kayıt · uygun olay {_n(integ['eligible_events'])} · benzersiz konum "
      f"{_n(integ['unique_locations'])} · ağırlık toplamı {_n(integ['weight_sum'])} · 00:00 toplam "
      f"{_n(integ['midnight_total'])} (uygun kümede {_n(integ['midnight_in_eligible'])}, dışında "
      f"{_n(integ['midnight_outside_eligible'])}) · D (00:00 hariç) {_n(integ['D_no_midnight_rows'])} satır.")
    w("")
    w("| Kontrol | Sonuç | Ayrıntı |")
    w("|---|:---:|---|")
    for k, v in integ["checks"].items():
        w(f"| `{k}` | {'✓' if v['ok'] else '✗'} | {v['detail'] if v['detail'] is not None else ''} |")
    w("")
    w("## 2. Ağırlıklı k-mesafe")
    w("")
    w("| k | 0 m payı | p25 | p50 | p75 | p90 | p95 |")
    w("|---:|---:|---:|---:|---:|---:|---:|")
    for k, v in r["kdistance"]["by_k"].items():
        p = v["percentiles_m"]
        w(f"| {k} | {_pct(v['zero_distance_share'])} | {_n(p['25'], 1)} | {_n(p['50'], 1)} | {_n(p['75'], 1)} | "
          f"{_n(p['90'], 1)} | {_n(p['95'], 1)} |")
    w("")
    w("![k-mesafe](figures/k_distance.png)")
    w("")
    w("## 3. Ağırlıklı DBSCAN eşdeğerliği (gerçek veri)")
    w("")
    w("| Senaryo | eps | ms | Olay | Benzersiz | Çekirdek aynı | Gürültü aynı | Çekirdek ARI | Tüm ARI | "
      "Farklı sınır / sınır | Farklılar çok kümeli komşulukta | Çift (kayıt → ağırlıklı) | Süre sn (kayıt → ağırlıklı) |")
    w("|---|---:|---:|---:|---:|:---:|:---:|---:|---:|---:|:---:|---:|---:|")
    for s in r["equivalence"]["scenarios"]:
        if s.get("core_identical") is None:
            w(f"| {s['label']} | {s['eps_m']} | {s['min_samples']} | — | — | — | — | — | — | — | — | — | "
              f"kayıt: {s['records_status']}, ağırlıklı: {s['weighted_status']} |")
            continue
        w(f"| {s['label']} | {s['eps_m']} | {s['min_samples']} | {_n(s['n_events'])} | {_n(s['n_unique_locations'])} | "
          f"{'✓' if s['core_identical'] else '✗'} | {'✓' if s['noise_identical'] else '✗'} | {_f(s['core_partition_ari'], 4)} | "
          f"{_f(s['ari_all_events'], 6)} | {_n(s['border_events_different_cluster'])} / {_n(s['border_events'])} | "
          f"{'✓' if s['differing_borders_all_adjacent_to_multiple_clusters'] in (True, None) else '✗'} | "
          f"{_n(s['records_neighbor_pairs'])} → {_n(s['weighted_neighbor_pairs'])} | "
          f"{_f(s['records_runtime_s'], 2)} → {_f(s['weighted_runtime_s'], 2)} |")
    fa = r["equivalence"]["full_data_records_attempt"]
    w("")
    w(f"Tam veri kayıt düzeyi denemesi (`{fa['experiment_id']}`): **{fa['status']}** — {fa.get('error') or ''}")
    w("")
    w("![Eşdeğerlik](figures/weighted_equivalence.png)")
    w("")
    w("## 4. DBSCAN ızgarası (tam veri, ağırlıklı)")
    w("")
    w("| eps | ms | Durum | Küme | Gürültü | En büyük pay | Siluet ortak | Siluet haversine | DB | DBCV | Kararlılık ARI | Fit sn | Fit MB | Kabul |")
    w("|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for x in _rows(r, "dbscan"):
        p = x["params"]
        if x["status"] != "success":
            w(f"| {p['eps_m']} | {p['min_samples']} | {x['status']} | — | — | — | — | — | — | — | — | — | — | {(x.get('error') or '')[:60]} |")
            continue
        fu = x["full"]
        w(f"| {p['eps_m']} | {p['min_samples']} | ✓ | {_n(fu['n_clusters'])} | {_f(fu['noise_ratio'])} | "
          f"{_f(fu['largest_cluster_share'], 4)} | {_f(_metric(x['silhouette_common']))} | "
          f"{_f(_metric(x.get('silhouette_native')))} | {_f(_metric(x['davies_bouldin']))} | {_f(_metric(x['dbcv']))} | "
          f"{_f(x.get('parameter_stability_ari'))} | {_f(x['runtime_s'], 1)} | {_n(x['fit_memory_mb'])} | "
          f"{'✓' if x.get('admissible') else '✗ ' + '; '.join(x.get('rejection_reasons', []))} |")
    w("")
    w("![DBSCAN](figures/dbscan_parameter_sensitivity.png)")
    w("")
    w("## 5. K-Means ızgarası (tam veri, ağırlıklı)")
    w("")
    w("| k | Atalet (m²) | Siluet ortak | DB | DBCV | En büyük pay | Fit sn |")
    w("|---:|---:|---:|---:|---:|---:|---:|")
    for x in sorted(_rows(r, "kmeans"), key=lambda q: q["params"]["k"]):
        if x["status"] != "success":
            continue
        w(f"| {x['params']['k']} | {x['inertia']:.3e} | {_f(_metric(x['silhouette_common']))} | "
          f"{_f(_metric(x['davies_bouldin']))} | {_f(_metric(x['dbcv']))} | {_f(x['full']['largest_cluster_share'], 4)} | "
          f"{_f(x['runtime_s'], 1)} |")
    w(f"\nDirsek (kneedle) k = {r['selection'].get('kmeans_elbow_k')}.")
    w("")
    w("![K-Means](figures/kmeans_elbow_silhouette.png)")
    w("")
    w("## 6. HDBSCAN ızgarası (100k olay örneklemi)")
    w("")
    w("| mcs | ms | Küme | Gürültü | En büyük pay | Siluet ortak | DB | DBCV | Üyelik olasılığı medyan | Fit sn | Fit MB | Kabul |")
    w("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for x in _rows(r, "hdbscan"):
        p = x["params"]
        if x["status"] != "success":
            w(f"| {p['min_cluster_size']} | {p['min_samples']} | {x['status']} | | | | | | | | | |")
            continue
        es = x["eval_set"]
        w(f"| {p['min_cluster_size']} | {p['min_samples']} | {_n(es['n_clusters'])} | {_f(es['noise_ratio'])} | "
          f"{_f(es['largest_cluster_share'], 4)} | {_f(_metric(x['silhouette_common']))} | {_f(_metric(x['davies_bouldin']))} | "
          f"{_f(_metric(x['dbcv']))} | {_f(x['membership_probability']['median'])} | {_f(x['runtime_s'], 1)} | "
          f"{_n(x['fit_memory_mb'])} | {'✓' if x.get('admissible') else '✗ ' + '; '.join(x.get('rejection_reasons', []))} |")
    w("")
    w("![HDBSCAN](figures/hdbscan_distribution.png)")
    w("")
    if r["_comparison"]:
        w("## 7. Seçilen konfigürasyonların karşılaştırması (ortak değerlendirme kümesi)")
        w("")
        w("| Algoritma | Parametreler | Fit kapsamı | Küme (tam) | Gürültü (tam) | Küme (ortak) | Gürültü (ortak) | "
          "En büyük pay (ortak) | Siluet ortak | DB | DBCV | Fit sn | Fit MB |")
        w("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for c in r["_comparison"]:
            w(f"| {ALG_TR[c['algorithm']]} | `{json.dumps(c['parameters'])}` | {c['fit_scope']} | "
              f"{_n(c['n_clusters_full'])} | {_f(c['noise_ratio_full'])} | {_n(c['eval_set_n_clusters'])} | "
              f"{_f(c['eval_set_noise_ratio'])} | {_f(c['eval_set_largest_cluster_share'], 4)} | "
              f"{_f(_metric(c['silhouette_common']))} | {_f(_metric(c['davies_bouldin']))} | {_f(_metric(c['dbcv']))} | "
              f"{_f(c['runtime_s'], 1)} | {_n(c['fit_memory_mb'])} |")
        w("")
        for f in ("silhouette_all_configs", "noise_ratio_comparison", "cluster_size_distribution", "runtime_comparison",
                  "memory_comparison"):
            w(f"![{f}](figures/{f}.png)")
            w("")
        rv = r.get("selection_review")
        if rv:
            w("### 7.1 Seçilen DBSCAN'in gerekçe sınaması (kayıtlı etiketlerden; seçim kuralı değiştirilmez)")
            w("")
            w("Uzanım = küme olaylarının UTM sınırlayıcı kutu köşegeni; uzun köşegen yoğunluk zincirlenmesinin "
              "göstergesidir. Etkin yıl = kümenin olay içerdiği yıl sayısı (2013–2025).")
            w("")
            w("| eps | ms | Seçilen | Küme | Gürültü | Olay/küme medyan · maks | Konum/küme medyan | Tek konumlu küme | "
              "Uzanım medyan · p95 · maks (m) | >200 m küme | 13 yılın tamamında etkin | ARI | Siluet | DBCV |")
            w("|---:|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
            for x in rv["rows"]:
                e, a = x["extent_diag_m"], x["active_years"]
                w(f"| {x['params']['eps_m']} | {x['params']['min_samples']} | {'✓' if x['selected'] else ''} | "
                  f"{_n(x['n_clusters'])} | {_f(x['noise_ratio_full'])} | {_n(x['events_per_cluster']['median'])} · "
                  f"{_n(x['events_per_cluster']['max'])} | {_n(x['unique_locations_per_cluster']['median'])} | "
                  f"{_pct(x['single_location_cluster_share'])} | {_n(e['median'])} · {_n(e['p95'])} · {_n(e['max'])} | "
                  f"{_pct(x['clusters_over_threshold_share'], 2)} | {_pct(a['share_all_years'])} | "
                  f"{_f(x['parameter_stability_ari'])} | {_f(x['silhouette_common'])} | {_f(x['dbcv'])} |")
            w("")
            sel_r = next((x for x in rv["rows"] if x["selected"]), None)
            if sel_r:
                e = sel_r["extent_diag_m"]
                others = [x for x in rv["rows"] if x["params"]["eps_m"] != sel_r["params"]["eps_m"]]
                other_txt = "; ".join(
                    f"eps={x['params']['eps_m']}/ms={x['params']['min_samples']}: maks {_n(x['extent_diag_m']['max'])} m, "
                    f">200 m küme payı {_pct(x['clusters_over_threshold_share'], 1)}" for x in others)
                w(f"- **Zincirlenme:** seçilen konfigürasyonda en geniş küme köşegeni {_n(e['max'])} m; 200 m'yi aşan "
                  f"küme payı {_pct(sel_r['clusters_over_threshold_share'], 2)}."
                  + (f" Karşılaştırma — {other_txt}." if other_txt else ""))
                w(f"- **Coğrafi ölçek:** medyan {_n(sel_r['unique_locations_per_cluster']['median'])} benzersiz konum ve "
                  f"{_n(e['median'])} m uzanım (kavşak ölçeği); tek koordinattan oluşan küme payı "
                  f"{_pct(sel_r['single_location_cluster_share'])} — kümeler salt tekrarlanan geokod değildir.")
                w(f"- **Zaman sürekliliği:** 13 yılın tamamında en az bir olay içeren küme payı "
                  f"{_pct(sel_r['active_years']['share_all_years'])} (kronik sıcak nokta).")
                w(f"- **Bedel:** gürültü oranı {_pct(sel_r['noise_ratio_full'])}; model şehir genelini değil "
                  "kronik yoğunlaşmaları temsil eder. Daha düşük min_samples daha çok olayı kapsar fakat parametre "
                  "kararlılığı (ARI) ve yıllar arası süreklilik düşer.")
                same = sorted([x for x in rv["rows"] if x["params"]["eps_m"] == sel_r["params"]["eps_m"]],
                              key=lambda x: x["params"]["min_samples"])
                w("- **Siluetin yorumu:** küçük eps kümeleri kompakt ve birbirinden uzak olduğu için siluet yüksek çıkar; "
                  "bu, yoğunluk yapısının değil kavşak ölçeğindeki ayrışmanın ölçüsüdür. Aynı eps'te min_samples'a göre "
                  "DBCV: " + ", ".join(f"ms={x['params']['min_samples']}: {_f(x['dbcv'])}" for x in same)
                  + " — gürültü payı ile yoğunluk-geçerliliği arasındaki ödünleşim.")
                w("")
        t = r["temporal"]
        w("## 8. Zamansal kararlılık")
        w("")
        w("(a) = sabit parametreler (yıllık sıcak nokta); (c) = min_samples yıllık hacme ölçeklenmiş.")
        w("")
        w("| Yıl | Olay | (a) Küme | (a) Gürültü | (a) Jaccard | (a) Önceki yıl kümesinde | (c) ms | (c) Küme | (c) Gürültü | "
          "(c) En büyük pay | (c) Jaccard | K-Means merkez kayması medyan (m) |")
        w("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for y in t["years"]:
            w(f"| {y['year']} | {_n(y['n_events'])} | {_n(y.get('dbscan_n_clusters'))} | {_f(y.get('dbscan_noise_ratio'))} | "
              f"{_f(y.get('jaccard_vs_prev_year'))} | {_pct(y.get('recurrence_share'))} | {_n(y.get('scaled_min_samples'))} | "
              f"{_n(y.get('scaled_n_clusters'))} | {_f(y.get('scaled_noise_ratio'))} | "
              f"{_f(y.get('scaled_largest_cluster_share'), 4)} | {_f(y.get('scaled_jaccard_vs_prev_year'))} | "
              f"{_n((y.get('kmeans_centroid_shift') or {}).get('median_m'))} |")
        ti = temporal_interpretation(t)
        w("")
        w("**Zamansal kararlılık ile kaza hacmi değişiminin ayrımı.** Yıllık olay sayısı medyanı 2013–2019'da "
          f"{_n(ti['events_pre_median'])}, 2020–2025'te {_n(ti['events_post_median'])}. (a) Sabit eşikte "
          f"min_samples tam veri için seçilmiş değerdir; tek yılda bu yoğunluğa ulaşan konum çok azdır (küme "
          f"medyanı {_n(ti['fixed_clusters_pre_median'])} → {_n(ti['fixed_clusters_post_median'])}, gürültü ≥ "
          f"{_f(ti['fixed_noise_min'])}). Bu yüzden (a)'daki düşüş bir *kararlılık* kaybı değil, eşiğin yıllık "
          "hacme göre çok yüksek kalmasıdır; boş kapsamlı yıllarda Jaccard tanımsızdır "
          f"(N/A: {', '.join(map(str, ti['fixed_jaccard_undefined_years'])) or '—'}). (a) sütunlarındaki oranlar "
          f"birkaç kümeye dayandığı yıllarda (≤5 küme: {', '.join(map(str, ti['fixed_few_cluster_years'])) or '—'}) "
          "istatistiksel olarak anlamlı değildir. (c) Hacme ölçekli eşikte "
          f"(ms {ti['scaled_ms_pre']} → {ti['scaled_ms_post']}) yıllık küme sayısı benzer düzeyde kalır "
          f"({_n(ti['scaled_clusters_pre_median'])} → {_n(ti['scaled_clusters_post_median'])}); ardışık yıl Jaccard "
          f"medyanı {_f(ti['scaled_jaccard_pre_median'])} → {_f(ti['scaled_jaccard_post_median'])}. Ölçekli "
          "eşikteki bu daha küçük düşüş, hacim etkisi büyük ölçüde giderildikten sonra kalan mekânsal değişimdir; "
          f"ancak ms {ti['scaled_ms_post']} düzeyine indiğinde küçük, rastlantısal kümeler de oluşabildiğinden 2020 sonrası değerler "
          "dikkatle yorumlanmalıdır. (b) Kalıcılık analizi tam veri modelinin aynı kümelerini yıllara göre izler "
          "ve hacimden bağımsız bir süreklilik ölçüsüdür.")
        pers = t["persistence"]
        w("")
        w(f"Kalıcılık (tam veri modeli, {_n(pers['n_clusters'])} küme): {len(pers['years'])} yılın tamamında etkin "
          f"{_pct(pers['share_active_all_years'])}, 10+ yılda etkin {_pct(pers['share_active_10plus_years'])}; "
          f"tüm yıllarda etkin kümelerdeki olay payı {_pct(pers['events_in_clusters_active_all_years_share'])}.")
        w("")
        w("| Yıllar | Spearman (küme olay sayıları) | Üst-50 örtüşmesi |")
        w("|---|---:|---:|")
        for c in pers["consecutive"]:
            top_key = next(k for k in c if k.startswith("top"))
            w(f"| {c['years']} | {_f(c['spearman_cluster_counts'])} | {_pct(c[top_key], 0)} |")
        w("")
        w("![Zamansal](figures/temporal_stability.png)")
        w("")
        w("## 9. Veri kalitesi duyarlılığı")
        w("")
        w("| Varyant | Hariç olay | Kırpma | Küme | Gürültü | Temel küme (ortak) | Temel gürültü (ortak) | ARI | Gürültü uyumu | Korunan temel küme | Korunan kümelerdeki olay |")
        w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for v in r["sensitivity"]["variants"]:
            if v["status"] != "success":
                w(f"| {v['variant']} | {v['status']} | | | | | | | | | |")
                continue
            w(f"| {v['variant']} | {_n(v['excluded_events'])} | {_n(v['weight_cap'])} | {_n(v['n_clusters'])} | "
              f"{_f(v['noise_ratio'])} | {_n(v['baseline_n_clusters_on_common'])} | {_f(v['baseline_noise_ratio_on_common'])} | "
              f"{_f(v['ari_vs_baseline_common_events'], 4)} | {_f(v['noise_status_agreement'], 4)} | "
              f"{_pct(v['baseline_clusters_retained_share'])} | {_pct(v['baseline_events_in_retained_clusters_share'])} |")
        w("")
        w("![Duyarlılık](figures/data_quality_sensitivity.png)")
        w("")
        pr = r["profiles"]
        w("## 10. Küme profilleri (seçilen DBSCAN, olay sayısına göre ilk 15)")
        w("")
        w(f"{_n(pr['dbscan_counts']['clusters'])} küme, {_n(pr['dbscan_counts']['events'])} kümelenmiş olay; "
          f"yaralanmalı {_n(pr['dbscan_counts']['injury_crashes'])}, ölümlü {_n(pr['dbscan_counts']['fatal_crashes'])}.")
        w("")
        w("| # | Olay | Konum | İlçe | Merkez (enlem, boylam) | Zarf km² | r90 m | Tarih aralığı | Yaralanmalı | Ölümlü | Zirve saat | Başlıca cadde |")
        w("|---:|---:|---:|---|---|---:|---:|---|---:|---:|---:|---|")
        for x in pr["dbscan_top"][:15]:
            street = json.loads(x["top_streets"])
            w(f"| {x['rank_by_events']} | {_n(x['n_events'])} | {_n(x['n_unique_locations'])} | {x['dominant_borough'] or '—'} | "
              f"{x['centroid_lat']:.5f}, {x['centroid_lon']:.5f} | {_f(x['hull_area_km2'], 4)} | {_n(x['radius_p90_m'])} | "
              f"{x['date_min']} → {x['date_max']} | {_n(x['injury_crashes'])} | {_n(x['fatal_crashes'])} | {x['peak_hour']} | "
              f"{street[0]['value'] if street else '—'} |")
        w("")
        w("![Harita](figures/cluster_map_city.png)")
        w("")
        w("![Harita](figures/cluster_map_manhattan_brooklyn.png)")
        w("")
    fc = r["final_choice"]
    w("## 11. Seçim")
    w("")
    w(f"- Seçim ölçütleri (önceden tanımlı): `{json.dumps(r['selection']['criteria'], ensure_ascii=False)}`")
    w(f"- Seçilen: DBSCAN `{r['selection']['dbscan']}`, K-Means `{r['selection']['kmeans']}`, HDBSCAN `{r['selection']['hdbscan']}`")
    w(f"- Ana model: **{fc['primary_algorithm']}** — {fc['rule']}")
    w("")
    w("## 12. Çıktı dosyaları")
    w("")
    for k, v in r.get("files", {}).items():
        w(f"- `{k}`: `{Path(v).relative_to(config.REPO_ROOT) if str(v).startswith(str(config.REPO_ROOT)) else v}`")
    w("")
    return "\n".join(L)
