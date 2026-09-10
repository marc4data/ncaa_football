"""Matchup's game-leaders panel: who led, and what they led (R-514).

⚠️ THE DEFECT THIS FILE EXISTS FOR IS OVERCLAIMING, AND IT IS TRUE ON THE FIRST GAME ANYONE
OPENS.

`rank_population` is how many players the ranking ran over. On `passing/YDS` it is **1 in
51.2% of team-games** — one team, one passer — so "Ty Simpson led Alabama in passing" is a
true sentence about a competition that did not happen. Measured across 3,542 games, not
inferred, and `401752665` (Alabama at Florida State, 2025 week 1) has it on both sides.

`highest_tied_players > 1` is the other half. **20.2% of `defensive/TOT` rows end in a tie**,
and the same game has Deontae Lawson on 6 tackles tied three ways over a field of 21. A080
breaks ties with `min()` so the same name returns on every load — **stable is not the same as
sole**, and printing one name alone is a different false claim from the first.

The break was staged: rendering "led the team" from `highest_player_name` alone, with no
reading of `rank_population` or `highest_tied_players`, and pointing it at that game.

⚠️ THE RANKING IS READ, NOT COMPUTED. B076 ended with this item blocked because nothing in
serving ranked players within a game. A080 built `srv_game_team_leader` at
(game_id, team_id, stat_category, stat_type) — one row per QUESTION ASKED, not per player,
which is why it is 296,629 rows and not the 1,201,737 the per-player shape came out at. The
panel reads it with a WHERE and nothing else.
"""
import html
import re
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))

SOURCE = (Path(__file__).resolve().parents[1] / "site" / "views" / "matchup.py").read_text()


