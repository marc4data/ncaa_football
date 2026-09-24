"""A227 — the site may not publish a model that was trained on the closing line.

📊 THE FINDING: five of the six models whose figures this site published were given the
closing spread as a feature and then graded on how well they beat that spread. Their accuracy
numbers describe a model that had already seen the answer.

🚨 WHAT MAKES THIS A TEST FILE RATHER THAN A ONE-LINE FILTER: the same claim is published by
FOUR different surfaces — the Model Performance page, the Edge Finder and its track record,
the Odds Board's "Model margin" line, and the Excel workbook. A withdrawal that covers three
of them is not a withdrawal, and the one it is most likely to miss is the workbook, because
that is a file Marc sends to people and it outlives the page it disagrees with.

⚠️ SO THE ASSERTIONS HERE ARE MOSTLY *EVERY SURFACE*, NOT *THIS SURFACE*. A per-file list is
four copies free to disagree (R-574), and the disagreement is invisible: each page looks
internally consistent while they contradict each other.
"""
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import select_list                                   # noqa: E402
from lib import models                               # noqa: E402

PERFORMANCE = (ROOT / "site" / "views" / "performance.py").read_text(encoding="utf-8")
EDGES = (ROOT / "site" / "views" / "edges.py").read_text(encoding="utf-8")
ODDS = (ROOT / "site" / "views" / "odds.py").read_text(encoding="utf-8")
WORKBOOK = (ROOT / "site" / "lib" / "workbook.py").read_text(encoding="utf-8")

# The views whose ROW IS A MODEL — withdrawing one means dropping rows, in SQL, upstream of
# the query's own row cap.
PER_MODEL_VIEWS = ("srv_model_performance", "srv_edge_finder",
                   "srv_edge_bucket_performance")

# 🚨 ONE EXEMPTION, NAMED, WITH ITS REASON — NOT A LOOSENED RULE.
#
# `edges._withdrawal_emptied` asks whether a market had graded buckets BEFORE the exclusion,
# so that an empty track record can say WHICH absence it is (AC-G.11) instead of guessing.
# Filtering it would make it agree with the query it exists to explain, and it would answer
# nothing — a guard that cannot disagree is decoration (R-760).
#
# ⚠️ IT IS SAFE BECAUSE OF WHAT IT SELECTS: one column, `market`, which is not a prediction,
# not a metric and not a model name. It can tell the page that rows existed; it cannot
# publish anything about them. An exemption that returned measures would not be safe and is
# not what this allows.
DELIBERATELY_UNFILTERED = {
    "select market from srv_edge_bucket_performance where market = :market limit 1",
}


def _code_strings(source):
    """Every string literal a module EXECUTES — docstrings excluded.

    ⚠️ THE CARVE-OUT IS DELIBERATE AND IT IS NARROWER THAN "COMMENTS ARE EXEMPT". Recording
    WHY `fastai_home_win` is absent, in the docstring of the function that renders that
    absence, is the documentation this project runs on. Hardcoding the same name into a
    filter is the defect. `ast` can tell the two apart; a line-based strip cannot, and the
    first draft of this test failed on its own prose because of it.
    """
    import ast
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings:
            yield node.value


def _statements(source):
    """Every SQL string literal in a module, flattened and comment-stripped.

    Uses A102's `select_list.strip_comments` rather than a fresh regex: a `--` line
    mentioning a column blinds a naive parse in both directions, and this file is not going
    to be the fourth guard to learn that (R-669).
    """
    for raw in re.findall(r'"""(.*?)"""', source, re.S):
        # ⚠️ ANCHORED ON `select` AS THE FIRST TOKEN, NOT MERELY CONTAINING IT. The first
        # draft searched for the words `select` and `from` anywhere, and matched this
        # project's MODULE DOCSTRINGS — which discuss what their queries select and from
        # where. A guard that reads prose as SQL is R-3007's family, found the same way:
        # by running it.
        if re.match(r"\s*select\b", raw, re.I):
            yield " ".join(select_list.strip_comments(raw).split())


# ==========================================================================================
# THE LIST ITSELF
# ==========================================================================================

