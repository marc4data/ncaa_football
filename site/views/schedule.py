"""Schedule — page 2.

GRAIN IS ONE ROW PER GAME (AC-2.1). This is the inversion the spec once carried backwards:
a count on srv_game equals the game count for the filtered scope, never twice it, because
the view reads fct_game rather than fct_game_team.

TWO VIEWS, AS TABS (R-043). Dense is the table; Stacked is the card. Tabs rather than a
toggle because a tab is URL-addressable through st.query_params and a toggle is not — the
same finding that shaped the rest of the site's navigation. Both read the SAME single
relation and the same frame; the stacked view is a different rendering, not a second query.


THE STACKED CARD, NAMED
=======================

Shared vocabulary, so a change request can point at a part instead of describing it. Every
name below maps to the class that renders it, and `test_the_card_vocabulary_matches_the_markup`
fails if a name stops matching the markup — the map cannot rot into fiction.

TWO VARIANTS, and they are deliberately structured differently:

    RESULT CARD    a completed game.  Header row is the box-score headings; the line block
                   carries the closing line against what actually happened.
    PREVIEW CARD   a game not yet played.  Header row is empty — there are no quarters to
                   head — and the line block carries the current market.

("preview" rather than "incomplete": a game in progress is also incomplete, and on a Saturday
that difference will matter.)

THE RESULT CARD

                  ├─ team column ─┤├ line block ┤├──── box score ─────┤

    header row      7:30 PM PDT ○■◆│ Line Actual │  1   2   3   4  OT  T
    away row      ▣ Auburn    5-5 │ O/U  51.5  48 │  3   7   0   7      17
    home row    @ ▣ Alabama   9-2▸│ Sprd -7.0 -14 │  7  10   7   7      31
                  └ team cluster ┘   └ line row ┘   └ quarter cells ┘ └ final cell
    card footer   ☀ 54°F · ESPN · Bryant-Denny · ▤

THE PREVIEW CARD — same three rows, same team column, no box score.

    header row      7:30 PM PDT   │ Line  Δ Open
    away row      ▣ Auburn    5-5 │ O/U   52.5   +1.5
    home row    @ ▣ Alabama   8-2 │ Sprd  -7.5   -0.5
    card footer   ☀ 54°F · ESPN · Bryant-Denny · ▤

THE PARTS

    game card ................ cfdb-gamecard        one game, border and all
    card grid ................ cfdb-gc              the three rows; ONE grid, see R-114
    kickoff cell ............. cfdb-gc-time         header row, team column
    header cell .............. cfdb-gc-h            1 2 3 4 OT F
    team column .............. cfdb-gc-team         the flexible left column
    home marker .............. cfdb-athome          the @ or vs before the home team
    team link ................ cfdb-teamlink        logo, rank badge and name; clickable
    team record .............. cfdb-team-record     outside the link, neutral (R-129)
    winner marker ............ cfdb-winner          after the record (R-135)
    line block ............... cfdb-gc-mid          BOTH cards; result shows line against
                                                    actual, preview shows line against move
    line block header ........ cfdb-gc-mid-head     the Line / Actual (or Delta Open) heads
    quarter cell ............. cfdb-gc-n            one quarter, or the reserved OT track
    final cell ............... cfdb-gc-tot          the F column
    absence note ............. cfdb-ls-why          "no quarter scores recorded" (R-092)
    card footer .............. cfdb-gamecard-meta   weather, network, venue, matchup
    card grid (the page) ..... cfdb-cardgrid        the two-up arrangement OF cards (R-110)

    result strip ............. cfdb-strip           three indicators, in the kickoff cell
    indicator ................ cfdb-ind             one of them; shape says which

A NOTE ON "SUB-TABLE". There are none. The card was two blocks that agreed until R-114 made it
a single CSS grid, so the line block and the box score are COLUMNS OF THE SAME GRID as the team
names — which is the only reason their rows share baselines. Asking to move something "into its
own table" would undo that; asking to move it to another COLUMN or ROW will not.
"""
import re

import pandas as pd
import streamlit as st

from lib import chips, distribution, filters, fmt, params, shell, states, table
from lib.metrics import UPSET_BIG_MARGIN, UPSET_BLOWOUT_MARGIN
from lib.query import query
from lib.table import Col

# R-128. THE LABEL CHANGED; THE KEY DID NOT, AND THAT IS THE WHOLE POINT.
# The dict key is the `?view=` value, so renaming it would break every existing link to the
# table view — R-097 was about exactly this class of silent breakage.
VIEWS = {"dense": "Inline", "stacked": "Stacked"}

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

# R-104's fields, rendered. Δ rather than ▷: the direction is already carried by the sign,
# and a directional glyph beside a negative number is two cues that can disagree.
MOVE_GLYPH = "Δ"

# R-109. One letter for the score column of a box score, chosen once so a box score on any
# future page uses the same one. T for Total.
#
# R-114 removed its NEIGHBOUR rather than this: the box score used to carry an abbreviated
# team label in its first column, and once the team row became the box score's row that label
# sat three inches from the full name it abbreviated — the name twice, which is the monogram
# problem in a new place.
TOTAL_HEADER = "T"   # R-162 REVERSES R-150: Marc checked the major sites; they use T.


def _rows(season: int, week, season_type: str, conference,
          division: str = 'fbs') -> pd.DataFrame:
    sql = """
        select game_id, season, week, season_type, start_date_et, game_date,
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
               home_team_record_after_display, away_team_record_after_display,
               excitement_index,
               is_indoors, temperature_f, weather_condition_code, weather_condition,
               home_q1, home_q2, home_q3, home_q4, home_overtime_points, home_periods,
               away_q1, away_q2, away_q3, away_q4, away_overtime_points, away_periods,
               as_of_ts
        from srv_game
        where season = :season and season_type = :season_type
          and (:week is null or week = :week)
          -- FBS spine: EITHER team FBS, defaulted rather than hardcoded, so
          -- 'All divisions' in the filter bar genuinely widens it.
          and (:division = 'all' or is_fbs_game)
          and (:conf is null or home_conference = :conf or away_conference = :conf)
        -- R-108. Date, then kickoff, then the best rank ON THE FIELD, then the home name.
        -- The rank only ever breaks a tie between games kicking at the same minute, which
        -- is exactly where a reader wants the ranked matchup first. `nulls last` is the
        -- whole of "unranked last" — without it Postgres sorts NULL high and every unranked
        -- game leads its own time slot.
        order by game_date, start_date_et, best_rank_in_game nulls last,
                 home_team_display, game_id
        limit 400
    """
    return query(sql, {"season": season, "week": week, "season_type": season_type,
                       "conf": conference, "division": division})


# --- shared cell renderers ------------------------------------------------------------

