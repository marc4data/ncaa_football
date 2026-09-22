"""A205 — the SLATE's team names link, and the page says how to add a game.

🚨 FIVE OF THIS ROUND'S STAGED BREAKS FIRST REPORTED "RED" AGAINST THIS FILE BEFORE IT
EXISTED. `pytest` exits non-zero when nothing collects, and a verdict that reads the exit code
alone calls an empty run a failing one — **R-758's third mode wearing different clothes**. The
harness now distinguishes "no tests ran" from "a test failed", and these are the tests.
"""
import ast
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from views import today                                    # noqa: E402

SOURCE = (ROOT / "site" / "views" / "today.py").read_text()


class _Scope:
    season = 2026

    def link(self, page, **kw):
        bits = "&".join(f"{k}={v}" for k, v in kw.items())
        return f"/{page}?{bits}" if bits else f"/{page}"


def _team_row(**kw):
    row = {"away_team_display": "Mississippi State", "away_team_slug": "mississippi-state",
           "away_logo_url": "https://cdn.example/a.png", "away_rank": 24.0,
           "away_team_record_display": "3-0", "is_completed": False}
    row.update(kw)
    return row


def code_of(name: str) -> str:
    """A function's source with its docstring stripped (§2.2.1c.1 — the prose about a symbol
    in this file outnumbers the code using it)."""
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


# ── PART 2: the names link ────────────────────────────────────────────────────────────

def test_the_team_name_links_to_the_teams_page():
    """> **MARC, v13 addition 3:** *"For SLATE, the Team names need to by hyperlinks to the
    > Teams page."* — the destination Schedule's own team name uses."""
    cell = today._slate_team(_team_row(), "away", _Scope(), lambda t: str(t))
    assert "href='/team?team=mississippi-state'" in cell
    assert "cfdb-slate-teamlink" in cell


def test_the_link_wraps_the_name_and_leaves_the_record_outside():
    """🚨 R-129's BOUNDARY, AND THE FIRST DRAFT BROKE IT IN A WAY THAT LOOKED FINE.

    📊 The first version opened the anchor at the name's `<span>` and closed it at the FIRST
    `</span>` in the cell — but the **logo box closes at character 152** while the name opens
    at **193**, so the anchor would have closed 41 characters before it opened. Measured on
    the real cell rather than reasoned about.

    ⚠️ And the record must stay OUTSIDE: styling cannot remove a pointer cursor, and dead text
    under one is worse than either state.
    """
    cell = today._slate_team(_team_row(), "away", _Scope(), lambda t: str(t))
    assert ("<a class='cfdb-slate-teamlink' href='/team?team=mississippi-state' "
            "target='_self'><span class='cfdb-team'>Mississippi State</span></a>") in cell
    assert cell.index("</a>") < cell.index("cfdb-team-record"), "the record is outside"
    # and the logo is outside too — it is not a second link to the same place
    assert cell.index("cfdb-logo-box") < cell.index("<a class=")


def test_a_team_with_no_slug_is_plain_text():
    """⚠️ A LINK TO `/team?team=None` IS WORSE THAN A CELL THAT WAS NEVER CLICKABLE
    (`table.team_link`'s own rule, and A203's case). `NaN` is truthy, so every absence is
    tested rather than the convenient one."""
    for missing in (None, float("nan"), "", "   ", pd.NA):
        cell = today._slate_team(_team_row(away_team_slug=missing), "away", _Scope(),
                                 lambda t: str(t))
        assert "cfdb-slate-teamlink" not in cell, missing
        assert "Mississippi State" in cell, missing
        assert "nan" not in cell.lower() and "None" not in cell


def test_the_row_has_two_destinations_and_they_answer_different_questions():
    """⚠️ THE NAME GOES TO THE TEAM; THE GAME GLYPH GOES TO THE MATCHUP. Two targets in one
    row is only confusing if they answer the same question, and these do not."""
    body = code_of("_slate")
    assert "_slate_team(row, 'away', scope, esc)" in body
    assert "_slate_link(row, esc, scope)" in body
    link = code_of("_slate_link")
    assert 'scope.link("matchup"' in link
    team = code_of("_slate_team")
    assert 'scope.link("team"' in team


# ── PART 3: the page says how to add a game ───────────────────────────────────────────

def test_the_section_says_how_to_add_a_game():
    """> **MARC, v13 addition 3:** *"There needs to be some info on how/where to add games to
    > the list on the page (pointing them to the bottom section of the Nav bar and including
    > the game_id, which is available in the URL of the Matchup page."*

    ⚠️ IT NAMES **WHERE** AND **WHAT**, AND SHOWS THE SHAPE RATHER THAN DESCRIBING IT. A reader
    who has seen `game_id=401866418` once in an address bar does not need the word
    "querystring".
    """
    hint = today._ADD_GAMES_HINT
    assert "Add games to Looking Forward" in hint, "it names WHERE"
    assert "bottom" in hint and "sidebar" in hint
    # 🚨 THE EXAMPLE IS CHECKED AGAINST ITS SHAPE, NOT AGAINST ITSELF. The first draft
    # asserted `_ADD_GAMES_EXAMPLE in hint` — and an EMPTY example satisfies that, because
    # `"" in anything` is True. A staged break blanking the constant came back GREEN, which is
    # R-760's family: an assertion that compares the code to itself cannot fail.
    import re as _re
    shown = _re.search(r"game_id=(\d{6,})", hint)
    assert shown, f"the hint must show a real game_id, got: {hint}"
    assert shown.group(1) == today._ADD_GAMES_EXAMPLE
    assert _re.search(r"for example (\d{6,})", hint), "and the bare id on its own"
    assert "Matchup" in hint
    # and the section renders it
    assert "_ADD_GAMES_HINT" in code_of("_looking_forward")


def test_the_hint_is_one_sentence_read_in_two_places():
    """🚨 THE PROMPT'S OWN WARNING: *"do not write a second copy of the rule that can drift."*

    ⚠️ This project's most-repeated failure in miniature. **The constant is the sentence; the
    sidebar box's `help=` points at it**, rather than restating it in words that agree today.
    """
    box = code_of("_looking_forward_box")
    assert "_ADD_GAMES_HINT" in box, "the box reads the shared sentence"
    assert "Paste game_ids or Matchup page links" not in SOURCE, (
        "the box's old hand-written copy of the rule is gone")
    # exactly one definition
    assert SOURCE.count("_ADD_GAMES_HINT = (") == 1


def test_the_hint_survives_the_gate_being_shut():
    """> **A205's prompt:** *"It must stay true when the gate is closed… the line still tells a
    > reader how to queue a game for when the week opens, or it is not shown."*

    ✅ SHOWN. A199 draws the paste box whatever the gate says — a reader lines games up before
    the week opens — so the line that explains it must not vanish at the moment he has time to
    plan.
    """
    body = code_of("_looking_forward")
    splash = body[body.index("if pending:"):body.index("games = _high_value_games(")]
    assert "_ADD_GAMES_HINT" in splash, "the shut-gate branch carries the hint"
    assert splash.count("_ADD_GAMES_HINT") == 2, (
        "both shut-gate captions carry it — with and without pasted ids")
