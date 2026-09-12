"""The Matchup market card and the win-probability bar (R-519, R-526).

⚠️ THIS FILE REPLACES test_matchup_market.py AND test_matchup_line_movement.py, because the
two panels they covered became ONE card. Marc: "Taking up WAY too much space. Develop a card
that we can drop in somewhere to cover both." Their assertions are here, not deleted — the
caveats especially, which are the highest-value things either file carried.

WHAT THIS FILE EXISTS TO CATCH, ranked:

 1. 🚨 THE FAVORITE BEING DERIVED INSTEAD OF READ. `spread_favorite_side` and
    `moneyline_favorite_side` answer the same question of two markets, and
    `favorite_definitions_disagree` flags the 70 games where they differ. A card that took
    the sign of `spread` would render perfectly and would silently pick a side of a question
    the warehouse deliberately recorded as open. The test points the card at the wrong column
    and demands a red.

 2. ⚠️ THE TWO BAR SEGMENTS TRADING PLACES. B081 and B082 both proved a presence assertion
    passes a swap — "both percentages appear" is true either way round. Read positionally.

 3. ⚠️ A CAVEAT GOING MISSING. The book is named on every figure, a single-snapshot game says
    its excursion is the net move restated, and a window spanning the snapshot gap says its
    excursion is a floor. All three render perfectly when absent, which is what makes them
    worth a test rather than a review.

THE FIXTURES ARE REAL ROWS, read back from srv_game:

  401858442  Penn State at Temple, 2026 wk2 — the PRIMARY fixture, chosen because it is the
             only shape that exercises everything: a favorite on the AWAY side (so a card
             that assumed home would pass on a home-favorite row), 17 snapshots, a spread
             move of +2.0 whose excursion is +3.0 — genuinely different numbers — and an
             overround of 1.0539, which is MATERIALLY above 1.

  401754591  Clemson at Louisville, 2025 wk12 — one snapshot, so its excursion equals its net
             move by construction. That is the caveat case, and 1,577 of 1,854 rows share it.

🚨 THE OVERROUND MATTERS AND IT IS A TRAP. A correct de-vig and Marc's sketched one AGREE
EXACTLY when the overround is zero. 401754591 is -145/+145, whose raw implieds sum to 1.0000,
so verifying the de-vig there would show nothing. That is why the primary fixture is the
Temple game.
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


class HarnessGap(BaseException):
    """An un-stubbed `st.*`. BaseException so `except Exception` cannot swallow it.

    ⚠️ DUNDERS ARE EXEMPT. B082 raised on every unknown attribute and hit
    `INTERNALERROR> HarnessGap: the page called st.__file__()` — pytest reads __file__ while
    FORMATTING a failure, so the staged break worked and its evidence vanished.
    """


_PROVIDED = ("markdown", "caption", "subheader", "write", "columns", "divider",
             "info", "warning", "error", "button", "session_state",
             "cache_data", "cache_resource")


def _stub_streamlit():
    captured = []

    def recorder(kind):
        def call(*args, **kwargs):
            captured.append((kind, " ".join(str(a) for a in args)))
        return call

    class _Col:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def markdown(self, *a, **k):
            captured.append(("markdown", " ".join(str(x) for x in a)))

        def caption(self, *a, **k):
            captured.append(("caption", " ".join(str(x) for x in a)))

        def metric(self, label, value, help=None):
            captured.append(("metric", f"{label} {value} {help or ''}"))

        def __getattr__(self, name):
            if name.startswith("__") and name.endswith("__"):
                raise AttributeError(name)
            raise HarnessGap(f"HARNESS GAP: a column called .{name}()")

    class _Stub(types.ModuleType):
        def __getattr__(self, name):
            if name.startswith("__") and name.endswith("__"):
                raise AttributeError(name)
            raise HarnessGap(f"HARNESS GAP: the page called st.{name}(), which this harness "
                             f"does not provide. Provided: {', '.join(_PROVIDED)}")

    stub = _Stub("streamlit")
    for name in ("markdown", "caption", "subheader", "write", "divider",
                 "info", "warning", "error"):
        setattr(stub, name, recorder(name))
    stub.columns = lambda spec, **k: [
        _Col() for _ in range(spec if isinstance(spec, int) else len(spec))]
    stub.button = lambda *a, **k: False

    def cache(*a, **k):
        if len(a) == 1 and callable(a[0]) and not k:
            return a[0]
        return lambda fn: fn

    stub.cache_data = stub.cache_resource = cache
    stub.session_state = {}
    return stub, captured


# ⚠️ `lib.attribution` IS HERE BECAUSE R-596 MADE THIS MODULE CALL `_model`, AND B081 WROTE
# THIS TRAP DOWN ONE ROUND BEFORE IT BIT.
#
# `_model` ends with `attribution.model_attribution(...)`, which holds its own
# `import streamlit`. Reloading the view without reloading that module leaves the licence
# caption emitting into the REAL streamlit — invisible to the capture, and in a full-suite run
# it raises out of streamlit's own bare-mode warning path.
#
# 🚨 IT PASSED ALONE AND IN THIS MODULE, AND FAILED ONLY IN THE FULL SUITE. That is the
# order-dependence A094 found in its own test infrastructure, and the reason the prompt says
# to run every negative test both ways.
_RELOAD = ("lib.states", "lib.table", "lib.identity", "lib.chips", "lib.attribution",
           "views.matchup")


def _reload_all():
    import importlib
    for name in _RELOAD:
        importlib.reload(importlib.import_module(name))


# 🚨 R-605's BOARD READS srv_game_team, SO THE FIXTURE MUST TOO — OR THE SUITE GOES ONLINE.
# `_board` calls `_game_team_rows`, which calls `query`. Left unstubbed these tests opened a
# real connection and took 19 seconds instead of one, which is the ambient-credential failure
# conftest.py exists to prevent, wearing a different hat.
#
# ⚠️ MEASURED FROM srv_game_team FOR 401858442, the module's primary fixture: Penn State away
# at -24, Temple home at +24. The two are MIRRORS and that is the whole point of R-685 — a
# board that read `spread` for both rows would print +24 twice and look entirely reasonable.
_GAME_TEAM = {
    213: {"team_id": 213, "is_home": False, "team_display": "Penn State",
          "spread_final": -24.0},
    218: {"team_id": 218, "is_home": True, "team_display": "Temple",
          "spread_final": 24.0},
}


def _game_team_rows_for(overrides):
    """The stub, honouring `away_spread_final` / `home_spread_final` overrides.

    🚨 WITHOUT THIS A TEST THAT MOVES THE SPREAD MOVES NOTHING. R-605 took the per-side number
    off `srv_game` and onto `srv_game_team`, so `card(spread=-7.5, ...)` no longer touches what
    the board prints — and `test_a_HOME_favorite_is_named_correctly_too` would have passed or
    failed for reasons unrelated to its name. Seven rounds of this page's fixtures have failed
    to distinguish what they claimed to test; this is the eighth caught before it shipped.
    """
    rows = {k: dict(v) for k, v in _GAME_TEAM.items()}
    if "away_spread_final" in overrides:
        rows[213]["spread_final"] = overrides["away_spread_final"]
    if "home_spread_final" in overrides:
        rows[218]["spread_final"] = overrides["home_spread_final"]
    return {k: pd.Series(v) for k, v in rows.items()}


def _make(target):
    real = sys.modules.get("streamlit")
    stub, captured = _stub_streamlit()
    sys.modules["streamlit"] = stub
    _reload_all()
    matchup = sys.modules["views.matchup"]

    def run(**overrides):
        captured.clear()
        matchup._game_team_rows = lambda _g, _o=overrides: _game_team_rows_for(_o)
        row_overrides = {k: v for k, v in overrides.items()
                         if not k.endswith("_spread_final")}
        getattr(matchup, target)(pd.Series(_row(**row_overrides)))
        return list(captured)

    return run, real


@pytest.fixture
def card():
    """`_market_card`, with streamlit captured.

    ⚠️ IT PUTS THE MODULES BACK — reloading lib.states against a stub binds the stub inside it
    for the rest of the session, and test_matchup_drives learned that the hard way.
    """
    run, real = _make("_market_card")
    yield run
    if real is not None:
        sys.modules["streamlit"] = real
    else:
        sys.modules.pop("streamlit", None)
    _reload_all()


@pytest.fixture
def row_panel():
    """`_market_and_model` — the two halves sharing one row (R-596)."""
    run, real = _make("_market_and_model")
    yield run
    if real is not None:
        sys.modules["streamlit"] = real
    else:
        sys.modules.pop("streamlit", None)
    _reload_all()


@pytest.fixture
def bar():
    """`_win_probability_bar`."""
    run, real = _make("_win_probability_bar")
    yield run
    if real is not None:
        sys.modules["streamlit"] = real
    else:
        sys.modules.pop("streamlit", None)
    _reload_all()


def _row(**overrides):
    """srv_game row for 401858442 — Penn State at Temple, 2026 week 2. Read, not invented."""
    row = {
        "game_id": 401858442,
        "away_team": "Penn State", "home_team": "Temple",
        "away_abbreviation": "PSU", "home_abbreviation": "TEM",
        "away_color_on_light": "#041E42", "away_color_on_dark": "#9EA2A2",
        "home_color_on_light": "#9D2235", "home_color_on_dark": "#EAAA00",
        # Temple are +24 at home, so PENN STATE are the favorite — an AWAY favorite, which is
        # what makes a card that assumed "home" fail here rather than in production.
        "spread": 24.0, "over_under": 50.0,
        "home_moneyline": 1100, "away_moneyline": -3300,
        "spread_favorite_side": "away", "moneyline_favorite_side": "away",
        "favorite_definitions_disagree": False,
        "market_implied_home_win_probability": 0.07907,
        "market_implied_away_win_probability": 0.92093,
        # R-605's fourth column, measured from srv_game for this game. ⚠️ THE FIXTURE HAD
        # NEITHER THESE NOR THE TEAM IDS, which is why the board rendered em dashes in both
        # the spread and the implied-points cells — the B083 class exactly: a fixture LESS
        # complete than the query, so the page reads a key nothing supplies.
        "market_implied_home_points": 13.5, "market_implied_away_points": 37.5,
        "home_team_id": 218, "away_team_id": 213,
        "overround": 1.053922, "devig_method": "multiplicative",
        "provider_key": "bovada",
        "line_snapshot_ts": pd.Timestamp("2026-09-10 12:00:25.567931+00:00"),
        "line_movement_provider_key": "draftkings",
        "line_snapshot_count": 17,
        "line_movement_spans_snapshot_gap": False,
        # R-645: the card reads the UNPREFIXED family, which is the same row as `spread` and
        # `over_under` above and the same one the Excel export has always read. The `line_`
        # entries below stay because the EXCURSION caption is still one book's series — and
        # this fixture deliberately gives the two families different books, which is the case
        # that was rendering a Bovada price beside a DraftKings move.
        "spread_move_from_open": 2.0,
        "total_move_from_open": -2.0,
        "line_spread_move_from_open": 2.0,
        "line_spread_largest_excursion": 3.0,
        "line_total_move_from_open": -2.0,
        "line_total_largest_excursion": -2.0,
        "line_market_implied_win_probability_move_from_open": 0.0,
        "line_market_implied_win_probability_largest_excursion": 0.0,
    }
    row.update(overrides)
    return row


def _plain(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()


def _text(entries):
    return " ".join(_plain(b) for _, b in entries)


def _captions(entries):
    return " ".join(_plain(b) for k, b in entries if k == "caption")


def _card_markup(entries):
    """The card block itself — the one markdown that carries the line rows."""
    blocks = [b for k, b in entries if k == "markdown" and "Moneyline" in b or
              (k == "markdown" and "Spread" in b)]
    assert blocks, f"the card did not render; drew {[k for k, _ in entries]}"
    return blocks[0]


# --- 🚨 the favorite, read rather than derived --------------------------------------------------

def test_the_favorite_comes_from_spread_favorite_side(card):
    """🚨 THE ASSERTION THIS FILE EXISTS FOR.

    Penn State are the favorite and they are the AWAY team, so a card that assumed the home
    side, or that read the sign of `spread`, renders "TEM" here. The spread is +24 from the
    home perspective, and the favorite's line is -24 from theirs — same magnitude, and only
    the name in front of it says which side is which.

    🚨 THE TWO COLUMNS ARE MADE TO DISAGREE ON PURPOSE, AND THE FIRST DRAFT OF THIS TEST DID
    NOT DO THAT. On the real row both say "away", so pointing the card at
    `moneyline_favorite_side` — the wrong definition, the exact break this test is named for
    — left it GREEN. Measured, by staging that break. A test whose fixture cannot tell two
    columns apart is not testing which one is read.
    """
    markup = _plain(_card_markup(card(moneyline_favorite_side="home")))
    assert "PSU -24.0" in markup, f"the favorite is not read from the SPREAD column: {markup}"
    assert "TEM -24.0" not in markup, "the card read the moneyline definition"


def test_a_HOME_favorite_is_named_correctly_too(card):
    """The other direction, because a side read one way is half tested."""
    markup = _plain(_card_markup(card(spread=-7.5, spread_favorite_side="home",
                                      home_spread_final=-7.5, away_spread_final=7.5)))
    assert "TEM -7.5" in markup, f"the home favorite's line is wrong: {markup}"
    assert "PSU -7.5" not in markup
    assert "PSU +7.5" in markup, "the underdog did not get the mirror"


def test_no_favorite_side_falls_back_to_the_HOME_PERSPECTIVE_and_says_so(card):
    """⚠️ THE COMMON CASE, NOT THE EDGE ONE: 2,234 of 2025's 3,831 games carry no favorite
    side, because most were never priced by a book cfdb records.

    With no side recorded the number is still true — it is the spread as the column defines
    it — so it renders against the home team's name rather than being guessed or dropped.
    """
    markup = _plain(_card_markup(card(spread_favorite_side=None)))
    assert "TEM +24.0" in markup, f"the home-perspective fallback did not render: {markup}"


def test_the_card_says_so_when_the_two_definitions_DISAGREE(card):
    """🚨 70 GAMES ACROSS THE RECORD, 28 of them in 2025.

    The spread and the moneyline can name different favorites, and the model records that
    rather than resolving it. A card that showed one silently would be deciding a question the
    warehouse left open — so the disagreement is stated, with both names.
    """
    text = _captions(card(favorite_definitions_disagree=True,
                          spread_favorite_side="away", moneyline_favorite_side="home"))
    assert "disagree" in text or "favorite" in text
    assert "PSU" in text and "TEM" in text, \
        "the disagreement caption did not name both sides"


def test_no_disagreement_means_no_caption_about_one(card):
    assert "disagreement" not in _captions(card())


# --- the movement chips -------------------------------------------------------------------------

def test_the_movement_arrow_points_the_way_the_number_MOVED(card):
    """⚠️ ▲/▼ IS MARC'S REQUEST AND THE UNSIGNED MAGNITUDE IS THE ANSWER TO SCHEDULE'S
    OBJECTION. `schedule.py:167` chose Δ deliberately: "a directional glyph beside a negative
    number is two cues that can disagree". Here there is one cue — the arrow — and the number
    beside it carries no sign to contradict it.

    The spread moved +2.0, so the arrow is up and the amount reads 2.0, not +2.0 and not -2.0.
    """
    markup = _plain(_card_markup(card()))
    assert "▲ 2.0" in markup, f"the spread's up-arrow and amount are wrong: {markup}"
    assert "▲ +2.0" not in markup, "the sign is duplicated beside the arrow"


def test_a_downward_move_points_down(card):
    """The total moved -2.0 on this game, which is the other direction on the same card."""
    markup = _plain(_card_markup(card()))
    assert "▼ 2.0" in markup, f"the total's down-arrow is wrong: {markup}"


def test_a_line_that_never_moved_says_UNMOVED_rather_than_drawing_an_arrow(card):
    """Zero has no direction, and an arrow pointing at nothing is a claim about nothing."""
    markup = _plain(_card_markup(card(spread_move_from_open=0.0)))
    assert "unmoved" in markup


def test_a_line_with_no_opening_price_draws_NO_chip_at_all(card):
    """⚠️ A line that did not move and a line with no opening price on record are different
    statements, and only the second one is an absence."""
    markup = _plain(_card_markup(card(spread_move_from_open=None)))
    assert "unmoved" not in markup.split("Over/Under")[0]
    assert "▲" not in markup.split("Over/Under")[0]


# --- the moneylines -----------------------------------------------------------------------------

def _board_rows(markup):
    """The board's two team rows, split on the names, away first.

    ⚠️ R-605 PUT FOUR CELLS BETWEEN THE TEAM NAME AND ITS PRICE, so "PSU -3300" is no longer
    contiguous text and a substring test stopped meaning anything. Splitting on the names is
    the structural form of the same claim — and it is STRONGER, because it says the price is
    in that team's ROW rather than merely somewhere after its name.
    """
    away = markup.split("PSU", 1)[1].split("TEM", 1)[0]
    home = markup.split("TEM", 1)[1]
    return away, home


def test_each_moneyline_sits_beside_its_own_team(card):
    """+1100 and -3300 mean opposite things and a swap renders perfectly."""
    away, home = _board_rows(_plain(_card_markup(card())))
    assert re.search(r"-3,?300", away), f"the away moneyline is not in the away row: {away}"
    assert re.search(r"\+1,?100", home), f"the home moneyline is not in the home row: {home}"
    assert "-3,300" not in home and "-3300" not in home, \
        "the away price leaked into the home row"


# --- absence --------------------------------------------------------------------------------------

def test_a_game_the_books_never_priced_renders_EMPTY_and_draws_no_card(card):
    """Most of 110,634 games predate betting data entirely — an absence of market, not a
    failure to fetch one.

    ⚠️ THE SECOND ASSERTION IS THE ONE THAT MATTERS: B076's lesson is that an Empty state
    rendering ABOVE a card that also drew looks exactly like this test passing.
    """
    entries = card(spread=None, over_under=None, home_moneyline=None, away_moneyline=None)
    body = _text(entries)
    assert "would be here" in body, "the Empty state did not render"
    assert "2013 onward" in body
    assert "Moneyline" not in body, "an unpriced game still drew the card"


def test_a_moneyline_with_no_spread_is_still_a_priced_game(card):
    """The card requires BOTH kinds of price to be absent before it gives up."""
    away, _home = _board_rows(_plain(_card_markup(card(spread=None, over_under=None))))
    assert "-3,300" in away or "-3300" in away


# --- the caveats, which are what the old line-movement file was really for -----------------------

def test_the_book_is_named_AND_LINKED(card):
    """Every figure is ONE book's by construction. A price with no book attached is the
    provenance defect the `market_implied_` prefix rule exists to prevent, and it renders
    perfectly while being wrong.

    R-597: Marc asked for the book by NAME and as a LINK, and explicitly not suppressed into
    the question-mark hover — so this asserts the display name and the href, not the key.

    ⚠️ R-606 MOVED IT FROM A CAPTION INTO THE CARD'S FOOTER. Marc: "Footer underneath the
    card should indicate Provider and when the last metric snapshot was gathered." The book is
    the same book, named the same way and linked the same way — it is furniture now rather
    than prose, so this reads the markup instead of the captions.
    """
    markup = " ".join(b for _k, b in card())
    assert "DraftKings" in markup, "the book is not named in its display form"
    assert "sportsbook.draftkings.com" in markup, "the book is not a link"


def test_an_UNKNOWN_book_renders_its_key_and_NOT_a_dead_link(card):
    """🚨 A LINK THAT 404s IS WORSE THAN PLAIN TEXT. CFBD can add a book tomorrow, and the
    map is this page's own because no provider URL exists anywhere in the warehouse.

    ⚠️ SCOPED TO THE FOOTER, NOT THE WHOLE CARD. The dataset caption carries a legitimate
    link to /dictionary, so "no href anywhere" would fail on a link that is supposed to be
    there — the assertion is about the BOOK, so it reads the block the book lives in.
    """
    markup = " ".join(b for _k, b in card(line_movement_provider_key="newbook",
                                          provider_key="newbook"))
    footer = markup.split("Line from", 1)[1] if "Line from" in markup else ""
    assert "newbook" in footer, f"the unmapped key is not in the footer: {footer[:200]}"
    assert "href" not in footer.split("</div>", 1)[0], \
        "an unmapped book was given a guessed URL"


def test_an_unnamed_book_says_so_rather_than_going_quiet(card):
    markup = " ".join(b for _k, b in card(line_movement_provider_key=None,
                                          provider_key=None))
    assert "an unnamed book" in markup


def test_the_devig_method_and_the_overround_travel_with_the_probabilities(card):
    """A de-vigged number presented without its method or its overround is a derived figure
    wearing the authority of a quoted one."""
    text = _captions(card())
    assert "7.9%" in text, f"the home implied probability is missing: {text}"
    assert "92.1%" in text
    assert "multiplicative" in text
    assert "1.0539" in text, "the overround is not stated at four decimals"


def test_a_SINGLE_SNAPSHOT_game_says_its_excursion_is_the_net_move_restated(card):
    """⚠️ B074'S CAVEAT, AND IT DECIDES WHETHER THE LINE RENDERS AT ALL.

    1,577 of 1,854 rows carry one snapshot. On those the furthest the line got and its net
    move are THE SAME NUMBER by construction, so drawing both would be inventing a second
    fact. The excursion line is not drawn; the caption says why.
    """
    text = _captions(card(line_snapshot_count=1))
    assert "observed once" in text
    assert "Furthest from the open" not in text, \
        "a single-snapshot game drew its excursion as a separate measurement"


def test_a_MULTI_SNAPSHOT_game_does_draw_its_excursions(card):
    """17 snapshots, and the spread's excursion (+3.0) is genuinely not its net move (+2.0)."""
    text = _captions(card())
    assert "Furthest from the open" in text
    assert "spread +3.0" in text, f"the excursion is not the excursion: {text}"


