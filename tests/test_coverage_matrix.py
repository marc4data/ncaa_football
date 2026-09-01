"""The document that says how much of CFBD is actually in the warehouse.

Before this existed, the answer was a number someone counted by hand and got differently each
time. It came out at 134 of 1,191 fields — 11.3% — which is the cost of streamlining toward
one website stated in one figure. A generator that produced a *comfortable* wrong number would
be worse than no generator, so these tests are mostly about the ways it could flatter itself.
"""
import json

from src import coverage_matrix as cm
from src.data_dictionary.spec import Spec
from src.endpoints import BY_PATH

DOC = cm.OUTPUT


def spec() -> Spec:
    return Spec(json.loads(cm.SPEC_PATH.read_text()))


# --- the generator ------------------------------------------------------------------------

def test_staging_models_bind_to_the_raw_tables_they_select_from():
    """The endpoint -> model link is derived from `source('raw', ...)` in the SQL, not from a
    hand-kept list that would drift the first time a model was renamed."""
    bindings = cm.staging_models()
    assert bindings["raw_venues"].keys() == {"stg_venues"}
    assert bindings["raw_games"].keys() == {"stg_games"}
    # One model can cover several endpoints — stg_team_rating unions five ratings sources —
    # and one raw table can feed several models. Both directions have to survive.
    assert "stg_team_rating" in bindings["raw_ratings_srs"]
    assert "stg_team_rating" in bindings["raw_ppa_teams"]


def test_envelope_keys_are_not_counted_as_exposed_fields():
    """`params` is the REQUEST and `content` is the response wrapper. Both are read by nearly
    every model, and counting them would credit the pipeline for reading its own bookkeeping —
    inflating coverage on exactly the endpoints with the least of it."""
    keys = cm.staging_models()["raw_teams"]["stg_teams"]
    assert "year" not in keys, "`year` comes from json_get_string('params', 'year')"
    assert "data" not in keys, "`data` is the envelope's payload wrapper"
    assert {"school", "mascot", "conference"} <= keys


def test_a_fully_unnested_endpoint_reports_complete():
    """stg_venues reads all fourteen fields /venues publishes — verified against the spec by
    hand. If the matcher ever stops seeing them, this is where it shows."""
    rows = {r.path: r for r in cm.build_rows(spec(), {"raw_venues": 2})}
    venues = rows["venues"]
    assert venues.fields_available == 14
    assert venues.fields_unnested == 14
    assert venues.missing_fields == []
    assert venues.status == "complete"


def test_a_model_that_drops_fields_reports_partial_and_names_them():
    """The gap has to be specific to be worth anything. `stg_games` exposes nineteen of the
    forty-one fields /games publishes; both conference names are among the twenty-two it
    drops, which is why Scores could not label a conference game without a join."""
    rows = {r.path: r for r in cm.build_rows(spec(), {"raw_games": 341})}
    games = rows["games"]
    assert games.status == "partial"
    assert games.fields_available > games.fields_unnested
    assert {"homeConference", "awayConference"} <= set(games.missing_fields)


def test_landed_but_unread_endpoints_are_distinguished_from_never_fetched():
    """"Raw only" and "no raw data" are different problems with different fixes — one needs a
    staging model, the other needs a backfill. Collapsing them into "missing" is what made the
    gap look like one big undifferentiated task.

    THE FIXTURE IS SYNTHETIC ON PURPOSE. This used to assert on /drives, which was genuinely
    raw-only at the time; the play-by-play round modelled it and the test broke. There are now
    ZERO raw-only endpoints, so no real one can stand in — but the distinction still has to
    hold the day a new endpoint lands ahead of its model. Handing build_rows a landed count
    for an endpoint that has no model exercises exactly that.
    """
    rows = {r.path: r for r in cm.build_rows(spec(), {"raw_coaches_tenures": 12})}
    assert rows["coaches/tenures"].status == "raw only", (
        "an endpoint with landed responses and no model is a MODELLING task")
    assert rows["teams/matchup"].status == "no raw data", (
        "an endpoint with no landed responses is a BACKFILL task")


def test_unregistered_endpoints_are_reported_as_such():
    """Ranked worst-first, an endpoint we have not decided about should not be able to hide
    behind an endpoint we have.

    SYNTHETIC, BECAUSE THERE ARE NO UNREGISTERED ENDPOINTS LEFT. This asserted on
    `passing/plays`, which was genuinely unregistered until Priority 6 registered all five
    passing paths — every path the spec serves is now in src/endpoints.py. The status still
    has to work the day CFBD ships a sixth, so the case is constructed rather than borrowed
    from a real gap that no longer exists.
    """
    invented = "totally/new/endpoint"
    doc = spec()
    doc.doc["paths"]["/" + invented] = doc.doc["paths"]["/venues"]
    rows = {r.path: r for r in cm.build_rows(doc, {})}
    assert rows[invented].status == "unregistered"
    assert rows[invented].endpoint is None

    # And nothing real is unregistered any more, which is the state worth pinning.
    real = {r.path for r in cm.build_rows(spec(), {}) if r.status == "unregistered"}
    assert not real, f"the spec serves endpoints nobody has decided about: {sorted(real)}"


def test_every_spec_endpoint_gets_a_row():
    """The spec is the denominator. An endpoint the generator skipped would be a gap that the
    gap report cannot see."""
    rows = cm.build_rows(spec(), {})
    assert len(rows) == len(spec().doc["paths"])
    assert {r.path for r in rows} >= set(BY_PATH)


def test_ops_tables_are_not_mistaken_for_endpoint_coverage():
    """raw_manifest and friends are our own telemetry landing in the same schema because they
    go through the same loader. They have staging models and no endpoint; counting them would
    flatter the coverage figure with data CFBD never served."""
    assert "raw_manifest" in cm.OPS_TABLES
    rows = {r.path for r in cm.build_rows(spec(), {})}
    assert not rows & {"manifest", "dbt_test_result", "deploy_status"}


# --- the committed document -----------------------------------------------------------------

def test_the_matrix_is_committed_and_marked_generated():
    assert DOC.exists(), "docs/cfbd_coverage.md is missing — run python -m src.coverage_matrix"
    text = DOC.read_text()
    assert "do not edit by hand" in text
    assert "python -m src.coverage_matrix" in text


def test_the_committed_matrix_covers_every_endpoint_in_the_vendored_spec():
    """The doc and the spec are both tracked, so this part is deterministic — unlike the raw
    counts, which depend on which machine was asked and are stamped in the header instead.

    Regenerating in CI is not possible: `data/` is gitignored, so a CI run sees no landed data
    at all and would rewrite every row to "no raw data". This checks the half that does not
    move.
    """
    text = DOC.read_text()
    for path in spec().doc["paths"]:
        assert f"| `{path.lstrip('/')}` |" in text, f"{path} is missing from the matrix"


def test_the_matrix_states_how_its_field_counts_are_derived():
    """Leaf-name matching can overcount. A number this stark gets quoted, so the document has
    to carry its own caveat rather than relying on whoever quotes it having read the code."""
    text = DOC.read_text()
    assert "Leaf matching" in text
    assert "cannot miss a field that is" in text
