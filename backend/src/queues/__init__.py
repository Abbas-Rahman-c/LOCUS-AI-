"""
queues package - pgmq workers and producers.

Renamed from ``queue`` to avoid shadowing Python's stdlib ``queue`` module
when ``src/`` is on PYTHONPATH (caused startup failures under uvicorn).
"""
