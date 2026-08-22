"""Status chips: fixed width, glyph first, colour second.

AC-G.20 to AC-G.23. The hard rule is that meaning survives greyscale — colour is the second
signal, never the only one, so the glyph carries the meaning on its own and every chip
carries a spelled-out accessible label.
"""
import streamlit as st

# class -> (glyph, default label, aria description)
VARIANTS = {
    "y": ("✓", "Yes",   "yes / cover / win / pass"),
    "n": ("✗", "No",    "no / did not cover / loss"),
    "w": ("—", "Pending", "push, pending, unknown or backtest-only"),
    "p": ("▲", "Edge",  "positive edge or improvement"),
    "r": ("!", "Error", "failure, error or stale"),
}


def chip_html(variant: str, label: str = None, title: str = None) -> str:
    """One chip as HTML, so it can be embedded in a table cell as well as rendered alone."""
    glyph, default_label, aria = VARIANTS.get(variant, VARIANTS["w"])
    text = default_label if label is None else label
    return (f"<span class='cfdb-chip cfdb-chip-{variant}' "
            f"title='{title or aria}' aria-label='{title or aria}'>"
            f"<span class='cfdb-chip-glyph'>{glyph}</span>{text}</span>")


def chip(variant: str, label: str = None, title: str = None) -> None:
    st.markdown(chip_html(variant, label, title), unsafe_allow_html=True)


def cover_chip_html(result) -> str:
    """Cover outcomes, with push distinct from pending (AC-3.3).

    Those two are the pair most often collapsed into one grey box, and they mean different
    things: a push is a settled result, a pending is an unplayed game.
    """
    if result is None:
        return chip_html("w", "Pending", "game not yet played")
    value = str(result).lower()
    if value in ("push",):
        return chip_html("w", "Push", "landed exactly on the spread; a settled result")
    if value in ("true", "home", "cover", "y"):
        return chip_html("y", "Cover", "covered the spread")
    if value in ("false", "away", "no", "n"):
        return chip_html("n", "DNC", "did not cover the spread")
    return chip_html("w", str(result), "unknown cover state")


def out_of_sample_chip_html(is_out_of_sample: bool) -> str:
    """AC-12.5 / AC-10.8.

    The copy says "week", not "prediction": is_out_of_sample_week is a property of the
    training cut, not of an individual row, and only one of those two claims is true.
    """
    if not is_out_of_sample:
        return ""
    return chip_html("w", "Out-of-sample week",
                     "the model's training set contains no regular-season game this early; "
                     "this is extrapolation, not inference")


SPREAD_SIGN_NOTE = (
    "**A negative spread means the home team is favoured** — and a negative predicted "
    "margin means the model agrees. cfdb stores margin as away points minus home points, "
    "so both numbers point the same way."
)


def spread_sign_note() -> None:
    """R-009. One line of copy, in one place, used on every page that shows a spread.

    Written as a shared component rather than three captions because the confusion is not
    Schedule-specific: the same sign appears on Scores and Matchup, and three copies of one
    sentence is three chances for them to drift. It is also the cheapest item in the
    register and sat open for three rounds, which is its own argument for making it
    impossible to forget.
    """
    st.caption(SPREAD_SIGN_NOTE)
