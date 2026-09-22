"""A203 — the Offense/Defense panel's companion table, and the marks it connects to.

📊 THE NUMBERS THESE TESTS REFER TO WERE MEASURED IN A BROWSER, not here. At 1440 with the
sidebar open: row height **30.1px**, 15 rows plus 84px of chrome = **557px** against a chart of
**559px**; **0 of 60 cells clipped**; **15 logos, 0 logo-mark collisions, 5 logo-logo**. They
live in `claude_work/cfdb_report_A203_offense_defense_table.md`.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from views import today                                    # noqa: E402

SOURCE = (ROOT / "site" / "views" / "today.py").read_text()
THEME = (ROOT / "site" / "lib" / "theme.py").read_text()


class _Scope:
    season = 2026

    def link(self, page, **kw):
        bits = "&".join(f"{k}={v}" for k, v in kw.items())
        return f"/{page}?{bits}" if bits else f"/{page}"


def _row(team="Miami", **kw):
    row = {"team": team, "x": 203.0, "y": 702.0, "games": 2,
           "logo_url": "https://cdn.example/m.png", "team_slug": "miami",
           "record_before_display": "2-0", "rank": None}
    row.update(kw)
    return row


def _ranked(n=3):
    """`n` rows, descending by distance, the shape `_distance_ranking` returns."""
    return [(100.0 - i, _row(team=f"Team{i}", y=700.0 - i * 20, x=200.0 + i * 10,
                             team_slug=f"team{i}")) for i in range(n)]


def code_of(name: str) -> str:
    """A function's source with its docstring stripped — this file's prose about a symbol
    outnumbers the code using it (§2.2.1c.1)."""
    tree = ast.parse(SOURCE)

    def find(nodes):
        for node in nodes:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
            found = find(getattr(node, "body", []))
            if found is not None:
                return found
        return None

    node = find(tree.body)
    assert node is not None, f"no function {name!r}"
    body = node.body
    if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return "\n".join(ast.get_source_segment(SOURCE, n) for n in body)


# ── PART 1: the table ─────────────────────────────────────────────────────────────────

def test_gained_and_allowed_are_their_own_columns():
    """> **MARC, v13:** *"Create columns for the Gained and Allowed so the values are
    > vertically aligned"* — not A190's run-together `702 / 203` cell."""
    html = today._distance_table(_ranked(), (300.0, 400.0), 138, scope=_Scope())
    assert ">Gained</th>" in html and ">Allowed</th>" in html
    assert "cfdb-far-slash" not in html, "the run-together cell is gone"
    # one row, four cells, in order
    first = html[html.index("<tbody>"):html.index("</tr>", html.index("<tbody>"))]
    assert first.count("<td") == 4, first


def test_the_columns_are_sized_by_a_colgroup_not_by_the_cells():
    """🚨 `table-layout:fixed` READS THE FIRST ROW. 📊 The widths were on the `td` at first and
    were IGNORED — the browser took them from the `thead`, which carried none, and split the
    space equally: 99.5px each to Team, Gained and Allowed when Team needed **155.3px**.
    **Ten of sixty cells clipped, all of them team names.**"""
    html = today._distance_table(_ranked(), (300.0, 400.0), 138, scope=_Scope())
    cols = re.findall(r"<col(?:\s[^>]*)?>", html)
    assert len(cols) == 4, cols
    assert cols[1] == "<col>", "the team column takes the remainder"
    assert f"width:{today._FAR_NUM_PX}px" in html


def test_the_team_name_links_to_its_team_page():
    """> **MARC, v13:** *"Team name hyperlink to Teams page"* — through `scope.link`, which is
    the destination Schedule's own team name uses."""
    html = today._distance_table(_ranked(), (300.0, 400.0), 138, scope=_Scope())
    hrefs = re.findall(r"class='cfdb-far-link' href='([^']+)'", html)
    assert hrefs == ["/team?team=team0", "/team?team=team1", "/team?team=team2"], hrefs


def test_a_team_with_no_slug_is_plain_text_rather_than_a_link_to_nowhere():
    """⚠️ `table.team_link`'s own rule: a link to `/team?team=None` is worse than a cell that
    was never clickable. `NaN` is truthy, so both absences are tested."""
    for missing in (None, float("nan")):
        html = today._distance_table([(9.0, _row(team_slug=missing))], (300.0, 400.0), 1,
                                     scope=_Scope())
        assert "cfdb-far-link" not in html, missing
        assert "Miami" in html and "nan" not in html.lower()


