# CFBD coverage matrix

**Generated — do not edit by hand.** `python -m src.coverage_matrix`

Spec v5.25.0 · 79 endpoints · generated 2026-08-31 · raw counts from `data/raw/` (response files on disk)

What the API serves, what we fetch, what has landed, and what is actually exposed as
columns. The last of those is the one that was never measured: the pipeline was
streamlined toward one website, and a field nobody's page needed was never fetched,
never unnested, and never missed. Every DAG stayed green throughout.

## Where it stands

| Status | Endpoints | Meaning |
|---|---:|---|
| complete | 8 | every field the spec publishes is exposed as a column |
| partial | 11 | a staging model exists but drops fields |
| raw only | 46 | responses have landed; nothing reads them |
| no raw data | 9 | registered, never fetched |
| unregistered | 5 | the API serves it; we have not decided about it |

**Fields exposed: 165 of 1191 (13.9%).** That percentage is the product gap in one number.

## By endpoint

`Swept` means the endpoint is in the default breadth sweep; `CLI` means registered but
opt-in, because its cost is a different order of magnitude or it needs an argument no
sweep can invent.

| Endpoint | Registered | Raw | Staging model | Fields | Status |
|---|---|---:|---|---:|---|
| `calendar` | swept | 27 | `stg_calendar` | 7/7 | complete |
| `coaches` | swept | 142 | — | 0/19 | raw only |
| `coaches/profile` | CLI | — | — | 0/19 | no raw data |
| `coaches/seasons` | swept | 4 | — | 0/36 | raw only |
| `coaches/tenures` | CLI | 3 | — | 0/18 | raw only |
| `conferences` | swept | 5 | `stg_conferences` | 6/6 | complete |
| `conferences/affiliations` | swept | 4 | — | 0/9 | raw only |
| `conferences/changes` | swept | 4 | — | 0/11 | raw only |
| `draft/picks` | swept | 61 | — | 0/24 | raw only |
| `draft/positions` | swept | 2 | — | 0/2 | raw only |
| `draft/teams` | swept | 2 | — | 0/4 | raw only |
| `drives` | swept | 15 | — | 0/24 | raw only |
| `game/box/advanced` | CLI | — | — | 0/34 | no raw data |
| `games` | swept | 343 | `stg_games` | 19/41 | partial |
| `games/media` | swept | 9 | `stg_game_media` | 6/12 | partial |
| `games/players` | swept | 45 | `stg_game_player_stat` | 7/7 | complete |
| `games/teams` | swept | 45 | `stg_game_team_stat` | 8/8 | complete |
| `games/weather` | swept | 5 | `stg_game_weather` | 22/22 | complete |
| `info` | CLI | 14 | `stg_api_quota` | 7/13 | partial |
| `info/usage` | CLI | 14 | `stg_api_usage_endpoint` | 6/10 | partial |
| `lines` | swept | 63 | `stg_lines` | 12/23 | partial |
| `live/plays` | CLI | — | — | 0/63 | no raw data |
| `metrics/fg/ep` | swept | 2 | — | 0/3 | raw only |
| `metrics/wp` | CLI | — | — | 0/16 | no raw data |
| `metrics/wp/pregame` | swept | 9 | — | 0/8 | raw only |
| `passing/players/games` | — | — | — | 0/22 | unregistered |
| `passing/players/season` | — | — | — | 0/18 | unregistered |
| `passing/plays` | — | — | — | 0/36 | unregistered |
| `passing/teams/games` | — | — | — | 0/20 | unregistered |
| `passing/teams/season` | — | — | — | 0/16 | unregistered |
| `player/portal` | swept | 4 | — | 0/10 | raw only |
| `player/returning` | swept | 4 | — | 0/15 | raw only |
| `player/search` | CLI | — | — | 0/16 | no raw data |
| `player/season/overview` | CLI | — | — | 0/17 | no raw data |
| `player/usage` | swept | 15 | — | 0/14 | raw only |
| `playoffs/cfp` | swept | 3 | — | 0/34 | raw only |
| `playoffs/cfp/games` | swept | 3 | — | 0/19 | raw only |
| `playoffs/cfp/participants` | swept | 3 | — | 0/12 | raw only |
| `plays` | swept | 44 | — | 0/28 | raw only |
| `plays/stats` | swept | 44 | — | 0/20 | raw only |
| `plays/stats/types` | swept | 2 | — | 0/2 | raw only |
| `plays/types` | swept | 2 | — | 0/3 | raw only |
| `ppa/games` | swept | 14 | — | 0/13 | raw only |
| `ppa/players/games` | swept | 48 | — | 0/11 | raw only |
| `ppa/players/season` | swept | 26 | — | 0/14 | raw only |
| `ppa/predicted` | CLI | — | — | 0/2 | no raw data |
| `ppa/teams` | swept | 15 | `stg_team_rating` | 3/10 | partial |
| `rankings` | swept | 195 | `stg_rankings` | 11/11 | complete |
| `ratings/core` | swept | 15 | — | 0/11 | raw only |
| `ratings/elo` | swept | 15 | `stg_team_rating` | 3/4 | partial |
| `ratings/fpi` | swept | 15 | `stg_team_rating` | 7/13 | partial |
| `ratings/sp` | swept | 16 | `stg_team_rating` | 6/18 | partial |
| `ratings/sp/conferences` | swept | 15 | — | 0/16 | raw only |
| `ratings/srs` | swept | 15 | `stg_team_rating` | 4/6 | partial |
| `ratings/srs/expanded` | swept | 15 | — | 0/7 | raw only |
| `records` | swept | 170 | — | 0/11 | raw only |
| `recruiting/groups` | swept | 2 | — | 0/7 | raw only |
| `recruiting/players` | swept | 4 | — | 0/19 | raw only |
| `recruiting/teams` | swept | 4 | — | 0/4 | raw only |
| `roster` | swept | 4 | — | 0/16 | raw only |
| `scoreboard` | CLI | — | — | 0/28 | no raw data |
| `stats/categories` | swept | 2 | — | 0/1 | raw only |
| `stats/game/advanced` | swept | 14 | — | 0/20 | raw only |
| `stats/game/havoc` | swept | 14 | — | 0/15 | raw only |
| `stats/player/season` | swept | 58 | — | 0/9 | raw only |
| `stats/player/success` | swept | 17 | — | 0/9 | raw only |
| `stats/player/success/game` | swept | 48 | — | 0/13 | raw only |
| `stats/season` | swept | 170 | `stg_team_season_stat` | 5/5 | complete |
| `stats/season/advanced` | swept | 38 | — | 0/25 | raw only |
| `talent` | swept | 4 | — | 0/3 | raw only |
| `teams` | swept | 162 | `stg_teams` | 12/25 | partial |
| `teams/ats` | swept | 15 | — | 0/9 | raw only |
| `teams/fbs` | swept | 4 | — | 0/25 | raw only |
| `teams/matchup` | CLI | — | — | 0/18 | no raw data |
| `venues` | swept | 2 | `stg_venues` | 14/14 | complete |
| `wepa/players/kicking` | swept | 15 | — | 0/7 | raw only |
| `wepa/players/passing` | swept | 15 | — | 0/8 | raw only |
| `wepa/players/rushing` | swept | 15 | — | 0/8 | raw only |
| `wepa/team/season` | swept | 31 | — | 0/15 | raw only |

