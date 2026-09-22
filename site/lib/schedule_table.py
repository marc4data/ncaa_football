"""Schedule's game table — its columns and their cells, shared by two pages.

🚨 A196 (cfdb-main-R-2032). PROMOTED OUT OF `views/schedule.py` RATHER THAN COPIED, BECAUSE
TODAY'S "LOOKING FORWARD" IS THE SAME TABLE.

> **MARC, v12:** *"the layout should be the same as Schedule"*.

⚠️ **THE SAME TABLE MEANS THE SAME CODE, NOT THE SAME APPEARANCE.** A copy is two tables that
agree until one of them changes, and "it looks the same today" is exactly how a copy starts.

⚠️ AND IT LIVES IN `lib/` BECAUSE A VIEW MAY NOT IMPORT ANOTHER VIEW. `site/lib/` is session
A's by declaration (§3), and both callers — `views/schedule.py` and `views/today.py` — are A's
as well, so this is a move inside one owner rather than a reach across the A/B line.

✅ **EVERY FUNCTION AND CONSTANT IS VERBATIM.** Nothing was rewritten in the move, and
`schedule.py` keeps a module-level alias for each one so its own call sites are untouched —
the stacked card reads six of these. A196 rendered Schedule before and after to prove the
page did not move, and `test_schedule_table_is_not_a_copy` holds the arrangement.
"""
import pandas as pd

from lib import fmt, glyphs, table
from lib.query import query
from lib.table import Col


# R-085. A CHARACTER COUNT, NOT A WRAP PREDICTION.
#
# "Would this wrap" depends on rendered width, which is not knowable server-side and would
# behave differently on two screens. A threshold on the display name is deterministic: the
# same row abbreviates identically everywhere.
#
# 18 is chosen against the data rather than by eye — it abbreviates the genuinely long names
# ("Middle Tennessee State", "Southeastern Louisiana") while leaving the ones a reader
# expects to see spelled out ("Oklahoma State", 14; "Northwestern", 12) alone.
TEAM_NAME_MAX = 18


# R-027. The 18 condition codes CFBD actually sends, mapped to a small set. Nothing here is
# invented: every code below was observed in the data, and code 0 arrives with a blank label
# and is treated as unknown rather than as clear weather.
WEATHER_GLYPH = {
    1: "☀", 2: "☀",                      # Clear, Fair
    3: "☁", 4: "☁",                      # Cloudy, Overcast
    5: "≋",                               # Fog
    7: "☂", 8: "☂", 9: "☂", 17: "☂", 18: "☂",   # rain, all intensities
    12: "❄", 13: "❄", 20: "❄",           # sleet
    14: "❄", 15: "❄", 16: "❄",           # snow
    25: "⚡",                              # Thunderstorm
}
# R-175. A DOMED STADIUM, DRAWN RATHER THAN BORROWED.
#
# It was U+2302 HOUSE, and it read as a house because it is one. Marc asked for "some kind of
# stadium with dome, or simple astrodome wireframe".
#
# NOT AN EMOJI, AND THAT IS THE SAME CONSTRAINT R-141 ALREADY SETTLED. 🏟 and 🏛 are
# emoji-presentation characters: they do not share a baseline with text glyphs, do not size
# with them, and vary by platform. Choosing one would re-open on this mark exactly the problem
# the whole indicator system was rebuilt as CSS shapes to avoid. Unicode has no
# text-presentation dome, so the honest options were an SVG or a worse character.
#
# `stroke="currentColor" fill="none"` means it inherits the surrounding colour and themes for
# free in both palettes; `1em` sizing means it scales with whatever row it sits in, like every
# other mark. No width/height attributes — CSS owns the box.
DOME_MARK = (
    "<svg class='cfdb-dome' viewBox='0 0 20 20' fill='none' stroke='currentColor' "
    "stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
    "<path d='M2.5 14.5a7.5 7.5 0 0 1 15 0'/>"      # the shell
    "<path d='M1.5 14.5h17'/>"                       # the ground line
    "<path d='M5 14.5v2M15 14.5v2'/>"                # the uprights
    "</svg>")
NEUTRAL_GLYPH = "◇"


