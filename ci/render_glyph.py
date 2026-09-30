r"""Photograph a glyph that is too small to see and too far right to be in the viewport.

🚨 THIS EXISTS BECAUSE A265's `*_upset_glyphs_in_context_*.png` CONTAINED NO UPSET GLYPH, IN
BOTH FRAMES, AND EVERY COORDINATE IN THE COMMAND WAS CORRECT (cfdb-main-R-4204/R-4252).

📊 THE CAUSE, MEASURED BY A266: at a 1440 viewport the upset column sits at **x ≈ 1618** —
OUTSIDE the viewport — inside the site's horizontally scrolling `.cfdb-scroll` wrapper (A208).
`page.screenshot(clip=...)` clips the VIEWPORT, so a clip at x=1618 photographs whatever is
painted at the rightmost visible column instead. ⚠️ The crop did not "stop short": it
photographed a different thing at the right coordinates, which is R-859's class in a
screenshot — the command answered "what is painted here" when the question was "show me that
element".

✅ THE INSTRUMENT THAT WORKS, and A265 had already used it successfully in the same round for
`A265_upset_glyph_cell_dark.png`: an ELEMENT screenshot. Playwright scrolls an element into
view before shooting it, so the horizontal scroll is handled and no coordinate is ever typed.

⚠️ AND THE SCALE IS PART OF THE INSTRUMENT, NOT A PREFERENCE. The upset glyph's own box
measures **10.36 x 10.36 px** with a **1px** ring. At `device_scale_factor` 1 or 2 that ring is
one or two pixels in the artifact and a reviewer cannot tell `#1f6feb` from `#58a6ff` — which
is the exact distinction these renders exist to show. **3 or 4.**

📋 THERE WAS NO OLDER VIEWPORT-CLIP HELPER TO RETIRE (§3.2.3): A265's clip was written inline
in a throwaway script and never shared, so this file supersedes a habit rather than a module.
**Use this instead of `page.screenshot(clip=...)` for anything glyph-sized.**

    from ci.render_glyph import shoot_element_context

    shoot_element_context(page, ".cfdb-ind.cfdb-sh-upset", out / "upset_light.png")
"""
from pathlib import Path
from typing import Optional

# The glyph box is 10.36px square with a 1px ring; below 3 the ring is not legible in the
# artifact a reviewer actually opens. Used by every caller that does not say otherwise.
GLYPH_SCALE = 4

# How far up to climb from the glyph to get something worth calling "context". `td` is the
# cell the indicators share with their game's link, which is what "in context" means on the
# Today table — the quiet circle, the filled circle, the square and the diamond together.
DEFAULT_CONTEXT = "td"


def context_of(page, selector: str, ancestor: str = DEFAULT_CONTEXT):
    """The element to photograph: `selector`'s nearest `ancestor`, or the glyph itself.

    ⚠️ Returns None rather than raising when the selector matches nothing, so a caller can
    report WHICH absence it is (AC-G.11) instead of dying on a stack trace.
    """
    el = page.query_selector(selector)
    if el is None:
        return None
    handle = el.evaluate_handle(
        "(g, sel) => g.closest(sel) || g", ancestor)
    return handle.as_element() or el


def shoot_element_context(page, selector: str, path: Path,
                          ancestor: str = DEFAULT_CONTEXT) -> Optional[dict]:
    """Element-screenshot `selector`'s enclosing `ancestor` to `path`.

    Returns the glyph's measured geometry and painted colours, or None if it is not there —
    so a round can report the numbers beside the picture rather than only the picture.
    ⚠️ The colours are read from the LIVE DOM, never from the stylesheet: A244 measured a rule
    claiming 8.14:1 while the page painted 4.18:1, and A265's `z-index:-1` chip measured
    perfectly while rendering invisible.
    """
    target = context_of(page, selector, ancestor)
    if target is None:
        return None
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    target.screenshot(path=str(path))
    return page.evaluate(
        """(sel) => {
             const g = document.querySelector(sel);
             if (!g) return null;
             const b = g.getBoundingClientRect(), cs = getComputedStyle(g);
             return {w: +b.width.toFixed(2), h: +b.height.toFixed(2),
                     ring: cs.borderColor, ringWidth: cs.borderWidth,
                     fill: cs.backgroundColor, opacity: cs.opacity};
           }""", selector)