def _text(value) -> str:
    """A cell value as a string, or "".

    `value or ""` IS NOT THIS, and the difference cost the stacked view fifteen rows. pandas
    returns NaN for a null in an object column, NaN is TRUTHY, so `nan or ""` evaluates to
    nan — which then fails a str.join with "expected str instance, float found". The view
    rendered the first fifteen games and died on the sixteenth, where the network was null.

    It failed inside states.section, which caught it and rendered an Error state, so there
    was no exception to see and no test to fail. It was found by counting cards against rows.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def _missing(value) -> bool:
    """Null in either of the two shapes a serving row hands back."""
    return value is None or (isinstance(value, float) and pd.isna(value))


def _team_name(row, side: str) -> str:
    """Display name, abbreviated past the threshold. R-085."""
    name = _text(row.get(f"{side}_team_display")) or "—"
    if len(name) > TEAM_NAME_MAX:
        # An abbreviation can be null for a team absent from /teams, so fall back to a
        # truncation rather than to NaN.
        return _text(row.get(f"{side}_abbreviation")) or name[:TEAM_NAME_MAX]
    return name


def _record_span(row, side: str) -> str:
    """The record, on its own. R-129 needs it separable from the part that is a link.

    The record is the one LEADING INTO this game's week, from fct_team_record_week — not the
    season-final record, which is what fct_team_record would give and which would show 11-2
    beside a game played in September. Renders NOTHING when it is absent rather than
    substituting the season figure (R-084) — and after R-127 "absent" finally means what it
    says: a team we hold no results for, not a team whose season has not started.
    """
    # R-140. A COMPLETED GAME SHOWS THE RECORD IT PRODUCED; A SCHEDULED ONE SHOWS THE RECORD
    # THE TEAM CARRIES IN. Two columns, one slot, chosen by whether the game has been played —
    # which is the only reading of Marc's sentence that can be true, since a record "after the
    # game" cannot exist for a game nobody has played.
    if row.get("is_completed"):
        record = row.get(f"{side}_team_record_after_display")
        title = "record after this game"
    else:
        record = row.get(f"{side}_team_record_display")
        title = "record going into this game"
    if _missing(record):
        return ""
    return f"<span class='cfdb-team-record' title='{title}'>{record}</span>"


def _team_with_record(row, side: str) -> str:
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
    short = _team_name(row, side)
    if display and short != str(display):
        base = base.replace(f">{display}<", f">{short}<")
    return base + _record_span(row, side)


def _winner_side(row):
    """"home", "away", "tie", or None for a game not yet played. R-029, unchanged in fact.

    `winner` is computed in dbt and carries the team NAME. Pending is distinct from a tie:
    an unplayed game has no winner YET, and a tie has no winner AT ALL. Collapsing those into
    one blank is the mistake the chip this replaced already refused to make.
    """
    if not row.get("is_completed"):
        return None
    winner = row.get("winner")
    if _missing(winner):
        return "tie"
    return "home" if winner == row.get("home_team_display") else "away"


def _winner_marker(row, side: str) -> str:
    """R-100 / R-113. The marker, and the SPACE FOR THE MARKER on the row that lacks it.

    If only the winning row carried a character the two scores would no longer line up
    vertically, and a misaligned pair of numbers reads as a rendering bug rather than as a
    marker. `.cfdb-winner-spacer` is a fixed-width empty inline-block, already used by the
    Scores page for exactly this.

    A glyph rather than a colour, so the result survives greyscale and a colour-blind reader
    (AC-G.22).
    """
    state = _winner_side(row)
    if state == "tie":
        return f"<span class='cfdb-winner' title='the game ended level'>{TIE_GLYPH}</span>"
    if state == side:
        return f"<span class='cfdb-winner' title='won'>{WINNER_GLYPH}</span>"
    return "<span class='cfdb-winner-spacer'></span>"


def _score_cell(row, side: str) -> str:
    """R-100. The winner marker moved onto the score it describes.

    It used to be its own "Won" column holding a chip with a team name in it — a full column
    of width to restate something the two numbers beside it already implied, and the name was
    a third rendering of a team already named twice on the row.
    """
    return _winner_marker(row, side) + fmt.number(row.get(f"{side}_points"),
                                                  f"{side}_points", 0)


def _weather_cell(row) -> str:
    """R-027. Icon plus temperature — EXCEPT indoors, where there is no temperature to give.

    CFBD reports the weather at the venue's LOCATION, not inside it, so a domed game carries
    ordinary outdoor readings. Rendering "94°F" beside a game played under a roof is a true
    number answering the wrong question, so the dome glyph stands alone.
    """
    if row.get("is_indoors"):
        return f"<span class='cfdb-wx' title='indoor venue'>{DOME_MARK}</span>"
    temp = row.get("temperature_f")
    if _missing(temp):
        return ""
    code = row.get("weather_condition_code")
    glyph = WEATHER_GLYPH.get(int(code)) if not _missing(code) else None
    label = row.get("weather_condition") or "conditions not recorded"
    return (f"<span class='cfdb-wx' title='{label}'>"
            f"{glyph or ''} {float(temp):.0f}°F</span>")


# R-141. THE UPSET LEVELS DIFFER ONLY BY COLOUR, and that is a decision rather than an
# oversight. It is the third deliberate exception to the site's glyph-plus-label convention
# after R-026's neutral-site icon, taken for the same reason: a small known user base, a
# legend that explains it once, and a dense row where three labelled indicators would cost more
# width than the whole rest of the cell.
UPSET_LEVEL_CLASS = {"upset": "cfdb-u1", "big": "cfdb-u2", "blowout": "cfdb-u3"}
UPSET_LEVEL_TITLE = {
    "": "no closing line, so nothing named a favorite",
    "none": "the favorite won",
    "upset": "upset",
    "big": "upset by more than a touchdown",
    "blowout": "upset by more than two touchdowns",
}
# R-181. ONE BASIS, so the tooltip states it rather than naming which of two produced the
# verdict. Still said out loud: a reader checking a surprising upset needs to know it is the
# closing spread being judged against and not a poll.
UPSET_AGAINST = "the closing spread"


# R-171. "No closing line held" is a DASH, not a shape.
#
# It was a dotted outline, which still reads as a value being shown — Marc set Division to All
# Divisions, pulled in lower-division games that carry no spread or total at all, and the strip
# came out as three faint outlines with nothing saying why. A dash is the site's existing mark
# for "we hold nothing here": `fmt.EM_DASH` does the same job in every table cell on the site.
NO_DATA_MARK = "–"


def _upset_title(level: str) -> str:
    """The verdict, and what it was judged against. R-181."""
    verdict = UPSET_LEVEL_TITLE.get(level, level)
    return f"{verdict}, against {UPSET_AGAINST}" if level else verdict


def _indicator(shape: str, state: str, title: str, extra: str = "") -> str:
    """One indicator. SHAPES, NOT EMOJI — and a different shape per POSITION.

    Marc's three states mixed emoji-presentation characters with text-presentation ones, which
    do not share a baseline, do not size together and vary by platform. A span with a
    background, a border and a radius gives one rule for size, baseline and colour.

    THE SHAPE IS WHAT MAKES EACH ONE SELF-IDENTIFYING. All three were circles, so they could
    only be told apart by their position in the strip — and position is unreadable the moment
    one of them is invisible, which is most of the time. Circle, square, diamond: a reader can
    match any single indicator to its legend entry without counting its neighbours.
    """
    # THE DASH KEEPS THE SHAPE CLASS AND THEREFORE THE BOX. R-166 aligns every card's strip
    # by giving the indicators identical footprints; a mark that sized itself differently
    # would take that alignment out from under a whole column of cards.
    mark = NO_DATA_MARK if state == "nodata" else ""
    return (f"<span class='cfdb-ind cfdb-sh-{shape} cfdb-ind-{state} {extra}' "
            f"title='{title}'>{mark}</span>")


def _result_strip(row) -> str:
    """R-141. Three indicators, populated only for a completed game.

    THE WIDTH IS RESERVED ON EVERY ROW, PLAYED OR NOT. An indicator set that appears only on
    completed games shifts the columns beside it the moment a week is half played — the
    alignment failure this page has fixed three times.

    "NOT AN UPSET" IS AN ANSWER, AND IT USED TO RENDER AS NOTHING. That made it identical to
    "not played yet", which is a different fact, and it meant the first slot was blank on all
    124 completed games of a typical week — so the two visible indicators sat in slots two and
    three and read as slots one and two. It now draws a quiet outline: present, answered,
    unremarkable. Only a game nobody has played renders truly nothing.
    """
    if not row.get("is_completed"):
        return ("<span class='cfdb-strip'>"
                + _indicator("upset", "none", "not played yet")
                + _indicator("cover", "none", "not played yet")
                + _indicator("over", "none", "not played yet")
                + "</span>")
    # R-172. NULL IS NOT "none". `is_upset` is null when neither side was ranked, and the
    # previous `or "none"` turned that absence into an assessment — a quiet circle claiming we
    # had looked. It is a dash now, the same mark the cover and total slots already use for
    # "nothing to measure against".
    upset = _text(row.get("upset_level"))
    cover, over = _text(row.get("winner_covered_close")), _text(row.get("over_met"))
    fills = {"yes": "fill", "no": "open", "push": "push"}
    parts = [
        _indicator("upset",
                   "fill" if upset in UPSET_LEVEL_CLASS
                   else "quiet" if upset == "none" else "nodata",
                   _upset_title(upset),
                   UPSET_LEVEL_CLASS.get(upset, "")),
        _indicator("cover", fills.get(cover, "nodata"),
                   {"yes": "the winner also covered the closing spread",
                    "no": "the winner did not cover the closing spread",
                    "push": "the closing spread pushed"}.get(cover, "no closing spread held"),
                   "cfdb-acc"),
        _indicator("over", fills.get(over, "nodata"),
                   {"yes": "over the closing total",
                    "no": "under the closing total",
                    "push": "landed on the closing total"}.get(over, "no closing total held"),
                   "cfdb-acc"),
    ]
    return f"<span class='cfdb-strip'>{''.join(parts)}</span>"


def _neutral_glyph(row) -> str:
    """R-026. ICON ALONE, NO TEXT LABEL.

    A DELIBERATE EXCEPTION to the site's glyph+label convention, decided by Marc against a
    small known user base and logged in the decision log with its reason. It is not an
    oversight and it is not to be "fixed" back to glyph+label. R-102's legend is what makes
    the exception defensible: the page explains the glyph once, at the top.
    """
    if not row.get("is_neutral_site"):
        return ""
    return f"<span class='cfdb-neutral' title='neutral site'>{NEUTRAL_GLYPH}</span>"


def _columns(scope) -> list:
    return [
        # AC-2.5: the row goes to the game, the team NAME goes to the team.
        # R-146. The neutral-site flag rides the kickoff cell, which had spare width and is
        # where a reader already looks for "where and when".
        Col("start_date_et", "Kickoff", render=lambda r: (
            f"{fmt.clock(r.get('start_date_et'))}{_neutral_glyph(r)}")),
        Col("away", "Away", render=lambda r: _team_with_record(r, "away"),
            link=lambda r: scope.link("team", team=r.get("away_team_slug"))),
        # R-100. The "Won" chip column is gone; the marker rides the score.
        Col("away_points", "", "num", dp=0, render=lambda r: _score_cell(r, "away")),
        Col("home", "Home", render=lambda r: _team_with_record(r, "home"),
            link=lambda r: scope.link("team", team=r.get("home_team_slug"))),
        Col("home_points", "", "num", dp=0, render=lambda r: _score_cell(r, "home")),
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
        Col("weather", "Wx", "center", render=_weather_cell),
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
                              f"<span class='cfdb-strip-gap'></span>{_result_strip(r)}")),
    ]


# R-176. TWO COLUMNS, NOT THREE. Marc: "Result should just have Won and Tied. The rest of the
# items all belong under Against The Line, which is going to be very long. Maybe move Result
# under Game so the aspect ratio works better." Eighteen marks split 7 against 11 balances
# better than 5/7/6 across three columns.
#
# §3a RESOLVED BY REMOVING THE PROBLEM RATHER THAN RENAMING AROUND IT. The objection was that
# a rank-based upset has nothing to do with the line. R-181 made the line the only basis, so
# every row in that column really is against the line and the heading is now literally true.
#
# A SHAPE ENTRY IS (shape, state, extra), NOT A PRE-JOINED CSS STRING. That is what lets
# `_legend_key` call `_indicator` — see R-178 — so the legend cannot draw a mark the row does
# not, by construction rather than by test.
LEGEND_GROUPS = [
    ("Game", [
        ("glyph", "cfdb-details", table.DETAILS_GLYPH, "Open the matchup"),
        ("glyph", "cfdb-neutral", NEUTRAL_GLYPH, "Neutral site"),
        ("glyph", "cfdb-legend-ch", DOME_MARK, "Indoors"),
        ("glyph", "cfdb-legend-ch", "@", "At the home team"),
        ("glyph", "cfdb-legend-ch", "vs", "Neutral site, no home team"),
    ]),
    ("Result", [
        ("glyph", "cfdb-winner", WINNER_GLYPH, "Won"),
        ("glyph", "cfdb-winner", TIE_GLYPH, "Tied"),
    ]),
    ("Against the line", [
        ("glyph", "cfdb-legend-ch", MOVE_GLYPH, "Change since the line opened"),
        ("shape", "upset", "quiet", "", "The favorite won"),
        # THESE NUMBERS WERE WRONG BY ONE, AND HAD BEEN SINCE R-141.
        #
        # `srv_game` classifies with a STRICT `>`: a 7-point win is level 1 and a 14-point win
        # is level 2. The labels said "7+" and "14+", which claimed the opposite at both
        # boundaries — 138 completed games in the current data carry a level the legend
        # contradicts. The data was never wrong; only this was, which is the worse failure
        # because nothing breaks visibly.
        #
        # Derived from the dbt vars rather than retyped, so the two cannot drift again. This
        # is a STOPGAP: the thresholds still reach the page by reading a file, and the real
        # fix is carrying them as columns on `srv_game` the way `training_week_floor` already
        # is (R-224). Then the page reads the row it is already fetching.
        ("shape", "upset", "fill", "cfdb-u1", f"Upset by {UPSET_BIG_MARGIN} or fewer"),
        ("shape", "upset", "fill", "cfdb-u2",
         f"Upset by {UPSET_BIG_MARGIN + 1}\u2013{UPSET_BLOWOUT_MARGIN}"),
        ("shape", "upset", "fill", "cfdb-u3", f"Upset by {UPSET_BLOWOUT_MARGIN + 1}+"),
        ("shape", "cover", "fill", "cfdb-acc", "Winner covered"),
        ("shape", "cover", "open", "cfdb-acc", "Winner did not cover"),
        ("shape", "over", "fill", "cfdb-acc", "Over"),
        ("shape", "over", "open", "cfdb-acc", "Under"),
        ("shape", "cover", "nodata", "", "No closing line held"),
        ("shape", "upset", "nodata", "", "No line, so no favorite"),
    ]),
]

# R-176: the columns are a declared LAYOUT OVER the groups, so a regroup is a change here and
# `LEGEND_GROUPS` stays the single inventory the completeness tests read.
LEGEND_COLUMNS = [["Game", "Result"], ["Against the line"]]

# R-177. Two worked examples beside the long column's heading. The strip is read as a unit of
# three and eleven rows explain it one mark at a time; a complete strip teaches the composition
# in the space of a heading.
#
# BUILT BY `_result_strip` FROM A SYNTHETIC ROW, NOT BY HAND. A legend example assembled from
# its own markup is a second implementation of the strip, and the first thing it does is drift.
LEGEND_EXAMPLES = [
    ({"is_completed": True, "upset_level": "none",
      "winner_covered_close": "yes", "over_met": "yes"},
     "favorite won · winner covered · over"),
    ({"is_completed": True, "upset_level": "big",
      "winner_covered_close": "yes", "over_met": "no"},
     "upset by 7+ · winner covered · under"),
]


def _legend_key(kind: str, *args) -> str:
    """A legend swatch. R-178, AND THE POINT IS THAT IT DELEGATES.

    THE OLD VERSION EMITTED ITS OWN EMPTY SPAN, and that is why Marc saw nothing for "No
    closing line held" and "No line and no ranking". `_indicator` puts the dash INSIDE the
    span; this function wrote `...></span>` with no content, and `.cfdb-ind-nodata` is
    transparent by design because on the row the dash is the visible thing and the box only
    holds R-166's alignment. So the two entries were not faint. They were absent.

    A GREEN TEST WAS HOLDING IT THERE. `test_a_legend_swatch_is_a_shape_or_a_glyph_and_never_
    both` asserted `shape.endswith("></span>")` — an assertion that a swatch is EMPTY. It
    passed throughout, and nobody could fix the defect without breaking it.

    The fix is not a dash here too. That would be a second implementation of "what a no-data
    indicator looks like", and this project has been bitten four times by two implementations
    of one thing. It calls `_indicator`.
    """
    if kind == "glyph":
        css, glyph = args
        return f"<span class='{css}'>{glyph}</span>"
    shape, state, extra = args
    return _indicator(shape, state, "", extra)


def _legend() -> None:
    """R-159/R-176. The legend, as a popover, in two columns.

    NOT A MODAL, deliberately: a legend is consulted WHILE looking at the thing it explains,
    and a modal covers exactly what the reader is comparing against. `st.popover` opens over
    the page, dismisses on click-away, and costs one button of space when closed.

    It also keeps the sidebar for navigation. An earlier version lived under the nav and pushed
    Streamlit's nav past its collapse threshold, hiding eight pages behind "View 8 more".

    EIGHTEEN MARKS, in two columns — Game and Result stacked on the left, the long group on the
    right. Eighteen in one list is a list nobody reads, and 7 against 11 balances better across
    two columns than 5/7/6 does across three.
    """
    by_title = dict(LEGEND_GROUPS)
    with st.popover("Legend", use_container_width=True,
                    help="What every mark on this page means"):
        columns = st.columns(len(LEGEND_COLUMNS))
        for column, titles in zip(columns, LEGEND_COLUMNS):
            blocks = []
            for title in titles:
                rows = "".join(
                    f"<div class='cfdb-legend-row'>"
                    f"<span class='cfdb-legend-key'>{_legend_key(entry[0], *entry[1:-1])}"
                    f"</span><span>{entry[-1]}</span></div>"
                    for entry in by_title[title])
                head = f"<div class='cfdb-legend-title'>{title}</div>"
                if title == LEGEND_COLUMNS[-1][0]:
                    # R-177: the examples ride the heading's line, right-aligned.
                    samples = "".join(
                        f"<span class='cfdb-legend-eg' title='{caption}'>"
                        f"{_result_strip(row)}</span>"
                        for row, caption in LEGEND_EXAMPLES)
                    head = (f"<div class='cfdb-legend-head'>"
                            f"<span class='cfdb-legend-title'>{title}</span>"
                            f"<span class='cfdb-legend-egs'>{samples}</span></div>")
                blocks.append(f"{head}{rows}")
            column.markdown(f"<div class='cfdb-legend-side'>{''.join(blocks)}</div>",
                            unsafe_allow_html=True)
        # R-177's captions, once, below the examples they describe — a tooltip on a strip in a
        # popover is a tooltip inside a tooltip.
        captions = " &nbsp;·&nbsp; ".join(caption for _, caption in LEGEND_EXAMPLES)
        st.markdown(f"<div class='cfdb-legend-egcap'>Examples: {captions}</div>",
                    unsafe_allow_html=True)
        # R-158: the sign convention is a CONVENTION, which is what a legend is for.
        # SPREAD_SIGN_NOTE is markdown and this is an HTML block, so `**bold**` would render as
        # literal asterisks. Converted rather than restated — R-009 made it a shared constant
        # precisely so there would not be a second copy to drift.
        note = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", chips.SPREAD_SIGN_NOTE)
        st.markdown(f"<div class='cfdb-legend-note'>{note}</div>", unsafe_allow_html=True)


# === THE WEEK BAND ========================================================================
#
# Marc: *"I'd start with a Week subgrouping in Schedule and have each of the metrics shown in
# that header bar."*
#
# THREE METRICS, AND WHICH THREE IS THE ARGUMENT. The implied pair is the headline because it
# is the only thing on this page that moves with the season: measured over 2024-25, the gap
# between the implied favorite and underdog runs 20.3 points in weeks 1-3 and 10.1 from week 5
# on, and it replicates to a tenth of a point across the two seasons. The O/U rides alongside
# as the CONTROL — it swings 1.4 points all season, and a reader who sees two numbers moving
# and one holding still learns something the two alone do not tell them.
#
# The implied pair shares one axis (0..60), so the horizontal gap between the two humps IS the
# spread and the pair converging through the season is visible without reading a number.
#
# `spread_abs` and `temperature_f` are computed and published; they are simply not in this
# band. Three fits at 1200px and four does not, and prompt 036 spent a round removing eleven
# rows from above the first card — a band that wraps hands them straight back.
BAND_METRICS = [
    ("market_implied_favorite_points", "Implied fav"),
    ("market_implied_underdog_points", "Implied dog"),
    ("total", "O/U"),
]


@st.cache_data(ttl=900)
def _distributions(season: int, season_type: str) -> pd.DataFrame:
    """Every distribution row for this season, both spans.

    ONE RELATION, as the contract requires. The whole season is fetched rather than the weeks
    on screen because it is a few hundred rows either way and the cache key is then the season
    rather than the filter state — a reader stepping through weeks hits the cache instead of
    the database.
    """
    return query("""
        select season, season_type, week, span, metric, as_of_date,
               games_in_week, n, coverage_pct, games_locked, games_live, is_locked,
               mean, stddev, min_value, max_value,
               p02, p05, p25, p50, p75, p95, p98,
               iqr, whisker_lo, whisker_hi, outlier_count,
               bin_min, bin_max, bin_incr, bin_count,
               below_min_count, above_max_count, bin_counts,
               row_number() over (partition by season, season_type, week, span, metric
                                  order by as_of_date desc) as recency
        from srv_week_metric_distribution
        where season = :season and season_type = :season_type
        order by week, span, metric
        limit 4000
    """, {"season": season, "season_type": season_type})


def _latest(df: pd.DataFrame, week: int, span: str, metric: str):
    """The newest snapshot for one grain, or None.

    None is a real answer: a week nobody has priced has no row, and the renderer draws a
    reserved empty box rather than nothing. The snapshot history is what makes "the O/U
    tightened over four days" answerable and is not what a header bar shows, so only the
    latest is used here.
    """
    if df is None or df.empty:
        return None
    hit = df[(df["recency"] == 1) & (df["week"] == week)
             & (df["span"] == span) & (df["metric"] == metric)]
    return None if hit.empty else hit.iloc[0]


def _band_strip(dists: pd.DataFrame, week: int, span: str) -> str:
    return "".join(distribution.thumbnail(_latest(dists, week, span, metric), label)
                   for metric, label in BAND_METRICS)


def _week_band(dists: pd.DataFrame, week: int, scope) -> None:
    """One row above a week's games. Never two, and never repeated per day."""
    note = ""
    if scope.division == "all":
        # THE DISTRIBUTION IS FBS-ONLY AND THE PAGE'S DIVISION FILTER IS NOT.
        # With Division set to All, the cards below include games these numbers exclude.
        # Saying so is cheaper than a reader adding them up and finding they disagree; the
        # alternative was a division dimension on the grain, which roughly triples the rows
        # to fix a mismatch that only appears at this one setting.
        note = ("<span class='cfdb-dist-label' title='These distributions cover FBS games "
                "only \u2014 either team FBS \u2014 while the cards below include every "
                "division you have selected.'>FBS only</span>")
    st.markdown(
        f"<div class='cfdb-weekband'>"
        f"<span class='cfdb-weekband-title'>Week {int(week)}</span>{note}"
        f"<span class='cfdb-weekband-strip'>{_band_strip(dists, week, 'week')}</span>"
        f"</div>", unsafe_allow_html=True)


