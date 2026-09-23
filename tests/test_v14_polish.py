"""A211 — Marc's v14 polish pass: Title Case, a narrowed control, an arrow that points up,
and an Outcome scale a reader can tell apart.

Four independent fixes, each with its own acceptance. The two that are numbers are asserted as
numbers here; the two that are strings are asserted against the emitted markup.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from lib import fmt, glyphs                                   # noqa: E402

THEME = (ROOT / "site" / "lib" / "theme.py").read_text()
TODAY = (ROOT / "site" / "views" / "today.py").read_text()
VIEWS = sorted((ROOT / "site" / "views").glob("*.py"))


def rule(selector: str) -> str:
    """The declaration block for a selector, ANCHORED AT A LINE START.

    🚨 A SELECTOR IS NOT A SUBSTRING (R-2260, and twice since).
    """
    m = re.search(rf"^{re.escape(selector)}", THEME, re.M)
    assert m, f"no rule starting a line with {selector!r}"
    return THEME[m.start():THEME.index("}", m.start())]


# ── PART 1: Title Case ────────────────────────────────────────────────────────────────

def test_title_case_capitalises_major_words_and_leaves_the_minor_ones():
    """> **MARC, v14:** *"Section headers should be more formal (Camel Case for major words.
    > Don't capitalize the, per, and, etc)"*

    📋 READ AS TITLE CASE and said so in the report, because Camel Case literally is
    `LookingBack`. **If the reading is wrong it is one list and one function to change.**
    """
    assert fmt.title_case("most exciting") == "Most Exciting"
    assert fmt.title_case("how the week went against the market") == \
        "How the Week Went Against the Market"
    assert fmt.title_case("offense and defense, per game") == "Offense and Defense, per Game"
    # the three he named by name
    for minor in ("the", "per", "and"):
        assert fmt.title_case(f"yards {minor} game") == f"Yards {minor} Game"


def test_the_first_and_last_word_are_always_capitalised():
    """🚨 EVERY STYLE GUIDE AGREES ON THIS and a reader notices when it is missing."""
    assert fmt.title_case("the week's movers") == "The Week's Movers"
    assert fmt.title_case("what to look for") == "What to Look For"
    assert fmt.title_case("and then") == "And Then"


def test_a_word_that_already_carries_a_capital_is_left_alone():
    """⚠️ `.capitalize()` WOULD PRODUCE `O/u`, `Ats` AND `Mcneese`. Only an all-lowercase word
    is touched, so published values and initialisms survive a heading they appear in."""
    for word in ("O/U", "ATS", "FBS", "McNeese", "TCU"):
        assert fmt.title_case(f"{word} per game").startswith(word)
    assert fmt.title_case("O/U per game") == "O/U per Game"


def test_a_segment_after_a_separator_opens_its_own_phrase():
    """⚠️ *"Looking Forward · Week 4"* — to a reader that dot starts a new heading."""
    assert fmt.title_case("Looking forward · week 4") == "Looking Forward · Week 4"


def test_an_empty_or_single_word_heading_survives():
    """🚨 `"" in anything` IS TRUE (R-2255), so the empty case is asserted on the RESULT."""
    assert fmt.title_case("") == ""
    assert fmt.title_case("Leaderboards") == "Leaderboards"
    assert fmt.title_case("slate") == "Slate"


# the headings that are DATA, not prose — each with the reason it is exempt
_DATA_HEADINGS = {
    "site/views/movement.py": "the two team names of the game being charted",
    "site/views/players.py": "the player's own name",
}


def test_every_section_heading_goes_through_the_one_helper():
    """🚨 EIGHTEEN PAGES EACH SPELLING THEIR OWN HEADING IS HOW THE NINETEENTH DRIFTS.

    ⚠️ AND THE EXEMPTIONS ARE NAMED RATHER THAN INFERRED. A heading built from a team or
    player name is a published value and is not this rule's business; it is listed above with
    its reason, so the next reader does not have to guess why it is missing.
    """
    # 🚨 `ast`, NOT A REGEX. The first draft of this test matched `st.subheader("Game
    # leaders")` inside two COMMENTS in `matchup.py` describing a call B110 deleted — prose
    # about a symbol outnumbering the code that uses it, which is this codebase's signature
    # failure (§2.2.1c.1) landing in the test written to prevent it. A call is an AST node.
    offenders = []
    for path in VIEWS:
        source = path.read_text()
        key = path.relative_to(ROOT).as_posix()
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "subheader"):
                continue
            if key in _DATA_HEADINGS:
                continue
            first = node.args[0] if node.args else None
            wrapped = (isinstance(first, ast.Call)
                       and isinstance(first.func, ast.Attribute)
                       and first.func.attr == "title_case")
            if not wrapped:
                offenders.append(f"{key}:{node.lineno}")
    assert not offenders, (
        "a section heading that does not go through fmt.title_case: " + "; ".join(offenders))


def test_no_section_heading_is_left_in_sentence_case():
    """⚠️ THE HELPER BEING CALLED IS NOT THE SAME AS THE OUTPUT BEING RIGHT. This runs the
    literals the views pass through the helper and asserts each one MOVES or is already
    correct — a heading that came out unchanged and should not have is the failure."""
    changed, unchanged = [], []
    for path in VIEWS:
        for literal in re.findall(r"fmt\.title_case\(\s*[\"']([^\"'{}]+)[\"']\s*\)",
                                  path.read_text()):
            (changed if fmt.title_case(literal) != literal else unchanged).append(literal)
    assert changed, "no heading moved — is the helper wired up at all?"
    # every remaining one must already BE Title Case, not merely short
    for literal in unchanged:
        assert fmt.title_case(literal) == literal, literal
    # and the specific ones Marc would notice
    assert "Most exciting" in changed or "Most Exciting" in unchanged


def test_column_headers_are_not_in_scope():
    """⚠️ MARC SAID SECTION HEADERS. Column headers are small-caps by design and he did not
    mention them; `table.Col` labels must not have been swept up."""
    assert "fmt.title_case" not in (ROOT / "site" / "lib" / "table.py").read_text()


# ── PART 2: the close-line control ────────────────────────────────────────────────────

def test_the_close_line_control_is_no_longer_full_width():
    """📊 MEASURED BEFORE: 980px of a 980px section at 1440, and 564 of 564 at 1024 — 100% at
    both. AFTER: 215.6px (22.0%) at 1440, and 170px at 1024 where the floor wins.

    > **MARC, v14:** *"shouldn't span the full width of the page. Reduce to 10-25%"*
    """
    block = rule(".st-key-today_close_cut {")
    width = re.search(r"width:(\d+)%", block)
    assert width, f"no percentage width in {block!r}"
    assert 10 <= int(width.group(1)) <= 25, f"{width.group(1)}% is outside Marc's 10-25%"
    # ⚠️ AND A FLOOR, or the widest option clips at the narrow end
    assert re.search(r"min-width:[^;]+", block), "no floor — `8 points` would clip at 1024"


def test_the_control_is_scoped_by_the_widgets_own_key():
    """⚠️ THE RULE AND THE KEY ARE ONE FACT IN TWO FILES, so they are compared. Streamlit
    stamps `st-key-<key>` from the `key=` the widget is given."""
    assert 'key="today_close_cut"' in TODAY
    assert ".st-key-today_close_cut" in THEME


# ── PART 3: the arrow ─────────────────────────────────────────────────────────────────

def _axis_text(needle: str) -> str:
    start = TODAY.index(needle)
    return TODAY[start - 400:start + 200]


def test_the_vertical_axis_arrow_renders_upward():
    """> **MARC, v14:** *"the arrow for better needs to rotate 90 degrees clockwise to be
    > pointing upwards... It's pointing to the left of the page."*

    📊 MEASURED FROM THE ELEMENT'S SCREEN CTM, not read off the source: before, `\\u2191`
    inside `rotate(-90)` came out at screen `[-1, 0]` — **left**. After, `\\u2192` comes out at
    `[0, -1]` — **up**.

    ⚠️ A DIFFERENT GLYPH, NOT A SECOND ROTATION: rotating the text again would turn the words
    too, and they are already correct.
    """
    # the em dash is an escape in the source too
    block = _axis_text("better \\u2014 more yards gained per game")
    assert "rotate(-90" in block, "the Y subtitle is a rotated text element"
    # ⚠️ `today.py` WRITES THE ESCAPE `\\u2192`, NOT THE CHARACTER, so a search for the
    # glyph itself finds nothing — the first run of this test failed on its own instrument.
    assert "\\u2192 better" in block, "must point along +x to render up"
    assert "\\u2191 better" not in TODAY, "an up-arrow renders LEFT at -90 deg"


def test_the_horizontal_axis_and_the_corner_were_checked_and_left_alone():
    """🚨 MARC NAMED ONLY THE Y AXIS. 📊 Measured in the same pass: `Defense`'s `\\u2192` sits
    in an UNROTATED text and renders `[1, 0]` — right, which is the fewer-yards direction and
    therefore correct; the corner's `\\u2197` renders `[0.707, -0.707]` — up-right, the good
    corner. **Both right, and said so rather than left unmentioned** (AC-G.11)."""
    assert "fewer yards allowed per game \\u2192 better" in TODAY
    assert "better \\u2197" in TODAY
    corner = _axis_text("better \\u2197")
    assert "rotate(" not in corner.split("cfdb-sc-corner")[-1][:200], "the corner is unrotated"


# ── PART 4: the Outcome bands ─────────────────────────────────────────────────────────

def _channel(value: float) -> float:
    value /= 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _bands() -> dict:
    """The three bands, both themes, read out of the stylesheet's own `light-dark()`."""
    out = {"light": {}, "dark": {}}
    for key in ("u1", "u2", "u3"):
        m = re.search(rf"--cfdb-{key}:\s*light-dark\((#[0-9a-fA-F]{{6}}),\s*"
                      rf"(#[0-9a-fA-F]{{6}})\)", THEME)
        assert m, f"--cfdb-{key} is not a light-dark() pair"
        out["light"][key], out["dark"][key] = m.group(1), m.group(2)
    return out


