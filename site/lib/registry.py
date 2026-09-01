"""What each page reads, and whether it can be built yet.

Readiness is the three-part definition from the requirements — Exists / Complete /
Published — held as data so the nav, the page header and the Degraded copy all read the
same source. A page section carrying a stale readiness line is a defect in the document;
holding it here is how the site avoids the same failure.

`blocker` is what a Degraded page names in the UI. It is the OBJECT, not a description,
because AC-G.7 requires the user to be able to read the blocker off the screen.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Page:
    key: str
    title: str
    group: str
    view: Optional[str]
    exists: bool
    complete: bool
    published: bool
    blocker: Optional[str] = None
    blocker_note: str = ""
    partial_sections: List[str] = field(default_factory=list)
    # Whether the page gets a nav slot. A page with its own index does not need one — see
    # `team`. Distinct from `buildable`: a page can be built, reachable and deliberately
    # absent from the sidebar.
    in_nav: bool = True

    @property
    def buildable(self) -> bool:
        return self.exists and self.complete and self.published

    @property
    def url_path_for_nav(self) -> str:
        """The href Streamlit renders for this page's sidebar link."""
        return self.key

    @property
    def readiness(self) -> str:
        mark = lambda ok: "✓" if ok else "✗"          # noqa: E731
        return (f"Exists {mark(self.exists)} · Complete {mark(self.complete)} · "
                f"Published {mark(self.published)}")


OVERVIEW, GAMES, BETTING, DELIVERABLE, REFERENCE, BACK = (
    "Overview", "Games & teams", "Betting", "Deliverable", "Reference", "Back of house")

PAGES = [
    Page("today", "Today", OVERVIEW, "srv_today_edges", True, True, True),
    Page("schedule", "Schedule", GAMES, "srv_schedule", True, True, True),
    Page("scores", "Scores", GAMES, "srv_scoreboard", True, True, True),
    Page("rankings", "Rankings", GAMES, "srv_rankings", True, True, True),
    Page("standings", "Standings", GAMES, "srv_standings", True, True, True),
    Page("stats", "Stats", GAMES, "srv_team_stats", True, True, True,
         partial_sections=["Opponent scope and adjusted basis (stat_scope / stat_basis)"]),
    Page("teams", "Teams", GAMES, "srv_teams_index", True, True, True),
    # NOT IN NAV. Teams IS the index for this page — searchable, conference-filtered, 681
    # cards — so a nav entry that lands on an arbitrary team is strictly worse than the
    # picker that already exists. The distinction from Matchup, which we just went the other
    # way on: Matchup had NO index, so removing it from nav would have left it reachable
    # only by luck. This one is reachable from Teams, Standings, Schedule, Scores and every
    # team name on the site.
    #
    # AC-G.51 does not apply: that is about BLOCKED pages staying visible, and this page is
    # built. The page count stays 18; this is a nav decision, not a scope one.
    Page("team", "Team page", GAMES, "srv_team_overview", True, True, True,
         in_nav=False,
         partial_sections=["Week-over-week trends (weekly rating history)",
                           "Roster (dim_athlete)"]),
    # UNBLOCKED. The note this replaces said the page was "the only blocked page whose raw
    # data is not already on disk" — which stopped being true when the staging breadth work
    # landed stg_roster, stg_player_season_stat, stg_game_player_stat, stg_play and
    # stg_play_stat. dim_athlete, fct_player_season_stat, fct_player_game_stat, fct_play and
    # fct_play_stat are built on them, and three serving views sit on top.
    #
    # The page reads THREE views rather than one because it shows three grains — season
    # totals, a game log and individual plays — and the site reads one relation per query.
    # `view` names the primary, which is what the header and the dataset caption cite.
    Page("players", "Players", GAMES, "srv_player_stats", True, True, True),
    # NOT IN NAV. Marc asked in wireframe v0.2, again in feedback 01, and again after
    # using the picker that was built in response: "it's a click-through asset". Schedule,
    # Scores and Today are its index, and now that rows actually link, they are how it is
    # reached. The picker stays for /matchup with no game_id — arriving cold should still
    # work — but a nav slot for a drill-through is a slot that lands nobody usefully.
    # Weather is BUILT. fct_game_weather and srv_game_weather now exist and the page renders
    # conditions at kickoff. Travel and elevation remain listed, but the reason has changed
    # and is worth recording: they were blocked on there being no join key from a game to a
    # venue, and /games/weather turned out to carry venueId on every row — matching dim_venue
    # 6,847 of 6,847. The key exists; the feature is now merely unbuilt.
    Page("matchup", "Matchup", GAMES, "srv_matchup", True, True, True, in_nav=False,
         partial_sections=["Travel and rest (distance and days between games)"]),
    Page("odds", "Odds Board", BETTING, "srv_odds_board", True, True, True),
    Page("edges", "Edge Finder", BETTING, "srv_edge_finder", True, True, True,
         partial_sections=["Hit-rate slider, bucket n and calibration "
                           "(fct_edge_bucket_performance)"]),
    Page("performance", "Model Performance", BETTING, "srv_model_performance", True, True, True),
    Page("movement", "Line Movement", BETTING, "srv_line_movement", True, True, True),
    Page("export", "Excel Export", DELIVERABLE, None, True, True, True),
    Page("dictionary", "Data Dictionary", REFERENCE, "srv_data_dictionary", True, True, True),
    Page("methodology", "Methodology", REFERENCE, None, True, True, True),
    Page("system", "System Overview", BACK, "srv_system_health", True, True, True,
         partial_sections=["Pipeline runs (fct_pipeline_run does not exist)"]),
]

BY_KEY = {p.key: p for p in PAGES}
GROUPS = [OVERVIEW, GAMES, BETTING, DELIVERABLE, REFERENCE, BACK]