def _season_to_date_band(dists: pd.DataFrame, weeks) -> None:
    """The reference line, at the top of the page.

    ACCUMULATES THROUGH THE WEEK BEFORE THE ONE SHOWN, so the reference does not contain the
    thing being referenced — the same rule srv_game's `series` CTE applies to a head-to-head
    record. In week 1 there is nothing before it, so there is no row and no band: an Empty
    state rather than a zero.

    KEYED ON THE LATEST WEEK ON SCREEN, not the earliest. Schedule's default is one week, and
    for that case the two are identical — through W-1, no overlap with what is shown. With
    Week set to All the earliest is week 1, which has no season-to-date row at all, and the
    band would silently vanish exactly when "an overall reference" is most useful. The latest
    week gives the fullest figure the season has.

    The honest cost of that choice, stated once: in a multi-week view the reference DOES
    overlap the weeks below it. That is fine there — the per-week bands are already the
    week-over-week story, and this line's job is the season as a whole — but it is a real
    difference from the single-week case and not an oversight.
    """
    if not len(weeks):
        return
    week = int(max(weeks))
    if not any(_latest(dists, week, "season_to_date", m) is not None
               for m, _ in BAND_METRICS):
        return
    st.markdown(
        f"<div class='cfdb-weekband'>"
        f"<span class='cfdb-weekband-title'>Season to date</span>"
        f"<span class='cfdb-dist-label'>through week {week - 1}</span>"
        f"<span class='cfdb-weekband-strip'>"
        f"{_band_strip(dists, week, 'season_to_date')}</span>"
        f"</div>", unsafe_allow_html=True)


