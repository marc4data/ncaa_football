"""The footer, which every page renders and nothing tested.

AC-G.43 puts the CollegeFootballData credit on every page, and the footer is the only place
it appears — yet until now not one assertion touched it. What follows pins the two things
that make it work: the credit is a live link rather than the name of one, and the author
links are readable and reachable.

The icons here are inline SVG for the reason the dome is (R-141, R-175): ✉ has no fixed
presentation, so the platform decides whether it is a hairline dingbat or a colour emoji.
The last test in this file is what stops that glyph coming back.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))

from lib import attribution, theme   # noqa: E402

FOOTER = f"{attribution.CFBD_CREDIT} {attribution.AUTHOR_LINKS}"

# href, then the anchor's own content.
ANCHOR = re.compile(r"<a\s[^>]*?href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.S)


def _anchors(html: str):
    return ANCHOR.findall(html)


def _visible(inner: str) -> str:
    """The text a reader actually sees: markup removed, whitespace collapsed."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inner)).strip()


def _css_without_comments() -> str:
    """CSS with /* ... */ stripped.

    Both stylesheets, because `inject()` ships both and the footer rules happen to live in
    the second one — a test that read only `theme.CSS` would report "not defined" for a rule
    that is on every page.

    The seventh time in this repo that a source-reading test would otherwise have matched
    its own prose — the comment above `.cfdb-icon` names the very unit the test asserts on.
    """
    return re.sub(r"/\*.*?\*/", "", theme.CSS + theme.TABLE_CSS, flags=re.S)


def test_the_cfbd_credit_is_a_link_and_not_just_the_words():
    """AC-G.43 is satisfied by a reachable credit. An earlier version used markdown link
    syntax inside `unsafe_allow_html`, which does not parse markdown — so the site shipped
    literal square brackets and no link at all. Assert the anchor, not the name."""
    hrefs = [href for href, _ in _anchors(attribution.CFBD_CREDIT)]
    assert "https://collegefootballdata.com" in hrefs
    assert "[" not in attribution.CFBD_CREDIT, (
        "markdown link syntax does not render inside unsafe_allow_html")


def test_the_website_link_says_about_marc_and_shows_it_is_a_website():
    """R-271. A URL printed as its own label makes the reader parse a string to learn it is a
    personal site; "Marc's Website" fixed that and said the obvious part. "About Marc" names
    what is on the other side, and a globe carries the rest.

    THE GLYPH IS A DRAWING, WHICH IS NOT A STYLE CHOICE HERE. 🌐 and 🔗 have no fixed
    presentation — one platform draws a hairline dingbat, another a full-colour emoji, and
    nothing in CSS decides which. That is the defect U+2709 had (R-141, R-175), and the test
    below still forbids it across the whole footer.
    """
    site = [(href, inner) for href, inner in _anchors(attribution.AUTHOR_LINKS)
            if "netlify" in href]
    assert len(site) == 1, "exactly one link to Marc's own site"
    href, inner = site[0]
    assert _visible(inner) == "About Marc"
    assert "netlify" not in _visible(inner) and "://" not in _visible(inner)
    assert href.startswith("https://"), href
    assert "<svg" in inner, "the website mark is missing"

    # AND IT MUST NOT WEAR `cfdb-icon-link`. That class marks the ICON-ONLY anchors, and the
    # test below asserts their content is a drawing and nothing else — this one is a word
    # plus a glyph, so the class would make it fail for being exactly what it should be.
    anchor = re.search(r"<a\s[^>]*netlify[^>]*>", attribution.AUTHOR_LINKS).group()
    assert "cfdb-icon-link" not in anchor, anchor


def test_each_icon_link_is_a_drawing_with_an_accessible_name():
    """The SVG is `aria-hidden`, so the anchor's `aria-label` is the ONLY accessible name a
    screen reader has for it. An icon link that loses its label is an unlabelled link, which
    is worse than the bold `in` it replaced."""
    icons = re.findall(
        r"<a\s([^>]*cfdb-icon-link[^>]*)>(.*?)</a>", attribution.AUTHOR_LINKS, re.S)
    assert len(icons) == 2, "email and LinkedIn"
    for attrs, inner in icons:
        assert "aria-label=" in attrs and "title=" in attrs, attrs
        assert "<svg" in inner, "the icon is a drawing, not a character"
        assert _visible(inner) == "", (
            "an icon link renders no text of its own; anything visible here is a fallback "
            "glyph that will sit beside the drawing")


def test_the_mail_and_linkedin_links_point_where_they_say():
    hrefs = [href for href, _ in _anchors(attribution.AUTHOR_LINKS)]
    assert "mailto:marc4data@gmail.com" in hrefs
    assert "https://www.linkedin.com/in/marc4data/" in hrefs


def test_the_icons_are_drawn_larger_than_the_text_beside_them_and_scale_with_it():
    """The whole point of the change: at 1em an icon reads as SMALLER than the letters next
    to it, because a drawing needs more box than a letter to carry the same weight.

    Sized in `em` rather than `px` so the footer's .82rem type and its icons stay in
    proportion if either moves. A px value here would pass a "bigger" assertion today and
    silently stop tracking the text tomorrow.
    """
    css = _css_without_comments()
    rule = re.search(r"\.cfdb-icon\s*\{([^}]*)\}", css)
    assert rule, ".cfdb-icon is not defined"
    body = rule.group(1)
    for prop in ("width", "height"):
        found = re.search(rf"{prop}\s*:\s*([\d.]+)em", body)
        assert found, f"{prop} must be sized in em so it tracks the footer's font-size: {body}"
        assert float(found.group(1)) > 1.0, (
            f"{prop} is {found.group(1)}em — an icon at or below 1em reads smaller than the "
            "text beside it")


def test_no_presentation_ambiguous_glyph_survives_in_the_footer():
    """The negative test for R-141's failure mode, and the reason the drawings exist.

    U+2709 and friends have no fixed presentation: the platform decides between a thin
    dingbat and a full-colour emoji, and CSS cannot overrule it. Reintroducing ✉ — or any
    emoji-capable character — turns this red.
    """
    strays = [ch for ch in FOOTER
              if ord(ch) > 0x2100 and ch not in "—–’·"]
    assert not strays, (
        f"presentation-ambiguous character(s) in the footer: {strays!r} — use an inline "
        "SVG, as MAIL_MARK and LINKEDIN_MARK do")