## What each gap costs

Endpoints with a staging model that drops fields. These are the cheapest wins: the
data is already landed and the model already exists — the fields were simply not
carried through.

| Endpoint | Model | Dropped | Fields not exposed |
|---|---|---:|---|
| `games` | stg_games | 22 | `awayConference`, `awayLineScores`, `awayPostgameElo`, `awayPostgameWinProbability`, `awayPregameElo`, `awaySeed`, `bowlName`, `bracketSlot`, `competition`, `format`, `highlights`, `homeConference`, … (+10) |
| `teams` | stg_teams | 13 | `alternateNames`, `capacity`, `constructionYear`, `countryCode`, `dome`, `elevation`, `grass`, `latitude`, `longitude`, `name`, `timezone`, `twitter`, … (+1) |
| `ratings/sp` | stg_team_rating | 12 | `db`, `explosiveness`, `frontSeven`, `pace`, `passing`, `passingDowns`, `runRate`, `rushing`, `standardDowns`, `success`, `total`, `year` |
| `lines` | stg_lines | 11 | `awayClassification`, `awayConference`, `awayScore`, `awayTeam`, `awayTeamId`, `homeClassification`, `homeConference`, `homeScore`, `homeTeam`, `homeTeamId`, `startDate` |
| `ppa/teams` | stg_team_rating | 7 | `firstDown`, `passing`, `rushing`, `season`, `secondDown`, `thirdDown`, `total` |
| `games/media` | stg_game_media | 6 | `awayConference`, `awayTeam`, `homeConference`, `homeTeam`, `isStartTimeTBD`, `startTime` |
| `info` | stg_api_quota | 6 | `adjustedMetrics`, `graphQl`, `livePlayByPlay`, `products`, `scoreboard`, `weather` |
| `ratings/fpi` | stg_team_rating | 6 | `averageWinProbability`, `gameControl`, `remainingStrengthOfSchedule`, `strengthOfRecord`, `strengthOfSchedule`, `year` |
| `info/usage` | stg_api_usage_endpoint | 4 | `cbbRequests`, `cfbRequests`, `requestedAt`, `uniqueEndpoints` |
| `ratings/srs` | stg_team_rating | 2 | `division`, `year` |
| `ratings/elo` | stg_team_rating | 1 | `year` |

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
