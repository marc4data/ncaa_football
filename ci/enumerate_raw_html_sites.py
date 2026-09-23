r"""Every `unsafe_allow_html=` call site on the site, classified by what it can emit.

🚨 A219 (cfdb-main-R-2661). B148's defect: `st.markdown(..., unsafe_allow_html=True)` PARSES
MARKDOWN FIRST, and **a blank line terminates a raw HTML block in Markdown**. The parser closes
the block mid-tag, injects `<p>`, and escapes everything after it. Nine circles became one, and
1,934 Python tests stayed green — the suite asserts the string BEFORE Streamlit's frontend
parses it.

⚠️ `git grep -c` COUNTS LINES, NOT CALLS (R-859, and §2.2.1c.1's whole subject). Cowork's count
was 67 lines across 18 files. This walks the AST instead, so a call spanning three lines counts
once and a mention in a comment or docstring counts not at all.

THE THREE CLASSES THE ROUND HAS TO SEPARATE, because each needs different treatment:

    literal    a string constant. Can only contain a blank line if one is TYPED into it.
    composed   an f-string or concatenation built from page-side values.
    data       a composed string that interpolates something read from the warehouse —
               a team name, a network, a venue, a note. **This is the dangerous class:
               nothing on the page controls what the column holds.**

⚠️ THE `data` TEST IS A HEURISTIC AND IS REPORTED AS ONE. It looks for `row.get(...)`,
`.get(...)`, `fmt.*`, `html.escape(...)` and subscripting inside the interpolations. It can
over-report (a `.get` on a local dict) and it cannot see a value that reached the string through
a variable assigned three lines earlier. **Its purpose is to bound the problem, not to settle
any single call site.**

    python ci/enumerate_raw_html_sites.py            # table
    python ci/enumerate_raw_html_sites.py --json     # machine-readable
"""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

DATA_HINTS = ("get", "escape", "text", "number", "title_case", "loc", "iloc")


def _call_name(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Attribute):
        owner = f.value.id if isinstance(f.value, ast.Name) else "…"
        return f"{owner}.{f.attr}"
    if isinstance(f, ast.Name):
        return f.id
    return "…"


def _looks_like_data(node: ast.AST) -> bool:
    """Does any interpolation in this expression read a value rather than compose one?"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            if sub.func.attr in DATA_HINTS:
                return True
        if isinstance(sub, ast.Subscript):
            return True
    return False


def classify(arg: ast.AST) -> str:
    if arg is None:
        return "unknown"
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return "literal"
    return "data" if _looks_like_data(arg) else "composed"


def literal_has_blank_line(arg: ast.AST) -> bool:
    return (isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            and "\n\n" in arg.value)


def sites() -> list:
    out = []
    for path in sorted(SITE.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            kw = next((k for k in node.keywords if k.arg == "unsafe_allow_html"), None)
            if kw is None:
                continue
            raw = (kw.value.value is True
                   if isinstance(kw.value, ast.Constant) else None)
            arg = node.args[0] if node.args else None
            out.append({
                "file": str(path.relative_to(ROOT)),
                "line": node.lineno,
                "call": _call_name(node),
                "raw_html": raw,
                "klass": classify(arg),
                "literal_blank_line": literal_has_blank_line(arg),
                "src": ast.unparse(node)[:90].replace("\n", " "),
            })
    return out


if __name__ == "__main__":
    rows = sites()
    if "--json" in sys.argv:
        print(json.dumps(rows, indent=1))
        raise SystemExit(0)
    by_file = {}
    for r in rows:
        by_file.setdefault(r["file"], []).append(r)
    print(f"{'file':38} {'calls':>5} {'literal':>8} {'composed':>9} {'data':>5}")
    for f, rs in sorted(by_file.items(), key=lambda kv: -len(kv[1])):
        print(f"{f:38} {len(rs):>5} "
              f"{sum(1 for r in rs if r['klass'] == 'literal'):>8} "
              f"{sum(1 for r in rs if r['klass'] == 'composed'):>9} "
              f"{sum(1 for r in rs if r['klass'] == 'data'):>5}")
    print(f"{'TOTAL':38} {len(rows):>5} "
          f"{sum(1 for r in rows if r['klass'] == 'literal'):>8} "
          f"{sum(1 for r in rows if r['klass'] == 'composed'):>9} "
          f"{sum(1 for r in rows if r['klass'] == 'data'):>5}")
    print()
    print("calls by function:", end=" ")
    fns = {}
    for r in rows:
        fns[r["call"]] = fns.get(r["call"], 0) + 1
    print("  ".join(f"{k} {v}" for k, v in sorted(fns.items(), key=lambda kv: -kv[1])))
    print("unsafe_allow_html=True:",
          sum(1 for r in rows if r["raw_html"] is True),
          " =False/other:", sum(1 for r in rows if r["raw_html"] is not True))
    blanks = [r for r in rows if r["literal_blank_line"]]
    print(f"LITERALS THAT ALREADY CONTAIN A BLANK LINE: {len(blanks)}")
    for r in blanks:
        print(f"   🚨 {r['file']}:{r['line']}  {r['src']}")