def test_every_withdrawn_model_cites_the_notebook_and_cell_it_was_judged_from():
    """🚨 THE VERDICT IS EVIDENCE, NOT AN OPINION, AND R-2421 IS WHY THE CELL NUMBER MATTERS.

    A220 read notebook 01 cell 11, found no spread, and reported the model clean. The list
    that model actually fits is in cell 13 and begins with the spread. A verdict recorded
    without the cell it was read from cannot be re-checked by the next person, and this one
    was wrong for exactly that reason once already.
    """
    assert models.WITHDRAWN, "nothing withdrawn — this whole file now proves nothing"
    for name, (reason, evidence) in models.WITHDRAWN.items():
        assert reason.strip(), name
        assert re.search(r"notebook \d+", evidence), f"{name} cites no notebook: {evidence}"
        assert re.search(r"cell \d+", evidence), f"{name} cites no cell: {evidence}"


def test_a_model_is_never_both_withdrawn_and_published():
    assert not (set(models.WITHDRAWN) & set(models.PUBLISHED))
    assert models.ALL_MODELS == set(models.WITHDRAWN) | set(models.PUBLISHED)


def test_an_unknown_model_is_not_withdrawn():
    """⚠️ THE DEFAULT RUNS THE OTHER WAY ON PURPOSE, AND IT IS A TRADE WORTH STATING.

    The replacement line-free model arrives under a name this file has never seen. A
    default of "hide anything unrecognised" would hide it on arrival — a withdrawal that
    swallows its own replacement — and would do it silently, which is the worse half.
    """
    assert not models.is_withdrawn("some_future_line_free_model")
    assert not models.is_withdrawn(None)
    # R-2255: `"" in anything` is True. An empty name is not a withdrawn model.
    assert not models.is_withdrawn("")


def test_the_clean_model_is_actually_published():
    """📊 `random_forest_score` was checked the same way the others were, not assumed clean:
    pack notebook 02 fits at cell 15 on the list at cell 11, twelve EPA and success-rate
    features, no line field. If this ever flips, the site publishes nothing at all and that
    is a decision, not a test to relax."""
    assert "random_forest_score" in models.PUBLISHED
    assert not models.is_withdrawn("random_forest_score")


# ==========================================================================================
# EVERY SURFACE, NOT THIS SURFACE
# ==========================================================================================

@pytest.mark.parametrize("name", ["performance.py", "edges.py", "workbook.py"])
def test_every_per_model_query_excludes_the_withdrawn_models(name):
    """🚨 THE ONE THAT CATCHES A NEW QUERY SOMEBODY ADDS LATER.

    Asserting "the filter appears in this file" would pass on a file with one filtered query
    and three unfiltered ones. This walks EVERY statement reading a per-model view and
    requires the exclusion on each, so adding a fourth query without it is red.
    """
    source = {"performance.py": PERFORMANCE, "edges.py": EDGES,
              "workbook.py": WORKBOOK}[name]
    for sql in _statements(source):
        reads = [v for v in PER_MODEL_VIEWS if re.search(rf"\bfrom\s+{v}\b", sql)]
        if not reads:
            continue
        if sql in DELIBERATELY_UNFILTERED:
            continue
        assert "{PUBLISHED_MODELS_ONLY}" in sql, (
            f"{name} reads {reads[0]} without the withdrawal filter: {sql[:160]}")


def test_the_exclusion_is_upstream_of_the_row_cap():
    """📊 WHY IT IS SQL AND NOT A PANDAS DROP, MEASURED: five of six models are withdrawn.

    A 200-row read filtered afterwards spends its cap on rows nobody will see and can return
    nothing publishable while the database holds hundreds. The cap silently becomes the
    filter. So the clause has to be inside the statement, before `limit`.
    """
    for source in (PERFORMANCE, EDGES, WORKBOOK):
        for sql in _statements(source):
            if "{PUBLISHED_MODELS_ONLY}" not in sql:
                continue
            assert re.search(r"\blimit\b", sql, re.I), sql[:120]
            assert sql.lower().index("{published_models_only}".lower()) \
                < sql.lower().rindex("limit"), f"filter sits after the cap: {sql[:160]}"


