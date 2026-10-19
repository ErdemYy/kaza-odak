"""SafeRoute 3D komut satırı arayüzü.

Kullanım:
    saferoute download [--page-size N] [--resume DIZIN]
    saferoute verify [DIZIN]
    saferoute eda [--snapshot DIZIN] [--out DIZIN]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from saferoute import config


def _cmd_download(args: argparse.Namespace) -> int:
    from saferoute.data.download import download_snapshot

    path = download_snapshot(snapshot_dir=args.resume, page_size=args.page_size)
    print(path)
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    from saferoute.data.loader import IntegrityError, latest_snapshot, verify_snapshot

    snap = Path(args.snapshot) if args.snapshot else latest_snapshot()
    try:
        m = verify_snapshot(snap)
    except IntegrityError as exc:
        print(f"BÜTÜNLÜK HATASI: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {snap.name} — {m['row_count']:,} satır, {len(m['parts'])} parça, durum={m['status']}")
    return 0


def _cmd_eda(args: argparse.Namespace) -> int:
    from saferoute.data.loader import latest_snapshot
    from saferoute.eda.report import run_eda

    snap = Path(args.snapshot) if args.snapshot else latest_snapshot()
    run_eda(snap, Path(args.out), trace_memory=args.trace_memory)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="saferoute", description="SafeRoute 3D veri hattı")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("download", help="Ham veri anlık görüntüsünü indir")
    p.add_argument("--page-size", type=int, default=250_000)
    p.add_argument("--resume", type=Path, default=None, help="Yarım kalmış anlık görüntü dizini")
    p.set_defaults(func=_cmd_download)

    p = sub.add_parser("verify", help="Anlık görüntü sağlama toplamlarını doğrula")
    p.add_argument("snapshot", nargs="?", default=None)
    p.set_defaults(func=_cmd_verify)

    p = sub.add_parser("eda", help="Keşifsel veri analizi raporu üret")
    p.add_argument("--snapshot", default=None)
    p.add_argument("--out", default=str(config.REPORTS_DIR / "phase1"))
    p.add_argument("--trace-memory", action="store_true", help="Python bellek tepe değerini ölç (yavaşlatır)")
    p.set_defaults(func=_cmd_eda)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
