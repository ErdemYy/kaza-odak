"""Faz 2 işlem yapılandırması.

Yapılandırma her çıktı dosyasının yan kaydına (sidecar) yazılır ve SHA-256 özeti
alınır; aynı kaynak + aynı yapılandırma aynı çıktıyı üretir.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

# Faz 2 mantığı değiştiğinde artırılır; yan kayıtlarda saklanır.
PIPELINE_VERSION = "2.1.1"


@dataclass(frozen=True)
class PreprocessConfig:
    # Resmî poligon dışında olup bu mesafeden (metre) yakın noktalar "kıyıya yakın" sayılır
    # (köprüler, kıyı yolları, su üstü geokodlama sapmaları). İlçe ATANMAZ.
    # 500 m: gerçek veride poligon dışı mesafe dağılımında 500–1000 m arası boştur
    # (doğal kırılma). Bu eşik, köprü ve kıyı yolu gibi poligon dışı ama kara bağlantılı
    # konumları kapsamayı amaçlar; uzak noktalar (km'ler) dışarıda kalır.
    nearshore_buffer_m: float = 500.0
    # Kıyıya yakın noktalar mekânsal kümelemeye alınsın mı?
    clustering_include_nearshore: bool = True
    # Kesin 00:00 saatleri şüpheli olarak işaretlenir (silinmez, değiştirilmez).
    midnight_suspect_hour: int = 0
    midnight_suspect_minute: int = 0
    # Gün dilimi sınırları (başlangıç saati -> etiket); yarı açık aralıklar.
    time_periods: tuple[tuple[int, str], ...] = (
        (0, "night"), (6, "morning"), (12, "afternoon"), (18, "evening"),
    )
    # Metrik projeksiyon (K-Means ve kıyı mesafesi için).
    projected_crs: str = "EPSG:32618"
    geographic_crs: str = "EPSG:4326"
    # Haversine için yerküre ortalama yarıçapı (IUGG), metre.
    earth_radius_m: float = 6_371_008.8
    # Raporlama: en çok tekrarlanan kaç konum listelensin.
    top_repeated_locations: int = 25
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)

    def sha256(self) -> str:
        payload = json.dumps({"version": PIPELINE_VERSION, **self.as_dict()}, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
