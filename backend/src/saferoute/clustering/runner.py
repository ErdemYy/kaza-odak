"""Faz 3 deney orkestrasyonu.

Aşamalar (sırasıyla): bütünlük → k-mesafe → ağırlıklı/kayıt eşdeğerliği → DBSCAN ızgarası →
K-Means ızgarası → HDBSCAN ızgarası → değerlendirme → seçim → seçim incelemesi → zamansal
kararlılık → veri kalitesi duyarlılığı → küme profilleri → çıktılar.

Her deney ``registry`` içinde deterministik kimlikle kaydedilir; başarılı deney ve etiket
dosyası mevcutsa yeniden çalıştırılmaz (``force=True`` hariç). Tüm sonuçlar
``phase3/results.json`` dosyasına yazılır; rapor ve defter bu dosyadan "sunum modunda" okur.
"""

from __future__ import annotations

import gc
import json
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from saferoute import config
from saferoute.clustering import evaluation as ev_
from saferoute.clustering.data import EventData, load_events, processed_dir, subset_mask, verify_integrity
from saferoute.clustering.profiling import cluster_profiles, load_profile_columns
from saferoute.clustering.registry import ExperimentRecord, Registry, experiment_id, software_versions
from saferoute.clustering.settings import CLUSTERING_CODE_VERSION, load_config
from saferoute.clustering.worker import run_isolated
from saferoute.perf import available_memory_mb, peak_memory_mb
from saferoute.preprocess.coordinates import EARTH_RADIUS_M, meters_to_radians

STAGES = ("integrity", "kdistance", "equivalence", "dbscan", "kmeans", "hdbscan", "evaluate", "select",
          "review", "temporal", "sensitivity", "profiles")
# Her aşamanın results içindeki anahtarları (kontrol noktası için)
STAGE_KEYS = {"integrity": ["integrity"], "kdistance": ["kdistance"], "equivalence": ["equivalence"],
              "dbscan": ["dbscan_grid_ids"], "kmeans": ["kmeans_grid_ids"], "hdbscan": ["hdbscan_grid_ids"],
              "evaluate": ["evaluation"], "select": ["selection"], "review": ["selection_review"],
              "temporal": ["temporal"], "sensitivity": ["sensitivity"], "profiles": ["profiles"]}

KIND_FEATURE = {"dbscan_weighted": "A_dbscan_haversine_weighted", "dbscan_records": "A_dbscan_haversine",
                "kmeans_weighted": "B_kmeans_projected_weighted", "hdbscan_events": "B_kmeans_projected"}


