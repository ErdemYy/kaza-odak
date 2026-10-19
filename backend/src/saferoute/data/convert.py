"""Ham CSV anlık görüntüsünün kayıpsız Parquet kopyası.

Kopya, ham veriyle birebir aynı içeriği taşır: tüm sütunlar metin, yalnızca boş alanlar
null. Tür dönüşümü burada YAPILMAZ (Faz 2'nin konusu); amaç tekrar tekrar CSV
ayrıştırmadan hızlı ve sütun-seçmeli okuma sağlamaktır. Ham veri yerinde kalır.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from saferoute import config
from saferoute.data.download import file_sha256
from saferoute.data.loader import read_manifest, read_raw_table

PARQUET_NAME = "crashes_raw_text.parquet"
SIDECAR_NAME = "crashes_raw_text.parquet.json"


def snapshot_to_parquet(snapshot_dir: Path, out_root: Path | None = None, force: bool = False) -> Path:
    """Doğrulanmış anlık görüntüyü ``data/interim/<dataset>/<snapshot>/`` altına Parquet olarak yazar.

    Aynı kaynak sağlama toplamından üretilmiş geçerli bir kopya varsa yeniden yazmaz.
    """
    snapshot_dir = Path(snapshot_dir)
    manifest = read_manifest(snapshot_dir)
    out_dir = Path(out_root or config.INTERIM_DIR) / manifest["dataset_id"] / snapshot_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)
    target, sidecar = out_dir / PARQUET_NAME, out_dir / SIDECAR_NAME

    if not force and target.exists() and sidecar.exists():
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        if meta["source_combined_sha256"] == manifest["combined_sha256"] and file_sha256(target) == meta["sha256"]:
            return target

    table = read_raw_table(snapshot_dir, verify=True)
    tmp = target.with_name(target.name + ".tmp")
    pq.write_table(table, tmp, compression="zstd")
    os.replace(tmp, target)

    check = pq.read_metadata(target)
    if check.num_rows != manifest["row_count"]:
        raise RuntimeError(f"Parquet satır sayısı ({check.num_rows}) manifest ile uyuşmuyor.")

    meta: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_snapshot": snapshot_dir.name,
        "source_combined_sha256": manifest["combined_sha256"],
        "row_count": check.num_rows,
        "column_count": check.num_columns,
        "schema": "tüm sütunlar string (kayıpsız ham kopya); yalnızca boş CSV alanları null",
        "compression": "zstd",
        "bytes": target.stat().st_size,
        "sha256": file_sha256(target),
    }
    sidecar.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return target
