"""Faz 1–4 kayıtlarından okunan katalog: genel bakış, deney kaydı, model karşılaştırması, veri sözlüğü.

Hiçbir sayı burada üretilmez veya sabit yazılmaz; tümü doğrulanmış kayıt dosyalarından okunur.
Bir değer kaynakta yoksa ``None`` döner ve arayüz "mevcut değil" gösterir.
"""

from __future__ import annotations

import datetime as dt
import json
from functools import cached_property
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

from saferoute import config

# Seçim ve karşılaştırma yorumları: Faz 3 teknik raporundaki (docs/phase3/TEKNIK_RAPOR.md) sınırlılıklar.
COMPARISON_CAVEATS = [
    "HDBSCAN 100.000 olaylık sabit tohumlu örneklemde çalıştı; ana DBSCAN tam veride (2.020.638 olay, ağırlıklı "
    "benzersiz konum) uygulandı. Küme sayıları doğrudan karşılaştırılamaz.",
    "Siluet, Davies–Bouldin ve DBCV aynı 100.000 olaylık ortak değerlendirme kümesinde, gürültü hariç tabakalı "
    "örneklemle hesaplandı; tam veri metrikleri değildir.",
    "Siluet bir doğruluk ölçüsü değildir: denetimsiz kümelemede yer gerçeği (ground truth) yoktur. 0,945 değeri "
    "kompakt ve birbirinden uzak kavşak kümelerini yansıtır; %94,5 doğruluk anlamına gelmez.",
    "K-Means gürültü kavramına sahip değildir; her olayı bir kümeye atar. Gürültü oranı 'uygulanamaz' olarak "
    "gösterilir (0 değil).",
    "Algoritmalar tek bir başarı puanına indirgenmez; seçim kuralları sonuçlardan önce tanımlandı "
    "(en büyük küme ≤ %5, ≥ 20 küme).",
]

SCOPE_LABELS = {
    "full_weighted": "Tam veri (ağırlıklı benzersiz konum)",
    "sample": "Örneklem",
    "region": "Bölgesel alt küme",
    "year": "Tek yıl",
    "variant": "Veri kalitesi varyantı",
    "records": "Kayıt düzeyi",
}


def _read_json(p: Path) -> Any:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def scope_class(e: dict[str, Any]) -> str:
    scope = e.get("scope") or {}
    sub = scope.get("subset") or {}
    if sub.get("sample"):
        return "sample"
    if sub.get("region"):
        return "region"
    if sub.get("years"):
        return "year"
    if sub.get("exclude") or scope.get("weight_cap"):
        return "variant"
    if scope.get("kind") in ("dbscan_weighted", "kmeans_weighted"):
        return "full_weighted"
    return "records"


def scope_text(e: dict[str, Any]) -> str:
    scope = e.get("scope") or {}
    sub = scope.get("subset") or {}
    parts = [SCOPE_LABELS[scope_class(e)]]
    if s := sub.get("sample"):
        parts.append(f"n = {s['n']:,} olay, tohum {s['seed']}".replace(",", "."))
    if r := sub.get("region"):
        parts.append(f"enlem {r['min_lat']}–{r['max_lat']}, boylam {r['min_lon']}–{r['max_lon']}")
    if y := sub.get("years"):
        parts.append("yıl " + ", ".join(map(str, y)))
    if ex := sub.get("exclude"):
        parts.append("hariç: " + ", ".join(ex))
    if scope.get("weight_cap"):
        parts.append(f"ağırlık üst sınırı {scope['weight_cap']}")
    return " · ".join(parts)


