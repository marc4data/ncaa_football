"""A204 PART 4 — the close-line cutoff is the reader's, and it rides the URL.

> **MARC, v13 addition 2:** *"Try switching the threshold for close-line cutoff to 6 to see
> how many games it brings in. Can that be drop-down for end-users to manipulate on the fly?"*

📊 THE COUNTS THAT PROMPTED IT, measured against live published serving for 2026 FBS
regular-season games before anything was built — week 4 / season to date:
`< 3` → 2 / 10 · `< 4` → 4 / 19 · `< 6` → 8 / 28 · `< 8` → 12 / 37.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from views import today                                    # noqa: E402
from lib import params                                     # noqa: E402

SOURCE = (ROOT / "site" / "views" / "today.py").read_text()
SHARED = (ROOT / "site" / "lib" / "schedule_table.py").read_text()
MODEL = (ROOT / "dbt" / "models" / "serving" / "srv_game.sql").read_text()


def _row(**kw):
    row = {"is_top25_matchup": False, "is_undefeated_entering": False,
           "is_added_by_you": False, "spread_current": None}
    row.update(kw)
    return row


# ── the default is 4, and 4 is what the published flag means ──────────────────────────

def test_the_default_is_four_and_that_is_marcs_standing_rule():
    """🚨 PINNED DELIBERATELY. 4 is the rule Marc set in A196 and it is what
    `srv_game.is_high_value` still bakes in, so an untouched dropdown and the published flag
    agree. ⚠️ Changing this default silently changes what the page means by "high value"
    without changing anything in dbt."""
    assert today._CLOSE_DEFAULT == 4
    assert today._CLOSE_CHOICES == (3, 4, 6, 8)


def test_at_the_default_the_page_agrees_with_the_published_flag():
    """The two definitions must not drift while they both exist.

    ⚠️ This is the only assertion that ties the page's comparison back to the model's own, and
    it is why `is_undefeated_close` was kept rather than deleted in the same round.
    """
    for spread, entering, expected in [
            (-3.0, True, True), (-3.9, True, True), (-4.0, True, False),
            (-4.0, False, False), (4.5, True, False), (-1.0, False, False),
            (None, True, False), (float("nan"), True, False)]:
        row = _row(is_undefeated_entering=entering, spread_current=spread)
        assert today._is_close(row, 4) is expected, (spread, entering)


def test_the_boundary_is_strictly_inside_the_number():
    """`< n`, not `<= n` — A196 measured 12 games in the corpus at exactly 4.0, so the
    difference is not academic."""
    assert today._is_close(_row(is_undefeated_entering=True, spread_current=6.0), 6) is False
    assert today._is_close(_row(is_undefeated_entering=True, spread_current=5.5), 6) is True


def test_a_wider_cutoff_admits_strictly_more_games():
    """Monotonic by construction, asserted because the dropdown promises it: raising the
    number can only add games, never swap them."""
    rows = [_row(is_undefeated_entering=True, spread_current=s)
            for s in (-1.0, -3.0, -5.5, -6.5, -9.0)]
    counts = [sum(today._is_close(r, cut) for r in rows) for cut in today._CLOSE_CHOICES]
    assert counts == sorted(counts)
    # |−1| |−3| |−5.5| |−6.5| |−9| against 3, 4, 6, 8
    assert counts == [1, 2, 3, 4], counts


def test_a_game_with_no_line_never_qualifies_however_wide_the_cutoff():
    """⚠️ 13 of week 4's 71 FBS games carry no line.

    🚨 AND THE `pd.isna` GUARD IS LOAD-BEARING FOR A REASON THAT IS NOT THE OBVIOUS ONE.
    `abs(float("nan")) < 6` is already False by IEEE, so a float NaN needs no guard at all —
    a staged break removing it came back GREEN and proved this test was decoration (R-760).
    **`pd.NA` is what the guard actually catches**: `float(pd.NA)` RAISES, so without it a
    missing line would take the section's error card instead of failing the rule quietly.
    """
    import pandas as _pd
    for cut in today._CLOSE_CHOICES:
        for absent in (float("nan"), None, _pd.NA, _pd.NaT):
            assert today._is_close(
                _row(is_undefeated_entering=True, spread_current=absent), cut) is False, (
                    cut, absent)


def test_an_undefeated_side_is_required_not_just_a_close_line():
    """A one-point line between two 2-1 teams is a close game and is not this rule."""
    for cut in today._CLOSE_CHOICES:
        assert today._is_close(
            _row(is_undefeated_entering=False, spread_current=-0.5), cut) is False


# ── the parameter, or it is dropped on the next click ─────────────────────────────────

def test_the_cutoff_is_registered_or_a_sort_would_discard_it():
    """🚨 `link_here()` AND `current()` FILTER TO `KNOWN`. This is the `player`/`q` bug and
    then A199's `lf`; the third time it is a test rather than a comment."""
    assert "cut" in params.KNOWN
    assert params.ENUM_PARAMS["cut"] == {"3", "4", "6", "8"}


