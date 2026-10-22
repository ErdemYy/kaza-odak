"""Kaza Odak komut satırı arayüzü (teknik paket adı: saferoute).

Kullanım:
    saferoute check-source             Kaynak erişilebilirliği ve güncellik kontrolü
    saferoute download [--page-size N] [--resume DIZIN]
    saferoute verify [DIZIN]           SHA-256 bütünlük doğrulaması
    saferoute record [DIZIN]           Edinim kaydını data/metadata/ altına yaz
    saferoute parquet [DIZIN]          Kayıpsız Parquet kopyası (data/interim/)
    saferoute eda [--snapshot DIZIN] [--out DIZIN]
    saferoute boundaries               Resmî ilçe sınırlarını indir (gthc-hcne)
    saferoute preprocess [--force]     Faz 2 hattı + raporlar
    saferoute cluster [--force]        Faz 3 kümeleme deneyleri + raporlar
    saferoute viz-build                Faz 4 coğrafi sunum katmanları (manifest doğrulamalı)
    saferoute serve [--port 8000]      Faz 4–5 API'si (+ derlenmiş ön yüz)
    saferoute phase5-bench             Faz 5 filtre/laboratuvar API ölçümü
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from saferoute import config


def _snapshot(arg: str | None) -> Path:
    from saferoute.data.loader import latest_snapshot

    return Path(arg) if arg else latest_snapshot()


def _cmd_check_source(args: argparse.Namespace) -> int:
    from saferoute.data.metadata import check_source, write_record

    record = check_source()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = write_record(record, f"source_status_{stamp}.json")
    print(json.dumps(record, indent=2, ensure_ascii=False))
    print(f"Kaydedildi: {path}")
    return 0 if record.get("reachable") else 2


def _cmd_download(args: argparse.Namespace) -> int:
    from saferoute.data.download import DownloadError, download_snapshot
    from saferoute.data.metadata import acquisition_record, write_record

    try:
        path = download_snapshot(snapshot_dir=args.resume, page_size=args.page_size)
    except DownloadError as exc:
        print(f"İNDİRME TAMAMLANAMADI: {exc}", file=sys.stderr)
        print("Kısmi veri korunuyor; 'saferoute download --resume <dizin>' ile sürdürülebilir.", file=sys.stderr)
        return 1
    rec = write_record(acquisition_record(path), f"acquisition_{path.name}.json")
    print(f"Edinim kaydı: {rec}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    from saferoute.data.loader import IntegrityError, verify_snapshot

    snap = _snapshot(args.snapshot)
    try:
        m = verify_snapshot(snap)
    except IntegrityError as exc:
        print(f"BÜTÜNLÜK HATASI: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {snap.name} — {m['row_count']:,} satır, {len(m['parts'])} parça, durum={m['status']}")
    return 0


def _cmd_record(args: argparse.Namespace) -> int:
    from saferoute.data.metadata import acquisition_record, write_record

    snap = Path(args.snapshot) if args.snapshot else _snapshot(None)
    rec = acquisition_record(snap)
    path = write_record(rec, f"acquisition_{snap.name}.json")
    print(f"{rec['acquisition_status']}: {rec['row_count']:,} satır -> {path}")
    return 0


def _cmd_parquet(args: argparse.Namespace) -> int:
    from saferoute.data.convert import snapshot_to_parquet

    path = snapshot_to_parquet(_snapshot(args.snapshot), force=args.force)
    print(path)
    return 0


def _cmd_eda(args: argparse.Namespace) -> int:
    from saferoute.eda.report import run_eda

    run_eda(_snapshot(args.snapshot), Path(args.out), dictionary_path=Path(args.dictionary))
    return 0


def _cmd_boundaries(args: argparse.Namespace) -> int:
    from saferoute.preprocess.boundaries import download_boundaries

    print(download_boundaries())
    return 0


def _cmd_preprocess(args: argparse.Namespace) -> int:
    from saferoute.preprocess.boundaries import latest_boundaries
    from saferoute.preprocess.pipeline import output_paths, run_pipeline
    from saferoute.preprocess.report import write_reports

    snap = _snapshot(args.snapshot)
    try:
        bdir = Path(args.boundaries) if args.boundaries else latest_boundaries()
    except FileNotFoundError:
        from saferoute.preprocess.boundaries import download_boundaries

        print("İlçe sınırı anlık görüntüsü yok; resmî kaynaktan indiriliyor.")
        bdir = download_boundaries()
    summary = run_pipeline(snap, bdir, force=args.force)
    if not summary.get("raw_unchanged", True):
        print("HATA: ham veri işlem sırasında değişti.", file=sys.stderr)
        return 1
    if not args.skip_reports:
        import pandas as pd

        paths = output_paths(snap.name)
        processed = pd.read_parquet(paths["processed"])
        mapping = pd.read_parquet(paths["mapping"])
        figs = write_reports(summary, processed, mapping)
        print(f"Faz 2 raporları yazıldı ({len(figs)} şekil): {config.REPORTS_DIR / 'phase2'}")
    return 0


def _cmd_cluster(args: argparse.Namespace) -> int:
    from saferoute.clustering.runner import Phase3Runner
    from saferoute.clustering.settings import load_config

    runner = Phase3Runner(load_config(Path(args.config)) if args.config else None, force=args.force)
    stages = [s.strip() for s in args.stages.split(",")] if args.stages else None
    results = runner.run_all(stages)
    print(f"Hesaplanan aşamalar: {results['stages_computed_this_run']}; boş bellek (son): "
          f"{results['meta']['available_memory_mb_end']} MB; orkestratör tepe: {results['meta']['orchestrator_peak_memory_mb']} MB")
    if not args.skip_reports and "profiles" in results["stages_computed_this_run"]:
        from saferoute.clustering.report import write_reports

        figs = write_reports(results, runner)
        print(f"Faz 3 raporları yazıldı ({len(figs)} şekil): {config.REPORTS_DIR / 'phase3'}")
    print(f"Deney sayısı: {results['meta']['n_experiments']}, durumlar: {results['meta']['status_counts']}")
    return 0


def _cmd_viz_build(args: argparse.Namespace) -> int:
    from saferoute.viz.layers import build_layers

    build_layers(out_dir=Path(args.out) if args.out else None)
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from saferoute.viz.api import create_app

    frontend = Path(args.frontend) if args.frontend else config.REPO_ROOT / "frontend" / "dist"
    analytics: dict[str, object] | bool = {"lab_root": Path(args.lab_root)} if args.lab_root else True
    app = create_app(Path(args.layers) if args.layers else None, frontend_dir=frontend, analytics=analytics)
    print(f"Ön yüz: {frontend if frontend.exists() else 'derlenmemiş (yalnızca API)'}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def _cmd_viz_bench(args: argparse.Namespace) -> int:
    from saferoute.viz.benchmark import run_benchmark

    res = run_benchmark(repeats=args.repeats)
    for name, r in res["requests"].items():
        print(f"{name:28s} {r['status']} medyan {r['median_ms']} ms · gzip {r['wire_bytes_gzip']} B")
    return 0


def _cmd_phase5_bench(args: argparse.Namespace) -> int:
    from saferoute.analytics.benchmark import run_benchmark

    res = run_benchmark(repeats=args.repeats)
    print(f"Uygulama + olay deposu hazır: {res['app_and_store_ready_s']} sn · bellek {res['rss_after_store_mb']} MB")
    for name, r in res["requests"].items():
        print(f"{name:28s} {r['status']} ilk {r['first_ms']} ms · medyan {r['median_ms']} ms · gzip {r['wire_bytes_gzip']} B")
    if "dynamic_job" in res:
        print(f"Dinamik DBSCAN işi: {res['dynamic_job']['state']} ({res['dynamic_job']['source']}) {res['dynamic_job']['wall_s']} sn")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="saferoute", description="Kaza Odak veri hattı")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check-source", help="Resmi kaynağın erişilebilirliğini ve güncelliğini kontrol et")
    p.set_defaults(func=_cmd_check_source)

    p = sub.add_parser("download", help="Ham veri anlık görüntüsünü indir")
    p.add_argument("--page-size", type=int, default=250_000)
    p.add_argument("--resume", type=Path, default=None, help="Yarım kalmış anlık görüntü dizini")
    p.set_defaults(func=_cmd_download)

    p = sub.add_parser("verify", help="Anlık görüntü sağlama toplamlarını doğrula")
    p.add_argument("snapshot", nargs="?", default=None)
    p.set_defaults(func=_cmd_verify)

    p = sub.add_parser("record", help="Edinim kaydını yaz (tam veya kısmi)")
    p.add_argument("snapshot", nargs="?", default=None)
    p.set_defaults(func=_cmd_record)

    p = sub.add_parser("parquet", help="Kayıpsız Parquet kopyası üret")
    p.add_argument("snapshot", nargs="?", default=None)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=_cmd_parquet)

    p = sub.add_parser("eda", help="Keşifsel veri analizi raporu ve veri sözlüğü üret")
    p.add_argument("--snapshot", default=None)
    p.add_argument("--out", default=str(config.REPORTS_DIR / "phase1"))
    p.add_argument("--dictionary", default=str(config.DOCS_DIR / "data_dictionary.md"))
    p.set_defaults(func=_cmd_eda)

    p = sub.add_parser("boundaries", help="Resmî NYC ilçe sınırlarını (gthc-hcne) indir ve doğrula")
    p.set_defaults(func=_cmd_boundaries)

    p = sub.add_parser("preprocess", help="Faz 2: interim, processed ve öznitelik matrislerini üret")
    p.add_argument("--snapshot", default=None)
    p.add_argument("--boundaries", default=None, help="İlçe sınırı anlık görüntü dizini")
    p.add_argument("--force", action="store_true", help="Güncel olsa bile yeniden üret")
    p.add_argument("--skip-reports", action="store_true")
    p.set_defaults(func=_cmd_preprocess)

    p = sub.add_parser("cluster", help="Faz 3: kümeleme deneyleri, değerlendirme ve sonuç dosyaları")
    p.add_argument("--config", default=None, help="TOML yapılandırma (varsayılan: backend/configs/phase3.toml)")
    p.add_argument("--force", action="store_true", help="Kayıtlı başarılı deneyleri de yeniden çalıştır")
    p.add_argument("--stages", default=None,
                   help="Virgülle ayrılmış aşamalar (ör. hdbscan,evaluate); önceki aşamalar kontrol noktasından okunur")
    p.add_argument("--skip-reports", action="store_true")
    p.set_defaults(func=_cmd_cluster)

    p = sub.add_parser("viz-build", help="Faz 4: Faz 3 çıktılarından doğrulanmış coğrafi sunum katmanları")
    p.add_argument("--out", default=None, help="Çıktı dizini (varsayılan: <processed>/phase4)")
    p.set_defaults(func=_cmd_viz_build)

    p = sub.add_parser("serve", help="Faz 4: katman API'si ve derlenmiş ön yüz")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--layers", default=None, help="Katman dizini (varsayılan: <processed>/phase4)")
    p.add_argument("--frontend", default=None, help="Derlenmiş ön yüz (varsayılan: frontend/dist)")
    p.add_argument("--lab-root", default=None,
                   help="Laboratuvar iş kaydı + sonuç dizini (varsayılan: <processed>/phase5/lab_cache; yalıtılmış test/demo için)")
    p.set_defaults(func=_cmd_serve)

    p = sub.add_parser("viz-bench", help="Faz 4: API gecikme/yük ölçümü (reports/phase4/api_benchmark.json)")
    p.add_argument("--repeats", type=int, default=15)
    p.set_defaults(func=_cmd_viz_bench)

    p = sub.add_parser("phase5-bench", help="Faz 5: filtre/laboratuvar API ölçümü (reports/phase5/api_benchmark.json)")
    p.add_argument("--repeats", type=int, default=10)
    p.set_defaults(func=_cmd_phase5_bench)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