class Phase3Catalog:
    """Faz 3 deney kaydı ve değerlendirme sonuçları (salt okunur)."""

    def __init__(self, phase3_dir: Path):
        self.dir = Path(phase3_dir)
        self.registry: list[dict[str, Any]] = _read_json(self.dir / "experiments.json")
        self.by_id = {e["experiment_id"]: e for e in self.registry}
        self.results: dict[str, Any] = _read_json(self.dir / "results.json")
        self.comparison_rows: list[dict[str, Any]] = _read_json(self.dir / "algorithm_comparison.json")["rows"]
        self.model_metadata: dict[str, Any] = _read_json(self.dir / "model_metadata.json")
        self.eval_by_id = {r["experiment_id"]: r for r in self.results.get("evaluation", {}).get("table", [])}
        sel = self.model_metadata.get("selected", {})
        self.selected_ids = {v["experiment_id"]: k for k, v in sel.items()}

    def labels_path(self, experiment_id: str) -> Path | None:
        e = self.by_id.get(experiment_id)
        if not e or not e.get("labels_path"):
            return None
        p = Path(e["labels_path"])
        if not p.is_absolute() or not p.exists():
            p = self.dir / "labels" / f"{experiment_id}.npz"
        return p if p.exists() else None

    def _metrics(self, eid: str) -> dict[str, Any] | None:
        r = self.eval_by_id.get(eid)
        if not r:
            return None

        def val(k: str) -> float | None:
            v = r.get(k)
            return v.get("value") if isinstance(v, dict) and v.get("status") == "ok" else None

        full = r.get("full") or {}
        ev = r.get("eval_set") or {}
        return {"silhouette": val("silhouette_common"), "silhouette_haversine": val("silhouette_native"),
                "davies_bouldin": val("davies_bouldin"), "dbcv": val("dbcv"),
                "parameter_stability_ari": r.get("parameter_stability_ari"), "admissible": r.get("admissible"),
                "rejection_reasons": r.get("rejection_reasons") or [],
                "n_clusters_full": full.get("n_clusters"), "noise_ratio_full": full.get("noise_ratio"),
                "largest_cluster_share_full": full.get("largest_cluster_share"),
                "cluster_size_full": full.get("cluster_size"),
                "n_clusters_eval": ev.get("n_clusters"), "noise_ratio_eval": ev.get("noise_ratio"),
                "largest_cluster_share_eval": ev.get("largest_cluster_share"),
                "fit_memory_mb": r.get("fit_memory_mb"), "fit_scope": r.get("fit_scope")}

    def summary_row(self, e: dict[str, Any]) -> dict[str, Any]:
        eid = e["experiment_id"]
        return {
            "experiment_id": eid, "stage": e.get("stage"), "algorithm": e.get("algorithm"), "params": e.get("params"),
            "feature_set": e.get("feature_set"), "scope_class": scope_class(e), "scope_text": scope_text(e),
            "status": e.get("status"), "error": e.get("error"), "n_events": e.get("n_events"),
            "n_unique_locations": e.get("n_unique_locations"), "runtime_s": e.get("runtime_s"),
            "peak_memory_mb": e.get("peak_memory_mb"), "seed": e.get("seed"),
            "dataset_version": e.get("dataset_version"), "processing_version": e.get("processing_version"),
            "software": e.get("software"), "created_at": e.get("created_at"),
            "selected_as": self.selected_ids.get(eid), "has_labels": self.labels_path(eid) is not None,
            "metrics": self._metrics(eid), "raw_metrics": e.get("metrics"),
        }

    def experiments(self) -> list[dict[str, Any]]:
        return [self.summary_row(e) for e in self.registry]

    def experiment(self, eid: str) -> dict[str, Any] | None:
        e = self.by_id.get(eid)
        return self.summary_row(e) if e else None

    def find(self, algorithm: str, params: dict[str, Any], scope_cls: str = "full_weighted") -> dict[str, Any] | None:
        """Tam veri kapsamında aynı algoritma + parametreli başarılı kayıtlı deney (ızgara deneyleri)."""
        for e in self.registry:
            if (e.get("algorithm") == algorithm and e.get("status") == "success" and scope_class(e) == scope_cls
                    and e.get("stage", "").endswith("grid") and e.get("params") == params):
                return e
        return None

    def comparison(self) -> dict[str, Any]:
        rows = []
        for r in self.comparison_rows:
            algo = r["algorithm"]
            is_kmeans = algo == "kmeans"
            reg = self.by_id.get(r["experiment_id"], {})
            sample_scope = r.get("n_clusters_full") is None
            rows.append({
                "algorithm": algo, "experiment_id": r["experiment_id"], "parameters": r.get("parameters"),
                "features": r.get("features"), "fit_scope": r.get("fit_scope"),
                "fit_n_events": reg.get("n_events"), "fit_n_points": reg.get("n_unique_locations"),
                "scope_class": scope_class(reg) if reg else None,
                "n_clusters": r.get("eval_set_n_clusters") if sample_scope else r.get("n_clusters_full"),
                "n_clusters_scope": "örneklem (100k olay)" if sample_scope else "tam veri",
                "noise_ratio": None if is_kmeans else (r.get("eval_set_noise_ratio") if sample_scope else r.get("noise_ratio_full")),
                "noise_applicable": not is_kmeans,
                "noise_scope": None if is_kmeans else ("örneklem (100k olay)" if sample_scope else "tam veri"),
                "largest_cluster_share": r.get("eval_set_largest_cluster_share") if sample_scope else r.get("largest_cluster_share_full"),
                "silhouette": (r.get("silhouette_common") or {}).get("value"),
                "silhouette_detail": r.get("silhouette_common"),
                "silhouette_haversine": (r.get("silhouette_native") or {}).get("value") if r.get("silhouette_native") else None,
                "davies_bouldin": (r.get("davies_bouldin") or {}).get("value"), "davies_bouldin_detail": r.get("davies_bouldin"),
                "dbcv": (r.get("dbcv") or {}).get("value"), "dbcv_detail": r.get("dbcv"),
                "parameter_stability_ari": r.get("parameter_stability_ari"),
                "runtime_s": r.get("runtime_s"), "peak_memory_mb": r.get("peak_memory_mb"), "fit_memory_mb": r.get("fit_memory_mb"),
                "admissible": r.get("admissible"), "rejection_reasons": r.get("rejection_reasons") or [],
                "primary": self.model_metadata.get("primary_model") == algo,
            })
        res = self.results
        grids = {a: [self.summary_row(self.by_id[i]) for i in res.get(f"{a}_grid_ids", []) if i in self.by_id]
                 for a in ("dbscan", "kmeans", "hdbscan")}
        return {
            "dataset_version": self.model_metadata.get("dataset_version"),
            "processing_version": self.model_metadata.get("processing_version"),
            "software": self.model_metadata.get("software"),
            "eval_set": res.get("evaluation", {}).get("eval_set"),
            "selection_criteria": res.get("selection", {}).get("criteria"),
            "kmeans_elbow_k": res.get("selection", {}).get("kmeans_elbow_k"),
            "rows": rows, "grids": grids, "selection_review": res.get("selection_review"),
            "sensitivity": res.get("sensitivity"), "final_choice": res.get("final_choice"),
            "temporal": {k: res.get("temporal", {}).get(k) for k in ("years", "refit_rule", "note", "persistence")},
            "caveats": COMPARISON_CAVEATS,
            "label_semantics": self.model_metadata.get("label_semantics"),
            "eps_conversion": self.model_metadata.get("eps_conversion"),
        }

    def load_event_labels(self, eid: str, n_events: int) -> tuple[np.ndarray, np.ndarray]:
        """Kayıtlı deneyin olay düzeyi etiketleri: (olay indeksleri, etiketler). Hizalama denetimli."""
        p = self.labels_path(eid)
        if p is None:
            raise FileNotFoundError(f"{eid}: etiket dosyası yok")
        z = np.load(p)
        idx, lab = z["event_index"].astype(np.int64), z["labels"].astype(np.int32)
        e = self.by_id[eid]
        if len(idx) != len(lab) or (e.get("n_events") is not None and len(idx) != e["n_events"]):
            raise ValueError(f"{eid}: etiket sayısı kayıttaki olay sayısıyla uyuşmuyor")
        if len(idx) and (idx.min() < 0 or idx.max() >= n_events):
            raise ValueError(f"{eid}: olay indeksi depo boyutunu aşıyor (veri sürümü farklı)")
        return idx, lab


