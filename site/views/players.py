"""Players — the play-level page.

Four grains on one page, and each is its own serving view because the site reads one
relation per query with no joins (G-2):

    identity + season totals   srv_player_stats      2004-2026
    game log                   srv_player_game_log   2024+
    play-level drill-down      srv_player_play       2024+

THE DEPTH IS ASYMMETRIC AND THE PAGE SAYS SO RATHER THAN HIDING IT. /stats/player/season is
`full` scope and runs back to 2004; box scores and plays are `recent` and start at 2024. A
1998 season with totals and no game log is the honest state, not a defect, so the lower
sections declare their own floor instead of rendering an empty table that looks broken.

THE PICKER IS A SEARCH, NOT A LIST. There are 65,181 players in the fact and a selectbox of
that is unusable. Typing narrows server-side, which also keeps the query bounded — every
query on this page carries a LIMIT because AC-G.39 requires one even where today's filter
happens to be small.

Names are not unique and the page must not pretend they are: 1,343 (season, first, last)
combinations map to more than one athlete, including nine Jayden Williamses. The picker
therefore shows team and position beside the name, and every link carries the slug, which
has the player id in it.
"""
import pandas as pd
import streamlit as st

from lib import filters, params, shell, states, table
from lib.query import query
from lib.table import Col

# Below this the lower two sections have no data by construction, not by accident.
BOX_SCORE_FIRST_SEASON = 2024


@st.cache_data(ttl=3600)
def _search(season: int, term: str, conference) -> pd.DataFrame:
    """Players matching a name fragment. Server-side so the result set stays bounded."""
    return query("""
        select distinct player_slug, player_name, team, position, conference
        from srv_player_stats
        where season = :season
          and lower(player_name) like :term
          and (:conference is null or conference = :conference)
        order by player_name
        limit 60
    """, {"season": season, "term": f"%{term.lower()}%", "conference": conference})


def body(page) -> None:
    scope = filters.game_scope(
        show_week=False,
        week_note="Season totals are cumulative, so a week does not scope them.")
    table.dataset_caption("Player stats", "srv_player_stats")

    with states.section("srv_player_stats"):
        season, conference = scope.season, scope.conference
        term = st.text_input("Find a player", value=params.get("q") or "",
                             placeholder="Type part of a name — e.g. Klubnik")
        if not term or len(term.strip()) < 2:
            states.empty(
                "A player's season totals, game log and every play they appear in would be here.",
                "Type at least two characters to find a player. "
                "There are 65,181 players in the warehouse, which is too many to list.")
            return

        matches = _search(season, term.strip(), conference)
        if matches.empty:
            states.empty(
                f"Players matching “{term}” would be here.",
                f"No player in {season} matches that name"
                + (f" within {conference}." if conference else "."),
                fix_label="Clear the conference filter" if conference else None,
                fix=lambda: (params.set_params(conference=None), st.rerun()))
            return

        # Team and position are in the label because the name alone is genuinely ambiguous.
        labels = [f"{r.player_name} — {r.team}" + (f" ({r.position})" if r.position else "")
                  for r in matches.itertuples()]
        slugs = matches["player_slug"].tolist()
        current = params.get("player")
        index = slugs.index(current) if current in slugs else 0
        chosen = st.selectbox(f"{len(labels)} match(es)", range(len(labels)),
                              format_func=lambda i: labels[i], index=index)
        slug = slugs[chosen]
        params.set_params(q=term.strip(), player=slug)

        _season_totals(season, slug, labels[chosen])

    _game_log(season, slug)
    _drill_down(season, slug)


# --- season totals -------------------------------------------------------------------------

def _season_totals(season: int, slug: str, label: str) -> None:
    df = query("""
        select season, player_slug, player_name, position, team, conference,
               stat_category, stat_type, stat_value, rank_desc, rank_asc, percentile,
               rank_population, class_year_display, height_display, weight_pounds, jersey,
               as_of_ts
        from srv_player_stats
        where season = :season and player_slug = :slug
        order by stat_category, stat_type
        limit 400
    """, {"season": season, "slug": slug})
    table.as_of_caption(df)

    if not df.empty:
        _identity(df.iloc[0], label)

    states.render_or_state(
        df, "srv_player_stats",
        f"{label}'s {season} totals would be here.",
        f"No season totals recorded for this player in {season}.",
        renderer=_totals_table)


def _identity(row, label: str) -> None:
    """The header block. Every field is nullable, and an em dash is the honest rendering of
    a missing one (AC-G.32) — these come from the roster feed, which cfdb holds for 2024
    onward only, so a 2011 season legitimately has none of them."""
    def show(value):
        return "—" if value is None or (isinstance(value, float) and pd.isna(value)) else value

    st.subheader(label)
    cols = st.columns(5)
    for col, (name, value) in zip(cols, [
            ("Class", show(row.get("class_year_display"))),
            ("Height", show(row.get("height_display"))),
            ("Weight", f"{int(row['weight_pounds'])} lb"
                       if pd.notna(row.get("weight_pounds")) else "—"),
            ("Jersey", f"#{int(row['jersey'])}" if pd.notna(row.get("jersey")) else "—"),
            ("Conference", show(row.get("conference")))]):
        col.metric(name, value)


def _percentile(row) -> str:
    value = row.get("percentile")
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value) * 100:.1f}%"