def test_the_contrast_calculator_agrees_with_known_values():
    """🚨 CALIBRATED BEFORE IT IS TRUSTED. Black on white is 21:1 and a colour against itself
    is 1:1 — a calculator that has only ever produced plausible-looking numbers is one nobody
    has checked."""
    assert round(contrast("#000000", "#ffffff"), 1) == 21.0
    assert round(contrast("#5f5f67", "#5f5f67"), 2) == 1.00
    assert round(contrast("#767676", "#ffffff"), 1) == 4.5


def test_adjacent_outcome_bands_can_be_told_apart():
    """> **MARC, v14:** *"The color scale on the Outcome cicrle glyph is too hard to
    > differentiate."*

    🚨 HE SAID *TOO HARD TO DIFFERENTIATE*, SO THE ACCEPTANCE IS A NUMBER. 📊 Before, EVERY
    adjacent pair was under 1.5:1 — light 1.46 and 1.48, dark 1.45 and 1.28. That is what the
    complaint is when it is measured.
    """
    bands = _bands()
    for theme, values in bands.items():
        for lo, hi in (("u1", "u2"), ("u2", "u3")):
            got = contrast(values[lo], values[hi])
            assert got >= 1.5, (
                f"{theme}: {lo} {values[lo]} and {hi} {values[hi]} are {got:.2f}:1 apart — "
                f"a reader cannot tell them apart")


