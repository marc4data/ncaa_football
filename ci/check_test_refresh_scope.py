"""Find tests a gated DAG cannot satisfy, before they block a publish.

THE RULE, WHICH `dags/scores_refresh_dag.py` ALREADY STATES IN PROSE:

    A test comparing something the DAG DOES refresh against something it does NOT is
    measuring the gap between two fetch times, not correctness.

`cfbd_scores_refresh` rebuilds `+srv_game +srv_team_game_log +srv_game_weather` every two
hours. Any test that straddles that boundary — one ref inside the selection, another outside —
fails whenever the two sides are at different refreshes, which on a game day is constantly.

WHY IT MATTERS MORE THAN A RED TEST. `publish_to_serving` is downstream of `dbt_test` on the
default all_success rule. A straddling test therefore does not just report a false problem: it
STOPS THE SITE UPDATING, silently, for as long as the gap persists.

SEVEN TESTS HAVE HIT THIS. Six were tagged `full_refresh_only` one at a time across the week of
24 August, each looking like a separate bug. The seventh — `assert_team_series_reconciles` —
blocked three consecutive runs on 2026-09-04 and would have blocked all twelve on a November
Saturday, which settles ~298 games.

Six point fixes and a prose rule did not prevent a seventh, so this is the check. It reads the
compiled manifest, which knows the real dependency edges, rather than the test's text.

A straddling test is not wrong — it is usually the most valuable kind, comparing two
independent derivations. It simply belongs on the build that refreshes both sides, which is
what the tag means.
"""
import json
import sys
from pathlib import Path

MANIFEST = Path("dbt/target/manifest.json")

# What the PARTIAL-REBUILD DAGs rebuild, mirroring their selectors. `+` pulls ancestors.
#
# R-338: this listed only the scores DAG's three roots, so the over-tagging check reasoned
# about half the pattern. cfbd_lines_snapshot is the same shape of job and its two roots were
# missing, which is the same one-instance blindness that let the exclusion itself go unapplied
# to that DAG for a day and a half.
GATED_SELECTION = (
                   # cfbd_scores_refresh — SCORES_SELECTOR
                   "model.cfdb_dbt.srv_game",
                   "model.cfdb_dbt.srv_team_game_log",
                   "model.cfdb_dbt.srv_game_weather",
                   # R-492. Added to SCORES_SELECTOR because the hot publish was already
                   # shipping srv_team_week on every gate-open run without rebuilding it.
                   # ⚠️ THIS MIRROR IS THE LIST test_dag_structure.py:120 WARNS ABOUT —
                   # "a list nobody reads is a list nobody maintains", written after
                   # assert_team_series_reconciles slipped through a two-entry tuple nobody
                   # had updated. Changing the DAG's selector without changing this line
                   # leaves the straddle check reasoning about the old selection, which fails
                   # in the direction that looks fine.
                   "model.cfdb_dbt.srv_team_week",
                   # R-530 / R-532. Same round, same reason: both were published on the hot
                   # publish and rebuilt only weekly. ⚠️ Updating this mirror is the step
                   # test_dag_structure.py:120 warns about by name — A078 remembered it, and
                   # the round before that is the one where a name nobody added to a tuple let
                   # the seventh straddling test through.
                   "model.cfdb_dbt.srv_game_team",
                   "model.cfdb_dbt.srv_odds_board",
                   "model.cfdb_dbt.srv_line_movement",
                   # R-533. Three models marginal; all ancestors already selected.
                   "model.cfdb_dbt.srv_standings",
                   "model.cfdb_dbt.srv_team_overview",
                   "model.cfdb_dbt.srv_teams_index",
                   # cfbd_lines_snapshot — DISTRIBUTION_SELECTOR
                   "model.cfdb_dbt.srv_week_metric_distribution",
                   "model.cfdb_dbt.srv_week_metric_distribution_bin")

EXEMPT_TAG = "full_refresh_only"
# Also excluded by the DAG, so also not a risk to it.
SWEEP_TAG = "slow_sweep"

