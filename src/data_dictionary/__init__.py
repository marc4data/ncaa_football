"""CFBD data dictionary — what each endpoint represents and what every field means.

CFBD's OpenAPI spec is complete on structure and almost silent on meaning: it carries a
description for four of its 1,017 response fields, and it states the grain of an endpoint
nowhere at all. This package closes that gap from three directions — the spec for structure,
CFBD's published glossary for the metrics it does define, and the landed corpus in `data/raw`
for everything measurable — and labels every definition with which of those it came from.

    definitions.py  the field definition map (data in definitions.json) and the provenance rule
    spec.py         flatten the OpenAPI document into endpoint / field / parameter rows
    profile.py      measure the landed raw files: grain, null rates, value domains
    workbook.py     render it all as xlsx
    __main__.py     the CLI that wires them together

Run it with:

    python -m src.data_dictionary --spec data/api-docs.json
"""
from .definitions import CANON, GLOSSARY, GLOSSARY_FIELDS, PATTERNS, define

__all__ = ["define", "GLOSSARY", "GLOSSARY_FIELDS", "CANON", "PATTERNS"]