def test_no_consumer_carries_its_own_copy_of_the_model_names():
    """⚠️ R-574 IN ANOTHER COSTUME. `performance.py` used to hold a literal `EXPECTED_MODELS`
    set of seven names; the workbook and the Edge Finder each knew their own. Four lists,
    and nothing that would notice them drifting apart.

    Comments are exempt — recording WHY a name was withdrawn where the code is, is the point
    of the evidence, and quoting it is not the same as hardcoding it (the same carve-out
    `test_export_page` makes for its sheet names).
    """
    for name, source in (("performance.py", PERFORMANCE), ("edges.py", EDGES),
                         ("odds.py", ODDS), ("workbook.py", WORKBOOK)):
        for model in models.WITHDRAWN:
            for literal in _code_strings(source):
                assert model not in literal, (
                    f"{name} names {model!r} in a string it executes; read lib.models")
            for line in source.splitlines():
                stripped = line.lstrip()
                if stripped.startswith("#") or model not in line:
                    continue
                assert '"' in line or "'" in line, (
                    f"{name} names {model!r} in code: {line.strip()[:90]}")


# ==========================================================================================
# THE GAME-GRAIN SURFACES — BLANK THE PREDICTION, KEEP THE GAME
# ==========================================================================================

def test_suppression_blanks_the_prediction_and_keeps_the_fixture():
    df = pd.DataFrame({
        "game_id": [1, 2],
        "home_team": ["Ohio State", "Michigan"],
        "model_name": ["ridge_margin_expanded", "random_forest_score"],
        "predicted_margin": [7.5, -3.0],
        "confidence_bucket": ["high", "lean"],
    })
    out, count = models.suppress_withdrawn(df)
    assert count == 1
    # The GAME survives — dropping the row would delete a fixture to hide a number on it.
    assert len(out) == 2 and list(out["home_team"]) == ["Ohio State", "Michigan"]
    assert pd.isna(out.loc[0, "predicted_margin"])
    assert pd.isna(out.loc[0, "confidence_bucket"])
    # And the publishable row is untouched.
    assert out.loc[1, "predicted_margin"] == -3.0


def test_suppression_reads_the_odds_boards_spelling_too():
    """🚨 THE TWO GAME-GRAIN VIEWS DISAGREE ABOUT WHICH COLUMN NAMES THE MODEL, MEASURED:

        srv_game        model_name='random_forest_score'  model_version_key='98d34949266b'
        srv_odds_board  no model_name at all              model_version_key='random_forest_score'

    Keying only on `model_name` leaves the Odds Board — which renders "Model margin … edge"
    — outside the withdrawal, silently, while looking wired up.
    """
    odds = pd.DataFrame({"model_version_key": ["ridge_margin_expanded"],
                         "predicted_margin": [4.0], "home_cover_edge": [1.5]})
    out, count = models.suppress_withdrawn(odds)
    assert count == 1
    assert pd.isna(out.loc[0, "predicted_margin"]) and pd.isna(out.loc[0, "home_cover_edge"])


def test_a_version_hash_is_never_mistaken_for_a_model_name():
    """The fallback above must not fire on `srv_game`, whose version key is a hash."""
    df = pd.DataFrame({"model_name": ["random_forest_score"],
                       "model_version_key": ["98d34949266b"], "predicted_margin": [2.0]})
    _, count = models.suppress_withdrawn(df)
    assert count == 0


def test_cfbd_in_game_win_probability_is_never_suppressed():
    """⚠️ R-2260 — A SUBSTRING IS NOT A RULE. `home_win_probability` is OUR model's number on
    `srv_game` and CFBD's in-game number on `srv_game_win_probability_play`. The second is
    not a prediction of ours and suppressing it would blank a chart for no reason. They are
    told apart by the relation carrying a model column at all, which the play-by-play one
    does not."""
    play = pd.DataFrame({"play_number": [1, 2], "home_win_probability": [0.51, 0.62]})
    out, count = models.suppress_withdrawn(play)
    assert count == 0
    assert list(out["home_win_probability"]) == [0.51, 0.62]