# ----------------------------------------------------------------------------- genel bakış
def _latest(dirpath: Path, pattern: str) -> Path | None:
    files = sorted(Path(dirpath).glob(pattern))
    return files[-1] if files else None


def source_record(pdir: Path) -> dict[str, Any]:
    """Veri kaynağı, edinim ve güncellik kaydı (Faz 1 dosyalarından)."""
    snap = Path(pdir).name
    acq = config.METADATA_DIR / f"acquisition_{snap}.json"
    acquisition = _read_json(acq) if acq.exists() else None
    status_p = _latest(config.METADATA_DIR, "source_status_*.json")
    status = _read_json(status_p) if status_p else None
    fresh = (status or {}).get("freshness") or {}
    rows_updated = fresh.get("rows_updated_at") or (acquisition or {}).get("source_rows_updated_at")
    days_now = None
    if rows_updated:
        days_now = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(rows_updated)).days
    return {
        "dataset_id": config.DATASET_ID, "dataset_name": (status or {}).get("name"),
        "source_url": config.DATASET_PAGE_URL, "catalog_url": config.CATALOG_URL,
        "attribution": (status or {}).get("attribution"), "snapshot": snap, "acquisition": acquisition,
        "freshness": {"checked_at": (status or {}).get("checked_at"), "rows_updated_at": rows_updated,
                      "declared_update_frequency": fresh.get("declared_update_frequency"),
                      "days_since_rows_updated_at_check": fresh.get("days_since_rows_updated"),
                      "days_since_rows_updated_now": days_now,
                      "staleness_threshold_days": fresh.get("staleness_threshold_days"),
                      "verdict_at_check": fresh.get("verdict")},
    }


