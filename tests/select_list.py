"""The names a SELECT list actually produces (R-669). ONE implementation, for both sessions.

🚨 WHY THIS EXISTS. Two guards in `tests/` each carried their own copy of

    COLUMNS.replace("\\n", " ").split(",")

and both can be blinded by a single SQL comment. A102 hit the loud half — it put an
explanatory `--` line inside `COLUMNS` and the market-card guard went RED on a column that IS
selected. ⚠️ THE SAME PARSE FAILS SILENTLY IN THE OTHER DIRECTION, which is the half that
matters, and nobody had seen it.

Measured against the live driver on 2026-09-11, one comment doing both at once:

    game_id, season, week,
    spread, spread_open, over_under,
    spread_favorite_side,
    -- dropped for now, favorite_definitions_disagree, restore with R-999
    home_moneyline

| column                        | Postgres selects | the naive parse claims |
|-------------------------------|------------------|------------------------|
| favorite_definitions_disagree | NO — commented   | YES  → silent pass     |
| home_moneyline                | yes              | NO   → false alarm     |

🚨 THE FIRST ROW IS B083's SHIPPED DEFECT EXACTLY. The market card read
`favorite_definitions_disagree`, the SELECT never asked for it, and the caption was dead code
on all 70 games it existed for. The guard written to catch that class can be switched off by a
comment mentioning the column it is guarding.

⚠️ WHAT THIS IS NOT. It is not a SQL parser and must not become one. It answers exactly one
question — *what names does this select list produce* — because that is what a guard comparing
`row.get("x")` against a SELECT needs. Anything harder than the shapes in `OUTPUT NAMES` below
returns None for that item rather than guessing, and a caller that cares can say so.

⚠️ WHY NOT ASK POSTGRES, WHICH WOULD BE EXACT. `cur.execute("select … limit 0")` gives the
driver's own column list and is the real authority. ✅ IT IS USED THAT WAY — as this round's
VALIDATION, run once against live serving, with the results in the B088 report. 🚨 But putting
it inside a unit test would give the suite a database dependency, and A101 spent R-662/R-667
removing exactly that. A guard that only runs where there is a tunnel is a guard that stops
running. So: Postgres validates the parser, the parser runs offline.

── WHAT IT SURVIVES ────────────────────────────────────────────────────────────────────────

Comments      `-- …` to end of line, and `/* … */` spanning lines
Strings       a `--` or a comma inside '…' or "…" is text, not syntax
Nesting       `coalesce(a, b) as x` is ONE column, not two
Aliases       `expr as name` and `expr name` produce `name`
Qualified     `g.spread` produces `spread`

⚠️ A088 MEASURED THIS FAMILY ON ANOTHER SELECT LIST and it is why the nesting and comment rules
are here rather than assumed: a comma inside a block comment invented one column name per
comma, and the word `from` truncated the list — 156 fragments of prose in place of 153 column
names.
"""
import re

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
# `as` is optional in Postgres, so `spread s` aliases too. Only a bare identifier can be an
# implicit alias — `case when … end` must use `as`, which the depth rule below already covers.
_TRAILING_ALIAS = re.compile(r"\bas\s+([A-Za-z_][A-Za-z0-9_$]*)\s*$", re.IGNORECASE)


def strip_comments(sql: str) -> str:
    """Remove `--` and `/* */` comments, leaving string literals alone.

    ⚠️ NEWLINES SURVIVE. A `--` comment ends at one, so flattening the text first — which is
    what `replace("\\n", " ")` did — destroys the only thing that terminates it. That single
    line is the whole defect: it turns the rest of the block into one comment for the purpose
    of anything that reads it afterwards.
    """
    out = []
    i, n = 0, len(sql)
    quote = None
    while i < n:
        ch = sql[i]
        if quote:
            out.append(ch)
            if ch == quote:
                # '' and "" are escaped quotes inside a literal, not the end of one.
                if i + 1 < n and sql[i + 1] == quote:
                    out.append(sql[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            while i < n and sql[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            i += 2
            while i + 1 < n and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def split_items(sql: str) -> list:
    """Split a select list on its TOP-LEVEL commas only.

    `coalesce(a, b) as x` is one item. Splitting on every comma is what turns a function call
    into two imaginary columns.
    """
    items, depth, quote, current = [], 0, None, []
    for ch in sql:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
            current.append(ch)
            continue
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            items.append("".join(current))
            current = []
            continue
        current.append(ch)
    items.append("".join(current))
    return [i.strip() for i in items if i.strip()]


def output_name(item: str):
    """The name this one select item produces, or None if it cannot be known cheaply.

    🚨 None IS A REAL ANSWER AND NOT A FAILURE. `count(*)` with no alias is named by Postgres,
    not by the text; guessing would put a name in the guard's "selected" set that the query
    never produces — which is the exact false negative this module exists to remove.
    """
    item = " ".join(item.split())
    if not item:
        return None
    alias = _TRAILING_ALIAS.search(item)
    if alias:
        return alias.group(1)
    if _IDENT.match(item):
        return item
    # `schema.table.column` — the last segment is the output name.
    if all(_IDENT.match(part) for part in item.split(".")) and "." in item:
        return item.rsplit(".", 1)[1]
    # `expr name` with the AS omitted, but only when the expression is itself an identifier;
    # anything else is an expression whose name Postgres decides.
    parts = item.split()
    if len(parts) == 2 and _IDENT.match(parts[0]) and _IDENT.match(parts[1]):
        return parts[1]
    return None


def selected_names(sql: str) -> set:
    """Every name a select list produces. The one function callers want."""
    return {name for name in
            (output_name(item) for item in split_items(strip_comments(sql)))
            if name}


def unnameable_items(sql: str) -> list:
    """Select items whose output name this module declines to guess.

    A guard can use this to say "I could not read these" rather than silently omitting them,
    which is how a parse becomes a blind spot.
    """
    return [item for item in split_items(strip_comments(sql)) if output_name(item) is None]
