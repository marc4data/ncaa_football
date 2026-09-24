"""WHICH MODELS THIS SITE MAY PUBLISH, AND WHY THE OTHERS WERE WITHDRAWN.

🚨 **FIVE OF THE SIX MODELS WHOSE NUMBERS THIS SITE PUBLISHED WERE TRAINED WITH THE CLOSING
SPREAD AS A FEATURE.** They were then graded on how well they beat that same spread. A
leaderboard that quietly outperforms the market because it was shown the market is not a
result; it is a bug with a percentage sign on it, and this site is a portfolio piece.

> **MARC, 2026-09-24 (cfdb-wtc-R-2426):** pull the spread-fed model from the site now; our own
> line-free model replaces it after cfdb-wtc-R-2490.

📊 **ESTABLISHED PER MODEL BY READING THE PACK NOTEBOOK THAT PRODUCES IT (A227, R-3100)** —
specifically the feature list the `.fit()` actually consumes, not the first list in the file.
⚠️ That distinction is the whole reason the evidence below cites a cell number: A220 read
notebook 01 cell 11, reported *"no spread"*, and the list that model really uses is in cell 13
(R-2421). Two true readings and an invented edge between them (§2.2.1f).

🚨 **NOTHING IS DELETED.** Predictions are append-only and the dbt singular test
`assert_predictions_are_never_mutated` enforces it. **This is a publication change** — the
rows stay in the warehouse, the site stops presenting them as results.

⚠️ **ONE LIST, READ BY EVERY SURFACE.** A per-file copy is four copies free to disagree
(R-574), and the disagreement would be invisible: each page would look internally consistent
while the workbook shipped a model the page had withdrawn. The reason travels WITH the name,
in the same structure, so a reader of any consumer can see why.
"""
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════════════════
# THE EVIDENCE, PER MODEL — notebook, the cell the fit consumes, and what was in it
# ══════════════════════════════════════════════════════════════════════════════════════════
#
# ⚠️ THE PACK IS LICENSED, PERSONAL AND NON-COMMERCIAL, AND THIS REPOSITORY IS PUBLIC.
# What is recorded here is a CITATION — a filename, a cell number, and the name of one
# feature. No pack code is reproduced here or anywhere else in this repo.

_SPREAD = "trained with the closing spread as a feature, then graded against that spread"

WITHDRAWN = {
    "ridge_margin_expanded": (
        _SPREAD,
        "pack notebook 01, cell 13 defines the feature list and cell 17 fits it; the list "
        "begins with the spread"),
    "xgboost_home_win_calibrated": (
        _SPREAD,
        "pack notebook 03, cell 11 defines the feature list, cell 13 builds the training "
        "matrix from it and cell 15 fits it; the list begins with the spread"),
    "logistic_home_win_c_0.25": (
        _SPREAD,
        "pack notebook 05, cell 11 defines the continuous features, cell 13 builds the "
        "training matrix and cell 17 fits it; the list begins with the spread"),
    "xgboost_home_win_shap_explained": (
        _SPREAD,
        "pack notebook 06, cell 11 defines the feature list, cell 13 builds the training "
        "matrix and cell 15 fits it; the list begins with the spread"),
    "stacked_ensemble_home_win": (
        _SPREAD + ", through all three of its base models",
        "pack notebook 07, cell 10 defines the feature pool, cell 16 filters it, cell 23 "
        "gives every base model that pool and cells 25 and 27 fit them; the pool begins "
        "with the spread. An ensemble over line-fed bases is line-fed however clean its "
        "own stacking step looks"),
    "fastai_home_win": (
        _SPREAD,
        "pack notebook 04, cell 11 defines the continuous features and cell 15 fits from "
        "them; the list begins with the spread. This model has no rows on the site either "
        "way — its export was never written — but it is named here so that loading it "
        "later cannot quietly publish it"),
}

# ✅ CLEAN, AND CHECKED THE SAME WAY RATHER THAN ASSUMED.
#
# `random_forest_score` (pack notebook 02) fits at cell 15 on the list defined at cell 11 —
# twelve adjusted EPA and success-rate features, no line field of any kind.
#
# ⚠️ TWO HONEST QUALIFICATIONS, because "clean" is a claim and this is where it is made:
#   1. Notebook 02 DOES name the spread twice, and neither use is a feature. Cell 13 puts it
#      in the `dropna` subset, so the training sample is restricted to games that had a line
#      — a selection effect, not leakage. Cell 19 uses it to GRADE against the line, which is
#      the correct use of a closing number.
#   2. It is the only model this site still publishes, so the Model Performance page is now a
#      one-row table rather than a leaderboard. That is stated on the page, not left to be
#      noticed.
PUBLISHED = frozenset({"random_forest_score"})

