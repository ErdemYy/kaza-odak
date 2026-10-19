"""Ham anlık görüntüyü bütünlük doğrulamasıyla belleğe yükler.

Tüm sütunlar ham metin olarak okunur: tür dönüşümü ve geçersiz değer tespiti EDA ve
ön işleme adımlarının açık sorumluluğudur. Yalnızca gerçekten boş alanlar eksik (null)
sayılır; "NA", "NULL" gibi metinler veri olarak korunur.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from saferoute import config
from saferoute.data.download import MANIFEST_NAME, file_sha256


class IntegrityError(RuntimeError):
    """Ham dosyalar manifest'teki sağlama toplamlarıyla uyuşmadığında fırlatılır."""


def latest_snapshot(raw_root: Path | None = None) -> Path:
    """Manifest'i olan en yeni tamamlanmış anlık görüntü dizinini döndürür."""
    base = Path(raw_root or config.RAW_DIR) / config.DATASET_ID
    candidates = sorted(p.parent for p in base.glob(f"snapshot_*/{MANIFEST_NAME}"))
    if not candidates:
        raise FileNotFoundError(f"{base} altında tamamlanmış anlık görüntü yok. Önce 'saferoute download' çalıştırın.")
    return candidates[-1]


def read_manifest(snapshot_dir: Path) -> dict[str, Any]:
    return json.loads((Path(snapshot_dir) / MANIFEST_NAME).read_text(encoding="utf-8"))


def verify_snapshot(snapshot_dir: Path) -> dict[str, Any]:
    """Her parçanın SHA-256 değerini manifest'e göre doğrular; uyuşmazlıkta hata fırlatır."""
    manifest = read_manifest(snapshot_dir)
    for part in manifest["parts"]:
        actual = file_sha256(Path(snapshot_dir) / part["file"])
        if actual != part["sha256"]:
            raise IntegrityError(f"{part['file']}: beklenen {part['sha256']}, bulunan {actual}")
    return manifest


def load_raw(snapshot_dir: Path, verify: bool = True, columns: list[str] | None = None) -> pd.DataFrame:
    """Anlık görüntünün tüm parçalarını metin sütunlu tek bir DataFrame olarak yükler."""
    return read_raw_table(snapshot_dir, verify, columns).to_pandas(types_mapper=pd.ArrowDtype)


def load_parquet(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    """``saferoute parquet`` ile üretilmiş kayıpsız Parquet kopyasını yükler."""
    return pq.read_table(path, columns=columns).to_pandas(types_mapper=pd.ArrowDtype)


def read_raw_table(snapshot_dir: Path, verify: bool = True, columns: list[str] | None = None) -> pa.Table:
    """Anlık görüntüyü tek bir Arrow tablosu olarak okur (pandas kopyası oluşturmadan)."""
    snapshot_dir = Path(snapshot_dir)
    manifest = verify_snapshot(snapshot_dir) if verify else read_manifest(snapshot_dir)
    field_names = [c["field_name"] for c in manifest["columns"]]
    convert = pacsv.ConvertOptions(
        column_types={name: pa.string() for name in field_names},
        null_values=[""],
        strings_can_be_null=True,
        include_columns=columns,
    )
    parse = pacsv.ParseOptions(newlines_in_values=True)
    tables = [
        pacsv.read_csv(snapshot_dir / part["file"], parse_options=parse, convert_options=convert)
        for part in manifest["parts"]
    ]
    table = pa.concat_tables(tables)
    if table.num_rows != manifest["row_count"]:
        raise IntegrityError(f"Okunan satır ({table.num_rows}) manifest ile ({manifest['row_count']}) uyuşmuyor.")
    return table
