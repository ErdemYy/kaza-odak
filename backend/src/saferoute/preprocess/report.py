"""Faz 2 raporları: şekiller, CSV tabloları, otomatik Markdown ve öznitelik seçimi raporu.

Tüm sayılar ``preprocessing_summary.json`` (hat çıktısı) ve işlenmiş Parquet'ten okunur.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from saferoute import config  # noqa: E402
from saferoute.eda.figures import BOROUGH_TR, HOTSPOT, MUTED, PRIMARY, WARNING, _save, _style, _thousands  # noqa: E402
from saferoute.preprocess import features  # noqa: E402
from saferoute.preprocess.pipeline import output_paths  # noqa: E402
from saferoute.preprocess.vehicles import CATEGORY_LABELS_TR  # noqa: E402

STATUS_TR = {
    "missing": "Eksik", "unparseable": "Ayrıştırılamaz", "non_finite": "Sonlu değil", "zero": "Sıfır (0,0)",
    "invalid_range": "Geçersiz aralık", "outside_nyc_far": "NYC dışı (uzak)",
    "outside_nyc_nearshore": "Poligon dışı, kıyıya yakın", "boundary_ambiguous": "Sınırda belirsiz",
    "valid_in_boundary": "Resmî ilçe sınırı içinde",
}
PERIOD_TR = {"night": "gece (00–06)", "morning": "sabah (06–12)", "afternoon": "öğleden sonra (12–18)",
             "evening": "akşam (18–24)"}
INFERENCE_TR = {"inferred": "poligonla çıkarıldı", "ambiguous_boundary": "sınırda belirsiz",
                "outside_polygons": "poligon dışında", "no_valid_coordinate": "geçerli koordinat yok"}
FLAG_TR = {"negative_value": "Negatif değer", "total_missing": "Toplam eksik", "component_missing": "Alt alan eksik",
           "total_lt_components": "Toplam < alt alanlar", "total_gt_components": "Toplam > alt alanlar", "ok": "Tutarlı"}


def _n(x: Any) -> str:
    if x is None:
        return "—"
    if isinstance(x, float) and not float(x).is_integer():
        return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(x):,}".replace(",", ".")


def _pv(pct: float | None) -> str:
    """Yüzde değerini Türkçe biçimde yazar (ör. %0,15)."""
    if pct is None:
        return "—"
    return "<%0,01" if 0 < pct < 0.005 else f"%{pct:.2f}".replace(".", ",")


def _p(part: float, total: float) -> str:
    if not total:
        return "—"
    v = 100.0 * part / total
    return "<%0,01" if 0 < v < 0.005 else f"%{v:.2f}".replace(".", ",")


# --------------------------------------------------------------------------- şekiller
def fig_missing_before_after(s: dict, out: Path) -> Path:
    cc = s["phase1_crosscheck"]
    rows = s["rows"]["raw"]
    items = [
        ("İlçe eksik", s["boroughs"]["original_missing"], s["boroughs"]["still_missing"]),
        ("Kümelemede kullanılamaz koordinat", rows - cc["valid_coordinates_bbox"]["phase2"],
         rows - s["rows"]["eligible_for_spatial_clustering"]),
    ]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    xs = np.arange(len(items))
    ax.bar(xs - 0.2, [b for _, b, _ in items], width=0.4, color=MUTED, label="Önce (ham / Faz 1 yöntemi)")
    ax.bar(xs + 0.2, [a for _, _, a in items], width=0.4, color=PRIMARY, label="Sonra (Faz 2)")
    ax.set_xticks(xs, [t for t, _, _ in items])
    for i, (_, b, a) in enumerate(items):
        ax.text(i - 0.2, b, _n(b), ha="center", va="bottom", fontsize=8)
        ax.text(i + 0.2, a, _n(a), ha="center", va="bottom", fontsize=8)
    _style(ax, "Eksik / kullanılamaz değerler: öncesi ve sonrası", "", "Kayıt")
    _thousands(ax)
    ax.legend(frameon=False, fontsize=9)
    fig.text(0.01, 0.01, "Koordinatlar doldurulmaz; fark yalnızca kaba kutu yerine resmî poligon + kıyı tamponu "
             "kullanılmasından gelir. İlçe, yalnızca resmî poligon içindeki noktalar için çıkarılır.", fontsize=7.5)
    return _save(fig, out / "missing_before_after.png")


def fig_coordinate_status(s: dict, out: Path) -> Path:
    counts = {k: v for k, v in s["coordinates"]["status_counts"].items()}
    keys = list(counts)[::-1]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    colors = [PRIMARY if k == "valid_in_boundary" else WARNING if k in ("outside_nyc_nearshore", "boundary_ambiguous")
              else HOTSPOT if k in ("zero", "invalid_range", "outside_nyc_far") else MUTED for k in keys]
    vals = [max(counts[k], 0) for k in keys]
    ax.barh([STATUS_TR[k] for k in keys], [v if v > 0 else np.nan for v in vals], color=colors)
    ax.set_xscale("log")
    for i, v in enumerate(vals):
        if v > 0:
            ax.text(v * 1.1, i, _n(v), va="center", fontsize=8)
        else:
            ax.text(0.01, i, "0", va="center", fontsize=8, transform=ax.get_yaxis_transform())
    _style(ax, "Koordinat kalite durumu (logaritmik eksen)", "Kayıt (log)", "")
    ax.grid(axis="x", alpha=0.25)
    return _save(fig, out / "coordinate_quality_status.png")


def fig_borough_inference(processed: pd.DataFrame, out: Path) -> Path:
    t = pd.crosstab(processed["borough_final"].astype(object).fillna("(eksik)"),
                    processed["borough_source"].astype(str))
    order = [b for b in config.BOROUGHS if b in t.index] + (["(eksik)"] if "(eksik)" in t.index else [])
    t = t.reindex(order).fillna(0)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    left = np.zeros(len(t))
    for col, color, label in (("original", PRIMARY, "Bildirilen ilçe"),
                              ("inferred_polygon", WARNING, "Poligonla kurtarılan"),
                              ("none", MUTED, "İlçe yok")):
        if col in t.columns:
            ax.barh([BOROUGH_TR.get(b, "İlçesiz") for b in t.index], t[col], left=left, color=color, label=label)
            left += t[col].to_numpy()
    _style(ax, "Nihai ilçe ve kaynağı (resmî DCP poligonları)", "Kayıt", "")
    ax.grid(axis="x", alpha=0.25)
    ax.set_xlim(0, left.max() * 1.08)
    _thousands(ax, "x")
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    return _save(fig, out / "borough_inference.png")


def fig_borough_conflicts(s: dict, out: Path, top: int = 12) -> Path:
    pairs = list(s["boroughs"]["conflict_pairs"].items())[:top][::-1]
    labels = [" → ".join(BOROUGH_TR.get(p, p) for p in k.split(" -> ")) for k, _ in pairs]
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(pairs) + 1.2))
    ax.barh(labels, [v for _, v in pairs], color=HOTSPOT)
    for i, (_, v) in enumerate(pairs):
        ax.text(v, i, " " + _n(v), va="center", fontsize=8)
    _style(ax, f"İlçe uyuşmazlıkları: bildirilen → poligon (toplam {_n(s['boroughs']['conflicts'])})", "Kayıt", "")
    ax.grid(axis="x", alpha=0.25)
    return _save(fig, out / "borough_conflicts.png")


def fig_repetition(s: dict, out: Path) -> Path:
    d = s["repetition"]["distribution"]
    labels = list(d)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    a1.bar(labels, [d[k]["locations"] for k in labels], color=PRIMARY)
    _style(a1, "Benzersiz konum sayısı", "Konum başına kaza", "Konum")
    _thousands(a1)
    a2.bar(labels, [d[k]["records"] for k in labels], color=WARNING)
    _style(a2, "Bu konumlardaki kaza sayısı", "Konum başına kaza", "Kaza")
    _thousands(a2)
    fig.suptitle("Koordinat tekrar sıklığı (kümelemeye uygun kayıtlar; aralık genişlikleri eşit değildir)",
                 x=0.01, ha="left", fontweight="bold")
    return _save(fig, out / "coordinate_repetition.png")


def fig_midnight(s: dict, out: Path) -> Path:
    hours = s["temporal"]["hour_counts"]
    ratios = s["temporal"]["minute_heaping"]["per_hour"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4))
    hs = sorted(int(h) for h in hours)
    a1.bar(hs, [hours[str(h)] for h in hs], color=PRIMARY)
    _style(a1, "Saate göre kaza", "Saat", "Kaza")
    a1.set_xticks(range(0, 24, 2))
    _thousands(a1)
    rh = sorted(int(h) for h in ratios)
    a2.bar(rh, [np.nan if ratios[str(h)]["ratio"] is None else ratios[str(h)]["ratio"] for h in rh], color=[HOTSPOT if h == 0 else MUTED for h in rh])
    _style(a2, "Tam saat (HH:00) yığılma oranı", "Saat", "HH:00 / diğer dakikalar ort.")
    a2.set_xticks(range(0, 24, 2))
    a2.axhline(1, color="black", linewidth=0.8, linestyle="--")
    return _save(fig, out / "hour_and_midnight.png")


def fig_vehicle_categories(s: dict, mapping: pd.DataFrame, out: Path) -> Path:
    top = mapping.head(15).iloc[::-1]
    cats = s["vehicles"]["by_category"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.2))
    a1.barh(top["normalized"], top["count"], color=MUTED)
    _style(a1, f"Önce: en sık 15 etiket ({_n(s['vehicles']['normalized_distinct_labels'])} farklı)", "Etiket geçişi", "")
    _thousands(a1, "x")
    a1.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4))
    a1.grid(axis="x", alpha=0.25)
    items = list(cats.items())[::-1]
    a2.barh([CATEGORY_LABELS_TR[k] for k, _ in items], [v for _, v in items], color=PRIMARY)
    _style(a2, f"Sonra: {s['vehicles']['category_count']} üst kategori", "Etiket geçişi", "")
    _thousands(a2, "x")
    a2.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4))
    a2.grid(axis="x", alpha=0.25)
    fig.text(0.01, 0.01, "Etiket geçişi = beş araç sütunundaki dolu etiket sayısı (kaza sayısı değil).", fontsize=8)
    return _save(fig, out / "vehicle_categories_before_after.png")


def fig_feature_sets(s: dict, out: Path) -> Path:
    fs = s["feature_sets"]
    names = list(fs)[::-1]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    colors = [WARNING if fs[n]["level"] == "unique_location" else PRIMARY for n in names]
    ax.barh(names, [fs[n]["rows"] for n in names], color=colors)
    for i, n in enumerate(names):
        ax.text(fs[n]["rows"], i, f"  {_n(fs[n]['rows'])} × {len(fs[n]['features'])}", va="center", fontsize=8)
    _style(ax, "Model öznitelik matrisleri (satır × öznitelik)", "Satır", "")
    ax.grid(axis="x", alpha=0.25)
    _thousands(ax, "x")
    ax.set_xlim(0, max(fs[n]["rows"] for n in names) * 1.3)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=PRIMARY, label="Kayıt düzeyi"), Patch(color=WARNING, label="Benzersiz konum + ağırlık")],
              frameon=False, fontsize=9, loc="lower right")
    return _save(fig, out / "feature_sets.png")


# --------------------------------------------------------------------------- raporlar
def write_reports(summary: dict, processed: pd.DataFrame, mapping: pd.DataFrame,
                  out_dir: Path | None = None, docs_dir: Path | None = None) -> list[Path]:
    out_dir = Path(out_dir or config.REPORTS_DIR / "phase2")
    docs_dir = Path(docs_dir or config.DOCS_DIR)
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    summary = dict(summary)
    summary["vehicles"] = {**summary["vehicles"],
                           "vehicle_1_missing_raw": int(processed["vehicle_type_code1"].isna().sum())}
    figs = [
        fig_missing_before_after(summary, fig_dir), fig_coordinate_status(summary, fig_dir),
        fig_borough_inference(processed, fig_dir), fig_borough_conflicts(summary, fig_dir),
        fig_repetition(summary, fig_dir), fig_midnight(summary, fig_dir),
        fig_vehicle_categories(summary, mapping, fig_dir), fig_feature_sets(summary, fig_dir),
    ]
    (out_dir / "preprocessing_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str),
                                                        encoding="utf-8")
    # Ham sınır dosyası git dışında; onu tanımlayan manifest rapora eşlik eder (izlenebilirlik).
    bsnap = config.RAW_DIR / config.BOROUGH_BOUNDARIES_DATASET_ID / summary["lineage"]["boundaries_snapshot"] / "manifest.json"
    if bsnap.exists():
        (out_dir / "boundaries_manifest.json").write_text(bsnap.read_text(encoding="utf-8"), encoding="utf-8")
    mapping.to_csv(out_dir / "vehicle_type_mapping.csv", index=False, encoding="utf-8")
    pd.DataFrame([{"bildirilen": k.split(" -> ")[0], "poligon": k.split(" -> ")[1], "kayit": v}
                  for k, v in summary["boroughs"]["conflict_pairs"].items()]).to_csv(
        out_dir / "borough_conflict_pairs.csv", index=False, encoding="utf-8")
    pd.DataFrame(summary["repetition"]["top_locations"]).to_csv(out_dir / "top_repeated_locations.csv",
                                                                 index=False, encoding="utf-8")
    raw_missing = {c: v for c, v in summary["standardize"].get("raw_missing_pct", {}).items()}
    table = features.feature_selection_table(processed, raw_missing)
    table.to_csv(out_dir / "feature_selection.csv", index=False, encoding="utf-8")
    (docs_dir / "feature_selection_report.md").write_text(render_feature_selection(table, summary), encoding="utf-8")
    (out_dir / "ON_ISLEME_RAPORU.md").write_text(render_markdown(summary, mapping), encoding="utf-8")
    return figs


def render_feature_selection(table: pd.DataFrame, s: dict) -> str:
    lines = [
        "# Öznitelik Seçimi Raporu — Faz 2",
        "",
        f"> `saferoute preprocess` tarafından otomatik üretilmiştir. Kaynak: `{s['lineage']['raw_snapshot']}`, "
        f"yapılandırma özeti `{s['lineage']['config_sha256'][:12]}…`. Eksik oranları ölçülmüştür.",
        "",
        "Modeller: **A** = Spatial DBSCAN (Haversine), **B** = Spatial K-Means (EPSG:32618), "
        "**C** = HDBSCAN (Haversine), **D** = deneysel uzay-zaman. Gerekçeler: `docs/feature_candidates.md`, "
        "`docs/phase2/TEKNIK_RAPOR.md`.",
        "",
        "| Öznitelik | Anlam | Köken | Veri türü | Eksik % | Dönüşüm | Modeller | Dahil edilmeme nedeni | Filtre | Yorum |",
        "|---|---|---|---|---:|---|---|---|---|---|",
    ]
    for r in table.itertuples(index=False):
        miss = "—" if r[4] is None or (isinstance(r[4], float) and np.isnan(r[4])) else \
            ("<%0,01" if 0 < r[4] < 0.005 else f"%{r[4]:.2f}".replace(".", ","))
        lines.append(f"| `{r[0]}` | {r[1]} | {r[2]} | {r[3]} | {miss} | {r[5]} | {r[6]} | {r[7]} | {r[8]} | {r[9]} |")
    lines += ["", "## Model öznitelik matrisleri", "",
              "| Dosya | Model | Düzey | Anahtar | Öznitelikler | Ağırlık | Satır | Metrik |",
              "|---|---|---|---|---|---|---:|---|"]
    for name, f in s["feature_sets"].items():
        lines.append(f"| `{name}.parquet` | {f['model']} | {f['level']} | `{f['key']}` | {', '.join(f['features'])} | "
                     f"{f.get('weight') or '—'} | {_n(f['rows'])} | {f['metric']} |")
    lines.append("")
    return "\n".join(lines)


def render_markdown(s: dict, mapping: pd.DataFrame) -> str:
    L: list[str] = []
    w = L.append
    rows = s["rows"]["raw"]
    b = s["boroughs"]
    c = s["coordinates"]
    t = s["temporal"]
    v = s["vehicles"]
    r = s["repetition"]
    w("# Faz 2 — Otomatik Ön İşleme Raporu")
    w("")
    w("> `saferoute preprocess` ile üretilmiştir; tüm sayılar gerçek veriden ölçülmüştür.")
    w("")
    w("## 1. Soy (lineage) ve katmanlar")
    w("")
    lin = s["lineage"]
    w("| Alan | Değer |")
    w("|---|---|")
    w(f"| Ham anlık görüntü | `{lin['raw_snapshot']}` |")
    w(f"| Ham birleşik SHA-256 | `{lin['raw_combined_sha256']}` |")
    w(f"| İlçe sınırları | `{lin['boundaries_snapshot']}`, sürüm {s['boundaries']['source_version']}, "
      f"SHA-256 `{lin['boundaries_sha256']}` |")
    w(f"| Yapılandırma SHA-256 | `{lin['config_sha256']}` (hat sürümü {lin['pipeline_version']}) |")
    w(f"| Ham veri değişmedi mi | {'Evet (işlem öncesi/sonrası SHA-256 aynı)' if s['raw_unchanged'] else '**HAYIR**'} |")
    w("")
    w("| Katman | Satır | Sütun |")
    w("|---|---:|---:|")
    w(f"| raw | {_n(rows)} | 29 |")
    w(f"| interim | {_n(s['files']['interim']['rows'])} | {s['files']['interim']['column_count']} |")
    w(f"| processed | {_n(s['files']['processed']['rows'])} | {s['files']['processed']['column_count']} |")
    for name, f in s["feature_sets"].items():
        w(f"| features/{name} | {_n(f['rows'])} | {len(f['features'])} öznitelik |")
    w("")
    w("## 2. Faz 1 sayılarının doğrulanması")
    w("")
    w("| Ölçüt | Faz 1 | Faz 2 (yeniden hesap) | Eşleşme |")
    w("|---|---:|---:|:---:|")
    for k, x in s["phase1_crosscheck"].items():
        w(f"| {k} | {_n(x['phase1'])} | {_n(x['phase2'])} | {'✓' if x['match'] else '✗'} |")
    w("")
    w("## 3. Resmî ilçe sınırları")
    w("")
    val = s["boundaries"]["validation"]
    w(f"- Kaynak `gthc-hcne` (DCP), sürüm **{s['boundaries']['source_version']}**, yayın {s['boundaries']['publication_date']}, "
      f"son satır güncellemesi {s['boundaries']['rows_updated_at']}")
    w(f"- {val['borough_count']} ilçe, geometri türleri {val['geometry_types']}, {val['polygon_parts']} poligon parçası, "
      f"tümü geçerli: {val['all_valid']}; beyan edilen CRS `{s['boundaries']['declared_crs']}` → `{val['crs']}`")
    w(f"- Alan (km², EPSG:32618): " + ", ".join(f"{BOROUGH_TR[k]} {_n(x)}" for k, x in val["area_km2_epsg32618"].items()))
    w(f"- İlçeler arası en büyük örtüşme: {val['max_pairwise_overlap_m2']:.2e} m² (kayan nokta düzeyi)")
    w("")
    w("## 4. Koordinat kalitesi")
    w("")
    w("| Durum | Kayıt | Oran |")
    w("|---|---:|---:|")
    for k, x in c["status_counts"].items():
        w(f"| {STATUS_TR[k]} (`{k}`) | {_n(x)} | {_p(x, rows)} |")
    w("")
    w(f"- Geçerli coğrafi kayıt: **{_n(s['rows']['is_valid_geographic_record'])}**; "
      f"mekânsal kümelemeye uygun: **{_n(s['rows']['eligible_for_spatial_clustering'])}**")
    pc = c["predicate_comparison_unique_points"]
    w(f"- Yüklem karşılaştırması ({_n(c['unique_candidate_points'])} benzersiz nokta): intersects/covered_by "
      f"{_n(pc['intersects_or_covered_by_any'])}, contains (yalnız iç) {_n(pc['contains_strict_interior_any'])}, "
      f"sınır çizgisi üstünde {_n(pc['on_boundary_line'])}, birden çok ilçede {_n(pc['multiple_boroughs'])}")
    d = c["distance_outside_nyc_m"]
    w(f"- Poligon dışı noktaların NYC karasına uzaklığı: medyan {_n(round(d['p50'], 1))} m, %95 {_n(round(d['p95'], 1))} m, "
      f"%99 {_n(round(d['p99'], 1))} m, maks. {_n(round(d['max'] or 0, 0))} m")
    w("  - Kümülatif: " + ", ".join(f"≤{k} m: {_n(x)}" for k, x in d["cumulative_within_m"].items()))
    o = c["overlapping_reasons"]
    w(f"- Çakışan nedenler: geçersiz koordinat ∧ ilçe eksik {_n(o['coordinate_invalid_and_borough_missing'])}; "
      f"geçersiz koordinat ∧ 00:00 {_n(o['coordinate_invalid_and_midnight_suspect'])}; "
      f"geçersiz koordinat ∧ yaralı bayrağı ≠ ok {_n(o['coordinate_invalid_and_injury_flagged'])}")
    pj = c["projection_check"]
    w(f"- Projeksiyon {pj['crs']} ({pj['crs_name']}): tüm noktalar kullanım alanında: {pj['all_inside_area_of_use']}; "
      f"gidiş-dönüş hatası maks. {pj['roundtrip_error_m_max']:.2e} m. Referans: {pj['reference']} "
      f"({_n(pj['pair_sample'])} rastgele çift, tohum {pj['seed']}):")
    w(f"  - UTM Öklid mesafesinin göreli hatası: medyan {pj['projection_rel_error_median']:.5f}, "
      f"maks. {pj['projection_rel_error_max']:.5f} (işaretli ortalama {pj['projection_rel_error_mean_signed']:+.5f})")
    w(f"  - Küresel Haversine'in göreli hatası (küre yaklaşımı): medyan {pj['haversine_rel_error_median']:.5f}, "
      f"maks. {pj['haversine_rel_error_max']:.5f}")
    w("")
    w("![Koordinat durumu](figures/coordinate_quality_status.png)")
    w("")
    w("## 5. İlçe çıkarımı")
    w("")
    w(f"- Bildirilen ilçe eksik: {_n(b['original_missing'])}")
    w(f"- **Poligonla kurtarılan: {_n(b['recovered_by_polygon'])}**")
    w(f"- **Hâlâ ilçesiz: {_n(b['still_missing'])}** — nedenler: "
      + ", ".join(f"{INFERENCE_TR.get(k, k)} {_n(x)}" for k, x in b["still_missing_by_reason"].items()))
    w(f"- Poligon dışında kalan (ilçe atanmayan) kayıt: {_n(b['outside_polygons'])}")
    w(f"- **İlçe uyuşmazlığı: {_n(b['conflicts'])}** (bildirilen ve çıkarılan ilçesi olan "
      f"{_n(b['comparable_original_and_inferred'])} kaydın {_pv(b['conflict_pct_of_comparable'])}'i)")
    w("")
    w("| Nihai ilçe | Kayıt |")
    w("|---|---:|")
    for k, x in b["final_counts"].items():
        w(f"| {BOROUGH_TR.get(k, k)} | {_n(x)} |")
    w("")
    w("![İlçe çıkarımı](figures/borough_inference.png)")
    w("")
    w("![Uyuşmazlıklar](figures/borough_conflicts.png)")
    w("")
    ca = c.get("conflict_analysis", {})
    if ca.get("count"):
        dd = ca["distance_to_reported_borough_m"]
        w(f"Çelişkili noktaların **bildirilen** ilçe poligonuna uzaklığı: medyan {_n(round(dd['p50'], 1))} m, "
          f"%90 {_n(round(dd['p90'], 1))} m, %99 {_n(round(dd['p99'], 1))} m, maks. {_n(round(dd['max'], 0))} m. "
          + "Kümülatif: " + ", ".join(f"≤{k} m: {_n(x)}" for k, x in ca["within_m"].items()))
        w("")
        gf = c.get("geocode_fallback", {})
        if gf:
            w(f"**Yedek geokodlama şüphesi** ({gf['rule']}): {_n(gf['locations'])} konum, {_n(gf['records'])} kayıt; "
              "yıllara göre: " + ", ".join(f"{k}: {_n(x)}" for k, x in gf["records_by_year"].items())
              + ". Bu kayıtlar silinmedi, `geocode_fallback_suspect_flag` ile işaretlendi.")
            w("")
        w("En sık çelişki konumları:")
        w("")
        w("| Enlem | Boylam | Bildirilen | Poligon | Kayıt | Bildirilene uzaklık (m) | Cadde | Kesişen |")
        w("|---:|---:|---|---|---:|---:|---|---|")
        for x in ca["top_locations"][:12]:
            w(f"| {x['latitude']:.6f} | {x['longitude']:.6f} | {BOROUGH_TR.get(x['borough_original'], x['borough_original'])} | "
              f"{BOROUGH_TR.get(x['borough_inferred'], x['borough_inferred'])} | {_n(x['records'])} | "
              f"{_n(round(x['distance_m'], 1))} | {x['on_street'] or '—'} | {x['off_street'] or '—'} |")
        w("")
    w("## 6. Zaman öznitelikleri ve 00:00")
    w("")
    mh = t["minute_heaping"]
    w(f"- Şüpheli 00:00 kaydı: **{_n(t['midnight_suspect'])}** ({_pv(t['midnight_suspect_pct'])})")
    w(f"- Tam saat yığılma oranı (HH:00 / diğer dakikalar ort.): 00:00 için **{_n(mh['midnight_ratio'])}**, "
      f"diğer saatlerin medyanı {_n(mh['other_hours_ratio_median'])}, en yükseği {_n(mh['other_hours_ratio_max'])}")
    w("- Gün dilimleri: " + ", ".join(f"{PERIOD_TR.get(k, k)} {_n(x)}" for k, x in t["time_period_counts"].items()))
    w("")
    w("![Saat ve 00:00](figures/hour_and_midnight.png)")
    w("")
    w("## 7. Araç türü standardizasyonu")
    w("")
    w(f"- Ham farklı etiket: {_n(v['raw_distinct_labels'])} → normalize: {_n(v['normalized_distinct_labels'])} → "
      f"üst kategori: {v['category_count']}")
    w(f"- Eşleşmeyen (`unmatched` → Diğer) etiket: {_n(v['unmatched_labels'])}, etiket geçişi: {_n(v['unmatched_mentions'])} "
      f"({_pv(v['unmatched_mentions_pct'])})")
    w("")
    w("| Kategori | Etiket geçişi |")
    w("|---|---:|")
    for k, x in v["by_category"].items():
        w(f"| {CATEGORY_LABELS_TR[k]} (`{k}`) | {_n(x)} |")
    w("")
    w("| Kural | Etiket geçişi |")
    w("|---|---:|")
    for k, x in v["by_rule"].items():
        w(f"| `{k}` | {_n(x)} |")
    w("")
    w("En sık eşleşmeyen etiketler: " + ", ".join(f"`{k}` ({_n(x)})" for k, x in list(v["top_unmatched"].items())[:15]))
    w("")
    w("Tam eşleme tablosu: `reports/phase2/vehicle_type_mapping.csv`.")
    w("")
    w("![Araç kategorileri](figures/vehicle_categories_before_after.png)")
    w("")
    w("## 8. Yaralanma ve ölüm tutarlılığı")
    w("")
    w("| Bayrak | Yaralı | Ölü |")
    w("|---|---:|---:|")
    for k in FLAG_TR:
        w(f"| {FLAG_TR[k]} | {_n(s['casualties']['injury']['flag_counts'][k])} | "
          f"{_n(s['casualties']['fatality']['flag_counts'][k])} |")
    w(f"| **En az bir bildirim (has_reported_*)** | {_n(s['casualties']['injury']['has_reported'])} | "
      f"{_n(s['casualties']['fatality']['has_reported'])} |")
    w("")
    w("## 9. Tekrarlanan koordinatlar")
    w("")
    w(f"- Uygun kayıt {_n(r['eligible_records'])}, benzersiz konum **{_n(r['unique_locations'])}**, konum başına "
      f"ortalama {_n(r['records_per_location_mean'])}, medyan {_n(r['records_per_location_median'])}, "
      f"maks. {_n(r['records_per_location_max'])}")
    w(f"- Tekrarlı konum {_n(r['repeated_locations'])}; bu konumlardaki kaza {_n(r['records_at_repeated_locations'])} "
      f"({_pv(r['records_at_repeated_locations_pct'])})")
    w("")
    w("| Konum başına kaza | Konum | Kaza |")
    w("|---|---:|---:|")
    for k, x in r["distribution"].items():
        w(f"| {k} | {_n(x['locations'])} | {_n(x['records'])} |")
    w("")
    w("Tek başına DBSCAN çekirdeği olan konumlar (ağırlık ≥ min_samples, eps'ten bağımsız):")
    w("")
    w("| min_samples | Konum | Bu konumlardaki kaza |")
    w("|---:|---:|---:|")
    for k, x in r["self_core_locations_by_min_samples"].items():
        w(f"| {k} | {_n(x['locations'])} | {_n(x['records'])} |")
    w("")
    w("En çok tekrarlanan konumlar:")
    w("")
    w("| # | Enlem | Boylam | Kaza | İlçe | Cadde | Kesişen |")
    w("|---:|---:|---:|---:|---|---|---|")
    for i, x in enumerate(r["top_locations"][:15], 1):
        w(f"| {i} | {x['latitude']:.6f} | {x['longitude']:.6f} | {_n(x['weight'])} | "
          f"{BOROUGH_TR.get(x['borough'], x['borough'] or '—')} | {x['on_street_name'] or '—'} | {x['off_street_name'] or '—'} |")
    w("")
    w("![Tekrar](figures/coordinate_repetition.png)")
    w("")
    w("## 10. Öznitelik matrisleri")
    w("")
    w("| Dosya | Model | Düzey | Öznitelikler | Satır | Ağırlık toplamı | Sonlu |")
    w("|---|---|---|---|---:|---:|:---:|")
    for name, f in s["feature_sets"].items():
        w(f"| `{name}` | {f['model']} | {f['level']} | {', '.join(f['features'])} | {_n(f['rows'])} | "
          f"{_n(f['weight_sum'])} | {'✓' if f['all_finite'] else '✗'} |")
    w("")
    w("![Öznitelik matrisleri](figures/feature_sets.png)")
    w("")
    w("![Öncesi/sonrası](figures/missing_before_after.png)")
    w("")
    w("## 11. Çalışma süresi ve bellek")
    w("")
    w("| Adım | Süre (sn) | Bellek tepe (MB) |")
    w("|---|---:|---:|")
    for st in s["runtime"]["steps"]:
        w(f"| {st['step']} | {_n(float(st['seconds']))} | {_n(st['peak_memory_mb_so_far'])} |")
    w(f"| **Toplam** | {_n(float(s['runtime']['total_seconds']))} | {_n(s['runtime']['peak_memory_mb'])} |")
    w("")
    return "\n".join(L)


def load_outputs(snapshot_name: str) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    paths = output_paths(snapshot_name)
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    return summary, pd.read_parquet(paths["processed"]), pd.read_parquet(paths["mapping"])