def test_a_window_spanning_the_snapshot_GAP_calls_its_excursion_a_FLOOR(card):
    """Three days in 2026 hold no snapshots. A window spanning them was not observed
    throughout, so the excursion is a floor — the line may have travelled further unobserved
    — and a floor presented as a measurement is the defect the caveat exists to prevent."""
    text = _captions(card(line_movement_spans_snapshot_gap=True))
    assert "floor" in text.lower()


def test_a_game_that_never_spanned_the_gap_does_not_fire_the_caveat(card):
    assert "floor" not in _captions(card()).lower()


def test_the_card_does_not_editorialise(card):
    """A059 measured the distributions and stopped there — Marc sets what counts as a big
    move, so nothing here is called sharp, heavy or significant."""
    text = _text(card()).lower()
    for verdict in ("sharp", "heavy", "significant", "big move", "steam"):
        assert verdict not in text, f"the card editorialised: {verdict!r}"


def test_the_shared_spread_sign_note_is_the_SHARED_one(card):
    """R-009. Compared against `chips.SPREAD_SIGN_NOTE` rather than a copy of its words, so a
    card that inlined its own sentence fails rather than passing a hardcoded string.

    ⚠️ R-607 MOVED WHERE IT IS SHOWN, NOT WHETHER THERE IS ONE OF IT. Marc asked for the
    generic prose to come off the card and into the `?` icons, so this sentence is now the
    Spread hover instead of a caption under the card. The guard is unchanged in substance and
    is the reason `_spread_help()` composes the shared constant rather than retyping it — a
    second copy of one sentence is exactly what R-009 exists to prevent, and moving it into a
    tooltip would have been the easiest possible way to create one.

    🚨 THE `**` IS STRIPPED because a `title=` attribute is plain text; the words are compared,
    the markdown markers are not.
    """
    import re

    from lib import chips
    from views import matchup
    plain_note = re.sub(r"\*\*(.+?)\*\*", r"\1", chips.SPREAD_SIGN_NOTE)
    assert plain_note in matchup._spread_help(), (
        "the Spread hover does not carry the SHARED sign note — if it was retyped, R-009's "
        "one-sentence-one-place rule is already broken")
    # And it reaches the card: the icon renders the hover into the markup.
    markup = " ".join(b for _k, b in card())
    assert html.escape(plain_note, quote=True) in markup, \
        "the sign note is composed but never rendered"


