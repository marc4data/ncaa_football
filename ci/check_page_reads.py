"""Every column a page READS must be a column its query SELECTS (R-623).

🚨 THIS HAS SHIPPED TWICE IN TWO DAYS AND NOTHING IN THE PROJECT COULD SEE IT.

  B083  the market card read `favorite_definitions_disagree` and `moneyline_favorite_side`;
        neither was in matchup's COLUMNS. The disagreement caption was dead code on all 70
        games it exists for.
  B084  the game header read `away_mascot` and the two split-record columns. A092 had shipped
        all four to srv_game and COLUMNS did not select them, so a finished, tested, green
        feature was invisible for two rounds.

⚠️ NEITHER FAILURE RAISES. `row.get("x")` on an absent column returns None, and a page that
handles None gracefully — which every page here does, by AC-G.32 — renders the ABSENCE state
perfectly. It looks like data we do not have.

── WHY THE TWO EXISTING INSTRUMENTS CANNOT DO THIS ─────────────────────────────────────────

  the unit tests   `_row(**overrides)` fixtures supply every key, so the fixture is more
                   complete than the query the page issues. Such a test asserts what the page
                   does with a row it will never receive.

  check_page_queries.py   IT EXECUTES THE SQL. A column the SQL never asks for is not in the
                   SQL to be executed. ⚠️ It is the wrong instrument for this question and was
                   deliberately NOT extended — bolting a source-parse onto a SQL-executor
                   makes one tool that does two things badly.

── WHAT THIS CHECKS, AND THE ONE THING IT DELIBERATELY DOES NOT ────────────────────────────

Per view module: the union of every column selected by every `query(...)` in it, against every
column-shaped name read off a row in it. A read must appear in the union.

🚨 IT IS A UNION, NOT A PER-QUERY ASSOCIATION, AND THAT IS A DELIBERATE LIMIT.
A page reads more than one frame — matchup alone reads srv_game, srv_team_week, srv_drive and
the leader view — and `row` in one panel is a different shape from `row` in the next. Deciding
WHICH query produced a given `row` needs dataflow through helper functions and across module
boundaries, and B083 and B084 both scoped their versions to one panel rather than attempt it.

So: this catches a column that NO query in the module selects, which is exactly both known
defects. It does NOT catch a column selected by one query and read off another query's row.
⚠️ That is a false-negative and it is named here rather than left for someone to discover —
the narrower thing that is true, rather than the broad one that is noisy.

── NO BLANKET EXEMPTION ────────────────────────────────────────────────────────────────────

⚠️ A088: "a check that needs a blanket exemption on day one is the third silent guard."
`PROVIDED_BY_THE_PAGE` below is per-name with a reason, the WEEKLY_BY_DESIGN pattern, and
`test_page_reads_guard.py` asserts it stays that way. An empty scan is an error, not a pass —
check_page_queries spent months green while scanning a directory that did not exist.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "site" / "views"
WORKBOOK = ROOT / "site" / "lib" / "workbook.py"

# Receivers whose `.get()` is not a row read. `params.get("tab")` is a URL parameter and has
# nothing to do with a serving column; without this the check reports every filter name.
NOT_A_ROW = {"params", "os", "environ", "st", "config", "session_state",
             "kwargs", "opts", "spec", "overrides", "row_config"}

# ⚠️ NAMES A PAGE LEGITIMATELY READS THAT NO QUERY SELECTS. One entry, one reason, no blanket.
# To add one you must be able to finish "the page reads this and no query selects it because…".
PROVIDED_BY_THE_PAGE = {
    "game_no": "a window function's alias in the Scores sheet SQL, which this parser drops "
               "along with the rest of the expression it is computed by.",
    "rows_in_scope": "the same — `count(*) over ()` in the Scores sheet.",
    "won": "derived in scores.py from `result`; never selected, and workbook.py says so.",
    "team_rank": "assembled by the page from the rank columns rather than read from one.",
}


def _strings(tree):
    """Every `NAME = "..."` in the module, at any level.

    Module-level for f-string placeholders like {_ADVANCED_COLUMNS}; function-local because
    schedule.py builds `sql = \"\"\"select …\"\"\"` and hands the NAME to query().
    """
    out = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            out[node.targets[0].id] = node.value.value
            continue
        # ⚠️ THE ASSIGNED VALUE IS NOT ALWAYS A BARE LITERAL, and schedule.py is why this
        # branch exists: `sql = """select …""".replace("{ROW_CAP}", str(ROW_CAP))`. The
        # assignment's value is a Call, and without this every one of that page's 28 reads
        # was reported as unselected — against a SELECT list that contains all of them.
        # A `.replace` of a placeholder cannot change a column NAME, so the underlying
        # literal is the right thing to read.
        for sub in ast.walk(node.value):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                    and re.search(r"\bselect\b", sub.value, re.IGNORECASE):
                out[node.targets[0].id] = sub.value
                break
    return out


def _module_strings(tree):
    """Module-level `NAME = "..."` only.

    ⚠️ DELIBERATELY NARROWER THAN `_strings`, AND THE DIFFERENCE IS A FALSE POSITIVE THIS
    CHECK ACTUALLY PRODUCED. `_strings` walks the whole tree so a function-local `sql = …` is
    resolvable, which SQL extraction needs. Applying that same map to a `.get(name)` argument
    made a local `title = "record going into this game"` in one function resolve a DIFFERENT
    function's `LEGEND_SUBSECTIONS.get(title)`, and the check reported an English sentence as
    an unselected column. A read is resolved only through a module-level constant, where the
    name means one thing everywhere.
    """
    return {node.targets[0].id: node.value.value
            for node in tree.body
            if isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)}


def _string_dicts(tree):
    """Module-level dicts whose values are all strings — `{"away": "away_mascot", …}`.

    🚨 THE READ IS NOT ALWAYS A LITERAL, AND B084's DEFECT IS THE PROOF. The game header does
    `row.get(_MASCOT_COLUMN[side])`, so the argument is a Subscript on a constant dict and a
    scan that only sees `row.get("literal")` cannot see the read at all. The first version of
    this check missed B084 entirely for that reason — caught by reintroducing the defect and
    watching the guard stay green, which is the whole argument for running the break.

    If a page can read ANY value of such a dict, every value must be selected: which key is
    used is a runtime choice and the check cannot know it, so it requires all of them.
    """
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Dict):
            values = [v.value for v in node.value.values
                      if isinstance(v, ast.Constant) and isinstance(v.value, str)]
            # ⚠️ EVERY VALUE MUST LOOK LIKE A COLUMN NAME. Pages also keep dicts of prose —
            # schedule.py has one of tooltip text — and treating "record going into this game"
            # as a column produced this check's only false positive. A column name is an
            # identifier; a sentence is not.
            if values and len(values) == len(node.value.values) \
                    and all(re.fullmatch(r"[a-z_][a-z0-9_]*", v) for v in values):
                out[node.targets[0].id] = values
    return out


def _read_names(argument, constants, dicts):
    """The column name(s) a `.get(...)` argument can resolve to."""
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
        return [argument.value]
    if isinstance(argument, ast.Name) and argument.id in constants:
        return [constants[argument.id]]
    if isinstance(argument, ast.Subscript) and isinstance(argument.value, ast.Name) \
            and argument.value.id in dicts:
        return dicts[argument.value.id]
    return []


def _sheet_sql():
    """name -> SQL for every workbook Sheet, read statically.

    scores.py binds `SCORES_SHEET = next(s for s in workbook.SHEETS if s.name == "Scores")`,
    so its SQL lives in another module. Resolved by AST rather than by importing, because
    importing a view module needs streamlit and check_page_queries avoids that for the same
    reason.
    """
    out = {}
    for node in ast.walk(ast.parse(WORKBOOK.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "Sheet" and len(node.args) >= 3 \
                and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[2], ast.Constant):
            out[node.args[0].value] = node.args[2].value
    return out


def _sql_from(node, strings, sheets, sheet_names):
    """The SQL a query() call was handed."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return strings.get(node.id)
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue) and isinstance(value.value, ast.Name):
                parts.append(strings.get(value.value.id, " "))
            else:
                parts.append(" ")
        return "".join(parts)
    # `query(" ".join(SCORES_SHEET.sql.split()), …)` — the sheet this module bound.
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr == "sql":
            for name in sheet_names:
                if name in sheets:
                    return sheets[name]
    return None