def test_the_workbook_suppresses_before_it_decides_a_sheet_is_empty():
    """🚨 THE WORKBOOK IS THE SURFACE THAT TRAVELS BY EMAIL AND OUTLIVES THE PAGE.

    Applied inside `read_sheet` rather than per sheet, so a sheet added later inherits it.
    Asserted on ORDER as well as presence: suppressing after the empty check would ship a
    sheet of blanked rows instead of an honest omission note.
    """
    body = WORKBOOK[WORKBOOK.index("def read_sheet("):]
    assert "models.suppress_withdrawn(df)" in body
    assert body.index("models.suppress_withdrawn(df)") < body.index("if df.empty:")


# ==========================================================================================
# WHAT THE READER IS TOLD — AC-13.4 AND AC-G.11
# ==========================================================================================

def test_both_pages_state_the_withdrawal_rather_than_quietly_getting_shorter():
    """AC-13.4: *a missing model is an absence the page states rather than an omission the
    reader has to notice.* The note is the page's, not a banner bolted on top."""
    for name, source in (("performance.py", PERFORMANCE), ("edges.py", EDGES)):
        assert "models.WITHDRAWAL_NOTE" in source, name


def test_the_note_promises_no_date_and_no_number():
    """⚠️ A216's CAPTION WENT FALSE IN ONE ROUND. "Arriving next week" is a claim the page
    cannot keep and cannot retract; a reader who comes back to find it still there learns
    that the site does not maintain what it says."""
    note = models.WITHDRAWAL_NOTE + " " + models.WITHDRAWAL_CAPTION
    assert not re.search(r"\b(next week|next month|soon|shortly|by \w+day)\b", note, re.I)
    assert not re.search(r"\b20\d\d-\d\d-\d\d\b", note)


def test_the_note_says_which_absence_this_is():
    """AC-G.11. This site already renders "not loaded" and "no rows for your filters"; a
    third absence that does not distinguish itself from those teaches the reader nothing."""
    note = models.WITHDRAWAL_NOTE.lower()
    assert "closing" in note and ("spread" in note or "line" in note)
    assert "withdrawn" in note
    # And it says the data still exists, because "gone" and "not shown" are different.
    assert "deleted" in note or "warehouse" in note


def test_the_all_withdrawn_state_is_stated_rather_than_blank():
    """🚨 REACHABLE, NOT HYPOTHETICAL: one model stands between this site and an empty Model
    Performance page, and the MONEYLINE track record is empty the moment A227 lands because
    all four models graded on it were line-fed."""
    assert "models.PUBLISHED" in PERFORMANCE, "the empty branch does not distinguish causes"
    assert "models.PUBLISHED" in EDGES
    assert "_withdrawal_emptied" in EDGES, (
        "the track record must MEASURE why it is empty, not infer it from the site-wide "
        "withdrawal — the spread market still has a publishable model")


def test_the_one_unfiltered_read_can_publish_nothing():
    """The exemption above is only safe while it stays a row-existence probe.

    If somebody adds a measure to that SELECT, the exemption silently becomes a hole that
    publishes withdrawn models' numbers — so the exemption carries its own guard rather
    than relying on the comment beside it being read.
    """
    banned = ("hit_rate", "bucket_games", "bucket_hits", "edge_", "mean_", "model_",
              "accuracy", "brier", "predicted_")
    for sql in DELIBERATELY_UNFILTERED:
        selected = sql[sql.index("select") + 6:sql.index(" from ")]
        for token in banned:
            assert token not in selected, (
                f"the unfiltered probe now selects {token!r}: {selected}")
        # And it must still be the probe, not a table read.
        assert re.search(r"limit 1\b", sql), sql


