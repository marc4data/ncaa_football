"""A200 — the four things Cowork saw in A199's renders and this round measured.

🚨 THE MEASUREMENTS THESE TESTS PIN ARE IN A BROWSER, NOT HERE. A unit test cannot see a
clipped cell or a table that overflows its box, so what it CAN hold is the decision: which
columns are drawn, what the tag says, that the kickoff carries its day on one string, and
that the SLATE's reason is a mark rather than a colour. The pixel proof lives in
`claude_work/renders/A200_*.png` and in the report's clone-method table.
"""
import ast
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from views import today                                    # noqa: E402

SOURCE = (ROOT / "site" / "views" / "today.py").read_text()
TREE = ast.parse(SOURCE)


def code_of(name: str, inner: str = None) -> str:
    """The SOURCE of a function with its DOCSTRING REMOVED.

    🚨 THIS FILE DOCUMENTS MORE DENSELY THAN IT CODES, so a substring search over a function
    hits the prose ABOUT a thing far more often than the code doing it — three of this
    round's own first-draft tests failed that way, one of them on its own docstring
    (§2.2.1c.1). `ast` answers the question that was actually asked.
    """
    def find(nodes, target):
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target:
                return node
            found = find(getattr(node, "body", []), target)
            if found is not None:
                return found
        return None

    node = find(TREE.body, name)
    assert node is not None, f"no function named {name!r}"
    if inner:
        node = find(node.body, inner)
        assert node is not None, f"no inner function {inner!r} in {name!r}"
    body = node.body
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return "\n".join(ast.get_source_segment(SOURCE, n) for n in body)


SHARED = (ROOT / "site" / "lib" / "schedule_table.py").read_text()
SHARED_TREE = ast.parse(SHARED)


def code_of_shared(name: str) -> str:
    """`code_of`'s twin for the shared module — source without the docstring."""
    node = next(n for n in SHARED_TREE.body
                if isinstance(n, ast.FunctionDef) and n.name == name)
    body = node.body
    if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return "\n".join(ast.get_source_segment(SHARED, n) for n in body)


THEME = (ROOT / "site" / "lib" / "theme.py").read_text()


def _game(**kw):
    row = {"game_id": 1, "start_date": pd.Timestamp("2026-09-26T19:30:00Z"),  # 12:30 PM PT
           "away_team_display": "Oklahoma", "home_team_display": "Georgia",
           "away_rank": float("nan"), "home_rank": 2.0,
           "away_logo_url": "https://cdn.example/a.png",
           "home_logo_url": "https://cdn.example/h.png",
           "network_abbreviation": "ESPN", "spread_current": -13.5,
           "kickoff_time_known": True, "is_completed": False,
           "is_top25_matchup": False, "is_undefeated_close": False,
           "is_added_by_you": False}
    row.update(kw)
    return row


# ── 1. the reason is readable without scrolling at 1440 ───────────────────────────────

def test_the_tags_are_the_short_wording_the_column_was_measured_for():
    """📊 The clone method at 1440: "Undefeated · close line" is 105.1px and
    "Undefeated · close" is 87.8px, against a Why column of 106px including 17.6px of cell
    padding. ⚠️ The long wording did not FIT the column it was sized against."""
    both = today._high_value_reason(
        {"is_top25_matchup": True, "is_undefeated_close": True})
    assert re.findall(r"cfdb-why-tag'>([^<]+)<", both) == ["Top 25", "Undefeated · close"]
    assert "close line" not in both, "the long wording is what overflowed"


def test_the_full_rule_moved_to_the_caption_rather_than_being_lost():
    """🚨 A SHORTER TAG MUST NOT MEAN A VAGUER PAGE. "Undefeated · close" does not say how
    close, so the sentence that does has to be on screen."""
    body = code_of("_looking_forward")
    assert "undefeated FBS team meets a line inside" in body
    assert "Kick-off times are Pacific" in body, (
        "the zone left the cells, so the caption has to carry it")


def test_the_score_columns_are_dropped_only_while_nothing_has_been_played():
    """🚨 96.4px OF EM DASHES IS WHAT MADE THE REASON UNREADABLE, and shortening the tags
    could not close the gap on its own (18.3px of 47.6px, measured).

    ⚠️ BUT A COMPLETED GAME IN THE UPCOMING WEEK MUST STILL SHOW ITS SCORE. A week can hold a
    Tuesday game that is already final, and hiding a real number to buy width is the trade
    this test exists to refuse.
    """
    body = code_of("_looking_forward", inner="render")
    assert 'rows["is_completed"].any()' in body, "the drop must be conditional on the data"
    assert 'c.field not in ("away_points", "home_points")' in body
    # and the condition guards the drop rather than sitting beside it
    drop = body.index('c.field not in ("away_points"')
    guard = body.index("if not played:")
    assert guard < drop, "the columns must come out INSIDE the not-played branch"


