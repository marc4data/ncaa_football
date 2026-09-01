# CFBD coverage matrix

**Generated — do not edit by hand.** `python -m src.coverage_matrix`

Spec v5.25.0 · 79 endpoints · generated 2026-09-01 · raw counts from the warehouse (row counts)

What the API serves, what we fetch, what has landed, and what is actually exposed as
columns. The last of those is the one that was never measured: the pipeline was
streamlined toward one website, and a field nobody's page needed was never fetched,
never unnested, and never missed. Every DAG stayed green throughout.

## Where it stands

| Status | Endpoints | Meaning |
|---|---:|---|
| complete | 70 | every field the spec publishes is exposed as a column |
| partial | 1 | a staging model exists but drops fields |
| raw only | 0 | responses have landed; nothing reads them |
| no raw data | 8 | registered, never fetched |
| unregistered | 0 | the API serves it; we have not decided about it |

**Fields exposed: 984 of 1191 (82.6%).** That percentage is the product gap in one number.

## By endpoint

`Swept` means the endpoint is in the default breadth sweep; `CLI` means registered but
opt-in, because its cost is a different order of magnitude or it needs an argument no
sweep can invent.

| Endpoint | Registered | Raw | Staging model | Fields | Status |
|---|---|---:|---|---:|---|
| `calendar` | swept | 26 | `stg_calendar` | 7/7 | complete |
| `coaches` | swept | 141 | `stg_coach_season` | 19/19 | complete |
| `coaches/profile` | CLI | — | — | 0/19 | no raw data |
| `coaches/seasons` | swept | 3 | `stg_coach_season_detail` | 36/36 | complete |
| `coaches/tenures` | CLI | — | — | 0/18 | no raw data |
| `conferences` | swept | 4 | `stg_conferences` | 6/6 | complete |
| `conferences/affiliations` | swept | 3 | `stg_conference_affiliation` | 9/9 | complete |
| `conferences/changes` | swept | 3 | `stg_conference_change` | 11/11 | complete |
| `draft/picks` | swept | 60 | `stg_draft_pick` | 24/24 | complete |
| `draft/positions` | swept | 1 | `stg_draft_position` | 2/2 | complete |
| `draft/teams` | swept | 1 | `stg_nfl_team` | 4/4 | complete |
| `drives` | swept | 16 | `stg_drive` | 24/24 | complete |
| `game/box/advanced` | CLI | 1,849 | `stg_game_box_info`, `stg_game_box_player`, `stg_game_box_team` | 34/34 | complete |
| `games` | swept | 348 | `stg_games` | 41/41 | complete |
| `games/media` | swept | 8 | `stg_game_media` | 12/12 | complete |
| `games/players` | swept | 46 | `stg_game_player_stat` | 7/7 | complete |
| `games/teams` | swept | 46 | `stg_game_team_stat` | 8/8 | complete |
| `games/weather` | swept | 4 | `stg_game_weather` | 22/22 | complete |
| `info` | CLI | 14 | `stg_api_quota` | 13/13 | complete |
| `info/usage` | CLI | 14 | `stg_api_recent_request`, `stg_api_usage_endpoint` | 10/10 | complete |
| `lines` | swept | 71 | `stg_lines` | 23/23 | complete |
| `live/plays` | CLI | — | — | 0/63 | no raw data |
| `metrics/fg/ep` | swept | 1 | `stg_field_goal_ep` | 3/3 | complete |
| `metrics/wp` | CLI | 1,853 | `stg_game_win_probability` | 16/16 | complete |
| `metrics/wp/pregame` | swept | 8 | `stg_game_pregame_wp` | 8/8 | complete |
| `passing/players/games` | CLI | 33 | `stg_passing_player_game` | 22/22 | complete |
| `passing/players/season` | CLI | 2 | `stg_passing_player_season` | 18/18 | complete |
| `passing/plays` | CLI | 33 | `stg_passing_play` | 36/36 | complete |
| `passing/teams/games` | CLI | 33 | `stg_passing_team_game` | 20/20 | complete |
| `passing/teams/season` | CLI | 2 | `stg_passing_team_season` | 16/16 | complete |
| `player/portal` | swept | 3 | `stg_player_portal` | 10/10 | complete |
| `player/returning` | swept | 3 | `stg_team_returning_production` | 15/15 | complete |
| `player/search` | CLI | — | — | 0/16 | no raw data |
| `player/season/overview` | CLI | — | — | 0/17 | no raw data |
| `player/usage` | swept | 16 | `stg_player_season_usage` | 14/14 | complete |
| `playoffs/cfp` | swept | 2 | `stg_cfp_bracket` | 8/34 | partial |
| `playoffs/cfp/games` | swept | 2 | `stg_cfp_matchup` | 19/19 | complete |
| `playoffs/cfp/participants` | swept | 2 | `stg_cfp_participant` | 12/12 | complete |
| `plays` | swept | 45 | `stg_play` | 28/28 | complete |
| `plays/stats` | swept | 45 | `stg_play_stat` | 20/20 | complete |
| `plays/stats/types` | swept | 1 | `stg_play_stat_type` | 2/2 | complete |
| `plays/types` | swept | 1 | `stg_play_type` | 3/3 | complete |
| `ppa/games` | swept | 15 | `stg_game_team_ppa` | 13/13 | complete |
| `ppa/players/games` | swept | 45 | `stg_player_game_ppa` | 11/11 | complete |
| `ppa/players/season` | swept | 27 | `stg_player_season_ppa` | 14/14 | complete |
| `ppa/predicted` | CLI | — | — | 0/2 | no raw data |
| `ppa/teams` | swept | 16 | `stg_team_rating`, `stg_team_season_ppa` | 10/10 | complete |
| `rankings` | swept | 196 | `stg_rankings` | 11/11 | complete |
| `ratings/core` | swept | 16 | `stg_rating_core` | 11/11 | complete |
| `ratings/elo` | swept | 16 | `stg_rating_elo`, `stg_team_rating` | 4/4 | complete |
| `ratings/fpi` | swept | 16 | `stg_rating_fpi`, `stg_team_rating` | 13/13 | complete |
| `ratings/sp` | swept | 17 | `stg_rating_sp`, `stg_team_rating` | 18/18 | complete |
| `ratings/sp/conferences` | swept | 16 | `stg_rating_sp_conference` | 16/16 | complete |
| `ratings/srs` | swept | 16 | `stg_rating_srs`, `stg_team_rating` | 6/6 | complete |
| `ratings/srs/expanded` | swept | 16 | `stg_rating_srs_expanded` | 7/7 | complete |
| `records` | swept | 171 | `stg_team_record` | 11/11 | complete |
| `recruiting/groups` | swept | 2 | `stg_team_recruiting_position_group` | 7/7 | complete |
| `recruiting/players` | swept | 3 | `stg_recruit` | 19/19 | complete |
| `recruiting/teams` | swept | 3 | `stg_team_recruiting_rank` | 4/4 | complete |
| `roster` | swept | 3 | `stg_roster` | 16/16 | complete |
| `scoreboard` | CLI | — | — | 0/28 | no raw data |
| `stats/categories` | swept | 1 | `stg_stat_category` | 1/1 | complete |
| `stats/game/advanced` | swept | 15 | `stg_game_team_advanced` | 20/20 | complete |
| `stats/game/havoc` | swept | 15 | `stg_game_team_havoc` | 15/15 | complete |
| `stats/player/season` | swept | 59 | `stg_player_season_stat` | 9/9 | complete |
| `stats/player/success` | swept | 18 | `stg_player_season_success` | 9/9 | complete |
| `stats/player/success/game` | swept | 45 | `stg_player_game_success` | 13/13 | complete |
| `stats/season` | swept | 171 | `stg_team_season_stat` | 5/5 | complete |
| `stats/season/advanced` | swept | 39 | `stg_team_season_advanced` | 25/25 | complete |
| `talent` | swept | 3 | `stg_team_talent` | 3/3 | complete |
| `teams` | swept | 160 | `stg_teams` | 25/25 | complete |
| `teams/ats` | swept | 16 | `stg_team_season_ats` | 9/9 | complete |
| `teams/fbs` | swept | 3 | `stg_team_fbs` | 25/25 | complete |
| `teams/matchup` | CLI | — | — | 0/18 | no raw data |
| `venues` | swept | 1 | `stg_venues` | 14/14 | complete |
| `wepa/players/kicking` | swept | 16 | `stg_player_season_wepa_kicking` | 7/7 | complete |
| `wepa/players/passing` | swept | 16 | `stg_player_season_wepa_passing` | 8/8 | complete |
| `wepa/players/rushing` | swept | 16 | `stg_player_season_wepa_rushing` | 8/8 | complete |
| `wepa/team/season` | swept | 32 | `stg_team_season_wepa` | 15/15 | complete |

