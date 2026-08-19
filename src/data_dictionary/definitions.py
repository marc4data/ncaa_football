"""The field definition map, and the rule that picks a definition for a field.

The map itself lives in `definitions.json` — it is data, edited far more often than this
code, and keeping it out of Python means a definition change is a clean one-line diff that
does not need a lint pass.

Provenance is the point of this module. CFBD publishes a description for only four response
fields in the entire API, so almost every definition here is ours rather than theirs. Every
row the workbook emits therefore carries where its definition came from:

    glossary : CFBD's own published definition, verbatim. Authoritative.
    docs     : text CFBD publishes in the OpenAPI spec. Authoritative.
    spec     : structural fact from the schema — type, nullability, enum. Authoritative.
    observed : measured from the landed raw files. Factual about the sample profiled.
    inferred : ours. NOT sourced. Read the confidence before relying on it.

and inferred rows additionally carry a confidence:

    high   : standard term, one plausible meaning
    medium : meaning clear, but a detail — units, scope, filter — is unverified
    low    : genuinely ambiguous; confirm with CFBD or against the data before relying on it

Never promote an inferred definition to a sourced provenance because it "reads right". The
value of this file is that the reader can tell the two apart.
"""
import json
from pathlib import Path
from typing import Dict, List, Tuple

HIGH, MEDIUM, LOW = "high", "medium", "low"
CONFIDENCES = (HIGH, MEDIUM, LOW)

GLOSSARY_PROV = "glossary"
DOCS_PROV = "docs"
SPEC_PROV = "spec"
OBSERVED_PROV = "observed"
INFERRED_PROV = "inferred"
PROVENANCES = (GLOSSARY_PROV, DOCS_PROV, SPEC_PROV, OBSERVED_PROV, INFERRED_PROV)

DEFINITIONS_FILE = Path(__file__).with_name("definitions.json")

UNDEFINED = (
    "Not defined. No CFBD source describes this field and its name is not self-explanatory "
    "— confirm against the data or with CFBD before use."
)


def _load(path: Path = DEFINITIONS_FILE) -> dict:
    with path.open() as fh:
        return json.load(fh)


_MAP = _load()

GLOSSARY: Dict[str, str] = _MAP["glossary"]
GLOSSARY_FIELDS: Dict[str, str] = _MAP["glossary_fields"]
CANON: Dict[str, List] = _MAP["canon"]
PATTERNS: List[List[str]] = _MAP["patterns"]


def leaf_of(field_path: str) -> str:
    """The final segment of a dot-path, stripped of array markers and lowercased."""
    return field_path.split(".")[-1].replace("[]", "").lower()


def define(field_path: str, spec_description: str = "") -> Tuple[str, str, str]:
    """Return (definition, provenance, confidence) for one field.

    Order matters and is deliberate: anything CFBD actually published wins over anything we
    wrote. `spec_description` is CFBD's own text from the OpenAPI spec, so it comes first.
    """
    if spec_description:
        return spec_description, DOCS_PROV, ""

    leaf = leaf_of(field_path)

    term = GLOSSARY_FIELDS.get(leaf)
    if term:
        return f"{term} — {GLOSSARY[term]}", GLOSSARY_PROV, ""

    entry = CANON.get(leaf)
    if entry:
        return entry[0], INFERRED_PROV, entry[1]

    for pattern, definition, confidence in PATTERNS:
        if leaf.endswith(pattern) or leaf.startswith(pattern):
            return definition, INFERRED_PROV, confidence

    return UNDEFINED, INFERRED_PROV, LOW