def test_schedule_keeps_its_own_columns_and_its_own_clock():
    """✅ THE SHARED MODULE IS NOT TOUCHED. A196 promoted it so Today could render Schedule's
    table; a change there would silently restyle a page this round was not asked to change.

    🚨 THIS ASKS THE FUNCTION, NOT THE FILE. The first draft asserted `"away_points" in SHARED`
    and came back GREEN under a break that deleted the column — because the name also appears
    in the module's SELECT list. A substring hit is not a column (§2.2.1c.2's shape, in a
    test rather than in a prompt).
    """
    from lib import schedule_table

    class _Scope:
        season, season_type, week, conference, division = 2026, "regular", 4, None, "fbs"

        def link(self, page, **kw):
            return f"/{page}"

    fields = [c.field for c in schedule_table.columns(_Scope())]
    assert "away_points" in fields and "home_points" in fields, (
        "Schedule still shows scores; only Looking Forward drops them, and only while "
        "nothing in its frame has been played")
    # and the shared column set knows nothing about this page's condition
    assert "is_completed" not in code_of_shared("columns")
    # Schedule's kickoff still carries its zone, via the shared renderer
    assert "fmt.clock(r.get('start_date'))" in code_of_shared("columns")


# ── 2. the kickoff reads on one line, with its day ────────────────────────────────────

def test_the_kickoff_carries_its_day_and_drops_the_zone():
    """📊 The cell's content box is 80px. "12:30 PM PDT" needs 90px, so 4 of 10 rows wrapped;
    "Sat 12:30 PM" needs 84.7px and the widest of the week needs 84.3px."""
    assert today._lf_kickoff(_game()) == "Sat 12:30 PM"
    assert today._lf_kickoff(
        _game(start_date=pd.Timestamp("2026-09-26T00:00:00Z"))) == "Fri 5:00 PM"
    assert "PDT" not in today._lf_kickoff(_game())


def test_a_missing_kickoff_is_an_em_dash_and_not_a_crash():
    """AC-G.11 and `NaN` is truthy: a game with no instant has no day either."""
    assert today._lf_kickoff(_game(start_date=None)) == "—"
    assert today._lf_kickoff(_game(start_date=pd.NaT)) == "—"


def test_the_day_and_the_time_come_from_ONE_conversion():
    """🚨 R-643's FAMILY. Reading the day off `game_date` and the time off `start_date` makes
    a late kickoff disagree with itself — the two halves must share one converted instant."""
    body = code_of("_lf_kickoff")
    assert "game_date" not in body, "the day must not come from a second column"
    assert body.count("fmt._local(") == 1, "one conversion, used for both halves"


# ── 3. the SLATE labels carry their AP ranks ──────────────────────────────────────────

def test_the_slate_label_carries_the_rank_on_the_side_it_belongs_to():
    assert today._slate_matchup(_game()) == "Oklahoma at #2 Georgia"
    assert today._slate_matchup(
        _game(away_rank=1.0, home_rank=14.0,
              away_team_display="Texas",
              home_team_display="Tennessee")) == "#1 Texas at #14 Tennessee"


def test_an_unranked_side_prints_no_rank_rather_than_nan():
    """🚨 `NaN` IS TRUTHY, and 6 of the 20 rank cells in the real week-4 slate are NaN.
    `if rank` would put `#nan` on every unranked team."""
    both = today._slate_matchup(_game(away_rank=float("nan"), home_rank=float("nan")))
    assert both == "Oklahoma at Georgia"
    assert "nan" not in both.lower() and "#" not in both


def test_a_rank_renders_as_an_integer_not_a_float():
    """The column is a float because it holds NaN; `#2.0 Georgia` is what that costs if the
    cast is forgotten."""
    assert "#2 Georgia" in today._slate_matchup(_game(home_rank=2.0))
    assert "2.0" not in today._slate_matchup(_game(home_rank=2.0))


def test_the_logos_are_drawn_and_a_missing_one_draws_nothing():
    svg = today._slate(pd.DataFrame([_game()]), esc=lambda t: str(t))
    assert svg.count("cfdb-slate-logo") == 2
    bare = today._slate(pd.DataFrame([_game(away_logo_url=float("nan"),
                                            home_logo_url=None)]), esc=lambda t: str(t))
    assert "cfdb-slate-logo" not in bare, "a missing logo draws nothing, not a broken image"
    assert "nan" not in bare.lower()