def test_an_illegal_cutoff_in_the_url_falls_back_rather_than_being_honoured():
    """⚠️ AN ENUM, NOT AN INT, AND THIS IS WHY. `?cut=5` must not produce a page whose caption
    states a rule nobody measured. The fallback is the default, and the caption then says 4.
    """
    body = _code_of("_close_cut_control")
    assert "_CLOSE_CHOICES" in body and "_CLOSE_DEFAULT" in body
    # 🚨 `params.get` RAISES `BadParam` FOR AN UNREGISTERED ENUM VALUE, and NOTHING on the
    # site catches it — grep for it and this control is the only handler. Because the control
    # runs inside `states.section`, an uncaught one would be drawn as "could not display this
    # section": a failure card for a typo in a shared link.
    assert "params.BadParam" in body, (
        "an illegal ?cut= must not reach states.section as a failure card")
    assert "except (params.BadParam, TypeError, ValueError)" in body
    assert "if value not in _CLOSE_CHOICES" in body


def test_the_control_writes_the_url_and_omits_the_default():
    """A URL carrying `cut=4` says nothing the page would not already do, and every extra
    parameter is one more thing to keep true in a shared link."""
    body = _code_of("_close_cut_control")
    assert "params.set_params(cut=" in body
    assert "None if chosen == _CLOSE_DEFAULT" in body


def test_the_control_sits_with_the_section_and_not_in_the_sidebar():
    """⚠️ A199's PASTE BOX IS IN THE SIDEBAR BECAUSE MARC ASKED FOR IT THERE. This one changes
    what a single section lists, so it belongs beside that section where its effect is visible
    in the same glance — and `st.sidebar` in this function would move it."""
    body = _code_of("_close_cut_control")
    assert "st.sidebar" not in body
    assert "st.selectbox(" in body


# ── the SQL, and where the logic lives ────────────────────────────────────────────────

def test_the_cutoff_reaches_sql_as_a_bound_number():
    """⚠️ A READER-SUPPLIED NUMBER IN A QUERY, like A199's ids — bound, never formatted."""
    assert "abs(spread_current) < :close_cut" in SHARED
    assert '"close_cut": close_cut,' in SHARED
    assert "close_cut}" not in SHARED and "+ str(close_cut" not in SHARED


def test_the_definition_half_is_published_and_the_choice_half_is_not():
    """🚨 §4.2.1's LINE, DRAWN WHERE THE ROUND DREW IT.

    *Which teams are undefeated entering a game* has one answer for every consumer, so it is a
    column. *Is the line inside the number this reader picked* has one consumer — this render,
    for this viewer — and there is no value of N that could be published, because N is a
    dropdown.
    """
    # ⚠️ THE COMMA MATTERS. `"as is_undefeated_entering" in MODEL` is satisfied by
    # `as is_undefeated_entering_unused`, and a staged break renaming the column came back
    # GREEN on exactly that. A substring hit is not an alias (§2.2.1c.2's shape).
    assert "as is_undefeated_entering,\n" in MODEL
    assert "is_undefeated_entering" in SHARED, "the page reads the published definition"
    # and the old flag is untouched, so every other reader keeps its meaning
    assert "as is_undefeated_close" in MODEL
    assert "as is_high_value" in MODEL