# --- 🚨 R-526: the win probability bar ------------------------------------------------------------

def test_the_two_segments_are_in_AWAY_then_HOME_order(bar):
    """🚨 THE SWAP THAT RENDERS PERFECTLY. Marc: "away on the left, home on the right."

    ⚠️ POSITIONAL. 7.9% and 92.1% both appear whichever way round they are drawn, so
    "both percentages are present" passes the swap — B081 and B082 each proved that on a
    different element. This reads the ORDER: the away width and label must come first.
    """
    markup = [b for k, b in bar() if k == "markdown"][0]
    away_at = markup.index("92.0930%") if "92.0930%" in markup else markup.index("92.09")
    home_at = markup.index("7.9070%") if "7.9070%" in markup else markup.index("7.90")
    assert away_at < home_at, "the home segment was drawn before the away segment"
    text = _plain(markup)
    assert text.index("PSU 92.1%") < text.index("TEM 7.9%"), \
        "the away label is not on the left"


def test_each_percentage_is_beside_its_OWN_team(bar):
    """Penn State are 92.1% and Temple are 7.9% — a swap here inverts the whole game."""
    text = _plain([b for k, b in bar() if k == "markdown"][0])
    assert "PSU 92.1%" in text and "PSU 7.9%" not in text
    assert "TEM 7.9%" in text and "TEM 92.1%" not in text


