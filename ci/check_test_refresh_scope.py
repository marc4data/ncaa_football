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
import ast
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
# 🚨 DERIVED FROM THE DAGs, NOT MIRRORED — A185 (cfdb-main-R-1911). THIS WAS A HAND-KEPT LIST
# AND IT WAS ALREADY WRONG.
#
# The block that used to sit here listed each gated DAG's selector roots by hand, and carried
# its own warning twice over: *"Changing the DAG's selector without changing this line leaves
# the straddle check reasoning about the old selection, which fails in the direction that looks
# fine"* and *"a list nobody reads is a list nobody maintains"*.
#
# 📊 IT HAD DRIFTED EXACTLY AS PREDICTED. `srv_team_week_metric_distribution` has been in
# SCORES_SELECTOR since A143 and was never added here, so this check had been reasoning about a
# ten-root selection against an eleven-root DAG — and A185 was about to add three more.
#
# ✅ The selectors are read from the DAG files with `ast.literal_eval`, the same way
# `ci/check_publish_build_agreement.py` reads them, so the two lists cannot disagree because
# there is now only one list. ⚠️ AST rather than a regex for that file's own stated reason:
# these are multi-line implicitly-concatenated strings with comments between the fragments.
GATED = [
    ("cfbd_scores_refresh", "dags/scores_refresh_dag.py", "SCORES_SELECTOR"),
    ("cfbd_lines_snapshot", "dags/lines_snapshot_dag.py", "DISTRIBUTION_SELECTOR"),
]


def _selector_roots(path: str, name: str) -> list:
    """The `+srv_x` roots of a DAG's selector, as manifest unique_ids."""
    tree = ast.parse((Path(__file__).resolve().parents[1] / path).read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name:
            selector = ast.literal_eval(node.value)
            break
    else:
        raise SystemExit(f"::error::{name} not found in {path}")
    roots = []
    for token in selector.replace("--select", "").split():
        model = token.lstrip("+").strip()
        if model:
            roots.append(f"model.cfdb_dbt.{model}")
    return roots


# 🚨 BOTH STRUCTURES COME FROM THE SAME READ. A185 found TWO hand-kept mirrors here, not one:
# `GATED_SELECTION` (the union, already stale) and `GATED_DAGS` (per DAG, which drives the
# error messages and was current). Updating one and not the other is how this check reports a
# straddle against a selection the DAG no longer has — which it did, naming
# `fct_game_win_probability_play` as unrefreshed by a DAG that had just been given it.
GATED_DAGS = {dag: tuple(_selector_roots(path, name)) for dag, path, name in GATED}

GATED_SELECTION = tuple(root for roots in GATED_DAGS.values() for root in roots)

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
