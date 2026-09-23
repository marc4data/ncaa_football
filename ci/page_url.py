"""Which URL does a page actually answer on? Derived from `site/app.py`, not assumed.

🚨 THIS EXISTS BECAUSE EVERY `Today` CROP A208 PRODUCED HAS A STREAMLIT MODAL ACROSS IT —
*"Page not found. The page that you have requested does not seem to exist. Running the app's
main page."*

📊 THE CAUSE, MEASURED: `site/app.py` registers Today with BOTH `url_path="today"` and
`default=True`. Streamlit serves the default page at the app ROOT, so `/today` is not a route
— it 404s, draws the dialog, and falls back to the default page, which IS Today. **The content
was right and the picture had a dialog over it.**

⚠️ AND THE REASON IT MATTERS IS REGISTER RULE 10, NOT TIDINESS. *"18 of 18 pages render"* once
went into two reports from a harness that set `?page=<key>` while `st.navigation` routes on
`url_path` — so all eighteen runs rendered the same default page and the number meant nothing.
**A harness that lands on the right page only because that page is the fallback is proving the
fallback works.** A crop is the instrument Cowork reads a round's work through.

    from ci.page_url import page_url
    page.goto("http://localhost:8604" + page_url("today"))     # -> "/"
    page.goto("http://localhost:8604" + page_url("scores"))    # -> "/scores"
"""
import ast
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "site" / "app.py"


def default_key(source: str = "") -> str:
    """The page key `app.py` marks as the default, read from `app.py`.

    ⚠️ READ RATHER THAN HARD-CODED, so moving the default moves the harness with it. The
    expression is `default=(p.key == "<key>")`; anything else here is a change this function
    has to be told about rather than one it should guess at.
    """
    text = source or APP.read_text()
    found = re.findall(r"default\s*=\s*\(\s*p\.key\s*==\s*(['\"])(\w+)\1\s*\)", text)
    if len(found) != 1:
        raise AssertionError(
            f"expected exactly one `default=(p.key == ...)` in app.py, found {len(found)}")
    return found[0][1]


def page_url(key: str, source: str = "") -> str:
    """`/` for the default page, `/<key>` for every other."""
    return "/" if key == default_key(source) else f"/{key}"


def registered_keys() -> list:
    """Every page key `st.Page` is built from, via the registry `app.py` iterates."""
    import sys
    sys.path.insert(0, str(APP.parent))
    from lib.registry import PAGES                            # noqa: PLC0415
    return [p.key for p in PAGES]


def _uses_url_path_for_every_page(source: str = "") -> bool:
    """`url_path=p.key`, which is what makes `/<key>` the route for a non-default page."""
    text = source or APP.read_text()
    return bool(re.search(r"url_path\s*=\s*p\.key", text))


if __name__ == "__main__":
    src = APP.read_text()
    print(f"default page: {default_key(src)!r} -> {page_url(default_key(src), src)!r}")
    print(f"url_path=p.key present: {_uses_url_path_for_every_page(src)}")
    tree = ast.parse(src)
    print(f"app.py parses: {bool(tree.body)}")
    for key in ("today", "scores", "matchup"):
        print(f"  {key:<10} -> {page_url(key, src)}")
