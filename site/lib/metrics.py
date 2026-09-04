"""Metric definitions the app is allowed to READ but never to restate.

A threshold is part of a metric definition and lives in `dbt/dbt_project.yml`, because dbt
owns transforms and metric definitions. The app needs the same numbers to LABEL what dbt
computed — and the two must never be typed out twice.

THEY WERE. `views/schedule.py` carried "Upset by 7+" and "Upset by 14+" as string literals
from R-141 until 2026-09-04, and `lib/workbook.py` grew a second reader of its own. Neither
was checked against the warehouse, and the page's numbers were wrong by one at BOTH
boundaries: srv_game classifies with a strict `>`, so a 7-point win is level 1 and a 14-point
win is level 2. 138 completed games carried a level the legend contradicted. The data was
never wrong; only the labels were, which is worse — nothing breaks visibly.

THIS MODULE IS A STOPGAP AND SHOULD SHRINK.
The numbers still reach the app by reading a file, which does not work inside the site image:
`deploy/docker-compose.yml` builds with `context: ./site`, so the repo root is outside the
build context and `dbt_project.yml` is not there. The fallback is correct today and would
silently stop being correct the day a var changes.

The real fix is to carry them as COLUMNS on `srv_game`, exactly as `training_week_floor`
already is (srv_game.sql:445, rendered by srv_edge_finder.sql:77-82). Then the page and the
workbook each read a row they were already fetching, no file access and no fallback, correct
in the container by construction. Filed as R-224; landing with the distribution work, which
touches that view anyway.
"""
from pathlib import Path


def _upset_thresholds() -> tuple:
    """`upset_margin_big` and `upset_margin_blowout`, from dbt's project file.

    NOTHING IN THE APP MAY RETYPE A METRIC DEFINITION. These live in `dbt/dbt_project.yml`
    because a threshold is a metric definition and does not belong in the app — the same rule
    that put them there in the first place. Reading them means the legend cannot go on
    describing a rule the warehouse has stopped applying.

    Parsed rather than imported: the site image has no dbt and no yaml dependency, and adding
    one to read two integers would be a poor trade. Falls back to the shipped values so a
    workbook still builds where the repo is not mounted.
    """
    import re as _re
    project = Path(__file__).resolve().parents[2] / "dbt" / "dbt_project.yml"
    defaults = (7, 14)
    try:
        text = project.read_text(encoding="utf-8")
    except OSError:
        return defaults
    found = []
    for name, fallback in (("upset_margin_big", 7), ("upset_margin_blowout", 14)):
        match = _re.search(rf"^\s*{name}:\s*(\d+)\s*$", text, _re.MULTILINE)
        found.append(int(match.group(1)) if match else fallback)
    return tuple(found)


UPSET_BIG_MARGIN, UPSET_BLOWOUT_MARGIN = _upset_thresholds()
