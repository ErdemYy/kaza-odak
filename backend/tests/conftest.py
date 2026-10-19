"""Testler için ağ gerektirmeyen sahte Socrata oturumu ve küçük, bilinen içerikli veri."""

from __future__ import annotations

import io
import json
from typing import Any

import pandas as pd
import pyarrow as pa
import pytest
import requests

from saferoute import config

FIELDS = [
    "crash_date", "crash_time", "borough", "zip_code", "latitude", "longitude", "location",
    "on_street_name", "off_street_name", "cross_street_name",
    "number_of_persons_injured", "number_of_persons_killed",
    "number_of_pedestrians_injured", "number_of_pedestrians_killed",
    "number_of_cyclist_injured", "number_of_cyclist_killed",
    "number_of_motorist_injured", "number_of_motorist_killed",
    "contributing_factor_vehicle_1", "contributing_factor_vehicle_2", "contributing_factor_vehicle_3",
    "contributing_factor_vehicle_4", "contributing_factor_vehicle_5",
    "collision_id", "vehicle_type_code1", "vehicle_type_code2", "vehicle_type_code_3",
    "vehicle_type_code_4", "vehicle_type_code_5",
]
CASUALTY = [f for f in FIELDS if f.startswith("number_of_")]
TRUTH = "Mon, 15 Jun 2026 23:05:52 GMT"


def make_row(**values: str | None) -> dict[str, str | None]:
    row: dict[str, str | None] = {f: None for f in FIELDS}
    for f in CASUALTY:
        row[f] = "0"
    row.update(values)
    return row


def d(day: str) -> str:
    return f"{day}T00:00:00.000"


def sample_rows() -> list[dict[str, str | None]]:
    """Her kalite sorununu bilinen sayıda içeren 7 satırlık örnek (beklenen değerler testlerde)."""
    r1 = make_row(
        crash_date=d("2020-01-01"), crash_time="10:40", borough="MANHATTAN", zip_code="10013",
        latitude="40.7208537", longitude="-74.0039287", location="(40.7208537, -74.0039287)",
        on_street_name="CANAL STREET", number_of_persons_injured="1", number_of_pedestrians_injured="1",
        contributing_factor_vehicle_1="Driver Inattention/Distraction", collision_id="1",
        vehicle_type_code1="Sedan", vehicle_type_code2="Bike",
    )
    r2 = make_row(
        crash_date=d("2020-02-01"), crash_time="0:00", borough="BROOKLYN", location="(40.7, -73.9)",
        contributing_factor_vehicle_1="Unspecified", collision_id="2", vehicle_type_code1="SEDAN ",
    )
    r3 = make_row(
        crash_date=d("2021-05-05"), crash_time="25:00", latitude="0", longitude="0",
        number_of_cyclist_injured="-1", collision_id="3",
    )
    r4 = make_row(
        crash_date=d("2021-06-01"), crash_time="23:59", borough="QUEENS", latitude="41.5", longitude="-73.9",
        number_of_persons_injured="2", number_of_motorist_injured="1", collision_id="3", vehicle_type_code1="Taxi",
    )
    r5 = make_row(
        crash_date="bad", borough="   ", latitude="abc", longitude="-73.9",
        number_of_persons_injured="x", collision_id="5",
    )
    r6 = dict(r1)
    r7 = make_row(
        crash_date=d("2022-03-04"), crash_time="7:05", zip_code="1001", latitude="40.75", longitude="-73.85",
        on_street_name="  MAIN ST  ", number_of_persons_killed="1", number_of_motorist_killed="1",
        collision_id="7.5",
    )
    return [r1, r2, r3, r4, r5, r6, r7]


def to_frame(rows: list[dict[str, str | None]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=FIELDS).astype(pd.ArrowDtype(pa.string()))


def csv_text(rows: list[dict[str, str | None]], fields: list[str] = FIELDS) -> str:
    """Socrata biçiminde CSV: dolu alanlar tırnaklı, boş (null) alanlar tırnaksız."""
    def cell(v: str | None) -> str:
        return "" if v is None else '"' + v.replace('"', '""') + '"'

    lines = [",".join(f'"{f}"' for f in fields)]
    lines += [",".join(cell(r.get(f)) for f in fields) for r in rows]
    return "\n".join(lines) + "\n"


class FakeResponse:
    def __init__(self, status: int = 200, body: bytes = b"", json_data: Any = None,
                 headers: dict[str, str] | None = None, break_after: int | None = None):
        self.status_code = status
        self._body = body
        self._json = json_data
        self.headers = headers or {}
        self._break_after = break_after

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error", response=self)

    def iter_content(self, chunk_size: int = 1024):
        stream = io.BytesIO(self._body)
        sent = 0
        while chunk := stream.read(16):
            if self._break_after is not None and sent >= self._break_after:
                raise requests.exceptions.ChunkedEncodingError("bağlantı koptu")
            sent += len(chunk)
            yield chunk


class FakeSession:
    """Sahte SODA sunucusu. ``failures`` listesi sıradaki CSV isteklerinin nasıl başarısız olacağını belirler:
    ``None`` (başarılı), ``503`` gibi bir tamsayı (HTTP durumu), ``"conn"`` (bağlantı hatası) veya
    ``"truncate"`` (akış kopması)."""

    def __init__(self, rows, failures=None, truth=TRUTH, server_count=None, fields=None, csv_fields=None):
        self.rows = rows
        self.failures = list(failures or [])
        self.truth = truth
        self.server_count = server_count
        self.fields = fields or FIELDS
        self.csv_fields = csv_fields or self.fields
        self.csv_calls: list[dict[str, Any]] = []
        self.headers: dict[str, str] = {}

    def get(self, url, params=None, timeout=None, stream=False):
        headers = {"X-SODA2-Truth-Last-Modified": self.truth}
        if url == config.METADATA_URL:
            return FakeResponse(json_data={
                "id": config.DATASET_ID, "name": "Motor Vehicle Collisions - Crashes",
                "rowsUpdatedAt": 1781564747, "viewLastModified": 1785531578,
                "columns": [{"fieldName": f, "dataTypeName": "text", "name": f} for f in self.fields],
            })
        if url == config.RESOURCE_JSON_URL:
            count = self.server_count if self.server_count is not None else len(self.rows)
            return FakeResponse(json_data=[{"row_count": str(count), "min_date": d("2020-01-01"),
                                            "max_date": d("2022-03-04")}], headers=headers)
        if url == config.RESOURCE_CSV_URL:
            self.csv_calls.append(dict(params))
            offset, limit = int(params["$offset"]), int(params["$limit"])
            body = csv_text(self.rows[offset:offset + limit], self.csv_fields).encode("utf-8")
            failure = self.failures.pop(0) if self.failures else None
            if failure is not None:
                if failure == "conn":
                    raise requests.ConnectionError("ağ hatası")
                if failure == "truncate":
                    return FakeResponse(body=body, headers=headers, break_after=32)
                return FakeResponse(status=failure, headers=headers)
            return FakeResponse(body=body, headers=headers)
        raise AssertionError(f"beklenmeyen URL: {url}")


@pytest.fixture
def rows():
    return sample_rows()


@pytest.fixture
def frame(rows):
    return to_frame(rows)


def read_manifest(snapshot_dir) -> dict[str, Any]:
    return json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
