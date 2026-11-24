"""Deterministic planning engine: BOM explosion, availability, allocation, substitution, time-phased MRP,
supplier evaluation, item-master duplicates and obsolescence (docs/UNIVERSAL_SCENARIO_ENGINE_ARCHITECTURE.md).

Pure functions over the dataclasses in `model.py`: no I/O, no clocks (the planning date is an input), `Decimal`
for every quantity and amount. Data reaches it through `loader.py`, which reads the canonical datasets through the
query engine, so tenant isolation, warehouse scope and cost permissions apply before anything is calculated.
Every result carries the issues it found and the reasoning behind it; nothing is executed in a source system.
"""
