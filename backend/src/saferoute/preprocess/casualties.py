"""Yaralanma/ölüm alanlarının kalite kontrolü ve bayrakları.

Ham sayılar ASLA yeniden hesaplanıp üzerine yazılmaz. Tutarsızlıklar bayrakla
işaretlenir; kümeleme sonrası profil çıkarımında hangi alanın kullanılacağı belgelenir.

Kalite bayrağı değerleri (öncelik sırasıyla):
  negative_value       herhangi bir alan negatif
  total_missing        kişi toplamı boş
  component_missing    yaya/bisikletli/motorlu alt alanlarından biri boş
  total_lt_components  kişi toplamı < alt alanların toplamı
  total_gt_components  kişi toplamı > alt alanların toplamı
  ok                   tutarlı
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

FLAG_VALUES = ("negative_value", "total_missing", "component_missing",
               "total_lt_components", "total_gt_components", "ok")
COMPONENTS = ("pedestrians", "cyclist", "motorist")


def _arr(s: pd.Series) -> np.ndarray:
    return s.astype("Float64").to_numpy(dtype="float64", na_value=np.nan)


def quality_flag(total: np.ndarray, parts: list[np.ndarray]) -> np.ndarray:
    comp = np.vstack(parts)
    comp_sum = comp.sum(axis=0)
    negative = (total < 0) | (comp < 0).any(axis=0)
    flag = np.full(len(total), "ok", dtype=object)
    flag[total > comp_sum] = "total_gt_components"
    flag[total < comp_sum] = "total_lt_components"
    flag[np.isnan(comp).any(axis=0)] = "component_missing"
    flag[np.isnan(total)] = "total_missing"
    flag[negative] = "negative_value"
    return flag


def add_casualty_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for kind, prefix in (("injured", "injury"), ("killed", "fatality")):
        total = _arr(df[f"number_of_persons_{kind}"])
        parts = [_arr(df[f"number_of_{c}_{kind}"]) for c in COMPONENTS]
        out[f"{prefix}_data_quality_flag"] = pd.Categorical(quality_flag(total, parts), categories=FLAG_VALUES)
        comp_sum = np.nansum(np.vstack(parts), axis=0)
        # Bildirilmiş en az bir yaralı/ölü: toplam alanı VEYA herhangi bir alt alan > 0.
        out[f"has_reported_{prefix}"] = (np.nan_to_num(total) > 0) | (comp_sum > 0)
        out[f"{prefix}_component_sum"] = pd.array(np.where(np.isnan(np.vstack(parts)).all(axis=0), np.nan, comp_sum),
                                                  dtype="Float64").astype("Int32")
    return out


def casualty_summary(df: pd.DataFrame, flags: pd.DataFrame) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for kind, prefix in (("injured", "injury"), ("killed", "fatality")):
        total = _arr(df[f"number_of_persons_{kind}"])
        comp = _arr(flags[f"{prefix}_component_sum"])
        diff = total - comp
        both = ~np.isnan(diff)
        out[prefix] = {
            "flag_counts": {k: int(v) for k, v in flags[f"{prefix}_data_quality_flag"].value_counts()
                            .reindex(FLAG_VALUES, fill_value=0).items()},
            "has_reported": int(flags[f"has_reported_{prefix}"].sum()),
            "total_field_positive": int((np.nan_to_num(total) > 0).sum()),
            "difference_distribution": {str(int(k)): int(v) for k, v in
                                        pd.Series(diff[both & (diff != 0)]).value_counts().sort_index().items()},
            "sum_total_field": int(np.nansum(total)),
            "sum_components": int(np.nansum(comp)),
        }
    return out
