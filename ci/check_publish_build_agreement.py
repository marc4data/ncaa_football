#!/usr/bin/env python
"""Every table the hot publish ships is either rebuilt by a gated DAG or justified as weekly.

    python ci/check_publish_build_agreement.py

WHY THIS EXISTS. A078 found srv_team_week in HOT_SERVING — shipped by publish_to_serving on
every gate-open run — while SCORES_SELECTOR never rebuilt it. The site was handed Sunday-built
rows arriving beside srv_game rows that had just moved, looking exactly as fresh. Then it
measured the rest of the list and the answer was not one instance: 18 of 24.

THE SHAPE OF THE DEFECT IS TWO LISTS THAT MUST AGREE AND NOTHING CHECKING THAT THEY DO.
src/publish_marts.py decides what ships; dags/*.py decide what is rebuilt. Every run was green
the whole time, because neither list is wrong on its own — they are only wrong about each
other. That is precisely the kind of defect a test has to find, because no run will.

⚠️ SELECTORS ARE READ VIA AST, NOT REGEX. They are multi-line implicitly-concatenated strings
with comments between the fragments, and A078's own comment contains a double-quoted phrase —
a regex over that silently captures half the selector plus some prose, and would then resolve
to the wrong model set without erroring. Ask Python what the value is.

⚠️ AND THE SELECTOR IS RESOLVED WITH `dbt ls`, NOT BY MATCHING NAMES. `+srv_game` pulls
ancestors, which is the entire point of the selector syntax; a name test would say srv_game is
covered and miss that fct_game_team came with it.
"""
import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# (dag file, selector variable, publish-list name) — every gated, partial-rebuild DAG.
#
# 🚨 A184 (cfdb-main-R-1904) ADDED THE THIRD COLUMN, AND IT CHECKS A DIFFERENT RULE FROM THE
# ONE THIS FILE WAS WRITTEN FOR. The original question was about FRESHNESS: is every hot-shipped
# table rebuilt often enough to be worth shipping? The new one is about the GATE: does each DAG
# publish only what that same run built and tested?
#
# 📊 Both were needed, because the first passed while the second was false. Every unbuilt table
# carried a `WEEKLY_BY_DESIGN` justification — "its data only changes weekly" — which is true
# and does not address the gate at all: the weekly DAG's `dbt_run` mutates the warehouse before
# its `dbt_test` decides whether to publish, so a failed weekly test leaves refused rows sitting
# in the warehouse for a two-hourly publish to pick up. A183 measured five such `srv_drive` rows
# live on the site.
GATED = [
    ("dags/scores_refresh_dag.py", "SCORES_SELECTOR", "SCORES_HOT"),
    ("dags/lines_snapshot_dag.py", "DISTRIBUTION_SELECTOR", "DISTRIBUTION_HOT"),
]


