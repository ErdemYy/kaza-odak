"""Çalışan süreç koruması.

* **Windows Job Object:** her laboratuvar çalışanı ayrı bir iş nesnesine bağlanır.
  ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`` — API süreci beklenmedik biçimde ölse bile (görev yöneticisinden
  sonlandırma, çökme) işletim sistemi tutamacı kapatır ve çalışanı da sonlandırır: yetim Python süreci kalmaz.
  ``JOB_OBJECT_LIMIT_PROCESS_MEMORY`` — çalışanın ayırabileceği bellek (commit) için sert tavan; aşılırsa
  ayırma başarısız olur (Python ``MemoryError``) ve sistemin geri kalanı belleğe boğulmaz.
* **Süreç ağacı sonlandırma ve doğrulama** (psutil): iptalde çalışan ve olası alt süreçleri sonlandırılır,
  ardından gerçekten bittikleri denetlenir.
* **Kimlik doğrulamalı yetim temizliği:** yeniden başlatmada yalnızca kayıttaki PID + oluşturulma zamanı +
  komut satırı eşleşen süreç sonlandırılır; başka projelerin süreçlerine dokunulmaz.

Windows dışında iş nesnesi yoktur (yalnızca psutil tabanlı izleme ve temizlik çalışır).
"""

from __future__ import annotations

import sys
from typing import Any

try:
    import psutil
except ImportError:  # pragma: no cover - psutil api ekinin bağımlılığıdır
    psutil = None  # type: ignore[assignment]

JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9


def _win_structs():
    import ctypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32), ("SchedulingClass", ctypes.c_uint32)]

    class EXTENDED(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO_COUNTERS), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    return EXTENDED


class WorkerGuard:
    """Bir çalışan sürecine bağlı iş nesnesi (Windows). Başka platformlarda yalnızca ``attached = False``."""

    def __init__(self, pid: int, memory_limit_mb: int | None):
        self.pid = pid
        self.memory_limit_mb = memory_limit_mb
        self.attached = False
        self.error: str | None = None
        self._handle = None
        if sys.platform != "win32":
            return
        try:
            self._attach_windows()
        except Exception as exc:  # koruma kurulamazsa iş yine çalışır; durum kaydedilir
            self.error = f"{type(exc).__name__}: {exc}"

    def _attach_windows(self) -> None:
        import ctypes
        import ctypes.wintypes as wt

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wt.HANDLE
        k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wt.LPCWSTR]
        k32.SetInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
        k32.OpenProcess.restype = wt.HANDLE
        k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        k32.AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]
        k32.CloseHandle.argtypes = [wt.HANDLE]
        EXTENDED = _win_structs()

        job = k32.CreateJobObjectW(None, None)
        if not job:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW")
        info = EXTENDED()
        flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if self.memory_limit_mb:
            flags |= JOB_OBJECT_LIMIT_PROCESS_MEMORY
            info.ProcessMemoryLimit = int(self.memory_limit_mb) * 2**20
        info.BasicLimitInformation.LimitFlags = flags
        if not k32.SetInformationJobObject(job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)):
            err = ctypes.get_last_error()
            k32.CloseHandle(job)
            raise OSError(err, "SetInformationJobObject")
        PROCESS_SET_QUOTA, PROCESS_TERMINATE = 0x0100, 0x0001
        hp = k32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, self.pid)
        if not hp:
            err = ctypes.get_last_error()
            k32.CloseHandle(job)
            raise OSError(err, "OpenProcess")
        ok = k32.AssignProcessToJobObject(job, hp)
        err = ctypes.get_last_error()
        k32.CloseHandle(hp)
        if not ok:
            k32.CloseHandle(job)
            raise OSError(err, "AssignProcessToJobObject")
        self._k32, self._handle, self.attached = k32, job, True

    def peak_commit_mb(self) -> float | None:
        """İş nesnesinin ölçtüğü en yüksek süreç belleği (commit, MB)."""
        if not self.attached:
            return None
        import ctypes

        EXTENDED = _win_structs()
        info = EXTENDED()
        self._k32.QueryInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
                                                        ctypes.c_uint32, ctypes.c_void_p]
        if not self._k32.QueryInformationJobObject(self._handle, JobObjectExtendedLimitInformation, ctypes.byref(info),
                                                   ctypes.sizeof(info), None):
            return None
        return round(info.PeakProcessMemoryUsed / 2**20, 1)

    def close(self) -> None:
        """Tutamacı kapatır. KILL_ON_JOB_CLOSE nedeniyle hâlâ çalışan bir süreç varsa sonlandırılır."""
        if self._handle:
            self._k32.CloseHandle(self._handle)
            self._handle = None

    def describe(self) -> dict[str, Any]:
        return {"job_object": self.attached, "kill_on_close": self.attached,
                "memory_limit_mb": self.memory_limit_mb if self.attached else None, "error": self.error}