def test_the_bar_says_the_number_is_the_MARKET_S_and_not_cfdb_s(bar):
    """🚨 §4.3: `market_implied_` names the PROVENANCE and it is a licence boundary wearing a
    naming convention.

    ⚠️ THIS ROUND PUTS A MARKET WIN PROBABILITY ON THE PAGE AND REMOVES A MODEL ONE FROM THE
    PANEL BELOW IT (R-579). A reader must not conclude they are the same number moving, so the
    bar names its source on the bar rather than in a footnote somewhere.
    """
    text = _plain([b for k, b in bar() if k == "markdown"][0]).lower()
    assert "market-implied" in text
    assert "not cfdb" in text or "the book's number" in text


def test_the_bar_COLLAPSES_TO_NOTHING_when_the_book_priced_no_probability(bar):
    """⚠️ MEASURED ON THE ONLY STATE THIS BAR RENDERS IN: 67 of 1,609 upcoming games carry a
    market probability. So the absent state is overwhelmingly the common one, and a reserved
    slot would be dead space on 96% of previews."""
    assert bar(market_implied_home_win_probability=None,
               market_implied_away_win_probability=None) == []


def test_the_away_segment_is_NOT_hardcoded_white():
    """🚨 MARC ASKED FOR WHITE AND WHITE FAILS IN LIGHT THEME — an invisible segment on a
    near-white page. R-547 was exactly this class: a hardcoded colour answering the operating
    system rather than the app.

    Asserted on the source, because the defect is a literal that renders fine in one theme.
    """
    block = SOURCE[SOURCE.index("_NEUTRAL_FILL"):SOURCE.index("def _win_probability_bar(")]
    assert "color-mix" in block and "CanvasText" in block, \
        "the neutral fill is not theme-derived"
    assert "#fff" not in block.lower() and "white" not in block.lower()


