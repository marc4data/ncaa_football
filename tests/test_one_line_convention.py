"""One sign convention for every line on the site — the market's (cfdb-wtc-R-2550).

Marc, 2026-10-01: *"The market uses a negative to indicate spread where Home team is favored.
Our margin uses a + to indicate home team is favored. Flipping the sign on 2 values that are
compared makes things difficult to comprehend. Not a good practice."*

So every line the site shows — the market's spread and the model's predicted margin — is read
AS STORED, away − home, where a home favourite is negative. Two ways that could quietly come
back, and one test for each:

1. **A flipped copy is read again.** dbt still publishes `predicted_margin_home_perspective`
   and `spread_home_perspective` until the CONTRACT round drops them (§3.3.2: after A deploys).
   Any `site/` file naming a `*_home_perspective` column trips this — except
   `actual_margin_home_perspective`, which is a RESULT (Today's favourite-covered logic), not a
   line.
2. **The app flips a line itself.** A negation (`-x` or `x * -1`) of an expression that reads a
   line column. That would also break G-3 (no metric arithmetic in the app).

Both read CODE — tokens and the AST — never comments or docstrings, because this codebase's
prose about a column outnumbers its uses (charter §2.2.1c.1).
"""
import ast
import io
import tokenize
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
RESULT_COLUMNS = {"actual_margin_home_perspective"}
LINE_COLUMNS = {"spread", "spread_open", "spread_current", "spread_at_close", "spread_final",
                "predicted_margin", "home_cover_edge"}


def _site_files():
    return sorted(p for p in SITE.rglob("*.py") if "__pycache__" not in p.parts)


# STRING for plain literals; FSTRING_MIDDLE because Python 3.12 tokenizes an f-string's text
# separately — and every SQL query on the site is a triple-quoted f-string.
_TEXT_TOKENS = {tokenize.NAME, tokenize.STRING, getattr(tokenize, "FSTRING_MIDDLE", tokenize.STRING)}


def _docstring_lines(tree) -> set:
    """The lines a module, class or function docstring occupies — prose, never a use."""
    lines = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                lines.update(range(body[0].lineno, body[0].end_lineno + 1))
    return lines


def _code_tokens(path):
    """Names and string text, minus comments (never tokens here) and docstrings."""
    skip = _docstring_lines(ast.parse(path.read_text(encoding="utf-8")))
    with path.open("rb") as handle:
        for tok in tokenize.tokenize(handle.readline):
            if tok.type in _TEXT_TOKENS and tok.start[0] not in skip:
                yield tok


def test_no_site_file_reads_a_flipped_line_column():
    offenders = []
    for path in _site_files():
        for tok in _code_tokens(path):
            text = tok.string
            if "_home_perspective" not in text:
                continue
            names = {w.strip("'\",. ") for w in text.replace("\n", " ").split()
                     if "_home_perspective" in w}
            for name in names - RESULT_COLUMNS:
                offenders.append(f"{path.relative_to(SITE.parent)}:{tok.start[0]}: {name}")
    assert not offenders, (
        "the site reads a home-positive copy of a line again — show the stored value, in the "
        "market's sign (cfdb-wtc-R-2550):\n" + "\n".join(offenders))


def _reads_a_line_column(node) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and sub.value in LINE_COLUMNS:
            return True
        if isinstance(sub, ast.Attribute) and sub.attr in LINE_COLUMNS:
            return True
    return False


def _is_minus_one(node) -> bool:
    return (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant) and node.operand.value == 1) or \
           (isinstance(node, ast.Constant) and node.value == -1)


def test_the_app_never_negates_a_line():
    offenders = []
    for path in _site_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            flipped = None
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
                flipped = node.operand
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
                if _is_minus_one(node.left):
                    flipped = node.right
                elif _is_minus_one(node.right):
                    flipped = node.left
            if flipped is not None and _reads_a_line_column(flipped):
                offenders.append(f"{path.relative_to(SITE.parent)}:{node.lineno}: "
                                 f"{ast.unparse(node)[:80]}")
    assert not offenders, (
        "the app flips the sign of a line — read the stored value instead (cfdb-wtc-R-2550, "
        "G-3):\n" + "\n".join(offenders))


def test_the_guard_can_see_both_kinds_of_flip():
    """The guard's own instruments, on code written to trip them: a token naming a flipped
    column, and an AST negation of a line read. Without this, an empty `site/` walk would pass."""
    names = [t.string for t in tokenize.tokenize(io.BytesIO(
        b'q(f"""select spread_home_perspective from {t}""")\n').readline) if t.type in _TEXT_TOKENS]
    assert any("spread_home_perspective" in n for n in names), "an f-string query is invisible"
    tree = ast.parse("a = -row.get('predicted_margin')\nb = df['spread'] * -1\n")
    hits = [n for n in ast.walk(tree)
            if (isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub)
                and _reads_a_line_column(n.operand))
            or (isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult) and _is_minus_one(n.right)
                and _reads_a_line_column(n.left))]
    assert len(hits) == 2
    assert len(_site_files()) > 20, "the guard walked an empty site/"
