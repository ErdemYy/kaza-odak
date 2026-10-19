"""Socrata (NYC Open Data) kaynağından meta veri ve sunucu tarafı istatistikleri okuma."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

from saferoute import config


def make_session() -> requests.Session:
    """Varsa SODA uygulama anahtarını başlığa ekleyen bir HTTP oturumu oluşturur."""
    session = requests.Session()
    session.headers["User-Agent"] = "SafeRoute3D/0.1 (academic research)"
    token = os.environ.get(config.SODA_APP_TOKEN_ENV)
    if token:
        session.headers["X-App-Token"] = token
    return session


def _epoch_to_iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()


def fetch_metadata(session: requests.Session, timeout: float = 60) -> dict[str, Any]:
    """Veri setinin yayıncı meta verisini (güncellenme zamanı, sütunlar, lisans) döndürür."""
    resp = session.get(config.METADATA_URL, timeout=timeout)
    resp.raise_for_status()
    m = resp.json()
    custom = (m.get("metadata") or {}).get("custom_fields") or {}
    return {
        "id": m.get("id"),
        "name": m.get("name"),
        "attribution": m.get("attribution"),
        "category": m.get("category"),
        "license": (m.get("license") or {}).get("name"),
        "rows_updated_at": _epoch_to_iso(m.get("rowsUpdatedAt")),
        "view_last_modified": _epoch_to_iso(m.get("viewLastModified")),
        "publication_date": _epoch_to_iso(m.get("publicationDate")),
        "update_frequency": (custom.get("Update") or {}).get("Update Frequency"),
        "columns": [
            {"field_name": c.get("fieldName"), "data_type": c.get("dataTypeName"), "name": c.get("name")}
            for c in m.get("columns", [])
            if not str(c.get("fieldName", "")).startswith(":")
        ],
    }


def fetch_server_stats(session: requests.Session, timeout: float = 120) -> dict[str, Any]:
    """Sunucu tarafında toplam kayıt sayısını ve tarih kapsamını sorgular (SoQL)."""
    params = {"$select": "count(*) AS row_count, min(crash_date) AS min_date, max(crash_date) AS max_date"}
    resp = session.get(config.RESOURCE_JSON_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    row = resp.json()[0]
    return {
        "row_count": int(row["row_count"]),
        "min_crash_date": row.get("min_date"),
        "max_crash_date": row.get("max_date"),
        "truth_last_modified": resp.headers.get("X-SODA2-Truth-Last-Modified"),
    }