def selected_columns(sql):
    """The bare names a SELECT list produces. An alias wins, brackets or not."""
    names = set()
    match = re.search(r"\bselect\b(.*?)\bfrom\b", " ".join(sql.split()), re.IGNORECASE | re.S)
    if not match:
        return names
    depth, piece, pieces = 0, "", []
    for character in match.group(1):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        if character == "," and depth == 0:
            pieces.append(piece)
            piece = ""
        else:
            piece += character
    pieces.append(piece)
    for piece in (p.strip() for p in pieces):
        if not piece:
            continue
        alias = re.search(r"\bas\s+([a-z_][a-z0-9_]*)\s*$", piece, re.IGNORECASE)
        if alias:
            names.add(alias.group(1))
            continue
        if "(" in piece:
            # A computed expression with no alias produces no name a page can read.
            continue
        names.add(piece.split()[-1].split(".")[-1])
    return names


# ⚠️ R-564's OTHER HALF, AND IT IS EXTENDED HERE RATHER THAN BUILT BESIDE.
#
# A088 found Scores calling `table.as_of_caption(raw)` while its query never selected
# `as_of_ts`. The helper returns SILENTLY when the column is absent, so the page asked for a
# stamp, srv_game_team had carried it all along, and a guard clause forgave the one line between
# them — for as long as the page had existed. AC-G.35 says every page states when its own data
# was loaded; Scores opted out in silence.
#
# 🚨 A `raise` INSIDE `as_of_caption` IS THE WRONG FIX, and A088 named the reason in advance: the
# `df.empty` branch must stay silent, so making the column branch raise would break EIGHTEEN
# pages' Empty paths to catch a nineteenth page's omission.
#
# ⚠️ EXTENDED RATHER THAN A NEW SCRIPT, DELIBERATELY. This file already parses, per module, every
# column any of its queries selects — which is the expensive half of the question — and the
# prompt for R-571 forbids a third source-parser. It is also the same SHAPE of question: a page
# asking for something its own query does not provide.
#
# ⚠️ WHAT THIS DOES NOT CHECK, said rather than left to be found: that the VIEW carries
# `as_of_ts`. That needs a database and this script is static. check_page_queries.py executes
# every page's SQL against CI's fixture, so a page selecting a column its view lacks already
# fails there — the two halves are covered by the two tools that can each see one.
AS_OF_EXEMPT = {}