# R-100 / R-113. THE SAME GLYPH THE SCORES PAGE ALREADY USES.
#
# Prompt 032 wrote this as ◀. `scores.py` has shipped ▸ against the same `.cfdb-winner`
# class since it was built, and R-100's own wording is "a relocation, not a new component".
# Two pages marking a winner with two different characters is a worse outcome than a
# one-character deviation from the prose, so this reuses the component whole. It also points
# INTO the number it precedes rather than away from it.
WINNER_GLYPH = "▸"
# A tie is completed AND has no winner, which is not the same fact as "not played yet". The
# chip this replaced kept those apart and so does this: nothing on either row means pending,
# `=` on BOTH rows means level, ▸ on one row means won.
TIE_GLYPH = "="


def text(value) -> str:
    """A cell value as a string, or "". THE BODY MOVED TO `fmt.text` IN A147; this is the call back.

    ⚠️ IT MOVED BECAUSE `lib/glyphs.py` NEEDS THE SAME RULE for the result strip's stored values,
    and a second implementation of "NaN is truthy, so guard it" is the drift this project keeps
    paying for. ⚠️ THE LOCAL NAME STAYS because eight call sites in this file read better with it
    and renaming them would move bytes on a page A147 must render byte-identically.
    """
    return fmt.text(value)


def missing(value) -> bool:
    """Null in either of the two shapes a serving row hands back."""
    return value is None or (isinstance(value, float) and pd.isna(value))


def team_name(row, side: str) -> str:
    """Display name, abbreviated past the threshold. R-085."""
    name = text(row.get(f"{side}_team_display")) or "—"
    if len(name) > TEAM_NAME_MAX:
        # An abbreviation can be null for a team absent from /teams, so fall back to a
        # truncation rather than to NaN.
        return text(row.get(f"{side}_abbreviation")) or name[:TEAM_NAME_MAX]
    return name


def record_span(row, side: str) -> str:
    """The record, on its own. R-129 needs it separable from the part that is a link.

    🚨 THE BODY MOVED TO `table.record_span` IN A144 AND THIS IS THE CALL BACK. Today's Looking
    Back needs the identical rule — R-140's completed/scheduled choice and R-084's point-in-time
    columns — and a second copy is the drift this project has paid for repeatedly. ⚠️ THE WRAPPER
    STAYS HERE because the `{side}_` column naming is Schedule's own shape, not a fact about what
    a record is: `srv_game_team` spells the same thing `record_before_display`.

    ✅ BYTE-IDENTICAL, ASSERTED RATHER THAN CLAIMED — see
    `test_the_record_span_moved_without_changing_a_byte`.
    """
    return table.record_span(row, f"{side}_team_record_display",
                             f"{side}_team_record_after_display")


def team_with_record(row, side: str) -> str:
    """Team cell with the record beside the name, smaller and regular weight. R-088.

    The record is the one LEADING INTO this game's week, from fct_team_record_week — not the
    season-final record, which is what fct_team_record would give and which would show 11-2
    beside a game played in September.

    Renders NOTHING when the record is absent rather than substituting the season figure. A
    record that is wrong for the week is worse than a missing one, which is the whole reason
    R-084 exists.
    """
    base = table.team_cell(row, f"{side}_team_slug", f"{side}_team_display",
                           f"{side}_logo_url", f"{side}_rank")
    # Swap the display name for the abbreviated form where it is over the threshold.
    display = row.get(f"{side}_team_display")
    short = team_name(row, side)
    if display and short != str(display):
        base = base.replace(f">{display}<", f">{short}<")
    return base + record_span(row, side)


def winner_side(row):
    """"home", "away", "tie", or None for a game not yet played. R-029, unchanged in fact.

    `winner` is computed in dbt and carries the team NAME. Pending is distinct from a tie:
    an unplayed game has no winner YET, and a tie has no winner AT ALL. Collapsing those into
    one blank is the mistake the chip this replaced already refused to make.
    """
    if not row.get("is_completed"):
        return None
    winner = row.get("winner")
    if missing(winner):
        return "tie"
    return "home" if winner == row.get("home_team_display") else "away"


def winner_marker(row, side: str) -> str:
    """R-100 / R-113. The marker, and the SPACE FOR THE MARKER on the row that lacks it.

    If only the winning row carried a character the two scores would no longer line up
    vertically, and a misaligned pair of numbers reads as a rendering bug rather than as a
    marker. `.cfdb-winner-spacer` is a fixed-width empty inline-block, already used by the
    Scores page for exactly this.

    A glyph rather than a colour, so the result survives greyscale and a colour-blind reader
    (AC-G.22).
    """
    state = winner_side(row)
    if state == "tie":
        return f"<span class='cfdb-winner' title='the game ended level'>{TIE_GLYPH}</span>"
    if state == side:
        return f"<span class='cfdb-winner' title='won'>{WINNER_GLYPH}</span>"
    return "<span class='cfdb-winner-spacer'></span>"


