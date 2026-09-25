r"""A225 — the All-weeks player board prints what it ranked, and the KPI numerals share a y.

Each test here is paired with a staged break that was RUN and went red against it; the breaks
and their results are in `claude_work/cfdb_report_A225_the_season_board_prints_what_it_ranked.md`.

## Checked against the three green-first-time patterns the prompt named

- **A COUNT CANNOT SEE A SWAP (B149).** Nothing below counts boards, columns or cards. The
  source test pins the RELATION each filter state reads, by capturing the SQL the call
  actually issues; the fold tests pin `(category, type)` PAIRS, not how many of them there are.
- **A TEST THAT INSPECTS A CONSTANT STAYS GREEN WHEN THE CALL STOPS PASSING IT (B149).** So
  `_player_board` is CALLED with a recording stub rather than read, and `_fold_metrics` is
  CALLED with a frame built to be ambiguous rather than checked for a `subset=` literal.
- **A GUARD CAN BE DOING NOTHING BECAUSE A HELPER ALREADY DOES THE WORK (A216's R-2608).**
  The identity test below is run against BOTH frame shapes — season and game-log — and asserts
  it HOLDS on one and FAILS on the other, so it cannot be passing for a reason unrelated to
  the code under test.
"""
import ast
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))
sys.path.insert(0, str(ROOT / "site" / "views"))

SOURCE = (ROOT / "site" / "views" / "today.py").read_text()
THEME = (ROOT / "site" / "lib" / "theme.py").read_text()


class _Scope:
    season, season_type, division, conference = 2026, "regular", "all", None

    def __init__(self, week):
        self.week = week

    def describe(self):
        return f"2026 regular week {self.week}"


def _sql_code(sql: str) -> str:
    """The SQL with its `--` comments stripped.

    🚨 THIS EXISTS BECAUSE A STAGED BREAK CAUGHT ITS ABSENCE IN THIS FILE'S OWN TESTS.
    A226's first draft put its reasoning inside the season query as `--` comments, and that
    prose contained the words `team_slug`, `week =` and `season_type` — so `"team_slug" in
    sql` was satisfied by the COMMENT. **The break that deleted the column from the SELECT
    left the test green**, and the break that should have proved the `week` filter absent went
    red on a sentence.

    ⚠️ THE PRIMARY FIX WAS NOT THIS HELPER, AND SAYING SO MATTERS. The repo already forbids
    prose between a page query's triple quotes —
    `test_no_page_query_carries_prose_between_its_triple_quotes` — because `--` swallows the
    rest of the line once a query is normalised and `%` is a driver parameter marker. **The
    comments moved out; this is the belt behind that brace**, so an assertion about what a
    query does can never again be answered by what a comment says.

    ⚠️ R-2260 — *a substring is not a rule* — in a codebase where the prose about an
    identifier reliably outnumbers the code using it.
    """
    return "\n".join(line.split("--")[0] for line in sql.splitlines())


def _capture(monkeypatch, week):
    """The SQL `_player_board` ACTUALLY ISSUES for a filter state.

    🚨 THE CALL, NOT THE SOURCE. A test that greps today.py for `srv_player_stats` stays green
    when the branch that reaches it stops being taken — B149's second pattern exactly.
    """
    import today
    seen = []

    def fake_query(sql, binds=None):
        seen.append(sql)
        return pd.DataFrame()

    monkeypatch.setattr(today, "query", fake_query)
    today._player_board(_Scope(week), 10, ("passing",), ("TD", "YDS"))
    assert len(seen) == 1, f"expected exactly one query, got {len(seen)}"
    return seen[0]


def test_WEEK_EQUALS_ALL_READS_THE_SEASON_VIEW(monkeypatch):
    """🚨 THE WHOLE POINT OF THE ROUND. `srv_player_game_log` is one row per player per stat
    per WEEK, so ranking by a window maximum and printing one of the rows prints a different
    number. `srv_player_stats` is one row per player per stat per SEASON, so the figure
    printed IS the figure ranked, by construction."""
    sql = _sql_code(_capture(monkeypatch, None))
    assert "from srv_player_stats" in sql, sql[:400]
    assert "srv_player_game_log" not in sql


