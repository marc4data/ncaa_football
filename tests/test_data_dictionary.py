"""Tests for the data dictionary.

The point of this artifact is that a reader can tell CFBD's word from ours. Most of what is
asserted here defends that property: provenance is never fabricated, the glossary is quoted
rather than paraphrased, and a field whose unit differs from a glossary term is not silently
given that term's definition.
"""
import json

import pytest

from src.data_dictionary import definitions as dfn
from src.data_dictionary.profile import candidate_keys, records_of, unique_combos
from src.data_dictionary.spec import Spec


# --------------------------------------------------------------------- the definition map
def test_definitions_json_is_wellformed():
    raw = json.loads(dfn.DEFINITIONS_FILE.read_text())
    assert set(raw) >= {"glossary", "glossary_fields", "canon", "patterns"}


def test_canon_keys_are_lowercase_and_unique():
    raw = json.loads(dfn.DEFINITIONS_FILE.read_text())
    keys = list(raw["canon"])
    assert keys == [k.lower() for k in keys]
    assert len(keys) == len(set(keys)), "duplicate key in canon"


def test_every_canon_entry_has_a_valid_confidence():
    for leaf, (definition, confidence) in dfn.CANON.items():
        assert definition.strip(), "{} has an empty definition".format(leaf)
        assert confidence in dfn.CONFIDENCES, "{} has confidence {!r}".format(leaf, confidence)


def test_glossary_field_map_resolves():
    """Every mapped field must point at a term that actually exists."""
    for leaf, term in dfn.GLOSSARY_FIELDS.items():
        assert term in dfn.GLOSSARY, "{} maps to unknown term {!r}".format(leaf, term)


def test_a_field_is_not_both_glossary_and_canon():
    """Ambiguity about which definition wins is how a wrong one ships."""
    overlap = set(dfn.GLOSSARY_FIELDS) & set(dfn.CANON)
    assert not overlap, "defined twice: {}".format(sorted(overlap))


@pytest.mark.parametrize("leaf", [
    "totalhavocevents", "dbhavocevents", "frontsevenhavocevents", "totalopportunies",
])
def test_count_fields_are_not_given_a_rate_definition(leaf):
    """These are event counts; the glossary terms they resemble are percentages.

    Mapping them straight onto the glossary would misstate the unit — a wrong definition that
    reads perfectly well, which is the kind this file exists to prevent.
    """
    assert leaf not in dfn.GLOSSARY_FIELDS
    definition, provenance, _ = dfn.define(leaf)
    assert provenance == dfn.INFERRED_PROV
    assert "not the rate" in definition or "Count of" in definition


def test_published_description_beats_our_own():
    definition, provenance, confidence = dfn.define("id", "CFBD's own words")
    assert (definition, provenance, confidence) == ("CFBD's own words", dfn.DOCS_PROV, "")


def test_glossary_definitions_are_quoted_verbatim():
    definition, provenance, _ = dfn.define("stuffRate")
    assert provenance == dfn.GLOSSARY_PROV
    assert dfn.GLOSSARY["Stuff Rate"] in definition


def test_unknown_field_is_marked_undefined_not_guessed():
    definition, provenance, confidence = dfn.define("zzzNotARealField")
    assert provenance == dfn.INFERRED_PROV
    assert confidence == dfn.LOW
    assert definition == dfn.UNDEFINED


def test_define_uses_the_leaf_of_a_dot_path():
    assert dfn.define("playoff.round")[0] == dfn.define("round")[0]
    assert dfn.define("teams[].school")[0] == dfn.define("school")[0]


# --------------------------------------------------------------------- spec flattening
def _spec():
    return Spec({
        "info": {"version": "test"},
        "paths": {
            "/things": {"get": {
                "operationId": "GetThings", "tags": ["things"],
                "description": "Returns things.",
                "parameters": [{"name": "year", "in": "query", "required": True,
                                "description": "Season year.",
                                "schema": {"type": "integer"}}],
                "responses": {"200": {"content": {"application/json": {"schema": {
                    "type": "array", "items": {"$ref": "#/components/schemas/Thing"}}}}}},
            }},
        },
        "components": {"schemas": {
            "Thing": {"type": "object", "required": ["id"], "properties": {
                "id": {"type": "integer", "format": "int32"},
                "kind": {"$ref": "#/components/schemas/Kind"},
                "venue": {"$ref": "#/components/schemas/Venue"},
                "parts": {"type": "array", "items": {"$ref": "#/components/schemas/Part"}},
            }},
            "Venue": {"type": "object", "properties": {"name": {"type": "string", "nullable": True}}},
            "Part": {"type": "object", "properties": {"label": {"type": "string"}}},
            "Kind": {"type": "string", "enum": ["a", "b"]},
        }},
    })


def test_nested_objects_flatten_to_dot_paths():
    _, fields, _ = _spec().extract()
    paths = {f["field_path"] for f in fields}
    assert "venue.name" in paths
    assert "parts[].label" in paths


def test_shared_child_entities_are_not_mistaken_for_recursion():
    """An array of a DIFFERENT entity must expand, not truncate.

    The first version of this walker pushed the child's name onto the ancestor stack before
    checking it, so every array-of-entity matched itself and eight endpoints came out empty.
    """
    _, fields, _ = _spec().extract()
    descriptions = " ".join(f["description"] for f in fields)
    assert "RECURSIVE" not in descriptions


def test_nullability_and_required_come_from_the_spec():
    _, fields, _ = _spec().extract()
    by_path = {f["field_path"]: f for f in fields}
    assert by_path["id"]["required"] == "yes"
    assert by_path["venue.name"]["nullable"] == "yes"
    assert by_path["id"]["nullable"] == "no"


def test_enums_are_carried_through():
    _, fields, _ = _spec().extract()
    kind = next(f for f in fields if f["field_path"] == "kind")
    assert kind["type"] == "enum<Kind>"
    assert kind["enum_values"] == "a; b"


def test_extract_can_be_restricted_to_landed_keys():
    endpoints, fields, _ = _spec().extract(keys={"nothing_landed"})
    assert endpoints == [] and fields == []


def test_vocabularies_are_collected():
    assert _spec().vocabularies() == [{"name": "Kind", "values": ["a", "b"]}]


# --------------------------------------------------------------------- profiling
def test_records_of_handles_every_payload_shape():
    assert records_of({"status_code": 200, "data": [{"a": 1}]}) == ([{"a": 1}], "wrapped")
    assert records_of([{"a": 1}]) == ([{"a": 1}], "bare_array")
    assert records_of({"a": 1}) == ([{"a": 1}], "bare_object")


def test_grain_detection_finds_the_smallest_unique_combination():
    records = [
        {"gameId": 1, "team": "A", "points": 7},
        {"gameId": 1, "team": "B", "points": 3},
        {"gameId": 2, "team": "A", "points": 21},
    ]
    combos = unique_combos(records, candidate_keys(records))
    assert ["gameId", "team"] in combos
    assert ["gameId"] not in combos


def test_columns_with_nulls_are_not_offered_as_keys():
    records = [{"id": 1, "team": None}, {"id": 2, "team": "A"}]
    assert "team" not in candidate_keys(records)