# ---------------------------------------------------------------------- süreç yardımcıları
def create_time(pid: int) -> float | None:
    if psutil is None:
        return None
    try:
        return psutil.Process(pid).create_time()
    except psutil.Error:
        return None


class Sampler:
    """Çalışan sürecin CPU ve fiziksel bellek kullanımını örnekler (psutil)."""

    def __init__(self, pid: int):
        self.peak_rss_mb = 0.0
        self.cpu_samples: list[float] = []
        self.cpu_time_s: float | None = None
        self.n = 0
        self._p = None
        if psutil is not None:
            try:
                self._p = psutil.Process(pid)
                self._p.cpu_percent(None)
            except psutil.Error:
                self._p = None

    def sample(self) -> float | None:
        """Anlık RSS (MB) veya süreç yoksa None."""
        if self._p is None:
            return None
        try:
            with self._p.oneshot():
                rss = self._p.memory_info().rss / 2**20
                cpu = self._p.cpu_percent(None)
                t = self._p.cpu_times()
        except psutil.Error:
            return None
        self.n += 1
        self.peak_rss_mb = max(self.peak_rss_mb, rss)
        self.cpu_samples.append(cpu)
        self.cpu_time_s = t.user + t.system
        return rss

    def summary(self) -> dict[str, Any]:
        cs = self.cpu_samples[1:] or self.cpu_samples  # ilk örnek referans ölçümdür
        return {"samples": self.n, "peak_rss_mb": round(self.peak_rss_mb, 1) if self.n else None,
                "mean_cpu_percent": round(sum(cs) / len(cs), 1) if cs else None,
                "max_cpu_percent": round(max(cs), 1) if cs else None,
                "cpu_time_s": round(self.cpu_time_s, 2) if self.cpu_time_s is not None else None,
                "cpu_note": "% değeri tek çekirdeğe göredir (100 = bir çekirdek tam dolu)"}


def kill_tree(pid: int, timeout: float = 5.0) -> dict[str, Any]:
    """Süreci ve alt süreçlerini sonlandırır; gerçekten bittiklerini doğrular."""
    if psutil is None:
        return {"verified": False, "reason": "psutil yok"}
    try:
        root = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return {"verified": True, "killed": 0, "already_exited": True}
    try:
        procs = [*root.children(recursive=True), root]
    except psutil.NoSuchProcess:
        procs = [root]
    for p in procs:
        try:
            p.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(procs, timeout=timeout)
    for p in alive:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(alive, timeout=timeout)
    return {"verified": not alive, "killed": len(procs), "still_alive": [p.pid for p in alive]}


def is_our_worker(pid: int | None, created: float | None) -> bool:
    """PID hâlâ, kayıttaki laboratuvar çalışanı mı? (PID yeniden kullanımına karşı oluşturulma zamanı ve komut
    satırı birlikte denetlenir.)"""
    if psutil is None or not pid or created is None:
        return False
    try:
        p = psutil.Process(pid)
        if abs(p.create_time() - created) > 0.5:
            return False
        cmd = " ".join(p.cmdline()).lower()
    except psutil.Error:
        return False
    return "python" in cmd and "multiprocessing" in cmd
