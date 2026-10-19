"""Kaynak erişilebilirliği/güncellik kontrolü ve edinim (acquisition) kayıtları.

Kayıtlar ``data/metadata/`` altına küçük JSON dosyaları olarak yazılır ve git'te izlenir;
böylece ham veri depoya girmeden hangi verinin, ne zaman, hangi durumda alındığı izlenebilir.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from saferoute import config
from saferoute.data.download import MANIFEST_NAME, PROGRESS_NAME
from saferoute.data.source import fetch_metadata, fetch_server_stats, make_session


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _days_between(earlier: str | None, later: datetime) -> int | None:
    if not earlier:
        return None
    ts = pd.Timestamp(earlier)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return (later - ts.to_pydatetime()).days


def assess_freshness(rows_updated_at: str | None, update_frequency: str | None, now: datetime) -> dict[str, Any]:
    """Beyan edilen güncelleme sıklığına göre kaynağın güncel olup olmadığını değerlendirir."""
    age = _days_between(rows_updated_at, now)
    threshold = config.STALENESS_THRESHOLD_DAYS.get(update_frequency or "")
    if age is None or threshold is None:
        verdict = "unknown"
    else:
        verdict = "updating" if age <= threshold else "stale"
    return {
        "rows_updated_at": rows_updated_at,
        "declared_update_frequency": update_frequency,
        "days_since_rows_updated": age,
        "staleness_threshold_days": threshold,
        "verdict": verdict,
    }


def check_source(session: requests.Session | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Resmi kaynağın erişilebilirliğini, sürümünü ve güncellik durumunu kontrol eder.

    Ağ hatasında istisna fırlatmaz; ``reachable=False`` ve hata metniyle döner.
    """
    session = session or make_session()
    now = now or _now()
    record: dict[str, Any] = {
        "checked_at": now.isoformat(),
        "dataset_id": config.DATASET_ID,
        "metadata_url": config.METADATA_URL,
        "app_token_configured": "X-App-Token" in session.headers,
    }
    try:
        meta = fetch_metadata(session)
        stats = fetch_server_stats(session)
    except requests.RequestException as exc:
        record.update({"reachable": False, "error": str(exc)})
        return record
    record.update({
        "reachable": True,
        "name": meta["name"],
        "attribution": meta["attribution"],
        "license": meta["license"],
        "view_last_modified": meta["view_last_modified"],
        "column_count": len(meta["columns"]),
        "server_row_count": stats["row_count"],
        "server_min_crash_date": stats["min_crash_date"],
        "server_max_crash_date": stats["max_crash_date"],
        "truth_last_modified": stats["truth_last_modified"],
        "freshness": assess_freshness(meta["rows_updated_at"], meta["update_frequency"], now),
    })
    try:
        resp = session.get(config.BOROUGH_BOUNDARIES_METADATA_URL, timeout=60)
        resp.raise_for_status()
        b = resp.json()
        record["borough_boundaries_source"] = {
            "dataset_id": config.BOROUGH_BOUNDARIES_DATASET_ID,
            "name": b.get("name"),
            "attribution": b.get("attribution"),
            "rows_updated_at": datetime.fromtimestamp(int(b["rowsUpdatedAt"]), tz=timezone.utc).isoformat()
            if b.get("rowsUpdatedAt") else None,
            "reachable": True,
        }
    except requests.RequestException as exc:
        record["borough_boundaries_source"] = {"dataset_id": config.BOROUGH_BOUNDARIES_DATASET_ID,
                                               "reachable": False, "error": str(exc)}
    return record


def acquisition_record(snapshot_dir: Path) -> dict[str, Any]:
    """Tamamlanmış ya da yarım kalmış bir anlık görüntü için edinim kaydı üretir.

    Yarım indirmelerde ``acquisition_status='partial'`` döner; kısmi veri asla tam veri
    gibi raporlanmaz.
    """
    snapshot_dir = Path(snapshot_dir)
    manifest_path, progress_path = snapshot_dir / MANIFEST_NAME, snapshot_dir / PROGRESS_NAME
    if manifest_path.exists():
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {
            "dataset_id": m["dataset_id"],
            "source_url": m["source_page_url"],
            "api_endpoint": m["download_method"]["endpoint"],
            "snapshot": snapshot_dir.name,
            "retrieval_started_utc": m["started_at"],
            "retrieval_completed_utc": m["completed_at"],
            "source_rows_updated_at": m["source_version"]["rows_updated_at_after"],
            "source_view_last_modified": m["source_version"]["view_last_modified"],
            "source_truth_last_modified": m["source_version"]["truth_last_modified_values"],
            "row_count": m["row_count"],
            "server_row_count": m["server_stats_after"]["row_count"],
            "column_count": m["column_count"],
            "earliest_crash_date": m["coverage"]["min_crash_date"],
            "latest_crash_date": m["coverage"]["max_crash_date"],
            "combined_sha256": m["combined_sha256"],
            "part_sha256": {p["file"]: p["sha256"] for p in m["parts"]},
            # Eski manifestlerde alan yoksa: satır sayısı sunucu sayımıyla eşleşiyorsa tam.
            "acquisition_status": m.get("acquisition_status")
            or ("full" if m["row_count"] == m["server_stats_after"]["row_count"] else "unverified"),
            "warnings": m["warnings"],
        }
    if progress_path.exists():
        p = json.loads(progress_path.read_text(encoding="utf-8"))
        return {
            "dataset_id": config.DATASET_ID,
            "source_url": config.DATASET_PAGE_URL,
            "snapshot": snapshot_dir.name,
            "retrieval_started_utc": p["started_at"],
            "source_rows_updated_at": p["metadata_before"]["rows_updated_at"],
            "row_count": sum(part["rows"] for part in p["parts"]),
            "server_row_count": p["server_stats_before"]["row_count"],
            "column_count": len(p["metadata_before"]["columns"]),
            "part_sha256": {part["file"]: part["sha256"] for part in p["parts"]},
            "acquisition_status": "partial",
            "note": "İndirme tamamlanmadı; 'saferoute download --resume' ile sürdürülebilir. "
                    "Bu kısmi veri tüm veri setini temsil etmez.",
        }
    raise FileNotFoundError(f"{snapshot_dir} içinde manifest veya ilerleme dosyası yok.")


def write_record(record: dict[str, Any], name: str, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir or config.METADATA_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