def test_the_published_flag_still_means_four():
    """⚠️ KEPT ON PURPOSE. `is_high_value` and `is_undefeated_close` are read elsewhere; if
    A204 had redefined them to follow a reader's dropdown, a flag would mean different things
    on different page loads."""
    # ⚠️ SLICED TO is_undefeated_close ALONE. From here to `as is_high_value` the block holds
    # TWO `abs(l.spread) < 4` — one per flag — so a break that changed one left the other to
    # satisfy the assertion, and it came back GREEN.
    start = MODEL.index("as is_undefeated_entering,")
    block = MODEL[start:MODEL.index("as is_undefeated_close")]
    assert block.count("abs(l.spread) < 4") == 1, (
        "is_undefeated_close still bakes in 4, and this slice holds only its copy")


# ── the caption never states a rule the page is not using ─────────────────────────────

def test_the_caption_states_the_number_actually_in_use():
    """🚨 A FIXED "four points" BESIDE A DROPDOWN SET TO 6 WOULD BE THE PAGE DESCRIBING A RULE
    IT IS NOT APPLYING — worse than saying nothing, because it reads as authoritative."""
    # 🚨 STRING LITERALS, NOT RAW SOURCE. `_looking_forward`'s body is ONE `with` statement,
    # so its source segment carries every comment inside it — and the first draft of this test
    # failed on the round's own comment explaining the rule. §2.2.1c.1, in a test again.
    texts = _strings_in("_looking_forward")
    assert any("{close_cut} points" in t for t in texts), texts
    assert not any("four points" in t for t in texts), (
        "a fixed wording would state a rule the dropdown may have changed")


def test_the_tag_and_the_mark_keep_saying_undefeated_close():
    """> **A204's prompt:** *"The reason tag and the SLATE mark keep saying 'Undefeated ·
    > close'; the caption states the current number."* The tag is the rule's NAME, and a name
    that changed with the number would make two readers of one page disagree about what they
    were looking at."""
    labels = [label for _f, _k, label in today._SLATE_MARKS]
    assert "Undefeated · close" in labels
    for n in today._CLOSE_CHOICES:
        assert str(n) not in " ".join(labels)


def _strings_in(name: str) -> list:
    """Every string literal inside a function — comments excluded, by construction."""
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
    out = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            out.append(sub.value)
        elif isinstance(sub, ast.JoinedStr):
            out.append(ast.get_source_segment(SOURCE, sub) or "")
    return out


def _code_of(name: str) -> str:
    """A function's source with its docstring removed — this file documents more densely than
    it codes, so a substring search over the raw text hits the prose about a thing far more
    often than the code doing it (§2.2.1c.1)."""
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


def test_the_cutoff_reaches_the_slate_as_an_argument_not_as_a_passenger():
    """🚨 A204 PUT `_close_cut` ON THE FRAME and A205 TOOK IT OFF AGAIN.

    A204 needed it there because `Col.render` is handed a ROW and nothing else, and the list's
    Why column had to know the reader's number. ⚠️ **A205 removed that column**, so the only
    reader went with it and the passenger became dead weight — a key nothing reads is a key
    the next person has to check before changing.

    ✅ `_slate` takes the cutoff as an argument, which is how it always wanted it.
    """
    body = _code_of("_looking_forward")
    assert "_close_cut=close_cut" not in body, "the dead passenger is gone"
    assert "close_cut=close_cut" in body, "the SLATE is still given the reader's number"
    # and the registry entry went with it — a registered name for a column nobody reads is
    # a stale exemption that outlives the thing it excused
    guard = (Path(__file__).resolve().parents[1] / "ci" / "check_page_reads.py").read_text()
    assert '"_close_cut"' not in guard

    # the reasons themselves still honour the cutoff
    row = _row(is_undefeated_entering=True, spread_current=-5.5)
    assert "is_undefeated_close" in today._reasons(row, 6)
    assert "is_undefeated_close" not in today._reasons(row, 4)