def score_cell(row, side: str) -> str:
    """R-100. The winner marker moved onto the score it describes.

    It used to be its own "Won" column holding a chip with a team name in it — a full column
    of width to restate something the two numbers beside it already implied, and the name was
    a third rendering of a team already named twice on the row.
    """
    return winner_marker(row, side) + fmt.number(row.get(f"{side}_points"),
                                                 f"{side}_points", 0)


def weather_cell(row) -> str:
    """R-027. Icon plus temperature — EXCEPT indoors, where there is no temperature to give.

    CFBD reports the weather at the venue's LOCATION, not inside it, so a domed game carries
    ordinary outdoor readings. Rendering "94°F" beside a game played under a roof is a true
    number answering the wrong question, so the dome glyph stands alone.
    """
    if row.get("is_indoors"):
        return f"<span class='cfdb-wx' title='indoor venue'>{DOME_MARK}</span>"
    temp = row.get("temperature_f")
    if missing(temp):
        return ""
    code = row.get("weather_condition_code")
    glyph = WEATHER_GLYPH.get(int(code)) if not missing(code) else None
    label = row.get("weather_condition") or "conditions not recorded"
    return (f"<span class='cfdb-wx' title='{label}'>"
            f"{glyph or ''} {float(temp):.0f}°F</span>")


def result_strip(row) -> str:
    """R-141's three indicators. THE BODY MOVED TO `glyphs.result_strip` IN A147.

    ⚠️ EVERY RULE TRAVELLED WITH IT — the reserved width on an unplayed row, R-172's null-is-not-
    "none", and the dash for "we hold nothing here". Nothing was reinterpreted on the way.
    """
    return glyphs.result_strip(row)


def neutral_glyph(row) -> str:
    """R-026. ICON ALONE, NO TEXT LABEL.

    A DELIBERATE EXCEPTION to the site's glyph+label convention, decided by Marc against a
    small known user base and logged in the decision log with its reason. It is not an
    oversight and it is not to be "fixed" back to glyph+label. R-102's legend is what makes
    the exception defensible: the page explains the glyph once, at the top.
    """
    if not row.get("is_neutral_site"):
        return ""
    return f"<span class='cfdb-neutral' title='neutral site'>{NEUTRAL_GLYPH}</span>"


def columns(scope) -> list:
    return [
        # AC-2.5: the row goes to the game, the team NAME goes to the team.
        # R-146. The neutral-site flag rides the kickoff cell, which had spare width and is
        # where a reader already looks for "where and when".
        Col("start_date", "Kickoff", render=lambda r: (
            f"{fmt.clock(r.get('start_date'))}{neutral_glyph(r)}")),
        Col("away", "Away", render=lambda r: team_with_record(r, "away"),
            link=lambda r: scope.link("team", team=r.get("away_team_slug"))),
        # R-100. The "Won" chip column is gone; the marker rides the score.
        Col("away_points", "", "num", dp=0, render=lambda r: score_cell(r, "away")),
        Col("home", "Home", render=lambda r: team_with_record(r, "home"),
            link=lambda r: scope.link("team", team=r.get("home_team_slug"))),
        Col("home_points", "", "num", dp=0, render=lambda r: score_cell(r, "home")),
        Col("spread_current", "Spread", "signed"),
        # R-087. O/U, reconciled with Odds Board so one field has one name site-wide.
        Col("total_current", "O/U", "num"),
        # R-137. PRED IS SHED, AND THE BUDGET IS WHY.
        #
        # Marc set the floor at 1200px and nominated this column first if the result strip did
        # not fit. It did not: at 1200 the table wrapped Spread, O/U, Pred, the kickoff time and
        # half the numbers. Eleven columns in ~605px of content is about 55px each, and a
        # signed number with a sign, two digits and a decimal needs more than that.
        #
        # Pred rather than Wx because it is the least populated of the two — 567 of 934 games in
        # 2025 carry a predicted margin against 913 of 934 carrying weather — and because the
        # number remains one click away on Matchup, which is where a reader compares a model to
        # a market. Weather is nowhere else on this page.
        #
        # R-086's note about the header stays true and is why the label was "Pred" at all; this
        # supersedes the column, not the reasoning.
        # R-027 / R-103.
        Col("weather", "Wx", "center", render=weather_cell),
        Col("network_abbreviation", "TV"),
        # R-101. ONE COLUMN, WITH A HEADER, FOR BOTH GLYPHS.
        #
        # These were two columns — `table.details_col` and a headerless neutral-site glyph —
        # costing two column widths for at most two characters, one of which was blank on
        # 95% of rows. R-026's icon-only exception is about the ROW, not the header: a header
        # on the column is not the glyph+label pattern Marc declined.
        # R-147. Matchup icon, then the result strip, with a space between them. The strip is
        # NOT inside the anchor: it is three states of information, not a destination, and a
        # pointer cursor over it would say otherwise.
        Col("game", "Game", "center",
            render=lambda r: (f"<a class='cfdb-cell-link-alt' "
                              f"href='{scope.link('matchup', game_id=r['game_id'])}' "
                              f"target='_self' title='Open the matchup'>"
                              f"<span class='cfdb-details'>{table.DETAILS_GLYPH}</span></a>"
                              f"<span class='cfdb-strip-gap'></span>{result_strip(r)}")),
    ]


