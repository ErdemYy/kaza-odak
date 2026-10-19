"""SafeRoute 3D komut satırı arayüzü.

Kullanım:
    saferoute check-source             Kaynak erişilebilirliği ve güncellik kontrolü
    saferoute download [--page-size N] [--resume DIZIN]
    saferoute verify [DIZIN]           SHA-256 bütünlük doğrulaması
    saferoute record [DIZIN]           Edinim kaydını data/metadata/ altına yaz
    saferoute parquet [DIZIN]          Kayıpsız Parquet kopyası (data/interim/)
    saferoute eda [--snapshot DIZIN] [--out DIZIN]
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="saferoute", description="SafeRoute 3D veri hattı")
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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