def test_A_PICKED_WEEK_STILL_READS_THE_GAME_LOG(monkeypatch):
    """⚠️ AND IT IS A CONSTRAINT, NOT A PREFERENCE: `srv_player_stats` publishes no `week`
    and no `season_type`, so a week-filtered board CANNOT be served from it."""
    sql = _sql_code(_capture(monkeypatch, 3))
    assert "from srv_player_game_log" in sql, sql[:400]
    assert "srv_player_stats" not in sql


def test_THE_SEASON_QUERY_SELECTS_THE_COLUMNS_THE_CARD_NEEDS_TO_LINK(monkeypatch):
    """A226 (cfdb-main-R-3055). `team_slug` is what makes the team abbreviation a LINK.

    🚨 A225 SHIPPED THIS BOARD WITH THE LINK GONE — 📊 16 anchors to 0 on the rendered
    Touchdowns board at week = All — because `_team_identity` builds the href from
    `team_slug` and only the game log carried it. A225 published it on the season view as an
    EXPAND; this asserts the page now reads it.

    ⚠️ AT THE CALL, NOT IN THE SOURCE. A `SOURCE.count("team_slug")` assertion passes while
    the column sits in a comment, in the other branch, or in a docstring — this project has
    paid for that shape repeatedly (R-2260: a substring is not a rule). The SQL the call
    actually issues is the only thing that answers *does the board fetch it*.

    ⚠️ AND A NULL SLUG IS NOT THIS TEST'S SUBJECT: `table.team_link` returns None for one, so
    the card renders unlinked rather than linking to nowhere (R-287). That branch is the
    render measurement's, in `ci/measure_team_links.py`.
    """
    select = _sql_code(_capture(monkeypatch, None)).split("from srv_player_stats")[0]
    for column in ("team_slug", "team_abbreviation", "team_logo_url", "team_display"):
        assert column in select, f"the season query does not select {column}: {select[:400]}"


def test_THE_SEASON_QUERY_DOES_NOT_FILTER_ON_A_COLUMN_THAT_VIEW_LACKS(monkeypatch):
    """A `where week = :week` against `srv_player_stats` would raise `UndefinedColumn` on
    every load — the B121 shape, and the reason §2.2.1c.2 exists."""
    sql = _sql_code(_capture(monkeypatch, None))
    for absent in (" week ", "week =", "season_type"):
        assert absent not in sql, f"the season query references {absent!r}: {sql[:400]}"


# ── the fold, and the identity that is the round's real acceptance ────────────────────────

def _frame(rows):
    return pd.DataFrame(rows)


def _season_rows():
    """One row per (player, category, type) — `srv_player_stats`' grain."""
    out = []
    for slug, name, td, yds in (("a", "Alpha", 14, 970), ("b", "Beta", 12, 1057)):
        out.append(dict(player_slug=slug, player_name=name, team="T",
                        stat_category="passing", stat_type="TD", stat_value=td))
        out.append(dict(player_slug=slug, player_name=name, team="T",
                        stat_category="passing", stat_type="YDS", stat_value=yds))
    return _frame(out)


def _game_log_rows():
    """Several rows per (player, category, type) — one per week, the old shape.

    🚨 ALPHA'S WEEKS ARE 2 THEN 6, AND THE 2 COMES FIRST. That is the defect reproduced: the
    board ranks him by 6 and `drop_duplicates` keeps the 2. A fixture whose first row happened
    to be the maximum would pass either way (R-744).
    """
    out = []
    for slug, name, weekly in (("a", "Alpha", (2, 6)), ("b", "Beta", (5, 1))):
        for week, td in enumerate(weekly, 1):
            out.append(dict(player_slug=slug, player_name=name, team="T", week=week,
                            stat_category="passing", stat_type="TD", stat_value=td))
            out.append(dict(player_slug=slug, player_name=name, team="T", week=week,
                            stat_category="passing", stat_type="YDS", stat_value=td * 70))
    return _frame(out)