def test_the_table_still_renders_when_no_scope_is_given():
    """The panel is the only caller, but a table that raises without a scope would turn an
    optional argument into a trap for the next one."""
    html = today._distance_table(_ranked(1), (300.0, 400.0), 138)
    assert "Team0" in html and "cfdb-far-link" not in html


def test_each_column_has_its_own_spark_denominator():
    """> **MARC, v13:** *"Inline spark bars would be helpful"*

    🚨 ONE DENOMINATOR PER COLUMN, over the rows shown — A175's rule, applied per column
    because gained and allowed are different quantities and a shared scale would make every
    Allowed bar a stub. ⚠️ And the 1.15 headroom (A189) survives: the widest bar is 1/1.15 of
    its track, never the whole of it.
    """
    html = today._distance_table(_ranked(3), (300.0, 400.0), 138, scope=_Scope())
    widths = [float(w) for w in re.findall(r"cfdb-far-spark-bar' style='width:([\d.]+)%", html)]
    assert len(widths) == 6, widths
    gained, allowed = widths[0::2], widths[1::2]
    # the widest in each column is the headroom ceiling, not 100%
    assert max(gained) == max(allowed) == round(100 / 1.15, 1), (gained, allowed)
    # and within a column the bars are proportional to the values
    assert gained[2] / gained[0] == pytest_approx(660 / 700), gained


def pytest_approx(value, rel=0.01):
    import pytest
    return pytest.approx(value, rel=rel)


def test_a_missing_value_draws_no_bar_rather_than_a_zero_one():
    """AC-G.11 and `NaN` is truthy: an absent number is not a number of zero."""
    html = today._far_spark(float("nan"), 800.0, "—")
    assert "cfdb-far-spark-bar" not in html
    assert "—" in html
    assert today._far_spark(100.0, 0.0, "100").count("cfdb-far-spark-bar") == 0, (
        "a zero denominator draws no bar rather than dividing by it")


def test_the_bar_sits_beside_the_number_and_not_underneath_it():
    """📊 THE SHARED `.cfdb-spark` COULD NOT BE REUSED AT THIS WIDTH, and the measurement is
    why: the column is 66px, the bar's ceiling is 87% of it, and that leaves **9px for a
    number needing 26px** — the value was drawn ON the bar in this round's first render.
    **A175/A189's RULE is reused; the markup that rule was wrapped in is not.**"""
    assert today._FAR_NUM_PX == 66
    rule = THEME[THEME.index(".cfdb-far-spark {"):]
    assert "display:flex" in rule[:rule.index("}")]
    html = today._far_spark(700.0, 800.0, "700")
    assert html.index("cfdb-far-spark-track") < html.index("cfdb-far-spark-value")


def test_the_type_is_the_sites_normal_table_size():
    """> **MARC, v13:** *"The table needs to be bigger… Font needs to be bigger"* — A190 used
    .72rem to fit six facts on a two-line grid at 18% of the row."""
    rule = THEME[THEME.index(".cfdb-far {"):]
    rule = rule[:rule.index("}")]
    assert "font-size:.9rem" in rule, rule
    table_rule = THEME[THEME.index(".cfdb-table {"):]
    assert "font-size:.9rem" in table_rule[:table_rule.index("}")], (
        "and .9rem is the site's own table size, not a number picked for this table")


def test_fifteen_rows_are_asked_for_and_the_chart_is_sized_to_hold_them():
    """> **MARC, v13:** *"enough real estate to include top 15 or 20"*

    📊 15 rows at 30.1px plus 84px of chrome is **557px**; the chart renders at
    `height x (column width / 560)`, so 490 x 1.141 = **559px** and they end together at 1440.
    ⚠️ **20 was measured and not taken**: it needs 686px of table, which would need a viewBox
    601 units tall against 560 wide — a plot taller than it is wide, squeezing the very axis
    Marc just asked to label "Defense".
    """
    assert today._DISTANCE_TOP_N == 15
    assert today._SCATTER_HEIGHT == 490
    body = code_of("_profile")
    assert "st.columns([66, 34]" in body, "the table needs more than A190's 18%"


def test_the_rank_header_still_says_it_is_the_distance_rank():
    """⚠️ A190's ruling, unchanged: a column headed "#" beside team logos on a page that also
    draws AP polls reads as the AP rank unless it says otherwise."""
    html = today._distance_table(_ranked(), (300.0, 400.0), 138, scope=_Scope())
    assert "This is the distance rank, not the AP rank." in html