def _stub_streamlit():
    captured = []

    def recorder(kind):
        def call(*args, **kwargs):
            captured.append((kind, " ".join(str(a) for a in args)))
        return call

    stub = types.ModuleType("streamlit")
    for name in ("subheader", "caption", "markdown", "write", "info", "warning", "error"):
        setattr(stub, name, recorder(name))

    class _Col:
        def metric(self, label, value, help=None):
            captured.append(("metric", f"{label} {value}"))

        def markdown(self, *args, **kwargs):
            captured.append(("markdown", " ".join(str(a) for a in args)))

    stub.columns = lambda n, **k: [_Col() for _ in range(n if isinstance(n, int) else len(n))]
    stub.button = lambda *a, **k: False
    stub.empty = lambda *a, **k: _Col()

    def cache(*args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return lambda fn: fn

    stub.cache_data = stub.cache_resource = cache
    stub.session_state = {}
    return stub, captured


_RELOAD = ("lib.states", "lib.table", "lib.identity", "lib.shell", "views.matchup")


def _reload_all():
    import importlib
    for name in _RELOAD:
        importlib.reload(importlib.import_module(name))


@pytest.fixture
def panel():
    """`_leaders` with streamlit captured and the query answered from constructed rows.

    ⚠️ IT PUTS THE MODULES BACK — reloading lib.states against a stub binds the stub inside it
    for the rest of the session, which cost test_matchup_drives six unrelated failures.
    """
    real = sys.modules.get("streamlit")
    stub, captured = _stub_streamlit()
    sys.modules["streamlit"] = stub
    _reload_all()
    matchup = sys.modules["views.matchup"]
    seen = {}

    def run(rows):
        captured.clear()
        seen.clear()

        def fake_query(sql, params=None):
            seen["sql"], seen["params"] = sql, params or {}
            seen["calls"] = seen.get("calls", 0) + 1
            return pd.DataFrame(rows)

        matchup.query = fake_query
        matchup._leaders(401752665)
        return list(captured), dict(seen)

    yield run, matchup

    if real is not None:
        sys.modules["streamlit"] = real
    else:
        sys.modules.pop("streamlit", None)
    _reload_all()


# The real slugs serving returns, so an href assertion is about a real destination rather
# than a shape. Read back from srv_game_team_leader for game 401752665.
_SLUGS = {"Ty Simpson": "ty-simpson-4685522",
          "Thomas Castellanos": "thomas-castellanos-4773919"}


def _row(side, category, stat, name, value, tied=1, population=8, **over):
    row = {"team_id": 333 if side == "home" else 96,
           "team": "Florida State" if side == "home" else "Alabama",
           "home_away": side, "stat_category": category, "stat_type": stat,
           "highest_player_name": name,
           "highest_player_slug": _SLUGS.get(name, name.lower().replace(" ", "-")),
           "highest_player_id": 1, "highest_stat_value": value, "highest_stat_raw": str(value),
           "highest_tied_players": tied, "rank_population": population,
           # ⚠️ season IS LOAD-BEARING FOR THE LINK, not decoration. The Players page is
           # season-scoped, and params.link drops any argument that is None — so without this
           # the href would silently lose its season and the assertion would still pass.
           "season": 2025,
           "as_of_ts": pd.Timestamp("2026-09-09T18:00:58Z")}
    row.update(over)
    return row


def _real_game():
    """⚠️ `401752665` EXACTLY AS SERVING RETURNS IT — the numbers were read back, not invented.

    It carries BOTH traps at once: passing is a field of one on each side, and Alabama's
    tackle leader is tied three ways over a field of 21.
    """
    return [
        _row("away", "passing", "YDS", "Ty Simpson", 254, tied=1, population=1),
        _row("away", "receiving", "YDS", "Germie Bernard", 146, tied=1, population=8),
        _row("away", "rushing", "YDS", "Kevin Riley", 31, tied=1, population=6),
        _row("away", "defensive", "TOT", "Deontae Lawson", 6, tied=3, population=21),
        _row("home", "passing", "YDS", "Thomas Castellanos", 152, tied=1, population=1),
        _row("home", "receiving", "YDS", "Jaylin Lucas", 66, tied=1, population=6),
        _row("home", "rushing", "YDS", "Thomas Castellanos", 78, tied=1, population=8),
        _row("home", "defensive", "TOT", "Earl Little II", 9, tied=1, population=20),
    ]


def _text(entries):
    return " ".join(
        re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body))).strip()
        for _, body in entries)


def _cell(entries, name):
    """The rendered fragment carrying one player's name, so a claim can be scoped to them."""
    for _kind, body in entries:
        for chunk in body.split("<div style='display:flex;align-items:flex-start"):
            if name in chunk:
                return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", chunk)))
    return ""


# --- ⚠️ the overclaim, which is the whole round ----------------------------------------------

def test_a_field_of_one_is_not_rendered_as_a_competition_won(panel):
    """THE ASSERTION THIS FILE EXISTS FOR.

    Ty Simpson threw for 254 yards and was Alabama's only passer. Both facts are true; only
    one of them is "led the team". Staged red by rendering the name and value with no reading
    of rank_population — the panel then says Simpson led a field of one, on the first game.
    """
    run, _ = panel
    entries, _ = run(_real_game())
    cell = _cell(entries, "Ty Simpson")
    assert cell, "the passing leader was never drawn"
    assert "only player recorded" in cell, \
        "a field of one rendered as though it were a competition"
    assert "best of" not in cell, "a field of one was described as the best of a field"
    assert "254" in cell, "the figure itself must still be shown — it is a real total"


def test_both_sides_field_of_one_are_caught_not_just_the_first(panel):
    run, _ = panel
    entries, _ = run(_real_game())
    assert "only player recorded" in _cell(entries, "Thomas Castellanos")