class Phase3Runner:
    def __init__(self, cfg: dict[str, Any] | None = None, pdir: Path | None = None, out_dir: Path | None = None,
                 force: bool = False, log: Callable[[str], None] = print):
        self.cfg = cfg or load_config()
        self.pdir = Path(pdir or processed_dir())
        self.out = Path(out_dir or self.pdir / "phase3")
        self.labels_dir = self.out / "labels"
        self.registry = Registry(self.out / "experiments_registry.json")
        self.force = force
        self.log = log
        self.seed = int(self.cfg["meta"]["random_seed"])
        self.isolate = bool(self.cfg["resources"].get("isolate_experiments", True))
        self.results: dict[str, Any] = {}
        self.ev: EventData | None = None
        self.software = software_versions()
        self._full_cache: dict[str, np.ndarray] = {}
        self._profiles: dict[str, Any] = {}
        self.checkpoint_path = self.out / "results_checkpoint.json"
        import sklearn

        # Siluet gibi parçalı ikili uzaklık hesaplarının bellek tavanı
        sklearn.set_config(working_memory=int(self.cfg["resources"].get("sklearn_working_memory_mb", 256)))

    # ------------------------------------------------------------------ yardımcılar
    @property
    def dataset_version(self) -> str:
        lin = self.ev.meta["lineage"]
        return f"raw:{lin['raw_combined_sha256'][:12]}|p2cfg:{lin['config_sha256'][:12]}|p2:{lin['pipeline_version']}"

    @property
    def processing_version(self) -> str:
        return f"phase3-code:{CLUSTERING_CODE_VERSION}|phase3-config:{self.cfg['_sha256'][:12]}"

    def run(self, stage: str, kind: str, params: dict[str, Any], subset: dict[str, Any] | None = None,
            weight_cap: float | None = None) -> dict[str, Any]:
        algorithm = kind.split("_")[0]
        feature_set = KIND_FEATURE[kind]
        scope = {"kind": kind, "subset": subset or {}, "weight_cap": weight_cap}
        exp_id = experiment_id(algorithm, params, feature_set, scope, self.dataset_version)
        old = self.registry.get(exp_id)
        if old and not self.force and old["status"] == "success" and old.get("labels_path") \
                and Path(old["labels_path"]).exists():
            return old
        min_free = self.cfg["resources"].get("min_free_memory_mb")
        gc.collect()
        free = available_memory_mb()
        if min_free and free is not None and free < min_free:
            rec = ExperimentRecord(
                experiment_id=exp_id, stage=stage, algorithm=algorithm, params=params, feature_set=feature_set,
                scope=scope, dataset_version=self.dataset_version, processing_version=self.processing_version,
                status="skipped_resource_limit", seed=self.seed, software=self.software,
                error=f"Bellek kapısı: boş fiziksel bellek {free:.0f} MB < gereken {min_free} MB; deney başlatılmadı.")
            self.registry.add(rec)
            self.log(f"[{stage}] {exp_id} {params} -> skipped_resource_limit (boş bellek {free:.0f} MB)")
            return self.registry.get(exp_id)
        task = {"kind": kind, "params": params, "processed_dir": str(self.pdir), "subset": subset,
                "weight_cap": weight_cap, "max_neighbor_pairs": int(self.cfg["resources"]["max_neighbor_pairs"]),
                "labels_out": str(self.labels_dir / f"{exp_id}.npz"), "seed": self.seed,
                "n_init": self.cfg["kmeans"]["n_init"], "max_iter": self.cfg["kmeans"].get("max_iter", 300),
                "method": self.cfg["hdbscan"].get("cluster_selection_method", "eom")}
        t0 = time.perf_counter()
        res = run_isolated(task, self.isolate)
        status = res.get("status", "failed")
        rec = ExperimentRecord(
            experiment_id=exp_id, stage=stage, algorithm=algorithm, params=params, feature_set=feature_set,
            scope=scope, dataset_version=self.dataset_version, processing_version=self.processing_version,
            status=status, error=res.get("error") or (None if status == "success" else "bilinmeyen hata"),
            n_events=res.get("n_events"), n_unique_locations=res.get("n_unique_locations"),
            metrics=res.get("extra", {}), runtime_s=res.get("runtime_s"), peak_memory_mb=res.get("peak_memory_mb"),
            memory_before_fit_mb=res.get("memory_before_fit_mb"), seed=self.seed, labels_path=res.get("labels_path"),
            software=self.software,
            warnings=[f"toplam süre (süreç başlatma + veri yükleme dahil) {time.perf_counter() - t0:.1f} sn",
                      f"başlangıçta boş sistem belleği {free} MB",
                      f"çocuk süreç kapandı: {res.get('child_closed')}"],
        )
        self.registry.add(rec)
        msg = f"[{stage}] {exp_id} {params} -> {status}"
        if status == "success":
            msg += f" ({rec.runtime_s} sn, tepe {rec.peak_memory_mb} MB)"
        else:
            msg += f": {rec.error[:160]}"
        self.log(msg)
        return self.registry.get(exp_id)

    @staticmethod
    def load_labels(rec: dict[str, Any]) -> dict[str, np.ndarray]:
        with np.load(rec["labels_path"]) as z:
            return {k: z[k] for k in z.files}

    def _full(self, exp_id: str) -> np.ndarray:
        """Tam veri etiketleri (önbellekli, gerekirse diskten yüklenir)."""
        if exp_id not in self._full_cache:
            self._full_cache[exp_id] = self.full_labels(self.registry.get(exp_id))
        return self._full_cache[exp_id]

    def full_labels(self, rec: dict[str, Any], fill: int = -2) -> np.ndarray:
        """Etiketleri tüm olay uzunluğuna yayar (alt küme dışındaki olaylar ``fill``)."""
        z = self.load_labels(rec)
        out = np.full(self.ev.n_events, fill, dtype=np.int32)
        out[z["event_index"]] = z["labels"]
        return out

    # ------------------------------------------------------------------ aşamalar
    def stage_integrity(self) -> None:
        self.log("Bütünlük doğrulaması…")
        self.results["integrity"] = verify_integrity(self.pdir)
        self.ev = load_events(self.pdir)

    def stage_kdistance(self) -> None:
        """Ağırlıklı k-mesafe: örnek olayın k'ıncı en yakın OLAYA uzaklığı (kendisi dahil, DBSCAN tanımı)."""
        c = self.cfg["kdistance"]
        ev = self.ev
        rng = np.random.default_rng(self.seed)
        idx = rng.choice(ev.n_events, size=min(c["sample_events"], ev.n_events), replace=False)
        tree = BallTree(np.column_stack([ev.loc_lat_rad, ev.loc_lon_rad]), metric="haversine")
        q = np.column_stack([ev.lat_rad[idx], ev.lon_rad[idx]])
        dist, ind = tree.query(q, k=int(c["max_unique_neighbors"]))
        cum = np.cumsum(ev.loc_weight[ind], axis=1)
        out = {}
        for k in c["k_values"]:
            reached = cum[:, -1] >= k
            pos = np.argmax(cum >= k, axis=1)
            d = np.where(reached, dist[np.arange(len(idx)), pos] * EARTH_RADIUS_M, np.nan)
            valid = d[~np.isnan(d)]
            out[str(k)] = {
                "n_sample": int(len(idx)), "not_reached_within_neighbors": int((~reached).sum()),
                "zero_distance_share": float((valid == 0).mean()),
                "percentiles_m": {str(p): float(np.percentile(valid, p)) for p in (10, 25, 50, 75, 90, 95)},
                "sorted_curve_m": np.sort(valid)[:: max(1, len(valid) // 400)].round(2).tolist(),
            }
        self.results["kdistance"] = {"method": "ağırlıklı k-mesafe (k'ıncı en yakın olay, kendisi dahil)",
                                     "seed": self.seed, "by_k": out}

    def stage_equivalence(self) -> None:
        c = self.cfg["equivalence"]
        ev = self.ev
        rows = []
        scenarios = [(r["name"], r.get("label", r["name"]), {"region": {k: r[k] for k in
                      ("min_lat", "max_lat", "min_lon", "max_lon")}}, eps, ms)
                     for r in c["regions"] for eps in c["eps_m"] for ms in c["min_samples"]]
        for y in c.get("city_wide_years", []):
            scenarios.append((f"city_{y}", f"Tüm şehir, {y} yılı", {"years": [y]}, c["city_wide_eps_m"],
                              c["city_wide_min_samples"]))
        for name, label, subset, eps, ms in scenarios:
            params = {"eps_m": eps, "min_samples": ms}
            rec = self.run("equivalence", "dbscan_records", params, subset)
            wtd = self.run("equivalence", "dbscan_weighted", params, subset)
            row = {"scenario": name, "label": label, "eps_m": eps, "min_samples": ms,
                   "records_status": rec["status"], "weighted_status": wtd["status"],
                   "records_experiment": rec["experiment_id"], "weighted_experiment": wtd["experiment_id"],
                   "n_events": wtd.get("n_events"), "n_unique_locations": wtd.get("n_unique_locations"),
                   "records_runtime_s": rec.get("runtime_s"), "weighted_runtime_s": wtd.get("runtime_s"),
                   "records_peak_mb": rec.get("peak_memory_mb"), "weighted_peak_mb": wtd.get("peak_memory_mb"),
                   "records_fit_mem_mb": _delta(rec), "weighted_fit_mem_mb": _delta(wtd),
                   "records_neighbor_pairs": rec["metrics"].get("n_neighbor_pairs"),
                   "weighted_neighbor_pairs": wtd["metrics"].get("n_neighbor_pairs")}
            if rec["status"] == "success" and wtd["status"] == "success":
                a, b = self.load_labels(rec), self.load_labels(wtd)
                assert np.array_equal(a["event_index"], b["event_index"]), "olay sırası iki yöntemde aynı olmalı"
                X = np.column_stack([ev.lat_rad[a["event_index"]], ev.lon_rad[a["event_index"]]])
                row.update(ev_.compare_partitions(a["labels"], a["core"], b["labels"], b["core"], X,
                                                  meters_to_radians(eps)))
                # Kayda geri eşleme: her olayın etiketi kendi konumunun etiketiyle aynı olmalı
                loc_label = dict(zip(b["loc"].tolist(), b["loc_labels"].tolist()))
                row["backmap_consistent"] = bool(all(
                    loc_label[l] == lab for l, lab in zip(ev.location_index[b["event_index"]].tolist(),
                                                          b["labels"].tolist())))
                row["event_count_conserved"] = int(len(b["labels"])) == int(len(a["labels"]))
            rows.append(row)
        full = self.run("equivalence", "dbscan_records",
                        {"eps_m": c["full_records_eps_m"], "min_samples": c["full_records_min_samples"]}, None)
        self.results["equivalence"] = {"scenarios": rows, "full_data_records_attempt": {
            k: full.get(k) for k in ("experiment_id", "status", "error", "n_events")}}

    def stage_dbscan(self) -> None:
        c = self.cfg["dbscan"]
        recs = [self.run("dbscan_grid", "dbscan_weighted", {"eps_m": e, "min_samples": m})
                for e in c["eps_m"] for m in c["min_samples"]]
        self.results["dbscan_grid_ids"] = [r["experiment_id"] for r in recs]

    def stage_kmeans(self) -> None:
        recs = [self.run("kmeans_grid", "kmeans_weighted", {"k": k}) for k in self.cfg["kmeans"]["k"]]
        self.results["kmeans_grid_ids"] = [r["experiment_id"] for r in recs]

    def eval_subset(self) -> dict[str, Any]:
        return {"sample": {"n": int(self.cfg["hdbscan"]["sample_events"]), "seed": self.seed}}

    def stage_hdbscan(self) -> None:
        c = self.cfg["hdbscan"]
        recs = [self.run("hdbscan_grid", "hdbscan_events", {"min_cluster_size": mcs, "min_samples": ms},
                         self.eval_subset())
                for mcs in c["min_cluster_size"] for ms in c["min_samples"]]
        self.results["hdbscan_grid_ids"] = [r["experiment_id"] for r in recs]

    def stage_evaluate(self) -> None:
        """Tüm başarılı ızgara deneylerini ORTAK değerlendirme kümesinde (HDBSCAN örneklemi) ölçer."""
        ev = self.ev
        e_mask = subset_mask(ev, self.eval_subset())
        e_idx = np.flatnonzero(e_mask)
        X_proj = np.column_stack([ev.x_m[e_idx], ev.y_m[e_idx]])
        X_rad = np.column_stack([ev.lat_rad[e_idx], ev.lon_rad[e_idx]])
        ec = self.cfg["evaluation"]
        table = []
        all_ids = (self.results["dbscan_grid_ids"] + self.results["kmeans_grid_ids"]
                   + self.results["hdbscan_grid_ids"])
        full_cache: dict[str, np.ndarray] = {}
        for exp_id in all_ids:
            rec = self.registry.get(exp_id)
            row = {"experiment_id": exp_id, "algorithm": rec["algorithm"], "params": rec["params"],
                   "status": rec["status"], "runtime_s": rec.get("runtime_s"), "peak_memory_mb": rec.get("peak_memory_mb"),
                   "fit_memory_mb": _delta(rec), "fit_scope": "örneklem (100k olay)" if rec["algorithm"] == "hdbscan"
                   else "tam veri (ağırlıklı benzersiz konum)", "error": rec.get("error")}
            if rec["status"] != "success":
                table.append(row)
                continue
            lab_full = self.full_labels(rec)
            if rec["algorithm"] != "hdbscan":
                full_cache[exp_id] = lab_full
                row["full"] = ev_.cluster_stats(lab_full)
            lab_e = lab_full[e_idx]
            assert (lab_e >= -1).all(), "değerlendirme kümesindeki her olay etiketli olmalı"
            row["eval_set"] = ev_.cluster_stats(lab_e)
            row["silhouette_common"] = ev_.silhouette(X_proj, lab_e, "euclidean", ec["silhouette_sample"], self.seed)
            if rec["algorithm"] == "dbscan":
                row["silhouette_native"] = ev_.silhouette(X_rad, lab_e, "haversine", ec["silhouette_sample"], self.seed)
            row["davies_bouldin"] = ev_.davies_bouldin(X_proj, lab_e, ec["silhouette_sample"], self.seed)
            row["dbcv"] = ev_.dbcv(X_proj, lab_e, ec["dbcv_sample"], self.seed)
            if rec["algorithm"] == "kmeans":
                row["inertia"] = rec["metrics"].get("inertia")
            if rec["algorithm"] == "hdbscan":
                z = self.load_labels(rec)
                p = z["probabilities"][z["labels"] >= 0]
                row["membership_probability"] = {"median": float(np.median(p)) if len(p) else None,
                                                 "p10": float(np.percentile(p, 10)) if len(p) else None}
            table.append(row)
            self.log(f"[evaluate] {exp_id} {rec['params']} k={row['eval_set']['n_clusters']} "
                     f"noise={row['eval_set']['noise_ratio']:.3f} sil={row['silhouette_common'].get('value')}")
        # Parametre kararlılığı (DBSCAN): ızgara komşularıyla tam veride ARI
        c = self.cfg["dbscan"]
        grid = {(r["params"]["eps_m"], r["params"]["min_samples"]): r["experiment_id"] for r in table
                if r["algorithm"] == "dbscan" and r["status"] == "success"}
        eps_l, ms_l = c["eps_m"], c["min_samples"]
        pair_ari: dict[tuple[str, str], float] = {}
        for (e, m), exp_id in grid.items():
            i, j = eps_l.index(e), ms_l.index(m)
            neigh = [(eps_l[a], ms_l[b]) for a, b in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1))
                     if 0 <= a < len(eps_l) and 0 <= b < len(ms_l) and (eps_l[a], ms_l[b]) in grid]
            vals = []
            for n in neigh:
                key = tuple(sorted((exp_id, grid[n])))
                if key not in pair_ari:
                    pair_ari[key] = ev_.ari(full_cache[key[0]], full_cache[key[1]])
                vals.append(pair_ari[key])
            row = next(r for r in table if r["experiment_id"] == exp_id)
            row["parameter_stability_ari"] = float(np.mean(vals)) if vals else None
            row["neighbor_ari"] = {f"eps={n[0]},ms={n[1]}": pair_ari[tuple(sorted((exp_id, grid[n])))] for n in neigh}
        self.results["evaluation"] = {"eval_set": {"n_events": int(len(e_idx)), "seed": self.seed,
                                                   "definition": "basit rastgele olay örneklemi = HDBSCAN fit kümesi"},
                                      "table": table}
        self._full_cache.update(full_cache)

    def stage_select(self) -> None:
        s = self.cfg["selection"]
        table = self.results["evaluation"]["table"]

        def admissible(r: dict) -> tuple[bool, list[str]]:
            reasons = []
            if r["status"] != "success":
                return False, [f"durum: {r['status']}"]
            stats = r.get("full") or r["eval_set"]
            if stats["n_clusters"] < s["min_clusters"]:
                reasons.append(f"küme sayısı {stats['n_clusters']} < {s['min_clusters']}")
            if (stats["largest_cluster_share"] or 0) > s["max_largest_cluster_share"]:
                reasons.append(f"en büyük küme payı {stats['largest_cluster_share']:.3f} > {s['max_largest_cluster_share']}")
            return not reasons, reasons

        for r in table:
            ok, why = admissible(r)
            r["admissible"], r["rejection_reasons"] = ok, why
        sil = lambda r: r.get("silhouette_common", {}).get("value") or -1.0  # noqa: E731
        db = [r for r in table if r["algorithm"] == "dbscan" and r["admissible"]]
        db_sel = max(db, key=lambda r: ((r.get("parameter_stability_ari") or -1), sil(r))) if db else None
        km = [r for r in table if r["algorithm"] == "kmeans" and r["status"] == "success"]
        km_sel = max(km, key=sil) if km else None
        hd_all = [r for r in table if r["algorithm"] == "hdbscan" and r["status"] == "success"]
        hd_adm = [r for r in hd_all if r["admissible"]]
        dbcv_v = lambda r: r.get("dbcv", {}).get("value") if r.get("dbcv", {}).get("value") is not None else -2  # noqa: E731
        hd_sel = max(hd_adm or hd_all, key=dbcv_v) if hd_all else None
        # Dirsek (kneedle): normalize eğriye en uzak nokta
        elbow = None
        if len(km) >= 3:
            ks = np.array([r["params"]["k"] for r in km], dtype=float)
            inert = np.array([r["inertia"] for r in km], dtype=float)
            o = np.argsort(ks)
            kn, iv = (ks[o] - ks[o][0]) / (ks[o][-1] - ks[o][0]), (inert[o] - inert[o][-1]) / (inert[o][0] - inert[o][-1])
            elbow = int(ks[o][np.argmax(np.abs((1 - kn) - iv))])
        self.results["selection"] = {
            "criteria": s, "dbscan": db_sel and db_sel["experiment_id"], "kmeans": km_sel and km_sel["experiment_id"],
            "hdbscan": hd_sel and hd_sel["experiment_id"], "hdbscan_admissible_count": len(hd_adm),
            "kmeans_elbow_k": elbow,
            "dbscan_admissible": [r["experiment_id"] for r in db],
        }

    def stage_review(self) -> None:
        """Kabul edilebilir DBSCAN adaylarının yapı tanıları (kayıtlı etiketlerden; yeniden fit yok).

        Seçim kuralı sonuçlardan önce tanımlandığı için burada DEĞİŞTİRİLMEZ; tanılar seçilen
        konfigürasyonun küme büyüklüğü, coğrafi ölçek, zincirlenme ve yıllar arası süreklilik
        bakımından gerekçesini sınar ve alternatiflerin bedelini görünür kılar.
        """
        sel = self.results["selection"]
        ev = self.ev
        years = self.cfg["temporal"]["years"]
        rows = []
        for exp_id in sel.get("dbscan_admissible", []):
            r = self._row(exp_id)
            lab = self.full_labels(self.registry.get(exp_id))
            d = ev_.structure_diagnostics(lab, ev.x_m, ev.y_m, ev.location_index, ev.year, years)
            rows.append({"experiment_id": exp_id, "params": r["params"], "selected": exp_id == sel["dbscan"],
                         "noise_ratio_full": r["full"]["noise_ratio"],
                         "parameter_stability_ari": r.get("parameter_stability_ari"),
                         "silhouette_common": _metric_value(r.get("silhouette_common")),
                         "dbcv": _metric_value(r.get("dbcv")), **d})
            del lab
            self.log(f"[review] {exp_id} {r['params']} uzanım maks={d.get('extent_diag_m', {}).get('max')}")
        self.results["selection_review"] = {
            "definition": "Kabul edilebilir DBSCAN adaylarının yapı tanıları; seçim kuralı değiştirilmez.",
            "years": years, "rows": rows}

    def _row(self, exp_id: str) -> dict[str, Any]:
        return next(r for r in self.results["evaluation"]["table"] if r["experiment_id"] == exp_id)

    def _require_selection(self, stage: str) -> bool:
        if not self.results["selection"].get("dbscan"):
            self.results[stage] = {"status": "not_run", "reason": "kabul ölçütlerini sağlayan DBSCAN konfigürasyonu yok"}
            self.log(f"[{stage}] atlandı: seçilmiş DBSCAN yok")
            return False
        return True

    def stage_temporal(self) -> None:
        if not self._require_selection("temporal"):
            return
        tc = self.cfg["temporal"]
        ev = self.ev
        sel = self.results["selection"]
        db = self._row(sel["dbscan"])["params"]
        k = self._row(sel["kmeans"])["params"]["k"] if sel["kmeans"] else None
        n_total = ev.n_events
        years_out = []
        prev: dict[str, Any] = {"fp": None, "centers": None, "fp_scaled": None}
        for y in tc["years"]:
            n_y = int((ev.year == y).sum())
            ms_y = int(db["min_samples"])  # (a) aynı parametreler; ölçekleme yok (bkz. yapılandırma)
            d = self.run("temporal", "dbscan_weighted", {"eps_m": db["eps_m"], "min_samples": ms_y}, {"years": [y]})
            row = {"year": y, "n_events": n_y, "dbscan_min_samples": ms_y, "dbscan_experiment": d["experiment_id"],
                   "dbscan_status": d["status"]}
            cur: dict[str, Any] = {"fp": None, "centers": None, "fp_scaled": None}
            m = ev.year == y
            if d["status"] == "success":
                lab = self.full_labels(d)
                row.update({f"dbscan_{k_}": v for k_, v in ev_.cluster_stats(lab[m]).items()
                            if k_ in ("n_clusters", "noise_ratio", "largest_cluster_share")})
                fp = ev_.footprint(ev.x_m[m], ev.y_m[m], lab[m], tc["grid_cell_m"])
                row["footprint_cells"] = len(fp)
                cur["fp"] = fp
                if prev["fp"] is not None:
                    row["jaccard_vs_prev_year"] = ev_.jaccard(fp, prev["fp"])
                    clustered = lab[m] >= 0
                    cells = np.column_stack([np.floor(ev.x_m[m][clustered] / tc["grid_cell_m"]),
                                             np.floor(ev.y_m[m][clustered] / tc["grid_cell_m"])]).astype(np.int64)
                    in_prev = np.fromiter((tuple(cc) in prev["fp"] for cc in cells), dtype=bool, count=len(cells))
                    row["recurrence_share"] = float(in_prev.mean()) if len(in_prev) else None
            if tc.get("scaled_refit"):
                ms_s = max(int(tc.get("min_samples_floor", 3)), int(round(db["min_samples"] * n_y / n_total)))
                ds = self.run("temporal", "dbscan_weighted", {"eps_m": db["eps_m"], "min_samples": ms_s}, {"years": [y]})
                row.update({"scaled_min_samples": ms_s, "scaled_experiment": ds["experiment_id"],
                            "scaled_status": ds["status"]})
                if ds["status"] == "success":
                    lab_s = self.full_labels(ds)
                    st = ev_.cluster_stats(lab_s[m])
                    row.update({"scaled_n_clusters": st["n_clusters"], "scaled_noise_ratio": st["noise_ratio"],
                                "scaled_largest_cluster_share": st["largest_cluster_share"]})
                    fp_s = ev_.footprint(ev.x_m[m], ev.y_m[m], lab_s[m], tc["grid_cell_m"])
                    row["scaled_footprint_cells"] = len(fp_s)
                    cur["fp_scaled"] = fp_s
                    if prev.get("fp_scaled") is not None:
                        row["scaled_jaccard_vs_prev_year"] = ev_.jaccard(fp_s, prev["fp_scaled"])
            if k:
                km = self.run("temporal", "kmeans_weighted", {"k": k}, {"years": [y]})
                row["kmeans_experiment"], row["kmeans_status"] = km["experiment_id"], km["status"]
                if km["status"] == "success":
                    cur["centers"] = self.load_labels(km)["centers"]
                    if prev["centers"] is not None:
                        row["kmeans_centroid_shift"] = ev_.match_centroids(prev["centers"], cur["centers"])
            prev = cur
            years_out.append(row)
        # Seçilen tam veri kümesinin kapsamı ile her yıl
        full = self._full(sel["dbscan"])
        full_fp = ev_.footprint(ev.x_m, ev.y_m, full, tc["grid_cell_m"])
        for row in years_out:
            if row.get("dbscan_status") == "success":
                d = self.registry.get(row["dbscan_experiment"])
                lab = self.full_labels(d)
                m = ev.year == row["year"]
                fp = ev_.footprint(ev.x_m[m], ev.y_m[m], lab[m], tc["grid_cell_m"])
                row["share_of_year_footprint_in_full_model"] = len(fp & full_fp) / len(fp) if fp else None
        self.results["temporal"] = {"years": years_out, "grid_cell_m": tc["grid_cell_m"],
                                    "refit_rule": "(a) Seçilen parametreler her yıl aynen uygulanır (yıllık sıcak nokta); "
                                                  "(c) min_samples yıllık hacme ölçeklenir: max(taban, round(ms·N_yıl/N_toplam)).",
                                    "note": "Yıllık yeniden fit kümelerinin numaraları yıllar arasında eşleştirilmez; "
                                            "karşılaştırma mekânsal kapsama (ızgara hücreleri) üzerindendir.",
                                    "persistence": self._persistence(full, tc)}

    def _persistence(self, full: np.ndarray, tc: dict[str, Any]) -> dict[str, Any]:
        """(b) Tam veri modelinin kümeleri yıllar boyunca etkin mi? Aynı koşunun etiketleri (kimlikler geçerli)."""
        from scipy.stats import spearmanr

        years = tc["years"]
        m = (full >= 0) & np.isin(self.ev.year, years)
        ct = pd.crosstab(full[m], self.ev.year[m]).reindex(columns=years, fill_value=0)
        active = (ct > 0).sum(axis=1)
        top_n = int(tc.get("persistence_top_n", 50))
        consecutive = []
        for a, b in zip(years[:-1], years[1:]):
            if ct[a].nunique() > 1 and ct[b].nunique() > 1:
                rho = float(spearmanr(ct[a], ct[b]).statistic)
            else:
                rho = None  # sabit girdi: korelasyon tanımsız (N/A)
            ta, tb = set(ct[a].nlargest(top_n).index), set(ct[b].nlargest(top_n).index)
            consecutive.append({"years": f"{a}-{b}", "spearman_cluster_counts": rho,
                                f"top{top_n}_overlap": len(ta & tb) / top_n})
        return {"n_clusters": int(len(ct)), "years": years,
                "active_years_distribution": {str(k): int(v) for k, v in active.value_counts().sort_index().items()},
                "share_active_all_years": float((active == len(years)).mean()),
                "share_active_10plus_years": float((active >= 10).mean()),
                "events_in_clusters_active_all_years_share": float(ct[active == len(years)].to_numpy().sum()
                                                                   / ct.to_numpy().sum()),
                "consecutive": consecutive,
                "events_per_year_in_clusters": {str(y): int(ct[y].sum()) for y in years}}

    def stage_sensitivity(self) -> None:
        if not self._require_selection("sensitivity"):
            return
        sc = self.cfg["sensitivity"]
        ev = self.ev
        base_id = self.results["selection"]["dbscan"]
        base = self._full(base_id)
        params = self._row(base_id)["params"]
        out = []
        for v in sc["variants"]:
            subset, cap = None, None
            if v.startswith("exclude_"):
                subset = {"exclude": [v.removeprefix("exclude_")]}
            elif v == "cap_repeated_weights":
                cap = float(np.percentile(ev.loc_weight, sc["weight_cap_percentile"]))
            rec = self.run("sensitivity", "dbscan_weighted", params, subset, cap)
            row = {"variant": v, "experiment_id": rec["experiment_id"], "status": rec["status"],
                   "excluded_events": int(ev.n_events - (rec.get("n_events") or 0)), "weight_cap": cap}
            if rec["status"] == "success":
                lab = self.full_labels(rec)
                common = lab >= -1
                b, s = base[common], lab[common]
                row.update({"n_clusters": ev_.cluster_stats(s)["n_clusters"],
                            "noise_ratio": ev_.cluster_stats(s)["noise_ratio"],
                            "baseline_n_clusters_on_common": ev_.cluster_stats(b)["n_clusters"],
                            "baseline_noise_ratio_on_common": ev_.cluster_stats(b)["noise_ratio"],
                            "ari_vs_baseline_common_events": ev_.ari(b, s),
                            "noise_status_agreement": float(((b < 0) == (s < 0)).mean())})
                # Temel kümelerin korunumu: ortak olaylarının >= %50'si tek bir varyant kümesinde mi?
                df = pd.DataFrame({"b": b[b >= 0], "s": s[b >= 0]})
                size = df.groupby("b").size()
                best = (df[df["s"] >= 0].groupby(["b", "s"]).size().groupby(level="b").max()
                        .reindex(size.index, fill_value=0))
                retained = (best / size) >= 0.5
                row["baseline_clusters_retained_share"] = float(retained.mean())
                row["baseline_events_in_retained_clusters_share"] = float(size[retained].sum() / size.sum())
            out.append(row)
        self.results["sensitivity"] = {"baseline": base_id, "params": params, "variants": out}

    def stage_profiles(self) -> None:
        self._profiles = {}
        if not self._require_selection("profiles"):
            return
        sel = self.results["selection"]
        attrs = load_profile_columns(self.pdir / "crashes_processed.parquet")
        assert len(attrs) == self.ev.n_events, "profil sütunları olaylarla hizalı olmalı"
        pc = self.cfg["profiles"]
        prof: dict[str, Any] = {}
        for alg in ("dbscan", "kmeans"):
            exp_id = sel[alg]
            if not exp_id:
                continue
            lab = self._full(exp_id)
            summary, geo = cluster_profiles(lab, self.ev.x_m, self.ev.y_m, self.ev.location_index, attrs, exp_id,
                                            hull_buffer_m=pc["hull_buffer_m"])
            for frame in (summary,):
                frame.insert(1, "algorithm", alg)
                frame.insert(2, "dataset_version", self.dataset_version)
                frame.insert(3, "processing_version", self.processing_version)
                frame.insert(4, "parameters", json.dumps(self._row(exp_id)["params"]))
            prof[alg] = {"summary": summary, "geojson": geo}
            self.log(f"[profiles] {alg} {exp_id}: {len(summary)} küme")
        self._profiles = prof
        db = prof["dbscan"]["summary"]
        self.results["profiles"] = {
            "dbscan_top": db.head(25).drop(columns=["hour_histogram"]).to_dict(orient="records"),
            "dbscan_counts": {"clusters": int(len(db)), "events": int(db["n_events"].sum()),
                              "fatal_crashes": int(db["fatal_crashes"].sum()),
                              "injury_crashes": int(db["injury_crashes"].sum())},
            "dbscan_by_borough": db.groupby("dominant_borough")["n_events"].agg(["size", "sum"]).rename(
                columns={"size": "clusters", "sum": "events"}).reset_index().to_dict(orient="records"),
        }

    # ------------------------------------------------------------------ çıktılar
    def write_outputs(self) -> dict[str, str]:
        sel = self.results["selection"]
        out = self.out
        files: dict[str, str] = {}
        meta_common = {"dataset_version": self.dataset_version, "processing_version": self.processing_version,
                       "config_path": self.cfg["_path"], "config_sha256": self.cfg["_sha256"],
                       "software": self.software}
        # Olay düzeyi küme üyelikleri (büyük; git dışı)
        for alg in ("dbscan", "kmeans"):
            exp_id = sel[alg]
            if not exp_id or alg not in self._profiles:
                continue
            z = self.load_labels(self.registry.get(exp_id))
            pts = pd.DataFrame({"collision_id": self.ev.collision_id[z["event_index"]],
                                "location_id": self.ev.location_index[z["event_index"]],
                                "cluster_id": z["labels"]})
            if "core" in z:
                pts["is_core"] = z["core"]
            pts.insert(0, "experiment_id", exp_id)
            pts.insert(1, "algorithm", alg)
            path = out / f"cluster_points_{alg}.parquet"
            pts.to_parquet(path, index=False, compression="zstd")
            files[f"cluster_points_{alg}"] = str(path)
            s = self._profiles[alg]["summary"]
            path = out / f"cluster_summary_{alg}.parquet"
            s.to_parquet(path, index=False)
            files[f"cluster_summary_{alg}"] = str(path)
            path = out / f"cluster_geometries_{alg}.geojson"
            geo = dict(self._profiles[alg]["geojson"])
            geo["metadata"] = {"experiment_id": exp_id, "algorithm": alg, "parameters": self._row(exp_id)["params"],
                               **{k: v for k, v in meta_common.items() if k != "software"}}
            path.write_text(json.dumps(geo, ensure_ascii=False), encoding="utf-8")
            files[f"cluster_geometries_{alg}"] = str(path)
        (out / "experiments.json").write_text(json.dumps(self.registry.ordered(), indent=2, ensure_ascii=False,
                                                         default=str), encoding="utf-8")
        files["experiments"] = str(out / "experiments.json")
        comparison = self.comparison_table()
        (out / "algorithm_comparison.json").write_text(json.dumps({**meta_common, "rows": comparison}, indent=2,
                                                                  ensure_ascii=False, default=str), encoding="utf-8")
        files["algorithm_comparison"] = str(out / "algorithm_comparison.json")
        model_meta = {**meta_common, "selected": {alg: {"experiment_id": sel[alg],
                                                        "parameters": self._row(sel[alg])["params"] if sel[alg] else None}
                                                  for alg in ("dbscan", "kmeans", "hdbscan")},
                      "primary_model": self.results.get("final_choice", {}).get("primary_algorithm"),
                      "label_semantics": "-1 = gürültü; küme numaraları anlamsal sınıf değildir ve koşular arasında "
                                         "eşleştirilemez.",
                      "eps_conversion": "eps_rad = eps_m / 6371008.8 (haversine, [enlem, boylam] radyan)",
                      "geometry_semantics": (self._profiles["dbscan"]["geojson"]["geometry_semantics"]
                                     if "dbscan" in self._profiles else None)}
        (out / "model_metadata.json").write_text(json.dumps(model_meta, indent=2, ensure_ascii=False, default=str),
                                                 encoding="utf-8")
        files["model_metadata"] = str(out / "model_metadata.json")
        files["phase4_manifest"] = str(self._write_phase4_manifest(files, meta_common))
        return files

    def _write_phase4_manifest(self, files: dict[str, str], meta_common: dict[str, Any]) -> Path:
        """Faz 4'e devredilen dosyaların özet kaydı (SHA-256, boyut, satır/öğe sayısı)."""
        import hashlib

        import pyarrow.parquet as pq

        entries = {}
        for key, p in files.items():
            path = Path(p)
            h = hashlib.sha256()
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            n = pq.ParquetFile(path).metadata.num_rows if path.suffix == ".parquet" else (
                len(json.loads(path.read_text(encoding="utf-8")).get("features", []))
                if path.suffix == ".geojson" else None)
            entries[key] = {"path": path.relative_to(config.REPO_ROOT).as_posix()
                            if path.is_relative_to(config.REPO_ROOT) else path.as_posix(), "sha256": h.hexdigest(), "bytes": path.stat().st_size, "rows": n}
        path = self.out / "phase4_manifest.json"
        path.write_text(json.dumps({**{k: v for k, v in meta_common.items() if k != "software"},
                                    "selected": self.results["selection"], "files": entries},
                                   indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return path

    def comparison_table(self) -> list[dict[str, Any]]:
        sel = self.results["selection"]
        rows = []
        for alg in ("dbscan", "kmeans", "hdbscan"):
            if not sel.get(alg):
                continue
            r = self._row(sel[alg])
            rows.append({
                "algorithm": alg, "experiment_id": r["experiment_id"], "parameters": r["params"],
                "fit_scope": r["fit_scope"], "features": KIND_FEATURE[self.registry.get(r["experiment_id"])["scope"]["kind"]],
                "n_clusters_full": (r.get("full") or {}).get("n_clusters"),
                "noise_ratio_full": (r.get("full") or {}).get("noise_ratio"),
                "largest_cluster_share_full": (r.get("full") or {}).get("largest_cluster_share"),
                "eval_set_n_clusters": r["eval_set"]["n_clusters"], "eval_set_noise_ratio": r["eval_set"]["noise_ratio"],
                "eval_set_largest_cluster_share": r["eval_set"]["largest_cluster_share"],
                "silhouette_common": r["silhouette_common"], "silhouette_native": r.get("silhouette_native"),
                "davies_bouldin": r["davies_bouldin"], "dbcv": r["dbcv"],
                "parameter_stability_ari": r.get("parameter_stability_ari"),
                "runtime_s": r["runtime_s"], "peak_memory_mb": r["peak_memory_mb"], "fit_memory_mb": r["fit_memory_mb"],
                "admissible": r.get("admissible"), "rejection_reasons": r.get("rejection_reasons"),
            })
        return rows

    # ------------------------------------------------------------------ hepsi
    def _load_checkpoint(self) -> dict[str, Any]:
        if not self.checkpoint_path.exists():
            return {"done": [], "results": {}}
        ck = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        if ck.get("config_sha256") != self.cfg["_sha256"] or ck.get("dataset_version") != self.dataset_version:
            self.log("Kontrol noktası farklı yapılandırma/veri sürümüne ait; yok sayıldı.")
            return {"done": [], "results": {}}
        return ck

    def _save_checkpoint(self, done: list[str]) -> None:
        payload = {"config_sha256": self.cfg["_sha256"], "dataset_version": self.dataset_version, "done": done,
                   "results": {k: v for k, v in self.results.items() if k not in ("files", "meta", "final_choice")}}
        tmp = self.checkpoint_path.with_name(self.checkpoint_path.name + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(self.checkpoint_path)

    def run_all(self, stages: list[str] | None = None) -> dict[str, Any]:
        """Aşamaları çalıştırır.

        ``stages`` verilirse yalnızca bu aşamalar hesaplanır; önceki aşamaların sonuçları kontrol
        noktasından (aynı yapılandırma + veri sürümü) okunur. Böylece uzun iş, bellek ve süre
        açısından güvenli parçalara bölünebilir. ``profiles`` hesaplandığında çıktılar da yazılır.
        """
        t0 = time.perf_counter()
        self.out.mkdir(parents=True, exist_ok=True)
        unknown = set(stages or []) - set(STAGES)
        if unknown:
            raise ValueError(f"Bilinmeyen aşama(lar): {sorted(unknown)}")
        fns = {"integrity": self.stage_integrity, "kdistance": self.stage_kdistance,
               "equivalence": self.stage_equivalence, "dbscan": self.stage_dbscan, "kmeans": self.stage_kmeans,
               "hdbscan": self.stage_hdbscan, "evaluate": self.stage_evaluate, "select": self.stage_select,
               "review": self.stage_review, "temporal": self.stage_temporal, "sensitivity": self.stage_sensitivity, "profiles": self.stage_profiles}
        self.stage_integrity()  # her zaman: ucuz, olay verisini yükler ve hizalamayı doğrular
        ck = self._load_checkpoint() if stages is not None else {"done": [], "results": {}}
        done = ["integrity"]
        computed = []
        last = max(STAGES.index(s) for s in stages) if stages else len(STAGES) - 1
        for name in STAGES[1:last + 1]:
            if stages is None or name in stages:
                ts = time.perf_counter()
                self.log(f"=== {name} ===")
                fns[name]()
                self.results.setdefault("stage_seconds", {})[name] = round(time.perf_counter() - ts, 1)
                computed.append(name)
            elif name in ck["done"]:
                for k in STAGE_KEYS[name]:
                    self.results[k] = ck["results"][k]
                self.results.setdefault("stage_seconds", {})[name] = \
                    ck["results"].get("stage_seconds", {}).get(name)
            else:
                raise RuntimeError(f"'{name}' aşaması kontrol noktasında yok; önce o aşamayı çalıştırın.")
            done.append(name)
            self._save_checkpoint(done)
            gc.collect()
        self.results["stages_computed_this_run"] = computed
        if "profiles" in computed:
            self.results["final_choice"] = final_choice(self.results, self.registry)
            self.results["files"] = self.write_outputs()
        self.results["meta"] = {"dataset_version": self.dataset_version, "processing_version": self.processing_version,
                                "config_sha256": self.cfg["_sha256"], "software": self.software,
                                "total_seconds_this_run": round(time.perf_counter() - t0, 1),
                                "orchestrator_peak_memory_mb": peak_memory_mb(),
                                "available_memory_mb_end": available_memory_mb(),
                                "n_experiments": len(self.registry.records),
                                "status_counts": pd.Series([r["status"] for r in self.registry.ordered()])
                                .value_counts().to_dict()}
        if "profiles" in computed:
            (self.out / "results.json").write_text(json.dumps(self.results, indent=2, ensure_ascii=False,
                                                              default=str), encoding="utf-8")
        return self.results


def _metric_value(m: dict[str, Any] | None) -> float | None:
    return None if not m else m.get("value")


def _delta(rec: dict[str, Any]) -> float | None:
    if rec.get("peak_memory_mb") is None or rec.get("memory_before_fit_mb") is None:
        return None
    return round(rec["peak_memory_mb"] - rec["memory_before_fit_mb"], 1)


def final_choice(results: dict[str, Any], registry: Registry) -> dict[str, Any]:
    """Ana model kararı: önceden tanımlı ölçütlerin ölçülen değerlerle karşılaştırılması (kural tabanlı, şeffaf)."""
    sel = results["selection"]
    table = {r["experiment_id"]: r for r in results["evaluation"]["table"]}
    rows = {alg: table[sel[alg]] for alg in ("dbscan", "kmeans", "hdbscan") if sel.get(alg)}
    criteria = {}
    for alg, r in rows.items():
        criteria[alg] = {
            "separates_noise": alg != "kmeans",
            "full_data_fit": r["fit_scope"].startswith("tam veri"),
            "admissible": r.get("admissible"),
            "silhouette_common": r["silhouette_common"].get("value"),
            "dbcv": r["dbcv"].get("value"),
            "runtime_s": r["runtime_s"],
            "peak_memory_mb": r["peak_memory_mb"],
        }
    temporal = results.get("temporal", {}).get("years", [])
    jac = [y["jaccard_vs_prev_year"] for y in temporal if y.get("jaccard_vs_prev_year") is not None]
    jac_s = [y["scaled_jaccard_vs_prev_year"] for y in temporal if y.get("scaled_jaccard_vs_prev_year") is not None]
    primary = "dbscan" if rows.get("dbscan") and rows["dbscan"].get("admissible") else None
    return {"primary_algorithm": primary, "criteria_by_algorithm": criteria,
            "dbscan_temporal_jaccard_median": float(np.median(jac)) if jac else None,
            "dbscan_temporal_scaled_jaccard_median": float(np.median(jac_s)) if jac_s else None,
            "rule": ("Ana model: tam veride uygulanabilen, gürültüyü ayırabilen ve kabul ölçütlerini sağlayan "
                     "yoğunluk tabanlı model. Ölçütü sağlamazsa ana model seçilmez (None) ve rapor bunu belirtir.")}
