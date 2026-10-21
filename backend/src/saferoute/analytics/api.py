"""Faz 5 API rotaları (Faz 4 ``create_app`` uygulamasına eklenir).

Ayrım ilkesi (arayüzde de aynı):
* ``/api/records/*`` — FİLTRELENMİŞ GERÇEK kayıtlar; küme etiketleri seçili modelin tam veri
  etiketleridir. Yeniden kümeleme YAPILMAZ.
* ``/api/lab/jobs`` — filtrelenmiş/örneklenmiş kapsam üzerinde YENİ kümeleme işi (ayrı süreç).
* ``/api/results/{kimlik}/*`` — kayıtlı Faz 3 deneyinin veya tamamlanmış laboratuvar işinin sonuçları.
  Bu uç noktalarda YALNIZCA zaman dilimi süzgeci (tarih, yıl, ay, gün, saat) kabul edilir: küme üyeliği sabit
  kalır, olaylar gerçek tarih/saatlerine göre süzülür. Kayıt filtreleri (ilçe, araç …) sonuçla karıştırılmaz.

Kimlikler: kayıtlı deney (ör. ``dbscan-52abd2c018``), laboratuvar işi sonucu ``lab-<iş kimliği>``, dinamik deney
``dyn-<önbellek anahtarı>``. Biçime uymayan kimlikler dosya sistemine dokunulmadan 404 ile reddedilir.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Literal

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response

from saferoute.analytics import ANALYTICS_VERSION
from saferoute.analytics.catalog import Phase3Catalog, data_dictionary, overview, scope_text, source_record
from saferoute.analytics.events import EventStore
from saferoute.analytics.filters import FilterError, FilterSpec, parse_filters
from saferoute.analytics.jobs import EmptyScope, JobManager, NotRetryable, QueueFull
from saferoute.analytics.lab_spec import FEATURE_SETS, LabRequestError, capabilities, validate_request
from saferoute.analytics.reporting import ReportDocument, render
from saferoute.analytics.results import LabelResult

FILTER_KEYS = ("boroughs", "date_from", "date_to", "years", "months", "dows", "hour_from", "hour_to", "vehicles",
               "factor", "injury", "fatal", "exclude_midnight")
TIME_KEYS = ("date_from", "date_to", "years", "months", "dows", "hour_from", "hour_to")
JOB_ID_RE = re.compile(r"^[0-9a-f]{12}$")
RESULT_ID_RE = re.compile(r"^(lab-[0-9a-f]{12}|dyn-[0-9a-f]{16}|[a-z][a-z0-9]{1,20}-[A-Za-z0-9]{1,40})$")


class Analytics:
    """Faz 5 durumunu tutar; olay deposu arka planda yüklenir (sunucu açılışı bekletilmez)."""

    def __init__(self, layer_store: Any, layers_dir: Path, lab_root: Path | None = None,
                 store_factory: Any = None, catalog: Phase3Catalog | None = None, budget: dict[str, Any] | None = None):
        self.layer_store = layer_store
        self.layers_dir = Path(layers_dir)
        self.pdir = self.layers_dir.parent
        self.store: EventStore | None = None
        self.jobs: JobManager | None = None
        self.error: str | None = None
        self.load_seconds: float | None = None
        self.ready = threading.Event()
        p3 = self.pdir / "phase3"
        self.catalog = catalog if catalog is not None else (Phase3Catalog(p3) if (p3 / "experiments.json").exists() else None)
        prep_p = self.pdir / "preprocessing_summary.json"
        self.prep = json.loads(prep_p.read_text(encoding="utf-8")) if prep_p.exists() else {}
        self.lab_root = lab_root or self.pdir / "phase5" / "lab_cache"
        self.budget = budget
        self._factory = store_factory or (lambda: EventStore.from_processed(self.pdir, self.layers_dir,
                                                                            layer_store.experiment_id))
        self.available = store_factory is not None or (self.pdir / "crashes_processed.parquet").exists()
        self._dictionary: dict[str, Any] | None = None
        if self.available:
            threading.Thread(target=self._load, name="saferoute-events", daemon=True).start()
        else:
            self.error = "İşlenmiş kayıt dosyası (crashes_processed.parquet) yok; Faz 5 analizleri devre dışı."
            self.ready.set()

    def _load(self) -> None:
        t0 = time.perf_counter()
        try:
            self.store = self._factory()
            self.jobs = JobManager(self.store, self.catalog, self.lab_root,
                                   self.layer_store.manifest.get("dataset_version") or "", self.budget)
            self.load_seconds = round(time.perf_counter() - t0, 2)
        except Exception as exc:  # yükleme hatası API'yi düşürmez; uç noktalar 503 döner
            self.error = f"Olay deposu yüklenemedi: {type(exc).__name__}: {exc}"
        finally:
            self.ready.set()

    def require(self) -> EventStore:
        if not self.ready.wait(timeout=60):
            raise HTTPException(503, "Olay deposu hâlâ yükleniyor; birkaç saniye sonra yeniden deneyin.")
        if self.store is None:
            raise HTTPException(503, self.error or "Faz 5 analizleri kullanılamıyor.")
        return self.store

    def filters(self, request: Request) -> FilterSpec:
        store = self.require()
        try:
            return parse_filters({k: request.query_params.get(k) for k in FILTER_KEYS}, set(store.factor_lookup))
        except FilterError as exc:
            raise HTTPException(422, str(exc)) from None

    def time_filters(self, request: Request) -> FilterSpec | None:
        """Sonuç uç noktaları için yalnızca zaman dilimi; başka kayıt filtresi gelirse 422 (iki mod karışmaz)."""
        store = self.require()
        other = [k for k in FILTER_KEYS if k not in TIME_KEYS and request.query_params.get(k) not in (None, "")]
        if other:
            raise HTTPException(422, f"Sonuç görünümünde yalnızca zaman dilimi süzgeci uygulanır; kayıt filtreleri "
                                     f"({', '.join(other)}) kayıtlı/dinamik sonuçla birleştirilmez.")
        try:
            spec = parse_filters({k: request.query_params.get(k) for k in TIME_KEYS}, set(store.factor_lookup))
        except FilterError as exc:
            raise HTTPException(422, str(exc)) from None
        return None if spec.is_empty() else spec

    def dictionary(self) -> dict[str, Any]:
        if self._dictionary is None:
            self._dictionary = data_dictionary(self.pdir, self.prep)
        return self._dictionary


def _bbox(bbox: str, max_span: float) -> tuple[float, float, float, float]:
    from saferoute.viz.api import parse_bbox

    b = parse_bbox(bbox, max_span)
    assert b is not None
    return b


def register(app: FastAPI, layer_store: Any, layers_dir: Path, **kw: Any) -> Analytics:
    from saferoute.viz.api import DEFAULT_POINT_LIMIT, MAX_POINT_BBOX_SPAN_DEG, MAX_POINT_LIMIT

    an = Analytics(layer_store, layers_dir, **kw)
    app.state.analytics = an

    def jobs() -> JobManager:
        an.require()
        if an.jobs is None:
            raise HTTPException(503, an.error or "Laboratuvar kullanılamıyor")
        return an.jobs

    def result_for(rid: str) -> tuple[LabelResult, dict[str, Any]]:
        if not RESULT_ID_RE.match(rid):
            raise HTTPException(404, "Geçersiz sonuç kimliği biçimi.")
        jm = jobs()
        if rid.startswith("dyn-"):
            job = jm.by_experiment(rid)
            if job is None:
                raise HTTPException(404, f"Tamamlanmış dinamik deney bulunamadı: {rid}")
            rid = f"lab-{job.id}"
        if rid.startswith("lab-"):
            job = jm.get(rid[4:])
            if job is None:
                raise HTTPException(404, f"Laboratuvar işi bulunamadı: {rid}")
            if job.state != "completed":
                raise HTTPException(409, f"İş tamamlanmadı (durum: {job.state}); sonuç yok.")
            try:
                res = jm.result(job.id)
            except (ValueError, OSError) as exc:
                raise HTTPException(409, f"Sonuç dosyası doğrulanamadı: {exc}") from None
            assert res is not None
            res.result_id = rid
            return res, job.to_dict()
        if an.catalog is None or rid not in an.catalog.by_id:
            raise HTTPException(404, f"Kayıtlı deney bulunamadı: {rid}")
        exp = an.catalog.experiment(rid)
        if not exp["has_labels"]:
            raise HTTPException(404, f"{rid}: etiket dosyası yok (deney durumu: {exp['status']})")
        try:
            return jm.registry_result(rid), exp
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(409, str(exc)) from None

    # ------------------------------------------------------------------ durum ve genel bakış
    @app.get("/api/analytics/status")
    def status() -> dict[str, Any]:
        return {"ready": an.ready.is_set() and an.store is not None, "loading": not an.ready.is_set(),
                "error": an.error, "load_seconds": an.load_seconds, "version": ANALYTICS_VERSION,
                "n_events": an.store.n_events if an.store else None,
                "job_recovery": an.jobs.recovery if an.jobs else None}

    def _shutdown() -> None:
        if an.jobs is not None:
            an.jobs.shutdown()

    if hasattr(app.state, "shutdown_hooks"):
        app.state.shutdown_hooks.append(_shutdown)

    @app.get("/api/overview")
    def get_overview() -> dict[str, Any]:
        store = an.require()
        if an.catalog is None:
            raise HTTPException(503, "Faz 3 deney kaydı yok")
        ov = overview(store, an.catalog, layer_store.manifest, an.prep, an.pdir)
        top = sorted(layer_store.clusters.values(), key=lambda r: r["rank_by_events"])[:10]
        ov["top_clusters"] = [{k: r.get(k) for k in ("cluster_id", "rank_by_events", "n_events", "n_unique_locations",
                                                      "dominant_borough", "injury_crashes", "fatal_crashes",
                                                      "centroid_lon", "centroid_lat", "peak_hour", "date_min", "date_max")}
                              | {"top_street": (r.get("top_streets") or [{}])[0].get("value")} for r in top]
        clusters_by_borough: dict[str, int] = {}
        for r in layer_store.clusters.values():
            b = r.get("dominant_borough") or "UNKNOWN"
            clusters_by_borough[b] = clusters_by_borough.get(b, 0) + 1
        for row in ov["by_borough"]:
            row["clusters_dominant"] = clusters_by_borough.get(row["borough"], 0)
        return ov

    @app.get("/api/filters/options")
    def options() -> dict[str, Any]:
        return an.require().options()

    # ------------------------------------------------------------------ filtrelenmiş kayıtlar (yeniden kümeleme yok)
    @app.get("/api/records/summary")
    def records_summary(request: Request) -> dict[str, Any]:
        return an.require().summary(an.filters(request))

    @app.get("/api/records/timeline")
    def records_timeline(request: Request, granularity: Literal["year", "month", "hour", "dow"] = "year") -> dict[str, Any]:
        return an.require().timeline(an.filters(request), granularity)

    @app.get("/api/records/density")
    def records_density(request: Request, cell: int = 1000) -> JSONResponse:
        store = an.require()
        spec = an.filters(request)
        try:
            return JSONResponse(store.density(spec, cell))
        except KeyError:
            raise HTTPException(422, f"Geçerli hücre boyutları: {sorted(store.cell_index)}") from None

    @app.get("/api/records/points")
    def records_points(request: Request, bbox: str = Query(..., max_length=200), kind: Literal["clustered", "noise", "all"] = "all",
                       limit: int = Query(DEFAULT_POINT_LIMIT, ge=1, le=MAX_POINT_LIMIT),
                       offset: int = Query(0, ge=0, le=10_000_000)) -> JSONResponse:
        store = an.require()
        spec = an.filters(request)
        return JSONResponse(store.points(spec, _bbox(bbox, MAX_POINT_BBOX_SPAN_DEG), kind, limit, offset))

    @app.get("/api/records/clusters")
    def records_clusters(request: Request) -> JSONResponse:
        """Mevcut modelin kümeleri; ``n_events`` = kümedeki FİLTRELENMİŞ olay sayısı (0 olanlar çıkarılır)."""
        store = an.require()
        spec = an.filters(request)
        counts = store.cluster_counts(spec)
        feats = []
        for cid, r in layer_store.clusters.items():
            n = int(counts[cid]) if cid < len(counts) else 0
            if n == 0:
                continue
            feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["centroid_lon"], r["centroid_lat"]]},
                          "properties": {"cluster_id": cid, "experiment_id": r["experiment_id"], "n_events": n,
                                         "n_events_full": r["n_events"], "rank": r["rank_by_events"],
                                         "borough": r["dominant_borough"]}})
        return JSONResponse({"type": "FeatureCollection", "experiment_id": layer_store.experiment_id,
                             "label_source": "tam veri modeli (yeniden kümeleme yok)", "filters": spec.to_dict(),
                             "total_clusters": len(layer_store.clusters), "returned": len(feats),
                             "events_in_clusters": int(counts.sum()), "features": feats})

    @app.get("/api/records/clusters/{cluster_id}")
    def records_cluster(cluster_id: int, request: Request, experiment_id: str | None = None) -> dict[str, Any]:
        store = an.require()
        if experiment_id is not None and experiment_id != layer_store.experiment_id:
            raise HTTPException(409, f"Küme kimliği farklı bir deneye ait ({experiment_id}).")
        full = layer_store.clusters.get(cluster_id)
        if full is None:
            raise HTTPException(404, f"Küme bulunamadı: {cluster_id}")
        spec = an.filters(request)
        model = layer_store.manifest["model"]
        return {"full": full, "filtered": store.cluster_filtered_detail(spec, cluster_id), "filters_tr": spec.describe_tr(),
                "filters_active": not spec.is_empty(),
                "model": {"algorithm": model["algorithm"], "experiment_id": model["experiment_id"],
                          "parameters": model["parameters"], "features": FEATURE_SETS["spatial_haversine"]["label"],
                          "metric": FEATURE_SETS["spatial_haversine"]["metric"]}}

    # ------------------------------------------------------------------ model karşılaştırma ve deneyler
    @app.get("/api/models/comparison")
    def comparison() -> dict[str, Any]:
        if an.catalog is None:
            raise HTTPException(503, "Faz 3 deney kaydı yok")
        return an.catalog.comparison()

    @app.get("/api/experiments")
    def experiments() -> dict[str, Any]:
        if an.catalog is None:
            raise HTTPException(503, "Faz 3 deney kaydı yok")
        rows = an.catalog.experiments()
        return {"count": len(rows), "experiments": rows, "selected": an.catalog.model_metadata.get("selected")}

    @app.get("/api/experiments/{experiment_id}")
    def experiment(experiment_id: str) -> dict[str, Any]:
        e = an.catalog.experiment(experiment_id) if an.catalog else None
        if e is None:
            raise HTTPException(404, f"Kayıtlı deney bulunamadı: {experiment_id}")
        return e

    # ------------------------------------------------------------------ sonuçlar (kayıtlı deney veya lab işi)
    @app.get("/api/results/{rid}/summary")
    def result_summary(rid: str) -> dict[str, Any]:
        res, meta = result_for(rid)
        return {"result_id": rid, "summary": res.summary(), "meta": meta}

    def _slice(res: LabelResult, request: Request) -> tuple[Any, FilterSpec | None]:
        spec = an.time_filters(request)
        return (None if spec is None else an.require().mask(spec)[res.event_index]), spec

    @app.get("/api/results/{rid}/clusters")
    def result_clusters(rid: str, request: Request) -> JSONResponse:
        res, _ = result_for(rid)
        sel, spec = _slice(res, request)
        out = res.centroids(sel=sel)
        if spec is not None:
            out["time_slice"] = {**out["time_slice"], "filters_tr": spec.describe_tr()}
        return JSONResponse(out)

    @app.get("/api/results/{rid}/timeline")
    def result_timeline(rid: str, granularity: Literal["year", "month", "hour", "dow"] = "year") -> dict[str, Any]:
        res, _ = result_for(rid)
        return res.timeline(granularity)

    @app.get("/api/results/{rid}/density")
    def result_density(rid: str, request: Request, cell: int = 1000) -> JSONResponse:
        res, _ = result_for(rid)
        sel, _ = _slice(res, request)
        try:
            return JSONResponse(res.density(cell, sel))
        except KeyError:
            raise HTTPException(422, f"Geçerli hücre boyutları: {sorted(an.require().cell_index)}") from None

    @app.get("/api/results/{rid}/table")
    def result_table(rid: str, limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
                     sort: Literal["n_events", "injury_crashes", "fatal_crashes", "n_unique_locations"] = "n_events") -> dict[str, Any]:
        res, _ = result_for(rid)
        return res.cluster_rows(limit, offset, sort)

    @app.get("/api/results/{rid}/points")
    def result_points(rid: str, request: Request, bbox: str = Query(..., max_length=200),
                      limit: int = Query(DEFAULT_POINT_LIMIT, ge=1, le=MAX_POINT_LIMIT),
                      offset: int = Query(0, ge=0, le=10_000_000)) -> JSONResponse:
        res, _ = result_for(rid)
        sel, _ = _slice(res, request)
        return JSONResponse(res.points(_bbox(bbox, MAX_POINT_BBOX_SPAN_DEG), limit, sel, offset))

    @app.get("/api/results/{rid}/clusters/{cluster_id}")
    def result_cluster(rid: str, cluster_id: int) -> dict[str, Any]:
        res, meta = result_for(rid)
        d = res.cluster_detail(cluster_id)
        if d is None:
            raise HTTPException(404, f"{rid} sonucunda küme yok: {cluster_id}")
        return {"cluster": d, "meta": meta}

    # ------------------------------------------------------------------ laboratuvar işleri
    def job_or_404(job_id: str):
        if not JOB_ID_RE.match(job_id):
            raise HTTPException(404, "Geçersiz iş kimliği biçimi.")
        job = jobs().get(job_id)
        if job is None:
            raise HTTPException(404, f"İş bulunamadı: {job_id}")
        return job

    @app.get("/api/lab/resources")
    def lab_resources() -> dict[str, Any]:
        """Anlık kaynak durumu: boş fiziksel bellek, başlatılabilirlik, çalışan bellek tavanı, kuyruk."""
        return jobs().resources()

    @app.get("/api/lab/capabilities")
    def lab_capabilities() -> dict[str, Any]:
        cap = capabilities()
        if an.jobs is not None:
            cap["budget"] = an.jobs.budget
        sw = (an.catalog.model_metadata.get("software") if an.catalog else None) or {}
        cap["software"] = sw
        return cap

    @app.post("/api/lab/jobs", status_code=202)
    def lab_submit(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
        jm = jobs()
        try:
            req = validate_request(body, set(an.store.factor_lookup) if an.store else None)
            job = jm.submit(req)
        except LabRequestError as exc:
            raise HTTPException(422, str(exc)) from None
        except EmptyScope as exc:
            raise HTTPException(422, str(exc)) from None
        except QueueFull as exc:
            raise HTTPException(429, str(exc)) from None
        return job.to_dict()

    @app.get("/api/lab/jobs")
    def lab_list(limit: int = Query(100, ge=1, le=500)) -> dict[str, Any]:
        return {"jobs": jobs().list(limit)}

    @app.get("/api/lab/jobs/{job_id}")
    def lab_get(job_id: str) -> dict[str, Any]:
        return job_or_404(job_id).to_dict()

    @app.delete("/api/lab/jobs/{job_id}")
    def lab_cancel(job_id: str) -> dict[str, Any]:
        job_or_404(job_id)
        job = jobs().cancel(job_id)
        assert job is not None
        return job.to_dict()

    @app.post("/api/lab/jobs/{job_id}/retry", status_code=202)
    def lab_retry(job_id: str) -> dict[str, Any]:
        """Yarım kalmış/başarısız/iptal/kaynak sınırlı bir işi AÇIK kullanıcı isteğiyle yeni iş olarak başlatır."""
        job_or_404(job_id)
        try:
            return jobs().retry(job_id, set(an.store.factor_lookup) if an.store else None).to_dict()
        except NotRetryable as exc:
            raise HTTPException(409, str(exc)) from None
        except (LabRequestError, EmptyScope) as exc:
            raise HTTPException(422, str(exc)) from None
        except QueueFull as exc:
            raise HTTPException(429, str(exc)) from None

    # ------------------------------------------------------------------ veri sözlüğü
    @app.get("/api/data/dictionary")
    def dictionary() -> dict[str, Any]:
        if not (an.pdir / "crashes_processed.parquet").exists():
            raise HTTPException(503, "İşlenmiş kayıt dosyası yok")
        return an.dictionary()

    # ------------------------------------------------------------------ dışa aktarma
    def _source() -> dict[str, Any]:
        src = source_record(an.pdir)
        acq = src.get("acquisition") or {}
        return {"dataset_id": src["dataset_id"], "dataset_name": src.get("dataset_name"), "source_url": src["source_url"],
                "snapshot": src["snapshot"], "rows_updated_at": src["freshness"].get("rows_updated_at"),
                "verdict": src["freshness"].get("verdict_at_check"), "retrieved_at": acq.get("retrieval_completed_utc")}

    def _send(doc: ReportDocument, fmt: str, name: str) -> Response:
        try:
            body, mime, ext = render(doc, fmt)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return Response(body, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}.{ext}"'})

    @app.get("/api/export/records")
    def export_records(request: Request, format: str = "md") -> Response:
        store = an.require()
        spec = an.filters(request)
        s = store.summary(spec)
        counts = store.cluster_counts(spec)
        model = layer_store.manifest["model"]
        order = counts.argsort()[::-1][:50]
        table = [{"cluster_id": int(c), "filtered_events": int(counts[c]),
                  "full_events": layer_store.clusters[int(c)]["n_events"],
                  "dominant_borough": layer_store.clusters[int(c)]["dominant_borough"],
                  "centroid_lon": layer_store.clusters[int(c)]["centroid_lon"],
                  "centroid_lat": layer_store.clusters[int(c)]["centroid_lat"]} for c in order if counts[c] > 0]
        doc = ReportDocument(
            kind="filtered_records", title="SafeRoute 3D — Filtrelenmiş kayıt özeti", source=_source(),
            data_version=layer_store.manifest.get("dataset_version"),
            algorithm={"name": model["algorithm"].upper(), "parameters": model["parameters"], "id": model["experiment_id"],
                       "features": FEATURE_SETS["spatial_haversine"]["label"], "metric": FEATURE_SETS["spatial_haversine"]["metric"],
                       "scope": "Tam veri etiketleri; filtrelenmiş kayıtlar üzerinde YENİDEN KÜMELEME YAPILMADI",
                       "software": (an.catalog.model_metadata.get("software") if an.catalog else None)},
            filters=s["filters_tr"], n_records=s["n_events"],
            metrics={"kayıt_payı": s["share_of_total"], "yaralanmalı_kaza": s["injury_crashes"], "ölümlü_kaza": s["fatal_crashes"],
                     "kümelerdeki_olay": s["model"]["events_in_clusters"], "gürültü_olayı": s["model"]["events_noise"],
                     "olay_içeren_küme": s["model"]["clusters_with_events"]},
            limitations=["Küme etiketleri tam veride bulunan kümelerdir; filtre yalnızca hangi kayıtların sayıldığını değiştirir."],
            sections=[{"id": "by_year", "title": "Yıllara göre olay", "kind": "table", "rows": s["by_year"]},
                      {"id": "by_borough", "title": "İlçelere göre", "kind": "table", "rows": s["by_borough"]},
                      {"id": "factors", "title": "Kaydedilmiş katkı faktörleri (kaza başına)", "kind": "table",
                       "rows": s["top_factors"]}],
            table=table)
        return _send(doc, format, f"saferoute-kayit-ozeti-{spec.digest(8)}")

    @app.get("/api/export/results/{rid}")
    def export_result(rid: str, format: str = "md") -> Response:
        res, meta = result_for(rid)
        sm = res.summary()
        if rid.startswith("lab-"):
            req = meta["request"]
            fs = FEATURE_SETS[req["feature_set"]]
            w = meta.get("worker") or {}
            metrics = ((meta.get("result") or {}).get("metrics")) or ((meta.get("result") or {}).get("phase3_metrics")) or {}
            algo = {"name": req["algorithm"].upper(), "parameters": req["params"], "id": rid, "features": fs["label"],
                    "metric": fs["metric"], "scope": f"{fs['level']}; örneklem: {req.get('sample') or 'yok'}",
                    "software": meta.get("code_version")}
            filters = meta.get("filters_tr") or []
            extra = {"çalışma_süresi_sn": w.get("runtime_s"), "tepe_bellek_mb": w.get("peak_memory_mb"),
                     "kaynak": meta.get("source"), "faz3_deneyi": meta.get("phase3_experiment")}
        else:
            e = meta
            algo = {"name": e["algorithm"].upper(), "parameters": e["params"], "id": rid, "features": e["feature_set"],
                    "metric": None, "scope": e["scope_text"], "software": e.get("software")}
            filters = [scope_text(an.catalog.by_id[rid])] if an.catalog else []
            metrics = e.get("metrics") or {}
            extra = {"çalışma_süresi_sn": e.get("runtime_s"), "tepe_bellek_mb": e.get("peak_memory_mb"), "kaynak": "Faz 3 kaydı"}
        flat = {"küme_sayısı": sm["n_clusters"],
                "gürültü_oranı": sm["noise_ratio"] if sm["noise_applicable"] else "uygulanamaz (K-Means)",
                "en_büyük_küme_payı": sm["largest_cluster_share"],
                **{k: v for k, v in metrics.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}, **extra}
        doc = ReportDocument(kind="clustering_result", title=f"SafeRoute 3D — Kümeleme sonucu {rid}", source=_source(),
                             data_version=layer_store.manifest.get("dataset_version"), algorithm=algo, filters=filters,
                             n_records=sm["n_events"], metrics=flat,
                             limitations=["Dinamik metrikler basit rastgele örneklemle hesaplanır; Faz 3 ortak "
                                          "değerlendirme kümesiyle doğrudan karşılaştırılamaz."] if rid.startswith("lab-") else [],
                             sections=[{"id": "sizes", "title": "Küme büyüklüğü dağılımı", "kind": "table", "rows": sm["size_histogram"]}],
                             table=res.export_rows())
        return _send(doc, format, f"saferoute-{rid}")

    return an