def as_of_audit(path, selected):
    """Does this module call as_of_caption without selecting the column it needs?"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = [node.lineno for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == "as_of_caption"]
    if not calls or "as_of_ts" in selected or path.name in AS_OF_EXEMPT:
        return None
    return calls[0]


def audit(path, sheets):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    strings = _strings(tree)          # any level — SQL is often a function local
    constants = _module_strings(tree)  # module level only — see the docstring
    dicts = _string_dicts(tree)
    sheet_names = re.findall(r'SHEETS\s+if\s+s\.name\s*==\s*"([^"]+)"', source)

    selected, provided, reads = set(), set(), {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            function = node.func
            name = function.id if isinstance(function, ast.Name) \
                else getattr(function, "attr", "")
            if name == "query" and node.args:
                sql = _sql_from(node.args[0], strings, sheets, sheet_names)
                if sql:
                    selected |= selected_columns(sql)
            if isinstance(function, ast.Attribute) and function.attr == "get" and node.args:
                receiver = function.value
                if isinstance(receiver, ast.Name) and receiver.id in NOT_A_ROW:
                    continue
                if isinstance(receiver, ast.Attribute) and receiver.attr in NOT_A_ROW:
                    continue
                for name in _read_names(node.args[0], constants, dicts):
                    reads.setdefault(name, node.lineno)
        # A column the page WRITES into the frame is one it may then read.
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant) \
                        and isinstance(target.slice.value, str):
                    provided.add(target.slice.value)

    missing = {name: line for name, line in reads.items()
               if name not in selected and name not in provided
               and name not in PROVIDED_BY_THE_PAGE}
    return selected, reads, missing


def main() -> int:
    sheets = _sheet_sql()
    files = sorted(VIEWS.glob("*.py"))
    total_reads, problems, stamps = 0, [], []
    for path in files:
        selected, reads, missing = audit(path, sheets)
        total_reads += len(reads)
        for name, line in sorted(missing.items()):
            problems.append((path, line, name))
        line = as_of_audit(path, selected)
        if line is not None:
            stamps.append((path, line))

    # An empty scan is the failure check_page_queries spent months not reporting.
    if total_reads < 50:
        print(f"::error::check_page_reads found only {total_reads} row reads across "
              f"{len(files)} modules — the scan is wrong, not the pages", file=sys.stderr)
        return 1

    print(f"Scanned {len(files)} view modules, {total_reads} row reads.")
    if stamps:
        print(f"\n::error::{len(stamps)} page(s) call table.as_of_caption() and never select "
              f"`as_of_ts`. The helper returns SILENTLY when the column is absent, so the page "
              f"asks for a stamp and renders none — AC-G.35, opted out of without saying so:",
              file=sys.stderr)
        for path, line in stamps:
            print(f"  {path.relative_to(ROOT)}:{line}  as_of_caption with no as_of_ts selected",
                  file=sys.stderr)
        print("\n  Add `as_of_ts` to that page's SELECT. If the page genuinely cannot have "
              "one, add it to AS_OF_EXEMPT in this file WITH A REASON.", file=sys.stderr)
    if not problems and not stamps:
        print("Every column a page reads is selected by one of its own queries.")
        print("Every page that asks for an as-of stamp selects the column it needs.")
        return 0
    if not problems:
        return 1

    print(f"\n::error::{len(problems)} column(s) are READ by a page and SELECTED by none of "
          f"its queries. `row.get()` returns None for these on every real page load, and the "
          f"page renders the absence state rather than failing:", file=sys.stderr)
    for path, line, name in problems:
        print(f"  {path.relative_to(ROOT)}:{line}  {name}", file=sys.stderr)
    print("\n  Add the column to that page's SELECT, or — if the page legitimately provides "
          "it — add it to PROVIDED_BY_THE_PAGE in this file WITH A REASON.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
