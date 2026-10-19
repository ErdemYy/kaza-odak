"""Veri sözlüğü: her ham sütunun anlamı, öngörülen kullanımı ve notları.

Anlam ve kullanım bilgisi burada elle tanımlanır; tür, eksik sayısı ve oranı ise her
koşuda profil sonuçlarından ölçülerek tabloya yazılır (sayılar elle kopyalanmaz).

Kullanım sınıfları (docs/feature_candidates.md ile aynı):
  A = Coğrafi model özelliği        B = Zamansal model özelliği (deneysel)
  C = Yalnızca filtre               D = Betimleyici / sonuç alanı
  E = Kimlik veya model dışı
"""

from __future__ import annotations

from typing import Any

USAGE_LABELS = {
    "A": "A — Coğrafi model özelliği",
    "B": "B — Zamansal model özelliği (deneysel) + filtre",
    "C": "C — Yalnızca filtre",
    "D": "D — Betimleyici / sonuç",
    "E": "E — Kimlik / model dışı",
}

_FACTOR = ("Araç {i} için polisin kaydettiği katkıda bulunan faktör", "C",
           "Serbest olmayan sözlük; 'Unspecified' gerçek bir faktör değil, bilinmiyor anlamında ele alınmalı.")
_VEHICLE = ("Araç {i} türü", "C",
            "Çok dağınık adlandırma (ör. Sedan / 4 dr sedan / PASSENGER VEHICLE); Faz 2'de kategori eşlemesi gerekir.")

FIELD_INFO: dict[str, tuple[str, str, str]] = {
    "crash_date": ("Kaza tarihi", "B",
                   "Saat bileşeni her zaman 00:00; saat bilgisi crash_time'dadır. Tarih/yıl filtresi."),
    "crash_time": ("Kaza saati (H:MM)", "B",
                   "00:00 değerinde belirgin yığılma var; bilinmeyen saat yerine girilmiş olabilir."),
    "borough": ("Kayıtta bildirilen ilçe", "C",
                "Model özelliği değil (koordinattan türetilebilir, sızıntı/çift temsil). Geometrik ilçe Faz 2'de ayrı sütun olacak."),
    "zip_code": ("Posta kodu", "C",
                 "İlçe ile aynı oranda eksik; filtre/betimleme için, modele girmez."),
    "latitude": ("Enlem (WGS84)", "A", "0 ve NYC dışı değerler geçersiz sayılır; eksikler doldurulmaz."),
    "longitude": ("Boylam (WGS84)", "A", "0 ve NYC dışı değerler geçersiz sayılır; eksikler doldurulmaz."),
    "location": ("'(enlem, boylam)' metni", "E",
                 "latitude/longitude ile birebir aynı bilgi; tekrarlı coğrafi temsil olduğu için dışlanır."),
    "on_street_name": ("Kazanın olduğu cadde", "D",
                       "Serbest metin, doldurma boşlukları yaygın; küme betimlemesinde kullanılabilir."),
    "off_street_name": ("Kesişen/yakın cadde", "D", "Serbest metin; betimleme amaçlı."),
    "cross_street_name": ("Çapraz sokak / adres metni", "D", "Çoğunlukla boş; betimleme amaçlı."),
    "number_of_persons_injured": ("Yaralanan toplam kişi", "D",
                                  "Küme betimlemesi; alt kırılım toplamıyla tutarsız kayıtlar var."),
    "number_of_persons_killed": ("Ölen toplam kişi", "D", "Küme betimlemesi; nadir olay."),
    "number_of_pedestrians_injured": ("Yaralanan yaya", "D", "Küme betimlemesi."),
    "number_of_pedestrians_killed": ("Ölen yaya", "D", "Küme betimlemesi."),
    "number_of_cyclist_injured": ("Yaralanan bisikletli", "D", "Küme betimlemesi."),
    "number_of_cyclist_killed": ("Ölen bisikletli", "D", "Küme betimlemesi."),
    "number_of_motorist_injured": ("Yaralanan motorlu araç kullanıcısı", "D", "Küme betimlemesi."),
    "number_of_motorist_killed": ("Ölen motorlu araç kullanıcısı", "D", "Küme betimlemesi."),
    "collision_id": ("Kaza kimliği", "E", "Benzersiz kimlik; birleştirme/izlenebilirlik için tutulur, modele girmez."),
}
for _i in range(1, 6):
    FIELD_INFO[f"contributing_factor_vehicle_{_i}"] = (_FACTOR[0].format(i=_i), _FACTOR[1], _FACTOR[2])
FIELD_INFO["vehicle_type_code1"] = (_VEHICLE[0].format(i=1), _VEHICLE[1], _VEHICLE[2])
FIELD_INFO["vehicle_type_code2"] = (_VEHICLE[0].format(i=2), _VEHICLE[1], _VEHICLE[2])
for _i in range(3, 6):
    FIELD_INFO[f"vehicle_type_code_{_i}"] = (_VEHICLE[0].format(i=_i), _VEHICLE[1], _VEHICLE[2])


def _pct(x: float) -> str:
    if 0 < x < 0.005:  # sıfır olmayan küçük oran "%0,00" görünüp yanıltmasın
        return "<%0,01"
    return f"%{x:.2f}".replace(".", ",")


def _n(x: int) -> str:
    return f"{int(x):,}".replace(",", ".")


def render_data_dictionary(profile: dict[str, Any], snapshot_name: str) -> str:
    """Ölçülmüş profil değerleriyle veri sözlüğü Markdown'ı üretir."""
    overview = profile["column_overview"]
    total = profile["schema"]["row_count"]
    lines = [
        "# Veri Sözlüğü — Motor Vehicle Collisions - Crashes (`h9gi-nx95`)",
        "",
        f"> `saferoute eda` tarafından otomatik üretilmiştir. Anlık görüntü: `{snapshot_name}`, "
        f"{_n(total)} satır. Eksik = boş veya yalnızca boşluk içeren alan.",
        "",
        "Veri türü sütunu `kaynak türü → ölçülen tür` biçimindedir. Kaynak türü Socrata meta verisinden, "
        "ölçülen tür dolu değerlerin tamamına uyan en dar türden gelir.",
        "",
        "| Sütun | Anlam | Veri türü | Eksik | Eksik % | Benzersiz (dolu) | Öngörülen kullanım | Notlar |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for col, o in overview.items():
        meaning, usage, notes = FIELD_INFO.get(col, ("—", "E", "Sözlükte tanımsız sütun"))
        if o["candidate_identifier"]:
            notes += " Aday kimlik sütunu (tümü dolu ve benzersiz)."
        lines.append(
            f"| `{col}` | {meaning} | {o['source_type'] or '—'} → {o['inferred_type']} | {_n(o['missing'])} | "
            f"{_pct(o['missing_pct'])} | {_n(o['unique_non_missing'])} | {USAGE_LABELS[usage]} | {notes} |"
        )
    lines += ["", "Sınıf tanımları ve gerekçeler için bkz. `docs/feature_candidates.md`.", ""]
    return "\n".join(lines)