def test_the_empty_quadrant_is_a_stated_state():
    html = today._distance_table([], None, 138, scope=_Scope())
    assert "No team in this scope is better than the median on both axes." in html
    assert "<table" not in html


def test_the_footnote_says_which_way_a_long_allowed_bar_reads():
    """🚨 A LONGER "ALLOWED" BAR IS WORSE, and a reader has no way to know that from the bar.
    ⚠️ Inverting it so longer-is-better would be a quantity nobody published, and the number
    beside it would then disagree with its own bar."""
    html = today._distance_table(_ranked(), (300.0, 400.0), 138, scope=_Scope())
    assert "a longer Allowed bar is more yards allowed" in html
    assert "relative to each column's own maximum" in html


# ── PART 2: the marks ─────────────────────────────────────────────────────────────────

def test_a_ranked_team_wears_its_logo_instead_of_a_circle():
    """> **MARC, v13:** *"Instead of putting the second circle around the mark, can you replace
    > the initial circle with the logo for the top 10?"*

    ⚠️ REPLACE, NOT DECORATE — A190's ring is gone AND the circle is gone for these teams,
    which is what makes the logo readable instead of sitting on a stroke.
    """
    rows = [dict(_row(team="Ranked"), accent="light-dark(#000,#fff)",
                 ranked_by_distance=True),
            dict(_row(team="Plain", x=400.0, y=300.0), accent="light-dark(#000,#fff)")]
    svg = today._scatter_svg(rows, (100.0, 500.0), (200.0, 800.0))
    assert svg.count("cfdb-sc-mark-logo") == 1
    assert svg.count("<circle class='cfdb-sc-pt'") == 1, "the ranked team has no circle"
    assert "cfdb-sc-ring" not in svg, "A190's ring is retired, not kept underneath"


def test_the_mark_logo_does_not_reuse_the_hover_tooltips_class():
    """🚨 `cfdb-sc-logo` WAS ALREADY TAKEN by A190's hover, which draws a crest for the team
    AND its opponent inside every hotspot. 📊 The first measurement of this round counted
    **285 "mark logos" for 15 ranked teams** — A190's own `.cfdb-dist` collision, in the same
    panel, one round later."""
    assert "class='cfdb-sc-mark-logo'" in SOURCE
    hover = code_of("_scatter_hotspot")
    assert "cfdb-sc-mark-logo" not in hover, "the two must not share a class"
    assert "cfdb-sc-logo" in hover, "the hover keeps the name it had"


def test_a_ranked_team_with_no_logo_keeps_its_circle():
    """⚠️ `NaN` is truthy. 0.00% null on this relation today is a measurement, not a
    guarantee, and a mark that vanished would be a team silently missing from the chart."""
    for missing in (None, float("nan")):
        rows = [dict(_row(logo_url=missing), accent="light-dark(#000,#fff)",
                     ranked_by_distance=True)]
        svg = today._scatter_svg(rows, (100.0, 500.0), (200.0, 800.0))
        assert "cfdb-sc-mark-logo" not in svg, missing
        assert svg.count("<circle class='cfdb-sc-pt'") == 1, missing
        assert "nan" not in svg.lower()


def test_the_hover_still_opens_over_a_logo_mark():
    """⚠️ A190's HTML hover layer is one hotspot per row, and the mark change must not drop
    the ranked teams out of it — they are the teams the table is about."""
    rows = [dict(_row(team="Ranked"), accent="light-dark(#000,#fff)",
                 ranked_by_distance=True),
            dict(_row(team="Plain", x=400.0, y=300.0), accent="light-dark(#000,#fff)")]
    svg = today._scatter_svg(rows, (100.0, 500.0), (200.0, 800.0))
    # ⚠️ THE CLASS IS `cfdb-sc-hot`, not `cfdb-sc-hotspot`. The first draft asserted a
    # name that appears nowhere and read 0 — a count of a string that cannot occur is the
    # same nothing as a feature that is missing, and only the failure told them apart.
    assert svg.count("class='cfdb-sc-hot'") == 2, "both teams keep a hotspot"
    # and the SVG <title> survives on the logo, which is what a screen reader announces
    assert "<title>Ranked" in svg


def test_the_retired_ring_class_is_gone_from_the_stylesheet_too():
    """A rule nothing emits is a rule the next reader has to check before changing."""
    assert "cfdb-sc-ring {" not in THEME