def overview(store: Any, catalog: Phase3Catalog, layer_manifest: dict[str, Any], prep: dict[str, Any],
             pdir: Path) -> dict[str, Any]:
    from saferoute.analytics.filters import FilterSpec

    src = source_record(pdir)
    s = store.summary(FilterSpec())
    counts = layer_manifest["counts"]
    model = layer_manifest["model"]
    rows = prep.get("rows", {})
    acq = src.get("acquisition") or {}
    years = s["by_year"]
    first, last = s["date_min"], s["date_max"]
    partial = []
    if first and not first.endswith("-01-01"):
        partial.append({"year": int(first[:4]), "reason": f"Veri {first} tarihinde başlıyor (yılın tamamı değil)"})
    if last and not last.endswith("-12-31"):
        partial.append({"year": int(last[:4]), "reason": f"Veri {last} tarihinde bitiyor (yılın tamamı değil)"})
    # Mevcut modelin en büyük kümeleri (Faz 4 küme özeti)
    return {
        "source": src,
        "records": {"raw_total": rows.get("raw") or acq.get("row_count"), "eligible": rows.get("eligible_for_spatial_clustering"),
                    "excluded": (rows.get("raw") or 0) - (rows.get("eligible_for_spatial_clustering") or 0),
                    "unique_locations": counts.get("locations_total"),
                    "exclusion_reasons": prep.get("coordinates", {}).get("exclusion_reason_counts")},
        "coverage": {"date_min": first, "date_max": last, "source_earliest": acq.get("earliest_crash_date"),
                     "source_latest": acq.get("latest_crash_date"), "partial_years": partial},
        "model": {"algorithm": model["algorithm"], "experiment_id": model["experiment_id"],
                  "parameters": model["parameters"], "clusters": counts["clusters"], "noise_ratio": counts["noise_ratio"],
                  "events_clustered": counts["events_clustered"], "events_noise": counts["events_noise"],
                  "dataset_version": layer_manifest.get("dataset_version"),
                  "processing_version": layer_manifest.get("processing_version"),
                  "software": catalog.model_metadata.get("software")},
        "by_year": years, "by_borough": s["by_borough"],
        "totals": {k: s[k] for k in ("injury_crashes", "fatal_crashes", "persons_injured", "persons_killed",
                                     "midnight_suspect")},
        "denominators": {"by_year": "kümelemeye uygun olaylar (geçerli NYC koordinatı + tarih)",
                         "by_borough": "kümelemeye uygun olaylar; ilçe = borough_final (bildirilen, yoksa poligondan çıkarılan)"},
    }