def test_no_text_is_drawn_on_top_of_either_fill():
    """⚠️ A team colour cannot be trusted to contrast with text — that is what
    `identity.text_on` exists for. `_drive_bar` on this same page already fills with a team
    colour and puts nothing on it; the labels here sit below the bar for the same reason."""
    block = SOURCE[SOURCE.index("def _win_probability_bar("):SOURCE.index("def row_for_side(")]
    segments = block[block.index("display:flex;height:10px"):block.index("justify-content")]
    assert "%</div>" not in segments, "a percentage was drawn inside a coloured segment"


def test_the_probabilities_are_READ_and_never_recomputed():
    """🚨 MARC SKETCHED A FORMULA THAT IS NOT A DE-VIG — the favorite's implied probability
    with `1 - p` for the underdog assigns the whole vig to one side. The built columns
    normalise both, and doing either sum here would be metric maths in the app (G-3).

    On this fixture the difference is 4.97 points: the built method gives Temple 0.0791, and
    Marc's shape would give 0.0294.
    """
    block = SOURCE[SOURCE.index("def _win_probability_bar("):SOURCE.index("def row_for_side(")]
    for computed in ("1 -", "1-", "/ (", "sum("):
        assert computed not in block.split('st.markdown')[0].replace("1 - p", ""), \
            f"the bar computes rather than reads: {computed!r}"