@pytest.mark.parametrize("module", ["views.performance", "views.edges", "lib.workbook"])
def test_every_surface_uses_the_SHARED_fragment_not_a_rederived_one(module):
    """🚨 THE GUARD THAT MAKES "FOUR SURFACES CANNOT DISAGREE" AN ASSERTION RATHER THAN A HOPE.

    Each consumer binds `PUBLISHED_MODELS_ONLY` locally, because `check_page_queries`
    resolves `{NAME}` holes only from module-level string constants in the same file. That
    binding is the seam: a consumer that builds its own clause — even one that looks right
    today — is a fourth list again, and it would drift the first time the withdrawal list
    changes and somebody updated three files.

    ⚠️ IDENTITY OF VALUE, not merely "contains the same names". Two clauses can name the
    same models and differ in null handling, which is exactly the subtle way this breaks.
    """
    import importlib
    imported = importlib.import_module(module)
    assert imported.PUBLISHED_MODELS_ONLY == models.PUBLISHED_MODELS_ONLY, (
        f"{module} carries its own clause: {imported.PUBLISHED_MODELS_ONLY!r}")


def test_the_shared_fragment_names_every_withdrawn_model():
    """And the fragment is derived from the list, so removing a model from `WITHDRAWN`
    releases it on all four surfaces at once — which is the intended behaviour, and is only
    safe because it is impossible to do on three of them."""
    for name in models.WITHDRAWN:
        assert f"'{name}'" in models.PUBLISHED_MODELS_ONLY, name
    for name in models.PUBLISHED:
        assert f"'{name}'" not in models.PUBLISHED_MODELS_ONLY, name


def test_the_fragment_is_valid_sql_when_nothing_is_withdrawn():
    """⚠️ THE EMPTY CASE IS REACHABLE — it is what this file looks like once the line-free
    replacement has landed and these six are retired. `not in ()` is a syntax error, so the
    empty case must collapse to a constant instead of emitting one."""
    real = dict(models.WITHDRAWN)
    try:
        models.WITHDRAWN.clear()
        assert models._sql_exclusion() == "true"
    finally:
        models.WITHDRAWN.update(real)
    assert models.PUBLISHED_MODELS_ONLY.startswith("(model_name is null")


@pytest.mark.parametrize("path", ["site/views/performance.py", "site/views/edges.py",
                                  "site/lib/workbook.py"])
def test_the_filter_hole_is_actually_interpolated(path):
    """🚨🚨 THE BUG THE LIVE RENDER CAUGHT, AND THE ONE CI COULD NOT HAVE.

    `{PUBLISHED_MODELS_ONLY}` inside a PLAIN string is not a hole — it is four words of
    literal text that Postgres rejects with a syntax error. Four of `edges.py`'s queries
    were plain strings, so the filter reached the database verbatim, `states.section` caught
    the SyntaxError, and the Edge Finder rendered an ERROR CARD on every load.

    ⚠️ `ci/check_page_queries.py` CANNOT SEE THIS CLASS AND IT IS WORTH SAYING WHY: it
    SUBSTITUTES the hole textually before executing, so it runs a correct query against a
    page that will never build one. The check passed while the page was broken — which is
    the same shape as R-538, an instrument whose own preparation hides the defect.

    So: a `query(...)` call whose SQL is a plain constant may not contain the hole. The
    workbook's Sheet SQL is exempt BY MECHANISM rather than by exception — those strings are
    resolved through `SQL_HOLES` in `Sheet.__init__`, and that resolution is asserted below.
    """
    import ast
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "query"):
            continue
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            assert "{PUBLISHED_MODELS_ONLY}" not in first.value, (
                f"{path} line {first.lineno}: the hole is in a PLAIN string, so it reaches "
                f"the database as literal text")


def test_the_workbooks_sheet_sql_resolves_the_hole_by_mechanism():
    """The exemption above is only sound while `SQL_HOLES` actually carries it."""
    from lib import workbook
    assert "PUBLISHED_MODELS_ONLY" in workbook.SQL_HOLES
    assert workbook.SQL_HOLES["PUBLISHED_MODELS_ONLY"] == models.PUBLISHED_MODELS_ONLY
    # And no sheet ships with the hole unresolved.
    for sheet in list(workbook.SHEETS) + list(workbook.PENDING_SHEETS):
        assert "{PUBLISHED_MODELS_ONLY}" not in sheet.sql, sheet.name