def test_a_tie_is_not_rendered_as_a_sole_leader(panel):
    """⚠️ A080 breaks ties with min() so the same name returns every load. STABLE IS NOT SOLE:
    Deontae Lawson's 6 tackles are shared three ways over a field of 21."""
    run, _ = panel
    cell = _cell(run(_real_game())[0], "Deontae Lawson")
    assert cell, "the tackle leader was never drawn"
    assert "tied" in cell, "three players sharing a value rendered as one leader"
    assert "3 of 21" in cell, "the tie was named without saying how many, or out of what"


def test_an_outright_leader_over_a_real_field_says_so(panel):
    """The other half — a caveat that fires on everything indicates nothing."""
    run, _ = panel
    cell = _cell(run(_real_game())[0], "Germie Bernard")
    assert "best of 8" in cell
    assert "tied" not in cell and "only player" not in cell


def test_the_word_led_is_never_used(panel):
    """The verb is the overclaim. The panel shows who, how much, and out of what — and lets
    the reader decide whether that is leading."""
    body = _text(panel[0](_real_game())[0]).lower()
    assert " led " not in body and "leader in" not in body


# --- the ranking is READ ----------------------------------------------------------------------

def test_one_query_for_both_teams_and_every_row(panel):
    """Not one per category. srv_game_team_leader is a different relation from srv_game_team,
    so this is a second read on the tab — correct, and not a G-2 violation."""
    run, _ = panel
    _, seen = run(_real_game())
    assert seen["calls"] == 1, f"the panel issued {seen['calls']} queries"
    assert "game_id" in seen["params"] and "keys" in seen["params"]


def test_the_panel_ranks_nothing(panel):
    """G-3 and the reason A080 exists. The ordering is the object's, not the page's."""
    run, _ = panel
    _, seen = run(_real_game())
    sql = seen["sql"].lower()
    for computed in ("order by", "rank(", "row_number(", "over (", "group by", "sum(", "join"):
        assert computed not in sql, f"the leaders query contains `{computed}`"
    assert "limit 8" in sql, "an unbounded select is a defect (AC-G.39)"


def test_the_composite_key_prevents_a_cross_product(panel):
    """`stat_category = any(...) and stat_type = any(...)` would match passing/TOT. The pairs
    are filtered as pairs."""
    run, matchup = panel
    _, seen = run(_real_game())
    assert "stat_category || '/' || stat_type" in seen["sql"]
    assert set(seen["params"]["keys"]) == set(matchup._LEADER_KEYS)


# --- the cut ------------------------------------------------------------------------------------

def test_the_cut_is_four_rows_and_excludes_the_field_of_one_categories(panel):
    """⚠️ MEASURED BEFORE CHOSEN. kicking is a field of one in 91.3% of team-games and punting
    in 88.8% — "the kicking leader" is a competition that did not happen nine times in ten."""
    _, matchup = panel
    assert len(matchup._LEADER_ROWS) == 4
    categories = [c for _l, c, _s in matchup._LEADER_ROWS]
    for excluded in ("kicking", "punting", "puntReturns", "kickReturns", "fumbles"):
        assert excluded not in categories, f"{excluded} is a field of one most of the time"


def test_no_row_maps_to_the_lowest_end(panel):
    """⚠️ "The player who threw the fewest interceptions" is not a leader, it is a sentence
    nobody wants. Both ends ship because the warehouse cannot know which way a stat reads; the
    page declares the direction, and all four are `highest_*`."""
    code = SOURCE[SOURCE.index("def _leader_cell("):SOURCE.index("def _leaders(")]
    assert "lowest_" not in code, "a row was inverted rather than omitted"
    categories = [c for _l, c, _s in
                  __import__("sys").modules["views.matchup"]._LEADER_ROWS]
    assert "interceptions" not in categories


def test_touchdown_rows_are_excluded(panel):
    """rushing/TD ties 47.3% of the time and receiving/TD 53.3%, because most games have
    several players with exactly one. A row that is a tie more often than not is noise."""
    _, matchup = panel
    assert not [s for _l, _c, s in matchup._LEADER_ROWS if s == "TD"]