# ----------------------------------------------------------------------------- veri sözlüğü
# Faz 2 FeatureSpec listesinde ayrı satırı olmayan işlenmiş sütunlar (kaynak: preprocess/geo.py,
# standardize.py, vehicles.py, casualties.py incelemesi).
SUPPLEMENT: dict[str, dict[str, str]] = {
    "coord_parse_status": {"meaning": "Koordinat ayrıştırma durumu (missing / unparseable / non_finite / parsed)",
                           "transform": "Ham enlem/boylam metninden sayı ayrıştırma", "group": "Coğrafi doğrulama"},
    "on_boundary_line": {"meaning": "Nokta ilçe sınır çizgisi üzerinde mi", "transform": "Poligon kesişim/kapsama karşılaştırması",
                         "group": "Coğrafi doğrulama"},
    "distance_outside_nyc_m": {"meaning": "NYC sınırı dışındaki noktanın sınıra uzaklığı (m)",
                               "transform": "Resmî ilçe poligonlarına mesafe (UTM)", "group": "Coğrafi doğrulama"},
    "exclusion_reason": {"meaning": "Mekânsal analizden dışlanma nedeni (none = dahil)",
                         "transform": "Koordinat kalite durumundan türetilir", "group": "Coğrafi doğrulama"},
    "borough_inference_status": {"meaning": "Poligondan ilçe çıkarımının sonucu",
                                 "transform": "inferred / ambiguous_boundary / outside_polygons / no_valid_coordinate",
                                 "group": "İlçe çıkarımı"},
    "vehicle_count_reported": {"meaning": "Kayıtta doldurulmuş araç türü alanı sayısı (0–5)",
                               "transform": "vehicle_type_code* alanlarının dolu olanları sayılır", "group": "Araç"},
    "injury_component_sum": {"meaning": "Yaya + bisikletli + sürücü yaralı alanlarının toplamı",
                             "transform": "Alt alanların toplamı (tutarlılık denetimi için)", "group": "Yaralanma"},
    "fatality_component_sum": {"meaning": "Yaya + bisikletli + sürücü ölü alanlarının toplamı",
                               "transform": "Alt alanların toplamı (tutarlılık denetimi için)", "group": "Yaralanma"},
}

RAW_RENAMES = {"borough": "borough_original"}


def _group_of(name: str) -> str:
    if name.startswith("contributing_factor"):
        return "Katkı faktörü"
    if name.startswith(("vehicle_type", "vehicle_category", "involves_", "vehicle_count")):
        return "Araç"
    if name.startswith(("number_of_", "has_reported", "injury_", "fatality_")):
        return "Yaralanma"
    if name.startswith(("crash_", "day_of_week", "is_weekend", "time_period", "hour_", "month_", "dow_",
                        "days_since", "midnight")):
        return "Tarih / saat"
    if name.startswith("borough") or name == "location_reported_borough_count":
        return "İlçe çıkarımı"
    if name in ("latitude", "longitude", "lat_rad", "lon_rad", "x_m", "y_m", "location_id", "location", "zip_code"):
        return "Konum"
    if name.endswith("street_name"):
        return "Konum"
    return "Coğrafi doğrulama"


def _spec_for(name: str, specs: dict[str, Any]) -> Any:
    if name in specs:
        return specs[name]
    if name.startswith("vehicle_category_"):
        return specs.get("vehicle_category_1..5")
    if name.startswith("involves_"):
        return specs.get("involves_<kategori>")
    return None


def parquet_null_counts(path: Path) -> tuple[int, dict[str, int | None], dict[str, str]]:
    """Satır grubu istatistiklerinden sütun başına eksik değer sayısı (istatistik yoksa None)."""
    pf = pq.ParquetFile(path)
    md = pf.metadata
    nulls: dict[str, int | None] = {}
    for j in range(md.num_columns):
        name = md.schema.column(j).path.split(".")[0]
        total: int | None = 0
        for i in range(md.num_row_groups):
            st = md.row_group(i).column(j).statistics
            if st is None or not st.has_null_count:
                total = None
                break
            total += st.null_count
        nulls[name] = total
    types = {f.name: str(f.type) for f in pf.schema_arrow}
    return md.num_rows, nulls, types