# ── 4. the SLATE's reason is a mark, and the marks combine ────────────────────────────

def test_every_reason_has_its_own_mark_and_they_combine():
    """🚨 COLOUR ALONE COULD NOT SAY THIS. An added game drew the same grey as
    "Undefeated · close", and a game on both rules drew one blue bar saying only "Top 25"."""
    # ⚠️ COUNT THE CHART'S MARKS, NOT THE LEGEND'S. The key embeds the same three shapes, and
    # the plus carries two classes, so a plain substring count of a one-mark chart reads 5.
    # Only a chart mark is wrapped in `<g><title>`.
    def marks(svg):
        return svg.count("<g><title>")

    one = today._slate(pd.DataFrame([_game(is_top25_matchup=True)]), esc=lambda t: str(t))
    assert marks(one) == 1

    both = today._slate(pd.DataFrame([_game(is_top25_matchup=True,
                                            is_undefeated_close=True)]), esc=lambda t: str(t))
    assert marks(both) == 2, "a game on both rules shows both marks"

    all_three = today._slate(pd.DataFrame([_game(is_top25_matchup=True,
                                                 is_undefeated_close=True,
                                                 is_added_by_you=True)]), esc=lambda t: str(t))
    assert marks(all_three) == 3


def test_the_marks_are_shapes_so_they_survive_a_greyscale_print():
    """⚠️ A198 checked this chart prints. A key keyed on colour alone is a blank key on a
    laser printer, so the three marks must be three different SHAPES."""
    shapes = {today._slate_mark_shape(kind, 6, 6).split()[0]
              for _flag, kind, _label in today._SLATE_MARKS}
    assert len(shapes) == 3, f"three reasons, three shapes, got {shapes}"
    assert {"<circle", "<polygon", "<path"} == shapes


def test_an_added_game_no_longer_draws_the_same_bar_as_an_undefeated_one():
    added = today._slate_bar_class(_game(is_added_by_you=True))
    undef = today._slate_bar_class(_game(is_undefeated_close=True))
    top = today._slate_bar_class(_game(is_top25_matchup=True))
    assert len({added, undef, top}) == 3, (added, undef, top)
    for cls in (added, undef, top):
        assert cls and cls in THEME, f"{cls} has no rule in theme.py"


def test_the_legend_is_on_the_chart_and_names_every_mark():
    """🚨 ON THE CHART, NOT ONLY IN THE CAPTION (A198's version was caption-only)."""
    svg = today._slate(pd.DataFrame([_game(is_top25_matchup=True)]), esc=lambda t: str(t))
    assert "cfdb-slate-key" in svg
    for _flag, _kind, label in today._SLATE_MARKS:
        assert label in svg, f"the legend does not name {label!r}"
    assert svg.index("cfdb-slate-key") < svg.index("cfdb-slate-day"), (
        "the key belongs above the first day, not after the chart")


def test_the_key_swatch_cannot_inherit_the_full_width_chart_rule():
    """🚨 FOUND IN A RENDER, INVISIBLE IN THE MARKUP. `.cfdb-slate svg { width:100% }` also
    matches a 12x12 key swatch, and the legend drew ONE GREY CIRCLE 980px ACROSS."""
    assert ".cfdb-slate .cfdb-slate-key-mark" in THEME, (
        "the override must out-specify `.cfdb-slate svg`")
    rule = THEME[THEME.index(".cfdb-slate .cfdb-slate-key-mark"):]
    rule = rule[:rule.index("}")]
    assert "width:12px" in rule and "height:12px" in rule


def test_the_reason_gutter_is_reserved_rather_than_taken_from_the_bars():
    """The marks sit at a fixed x, so they line up; the plot must shrink to make room or the
    bars would run underneath them."""
    plot = next(line for line in code_of("_slate").splitlines()
                if line.strip().startswith("plot ="))
    assert "_SLATE_WHY_PX" in plot, f"the gutter must come out of the plot width: {plot}"


@pytest.mark.parametrize("flag,kind", [(f, k) for f, k, _l in today._SLATE_MARKS])
def test_each_mark_hovers_with_its_own_name(flag, kind):
    svg = today._slate(pd.DataFrame([_game(**{flag: True})]), esc=lambda t: str(t))
    label = next(lb for f, _k, lb in today._SLATE_MARKS if f == flag)
    assert f"<title>{label}</title>" in svg
