"""Ham veri anlık görüntüsünü (snapshot) sayfalı, yeniden denemeli ve sürdürülebilir biçimde indirir.

Yöntem: Socrata SODA 2.x CSV uç noktası, ``$order=:id`` ile kararlı sıralama ve
``$limit``/``$offset`` sayfalama. ``:id`` sistem kimliğine göre sıralama, ``collision_id``
değerlerinde olası tekrarlar olsa bile hiçbir satırın atlanmamasını garanti eder.

Her sayfa ayrı bir ``part-NNNNN.csv`` dosyası olarak değiştirilmeden saklanır; indirme
tamamlandığında SHA-256 sağlama toplamlarını içeren ``manifest.json`` yazılır ve tüm
dosyalar salt-okunur yapılır (ham verinin değişmezliği).
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pyarrow.csv as pacsv
import requests

from saferoute import config
from saferoute.data.source import fetch_metadata, fetch_server_stats, make_session

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
MANIFEST_NAME = "manifest.json"
PROGRESS_NAME = "_progress.json"


class DownloadError(RuntimeError):
    """İndirme kurtarılamaz biçimde başarısız olduğunda fırlatılır."""


class _TransientError(Exception):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def count_csv_rows(path: Path) -> tuple[list[str], int]:
    """CSV başlığını ve veri satırı sayısını döndürür (tırnak içi satır sonlarını doğru sayar)."""
    with open(path, encoding="utf-8", newline="") as f:
        header = next(csv.reader(f), [])
    if not header:
        return [], 0
    table = pacsv.read_csv(
        path,
        parse_options=pacsv.ParseOptions(newlines_in_values=True),
        convert_options=pacsv.ConvertOptions(
            include_columns=[header[0]], column_types={header[0]: "string"}
        ),
    )
    return header, table.num_rows


def file_sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_page(
    session: requests.Session,
    snapshot_dir: Path,
    index: int,
    offset: int,
    page_size: int,
    expected_fields: list[str],
    max_retries: int,
    backoff: float,
    timeout: float,
    sleep: Callable[[float], None],
) -> dict[str, Any]:
    """Tek bir sayfayı indirir; geçici hatalarda üstel geri çekilmeyle yeniden dener."""
    params = {"$order": ":id", "$limit": page_size, "$offset": offset}
    final = snapshot_dir / f"part-{index:05d}.csv"
    tmp = final.with_name(final.name + ".partial")

    for attempt in range(1, max_retries + 1):
        try:
            with session.get(config.RESOURCE_CSV_URL, params=params, timeout=timeout, stream=True) as resp:
                if resp.status_code in RETRYABLE_STATUS:
                    raise _TransientError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                digest = hashlib.sha256()
                size = 0
                with open(tmp, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1 << 20):
                        if chunk:
                            f.write(chunk)
                            digest.update(chunk)
                            size += len(chunk)
                truth_modified = resp.headers.get("X-SODA2-Truth-Last-Modified")

            header, rows = count_csv_rows(tmp)
            if header != expected_fields:
                raise DownloadError(
                    f"Sayfa {index}: CSV başlığı beklenen şemayla uyuşmuyor. "
                    f"Beklenen={expected_fields}, gelen={header}"
                )
            os.replace(tmp, final)
            return {
                "file": final.name,
                "offset": offset,
                "rows": rows,
                "bytes": size,
                "sha256": digest.hexdigest(),
                "truth_last_modified": truth_modified,
                "attempts": attempt,
                "downloaded_at": _utc_now(),
            }
        except (
            requests.ConnectionError,
            requests.Timeout,
            requests.exceptions.ChunkedEncodingError,
            _TransientError,
        ) as exc:
            tmp.unlink(missing_ok=True)
            if attempt == max_retries:
                raise DownloadError(
                    f"Sayfa {index} (offset={offset}) {max_retries} denemede indirilemedi: {exc}"
                ) from exc
            sleep(backoff * 2 ** (attempt - 1))
        except requests.HTTPError as exc:
            tmp.unlink(missing_ok=True)
            raise DownloadError(f"Sayfa {index}: yeniden denenemeyen HTTP hatası: {exc}") from exc
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    raise AssertionError("unreachable")


def _software_versions() -> dict[str, str]:
    import pandas
    import pyarrow

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pandas": pandas.__version__,
        "pyarrow": pyarrow.__version__,
        "requests": requests.__version__,
    }


def _make_read_only(path: Path) -> None:
    os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)


def download_snapshot(
    out_root: Path | None = None,
    snapshot_dir: Path | None = None,
    page_size: int = 250_000,
    session: requests.Session | None = None,
    max_retries: int = 5,
    backoff: float = 2.0,
    timeout: float = 300,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> Path:
    """Veri setinin tam bir ham anlık görüntüsünü indirir ve ``manifest.json`` yazar.

    ``snapshot_dir`` verilirse ve içinde ``_progress.json`` varsa, yarım kalmış indirme
    kaldığı sayfadan sürdürülür. Tamamlanmış (manifest'i olan) bir anlık görüntü
    yeniden yazılmaz.
    """
    if page_size <= 0:
        raise ValueError("page_size pozitif olmalıdır")
    session = session or make_session()
    out_root = Path(out_root or config.RAW_DIR)

    if snapshot_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snapshot_dir = out_root / config.DATASET_ID / f"snapshot_{stamp}"
    snapshot_dir = Path(snapshot_dir)
    if (snapshot_dir / MANIFEST_NAME).exists():
        raise DownloadError(f"{snapshot_dir} zaten tamamlanmış bir anlık görüntü; değiştirilmez.")
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    progress_path = snapshot_dir / PROGRESS_NAME
    if progress_path.exists():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        if progress["page_size"] != page_size:
            raise DownloadError("Sürdürülen indirmede page_size değiştirilemez.")
        log(f"Sürdürülüyor: {len(progress['parts'])} sayfa zaten indirilmiş.")
    else:
        metadata = fetch_metadata(session)
        progress = {
            "started_at": _utc_now(),
            "page_size": page_size,
            "metadata_before": metadata,
            "server_stats_before": fetch_server_stats(session),
            "parts": [],
        }
        _write_json(progress_path, progress)

    expected_fields = [c["field_name"] for c in progress["metadata_before"]["columns"]]
    parts: list[dict[str, Any]] = progress["parts"]
    offset = sum(p["rows"] for p in parts)
    expected_total = progress["server_stats_before"]["row_count"]

    finished = bool(parts) and parts[-1]["rows"] < page_size
    while not finished:
        index = len(parts)
        part = _download_page(
            session, snapshot_dir, index, offset, page_size, expected_fields,
            max_retries, backoff, timeout, sleep,
        )
        if part["rows"] == 0:
            (snapshot_dir / part["file"]).unlink()
            break
        parts.append(part)
        _write_json(progress_path, progress)
        offset += part["rows"]
        log(f"Sayfa {index}: {part['rows']:,} satır (toplam {offset:,} / ~{expected_total:,})")
        finished = part["rows"] < page_size

    metadata_after = fetch_metadata(session)
    stats_after = fetch_server_stats(session)

    combined = hashlib.sha256()
    for p in parts:
        path = snapshot_dir / p["file"]
        if file_sha256(path) != p["sha256"]:
            raise DownloadError(f"{p['file']} diskteki sağlama toplamı indirme sırasındakiyle uyuşmuyor.")
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                combined.update(chunk)

    total_rows = sum(p["rows"] for p in parts)
    truth_values = {p["truth_last_modified"] for p in parts}
    truth_values |= {progress["server_stats_before"]["truth_last_modified"], stats_after["truth_last_modified"]}
    truth_values.discard(None)

    warnings: list[str] = []
    if total_rows != stats_after["row_count"]:
        warnings.append(
            f"İndirilen satır sayısı ({total_rows}) sunucu sayımıyla ({stats_after['row_count']}) uyuşmuyor."
        )
    if len(truth_values) > 1:
        warnings.append("Kaynak, indirme sırasında güncellendi; anlık görüntü tutarlı olmayabilir.")
    if progress["metadata_before"]["rows_updated_at"] != metadata_after["rows_updated_at"]:
        warnings.append("rowsUpdatedAt indirme sırasında değişti.")

    manifest = {
        "dataset_id": config.DATASET_ID,
        "dataset_name": metadata_after["name"],
        "source_page_url": config.DATASET_PAGE_URL,
        "catalog_url": config.CATALOG_URL,
        "metadata_url": config.METADATA_URL,
        "download_method": {
            "endpoint": config.RESOURCE_CSV_URL,
            "api": "Socrata SODA 2.x (CSV)",
            "ordering": "$order=:id",
            "pagination": "$limit/$offset",
            "page_size": page_size,
            "max_retries": max_retries,
        },
        "started_at": progress["started_at"],
        "completed_at": _utc_now(),
        "source_version": {
            "rows_updated_at_before": progress["metadata_before"]["rows_updated_at"],
            "rows_updated_at_after": metadata_after["rows_updated_at"],
            "view_last_modified": metadata_after["view_last_modified"],
            "truth_last_modified_values": sorted(truth_values),
            "update_frequency": metadata_after["update_frequency"],
        },
        "server_stats_before": progress["server_stats_before"],
        "server_stats_after": stats_after,
        "row_count": total_rows,
        "column_count": len(expected_fields),
        "columns": progress["metadata_before"]["columns"],
        "coverage": {
            "min_crash_date": stats_after["min_crash_date"],
            "max_crash_date": stats_after["max_crash_date"],
        },
        "parts": parts,
        "combined_sha256": combined.hexdigest(),
        "status": "complete" if not warnings else "complete_with_warnings",
        "warnings": warnings,
        "software": _software_versions(),
        "license": metadata_after["license"],
        "attribution": metadata_after["attribution"],
    }
    manifest_path = snapshot_dir / MANIFEST_NAME
    _write_json(manifest_path, manifest)
    progress_path.unlink(missing_ok=True)
    for p in parts:
        _make_read_only(snapshot_dir / p["file"])
    _make_read_only(manifest_path)

    for w in warnings:
        log(f"UYARI: {w}")
    log(f"Tamamlandı: {total_rows:,} satır, {len(parts)} parça -> {snapshot_dir}")
    return snapshot_dir