def data_dictionary(pdir: Path, prep: dict[str, Any]) -> dict[str, Any]:
    from saferoute.preprocess.features import FEATURE_SETS as FEATURE_SET_SPECS, FEATURE_SPECS

    pdir = Path(pdir)
    n_rows, nulls, types = parquet_null_counts(pdir / "crashes_processed.parquet")
    raw_missing = prep.get("standardize", {}).get("raw_missing_pct", {})
    raw_manifest = config.RAW_DIR / config.DATASET_ID / pdir.name / "manifest.json"
    if not raw_manifest.exists():
        raw_manifest = config.REPORTS_DIR / "phase1" / "source_manifest.json"
    rm = _read_json(raw_manifest) if raw_manifest.exists() else {}
    raw_rows = rm.get("row_count")

    def spec_dict(s: Any) -> dict[str, Any] | None:
        if s is None:
            return None
        return {"meaning": s.meaning, "origin": s.origin, "transform": s.transform, "models": s.models,
                "exclusion_reason": s.exclusion_reason, "filter_use": s.filter_use,
                "interpretation_use": s.interpretation_use}

    raw_cols = []
    for c in rm.get("columns", []):
        name = c["field_name"]
        pct = raw_missing.get(name)
        s = _spec_for(RAW_RENAMES.get(name, name), FEATURE_SPECS)
        raw_cols.append({"name": name, "source_name": c.get("name"), "source_type": c.get("data_type"),
                         "missing_pct": pct, "missing_count": round(pct / 100 * raw_rows) if pct is not None and raw_rows else None,
                         "processed_as": RAW_RENAMES.get(name, name) if RAW_RENAMES.get(name, name) in types else None,
                         "spec": spec_dict(s), "group": _group_of(name)})

    raw_names = {RAW_RENAMES.get(c["field_name"], c["field_name"]) for c in rm.get("columns", [])}
    model_sets: dict[str, list[str]] = {}
    for set_name, fs in FEATURE_SET_SPECS.items():
        for f in fs.get("features", []):
            model_sets.setdefault(f, []).append(set_name)
    processed = []
    for name, typ in types.items():
        s = _spec_for(name, FEATURE_SPECS)
        sup = SUPPLEMENT.get(name)
        info = spec_dict(s)
        if info is None and sup:
            info = {"meaning": sup["meaning"], "origin": "engineered", "transform": sup["transform"], "models": "—",
                    "exclusion_reason": "Kalite/denetim alanı; modele girmez", "filter_use": "Hayır",
                    "interpretation_use": "Veri kalitesi raporu", "source": "Faz 5: Faz 2 kaynak kodundan açıklama"}
        processed.append({"name": name, "dtype": typ, "missing_count": nulls.get(name), "rows": n_rows,
                          "origin": "raw" if name in raw_names else "engineered",
                          "in_feature_sets": model_sets.get(name, []), "in_model": bool(model_sets.get(name)),
                          "group": (sup or {}).get("group") or _group_of(name), "spec": info})
    fs_summary = prep.get("feature_sets", {})
    feature_sets = []
    for set_name, fs in FEATURE_SET_SPECS.items():
        summ = fs_summary.get(set_name, {})
        feature_sets.append({"name": set_name, "model": fs.get("model"), "level": fs.get("level"),
                             "features": fs.get("features"), "metric": fs.get("metric"), "units": fs.get("units"),
                             "weight": fs.get("weight"), "note": fs.get("note"), "row_filter": fs.get("row_filter"),
                             "rows": summ.get("rows"), "weight_sum": summ.get("weight_sum")})
    return {
        "raw": {"rows": raw_rows, "columns": raw_cols, "column_count": len(raw_cols), "source": raw_manifest.name},
        "processed": {"rows": n_rows, "columns": processed, "column_count": len(processed),
                      "null_count_method": "Parquet satır grubu istatistikleri (null_count)"},
        "feature_sets": feature_sets,
        "cleaning": {
            "coordinates": prep.get("coordinates", {}).get("status_counts"),
            "exclusion_reasons": prep.get("coordinates", {}).get("exclusion_reason_counts"),
            "rows": prep.get("rows"),
            "boroughs": {k: prep.get("boroughs", {}).get(k) for k in (
                "original_counts", "final_counts", "inferred_counts", "source_counts", "inference_status_counts",
                "original_missing", "recovered_by_polygon", "still_missing", "conflicts", "conflict_pct_of_comparable",
                "comparable_original_and_inferred", "conflict_pairs")},
            "vehicles": {k: prep.get("vehicles", {}).get(k) for k in (
                "raw_distinct_labels", "normalized_distinct_labels", "category_count", "label_mentions",
                "by_category", "by_rule")},
            "temporal": {"midnight_suspect": prep.get("temporal", {}).get("midnight_suspect"),
                         "midnight_suspect_pct": prep.get("temporal", {}).get("midnight_suspect_pct"),
                         "minute_heaping": prep.get("temporal", {}).get("minute_heaping")},
            "casualties": prep.get("casualties"), "repetition": prep.get("repetition"),
            "lineage": prep.get("lineage"),
        },
    }