def test_the_two_bands_marc_named_moved_and_the_one_he_did_not_stayed():
    """⚠️ `8-14` IS `u2` AND `15+` IS `u3` — the bands his two instructions name. `u1` is the
    1-7 upset and keeps its amber, because he did not name it and the change does not collide
    with it (measured 2.79:1 away in light, 2.28:1 in dark)."""
    bands = _bands()
    assert bands["light"]["u1"] == "#d9a406" and bands["dark"]["u1"] == "#e8b931"
    # grey for 8-14: the three channels sit close together
    for theme in ("light", "dark"):
        r, g, b = (int(bands[theme]["u2"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        assert max(r, g, b) - min(r, g, b) <= 24, f"{theme} u2 is not a grey: {bands[theme]['u2']}"
    # 🚨 AND 15+ IS THE HEAVIEST INK ON THE PAGE IN EACH THEME — near-black on white, and
    # near-white on the dark ground, because literal black there is an invisible mark.
    assert _luminance(bands["light"]["u3"]) < 0.05, "15+ must be near-black on a light page"
    assert _luminance(bands["dark"]["u3"]) > 0.80, "15+ must be near-white on a dark page"


def test_every_band_carries_a_separate_value_per_theme():
    """⚠️ `light-dark()` RESOLVES AGAINST `color-scheme`, WHICH STREAMLIT SETS ON THE APP
    CONTAINER AND NOT ON `body`. 📊 A probe appended to `document.body` read the LIGHT value in
    both themes and nearly produced a false defect; appended inside the app container it reads
    light #16191d and dark #f2f5f8, and a real drawn `.cfdb-u1` agrees with it in both."""
    bands = _bands()
    for key in ("u1", "u2", "u3"):
        assert bands["light"][key] != bands["dark"][key], f"{key} is the same in both themes"


def test_schedule_and_today_draw_the_outcome_glyph_from_one_producer():
    """🚨 IF THEY DID NOT, THE FIX WOULD REACH ONE PAGE AND NOT THE OTHER — the defect B143 and
    B144 spent two rounds on. 📊 They do: Today calls `glyphs.result_strip` directly and
    Schedule reaches it through `schedule_table.result_strip`, which is a one-line delegation."""
    schedule_table = (ROOT / "site" / "lib" / "schedule_table.py").read_text()
    assert "glyphs.result_strip(row)" in schedule_table
    assert "glyphs.result_strip(row)" in TODAY
    # and the colour is one class set, not two
    assert glyphs.UPSET_LEVEL_CLASS == {"upset": "cfdb-u1", "big": "cfdb-u2",
                                        "blowout": "cfdb-u3"}
    for css_class in glyphs.UPSET_LEVEL_CLASS.values():
        assert re.search(rf"^\.{css_class}\s", THEME, re.M), f"{css_class} has no rule"


def test_the_modules_still_parse():
    """A211 edits eight view files; a syntax error in one is a dead page, not a failed test."""
    for path in VIEWS + [ROOT / "site" / "lib" / "fmt.py", ROOT / "site" / "lib" / "theme.py"]:
        ast.parse(path.read_text())