# --- 🚨 the column list, which is what made the disagreement caption dead code ---------------

# Every srv_game column the card and the bar read off the row. A name here that is missing
# from `matchup.COLUMNS` is a `row.get()` that returns None on every real page load.
_CARD_COLUMNS = (
    "spread", "over_under", "home_moneyline", "away_moneyline",
    "spread_favorite_side", "moneyline_favorite_side", "favorite_definitions_disagree",
    "market_implied_home_win_probability", "market_implied_away_win_probability",
    "market_implied_home_points", "market_implied_away_points",
    "overround", "devig_method", "provider_key", "line_snapshot_ts",
    "spread_move_from_open", "total_move_from_open",
    "line_movement_provider_key", "line_snapshot_count",
    "line_movement_spans_snapshot_gap",
    "line_spread_move_from_open", "line_spread_largest_excursion",
    "line_total_move_from_open", "line_total_largest_excursion",
    "line_market_implied_win_probability_largest_excursion",
    "home_abbreviation", "away_abbreviation",
    "home_color_on_light", "home_color_on_dark",
)


def test_every_column_the_card_reads_is_actually_SELECTED():
    """🚨 THE DEFECT THIS ROUND SHIPPED AND THE LIVE RENDER CAUGHT.

    `favorite_definitions_disagree` and `moneyline_favorite_side` were read by the card and
    were NOT in `COLUMNS`, so `row.get()` returned None on every real page load and the
    disagreement caption was dead code — on all 70 games it exists for.

    ⚠️ NOTHING IN THE SUITE COULD SEE IT. These tests build the row by hand and supply every
    key, so the fixture was more complete than the query. `ci/check_page_queries.py` executes
    the SQL and so cannot notice a column the SQL never asked for. It took rendering the real
    body() against live serving on a game where the flag is true.

    This is the cheap guard for that class: the names the card reads, checked against the
    SELECT the page issues.

    ⚠️ R-669 REPLACED THE PARSE AND THAT WAS THE POINT OF B088. This read
    `COLUMNS.replace("\n", " ").split(",")`, which a single SQL comment can blind in BOTH
    directions — A102 hit the loud one (red on a column that IS selected) and the silent one
    is worse: a comment mentioning a column name between commas puts that name in the
    "selected" set while the query does not select it, which is precisely the defect below
    walking back in through the guard written to catch it. `select_list` is validated against
    the live driver; see its docstring.
    """
    from views import matchup
    import select_list
    selected = select_list.selected_names(matchup.COLUMNS)
    missing = [c for c in _CARD_COLUMNS if c not in selected]
    assert not missing, (
        f"the card reads these columns and the page does not select them, so they are None "
        f"on every load: {missing}")