def _by_week(df: pd.DataFrame, scope, render_day) -> None:
    """Week band, then the days inside it. Shared by both views so they cannot diverge.

    THE BAND MUST NOT REPEAT PER DAY, which is why the grouping is week-then-day rather than
    the day-only grouping both views had. With Schedule's default single week that is one
    band and it reads as a page header; with Week set to All it is one per week and the
    thumbnails become a genuine week-over-week strip. Both cases have to look deliberate.
    """
    dists = _distributions(scope.season, scope.season_type)
    _season_to_date_band(dists, df["week"].unique())
    for week, week_rows in df.groupby(df["week"], sort=True):
        _week_band(dists, week, scope)
        for day, rows in week_rows.groupby(week_rows["game_date"], sort=True):
            st.markdown(f"<div class='cfdb-daygroup'>{pd.Timestamp(day):%A %d %B %Y}</div>",
                        unsafe_allow_html=True)
            render_day(rows)


# --- the two views --------------------------------------------------------------------

def _dense(df: pd.DataFrame, scope) -> None:
    """AC-2.2: grouped by day, kickoff order within a day, with day headers."""
    layout = table.column_layout(df, _columns(scope))
    _by_week(df, scope, lambda rows: table.render(
        rows, _columns(scope), caption="", layout=layout,
        link_builder=lambda r: scope.link("matchup", game_id=r["game_id"])))