## What each gap costs

Endpoints with a staging model that drops fields. These are the cheapest wins: the
data is already landed and the model already exists — the fields were simply not
carried through.

| Endpoint | Model | Dropped | Fields not exposed |
|---|---|---:|---|
| — | — | 0 | Nothing left in this category. |

## Partial on purpose

These read as incomplete above and are not work to do. Each one's missing fields
are exposed elsewhere, from the endpoint that owns them.

**`playoffs/cfp`** — 26 fields not exposed here. COMPOSITE. Its `participants[]` is what /playoffs/cfp/participants serves and its `rounds[].matchups[]` is what /playoffs/cfp/games serves — both fully modelled from the endpoints that own them. Unnesting them here as well would put the same rows in two places from sources that can drift between fetches, with no way to say which is right. stg_cfp_bracket holds what only this endpoint has: the format, field size, status and champion.

## How the columns are decided

- **Registered** — presence in `src/endpoints.py`, and whether `include` puts it in
  the default sweep.
- **Raw** — a `raw.raw_<key>` table in the warehouse, or a `data/raw/<key>/`
  directory when the warehouse is not reachable. The header says which answered.
- **Staging model** — any `dbt/models/staging/*.sql` that selects from that raw table.
- **Fields** — leaf names in the spec's response schema, against the keys the model
  passes to the `json_get_*` macros. Leaf matching, not full dot-path: matching full
  paths reports zero for every endpoint whose payload nests, which is most of them.
  It can overcount when a nested object reuses a name; it cannot miss a field that is
  genuinely exposed. For a document that exists to find gaps, that is the safe
  direction to be wrong in — the real gap is at least this big.