# A SWEEP IS NOT A COMPARISON, AND THE FIRST VERSION OF THIS CHECK COULD NOT TELL.
#
# "Refs span the boundary" flagged five tests, four of them wrongly. `assert_facts_are_unique_
# on_their_natural_key` reads twelve facts and checks each one independently: a stale
# `fct_team_rating` cannot make `fct_game`'s uniqueness fail. Those had been running in the
# gated DAG for weeks without trouble, which is the empirical proof they are fine.
#
# What separates them cleanly is SIZE. Measured across every test that has hit this:
#
#     straddling comparisons   1-2 relations   (all four instances checked)
#     independent sweeps       8-80 relations
#
# A first version also required the word "join", which cost two of the four: one compares a
# model against a raw SOURCE and one compares two models without the keyword. The size test
# alone separates the real cases from the sweeps with nothing in between, so the join
# requirement was dropped as a filter that only removed true positives.
#
# SOURCES COUNT AS RELATIONS. `assert_derived_record_matches_cfbd_records` compares
# `fct_team_record`, which this DAG advances with every completed game, against
# `raw.raw_records`, which it never refetches. Ignoring sources missed exactly that shape.
#
# THIS IS A HEURISTIC AND THE CEILING IS THE SOFT PART. A straddling comparison across six
# relations would slip through. It sits here because every real instance has had two or fewer,
# and a check with a 4-in-5 false-positive rate gets switched off rather than obeyed — which
# would leave the class unguarded again.
MAX_REFS_FOR_A_COMPARISON = 5


def _ancestors(manifest: dict, node: str, seen=None) -> set:
    seen = seen if seen is not None else set()
    for parent in manifest["nodes"].get(node, {}).get("depends_on", {}).get("nodes", []):
        if parent not in seen:
            seen.add(parent)
            _ancestors(manifest, parent, seen)
    return seen


# 🚨 PER DAG, NOT UNIONED — R-672, AND THE UNION IS WHY THE THIRD INSTANCE GOT THROUGH.
#
# `GATED_SELECTION` above is every gated DAG's roots in one tuple, and `straddling_tests` used
# to union their ancestries into a single `refreshed` set. A model rebuilt by ANY gated DAG
# therefore counted as refreshed for ALL of them.
#
# ⚠️ MEASURED 2026-09-11, and it is exactly that shape:
# `assert_record_through_week_excludes_the_current_week` compares `fct_team_record_week`
# against `fct_game`. The SCORES DAG rebuilds both, so under the union the test looked safe.
# The LINES DAG's distribution selector rebuilds `fct_game` and NOT `fct_team_record_week` —
# so on 2026-09-11 at 16:02 UTC it compared a fresh fct_game against a stale record table,
# returned 2 rows, failed twice, and `publish_distributions` did not run for four hours.
#
# A test can be safe for one gated DAG and straddling for another. The union cannot say that,
# so the selections are kept apart and each is asked its own question.
# ⚠️ AND WHAT EACH DAG EXCLUDES, because the exclusions are no longer the same. R-672:
# `scores_refresh_only` marks a test that ONE gated DAG can satisfy, so only the other one
# excludes it. A guard that assumed a shared exclusion would report a tagged test as
# straddling forever.
DAG_EXEMPT_TAGS = {
    "cfbd_scores_refresh": (),
    "cfbd_lines_snapshot": ("scores_refresh_only",),
}

GATED_DAGS = {
    # cfbd_scores_refresh — SCORES_SELECTOR
    "cfbd_scores_refresh": (
        "model.cfdb_dbt.srv_game",
        "model.cfdb_dbt.srv_team_game_log",
        "model.cfdb_dbt.srv_game_weather",
        "model.cfdb_dbt.srv_team_week",
        "model.cfdb_dbt.srv_game_team",
        "model.cfdb_dbt.srv_odds_board",
        "model.cfdb_dbt.srv_line_movement",
        "model.cfdb_dbt.srv_standings",
        "model.cfdb_dbt.srv_team_overview",
        "model.cfdb_dbt.srv_teams_index",
        "model.cfdb_dbt.srv_team_week_metric_distribution",
    ),
    # cfbd_lines_snapshot — DISTRIBUTION_SELECTOR
    "cfbd_lines_snapshot": (
        "model.cfdb_dbt.srv_week_metric_distribution",
        "model.cfdb_dbt.srv_week_metric_distribution_bin",
    ),
}


def _refreshed_by(manifest: dict, roots) -> set:
    refreshed = set()
    for node in roots:
        refreshed.add(node)
        refreshed |= _ancestors(manifest, node)
    return refreshed