# --- the stacked view -----------------------------------------------------------------

def _has_periods(row, side: str) -> bool:
    periods = row.get(f"{side}_periods")
    return not _missing(periods)


# The numeric tracks, in rem so they do not move with the box score's own font size.
QUARTER_TRACK = "2.1rem"
TOTAL_TRACK = "3.4rem"


def _linescore_geometry(df: pd.DataFrame) -> dict:
    """R-015 FOR THE STACKED VIEW: the box score's shape decided ONCE, for the whole page.

    The dense view has done this since it was built — `_dense` computes `column_layout`
    outside the day loop and hands the same widths to every day's table. The cards had no
    equivalent: every `.cfdb-linescore` auto-sized to its own contents, so a card with an OT
    column was wider than the one beside it and the row labels started at a different x on
    every card. In a two-up grid that reads as broken alignment.

    ONE PAGE-WIDE FACT IS LEFT, AND R-116 IS WHY IT SURVIVED R-114.

      ot   does ANY game on this page need an OT column. If one does, EVERY card reserves the
           track — that is Marc's "the amount of space should still be the same up/down days"
           — but only a game that actually went to overtime DRAWS anything in it, which is his
           "should only show OT column if that game went into OT". Reserved and drawn are
           different decisions and the two sentences only look contradictory.

    `label_ch` is gone with the label column. R-114 makes the team row the box score's row, so
    an abbreviation beside the full name three inches to its left was the name twice — the
    monogram problem in a new place. R-109 asked for abbreviations when the box score stood
    alone; it does not any more.

    THE MEASUREMENT THAT PRODUCED `_ls_width` IS NOT LOST, IT IS DESIGNED OUT. That function
    existed because `table-layout:fixed` with `width:auto` still runs a content pass to decide
    the table's own width, which let the label column vary 31–46px across sixty cards on one
    page. A grid track stated in rem is not negotiable, so the failure has nowhere to live.
    """
    return {"ot": any(not _missing(row.get(f"{side}_periods"))
                      and int(row.get(f"{side}_periods")) > 4
                      for _, row in df.iterrows() for side in ("home", "away"))}