# --- the states ---------------------------------------------------------------------------------

def test_a_pre_2024_game_renders_empty_not_a_row_of_blanks(panel):
    """R-509's class, on `62718`.

    ⚠️ AND THE FRAME IS GENUINELY EMPTY HERE, WHICH IS THE OPPOSITE OF THE BOX SCORE ABOVE IT.
    srv_game_team holds an all-NULL row for every game back to 1869; srv_game_team_leader
    covers 2024-2026 and returns NO ROWS for anything earlier — verified: game 62718 returns
    0. The value test is still what is written, because a row arriving with no leader on it is
    the failure a frame check would miss.
    """
    run, _ = panel
    entries, _ = run([])
    body = _text(entries)
    assert "would be here" in body, "the Empty state did not render"
    assert "2024 onward" in body
    assert body.count("—") == 0, f"the panel drew {body.count('—')} em dashes"


def test_rows_present_but_carrying_no_leader_are_still_empty(panel):
    """The value test, and the reason it is written rather than `df.empty`."""
    run, _ = panel
    blank = [dict(r, highest_player_name=None) for r in _real_game()]
    assert "would be here" in _text(run(blank)[0])


def test_a_category_missing_for_both_sides_drops_its_row(panel):
    """⚠️ NOT AN EDGE CASE. defensive/TOT covers 58.1% of games, so tackles are absent on two
    games in five while the other three rows are present. Two dashes would read as "nobody
    made a tackle"."""
    run, _ = panel
    without = [r for r in _real_game() if r["stat_category"] != "defensive"]
    body = _text(run(without)[0])
    assert "Tackles" not in body, "an absent category drew an empty row"
    assert "Receiving yards" in body, "the rest of the panel went with it"


def test_one_side_missing_a_category_still_draws_the_other(panel):
    """Unlike the box score, a leader is a claim about ONE side — so half a row is honest
    here, where half a box score was not."""
    run, _ = panel
    rows = [r for r in _real_game()
            if not (r["home_away"] == "home" and r["stat_category"] == "receiving")]
    body = _text(run(rows)[0])
    assert "Germie Bernard" in body and "Receiving yards" in body


# --- the cadence (R-513) --------------------------------------------------------------------------

def test_the_block_says_its_own_cadence(panel):
    """⚠️ THE BOX SCORE ABOVE IT MOVES TWO-HOURLY AND THIS DOES NOT. The source is
    /games/players in the IMMUTABLE_WK bucket, so it rebuilds Thursday and Sunday — a
    two-hourly rebuild would write byte-identical rows, the false freshness A078 and A079
    spent two rounds removing. One page-level stamp over three cadences is the composition
    failure AC-G.33 is about."""
    body = _text(panel[0](_real_game())[0]).lower()
    assert "thursday" in body and "sunday" in body
    assert "behind the box score" in body


def test_the_qualifiers_are_explained_once_not_per_row(panel):
    body = _text(panel[0](_real_game())[0])
    assert "the field the ranking ran over" in body
    assert body.count("the field the ranking ran over") == 1


# --- R-515: the names go somewhere ------------------------------------------------------------

def _anchors(entries):
    """Every rendered anchor, as (href, visible text)."""
    raw = " ".join(body for _kind, body in entries)
    return re.findall(r'<a href="([^"]*)"[^>]*>([^<]*)</a>', raw)


def test_every_player_name_is_a_link_to_that_player(panel):
    """R-515. Four names on the panel and every one of them routed nowhere."""
    run, _ = panel
    entries, _ = run(_real_game())
    links = _anchors(entries)
    assert len(links) == 8, f"expected eight linked names, found {len(links)}"
    names = {text for _href, text in links}
    assert "Ty Simpson" in names and "Deontae Lawson" in names


