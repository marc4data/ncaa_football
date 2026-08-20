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

    @property
    def buildable(self) -> bool:
        return self.exists and self.complete and self.published

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
    Page("team", "Team page", GAMES, "srv_team_overview", True, True, True,
         partial_sections=["Week-over-week trends (weekly rating history)",
                           "Roster (dim_athlete)"]),
    Page("players", "Players", GAMES, "srv_player_stats", False, False, False,
         blocker="srv_player_stats",
         blocker_note="Blocked on dim_athlete, fct_player_season_stat, "
                      "fct_player_game_stat and fct_play. Scheduled last: it is the only "
                      "blocked page whose raw data is not already on disk."),
    Page("matchup", "Matchup", GAMES, "srv_matchup", True, True, True,
         partial_sections=["Weather (fct_game_weather)",
                           "Travel, rest and elevation (venue join key)"]),
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