# Every model the site knows about, withdrawn or not. `views/performance.py` renders a
# visible row for each one it did not load (AC-13.4) and needs the full set to do it.
ALL_MODELS = frozenset(WITHDRAWN) | PUBLISHED


def is_withdrawn(model_name) -> bool:
    """Whether this site may publish figures attributed to `model_name`.

    ⚠️ UNKNOWN NAMES ARE NOT WITHDRAWN, AND THAT IS THE DELIBERATE DIRECTION. The replacement
    line-free model lands under a new name after cfdb-wtc-R-2490, and a default that hid
    anything unrecognised would hide it on arrival — a withdrawal that silently swallows its
    own replacement. The list of what is BANNED is the thing under review; membership of it
    is explicit.

    ⚠️ AND A NULL IS NOT A WITHDRAWN MODEL (R-2255 — `"" in anything` is True). A game row
    with no model attached carries no prediction to suppress.
    """
    if model_name is None:
        return False
    return str(model_name) in WITHDRAWN


def withdrawal_reason(model_name) -> Optional[str]:
    """Why this model was withdrawn, or None if it was not. The reason travels with the
    name so a consumer never has to restate it."""
    entry = WITHDRAWN.get(str(model_name)) if model_name is not None else None
    return entry[0] if entry else None


def evidence(model_name) -> Optional[str]:
    """The notebook and cell the verdict was read from. A citation, never pack code."""
    entry = WITHDRAWN.get(str(model_name)) if model_name is not None else None
    return entry[1] if entry else None


def _sql_exclusion() -> str:
    """A WHERE fragment excluding every withdrawn model, for the views whose ROWS are
    per-model — `srv_model_performance`, `srv_edge_finder`, `srv_edge_bucket_performance`.

    🚨 FILTERED IN SQL RATHER THAN IN PANDAS, AND THE REASON IS THE `limit`. Every page query
    here carries an explicit row cap (AC-G.39). Reading 200 rows and dropping five models
    afterwards means the cap is spent on rows nobody will see — with five of six models
    withdrawn, a 200-row read could return no publishable row at all while the database holds
    hundreds. The filter has to be upstream of the cap or the cap silently becomes the filter.

    ⚠️ A NULL `model_name` IS KEPT. `x not in (...)` is NULL for a NULL x, which would drop
    the row; a row with no model named is not a row attributed to a withdrawn model, and an
    exclusion list should only ever remove things it names.

    ⚠️ AND IT IS TOTAL AT BOTH ENDS: with nothing withdrawn this is `true`, not `not in ()`,
    which is a syntax error. The empty case is reachable — it is what this file looks like
    once the line-free model has replaced these.
    """
    if not WITHDRAWN:
        return "true"
    names = ", ".join(f"'{name}'" for name in sorted(WITHDRAWN))
    return f"(model_name is null or model_name not in ({names}))"


# Interpolated into page queries as `{PUBLISHED_MODELS_ONLY}`. Built once at import so every
# consumer gets the same text, and registered in `ci/check_page_queries.py`'s SUBSTITUTIONS
# so that checker still EXECUTES those queries rather than waving them through.
PUBLISHED_MODELS_ONLY = _sql_exclusion()

# ══════════════════════════════════════════════════════════════════════════════════════════
# WHAT THE READER IS TOLD
# ══════════════════════════════════════════════════════════════════════════════════════════
#
# 🚨 AC-13.4 ALREADY DECIDED THE SHAPE: *"a missing model is an absence the page states
# rather than an omission the reader has to notice."* A withdrawn model is not a row that
# vanishes and not a table that quietly gets shorter.
#
# ⚠️ AC-G.11: THE NOTE MUST SAY WHICH ABSENCE THIS IS. This page already renders two others —
# "not loaded" (the export was never written) and "no rows for your filters" — and withdrawn
# is neither. A reader who cannot tell them apart learns nothing from any of them.
#
# ⚠️ AND NO DATE, NO NUMBER, NO PROMISE. "Arriving next week" is a claim the page cannot keep
# and cannot retract; A216's caption went false in a round. This says what is true now.
WITHDRAWAL_NOTE = (
    "**Withdrawn: trained on the closing line.** These models were given the closing spread "
    "as an input and then scored on how well they beat it, so their accuracy figures "
    "describe a model that had already seen the answer. They have been taken off the site "
    "rather than presented with a caveat. A replacement trained without any market input is "
    "being built; nothing is deleted, and the predictions remain in the warehouse.")