def _tracks(geo: dict) -> int:
    """Numeric columns: four quarters, the reserved OT track, and the total."""
    return 4 + (1 if geo["ot"] else 0) + 1


# R-149. The middle block's own tracks, as one sub-grid inside a single card-grid cell.
# Widened from 10.2rem to carry the line block's own horizontal padding, which is what
# separates it from the box score and from the team column.
MIDDLE_TRACK = "11.2rem"


def _right_span(geo: dict) -> str:
    """Everything to the right of the team column, as ONE span. R-149's regression fix.

    A scheduled card fills the row with two cells — the team cluster and one wide cell — so
    that wide cell has to cover EVERY remaining track: the middle block's and the box score's.
    The two places that needed this number computed it separately, R-149 widened one of them
    and not the other, and the header row came out a column short. CSS grid does not complain
    about that; it silently reflows every following cell one column right, which is why the
    logos ended up on the far side of the card with the names pushed out of view.

    One function, so the two cannot disagree again.
    """
    return f"grid-column:span {_tracks(geo) + 1}"


def _grid_style(geo: dict) -> str:
    quarters = 4 + (1 if geo["ot"] else 0)
    # R-149 IS A THIRD COLUMN OF THE SAME GRID, not a block bolted beside it. Row 2 and row 3
    # of the card already exist and already carry the team names and the box score; the market
    # or result numbers become the middle cell of those same rows, so they arrive on the team
    # names' baselines by construction. Anything else and the alignment R-114 bought goes.
    return (f"grid-template-columns:minmax(0,1fr) {MIDDLE_TRACK} "
            f"repeat({quarters},{QUARTER_TRACK}) {TOTAL_TRACK}")


def _line_block_header(preview: bool) -> str:
    """Row 1 of the line block. Two headings only — the label column heads nothing.

    "Actual" rather than "Final" on a result card: the box score's last column is already
    headed F for Final (R-150), and two columns headed the same thing on one card, meaning
    different things, is worse than a word that is merely less punchy.
    """
    second = f"{MOVE_GLYPH} Open" if preview else "Actual"
    return (f"<div class='cfdb-gc-mid cfdb-gc-mid-head'>"
            f"<span></span>"
            f"<span class='cfdb-gc-mid-line'>Line</span>"
            f"<span class='cfdb-gc-mid-actual'>{second}</span></div>")


def _cell(content: str, classes: str) -> str:
    return f"<div class='{classes}'>{content}</div>"


def _header_cells(geo: dict, row) -> str:
    """Row 1's right-hand side: the quarter headers, on the kickoff time's line.

    THAT SHARED LINE IS THE WHOLE OF R-114. The header used to belong to a table the teams
    block knew nothing about, which is precisely why the two rows below it sat low.
    """
    game_ot = (_has_periods(row, "home")
               and int(row.get("home_periods") or 0) > 4)
    cells = []
    for index, label in enumerate(("1", "2", "3", "4")):
        edge = " cfdb-gc-bl" if index == 0 else ""
        cells.append(_cell(label, f"cfdb-gc-h cfdb-gc-b cfdb-gc-bt{edge}"))
    if geo["ot"]:
        # R-116: reserved on every card, drawn only where there was an overtime.
        cells.append(_cell("OT" if game_ot else "",
                           "cfdb-gc-h" + (" cfdb-gc-b cfdb-gc-bt" if game_ot else "")))
    cells.append(_cell(TOTAL_HEADER, "cfdb-gc-h cfdb-gc-b cfdb-gc-bt cfdb-gc-bl"))
    return "".join(cells)


def _score_cells(row, side: str, geo: dict) -> str:
    """One team's quarters and total, as cells of the CARD's grid rather than a table's."""
    has = _has_periods(row, side)
    game_ot = has and int(row.get(f"{side}_periods") or 0) > 4
    cells = []
    for index, quarter in enumerate((1, 2, 3, 4)):
        value = row.get(f"{side}_q{quarter}")
        # R-092: absent, not zero. A row of zeros would claim four scoreless quarters.
        text = "—" if not has else ("" if _missing(value) else str(int(value)))
        edge = " cfdb-gc-bl" if index == 0 else ""
        cells.append(_cell(text, f"cfdb-gc-n cfdb-gc-b{edge}"))
    if geo["ot"]:
        overtime = row.get(f"{side}_overtime_points")
        cells.append(_cell(
            "" if not game_ot else ("0" if _missing(overtime) else str(int(overtime))),
            "cfdb-gc-n" + (" cfdb-gc-b" if game_ot else "")))
    # R-135: the total is just the total now. The marker moved to the team cluster, so this
    # cell carries no spacer either — both totals are plain numbers and align on their own.
    points = row.get(f"{side}_points")
    total = "" if _missing(points) else str(int(points))
    cells.append(_cell(total, "cfdb-gc-tot cfdb-gc-b cfdb-gc-bl"))
    return "".join(cells)