def _rank(row) -> str:
    """Rank WITH the population it was computed over. "40th" alone is unreadable — 40 of
    2,000 and 40 of 45 are different statements, which is why the view carries the n."""
    value, population = row.get("rank_desc"), row.get("rank_population")
    if value is None or pd.isna(value):
        return "—"
    if population is None or pd.isna(population):
        return f"{int(value)}"
    return f"{int(value)} of {int(population)}"


def _totals_table(df: pd.DataFrame) -> None:
    table.render(df, [
        Col("stat_category", "Category"),
        Col("stat_type", "Statistic"),
        Col("stat_value", "Value"),
        Col("rank_desc", "Rank", render=_rank),
        Col("percentile", "Percentile", render=_percentile),
    ], caption="srv_player_stats")


# --- game log ------------------------------------------------------------------------------

def _game_log(season: int, slug: str) -> None:
    st.divider()
    st.markdown("#### Game log")
    if season < BOX_SCORE_FIRST_SEASON:
        states.empty(
            f"A game-by-game log for {season} would be here.",
            f"Player box scores start at {BOX_SCORE_FIRST_SEASON}. Season totals above run "
            "back to 2004, so this player's season is covered — the per-game detail is not "
            "collected for it.")
        return

    with states.section("srv_player_game_log"):
        df = query("""
            select game_id, season, week, game_date, player_slug, team, opponent, home_away,
                   team_points, stat_category, stat_type, stat_raw, stat_value,
                   stat_made, stat_attempted, as_of_ts
            from srv_player_game_log
            where season = :season and player_slug = :slug
            order by week, stat_category, stat_type
            limit 600
        """, {"season": season, "slug": slug})
        states.render_or_state(
            df, "srv_player_game_log",
            f"A game-by-game log for {season} would be here.",
            "No box-score lines recorded for this player this season.",
            renderer=_game_log_table)


def _value(row) -> str:
    """One column for three shapes. A made/attempted pair renders as "12/31" with its rate,
    because the pair is what a reader recognises and the rate is what they want from it —
    and CFBD's own "--" for an uncomputed QBR is an absence, not a zero."""
    made, attempted = row.get("stat_made"), row.get("stat_attempted")
    if pd.notna(made) and pd.notna(attempted) and attempted:
        return f"{int(made)}/{int(attempted)} ({made / attempted * 100:.0f}%)"
    value = row.get("stat_value")
    if pd.notna(value):
        return f"{value:g}"
    raw = row.get("stat_raw")
    return "—" if raw in (None, "--") or pd.isna(raw) else str(raw)


def _game_log_table(df: pd.DataFrame) -> None:
    table.render(df, [
        Col("week", "Wk"),
        Col("opponent", "Opponent",
            render=lambda r: ("vs " if r.get("home_away") == "home" else "at ")
            + str(r.get("opponent") or "—")),
        Col("stat_category", "Category"),
        Col("stat_type", "Statistic"),
        Col("stat_raw", "Value", render=_value),
    ], caption="srv_player_game_log")


# --- play-level drill-down -------------------------------------------------------------------

def _drill_down(season: int, slug: str) -> None:
    st.divider()
    st.markdown("#### Every play, filterable")
    if season < BOX_SCORE_FIRST_SEASON:
        states.empty(
            f"Play-by-play for {season} would be here.",
            f"Play-level data starts at {BOX_SCORE_FIRST_SEASON}.")
        return

    with states.section("srv_player_play"):
        left, middle, right = st.columns(3)
        down = left.selectbox("Down", ["Any", "1", "2", "3", "4"])
        bucket = middle.selectbox(
            "Distance", ["Any", "short", "medium", "long", "goal to go"])
        zone = right.selectbox(
            "Field position", ["Any", "red zone", "opponent territory", "own territory"])

        df = query("""
            select play_id, season, week, game_date, player_slug, team, opponent, stat_type,
                   stat, period, down, distance, down_distance_display, distance_bucket,
                   field_zone, play_type, play_text, yards_gained, is_scoring_play, ppa,
                   as_of_ts
            from srv_player_play
            where season = :season
              and player_slug = :slug
              and (:down is null or down = :down)
              and (:bucket is null or distance_bucket = :bucket)
              and (:zone is null or field_zone = :zone)
            order by week, period, play_id
            limit 500
        """, {"season": season, "slug": slug,
              "down": None if down == "Any" else int(down),
              "bucket": None if bucket == "Any" else bucket,
              "zone": None if zone == "Any" else zone})

        filtered = any(v != "Any" for v in (down, bucket, zone))
        states.render_or_state(
            df, "srv_player_play",
            "Every play this player is credited on would be here.",
            # Coverage is genuinely partial, and saying "no plays" would be a stronger claim
            # than the data supports.
            ("No plays match those filters." if filtered
             else "No play-level lines have landed for this player. Play attribution is "
                  "collected per game and does not yet cover every game."),
            renderer=_plays_table,
            fix_label="Clear the play filters" if filtered else None,
            fix=lambda: st.rerun())


def _plays_table(df: pd.DataFrame) -> None:
    table.render(df, [
        Col("week", "Wk"),
        Col("down_distance_display", "Situation",
            render=lambda r: r.get("down_distance_display") or "—"),
        Col("field_zone", "Field"),
        Col("stat_type", "Credited"),
        Col("yards_gained", "Yds"),
        Col("play_text", "Play"),
    ], caption="srv_player_play")


def render() -> None:
    shell.render_page("players", body)