# The same fact in one line, for a caption rather than a callout.
WITHDRAWAL_CAPTION = (
    "Models trained on the closing spread have been withdrawn — their figures described a "
    "model that had seen the line it was being graded against.")


# ══════════════════════════════════════════════════════════════════════════════════════════
# THE GAME-GRAIN CASE, WHICH IS A DIFFERENT SHAPE AND NEEDS A DIFFERENT ANSWER
# ══════════════════════════════════════════════════════════════════════════════════════════
#
# 🚨 ON `srv_model_performance` AND `srv_edge_finder` THE ROW *IS* THE MODEL, so withdrawing
# one means dropping rows and `PUBLISHED_MODELS_ONLY` does it in SQL. ON `srv_game` AND
# `srv_odds_board` THE ROW IS A GAME that happens to carry a prediction in a few of its
# columns — and dropping those rows would delete the fixture from the schedule to suppress a
# number attached to it.
#
# ⚠️ SO THE PREDICTION IS BLANKED AND THE GAME SURVIVES. One list of which columns carry a
# claim, in the same file as the list of which models may make one.
PREDICTION_COLUMNS = frozenset({
    "predicted_margin", "predicted_margin_home_perspective",
    "predicted_home_points", "predicted_away_points", "predicted_total_points",
    "predicted_home_win_probability", "home_win_probability",
    "home_cover_edge", "home_win_probability_edge",
    "confidence_bucket", "model_name", "model_family", "model_version_key",
    "is_out_of_sample_week",
})

# ⚠️ `home_win_probability` IS ON THAT LIST AND IT IS THE ONE TO BE CAREFUL WITH.
# `srv_game` uses that name for OUR model's number, and `srv_game_win_probability_play` uses
# the same name for CFBD's in-game win probability, which is not a prediction of ours and
# must never be suppressed. The two are told apart by the relation, not by the column name —
# which is why `suppress_withdrawn` keys on `model_name` being PRESENT in the frame: the
# play-by-play relation has no such column, so it can never match. A substring is not a rule
# (R-2260).


def suppress_withdrawn(df):
    """Blank the prediction columns on any row attributed to a withdrawn model.

    Returns `(frame, rows_suppressed)`. The frame is a copy; nothing is mutated in place.

    ⚠️ A FRAME WITH NO `model_name` IS RETURNED UNTOUCHED AND THAT IS THE GUARD, not an
    oversight — see the note above about the two different `home_win_probability` columns.

    ⚠️ AND IT IS A NO-OP TODAY ON EVERY LIVE RELATION, WHICH IS WORTH STATING PLAINLY RATHER
    THAN LETTING IT LOOK LOAD-BEARING. 📊 A227 measured it: `srv_game` and `srv_odds_board`
    both carry `random_forest_score` and nothing else, so no live row matches. It is here
    because the load path is what decides which model lands on those views, and a defence
    that only exists where a problem is already visible is a defence against the past.
    """
    if df is None or getattr(df, "empty", True):
        return df, 0
    # 🚨 THE TWO GAME-GRAIN VIEWS DO NOT AGREE ON WHICH COLUMN NAMES THE MODEL, AND A227
    # MEASURED IT RATHER THAN ASSUMING THE OBVIOUS ONE:
    #
    #     srv_game        model_name = 'random_forest_score'   model_version_key = '98d34949266b'
    #     srv_odds_board  (no model_name column at all)        model_version_key = 'random_forest_score'
    #
    # So `model_version_key` is a HASH on one view and a NAME on the other. Keying only on
    # `model_name` would have left the Odds Board — which renders "Model margin … edge …" —
    # outside the withdrawal entirely, silently, and it would have looked wired up.
    #
    # ⚠️ THE FALLBACK IS SAFE IN THE OTHER DIRECTION because `is_withdrawn` matches exact
    # known names and nothing else: a version hash can never collide with one.
    key = next((c for c in ("model_name", "model_version_key") if c in df.columns), None)
    if key is None:
        return df, 0
    hit = df[key].map(is_withdrawn)
    count = int(hit.sum())
    if not count:
        return df, 0
    out = df.copy()
    for column in PREDICTION_COLUMNS & set(out.columns):
        out.loc[hit, column] = None
    return out, count
