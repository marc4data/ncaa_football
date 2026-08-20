"""Stats — page 6. One statistic, every team, ranked.

The shape is a leaderboard rather than a team-by-stat grid because the view's grain is
(season, team, stat) and a grid would need the app to pivot — which is transformation, not
display. Picking the statistic and reading down the ranking is also the question this page
actually gets asked.

The opponent-scope caveat is the honest part. `srv_team_stats` has no `stat_scope` or
`stat_basis` column; what it has is CFBD's own naming, where the opponent variant of a
statistic is a SEPARATE stat with an `Opponent` suffix. So `firstDowns` and
`firstDownsOpponent` appear as two entries in the picker, which is exactly what the data
says. Deriving a scope flag from the suffix here would be the app inventing a dimension the
warehouse does not have, and it would be wrong the first time CFBD names something
differently — so the picker stays literal and the gap is declared in the registry.
"""
import pandas as pd
import streamlit as st

from lib import params, shell, states, table
from lib.query import query
from lib.table import Col

# Ranking direction is a property of the statistic and cfdb does not model it yet, so the
# view carries BOTH ranks and the page lets the reader choose. Guessing per stat name would
# be a lookup table of 63 entries maintained in the app — the wrong place, and it would be
# silently wrong for any stat added later.
DIRECTIONS = {"Highest first": ("rank_desc", "desc"), "Lowest first": ("rank_asc", "asc")}
BY_PARAM = {code: label for label, (_, code) in DIRECTIONS.items()}


@st.cache_data(ttl=3600)
def _seasons() -> list:
    return query("select distinct season from srv_team_stats order by season desc limit 200"
                 )["season"].tolist()


@st.cache_data(ttl=3600)
def _stat_names(season: int) -> list:
    return query("""select distinct stat_name from srv_team_stats
                    where season = :season order by stat_name limit 500""",
                 {"season": season})["stat_name"].tolist()


@st.cache_data(ttl=3600)
def _conferences(season: int) -> list:
    return query("""select distinct conference from srv_team_stats
                    where season = :season and conference is not null
                    order by conference limit 60""", {"season": season})["conference"].tolist()


def body(page) -> None:
    with states.section("srv_team_stats"):
        seasons = _seasons()
        if not seasons:
            states.empty("A statistical leaderboard would be here.",
                         "No season statistics have been built yet.")
            return

        requested = params.get("season")
        season = requested if requested in seasons else seasons[0]

        stats = _stat_names(season)
        conferences = ["All"] + _conferences(season)
        with st.sidebar:
            season = st.selectbox("Season", seasons, index=seasons.index(season))
            # Re-read after the season changes: offering a stat that does not exist in the
            # chosen season would produce an Empty state the reader caused by using our own
            # control, which AC-G.16 exists to prevent.
            stats = _stat_names(season)
            current_stat = params.get("stat")
            stat_name = st.selectbox(
                "Statistic", stats,
                index=stats.index(current_stat) if current_stat in stats else 0)
            labels = list(DIRECTIONS)
            current_order = BY_PARAM.get(params.get("order"), labels[0])
            direction = st.radio("Order", labels, horizontal=True,
                                 index=labels.index(current_order))
            conferences = ["All"] + _conferences(season)
            chosen_conf = params.get("conference")
            conference = st.selectbox(
                "Conference", conferences,
                index=conferences.index(chosen_conf) if chosen_conf in conferences else 0)

        conference = None if conference == "All" else conference
        rank_field, order_code = DIRECTIONS[direction]
        params.set_params(season=season, stat=stat_name, conference=conference,
                          order=order_code)
        df = query(f"""
            select season, team_slug, team_display, conference, classification, logo_url,
                   stat_name, stat_value, stat_value_raw, rank_desc, rank_asc, percentile,
                   as_of_ts
            from srv_team_stats
            where season = :season
              and stat_name = :stat_name
              and (:conference is null or conference = :conference)
            order by {rank_field}
            limit 300
        """, {"season": season, "stat_name": stat_name, "conference": conference})
        table.as_of_caption(df)

        states.render_or_state(
            df, "srv_team_stats",
            f"The {season} leaderboard for {stat_name} would be here.",
            "No team recorded this statistic under the current filters."
            + (f" Conference filter “{conference}” may be too narrow." if conference else ""),
            renderer=lambda d: _leaderboard(d, rank_field),
            fix_label="Clear the conference filter" if conference else None,
            fix=lambda: (params.set_params(conference=None), st.rerun()))


def _rank_cell(row, rank_field: str) -> str:
    value = row.get(rank_field)
    return "—" if value is None or pd.isna(value) else f"{int(value)}"


def _percentile(row) -> str:
    """A percentile is a rate, and a rate on this page is a full-population figure.

    Rendered as a percentage rather than a 0–1 decimal because every other rate on the site
    is a percentage, and a column that reads 0.9926 next to columns that read 99.3% is the
    kind of inconsistency that makes a reader distrust both.
    """
    value = row.get("percentile")
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value) * 100:.1f}%"


def _leaderboard(df: pd.DataFrame, rank_field: str) -> None:
    table.render(df, [
        Col("rank", "#", render=lambda r: _rank_cell(r, rank_field)),
        Col("team", "Team", render=lambda r: table.team_cell(
            r, "team_slug", "team_display", "logo_url")),
        Col("conference", "Conference"),
        # stat_value_raw, not stat_value: the raw string is what CFBD published, and some
        # of these statistics are not numbers at all (time of possession is "32:41"). The
        # numeric column is what the ranking is computed from; the raw one is what is true.
        Col("stat_value_raw", "Value"),
        Col("percentile", "Percentile", render=_percentile),
    ], caption="srv_team_stats",
        link_builder=lambda r: params.link("team", team=r["team_slug"], season=r["season"]))


def render() -> None:
    shell.render_page("stats", body)