def selector_from(path: str, name: str) -> str:
    """The literal value of a module-level selector assignment, via AST."""
    tree = ast.parse((ROOT / path).read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name:
            return ast.literal_eval(node.value)
    raise SystemExit(f"::error::{name} not found in {path}")


def models_for(selector: str) -> set:
    """What the selector actually builds, resolved by dbt rather than inferred."""
    args = selector.replace("--select", "").split()
    # dbt beside the interpreter running this, falling back to PATH. CI installs into a venv
    # and does not necessarily activate it for a subprocess, and a bare "dbt" then fails with
    # a message about the SELECTOR rather than about the executable — which is how you spend
    # ten minutes debugging a selector that was fine.
    dbt = Path(sys.executable).with_name("dbt")
    exe = str(dbt) if dbt.exists() else "dbt"
    # ⚠️ THE PROFILES DIRECTORY IS RESOLVED EXPLICITLY AND ABSOLUTELY, and both halves of
    # that matter. This check ran green locally and died in CI on its first run.
    #
    #   - CI sets DBT_PROFILES_DIR to the RELATIVE path "dbt/profiles_ci", because every other
    #     ci/ step invokes dbt from the repo root. Running with cwd=dbt/ re-anchors it to
    #     dbt/dbt/profiles_ci: "Path 'dbt/profiles_ci' does not exist".
    #   - But running from the ROOT with --project-dir instead does not fix it either: dbt
    #     1.12 does not search the project directory for profiles.yml, so a laptop with no
    #     DBT_PROFILES_DIR then fails with "Could not find profile named 'cfdb_profile'".
    #     The old cwd=dbt/ form only worked because dbt searches the CURRENT directory.
    #
    # So neither cwd alone nor --project-dir alone is right. Resolve the directory against the
    # repo root and pass it, which is correct in both environments and depends on neither.
    env_profiles = os.environ.get("DBT_PROFILES_DIR")
    profiles = (Path(env_profiles) if env_profiles else Path("dbt"))
    if not profiles.is_absolute():
        profiles = ROOT / profiles
    out = subprocess.run(
        [exe, "--no-use-colors", "ls", "--project-dir", str(ROOT / "dbt"),
         "--profiles-dir", str(profiles),
         "--select", *args, "--resource-type", "model"],
        cwd=ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        # stderr is included deliberately: the first CI failure of this check reported
        # "dbt ls failed for '--select …'", which points at the selector when the actual
        # problem was the profiles dir. The selector is almost never the thing that is wrong.
        raise SystemExit(
            f"::error::dbt ls failed. The selector is printed for context, but read the "
            f"error below first — it is usually the environment, not the selector.\n"
            f"  selector: {selector}\n{out.stderr[-2000:]}{out.stdout[-2000:]}")
    return {line.rsplit(".", 1)[-1].strip()
            for line in out.stdout.splitlines() if line.startswith("cfdb_dbt")}


def main() -> int:
    from src.publish_marts import HOT_SERVING, WEEKLY_BY_DESIGN

    import src.publish_marts as pm

    built = set()
    per_dag = {}
    for path, name, publish_name in GATED:
        models = models_for(selector_from(path, name))
        built |= models
        per_dag[publish_name] = (path, name, models)

    unbuilt = [t for t in HOT_SERVING if t not in built]
    unjustified = [t for t in unbuilt if t not in WEEKLY_BY_DESIGN]
    # A justification for something that IS built is stale rather than harmful, but it is a
    # lie in the file a maintainer reads, so it fails too.
    stale = [t for t in WEEKLY_BY_DESIGN if t in built]
    unknown = [t for t in WEEKLY_BY_DESIGN if t not in HOT_SERVING]

    print(f"HOT_SERVING            {len(HOT_SERVING)}")
    print(f"  rebuilt by a gated DAG {len(HOT_SERVING) - len(unbuilt)}")
    print(f"  justified as weekly    {len(unbuilt) - len(unjustified)}")

    problems = False
    if unjustified:
        problems = True
        print(f"\n::error::{len(unjustified)} table(s) are published hot, never rebuilt by a "
              f"gated DAG, and carry no justification in WEEKLY_BY_DESIGN:", file=sys.stderr)
        for t in sorted(unjustified):
            print(f"  - {t}", file=sys.stderr)
        print("\n  Either add it to a gated DAG's selector, or add an entry to "
              "WEEKLY_BY_DESIGN in src/publish_marts.py saying why its data only changes "
              "weekly. A table that is neither is republished unchanged several times a day "
              "and arrives looking as fresh as the rows beside it.", file=sys.stderr)
    if stale:
        problems = True
        print(f"\n::error::{len(stale)} table(s) are justified as weekly but ARE rebuilt by a "
              f"gated DAG — the justification is stale and misleads the next reader:",
              file=sys.stderr)
        for t in sorted(stale):
            print(f"  - {t}", file=sys.stderr)
    if unknown:
        problems = True
        print(f"\n::error::{len(unknown)} entr(y/ies) in WEEKLY_BY_DESIGN are not in "
              f"HOT_SERVING at all:", file=sys.stderr)
        for t in sorted(unknown):
            print(f"  - {t}", file=sys.stderr)

    # ── THE GATE RULE: each DAG publishes only what that run built (cfdb-main-R-1904) ────────
    print()
    for publish_name, (path, selector_name, models) in sorted(per_dag.items()):
        published = set(getattr(pm, publish_name))
        expected = {t for t in HOT_SERVING if t in models}
        print(f"{publish_name:<18} publishes {len(published):>2}  "
              f"built by {selector_name} and hot: {len(expected):>2}")
        ships_unbuilt = sorted(published - expected)
        builds_unshipped = sorted(expected - published)
        if ships_unbuilt:
            problems = True
            print(f"\n::error::{publish_name} publishes {len(ships_unbuilt)} table(s) that "
                  f"{selector_name} does not build, so {path} would ship state its own tests "
                  f"never gated:", file=sys.stderr)
            for t in ships_unbuilt:
                print(f"  - {t}", file=sys.stderr)
            print("\n  A table is published only by a run whose tests covered it, against the "
                  "state being published. Either add it to that DAG's selector or remove it "
                  "from the publish list.", file=sys.stderr)
        if builds_unshipped:
            problems = True
            print(f"\n::error::{selector_name} builds {len(builds_unshipped)} hot table(s) that "
                  f"{publish_name} does not publish, so the rebuild never reaches the site:",
                  file=sys.stderr)
            for t in builds_unshipped:
                print(f"  - {t}", file=sys.stderr)

    if problems:
        return 1
    print("\nEvery hot-published table is either rebuilt by a gated DAG or justified as weekly,")
    print("and every gated DAG publishes exactly what it builds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