def _middle_cells(row) -> tuple:
    """R-149. The post-game mirror of the pre-game market block.

        label   |  line (at close)  |  actual
        O/U     |  total_at_close   |  total_points
        Spread  |  spread_at_close  |  actual_margin

    THE MOVE COLUMN IS NOT BUILT. Marc listed it as "would be nice", and the middle block
    already takes the card's minimum width from 560px to 700px — a fourth column pushes past
    what fits beside a two-up grid at the 1200px floor. Said here rather than silently dropped.

    `basis` rides the title because for a game older than 2026-08-15 the closing number is
    CFBD's recorded line rather than one we watched, and a page that shows the two identically
    is claiming a provenance it does not have.
    """
    rows = []
    for label, line, actual, basis, signed in (
            ("O/U", row.get("total_at_close"), row.get("total_points"),
             row.get("total_at_close_basis"), False),
            ("Spread", row.get("spread_at_close"), row.get("actual_margin"),
             row.get("spread_at_close_basis"), True)):
        if _missing(line) and _missing(actual):
            rows.append(None)
            continue
        shown = ("" if _missing(line) else
                 (fmt.signed(line, "spread_at_close") if signed
                  else fmt.number(line, "total_at_close")))
        # dp=0 on both: a margin and a points total are whole numbers of points. The line
        # beside them keeps its half-point, which is the real difference between the two
        # columns and worth seeing.
        got = ("" if _missing(actual) else
               (fmt.signed(actual, "actual_margin", 0) if signed
                else fmt.number(actual, "total_points", 0)))
        hint = ("the last line before kickoff" if basis == "observed_before_kickoff"
                else "as recorded by CollegeFootballData, not a line we observed")
        rows.append(
            f"<div class='cfdb-gc-mid'>"
            f"<span class='cfdb-gc-mid-label'>{label}</span>"
            f"<span class='cfdb-gc-mid-line' title='{hint}'>{shown}</span>"
            f"<span class='cfdb-gc-mid-actual'>{got}</span></div>")
    # A CELL ALWAYS, EVEN WITH NOTHING IN IT — and this is the second time that has mattered.
    #
    # Returning "" here dropped the middle cell from a completed row, so the row covered one
    # column fewer than the grid declares and everything after it reflowed one track right,
    # collapsing the `minmax(0,1fr)` team column to zero width. On the deployed site exactly
    # one card in 400 hit it: Delta State at Northeastern State, a completed game with no
    # closing line held, where the name rendered at 0px.
    #
    # The empty div is invisible; what it does is hold the column. Same reasoning as the
    # reserved indicator in `_result_strip` and the reserved OT track in `_score_cells`.
    blank = "<div class='cfdb-gc-mid'></div>"
    return rows[0] or blank, rows[1] or blank


def _market_cells(row, geo: dict) -> tuple:
    """R-118. The two market lines as row 2 and row 3 of the same grid.

    Away row carries the total and home row the spread, so each number sits beside the team
    it is quoted against — which now means ON ITS BASELINE, not merely near it.

    Returns ("", "") when there is no line. A market that does not exist yet is not a missing
    value: R-106 says nothing, not an empty slot and not a dash.
    """
    # THE MARKET OCCUPIES THE MIDDLE TRACK, NOT THE WHOLE RIGHT SIDE.
    #
    # Spanning everything let the inner `1fr` stretch, so the label sat at one edge and the
    # number at the other with a hand's width of nothing between them. In the middle track it
    # lands at exactly the x where a COMPLETED card puts its O/U and Spread — the two card
    # types are deliberately structured differently, and this is what keeps a reader's eye in
    # one place as they scan down a day that mixes them.
    tail = f"<div style='grid-column:span {_tracks(geo)}'></div>"
    lines = []
    for label, value, move, kind in (
            ("O/U", row.get("total_current"), row.get("total_move_from_open"), "num"),
            ("Spread", row.get("spread_current"), row.get("spread_move_from_open"), "sign")):
        if _missing(value):
            lines.append(None)
            continue
        shown = (fmt.signed(value, "spread_current") if kind == "sign"
                 else fmt.number(value, "total_current"))
        moved = "" if _missing(move) else f"{MOVE_GLYPH} {fmt.signed(move, 'move')}"
        lines.append(
            f"<div class='cfdb-gc-mid'>"
            f"<span class='cfdb-gc-mid-label'>{label}</span>"
            f"<span class='cfdb-gc-mid-line'>{shown}</span>"
            f"<span class='cfdb-gc-mid-actual'>{moved}</span></div>")
    if not any(lines):
        return "", ""
    blank = "<div class='cfdb-gc-mid'></div>"
    return (lines[0] or blank) + tail, (lines[1] or blank) + tail


def _why_missing(row) -> str:
    """R-092. ABSENT, NOT ZERO — and the card says WHICH.

    Only 44,775 of 110,879 games carry quarters: 64,254 hold an empty array and 1,850 hold
    JSON null, and the earliest is 2001. Modern seasons are effectively complete, so the gap
    is historical. Omitting the block silently would be honest about the value and silent
    about the reason, which leaves a reader wondering whether the page is broken.

    This is for a COMPLETED game whose quarters were never recorded. R-106 keeps it away from
    a scheduled one: a scheduled game is not a game whose quarter scores are missing.
    """
    if _has_periods(row, "away") or _has_periods(row, "home"):
        return ""
    season = row.get("season")
    text = ("Quarter scores are not recorded before 2001."
            if not _missing(season) and int(season) < 2001
            else "No quarter scores recorded for this game.")
    return f"<div class='cfdb-ls-why'>{text}</div>"


def _team_row(row, side: str, scope) -> str:
    """R-105 / R-107 / R-112 / R-117, all on one line of the card.

    R-105 — the cluster is ONE grid cell. `table.team_cell()` returns SEVERAL sibling spans
    and `_team_with_record` appends another; dropping that into a flex row with
    `justify-content:space-between` made every span its own flex item and spread all of them
    across ~1,400px. The `.4rem` margins were applied and then overwhelmed.

    R-107 — THE CARD APPLIES THE LINK ITSELF. `team_cell` does not build an anchor; in the
    dense table the href comes from the COLUMN's `link`, and a card has no column. Its own
    docstring records that `slug_field` "was accepted and ignored for weeks, which is why
    every team name on the site was inert text".

    R-112 — the home row is marked `@`, or `vs` at a neutral site, which is the only thing on
    the card that says which side is home. Away-over-home is a convention the reader was
    expected to hold, and at a neutral site it tells them something false.

    R-117 — THE RECORD IS INSIDE THE ANCHOR. It was a sibling span outside it, so the two
    things that name the team were one link and one piece of inert text beside it.
    """
    if side == "home":
        neutral = row.get("is_neutral_site")
        glyph = "vs" if neutral else "@"
        title = ("neutral site — neither team is at home" if neutral
                 else f"at {_text(row.get('home_team_display'))}")
        marker = f"<span class='cfdb-athome' title='{title}'>{glyph}</span>"
    else:
        marker = "<span class='cfdb-athome'></span>"
    # R-129 REVERSES R-117. The record leaves the anchor entirely rather than being styled to
    # look non-clickable — styling cannot remove the pointer cursor, and dead text under a
    # pointer is worse than either state.
    linked = table.team_cell(row, f"{side}_team_slug", f"{side}_team_display",
                             f"{side}_logo_url", f"{side}_rank")
    display = row.get(f"{side}_team_display")
    short = _team_name(row, side)
    if display and short != str(display):
        linked = linked.replace(f">{display}<", f">{short}<")
    slug = row.get(f"{side}_team_slug")
    if not _missing(slug):
        href = scope.link("team", team=slug)
        linked = f"<a class='cfdb-teamlink' href='{href}' target='_self'>{linked}</a>"
    # R-135 REVERSES R-120: the marker moves out of the total cell to sit after the record, at
    # the team name's size. It TRAILS the cluster, so unlike R-120 nothing shifts when only one
    # row carries it — the spacer is kept anyway so the two rows stay identical in structure
    # and a later change to alignment or ordering cannot reintroduce the drift.
    return (f"<div class='cfdb-gc-team'>{marker}{linked}"
            f"{_record_span(row, side)}{_winner_marker(row, side)}</div>")


