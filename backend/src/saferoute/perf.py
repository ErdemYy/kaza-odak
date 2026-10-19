"""Basit performans ölçümü: süre ve süreç bellek tepe değeri (platformlar arası)."""

from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from typing import Iterator


def peak_memory_mb() -> float | None:
    """Sürecin şimdiye kadarki en yüksek fiziksel bellek kullanımı (MB). Ölçülemezse None.

    Windows'ta PeakWorkingSetSize, Unix'te ru_maxrss kullanılır. Arrow/NumPy
    arabellekleri dahil tüm süreç belleğini kapsar.
    """
    try:
        if sys.platform == "win32":
            import ctypes
            import ctypes.wintypes as wt

            class _PMC(ctypes.Structure):
                _fields_ = [
                    ("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            pmc = _PMC()
            pmc.cb = ctypes.sizeof(pmc)
            k32 = ctypes.windll.kernel32
            k32.GetCurrentProcess.restype = wt.HANDLE
            k32.K32GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD]
            if not k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
                return None
            return round(pmc.PeakWorkingSetSize / 2**20, 1)
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(rss / 2**20 if sys.platform == "darwin" else rss / 2**10, 1)
    except Exception:  # ölçüm yan bilgidir; asla hattı durdurmamalı
        return None


class StepTimer:
    """Adım adım süre ve o ana kadarki bellek tepe değerini kaydeder."""

    def __init__(self) -> None:
        self.steps: list[dict[str, float | str | None]] = []

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        t0 = time.perf_counter()
        yield
        self.steps.append({
            "step": name,
            "seconds": round(time.perf_counter() - t0, 2),
            "peak_memory_mb_so_far": peak_memory_mb(),
        })