ROW_CAP = 1200


def rows(season: int, week, season_type: str, conference,
         division: str = 'fbs', high_value_only: bool = False) -> pd.DataFrame:
    """Schedule's own query. A196 added `high_value_only` and nothing else.

    🚨 TODAY'S LOOKING FORWARD READS THE SAME ROWS, SO IT CALLS THE SAME QUERY.

    ⚠️ A196 FIRST HAND-WROTE A PARALLEL SELECT FOR IT AND SHIPPED TWO COLUMNS THAT DO
    NOT EXIST — `venue_name` (it is `venue_display`) and `weather` (a synthetic column
    name Schedule's own `weather_cell` composes from `weather_condition`,
    `temperature_f` and `is_indoors`). The page raised `UndefinedColumn` into
    `states.section` and drew ONE error card — a handled failure that looks considered.
    **Guessing a column list for a table whose renderer already has one is how that
    happens**, and re-using the query removes the opportunity rather than the symptom.

    ⚠️ `high_value_only` ADDS A PREDICATE AND TWO FLAG COLUMNS. It does not change what
    Schedule selects or how it orders, so Schedule's own four call sites are untouched.
    """
    sql = """
        select game_id, season, week, season_type, start_date, game_date,
               home_team_slug, home_team_display, home_abbreviation, home_logo_url,
               home_conference, home_points, home_rank, home_team_record_display,
               away_team_slug, away_team_display, away_abbreviation, away_logo_url,
               away_conference, away_points, away_rank, away_team_record_display,
               venue_display, network, network_abbreviation, is_neutral_site,
               is_conference_game, is_completed, winner, best_rank_in_game,
               spread_current, total_current, predicted_margin, home_win_probability,
               spread_move_from_open, total_move_from_open,
               spread_at_close, spread_at_close_basis,
               total_at_close, total_at_close_basis,
               total_points, actual_margin,
               upset_level, winner_covered_close, over_met,
               upset_margin_big, upset_margin_blowout,
               home_team_record_after_display, away_team_record_after_display,
               excitement_index,
               is_indoors, temperature_f, weather_condition_code, weather_condition,
               count(*) over () as rows_in_scope,
               home_q1, home_q2, home_q3, home_q4, home_overtime_points, home_periods,
               away_q1, away_q2, away_q3, away_q4, away_overtime_points, away_periods,
               is_top25_matchup, is_undefeated_close,
               as_of_ts
        from srv_game
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          -- FBS spine: EITHER team FBS, defaulted rather than hardcoded, so
          -- 'All divisions' in the filter bar genuinely widens it.
          and (:division = 'all' or is_fbs_game)
          and (:conf is null or home_conference = :conf or away_conference = :conf)
          and (not :high_value_only or is_high_value)
        -- R-108. Date, then kickoff, then the best rank ON THE FIELD, then the home name.
        -- The rank only ever breaks a tie between games kicking at the same minute, which
        -- is exactly where a reader wants the ranked matchup first. `nulls last` is the
        -- whole of "unranked last" — without it Postgres sorts NULL high and every unranked
        -- game leads its own time slot.
        order by game_date, start_date, best_rank_in_game nulls last,
                 home_team_display, game_id
        limit {ROW_CAP}
    """.replace("{ROW_CAP}", str(ROW_CAP))
    return query(sql, {"season": season, "week": week, "season_type": season_type,
                       "conf": conference, "division": division,
                       "high_value_only": high_value_only})
