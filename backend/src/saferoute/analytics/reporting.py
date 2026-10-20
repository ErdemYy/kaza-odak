"""Analiz raporu: tek bir belge modeli, üç çıktı biçimi (JSON, Markdown özet, CSV tablo).

Belge şeması (``saferoute.report/1``) Faz 6–7'de yeni bölüm türleriyle genişletilebilir: her bölüm
``{"id", "title", "kind": "facts"|"table"|"text"|"list", ...}`` biçimindedir; işleyiciler bilinmeyen
bölüm türlerini atlamaz, ham JSON olarak yazar.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
from dataclasses import dataclass, field
from typing import Any

REPORT_SCHEMA = "saferoute.report/1"

GENERAL_LIMITATIONS = [
    "Kümeleme denetimsizdir; 'doğruluk' ölçülmez. Kaza yoğunluğu, araç/yaya başına risk anlamına gelmez "
    "(trafik hacmi verisi yoktur).",
    "Veri NYPD tarafından bildirilen kazalardır; bildirilmeyen kazalar ve geokodlama hataları sonuçları etkiler.",
    "00:00 saatli kayıtların bir kısmı saati bilinmeyen kayıtların gece yarısına yuvarlanmış olabilir "
    "(Faz 2 bayrağı: midnight_suspect_flag).",
    "Etken (contributing factor) metinleri kaynak veri setindeki İngilizce NYPD kodlarıdır ve 'kaydedilmiş' "
    "etkenlerdir; nedensellik kanıtı değildir.",
]


@dataclass
class ReportDocument:
    kind: str
    title: str
    source: dict[str, Any]
    data_version: str | None
    algorithm: dict[str, Any] | None = None
    filters: list[str] = field(default_factory=list)
    n_records: int | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)
    table: list[dict[str, Any]] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return {"schema": REPORT_SCHEMA, "kind": self.kind, "title": self.title, "generated_at": self.generated_at,
                "source": self.source, "data_version": self.data_version, "algorithm": self.algorithm,
                "filters": self.filters, "n_records": self.n_records, "metrics": self.metrics,
                "limitations": [*self.limitations, *GENERAL_LIMITATIONS], "sections": self.sections,
                "table": self.table}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=_jsonable)

    def to_csv(self) -> str:
        buf = io.StringIO()
        rows = self.table
        if not rows:
            buf.write("bilgi\nTablo yok\n")
            return buf.getvalue()
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in r.items()})
        return buf.getvalue()

    def to_markdown(self) -> str:
        d = self.to_dict()
        L = [f"# {self.title}", "", f"> Oluşturulma: {self.generated_at} · Şema `{REPORT_SCHEMA}` · Veri sürümü "
             f"`{self.data_version or '—'}`", ""]
        src = self.source
        L += ["## Veri kaynağı", "",
              f"- Veri seti: {src.get('dataset_name') or '—'} (`{src.get('dataset_id')}`) — {src.get('source_url')}",
              f"- Anlık görüntü: `{src.get('snapshot')}`; kaynak satır güncellemesi: {src.get('rows_updated_at') or '—'}",
              f"- Güncellik (kontrol anında): {src.get('verdict') or '—'}", ""]
        if self.algorithm:
            a = self.algorithm
            L += ["## Algoritma ve parametreler", "", f"- Algoritma: **{a.get('name')}**",
                  f"- Parametreler: `{json.dumps(a.get('parameters'), ensure_ascii=False)}`",
                  f"- Öznitelikler: {a.get('features') or '—'}", f"- Mesafe metriği: {a.get('metric') or '—'}",
                  f"- Kapsam: {a.get('scope') or '—'}", f"- Kimlik: `{a.get('id') or '—'}`",
                  f"- Yazılım / sürüm: {a.get('software') or '—'}", ""]
        L += ["## Filtreler", "", *[f"- {f}" for f in (self.filters or ["Filtre yok"])], "",
              f"**Kullanılan kayıt sayısı:** {_fmt(self.n_records)}", ""]
        if self.metrics:
            L += ["## Değerlendirme metrikleri", "", "| Metrik | Değer |", "|---|---|"]
            L += [f"| {k} | {_fmt(v)} |" for k, v in self.metrics.items()]
            L.append("")
        for s in self.sections:
            L += [f"## {s['title']}", ""]
            kind = s.get("kind")
            if kind == "facts":
                L += [f"- {k}: {_fmt(v)}" for k, v in s.get("items", {}).items()]
            elif kind == "list":
                L += [f"- {x}" for x in s.get("items", [])]
            elif kind == "text":
                L.append(str(s.get("text", "")))
            elif kind == "table" and s.get("rows"):
                cols = list(s["rows"][0].keys())
                L += ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
                L += ["| " + " | ".join(_fmt(r.get(c)) for c in cols) + " |" for r in s["rows"]]
            else:
                L.append("```json\n" + json.dumps(s, ensure_ascii=False, default=_jsonable) + "\n```")
            L.append("")
        L += ["## Sınırlılıklar", "", *[f"- {x}" for x in d["limitations"]], ""]
        return "\n".join(L)


def _jsonable(v: Any) -> Any:
    if hasattr(v, "item"):
        return v.item()
    return str(v)


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "evet" if v else "hayır"
    if isinstance(v, int):
        return f"{v:,}".replace(",", ".")
    if isinstance(v, float):
        return f"{v:.4f}".replace(".", ",")
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False, default=_jsonable)
    return str(v)


def render(doc: ReportDocument, fmt: str) -> tuple[str, str, str]:
    """(gövde, MIME türü, dosya uzantısı)."""
    if fmt == "json":
        return doc.to_json(), "application/json; charset=utf-8", "json"
    if fmt == "csv":
        return "﻿" + doc.to_csv(), "text/csv; charset=utf-8", "csv"  # BOM: Excel'de Türkçe karakterler
    if fmt in ("md", "markdown"):
        return doc.to_markdown(), "text/markdown; charset=utf-8", "md"
    raise ValueError("Biçim json, csv veya md olmalı")