def _prints_what_it_ranked(frame):
    """Every folded card's PRIMARY metric equals the value that board RANKED that player by.

    🚨 AND "RANKED BY" IS THE PER-PLAYER MAXIMUM, NOT THE ROW'S OWN `stat_value` — which is
    the first version of this helper and it was VACUOUS. `_fold_metrics` takes the card's
    `stat_value` and its `metric_<primary>` from THE SAME ROW, so comparing them compares a
    value with itself and holds on every frame ever built. The companion test below is what
    caught it: the check passed on the week-grain frame that reproduces the defect.

    ✅ The SQL orders by `max(stat_value) over (partition by player_slug, team)`, so the
    figure a card was ranked by is that maximum, and the defect is precisely that the card
    prints a different row's value. Recomputing the maximum from the input frame is the only
    way to see it from here.
    """
    import today
    specs = [today._metric_spec(e, "passing") for e in ("TD", "YDS")]
    p_cat, p_type = specs[0][1], specs[0][2]
    primary = frame[(frame["stat_category"] == p_cat) & (frame["stat_type"] == p_type)]
    peak = primary.groupby(["player_slug", "team"])["stat_value"].max()
    folded = today._fold_metrics(frame, specs, 10)
    assert folded is not None and not folded.empty, "no cards — the check proves nothing"
    key = specs[0][0]
    return all(float(r[f"metric_{key}"]) == float(peak[(r["player_slug"], r["team"])])
               for _i, r in folded.iterrows()), len(folded)


def test_EVERY_CARD_PRINTS_THE_FIGURE_IT_WAS_RANKED_BY_on_the_season_grain():
    """📊 THE PROPERTY, NOT THE NUMBERS. A test pinned to 14 goes stale next Saturday; the
    identity does not."""
    ok, n = _prints_what_it_ranked(_season_rows())
    assert n >= 2
    assert ok, "a card printed a figure it was not ranked by"


def test_THE_IDENTITY_CHECK_CAN_FAIL_because_the_old_grain_breaks_it():
    """🚨 R-760 AND A216's R-2608 TOGETHER: an assertion that cannot fire is decoration, and a
    guard that passes because something ELSE does the work proves nothing about this code.
    The same check on the game-log grain must FAIL — that is what makes the test above mean
    anything."""
    ok, _n = _prints_what_it_ranked(_game_log_rows())
    assert not ok, ("the identity held on the week-grain frame too, so the test above is not "
                    "measuring what it claims")


def test_THE_FOLD_KEYS_ON_CATEGORY_AND_TYPE_NOT_TYPE_ALONE():
    """A213's R-2540: `YDS` is published under seven categories and `TD` under six. A fold
    keyed on the type alone takes whichever row arrives first.

    ⚠️ THE FIXTURE IS BUILT SO THE WRONG ANSWER IS AVAILABLE AND DIFFERENT — the rushing
    `YDS` row comes FIRST and carries a distinct value, so a type-only fold returns 11 and a
    correct one returns 970."""
    import today
    frame = _frame([
        dict(player_slug="a", player_name="Alpha", team="T",
             stat_category="rushing", stat_type="YDS", stat_value=11),
        dict(player_slug="a", player_name="Alpha", team="T",
             stat_category="passing", stat_type="TD", stat_value=14),
        dict(player_slug="a", player_name="Alpha", team="T",
             stat_category="passing", stat_type="YDS", stat_value=970),
    ])
    specs = [today._metric_spec(e, "passing") for e in ("TD", "YDS", ("rushing:YDS", "RUSH"))]
    folded = today._fold_metrics(frame, specs, 10)
    row = folded.iloc[0]
    assert float(row["metric_YDS"]) == 970.0, "the fold took the rushing YDS for passing YDS"
    assert float(row["metric_rushing:YDS"]) == 11.0


# ── the caption has to describe what the board now does ───────────────────────────────────

def test_THE_CAPTION_DESCRIBES_SEASON_TOTALS_not_a_single_best_week():
    """§3.2.3: a caption a round makes false is worse than none — it is the sentence the next
    reader trusts. A216's wording described ranking by one week and printing another; A225
    removed that behaviour, so the words go with it."""
    import today
    caption = today._ALL_WEEKS_CAPTION
    assert "season totals" in caption
    for gone in ("single best week", "not his season totals", "one of those weeks"):
        assert gone not in caption, f"the caption still says {gone!r}"