def _card(row, scope, geo: dict) -> str:
    """One game, as a single grid.

    NOTE ON LINKS: the card is a <div>, not an <a>. The team names are already anchors and
    <a> cannot nest, so Matchup gets its own explicit affordance in the meta line — the same
    glyph, and the same reasoning, as `table.details_col`.
    """
    completed = bool(row.get("is_completed"))
    if completed:
        header = _line_block_header(preview=False) + _header_cells(geo, row)
        mid_away, mid_home = _middle_cells(row)
        away = mid_away + _score_cells(row, "away", geo)
        home = mid_home + _score_cells(row, "home", geo)
        why = _why_missing(row)
    else:
        # R-106: the box score is a POST-GAME element. Row 1 carries no header because there
        # are no quarters to head.
        away, home = _market_cells(row, geo)
        # Same shape as the result card: the line block gets its own header cell and the
        # box-score tracks are one silent span. Splitting it this way is what lets both
        # variants share `_line_block_header` and keeps the column coverage identical.
        span = f"grid-column:span {_tracks(geo)}"
        header = _line_block_header(preview=True) + f"<div style='{span}'></div>"
        if not away:
            # R-106: no line yet means NOTHING there — not an empty slot, not a dash. The row
            # still has to cover its columns, so it is two silent cells: an UNCLASSED div in
            # the line-block track, because `.cfdb-gc-mid` would draw its divider rule beside
            # an empty column, and the span across the box-score tracks.
            away = home = f"<div></div><div style='{span}'></div>"
        why = ""
    matchup = (f"<a href='{scope.link('matchup', game_id=row['game_id'])}' target='_self' "
               f"title='Open the matchup'><span class='cfdb-details'>"
               f"{table.DETAILS_GLYPH}</span></a>")
    # R-119: the SAME `_weather_cell` the dense Wx column uses, dome case included, so one
    # field looks the same in both tabs.
    meta = " · ".join(x for x in [
        _weather_cell(row),
        _text(row.get("network_abbreviation")),
        (f"{NEUTRAL_GLYPH} neutral site" if row.get("is_neutral_site") else ""),
        _text(row.get("venue_display")),
    ] if x)
    return (
        f"<div class='cfdb-gamecard'>"
        f"<div class='cfdb-gc' style='{_grid_style(geo)}'>"
        # R-114: the kickoff shares row 1 with the box-score header.
        f"<div class='cfdb-gc-time'>{fmt.clock(row.get('start_date_et'))}"
        f"<span class='cfdb-strip-gap'></span>{_result_strip(row)}</div>{header}"
        f"{_team_row(row, 'away', scope)}{away}"
        f"{_team_row(row, 'home', scope)}{home}"
        f"</div>{why}"
        f"<div class='cfdb-gamecard-meta'>{meta}{' · ' if meta else ''}{matchup}</div>"
        f"</div>")


def _stacked(df: pd.DataFrame, scope) -> None:
    """Away over home, details to the right. R-043.

    Built from the same frame as the dense view — no second query and no app-side join, which
    is the single-relation rule and also why the two views cannot disagree with each other.

    R-110: the cards go into a CSS grid, not `st.columns`. Streamlit renders server-side and
    cannot measure a viewport, so `st.columns(2)` would be a fixed two-up that keeps two
    cards side by side on a phone; `auto-fit` + `minmax` lets the browser reflow on its own,
    with no JavaScript and no custom component. Day groups still head their own section.
    """
    geo = _linescore_geometry(df)          # R-015: once for the page, not once per card.

    def day_of_cards(rows):
        cards = "".join(_card(r, scope, geo) for _, r in rows.iterrows())
        st.markdown(f"<div class='cfdb-cardgrid'>{cards}</div>", unsafe_allow_html=True)

    _by_week(df, scope, day_of_cards)


VIEW_KEY = "schedule_view"


def _view_switch(keys: list) -> str:
    """R-043's tab, without the double-take Marc reported: "I select it, then it moves and
    then quickly moves back. The second time I select it the change sticks."

    THE CAUSE IS AN `index=` ARGUMENT ON A WIDGET WITH NO `key=`, PLUS A URL WRITE.
    `params.set_params` assigns to `st.query_params`, and that assignment triggers a rerun of
    its own. So one click produced two passes:

        pass 1   the click sets the widget to Stacked, but `index` is still computed from the
                 URL, which says Dense — so the explicit index wins and it snaps back
        pass 2   the URL write from pass 1 has landed, `index` now says Stacked, and it sticks

    The visible flicker IS that sequence. Fixing it means removing the fight rather than
    damping it: a keyed widget owns its own value, `on_change` writes the URL in the SAME
    pass, and no `index` is passed at all.

    THE URL IS STILL THE SOURCE OF TRUTH ON ARRIVAL (R-043 — the tab is the URL, so a link to
    the stacked view lands on the stacked view). The mirror below is what tells an incoming
    link apart from a click: if the URL has changed since we last wrote it, a link was
    followed and the widget adopts it; otherwise the widget is authoritative.
    """
    from_url = params.get("view")
    from_url = from_url if from_url in keys else keys[0]
    mirror = f"{VIEW_KEY}_url"
    if st.session_state.get(mirror) != from_url:
        st.session_state[VIEW_KEY] = from_url
        st.session_state[mirror] = from_url

    def _sync() -> None:
        picked = st.session_state[VIEW_KEY]
        st.session_state[mirror] = picked
        params.set_params(view=picked)

    st.radio("View", keys, key=VIEW_KEY, horizontal=True,
             format_func=lambda k: VIEWS[k], label_visibility="collapsed",
             on_change=_sync)
    return st.session_state[VIEW_KEY]


def body(page) -> None:
    scope = filters.game_scope()
    with states.section("srv_game"):
        df = _rows(scope.season, scope.week, scope.season_type, scope.conference,
                   scope.division)
        table.as_of_caption(df)          # R-158: into Band 1, beside the status.
        df = table.apply_sort(df, _columns(scope))

        # R-158 BAND 3, reordered: the view switch is the row's only CONTROL, so it leads.
        # Dataset and the Legend button are references and follow it.
        switch, dataset, legend_slot = st.columns([2, 2, 1],
                                                  vertical_alignment="center")
        with switch:
            chosen = _view_switch(list(VIEWS))
        with dataset:
            table.dataset_caption("Schedule", "srv_game")
        with legend_slot:
            _legend()

        states.render_or_state(
            df, "srv_game",
            "The week's games would be listed here.",
            f"No games match {scope.describe()}.",
            renderer=lambda d: (_stacked(d, scope) if chosen == "stacked"
                                else _dense(d, scope)),
            fix_label="Clear filters", fix=filters.clear)


def render() -> None:
    shell.render_page("schedule", body)
