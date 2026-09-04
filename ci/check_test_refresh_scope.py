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

# What `cfbd_scores_refresh` rebuilds, mirroring SCORES_SELECTOR. `+` pulls ancestors.
GATED_SELECTION = ("model.cfdb_dbt.srv_game",
                   "model.cfdb_dbt.srv_team_game_log",
                   "model.cfdb_dbt.srv_game_weather")

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


def straddling_tests(manifest: dict) -> list:
    refreshed = set()
    for node in GATED_SELECTION:
        refreshed.add(node)
        refreshed |= _ancestors(manifest, node)

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
        inside = refs & refreshed
        outside = refs - refreshed
        if not (inside and outside):
            continue
        if len(refs) > MAX_REFS_FOR_A_COMPARISON:
            continue                       # a sweep over many relations, not a comparison
        out.append((node.get("name", unique_id), sorted(inside), sorted(outside)))
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
    for name, inside, outside in found:
        short = lambda ids: ", ".join(i.split(".")[-1] for i in ids)   # noqa: E731
        print(f"::error::{name} straddles the two-hourly refresh boundary: it reads "
              f"[{short(inside)}], which cfbd_scores_refresh rebuilds, against "
              f"[{short(outside)}], which it does not. Tag it `{EXEMPT_TAG}` or it will block "
              f"`publish_to_serving` whenever the two sides are at different refreshes.")
    if found:
        print(f"\n{len(found)} test(s) would stop the site updating on a game day. This is "
              f"the seventh occurrence of one pattern; the tag is the remedy the project "
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
