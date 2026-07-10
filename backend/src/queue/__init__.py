"""
Queue package (pgmq workers/producers).

This package name shadows the stdlib ``queue`` module when ``src`` is on
PYTHONPATH. Re-export stdlib queue APIs so libraries like asyncpg /
concurrent.futures still work when they ``import queue``.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_STDLIB_ALIAS = "_locus_stdlib_queue"

if _STDLIB_ALIAS not in sys.modules:
    _stdlib_path = Path(sys.base_prefix) / "Lib" / "queue.py"
    if not _stdlib_path.exists():
        import os

        _stdlib_path = Path(os.__file__).resolve().parent / "queue.py"
    _spec = importlib.util.spec_from_file_location(_STDLIB_ALIAS, _stdlib_path)
    assert _spec is not None and _spec.loader is not None
    _stdlib = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_stdlib)
    sys.modules[_STDLIB_ALIAS] = _stdlib
else:
    _stdlib = sys.modules[_STDLIB_ALIAS]

# Public stdlib surface expected by the ecosystem
Empty = _stdlib.Empty
Full = _stdlib.Full
Queue = _stdlib.Queue
PriorityQueue = _stdlib.PriorityQueue
LifoQueue = _stdlib.LifoQueue
SimpleQueue = _stdlib.SimpleQueue
deque = getattr(_stdlib, "deque", None)  # not always present; keep if available

__all__ = [
    "Empty",
    "Full",
    "Queue",
    "PriorityQueue",
    "LifoQueue",
    "SimpleQueue",
]
