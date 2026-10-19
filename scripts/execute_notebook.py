"""Bir Jupyter defterini hücre sırasıyla çalıştırır ve çıktılarıyla yerinde kaydeder.

Kullanım (backend sanal ortamıyla):
    backend/.venv/Scripts/python.exe scripts/execute_notebook.py notebooks/01_dataset_exploration.ipynb

Herhangi bir hücre hata verirse sıfırdan farklı çıkış koduyla durur.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient


def main(path: str, timeout: int = 1800) -> int:
    if sys.platform == "win32":  # pyzmq, Windows'un varsayılan Proactor döngüsüyle uyarı verir
        import asyncio

        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    nb_path = Path(path).resolve()
    nb = nbformat.read(nb_path, as_version=4)
    t0 = time.perf_counter()
    NotebookClient(nb, timeout=timeout, kernel_name="python3",
                   resources={"metadata": {"path": str(nb_path.parent)}}).execute()
    nbformat.write(nb, nb_path)
    n = sum(1 for c in nb.cells if c.cell_type == "code")
    print(f"{nb_path.name}: {n} kod hücresi hatasız çalıştı ({time.perf_counter() - t0:.0f} sn)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "notebooks/01_dataset_exploration.ipynb"))