def straddling_tests(manifest: dict) -> list:
    by_dag = {dag: _refreshed_by(manifest, roots) for dag, roots in GATED_DAGS.items()}

    out = []
    for unique_id, node in manifest["nodes"].items():
        if node.get("resource_type") != "test":
            continue
        tags = node.get("config", {}).get("tags", [])
        if EXEMPT_TAG in tags or SWEEP_TAG in tags:
            continue
        # Models AND sources. A source this DAG never refetches sits outside the refresh
        # exactly as an unrefreshed model does, and ignoring them missed one real instance.
        refs = {dep for dep in node.get("depends_on", {}).get("nodes", [])
                if dep.startswith(("model.", "source."))}
        if not refs:
            continue
        if len(refs) > MAX_REFS_FOR_A_COMPARISON:
            continue                       # a sweep over many relations, not a comparison
        for dag, refreshed in sorted(by_dag.items()):
            if any(tag in tags for tag in DAG_EXEMPT_TAGS.get(dag, ())):
                continue
            inside = refs & refreshed
            outside = refs - refreshed
            if inside and outside:
                out.append((node.get("name", unique_id), dag,
                            sorted(inside), sorted(outside)))
                break
    return sorted(out)


def main() -> int:
    if not MANIFEST.exists():
        print(f"::error::{MANIFEST} not found — run `dbt compile` or `dbt build` first")
        return 1
    manifest = json.loads(MANIFEST.read_text())

    tests = [n for n in manifest["nodes"].values() if n.get("resource_type") == "test"]
    # A SCAN THAT FINDS NOTHING IS A CHECK THAT PASSES FOR THE WRONG REASON — the failure
    # `ci/check_page_queries.py` shipped for months.
    if len(tests) < 50:
        print(f"::error::only {len(tests)} tests in the manifest; this check is not seeing "
              f"the project it is supposed to read")
        return 1

    found = straddling_tests(manifest)
    # Which DAGs can satisfy this test, so the message can name the RIGHT remedy.
    manifest_nodes = manifest["nodes"]
    safe_elsewhere = {}
    by_dag = {d: _refreshed_by(manifest, roots) for d, roots in GATED_DAGS.items()}
    for node in manifest_nodes.values():
        if node.get("resource_type") != "test":
            continue
        refs = {dep for dep in node.get("depends_on", {}).get("nodes", [])
                if dep.startswith(("model.", "source."))}
        safe_elsewhere[node.get("name")] = sorted(
            d for d, refreshed in by_dag.items()
            if refs and not (refs - refreshed))

    for name, dag, inside, outside in found:
        short = lambda ids: ", ".join(i.split(".")[-1] for i in ids)   # noqa: E731
        # 🚨 THE REMEDY DEPENDS ON WHETHER ANOTHER GATED DAG CAN STILL RUN IT. R-672: the
        # blunt `full_refresh_only` removes a test from BOTH gated DAGs, and
        # test_single_sided_tests_keep_their_coverage_in_the_partial_rebuild_dags rejects that
        # when one of them rebuilds both sides. Naming the wrong tag here sends the next
        # person straight into that refusal, which is what happened to A105.
        others = [d for d in safe_elsewhere.get(name, []) if d != dag]
        if others:
            remedy = (f"Tag it `scores_refresh_only` — {', '.join(others)} rebuilds both "
                      f"sides and must keep running it")
        else:
            remedy = "Tag it `full_refresh_only` — no gated DAG rebuilds both sides"
        # ⚠️ THE DAG IS NAMED, because "the two-hourly refresh boundary" is now several
        # boundaries and they disagree: R-672's instance was safe under cfbd_scores_refresh
        # and fatal under cfbd_lines_snapshot.
        print(f"::error::{name} straddles {dag}'s refresh boundary: it reads "
              f"[{short(inside)}], which {dag} rebuilds, against "
              f"[{short(outside)}], which it does not. {remedy}, or it will block "
              f"that DAG's publish whenever the two sides are at different refreshes.")
    if found:
        print(f"\n{len(found)} test(s) would stop the site updating on a game day. This is "
              f"the eighth occurrence of one pattern; the tag is the remedy the project "
              f"already uses.")
        return 1

    exempt = sum(1 for n in manifest["nodes"].values()
                 if n.get("resource_type") == "test"
                 and EXEMPT_TAG in n.get("config", {}).get("tags", []))
    print(f"Checked {len(tests)} tests. None straddles the two-hourly refresh boundary "
          f"untagged ({exempt} carry `{EXEMPT_TAG}`).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