# --- R-596: the market and the model share a row, market on the LEFT ----------------------------

def test_the_MARKET_is_drawn_before_the_MODEL(row_panel):
    """⚠️ POSITIONAL, NOT PRESENCE. Marc: "Model — move to the right of Market, so they share
    the same row."

    Both headings are on the page whichever order they are drawn in, so "Market appears"
    passes the swap. Presence has now passed this class on the game header, the win-probability
    bar and the yardage columns; this reads the ORDER.
    """
    entries = row_panel(predicted_margin=-7.4, predicted_margin_home_perspective=7.4,
                        predicted_total_points=48.5, home_cover_edge=5.9,
                        home_win_probability=None, training_week_floor=5, week=12,
                        season=2026, attribution="cfdb model, licensed pack")
    text = _text(entries)
    assert "Market" in text and "Model" in text, "one of the two halves did not draw"
    assert text.index("Market") < text.index("Model"), \
        "the model was drawn to the LEFT of the market"


def test_both_halves_keep_their_own_section(row_panel):
    """⚠️ ONE FAILING HALF MUST DEGRADE ONE HALF. They share a row, not a states.section — so
    a market failure still leaves the model drawing and vice versa."""
    import ast
    tree = ast.parse(SOURCE)
    wrapper = next(n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "_market_and_model")
    # ⚠️ THE CODE, NOT THE DOCSTRING. The first draft of this test grepped the source slice
    # and failed on the wrapper's own comment, which SAYS "states.section" while the body
    # correctly does not call it. A test that cannot tell prose from code is not reading code.
    body = ast.dump(ast.Module(body=[n for n in wrapper.body
                                     if not (isinstance(n, ast.Expr)
                                             and isinstance(n.value, ast.Constant))],
                               type_ignores=[]))
    assert "section" not in body, \
        "the row wrapper took a section of its own, so one failure would blank both halves"