def test_the_href_carries_that_players_own_slug(panel):
    """⚠️ NOT ANY SLUG — HIS. A link that reaches the Players page with the wrong athlete
    selected is worse than no link, because it looks like it worked."""
    run, _ = panel
    links = dict((text, href) for href, text in _anchors(run(_real_game())[0]))
    assert "ty-simpson-4685522" in links["Ty Simpson"], \
        f"Ty Simpson's link does not carry his slug: {links['Ty Simpson']}"
    assert "thomas-castellanos-4773919" in links["Thomas Castellanos"]
    assert "ty-simpson" not in links["Deontae Lawson"], "two names share one destination"


def test_the_link_follows_the_roster_pattern_and_carries_all_three_arguments(panel):
    """⚠️ team.py's roster link is the existing furniture and this follows it rather than
    coining a second way. All three arguments are load-bearing: the Players page refuses a
    search term under two characters, `player` picks this athlete out of the matches, and the
    page is season-scoped."""
    run, _ = panel
    href = dict((text, h) for h, text in _anchors(run(_real_game())[0]))["Ty Simpson"]
    assert href.startswith("/players?"), f"the link does not route to Players: {href}"
    for argument in ("q=", "player=ty-simpson-4685522", "season=2025"):
        assert argument in href, f"{argument} is missing from {href}"


def test_a_null_slug_renders_plain_text_and_no_anchor(panel):
    """⚠️ srv_game.sql's OWN RULE: "a null slug is a link to nowhere while a derived one
    reaches a page that renders Empty."

    Measured before deciding which of those two this is: highest_player_slug is null or blank
    on 0 of 296,629 rows, so this branch is unreachable against today's data. Staged red
    anyway — linking unconditionally emits `<a href="/players?q=Ty+Simpson&season=2025">` with
    no player at all, which lands on a search rather than on him.
    """
    run, _ = panel
    rows = [dict(r, highest_player_slug=None) if r["highest_player_name"] == "Ty Simpson"
            else r for r in _real_game()]
    entries, _ = run(rows)
    links = dict((text, href) for href, text in _anchors(entries))
    assert "Ty Simpson" not in links, "a null slug still emitted an anchor"
    assert "Ty Simpson" in _text(entries), "the name vanished instead of going plain"
    assert "Deontae Lawson" in links, "one null slug unlinked the whole panel"


def test_a_blank_slug_is_treated_as_a_null_one(panel):
    run, _ = panel
    rows = [dict(r, highest_player_slug="   ") if r["highest_player_name"] == "Ty Simpson"
            else r for r in _real_game()]
    assert "Ty Simpson" not in dict((t, h) for h, t in _anchors(run(rows)[0]))


def test_an_apostrophe_in_a_name_cannot_break_out_of_the_markup(panel):
    """⚠️ 6,124 leader names carry one — A'Amear Walton — and an unescaped apostrophe closes
    a single-quoted attribute and spills markup onto the page."""
    run, _ = panel
    rows = _real_game()
    rows[0] = dict(rows[0], highest_player_name="A'Amear Walton",
                   highest_player_slug="a-amear-walton-1")
    raw = " ".join(b for _k, b in run(rows)[0])
    assert "A&#x27;Amear Walton" in raw, "the apostrophe was not escaped"
    assert "A'Amear" not in raw, "a raw apostrophe reached the markup"


def test_the_claim_survives_the_link(panel):
    """⚠️ REQUIREMENT 3. A link change must not disturb what the panel is asserting — the
    four honesty properties B077 argued, re-checked here rather than assumed from the fact
    that the other tests still pass."""
    run, _ = panel
    entries, _ = run(_real_game())
    body = _text(entries)
    assert "only player recorded" in _cell(entries, "Ty Simpson")
    assert "tied, 3 of 21" in _cell(entries, "Deontae Lawson")
    assert " led " not in body.lower() and "leader in" not in body.lower()
    code = SOURCE[SOURCE.index("def _leader_name("):SOURCE.index("def _leaders(")]
    assert "lowest_" not in code