def test_THE_CAPTION_IS_ONLY_SHOWN_WHEN_EVERY_WEEK_IS_SELECTED():
    """⚠️ B149's first pattern — a count cannot see a swap. This pins the CONDITION, so a
    caption that started appearing on a week-filtered board would fail rather than merely
    change a total."""
    uses = [n for n in ast.walk(ast.parse(SOURCE))
            if isinstance(n, ast.Name) and n.id == "_ALL_WEEKS_CAPTION"]
    assert len(uses) >= 4, "the caption is defined and never used, or a board lost it"
    assert SOURCE.count("if scope.week is not None\n") >= 3 or \
        SOURCE.count('("" if scope.week is not None') >= 3, \
        "a board shows the All-weeks caption unconditionally"


def test_THE_DECLARED_VIEW_FOLLOWS_THE_FILTER():
    """R-574: `states.section`'s `view` is what the Error state AND the dataset caption both
    render from. With two sources behind one board it has to move with them, or the reader is
    told the season totals came from the game log."""
    assert '_board_view = ("srv_player_stats" if scope.week is None' in SOURCE
    assert 'states.section(_board_view, dataset=DATASETS[_board_view])' in SOURCE


# ── PART 2: the KPI numerals share a baseline ─────────────────────────────────────────────

def test_THE_KPI_NUMERALS_SHARE_A_Y_by_no_label_wrapping_rather_than_by_a_reserve():
    """🚨 THE PROPERTY IS UNCHANGED. THE MECHANISM THAT HOLDS IT IS NOT — A231 (R-3025).

    📊 A216 shipped six numerals at one y and the seventh 17.4px lower, because *"Undefeated
    teams that lost"* was the one label that wrapped. A225 fixed it by RESERVING two lines on
    every label, and this test asserted that reserve — `min-height` being exactly two of the
    label's own line-height.

    ✅ A231 REMOVED THE RESERVE AND THIS TEST WAS REWRITTEN RATHER THAN DELETED (R-2834).
    Marc's shorter wording — *"Undefeated but Lost"* — plus grow-only tiles means **no
    label's text wraps at 1600, 1440, 1300 or 1024 in either scheme**, so the reserve was
    holding 17.4 CSS px of empty space on all seven tiles. A test that goes on demanding the
    old mechanism would block the fix and say nothing about the property.

    ⚠️ AND THE PROPERTY IS NOW ENFORCED WHERE ITS CAUSE IS, IN `tests/test_kpi_row.py`:
    `test_no_kpi_label_is_long_enough_to_wrap` reads the labels the page actually ships and
    fails if one grows past what a tile holds on one line. **The reserve made that failure
    invisible — a long label would simply have used the second line while its numeral sat
    lower than the other six. The budget test makes it loud.**

    This assertion is the other half: the reserve must STAY gone, so that removing the budget
    test cannot quietly restore a silent failure mode.
    """
    block = THEME[THEME.index(".cfdb-kpi-label"):]
    block = block[:block.index("}") + 1]
    import re
    assert re.search(r"line-height:([\d.]+)", block), (
        "the KPI label has no stated line-height")
    assert "min-height" not in block, (
        "the reserved second line is back. If a label now needs it, shorten the label "
        "instead — and see test_no_kpi_label_is_long_enough_to_wrap for the budget.")


def test_THE_KPI_VALUE_DOES_NOT_WRAP():
    """A218's rule: a team name on two lines is a layout, a number on two lines is a lie."""
    block = THEME[THEME.index(".cfdb-kpi-value"):]
    block = block[:block.index("}") + 1]
    assert "white-space:nowrap" in block.replace(" ", "")


@pytest.mark.parametrize("name", ["_player_board", "_fold_metrics", "_ALL_WEEKS_CAPTION"])
def test_THE_NAMES_THIS_FILE_AND_THE_PAGE_SHARE_STILL_EXIST(name):
    """R-2353: a test naming a function that does not exist is worse than silence."""
    assert name in SOURCE