# --- 🚨 R-607: generic goes in the hover, THIS GAME stays on the card --------------------------
#
# Marc: "Use the ? icons to provide any supporting information about what the data means. It
# should be generic info about what the metrics mean, not specific info about the lines for the
# Matchup."
#
# 🚨 THE DANGEROUS DIRECTION IS THE ONE THAT LOOKS LIKE TIDYING. Several captions on this card
# are STATEMENTS ABOUT THIS ROW and they exist because the data is genuinely ambiguous:
# `favorite_definitions_disagree` is true on 70 games where the spread and the moneyline name
# different sides; A094 found a game priced −100000/−100000 rendering as a confident 50.0%. A
# future round tidying "too much text about Market" could move one of those into a `?` and it
# would look like progress. These two tests are what makes that fail.


def _titles(blocks):
    """Every `title=` tooltip in the card's markup — i.e. everything the `?` icons say."""
    markup = " ".join(b for _k, b in blocks)
    return re.findall(r"title='([^']*)'", markup)


def test_the_HELP_text_is_IDENTICAL_on_two_different_games(card):
    """🚨 THE STRUCTURAL TEST FOR "GENERIC", AND IT NEEDS NO JUDGEMENT.

    A sentence that is generic reads the same on every game in the database. A sentence about
    THIS row does not. So render two games whose market numbers differ in every field that has
    a caption — the spread, the total, the overround, the snapshot count, the book — and demand
    the hovers come back byte-identical.

    ⚠️ A ROW-SPECIFIC STATEMENT MOVED INTO A `?` FAILS HERE AUTOMATICALLY, because the thing
    that makes it row-specific is the thing that makes it differ between these two renders.
    """
    first = _titles(card())
    second = _titles(card(spread=-12.5, over_under=61.5, overround=1.0102,
                          line_snapshot_count=3, provider_key="espn_bet",
                          market_implied_home_win_probability=0.74,
                          market_implied_away_win_probability=0.26))
    assert first, "the card rendered no help at all"
    assert first == second, (
        "a `?` hover changed between two games, so it is not generic info about what the "
        f"metric means — it is a statement about one row:\n  {first}\n  {second}")


def test_a_ROW_SPECIFIC_caption_still_renders_and_was_not_tidied_away(card):
    """⚠️ THE OTHER HALF. The round removed generic prose; removing these would be a
    regression wearing the same costume.

    Each one is a fact about the game on screen that the warehouse deliberately recorded:
      · the two markets naming different favorites (70 games)
      · this row's overround, which is what the de-vig actually removed
      · the widest the line got, which is not the net move
    """
    blocks = card(favorite_definitions_disagree=True, moneyline_favorite_side="home")
    text = _captions(blocks)
    assert "cfdb records the disagreement rather than resolving it" in text, \
        "B083's favorite-disagreement caption is gone"
    assert "overround" in text, "this row's overround is gone"
    assert "Furthest from the open" in text, "the excursion line is gone"
    # And none of those three moved into a hover, where they would stop being about this game.
    hovers = " ".join(_titles(blocks))
    for leaked in ("overround 1.0", "Furthest from the open", "records the disagreement"):
        assert leaked not in hovers, f"a row-specific statement leaked into a `?`: {leaked!r}"


# --- 🚨 R-605: a derivation must not be dressed as a market ------------------------------------

def test_IMPLIED_POINTS_is_ONE_number_and_never_an_over_under_pair(card):
    """🚨 THIS TEST EXISTS BECAUSE ITS STAGED BREAK WENT GREEN.

    The reference board's fourth column is **Team Total**, a BETTABLE market with an over and
    an under, each separately priced. cfdb's equivalent is DERIVED — `market_implied_*_points`
    is computed from the total and the spread, and no book ever quoted it or took a bet on it.

    ⚠️ RENDERING IT AS `O 37.5 / U 37.5` WOULD LOOK RIGHT AND BE A LIE ABOUT PROVENANCE — the
    R-571 class, and §4.3's rule that `market_implied_` names where a number came from. Nothing
    in the suite caught it until the break was run.

    🚨 THE TOTAL COLUMN BESIDE IT IS LEGITIMATELY SPLIT `O` / `U`, so this is scoped to the
    away row's O-markers: exactly one, the real total. A blanket "no O in the card" would fail
    on the thing that is supposed to be there.
    """
    away, _home = _board_rows(_plain(_card_markup(card())))
    assert "37.5" in away, f"the away implied points are missing: {away}"
    assert len(re.findall(r"\bO\s", away)) == 1, (
        f"the away row carries more than one over-marker, so something other than the total "
        f"is being drawn as a two-sided market: {away}")
    assert not re.search(r"[OU]\s*37\.5", away), (
        "implied points were drawn with an over/under marker — that dresses a derivation as a "
        "quoted market (R-571, §4.3)")


def test_the_IMPLIED_POINTS_column_says_implied(card):
    """The label is the other half of the same guarantee: the column name carries the
    provenance, so a reader is never told this is a price."""
    markup = _plain(_card_markup(card()))
    assert "Implied points" in markup, f"the fourth column is not labelled implied: {markup}"
