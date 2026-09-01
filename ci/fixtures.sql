-- Minimal raw layer for CI, so dbt models and their tests run on every PR without the
-- 1.6 GB real raw layer.
--
-- Plain SQL rather than dbt seeds on purpose: a seed named `raw_teams` would overwrite the
-- real table if anyone ran `dbt seed` locally, and the fixture is easier to read as the
-- shape it actually is — one row per landed API response, payload in `content`.
--
-- The fixture deliberately spans both eras. 1900 games are stored at midnight UTC as
-- date-only values; 2024 games carry real kickoff times. That is what exercises the
-- per-season era detection in mart_team_schedule, which is where a 66,496-game date shift
-- once hid.

CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.raw_teams (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_games (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
-- Every landed endpoint has the same shape, so these differ only in name.
CREATE TABLE IF NOT EXISTS raw.raw_venues (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_conferences (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_calendar (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_lines (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_games_teams (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_games_players (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_games_weather (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_stats_categories (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_stats_game_advanced (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_stats_game_havoc (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_stats_player_season (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_stats_player_success (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_stats_player_success_game (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_records (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_model_prediction (
    source_file text NOT NULL, model_version text NOT NULL, prediction_ts timestamptz NOT NULL,
    row_number int NOT NULL, payload jsonb NOT NULL, loaded_at timestamptz DEFAULT now(),
    PRIMARY KEY (source_file, model_version, row_number)
);
CREATE TABLE IF NOT EXISTS raw.raw_deploy_status (
    observed_at timestamptz NOT NULL, deploy_sha text, main_sha text,
    commits_behind int, severity text, detail text,
    PRIMARY KEY (observed_at)
);
CREATE TABLE IF NOT EXISTS raw.raw_games_media (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_rankings (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_stats_season (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_stats_season_advanced (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_dbt_test_result (
    invocation_id text NOT NULL, unique_id text NOT NULL, generated_at timestamptz,
    dbt_version text, status text, failures bigint, execution_time numeric,
    message text, relation_name text,
    PRIMARY KEY (invocation_id, unique_id)
);
CREATE TABLE IF NOT EXISTS raw.raw_info (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_info_usage (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_warehouse_usage (
    observed_at timestamptz NOT NULL, operation text NOT NULL, outcome text,
    elapsed_seconds numeric, catalog text,
    PRIMARY KEY (observed_at, operation)
);
CREATE TABLE IF NOT EXISTS raw.raw_ratings_sp (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_ratings_srs (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_ratings_elo (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_ratings_fpi (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_ratings_sp_conferences (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_ratings_srs_expanded (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_ratings_core (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_ppa_teams (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_ppa_games (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_ppa_players_season (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_ppa_players_games (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_wepa_team_season (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_wepa_players_passing (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_wepa_players_rushing (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_wepa_players_kicking (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_teams_fbs (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_teams_ats (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_player_portal (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_player_returning (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_player_usage (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_metrics_fg_ep (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_metrics_wp_pregame (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_coaches (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_coaches_seasons (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_recruiting_players (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_recruiting_teams (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_recruiting_groups (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_talent (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_draft_picks (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_draft_positions (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_draft_teams (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_roster (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_conferences_affiliations (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_conferences_changes (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_playoffs_cfp (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_playoffs_cfp_games (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_playoffs_cfp_participants (
    filename text PRIMARY KEY, content jsonb, status_code int, params jsonb,
    fetched_at timestamptz, added_at timestamptz
);
CREATE TABLE IF NOT EXISTS raw.raw_manifest (
    endpoint text NOT NULL, filename text NOT NULL, params jsonb, status_code int,
    row_count int, fetched_at timestamptz, loaded_at timestamptz,
    PRIMARY KEY (endpoint, filename)
);

TRUNCATE raw.raw_teams, raw.raw_games, raw.raw_venues, raw.raw_conferences,
         raw.raw_calendar, raw.raw_lines, raw.raw_games_teams, raw.raw_records,
         raw.raw_info, raw.raw_info_usage, raw.raw_warehouse_usage,
         raw.raw_rankings, raw.raw_stats_season, raw.raw_stats_season_advanced,
         raw.raw_dbt_test_result, raw.raw_model_prediction, raw.raw_games_media,
         raw.raw_deploy_status,
         raw.raw_ratings_sp, raw.raw_ratings_srs, raw.raw_ratings_elo,
         raw.raw_ratings_fpi, raw.raw_ppa_teams,
         raw.raw_ratings_sp_conferences, raw.raw_ratings_srs_expanded,
         raw.raw_ratings_core,
         raw.raw_ppa_games, raw.raw_ppa_players_season,
         raw.raw_ppa_players_games,
         raw.raw_wepa_team_season, raw.raw_wepa_players_passing,
         raw.raw_wepa_players_rushing, raw.raw_wepa_players_kicking,
         raw.raw_teams_fbs, raw.raw_teams_ats, raw.raw_player_portal,
         raw.raw_player_returning, raw.raw_player_usage,
         raw.raw_metrics_fg_ep, raw.raw_metrics_wp_pregame,
         raw.raw_coaches, raw.raw_coaches_seasons,
         raw.raw_recruiting_players, raw.raw_recruiting_teams,
         raw.raw_recruiting_groups, raw.raw_talent,
         raw.raw_draft_picks, raw.raw_draft_positions, raw.raw_draft_teams,
         raw.raw_roster, raw.raw_conferences_affiliations,
         raw.raw_conferences_changes, raw.raw_playoffs_cfp,
         raw.raw_playoffs_cfp_games, raw.raw_playoffs_cfp_participants,
         raw.raw_games_players, raw.raw_games_weather,
         raw.raw_stats_categories, raw.raw_stats_game_advanced,
         raw.raw_stats_game_havoc, raw.raw_stats_player_season,
         raw.raw_stats_player_success, raw.raw_stats_player_success_game,
         raw.raw_manifest;

-- Teams, season-scoped. Only year-parameterized fetches feed stg_teams.
--
-- `logos` is a JSON ARRAY, and that is load-bearing rather than incidental. Every logo on
-- the site was null because `logo_source_url` reached into this array with `->> '0'` — the
-- object-KEY accessor, which finds no key named "0" and returns NULL without complaint. The
-- fixture must carry the array shape, because against an object the wrong accessor would
-- have worked and CI would have gone green on a broken build.
--
-- `color` likewise: it is read with the plain key accessor, and the contrast ladder falls
-- back silently when it is null, so a regression there is invisible in exactly the same way.
INSERT INTO raw.raw_teams (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-00-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"id": 1, "school": "Alpha State", "mascot": "Ones", "abbreviation": "ALP",
     "conference": "Test Conference", "division": null, "classification": "fbs",
     "color": "#123456", "alternateColor": "#abcdef",
     "logos": ["http://example.invalid/alpha.png", "http://example.invalid/alpha-dark.png"],
     "location": {"city": "Alphaville", "state": "AA"}},
    {"id": 2, "school": "Beta Tech", "mascot": "Twos", "abbreviation": "BET",
     "conference": "Test Conference", "division": null, "classification": "fbs",
     "color": "#654321", "alternateColor": "#fedcba",
     "logos": ["http://example.invalid/beta.png", "http://example.invalid/beta-dark.png"],
     "location": {"city": "Betaburg", "state": "BB"}}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:00Z', now()),
('2026-01-01T00-00-00-002Z.json', '{
  "status_code": 200, "params": {"year": "1900"},
  "data": [
    {"id": 1, "school": "Alpha State", "mascot": "Ones", "abbreviation": "ALP",
     "conference": "Old Conference", "division": null, "classification": "fbs",
     "color": "#123456", "alternateColor": "#abcdef",
     "logos": ["http://example.invalid/alpha.png"],
     "location": {"city": "Alphaville", "state": "AA"}},
    {"id": 2, "school": "Beta Tech", "mascot": "Twos", "abbreviation": "BET",
     "conference": "Old Conference", "division": null, "classification": "fbs",
     "color": "#654321", "alternateColor": "#fedcba",
     "logos": ["http://example.invalid/beta.png"],
     "location": {"city": "Betaburg", "state": "BB"}}
  ]}', 200, '{"year": "1900"}', '2026-01-01T00:00:00Z', now()),
-- A failed fetch, landed as the raw layer always does. Staging must filter it out.
('2026-01-01T00-00-00-003Z.json', '{"status_code": 401, "params": {"year": "2024"}, "data": null}',
 401, '{"year": "2024"}', '2026-01-01T00:00:01Z', now());

-- Games. Completed matchups, so every reconciliation test has something to reconcile.
--
-- THE POST-GAME PATH IS THE HALF THAT MATTERS ON A SATURDAY, and it was the half never
-- exercised: every page was verified against 2026 rows, and every 2026 row has
-- is_completed = false, so no scored formatter on the site had ever run against a real
-- value. Rehearsing against a completed 2025 week found two defects in an afternoon. These
-- three games keep that path exercised on every build instead of four times a season.
--
-- Game 9004 is against GAMMA COLLEGE, which is deliberately ABSENT FROM raw_teams. That is
-- not an oversight — it is the shape of 11% of the real scoreboard. dim_team is built from
-- CFBD's /teams response, which does not list every opponent an FBS side schedules, so a
-- Division II visitor exists in /games and not in /teams. Reading the display name off the
-- dimension left it NULL on 12,168 of 110,634 rows and the Scores page rendered the winner
-- as `None`. A fixture where every team is in both places cannot catch that.
--
-- Game 9005 is a TIE. A tie is a settled result and must never render as Pending, and it is
-- the branch where `winner is null` means something completely different from "not played
-- yet". College football had no overtime before 1996 and there are 2,600 of them on record.
INSERT INTO raw.raw_games (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-01-001Z.json', '{
  "status_code": 200, "params": {"year": "2024", "seasonType": "regular"},
  "data": [
    {"id": 9001, "season": 2024, "week": 1, "seasonType": "regular",
     "startDate": "2024-09-07T23:30:00.000Z", "completed": true, "conferenceGame": true,
     "neutralSite": false, "homeId": 1, "homeTeam": "Alpha State", "homePoints": 28,
     "homeClassification": "fbs", "awayId": 2, "awayTeam": "Beta Tech", "awayPoints": 21,
     "awayClassification": "fbs", "venue": "Alpha Field", "attendance": 50000},
    {"id": 9004, "season": 2024, "week": 2, "seasonType": "regular",
     "startDate": "2024-09-14T23:30:00.000Z", "completed": true, "conferenceGame": false,
     "neutralSite": false, "homeId": 1, "homeTeam": "Alpha State", "homePoints": 41,
     "homeClassification": "fbs", "awayId": 77, "awayTeam": "Gamma College",
     "awayPoints": 3, "awayClassification": "ii", "venue": "Alpha Field",
     "attendance": 41000},
    {"id": 9005, "season": 2024, "week": 3, "seasonType": "regular",
     "startDate": "2024-09-21T23:30:00.000Z", "completed": true, "conferenceGame": true,
     "neutralSite": false, "homeId": 2, "homeTeam": "Beta Tech", "homePoints": 17,
     "homeClassification": "fbs", "awayId": 1, "awayTeam": "Alpha State", "awayPoints": 17,
     "awayClassification": "fbs", "venue": "Beta Grounds", "attendance": 33000}
  ]}', 200, '{"year": "2024", "seasonType": "regular"}', '2026-01-01T00:00:02Z', now()),
-- Date-only era: midnight UTC, no kickoff time recorded.
('2026-01-01T00-00-01-002Z.json', '{
  "status_code": 200, "params": {"year": "1900", "seasonType": "regular"},
  "data": [
    {"id": 9002, "season": 1900, "week": 1, "seasonType": "regular",
     "startDate": "1900-11-10T00:00:00.000Z", "completed": true, "conferenceGame": false,
     "neutralSite": false, "homeId": 2, "homeTeam": "Beta Tech", "homePoints": 6,
     "homeClassification": "fbs", "awayId": 1, "awayTeam": "Alpha State", "awayPoints": 5,
     "awayClassification": "fbs", "venue": "Beta Grounds", "attendance": null}
  ]}', 200, '{"year": "1900", "seasonType": "regular"}', '2026-01-01T00:00:03Z', now());

-- The manifest spine: one row per landed response, including the failure.
INSERT INTO raw.raw_ppa_games (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-28-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024",
  "seasonType": "regular"
 },
 "data": [
  {
   "gameId": 9001,
   "season": 2024,
   "week": 1,
   "seasonType": "regular",
   "team": "Alpha State",
   "conference": "Test Conference",
   "opponent": "Beta Tech",
   "offense": {
    "overall": 0.13,
    "passing": 0.08,
    "rushing": 0.15,
    "firstDown": -0.06,
    "secondDown": 0.02,
    "thirdDown": 0.43
   },
   "defense": {
    "overall": 0.43,
    "passing": 0.38,
    "rushing": 0.45,
    "firstDown": 0.24,
    "secondDown": 0.32,
    "thirdDown": 0.73
   }
  },
  {
   "gameId": 9001,
   "season": 2024,
   "week": 1,
   "seasonType": "regular",
   "team": "Beta Tech",
   "conference": "Test Conference",
   "opponent": "Alpha State",
   "offense": {
    "overall": 0.43,
    "passing": 0.38,
    "rushing": 0.45,
    "firstDown": 0.24,
    "secondDown": 0.32,
    "thirdDown": 0.73
   },
   "defense": {
    "overall": 0.13,
    "passing": 0.08,
    "rushing": 0.15,
    "firstDown": -0.06,
    "secondDown": 0.02,
    "thirdDown": 0.43
   }
  }
 ]
}', 200, '{"year": "2024", "seasonType": "regular"}',
  '2026-01-01T00:00:39Z', now());

INSERT INTO raw.raw_ppa_players_season (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-29-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "season": 2024,
   "id": "1001",
   "name": "A. Passer",
   "position": "QB",
   "team": "Alpha State",
   "conference": "B12",
   "averagePPA": {
    "all": 0.352,
    "pass": 0.362,
    "rush": 0.372,
    "firstDown": 0.382,
    "secondDown": 0.392,
    "thirdDown": 0.402,
    "standardDowns": 0.412,
    "passingDowns": 0.422
   },
   "totalPPA": {
    "all": 114.748,
    "pass": 115.748,
    "rush": 116.748,
    "firstDown": 117.748,
    "secondDown": 118.748,
    "thirdDown": 119.748,
    "standardDowns": 120.748,
    "passingDowns": 121.748
   }
  },
  {
   "season": 2024,
   "id": "1002",
   "name": "B. Runner",
   "position": "RB",
   "team": "Beta Tech",
   "conference": "B12",
   "averagePPA": {
    "all": 0.552,
    "pass": 0.562,
    "rush": 0.572,
    "firstDown": 0.582,
    "secondDown": 0.592,
    "thirdDown": 0.602,
    "standardDowns": 0.612,
    "passingDowns": 0.622
   },
   "totalPPA": {
    "all": 58.2,
    "pass": 59.2,
    "rush": 60.2,
    "firstDown": 61.2,
    "secondDown": 62.2,
    "thirdDown": 63.2,
    "standardDowns": 64.2,
    "passingDowns": 65.2
   }
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:40Z', now());

INSERT INTO raw.raw_ppa_players_games (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-30-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024",
  "week": "1",
  "seasonType": "regular"
 },
 "data": [
  {
   "season": 2024,
   "week": 1,
   "seasonType": "regular",
   "id": "1001",
   "name": "A. Passer",
   "position": "QB",
   "team": "Alpha State",
   "opponent": "Beta Tech",
   "averagePPA": {
    "all": 0.412,
    "pass": 0.455,
    "rush": -0.12
   }
  },
  {
   "season": 2024,
   "week": 1,
   "seasonType": "regular",
   "id": "1002",
   "name": "B. Runner",
   "position": "RB",
   "team": "Beta Tech",
   "opponent": "Alpha State",
   "averagePPA": {
    "all": 0.201,
    "pass": null,
    "rush": 0.201
   }
  }
 ]
}', 200, '{"year": "2024", "week": "1", "seasonType": "regular"}',
  '2026-01-01T00:00:41Z', now());

INSERT INTO raw.raw_wepa_team_season (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-31-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "year": 2024,
   "teamId": 1,
   "team": "Alpha State",
   "conference": "Test Conference",
   "epa": {
    "total": 0.09,
    "passing": 0.1,
    "rushing": 0.11
   },
   "epaAllowed": {
    "total": 0.15,
    "passing": 0.16,
    "rushing": 0.17
   },
   "successRate": {
    "total": 0.375,
    "standardDowns": 0.385,
    "passingDowns": 0.395
   },
   "successRateAllowed": {
    "total": 0.446,
    "standardDowns": 0.456,
    "passingDowns": 0.466
   },
   "rushing": {
    "lineYards": 3.07,
    "secondLevelYards": 3.08,
    "openFieldYards": 3.09,
    "highlightYards": 3.1
   },
   "rushingAllowed": {
    "lineYards": 3.35,
    "secondLevelYards": 3.36,
    "openFieldYards": 3.37,
    "highlightYards": 3.38
   },
   "explosiveness": 0.939,
   "explosivenessAllowed": 0.91
  },
  {
   "year": 2024,
   "teamId": 2,
   "team": "Beta Tech",
   "conference": "Test Conference",
   "epa": {
    "total": 0.19,
    "passing": 0.2,
    "rushing": 0.21
   },
   "epaAllowed": {
    "total": 0.25,
    "passing": 0.26,
    "rushing": 0.27
   },
   "successRate": {
    "total": 0.475,
    "standardDowns": 0.485,
    "passingDowns": 0.495
   },
   "successRateAllowed": {
    "total": 0.546,
    "standardDowns": 0.556,
    "passingDowns": 0.566
   },
   "rushing": {
    "lineYards": 4.07,
    "secondLevelYards": 4.08,
    "openFieldYards": 4.09,
    "highlightYards": 4.1
   },
   "rushingAllowed": {
    "lineYards": 4.35,
    "secondLevelYards": 4.36,
    "openFieldYards": 4.37,
    "highlightYards": 4.38
   },
   "explosiveness": 1.039,
   "explosivenessAllowed": 1.01
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:42Z', now());

INSERT INTO raw.raw_wepa_players_passing (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-32-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "year": 2024,
   "athleteId": "1001",
   "athleteName": "A. Passer",
   "position": "QB",
   "team": "Alpha State",
   "conference": "Test Conference",
   "wepa": 0.48,
   "plays": 304
  },
  {
   "year": 2024,
   "athleteId": "1005",
   "athleteName": "F. Backup",
   "position": "QB",
   "team": "Beta Tech",
   "conference": "Test Conference",
   "wepa": 0.48,
   "plays": 12
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:43Z', now());

INSERT INTO raw.raw_wepa_players_rushing (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-33-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "year": 2024,
   "athleteId": "1002",
   "athleteName": "B. Runner",
   "position": "RB",
   "team": "Alpha State",
   "conference": "Test Conference",
   "wepa": 0.22,
   "plays": 152
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:44Z', now());

INSERT INTO raw.raw_wepa_players_kicking (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-34-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "year": 2024,
   "athleteId": "1006",
   "athleteName": "G. Kicker",
   "team": "Alpha State",
   "conference": "Test Conference",
   "paar": 16.71,
   "attempts": 31
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:45Z', now());

INSERT INTO raw.raw_teams_fbs (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-35-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "id": 1,
   "school": "Alpha State",
   "mascot": "Alpha State Mascot",
   "abbreviation": "ALP",
   "alternateNames": [
    "ALP",
    "Alpha State"
   ],
   "conference": "Test Conference",
   "division": null,
   "classification": "fbs",
   "color": "#003594",
   "alternateColor": "#ffffff",
   "logos": [
    "https://cdn.example/logos/1.png"
   ],
   "twitter": "@AlphaState",
   "location": {
    "id": 501,
    "name": "Alpha State Field",
    "city": "Testville",
    "state": "TX",
    "zip": "79601",
    "countryCode": "US",
    "timezone": "America/Chicago",
    "latitude": 32.472275,
    "longitude": -99.710464,
    "elevation": "520.9",
    "capacity": 12000,
    "constructionYear": 2017,
    "grass": false,
    "dome": false
   }
  },
  {
   "id": 2,
   "school": "Beta Tech",
   "mascot": "Beta Tech Mascot",
   "abbreviation": "BET",
   "alternateNames": [
    "BET",
    "Beta Tech"
   ],
   "conference": "Test Conference",
   "division": null,
   "classification": "fbs",
   "color": "#003594",
   "alternateColor": "#ffffff",
   "logos": [
    "https://cdn.example/logos/2.png"
   ],
   "twitter": "@BetaTech",
   "location": {
    "id": 502,
    "name": "Beta Tech Field",
    "city": "Testville",
    "state": "TX",
    "zip": "79601",
    "countryCode": "US",
    "timezone": "America/Chicago",
    "latitude": 32.472275,
    "longitude": -99.710464,
    "elevation": "520.9",
    "capacity": 12000,
    "constructionYear": 2017,
    "grass": false,
    "dome": true
   }
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:46Z', now());

INSERT INTO raw.raw_teams_ats (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-36-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "year": 2024,
   "teamId": 1,
   "team": "Alpha State",
   "conference": "Test Conference",
   "games": 11,
   "atsWins": 6,
   "atsLosses": 4,
   "atsPushes": 0,
   "avgCoverMargin": 3.32
  },
  {
   "year": 2024,
   "teamId": 2,
   "team": "Beta Tech",
   "conference": "Test Conference",
   "games": 12,
   "atsWins": 5,
   "atsLosses": 6,
   "atsPushes": 1,
   "avgCoverMargin": -1.14
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:47Z', now());

INSERT INTO raw.raw_player_portal (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-37-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "season": 2024,
   "firstName": "Casey",
   "lastName": "Mover",
   "position": "CB",
   "origin": "Alpha State",
   "destination": "Beta Tech",
   "transferDate": "2024-01-03T00:27:00.000Z",
   "rating": 0.912,
   "stars": 4,
   "eligibility": "Immediate"
  },
  {
   "season": 2024,
   "firstName": "Jordan",
   "lastName": "Waiting",
   "position": "WR",
   "origin": "Beta Tech",
   "destination": null,
   "transferDate": "2024-01-09T12:00:00.000Z",
   "rating": null,
   "stars": 3,
   "eligibility": "Immediate"
  },
  {
   "season": 2024,
   "firstName": "Casey",
   "lastName": "Mover",
   "position": "OL",
   "origin": "Gamma College",
   "destination": "Alpha State",
   "transferDate": "2024-02-01T09:00:00.000Z",
   "rating": null,
   "stars": 2,
   "eligibility": "Immediate"
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:48Z', now());

INSERT INTO raw.raw_player_returning (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-38-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "season": 2024,
   "team": "Alpha State",
   "conference": "Test Conference",
   "totalPPA": 100.6,
   "totalPassingPPA": 5.3,
   "totalReceivingPPA": 55.4,
   "totalRushingPPA": 39.9,
   "percentPPA": 0.338,
   "percentPassingPPA": 0.106,
   "percentReceivingPPA": 0.683,
   "percentRushingPPA": 0.238,
   "usage": 0.217,
   "passingUsage": 0.206,
   "receivingUsage": 0.515,
   "rushingUsage": 0.187
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:49Z', now());

INSERT INTO raw.raw_player_usage (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-39-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "season": 2024,
   "id": "1001",
   "name": "A. Passer",
   "position": "QB",
   "team": "Alpha State",
   "conference": "B12",
   "usage": {
    "overall": 0.464,
    "pass": 0.823,
    "rush": 0.046,
    "firstDown": 0.411,
    "secondDown": 0.471,
    "thirdDown": 0.6,
    "standardDowns": 0.404,
    "passingDowns": 0.634
   }
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:50Z', now());

INSERT INTO raw.raw_metrics_fg_ep (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-40-001Z.json', '{
 "status_code": 200,
 "params": {},
 "data": [
  {
   "yardsToGoal": 0,
   "distance": 17,
   "expectedPoints": 2.85
  },
  {
   "yardsToGoal": 20,
   "distance": 37,
   "expectedPoints": 2.41
  },
  {
   "yardsToGoal": 40,
   "distance": 57,
   "expectedPoints": 1.08
  }
 ]
}', 200, '{}',
  '2026-01-01T00:00:51Z', now());

INSERT INTO raw.raw_metrics_wp_pregame (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-41-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024",
  "seasonType": "regular"
 },
 "data": [
  {
   "season": 2024,
   "week": 1,
   "seasonType": "regular",
   "gameId": 9001,
   "homeTeam": "Alpha State",
   "awayTeam": "Beta Tech",
   "spread": -7.0,
   "homeWinProbability": 0.71
  }
 ]
}', 200, '{"year": "2024", "seasonType": "regular"}',
  '2026-01-01T00:00:52Z', now());

INSERT INTO raw.raw_metrics_wp_pregame (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-41-002Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024",
  "seasonType": "regular"
 },
 "data": [
  {
   "season": 2024,
   "week": 1,
   "seasonType": "regular",
   "gameId": 9001,
   "homeTeam": "Alpha State",
   "awayTeam": "Beta Tech",
   "spread": -9.5,
   "homeWinProbability": 0.78
  }
 ]
}', 200, '{"year": "2024", "seasonType": "regular"}',
  '2026-01-01T00:00:53Z', now());

-- stg_game_pregame_wp joins raw_manifest on endpoint + filename for the OBSERVED time, so
-- both snapshots need a manifest row or the model comes back empty and the no-dedup property
-- is asserted but never exercised.
--
-- status_code and row_count are NOT optional here: stg_raw_manifest derives is_success and
-- is_empty from them and both carry not_null tests. Omitting them failed two tests in a way
-- that pointed at the manifest model rather than at this fixture.
INSERT INTO raw.raw_coaches (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-42-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "id": 501,
   "firstName": "Head",
   "lastName": "Coach",
   "hireDate": "2021-12-01T00:00:00.000Z",
   "seasons": [
    {
     "teamId": 1,
     "school": "Alpha State",
     "conference": "Test Conference",
     "year": 2024,
     "games": 12,
     "wins": 9,
     "losses": 3,
     "ties": 0,
     "winPercentage": 0.75,
     "preseasonRank": 12,
     "postseasonRank": 8,
     "srs": 11.1,
     "spOverall": 18.4,
     "spOffense": 34.1,
     "spDefense": 15.7
    },
    {
     "teamId": 1,
     "school": "Alpha State",
     "conference": "Test Conference",
     "year": 2023,
     "games": 12,
     "wins": 7,
     "losses": 5,
     "ties": 0,
     "winPercentage": 0.583,
     "preseasonRank": null,
     "postseasonRank": null,
     "srs": 4.2,
     "spOverall": 8.1,
     "spOffense": 29.0,
     "spDefense": 20.9
    }
   ]
  },
  {
   "id": 502,
   "firstName": "Interim",
   "lastName": "Fill",
   "hireDate": "2024-10-27T00:00:00.000Z",
   "seasons": [
    {
     "teamId": 2,
     "school": "Beta Tech",
     "conference": "Test Conference",
     "year": 2024,
     "games": 4,
     "wins": 2,
     "losses": 2,
     "ties": 0,
     "winPercentage": 0.5,
     "preseasonRank": null,
     "postseasonRank": null,
     "srs": -8.6,
     "spOverall": -11.4,
     "spOffense": 20.5,
     "spDefense": 30.4
    },
    {
     "teamId": 3,
     "school": "Gamma College",
     "conference": null,
     "year": 2024,
     "games": 3,
     "wins": 1,
     "losses": 2,
     "ties": 0,
     "winPercentage": 0.333,
     "preseasonRank": null,
     "postseasonRank": null,
     "srs": -12.0,
     "spOverall": -14.2,
     "spOffense": 18.1,
     "spDefense": 32.3
    }
   ]
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:54Z', now());

INSERT INTO raw.raw_coaches_seasons (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-43-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "coach": {
    "id": 501,
    "firstName": "Head",
    "lastName": "Coach"
   },
   "team": {
    "id": 1,
    "school": "Alpha State",
    "conference": "Test Conference"
   },
   "year": 2024,
   "games": 12,
   "wins": 9,
   "losses": 3,
   "ties": 0,
   "winPercentage": 0.75,
   "preseasonRank": 12,
   "postseasonRank": 8,
   "srs": 11.1,
   "spOverall": 18.4,
   "spOffense": 34.1,
   "spDefense": 15.7,
   "teamMetrics": {
    "spSpecialTeams": -0.6,
    "strengthOfSchedule": 3.1,
    "secondOrderWins": 8.4,
    "fpi": 9.659,
    "yearOverYear": {
     "wins": 2,
     "srs": 6.9,
     "spOverall": 10.3
    }
   },
   "recruiting": {
    "rank": 10,
    "points": 275.39,
    "talent": 833.61
   },
   "pollResume": {
    "preseasonRank": 12,
    "postseasonRank": 8,
    "bestRank": 6,
    "weeksRanked": 14,
    "weeksTopTen": 5
   },
   "attributionComplete": true,
   "recordSplits": {
    "conference": {
     "games": 8,
     "wins": 6,
     "losses": 2,
     "ties": 0,
     "winPercentage": 0.75
    },
    "postseason": {
     "games": 1,
     "wins": 1,
     "losses": 0,
     "ties": 0,
     "winPercentage": 1.0
    },
    "home": {
     "games": 7,
     "wins": 6,
     "losses": 1,
     "ties": 0,
     "winPercentage": 0.857
    },
    "away": {
     "games": 4,
     "wins": 2,
     "losses": 2,
     "ties": 0,
     "winPercentage": 0.5
    },
    "neutral": {
     "games": 0,
     "wins": 0,
     "losses": 0,
     "ties": 0,
     "winPercentage": null
    }
   },
   "scoring": {
    "pointsFor": 411,
    "pointsAgainst": 233,
    "averagePointDifferential": 14.833
   },
   "cfp": {
    "appeared": true,
    "seed": 8,
    "outcome": "Quarterfinal"
   },
   "draftFollowingSeason": {
    "year": 2025,
    "totalPicks": 3,
    "firstRoundPicks": 1
   }
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:55Z', now());

INSERT INTO raw.raw_recruiting_players (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-44-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "id": "108699",
   "athleteId": "5079720",
   "recruitType": "HighSchool",
   "year": 2024,
   "ranking": 1,
   "name": "Top Recruit",
   "school": "Test High",
   "committedTo": "Alpha State",
   "position": "WR",
   "height": 75,
   "weight": 214,
   "stars": 5,
   "rating": 0.9997,
   "city": "Testville",
   "stateProvince": "TX",
   "country": "USA",
   "hometownInfo": {
    "latitude": 25.8967,
    "longitude": -80.2594,
    "fipsCode": "12086"
   }
  },
  {
   "id": "108700",
   "athleteId": null,
   "recruitType": "HighSchool",
   "year": 2024,
   "ranking": 812,
   "name": "Unsigned Recruit",
   "school": "Other High",
   "committedTo": null,
   "position": "OL",
   "height": 78,
   "weight": 300,
   "stars": 3,
   "rating": 0.8412,
   "city": "Elsewhere",
   "stateProvince": "OK",
   "country": "USA",
   "hometownInfo": {
    "latitude": 35.4,
    "longitude": -97.5,
    "fipsCode": "40109"
   }
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:56Z', now());

INSERT INTO raw.raw_recruiting_teams (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-45-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "year": 2024,
   "team": "Alpha State",
   "rank": 1,
   "points": 317.05
  },
  {
   "year": 2024,
   "team": "Beta Tech",
   "rank": 2,
   "points": 288.41
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:57Z', now());

INSERT INTO raw.raw_recruiting_groups (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-46-001Z.json', '{
 "status_code": 200,
 "params": {},
 "data": [
  {
   "team": "Alpha State",
   "conference": "Test Conference",
   "positionGroup": "Defensive Back",
   "averageRating": 0.8082,
   "totalRating": 3.2329,
   "commits": "4",
   "averageStars": "2.5000000000000000"
  },
  {
   "team": "Beta Tech",
   "conference": "Test Conference",
   "positionGroup": "Quarterback",
   "averageRating": 0.9101,
   "totalRating": 1.8202,
   "commits": "2",
   "averageStars": "4.0000000000000000"
  }
 ]
}', 200, '{}',
  '2026-01-01T00:00:58Z', now());

INSERT INTO raw.raw_talent (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-47-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "year": 2024,
   "team": "Alpha State",
   "talent": 1018.28
  },
  {
   "year": 2024,
   "team": "Beta Tech",
   "talent": 702.11
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:59Z', now());

INSERT INTO raw.raw_draft_picks (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-48-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "collegeAthleteId": 4431611,
   "nflAthleteId": 108247,
   "collegeId": 1,
   "collegeTeam": "Alpha State",
   "collegeConference": "Test Conference",
   "nflTeamId": 3,
   "nflTeam": "Chicago",
   "year": 2024,
   "overall": 1,
   "round": 1,
   "pick": 1,
   "name": "First Pick",
   "position": "Quarterback",
   "height": 73,
   "weight": 214,
   "preDraftRanking": 1,
   "preDraftPositionRanking": 1,
   "preDraftGrade": 97,
   "hometownInfo": {
    "city": "Washington",
    "state": "DC",
    "country": "USA",
    "latitude": "38.8949855",
    "longitude": "-77.0365708",
    "countyFips": "11001"
   }
  },
  {
   "collegeAthleteId": 4431612,
   "nflAthleteId": 108248,
   "collegeId": 2,
   "collegeTeam": "Beta Tech",
   "collegeConference": "Test Conference",
   "nflTeamId": 4,
   "nflTeam": "Cincinnati",
   "year": 2024,
   "overall": 33,
   "round": 2,
   "pick": 1,
   "name": "Round Two Pick",
   "position": "Wide Receiver",
   "height": 72,
   "weight": 198,
   "preDraftRanking": 30,
   "preDraftPositionRanking": 4,
   "preDraftGrade": 88,
   "hometownInfo": {
    "city": "Testville",
    "state": "TX",
    "country": "USA",
    "latitude": "32.47",
    "longitude": "-99.71",
    "countyFips": "48441"
   }
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:01:00Z', now());

INSERT INTO raw.raw_draft_positions (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-49-001Z.json', '{
 "status_code": 200,
 "params": {},
 "data": [
  {
   "name": "Quarterback",
   "abbreviation": "QB"
  },
  {
   "name": "Wide Receiver",
   "abbreviation": "WR"
  },
  {
   "name": "Center",
   "abbreviation": "C"
  }
 ]
}', 200, '{}',
  '2026-01-01T00:01:01Z', now());

INSERT INTO raw.raw_draft_teams (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-50-001Z.json', '{
 "status_code": 200,
 "params": {},
 "data": [
  {
   "location": "Chicago",
   "nickname": "Bears",
   "displayName": "Chicago Bears",
   "logo": "https://example/chi.png"
  },
  {
   "location": "Cincinnati",
   "nickname": "Bengals",
   "displayName": "Cincinnati Bengals",
   "logo": "https://example/cin.png"
  },
  {
   "location": "New York",
   "nickname": "Jets",
   "displayName": "New York Jets",
   "logo": "https://example/nyj.png"
  },
  {
   "location": "New York",
   "nickname": "Giants",
   "displayName": "New York Giants",
   "logo": "https://example/nyg.png"
  }
 ]
}', 200, '{}',
  '2026-01-01T00:01:02Z', now());

INSERT INTO raw.raw_roster (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-52-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "id": "1001",
   "firstName": "A",
   "lastName": "Passer",
   "team": "Alpha State",
   "weight": 216,
   "height": 74,
   "jersey": 7,
   "year": 4,
   "position": "QB",
   "homeCity": "Brandon",
   "homeState": "MS",
   "homeCountry": "USA",
   "homeLatitude": 32.2731,
   "homeLongitude": -89.9868,
   "homeCountyFIPS": "28121",
   "recruitIds": [
    "108699"
   ]
  },
  {
   "id": "1002",
   "firstName": "B",
   "lastName": "Runner",
   "team": "Alpha State",
   "weight": 205,
   "height": 70,
   "jersey": 22,
   "year": 2,
   "position": "RB",
   "homeCity": "Testville",
   "homeState": "TX",
   "homeCountry": "USA",
   "homeLatitude": 32.47,
   "homeLongitude": -99.71,
   "homeCountyFIPS": "48441",
   "recruitIds": []
  },
  {
   "id": "1002",
   "firstName": "B",
   "lastName": "Runner",
   "team": "Beta Tech",
   "weight": 205,
   "height": 70,
   "jersey": 24,
   "year": 2,
   "position": "RB",
   "homeCity": "Testville",
   "homeState": "TX",
   "homeCountry": "USA",
   "homeLatitude": 32.47,
   "homeLongitude": -99.71,
   "homeCountyFIPS": "48441",
   "recruitIds": []
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:01:04Z', now());

INSERT INTO raw.raw_conferences_affiliations (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-53-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "teamId": 1,
   "team": "Alpha State",
   "conferenceId": 4,
   "conference": "Test Conference",
   "conferenceAbbreviation": "TC",
   "classification": "fbs",
   "conferenceDivision": null,
   "startYear": 2024,
   "endYear": null
  },
  {
   "teamId": 1,
   "team": "Alpha State",
   "conferenceId": 9,
   "conference": "Old Conference",
   "conferenceAbbreviation": "OC",
   "classification": "fbs",
   "conferenceDivision": null,
   "startYear": 2013,
   "endYear": 2023
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:01:05Z', now());

INSERT INTO raw.raw_conferences_changes (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-54-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "teamId": 1,
   "team": "Alpha State",
   "fromConferenceId": 9,
   "fromConference": "Old Conference",
   "fromConferenceAbbreviation": "OC",
   "fromClassification": "fbs",
   "toConferenceId": 4,
   "toConference": "Test Conference",
   "toConferenceAbbreviation": "TC",
   "toClassification": "fbs",
   "effectiveYear": 2024
  },
  {
   "teamId": 3,
   "team": "Gamma College",
   "fromConferenceId": 20,
   "fromConference": "Small Conference",
   "fromConferenceAbbreviation": "SC",
   "fromClassification": "fcs",
   "toConferenceId": 4,
   "toConference": "Test Conference",
   "toConferenceAbbreviation": "TC",
   "toClassification": "fbs",
   "effectiveYear": 2024
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:01:06Z', now());

INSERT INTO raw.raw_playoffs_cfp (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-55-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": {
  "season": 2024,
  "competition": "cfp",
  "format": "twelve_team_2024",
  "teamCount": 12,
  "status": "completed",
  "participants": [
   {
    "team": {
     "id": 1,
     "school": "Alpha State",
     "conference": "Test Conference"
    },
    "committeeRank": 1,
    "seed": 1,
    "bidType": "automatic",
    "qualificationReason": "Conference champion automatic qualifier",
    "conferenceChampion": true,
    "qualifyingConference": "Test Conference",
    "firstRoundBye": true,
    "outcome": "champion",
    "eliminatedRound": null
   },
   {
    "team": {
     "id": 2,
     "school": "Beta Tech",
     "conference": "Test Conference"
    },
    "committeeRank": 2,
    "seed": 2,
    "bidType": "at_large",
    "qualificationReason": "At-large selection",
    "conferenceChampion": false,
    "qualifyingConference": null,
    "firstRoundBye": false,
    "outcome": "eliminated",
    "eliminatedRound": "quarterfinal"
   }
  ],
  "rounds": [
   {
    "code": "first_round",
    "name": "First Round",
    "order": 1,
    "matchups": []
   }
  ],
  "champion": {
   "id": 1,
   "school": "Alpha State",
   "conference": "Test Conference"
  }
 }
}', 200, '{"year": "2024"}',
  '2026-01-01T00:01:07Z', now());

INSERT INTO raw.raw_playoffs_cfp_games (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-56-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "id": 31,
   "bracketSlot": "FR1",
   "round": "first_round",
   "roundName": "First Round",
   "roundOrder": 1,
   "matchupOrder": 1,
   "startDate": "2024-12-21T21:00:00.000Z",
   "bowlName": "Test First Round",
   "slots": [
    {
     "position": 1,
     "seed": 5,
     "participant": {
      "id": 1,
      "school": "Alpha State",
      "conference": "Test Conference"
     },
     "source": null
    },
    {
     "position": 2,
     "seed": 12,
     "participant": {
      "id": 2,
      "school": "Beta Tech",
      "conference": "Test Conference"
     },
     "source": null
    }
   ],
   "game": {
    "id": 401677176,
    "startDate": "2024-12-21T21:00:00.000Z",
    "completed": true,
    "homeTeam": {
     "id": 1,
     "school": "Alpha State",
     "conference": "Test Conference"
    },
    "homePoints": 38,
    "awayTeam": {
     "id": 2,
     "school": "Beta Tech",
     "conference": "Test Conference"
    },
    "awayPoints": 24,
    "venueId": 501,
    "venue": "Alpha Field"
   },
   "advancesTo": {
    "matchupId": 36,
    "bracketSlot": "QF2",
    "position": 2
   }
  },
  {
   "id": 36,
   "bracketSlot": "QF2",
   "round": "quarterfinal",
   "roundName": "Quarterfinal",
   "roundOrder": 2,
   "matchupOrder": 2,
   "startDate": "2025-01-01T22:00:00.000Z",
   "bowlName": "Test Quarterfinal",
   "slots": [
    {
     "position": 1,
     "seed": 4,
     "participant": {
      "id": null,
      "school": null,
      "conference": "Test Conference"
     },
     "source": null
    },
    {
     "position": 2,
     "seed": null,
     "participant": null,
     "source": {
      "matchupId": 31
     }
    }
   ],
   "game": null,
   "advancesTo": {
    "matchupId": 40,
    "bracketSlot": "SF1",
    "position": 1
   }
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:01:08Z', now());

INSERT INTO raw.raw_playoffs_cfp_participants (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-57-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "team": {
    "id": 1,
    "school": "Alpha State",
    "conference": "Test Conference"
   },
   "committeeRank": 1,
   "seed": 1,
   "bidType": "automatic",
   "qualificationReason": "Conference champion automatic qualifier",
   "conferenceChampion": true,
   "qualifyingConference": "Test Conference",
   "firstRoundBye": true,
   "outcome": "champion",
   "eliminatedRound": null
  },
  {
   "team": {
    "id": 2,
    "school": "Beta Tech",
    "conference": "Test Conference"
   },
   "committeeRank": 2,
   "seed": 2,
   "bidType": "at_large",
   "qualificationReason": "At-large selection",
   "conferenceChampion": false,
   "qualifyingConference": null,
   "firstRoundBye": false,
   "outcome": "eliminated",
   "eliminatedRound": "quarterfinal"
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:01:09Z', now());

INSERT INTO raw.raw_manifest
  (endpoint, filename, params, status_code, row_count, fetched_at, loaded_at) VALUES
  ('metrics_wp_pregame', '2026-01-01T00-00-41-001Z.json',
   '{"year": "2024", "seasonType": "regular"}', 200, 1,
   '2026-01-01T00:00:52Z', '2026-01-01T00:00:52Z'),
  ('metrics_wp_pregame', '2026-01-01T00-00-41-002Z.json',
   '{"year": "2024", "seasonType": "regular"}', 200, 1,
   '2026-01-01T00:00:53Z', '2026-01-01T00:00:53Z')
ON CONFLICT DO NOTHING;

INSERT INTO raw.raw_manifest (endpoint, filename, params, status_code, row_count, fetched_at, loaded_at) VALUES
('teams', '2026-01-01T00-00-00-001Z.json', '{"year": "2024"}', 200, 2, '2026-01-01T00:00:00Z', now()),
('teams', '2026-01-01T00-00-00-002Z.json', '{"year": "1900"}', 200, 2, '2026-01-01T00:00:00Z', now()),
('teams', '2026-01-01T00-00-00-003Z.json', '{"year": "2024"}', 401, 0, '2026-01-01T00:00:01Z', now()),
('games', '2026-01-01T00-00-01-001Z.json', '{"year": "2024", "seasonType": "regular"}', 200, 3, '2026-01-01T00:00:02Z', now()),
('games', '2026-01-01T00-00-01-002Z.json', '{"year": "1900", "seasonType": "regular"}', 200, 1, '2026-01-01T00:00:03Z', now()),
-- An endpoint that has never returned rows: legitimately empty, must not read as a loss.
('records', '2026-01-01T00-00-02-001Z.json', '{"year": "2026"}', 200, 0, '2026-01-01T00:00:04Z', now());

-- ---------------------------------------------------------------------------------------
-- Phase 1 sources. Each carries the smallest payload that exercises a real hazard rather
-- than a happy path — the fixture's job is to fail when a model regresses, not to be
-- representative.
-- ---------------------------------------------------------------------------------------

-- Venues. Stands alone: /games gives a venue *name* and no usable id, so nothing joins here.
INSERT INTO raw.raw_venues (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-03-001Z.json', '{
  "status_code": 200, "params": {},
  "data": [
    {"id": 101, "name": "Alpha Field", "city": "Alphaville", "state": "AA", "zip": "00001",
     "countryCode": "US", "timezone": "America/Chicago", "latitude": 30.5, "longitude": -97.5,
     "elevation": 150.0, "capacity": 50000, "constructionYear": 1950, "grass": true,
     "dome": false},
    {"id": 102, "name": "Beta Grounds", "city": "Betaburg", "state": "BB", "zip": "00002",
     "countryCode": "US", "timezone": "America/New_York", "latitude": 40.1, "longitude": -75.2,
     "elevation": null, "capacity": null, "constructionYear": null, "grass": false,
     "dome": true}
  ]}', 200, '{}', '2026-01-01T00:00:05Z', now());

-- Conferences are season-scoped: the year lives only in params, never in the payload.
INSERT INTO raw.raw_conferences (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-04-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"id": 1, "name": "Test Conference", "shortName": "Test", "abbreviation": "TC",
     "classification": "fbs", "memberCount": 2}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:06Z', now());

-- Calendar. Carries a spring week on purpose: the 2020 FCS season was played in spring 2021
-- under its own season types, and requesting only regular/postseason silently omitted 532
-- real games. A fixture without a spring row lets that regression back in unnoticed.
INSERT INTO raw.raw_calendar (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-05-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"season": 2024, "week": 1, "seasonType": "regular",
     "startDate": "2024-08-24T00:00:00.000Z", "endDate": "2024-09-09T00:00:00.000Z",
     "firstGameStart": "2024-08-24T16:00:00.000Z",
     "lastGameStart": "2024-09-08T23:00:00.000Z"},
    {"season": 2024, "week": 1, "seasonType": "postseason",
     "startDate": "2024-12-14T00:00:00.000Z", "endDate": "2025-01-21T00:00:00.000Z",
     "firstGameStart": "2024-12-14T16:00:00.000Z",
     "lastGameStart": "2025-01-20T23:30:00.000Z"}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:07Z', now()),
-- The coverage floor itself. `assert_dim_week_floor_is_2002` asserts equality, not an
-- inequality, so the fixture has to carry the boundary season or the test fails in CI for
-- a reason that has nothing to do with the model. A fixture that asserts a boundary must
-- contain it.
('2026-01-01T00-00-05-003Z.json', '{
  "status_code": 200, "params": {"year": "2002"},
  "data": [
    {"season": 2002, "week": 1, "seasonType": "regular",
     "startDate": "2002-08-24T00:00:00.000Z", "endDate": "2002-09-02T00:00:00.000Z",
     "firstGameStart": "2002-08-24T16:00:00.000Z",
     "lastGameStart": "2002-09-01T23:00:00.000Z"}
  ]}', 200, '{"year": "2002"}', '2026-01-01T00:00:07Z', now()),
('2026-01-01T00-00-05-002Z.json', '{
  "status_code": 200, "params": {"year": "2020"},
  "data": [
    {"season": 2020, "week": 1, "seasonType": "spring_regular",
     "startDate": "2021-02-20T00:00:00.000Z", "endDate": "2021-02-27T00:00:00.000Z",
     "firstGameStart": "2021-02-20T18:00:00.000Z",
     "lastGameStart": "2021-02-26T23:00:00.000Z"},
    {"season": 2020, "week": 1, "seasonType": "spring_postseason",
     "startDate": "2021-04-24T00:00:00.000Z", "endDate": "2021-05-16T00:00:00.000Z",
     "firstGameStart": "2021-04-24T18:00:00.000Z",
     "lastGameStart": "2021-05-15T23:00:00.000Z"}
  ]}', 200, '{"year": "2020"}', '2026-01-01T00:00:07Z', now());

-- Box scores. `possessionTime` arrives as a padded clock string — " 30:15 " with surrounding
-- spaces — which is what broke the integer cast on the real data. Kept verbatim so the
-- split-and-parse path is exercised rather than assumed.
INSERT INTO raw.raw_games_teams (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-06-001Z.json', '{
  "status_code": 200, "params": {"year": "2024", "week": "1", "seasonType": "regular"},
  "data": [
    {"id": 9001, "teams": [
      {"teamId": 1, "team": "Alpha State", "homeAway": "home", "points": 28, "stats": [
        {"category": "totalYards", "stat": "412"},
        {"category": "netPassingYards", "stat": "244"},
        {"category": "rushingYards", "stat": "168"},
        {"category": "firstDowns", "stat": "22"},
        {"category": "turnovers", "stat": "1"},
        {"category": "possessionTime", "stat": " 32:41 "}
      ]},
      {"teamId": 2, "team": "Beta Tech", "homeAway": "away", "points": 21, "stats": [
        {"category": "totalYards", "stat": "355"},
        {"category": "netPassingYards", "stat": "301"},
        {"category": "rushingYards", "stat": "54"},
        {"category": "firstDowns", "stat": "19"},
        {"category": "turnovers", "stat": "2"},
        {"category": "possessionTime", "stat": " 27:19 "}
      ]}
    ]}
  ]}', 200, '{"year": "2024", "week": "1", "seasonType": "regular"}',
  '2026-01-01T00:00:08Z', now());

-- CFBD's own records, for the reconciliation test. Alpha won 9001, Beta lost it, so these
-- agree with what fct_team_record derives from the game spine. A fixture that disagreed
-- would make the test red for a reason that has nothing to do with the code under test.
-- Player box scores. Four levels of array: game -> teams[] -> categories[] -> types[] ->
-- athletes[]. The fixture keeps all four so a flattening bug cannot pass by collapsing one.
--
-- NOTE THERE IS NO teamId HERE, and that is faithful rather than lazy — /games/players
-- identifies teams by name only. A fixture that invented one would let a model be written
-- against an id that does not exist in production.
INSERT INTO raw.raw_games_players (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-07-001Z.json', '{
  "status_code": 200, "params": {"year": "2024", "week": "1", "seasonType": "regular"},
  "data": [
    {"id": 9001, "teams": [
      {"team": "Alpha State", "conference": "Test Conference", "homeAway": "home", "points": 28,
       "categories": [
         {"name": "passing", "types": [
           {"name": "C/ATT", "athletes": [{"id": "1001", "name": "A. Passer", "stat": "18/26"}]},
           {"name": "YDS",   "athletes": [{"id": "1001", "name": "A. Passer", "stat": "244"}]},
           {"name": "TD",    "athletes": [{"id": "1001", "name": "A. Passer", "stat": "3"}]}
         ]},
         {"name": "rushing", "types": [
           {"name": "CAR", "athletes": [
             {"id": "1002", "name": "B. Runner", "stat": "21"},
             {"id": "1003", "name": "C. Back",   "stat": "7"}]},
           {"name": "YDS", "athletes": [
             {"id": "1002", "name": "B. Runner", "stat": "131"},
             {"id": "1003", "name": "C. Back",   "stat": "37"}]}
         ]}
       ]},
      {"team": "Beta Tech", "conference": "Test Conference", "homeAway": "away", "points": 21,
       "categories": [
         {"name": "passing", "types": [
           {"name": "C/ATT", "athletes": [{"id": "2001", "name": "D. Arm", "stat": "24/39"}]},
           {"name": "YDS",   "athletes": [{"id": "2001", "name": "D. Arm", "stat": "301"}]}
         ]}
       ]}
    ]}
  ]}', 200, '{"year": "2024", "week": "1", "seasonType": "regular"}',
  '2026-01-01T00:00:09Z', now());

-- Weather. Flat, and every one of the twenty-two published fields is present so a model that
-- silently stopped reading one would not pass by finding null everywhere.
--
-- Game 9002 is INDOORS and still reports a temperature — that is what CFBD does, and it is
-- the trap the is_indoors column exists to let callers avoid. Game 9003 carries nulls across
-- every measurement, which is what an unplayed or old game looks like; a hard cast instead of
-- safe_numeric fails the model on exactly this row.
INSERT INTO raw.raw_games_weather (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-08-001Z.json', '{
  "status_code": 200, "params": {"year": "2024", "seasonType": "regular"},
  "data": [
    {"id": 9001, "season": 2024, "week": 1, "seasonType": "regular",
     "startTime": "2024-08-31T23:00:00.000Z", "gameIndoors": false,
     "homeTeam": "Alpha State", "homeConference": "Test Conference",
     "awayTeam": "Beta Tech", "awayConference": "Test Conference",
     "venueId": 501, "venue": "Alpha Field",
     "temperature": 71.4, "dewPoint": 55.2, "humidity": 56, "precipitation": 0,
     "snowfall": 0, "windDirection": 210, "windSpeed": 8.1, "pressure": 1014.6,
     "weatherConditionCode": 2, "weatherCondition": "Fair"},
    {"id": 9002, "season": 2024, "week": 2, "seasonType": "regular",
     "startTime": "2024-09-07T19:30:00.000Z", "gameIndoors": true,
     "homeTeam": "Beta Tech", "homeConference": "Test Conference",
     "awayTeam": "Alpha State", "awayConference": "Test Conference",
     "venueId": 502, "venue": "Beta Dome",
     "temperature": 72.0, "dewPoint": 50.0, "humidity": 45, "precipitation": 0,
     "snowfall": 0, "windDirection": 0, "windSpeed": 0, "pressure": 1016.0,
     "weatherConditionCode": 1, "weatherCondition": "Clear"},
    {"id": 9003, "season": 2024, "week": 3, "seasonType": "regular",
     "startTime": "2024-09-14T16:00:00.000Z", "gameIndoors": false,
     "homeTeam": "Alpha State", "homeConference": "Test Conference",
     "awayTeam": "Gamma College", "awayConference": null,
     "venueId": 501, "venue": "Alpha Field",
     "temperature": null, "dewPoint": null, "humidity": null, "precipitation": null,
     "snowfall": null, "windDirection": null, "windSpeed": null, "pressure": null,
     "weatherConditionCode": null, "weatherCondition": null}
  ]}', 200, '{"year": "2024", "seasonType": "regular"}',
  '2026-01-01T00:00:10Z', now());

-- Advanced stats. Both sides are present with DIFFERENT values, which is the point: a model
-- that read offense's keys for the defense columns would produce identical numbers and pass
-- every null and range check. Only distinct values catch it.
INSERT INTO raw.raw_stats_game_advanced (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-09-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024",
  "seasonType": "regular"
 },
 "data": [
  {
   "gameId": 9001,
   "season": 2024,
   "seasonType": "regular",
   "week": 1,
   "team": "Alpha State",
   "opponent": "Beta Tech",
   "offense": {
    "plays": 65,
    "drives": 12,
    "ppa": 0.51,
    "totalPPA": 33.2,
    "successRate": 0.48,
    "explosiveness": 1.71,
    "powerSuccess": 0.62,
    "stuffRate": 0.15,
    "lineYards": 2.41,
    "lineYardsTotal": 113,
    "secondLevelYards": 1.23,
    "secondLevelYardsTotal": 58,
    "openFieldYards": 3.77,
    "openFieldYardsTotal": 177,
    "standardDowns": {
     "ppa": 0.38,
     "successRate": 0.46,
     "explosiveness": 1.49
    },
    "passingDowns": {
     "ppa": 1.62,
     "successRate": 0.6,
     "explosiveness": 2.82
    },
    "rushingPlays": {
     "ppa": 0.44,
     "totalPPA": 20.9,
     "successRate": 0.42,
     "explosiveness": 1.68
    },
    "passingPlays": {
     "ppa": 1.26,
     "totalPPA": 22.7,
     "successRate": 0.66,
     "explosiveness": 2.17
    }
   },
   "defense": {
    "plays": 68,
    "drives": 15,
    "ppa": 0.81,
    "totalPPA": 36.2,
    "successRate": 0.51,
    "explosiveness": 2.01,
    "powerSuccess": 0.65,
    "stuffRate": 0.18,
    "lineYards": 2.71,
    "lineYardsTotal": 116,
    "secondLevelYards": 1.53,
    "secondLevelYardsTotal": 61,
    "openFieldYards": 4.07,
    "openFieldYardsTotal": 180,
    "standardDowns": {
     "ppa": 0.68,
     "successRate": 0.49,
     "explosiveness": 1.79
    },
    "passingDowns": {
     "ppa": 1.92,
     "successRate": 0.63,
     "explosiveness": 3.12
    },
    "rushingPlays": {
     "ppa": 0.74,
     "totalPPA": 23.9,
     "successRate": 0.45,
     "explosiveness": 1.98
    },
    "passingPlays": {
     "ppa": 1.56,
     "totalPPA": 25.7,
     "successRate": 0.69,
     "explosiveness": 2.47
    }
   }
  }
 ]
}', 200, '{"year": "2024", "seasonType": "regular"}',
  '2026-01-01T00:00:11Z', now());

-- Season advanced. Carries the extra season-only groups AND `totalOpportunies` spelled the
-- way CFBD spells it — reading the correct spelling returns null on every row.
INSERT INTO raw.raw_stats_season_advanced (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-10-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "season": 2024,
   "team": "Alpha State",
   "conference": "Test Conference",
   "offense": {
    "plays": 65,
    "drives": 12,
    "ppa": 0.51,
    "totalPPA": 33.2,
    "successRate": 0.48,
    "explosiveness": 1.71,
    "powerSuccess": 0.62,
    "stuffRate": 0.15,
    "lineYards": 2.41,
    "lineYardsTotal": 113,
    "secondLevelYards": 1.23,
    "secondLevelYardsTotal": 58,
    "openFieldYards": 3.77,
    "openFieldYardsTotal": 177,
    "standardDowns": {
     "ppa": 0.38,
     "successRate": 0.46,
     "explosiveness": 1.49,
     "rate": 0.72
    },
    "passingDowns": {
     "ppa": 1.62,
     "successRate": 0.6,
     "explosiveness": 2.82,
     "rate": 0.72,
     "totalPPA": 9.4
    },
    "rushingPlays": {
     "ppa": 0.44,
     "totalPPA": 20.9,
     "successRate": 0.42,
     "explosiveness": 1.68,
     "rate": 0.72
    },
    "passingPlays": {
     "ppa": 1.26,
     "totalPPA": 22.7,
     "successRate": 0.66,
     "explosiveness": 2.17,
     "rate": 0.72
    },
    "totalOpportunies": 52,
    "pointsPerOpportunity": 4.02,
    "fieldPosition": {
     "averageStart": 71.4,
     "averagePredictedPoints": 1.273
    },
    "havoc": {
     "total": 0.121,
     "frontSeven": 0.094,
     "db": 0.027
    }
   },
   "defense": {
    "plays": 68,
    "drives": 15,
    "ppa": 0.81,
    "totalPPA": 36.2,
    "successRate": 0.51,
    "explosiveness": 2.01,
    "powerSuccess": 0.65,
    "stuffRate": 0.18,
    "lineYards": 2.71,
    "lineYardsTotal": 116,
    "secondLevelYards": 1.53,
    "secondLevelYardsTotal": 61,
    "openFieldYards": 4.07,
    "openFieldYardsTotal": 180,
    "standardDowns": {
     "ppa": 0.68,
     "successRate": 0.49,
     "explosiveness": 1.79,
     "rate": 0.75
    },
    "passingDowns": {
     "ppa": 1.92,
     "successRate": 0.63,
     "explosiveness": 3.12,
     "rate": 0.75,
     "totalPPA": 12.4
    },
    "rushingPlays": {
     "ppa": 0.74,
     "totalPPA": 23.9,
     "successRate": 0.45,
     "explosiveness": 1.98,
     "rate": 0.75
    },
    "passingPlays": {
     "ppa": 1.56,
     "totalPPA": 25.7,
     "successRate": 0.69,
     "explosiveness": 2.47,
     "rate": 0.75
    },
    "totalOpportunies": 55,
    "pointsPerOpportunity": 4.32,
    "fieldPosition": {
     "averageStart": 74.4,
     "averagePredictedPoints": 1.573
    },
    "havoc": {
     "total": 0.151,
     "frontSeven": 0.124,
     "db": 0.057
    }
   }
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:12Z', now());

INSERT INTO raw.raw_stats_game_havoc (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-11-001Z.json', '{
  "status_code": 200, "params": {"year": "2024", "seasonType": "regular"},
  "data": [
    {"gameId": 9001, "season": 2024, "seasonType": "regular", "week": 1,
     "team": "Alpha State", "conference": "Test Conference",
     "opponent": "Beta Tech", "opponentConference": "Test Conference",
     "offense": {"totalPlays": 67, "totalHavocEvents": 17, "frontSevenHavocEvents": 7,
                 "dbHavocEvents": 10, "havocRate": 0.253, "frontSevenHavocRate": 0.104,
                 "dbHavocRate": 0.149},
     "defense": {"totalPlays": 65, "totalHavocEvents": 6, "frontSevenHavocEvents": 5,
                 "dbHavocEvents": 1, "havocRate": 0.092, "frontSevenHavocRate": 0.077,
                 "dbHavocRate": 0.015}}
  ]}', 200, '{"year": "2024", "seasonType": "regular"}', '2026-01-01T00:00:13Z', now());

-- A BARE ARRAY OF STRINGS, no wrapping object. The only endpoint shaped this way, and the
-- reason json_scalar_text exists: reading these with ::text keeps JSON's quotes.
INSERT INTO raw.raw_stats_categories (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-12-001Z.json', '{
  "status_code": 200, "params": {},
  "data": ["totalYards", "netPassingYards", "rushingYards", "firstDowns", "turnovers",
           "possessionTime", "thirdDownEff"]}', 200, '{}',
  '2026-01-01T00:00:14Z', now());

INSERT INTO raw.raw_stats_player_season (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-13-001Z.json', '{
  "status_code": 200, "params": {"year": "2024", "seasonType": "regular"},
  "data": [
    {"season": 2024, "playerId": "1001", "player": "A. Passer", "position": "QB",
     "team": "Alpha State", "conference": "Test Conference",
     "category": "passing", "statType": "YDS", "stat": "2944"},
    {"season": 2024, "playerId": "1001", "player": "A. Passer", "position": "QB",
     "team": "Alpha State", "conference": "Test Conference",
     "category": "passing", "statType": "TD", "stat": "24"},
    {"season": 2024, "playerId": "1002", "player": "B. Runner", "position": "RB",
     "team": "Alpha State", "conference": "Test Conference",
     "category": "rushing", "statType": "YDS", "stat": "1188"}
  ]}', 200, '{"year": "2024", "seasonType": "regular"}', '2026-01-01T00:00:15Z', now());

-- successRate null when plays is zero is the NORMAL case, not an edge one — a receiver has
-- no passing plays. Coercing it to 0 would make "0% on no attempts" and "0% on twenty
-- attempts" the same number.
INSERT INTO raw.raw_stats_player_success (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-14-001Z.json', '{
  "status_code": 200, "params": {"year": "2024", "seasonType": "regular"},
  "data": [
    {"season": 2024, "id": "1001", "name": "A. Passer", "position": "QB",
     "team": "Alpha State", "conference": "Test Conference",
     "passing": {"plays": 312, "successes": 151, "successRate": 0.484},
     "rushing": {"plays": 44, "successes": 21, "successRate": 0.477}},
    {"season": 2024, "id": "1004", "name": "E. Receiver", "position": "WR",
     "team": "Alpha State", "conference": "Test Conference",
     "passing": {"plays": 0, "successes": 0, "successRate": null},
     "rushing": {"plays": 2, "successes": 1, "successRate": 0.5}}
  ]}', 200, '{"year": "2024", "seasonType": "regular"}', '2026-01-01T00:00:16Z', now());

-- One 200 and one 400. The 400 is faithful: CFBD rejects a year-only call on this endpoint,
-- and a model that read the payload before checking the status would explode on it.
INSERT INTO raw.raw_stats_player_success_game (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-15-001Z.json', '{
  "status_code": 400, "params": {"year": "2024", "seasonType": "regular"},
  "data": {"error": "week required when team and playerId not specified"}}',
  400, '{"year": "2024", "seasonType": "regular"}', '2026-01-01T00:00:17Z', now()),
('2026-01-01T00-00-15-002Z.json', '{
  "status_code": 200, "params": {"year": "2024", "week": "1", "seasonType": "regular"},
  "data": [
    {"season": 2024, "seasonType": "regular", "week": 1, "gameId": 9001,
     "id": "1001", "name": "A. Passer", "position": "QB",
     "team": "Alpha State", "conference": "Test Conference", "opponent": "Beta Tech",
     "passing": {"plays": 26, "successes": 14, "successRate": 0.538},
     "rushing": {"plays": 3, "successes": 1, "successRate": 0.333}}
  ]}', 200, '{"year": "2024", "week": "1", "seasonType": "regular"}',
  '2026-01-01T00:00:18Z', now());

INSERT INTO raw.raw_records (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-07-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "year": 2024,
   "teamId": 1,
   "team": "Alpha State",
   "classification": "fbs",
   "conference": "Test Conference",
   "division": "",
   "expectedWins": 2.1,
   "total": {
    "games": 3,
    "wins": 2,
    "losses": 0,
    "ties": 1
   },
   "conferenceGames": {
    "games": 2,
    "wins": 1,
    "losses": 0,
    "ties": 1
   },
   "homeGames": {
    "games": 2,
    "wins": 2,
    "losses": 0,
    "ties": 0
   },
   "awayGames": {
    "games": 1,
    "wins": 0,
    "losses": 0,
    "ties": 1
   },
   "neutralSiteGames": {
    "games": 0,
    "wins": 0,
    "losses": 0,
    "ties": 0
   },
   "regularSeason": {
    "games": 3,
    "wins": 2,
    "losses": 0,
    "ties": 1
   },
   "postseason": {
    "games": 0,
    "wins": 0,
    "losses": 0,
    "ties": 0
   }
  },
  {
   "year": 2024,
   "teamId": 2,
   "team": "Beta Tech",
   "classification": "fbs",
   "conference": "Test Conference",
   "division": "",
   "expectedWins": 0.8,
   "total": {
    "games": 2,
    "wins": 0,
    "losses": 1,
    "ties": 1
   },
   "conferenceGames": {
    "games": 2,
    "wins": 0,
    "losses": 1,
    "ties": 1
   },
   "homeGames": {
    "games": 1,
    "wins": 0,
    "losses": 0,
    "ties": 1
   },
   "awayGames": {
    "games": 1,
    "wins": 0,
    "losses": 1,
    "ties": 0
   },
   "neutralSiteGames": {
    "games": 0,
    "wins": 0,
    "losses": 0,
    "ties": 0
   },
   "regularSeason": {
    "games": 2,
    "wins": 0,
    "losses": 1,
    "ties": 1
   },
   "postseason": {
    "games": 0,
    "wins": 0,
    "losses": 0,
    "ties": 0
   }
  },
  {
   "year": 2024,
   "teamId": 77,
   "team": "Gamma College",
   "classification": "ii",
   "conference": null,
   "division": "",
   "expectedWins": null,
   "total": {
    "games": 1,
    "wins": 0,
    "losses": 1,
    "ties": 0
   },
   "conferenceGames": {
    "games": 0,
    "wins": 0,
    "losses": 0,
    "ties": 0
   },
   "homeGames": {
    "games": 0,
    "wins": 0,
    "losses": 0,
    "ties": 0
   },
   "awayGames": {
    "games": 1,
    "wins": 0,
    "losses": 1,
    "ties": 0
   },
   "neutralSiteGames": {
    "games": 0,
    "wins": 0,
    "losses": 0,
    "ties": 0
   },
   "regularSeason": {
    "games": 1,
    "wins": 0,
    "losses": 1,
    "ties": 0
   },
   "postseason": {
    "games": 0,
    "wins": 0,
    "losses": 0,
    "ties": 0
   }
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:09Z', now()),
-- The legitimately-empty response already in the manifest. An endpoint that returns
-- no rows is not a failure, and nothing downstream may treat it as one.
('2026-01-01T00-00-02-001Z.json', '{
  "status_code": 200, "params": {"year": "2026"}, "data": []
  }', 200, '{"year": "2026"}', '2026-01-01T00:00:04Z', now());

-- Betting lines, two snapshots of the same game.
--
-- Snapshot 1 reproduces the collision that CFBD actually emits: `DraftKings` and
-- `Draft Kings` in one response for one game, identical spread, but the second carrying null
-- moneylines. They are one book, so mapping both to `draftkings` makes the grain collide —
-- and the fixture must contain the collision, or the dedup rule and its losslessness test
-- pass in CI without ever being exercised.
--
-- Two snapshots also mean `fct_betting_line` is built from more than one `snapshot_ts`,
-- which is the minimum needed for the incremental anti-join to mean anything.
INSERT INTO raw.raw_lines (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-08-001Z.json', '{
  "status_code": 200, "params": {"year": "2024", "week": "1", "seasonType": "regular"},
  "data": [
    {"id": 9001, "season": 2024, "week": 1, "seasonType": "regular",
     "homeTeam": "Alpha State", "awayTeam": "Beta Tech", "lines": [
      {"provider": "DraftKings", "spread": -7.5, "formattedSpread": "Alpha State -7.5",
       "spreadOpen": -7.0, "overUnder": 55.5, "overUnderOpen": 54.5,
       "homeMoneyline": -300, "awayMoneyline": 240},
      {"provider": "Draft Kings", "spread": -7.5, "formattedSpread": "Alpha State -7.5",
       "spreadOpen": -7.0, "overUnder": 55.5, "overUnderOpen": 54.5,
       "homeMoneyline": null, "awayMoneyline": null},
      {"provider": "Bovada", "spread": -7.0, "formattedSpread": "Alpha State -7",
       "spreadOpen": -7.0, "overUnder": 56.0, "overUnderOpen": 55.0,
       "homeMoneyline": -280, "awayMoneyline": 230}
    ]}
  ]}', 200, '{"year": "2024", "week": "1", "seasonType": "regular"}',
  '2026-01-01T00:00:10Z', now()),
('2026-01-01T00-00-09-001Z.json', '{
  "status_code": 200, "params": {"year": "2024", "week": "1", "seasonType": "regular"},
  "data": [
    {"id": 9001, "season": 2024, "week": 1, "seasonType": "regular",
     "homeTeam": "Alpha State", "awayTeam": "Beta Tech", "lines": [
      {"provider": "DraftKings", "spread": -8.0, "formattedSpread": "Alpha State -8",
       "spreadOpen": -7.0, "overUnder": 56.5, "overUnderOpen": 54.5,
       "homeMoneyline": -320, "awayMoneyline": 255}
    ]}
  ]}', 200, '{"year": "2024", "week": "1", "seasonType": "regular"}',
  '2026-01-01T00:00:14Z', now());

-- Manifest rows for the new endpoints. `stg_lines` takes its snapshot timestamp from
-- `fetched_at` here, not from the file, so a lines file with no manifest row is invisible.
INSERT INTO raw.raw_manifest (endpoint, filename, params, status_code, row_count, fetched_at, loaded_at) VALUES
('venues',      '2026-01-01T00-00-03-001Z.json', '{}', 200, 2, '2026-01-01T00:00:05Z', now()),
('conferences', '2026-01-01T00-00-04-001Z.json', '{"year": "2024"}', 200, 1, '2026-01-01T00:00:06Z', now()),
('calendar',    '2026-01-01T00-00-05-001Z.json', '{"year": "2024"}', 200, 2, '2026-01-01T00:00:07Z', now()),
('calendar',    '2026-01-01T00-00-05-002Z.json', '{"year": "2020"}', 200, 2, '2026-01-01T00:00:07Z', now()),
('calendar',    '2026-01-01T00-00-05-003Z.json', '{"year": "2002"}', 200, 1, '2026-01-01T00:00:07Z', now()),
('games/teams', '2026-01-01T00-00-06-001Z.json', '{"year": "2024", "week": "1", "seasonType": "regular"}', 200, 1, '2026-01-01T00:00:08Z', now()),
('records',     '2026-01-01T00-00-07-001Z.json', '{"year": "2024"}', 200, 2, '2026-01-01T00:00:09Z', now()),
('lines',       '2026-01-01T00-00-08-001Z.json', '{"year": "2024", "week": "1", "seasonType": "regular"}', 200, 1, '2026-01-01T00:00:10Z', now()),
('lines',       '2026-01-01T00-00-09-001Z.json', '{"year": "2024", "week": "1", "seasonType": "regular"}', 200, 1, '2026-01-01T00:00:14Z', now());

-- Quota telemetry. Two snapshots so the series has a delta rather than a single point —
-- one row answers "where are we", only a series answers "where are we heading".
--
-- The LATEST snapshot deliberately sits above the 90% error threshold, so the escalating
-- branch of the quota signal runs on every CI build. The earlier one is comfortably below
-- it, which keeps the series honest: a quota that was fine and is now not is the shape the
-- alarm exists to catch, and it also proves fct_api_usage takes the latest observation per
-- resource rather than the first or an average.
--
-- Only one severity per resource is observable at a time — the signal reports current state
-- — so the choice is which branch CI exercises, and an unexercised alarm is worth less than
-- an unexercised all-clear. ci/check_health_signals.py asserts this stays true.
INSERT INTO raw.raw_info (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-10-001Z.json', '{
  "status_code": 200, "params": {},
  "data": {"patronLevel": 3, "tierName": "Tier 3", "monthlyLimit": 75000,
           "remainingCalls": 73053, "usedCalls": 1947,
           "resetAt": "2026-09-01T00:00:00.000Z", "sharedPool": true,
           "products": ["cfb", "cbb"]}
  }', 200, '{}', '2026-01-01T00:00:20Z', now()),
('2026-01-01T00-00-10-002Z.json', '{
  "status_code": 200, "params": {},
  "data": {"patronLevel": 3, "tierName": "Tier 3", "monthlyLimit": 75000,
           "remainingCalls": 3750, "usedCalls": 71250,
           "resetAt": "2026-09-01T00:00:00.000Z", "sharedPool": true,
           "products": ["cfb", "cbb"]}
  }', 200, '{}', '2026-01-01T00:00:21Z', now());

-- The manifest labels this endpoint `info_usage`, not `info/usage`: src/ingest.fetch
-- flattens the slash so the endpoint can be a directory name. Joining on the API path
-- returns zero rows with no error, which is exactly how this model shipped broken once.
INSERT INTO raw.raw_info_usage (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-11-001Z.json', '{
  "status_code": 200, "params": {"days": "31", "limit": "50"},
  "data": {"window": {"start": "2026-07-18T00:00:00.000Z", "end": "2026-08-18T00:00:00.000Z"},
           "api": "cfb",
           "totals": {"requests": 1967, "cfbRequests": 1967, "cbbRequests": 0,
                      "uniqueEndpoints": 65},
           "topEndpoints": [
             {"api": "cfb", "endpoint": "/games", "requests": 324,
              "lastUsedAt": "2026-08-18T00:00:00.000Z"},
             {"api": "cfb", "endpoint": "/rankings", "requests": 203,
              "lastUsedAt": "2026-08-17T00:00:00.000Z"}],
           "recentRequests": []}
  }', 200, '{"days": "31", "limit": "50"}', '2026-01-01T00:00:22Z', now());

-- Warehouse telemetry, including a failed run: a failure burned warehouse time too,
-- usually more, having paid the cold start before dying.
INSERT INTO raw.raw_warehouse_usage (observed_at, operation, outcome, elapsed_seconds, catalog) VALUES
('2026-01-01T00:00:30Z', 'raw_sync', 'success', 5.9,  'workspace'),
('2026-01-01T00:01:00Z', 'dbt_run',  'success', 78.0, 'workspace'),
('2026-01-01T00:02:30Z', 'dbt_test', 'failed',  12.4, 'workspace');

INSERT INTO raw.raw_manifest (endpoint, filename, params, status_code, row_count, fetched_at, loaded_at) VALUES
('info',       '2026-01-01T00-00-10-001Z.json', '{}', 200, 1, '2026-01-01T00:00:20Z', now()),
('info',       '2026-01-01T00-00-10-002Z.json', '{}', 200, 1, '2026-01-01T00:00:21Z', now()),
('info_usage', '2026-01-01T00-00-11-001Z.json', '{"days": "31", "limit": "50"}', 200, 1, '2026-01-01T00:00:22Z', now());

-- Rankings. Three levels of nesting collapse in stg_rankings, so the fixture carries all
-- three: a week, holding two polls, each holding ranks. Two polls on purpose — the compare
-- view's disagreement spread is zero with one, and a zero can hide an arithmetic error.
INSERT INTO raw.raw_rankings (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-12-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"season": 2024, "week": 1, "seasonType": "regular", "polls": [
      {"poll": "AP Top 25", "isFinal": false, "ranks": [
        {"rank": 1, "teamId": 1, "school": "Alpha State", "conference": "Test Conference",
         "firstPlaceVotes": 40, "points": 1500},
        {"rank": 2, "teamId": 2, "school": "Beta Tech", "conference": "Test Conference",
         "firstPlaceVotes": 2, "points": 1400}]},
      {"poll": "Coaches Poll", "isFinal": false, "ranks": [
        {"rank": 3, "teamId": 1, "school": "Alpha State", "conference": "Test Conference",
         "firstPlaceVotes": 5, "points": 1300}]}
    ]}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:23Z', now());

-- Season stats. `statValue` is anyOf[string, number] in the OpenAPI spec, so the fixture
-- carries one of each: the numeric cast must survive a string without failing the build.
INSERT INTO raw.raw_stats_season (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-13-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"season": 2024, "team": "Alpha State", "conference": "Test Conference",
     "statName": "firstDowns", "statValue": 215},
    {"season": 2024, "team": "Beta Tech", "conference": "Test Conference",
     "statName": "firstDowns", "statValue": 180},
    {"season": 2024, "team": "Alpha State", "conference": "Test Conference",
     "statName": "possessionTime", "statValue": "31:12"}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:24Z', now());

-- dbt's own test outcomes, including a failure: the System Overview page exists to surface
-- failures, so a fixture of nothing but passes would exercise the wrong branch.
INSERT INTO raw.raw_dbt_test_result
  (invocation_id, unique_id, generated_at, dbt_version, status, failures, execution_time, message, relation_name) VALUES
('fixture-invocation-0001', 'test.cfdb_dbt.unique_fct_game_game_sk.abc123',
 '2026-01-01T00:00:25Z', '1.12.0', 'pass', 0, 0.05, NULL, '"cfdb"."marts"."fct_game"'),
('fixture-invocation-0001', 'test.cfdb_dbt.not_null_fct_game_season.def456',
 '2026-01-01T00:00:25Z', '1.12.0', 'fail', 3, 0.07, 'Got 3 results, configured to fail if != 0',
 '"cfdb"."marts"."fct_game"');

INSERT INTO raw.raw_manifest (endpoint, filename, params, status_code, row_count, fetched_at, loaded_at) VALUES
('rankings',     '2026-01-01T00-00-12-001Z.json', '{"year": "2024"}', 200, 1, '2026-01-01T00:00:23Z', now()),
('stats/season', '2026-01-01T00-00-13-001Z.json', '{"year": "2024"}', 200, 3, '2026-01-01T00:00:24Z', now());

-- Model predictions, in the pack's 42-column contract shape.
--
-- The sign convention is the reason these values look backwards and they are correct:
-- margin = away - home, so game 9001 (Alpha 28, Beta 21) has actual_margin = -7 and the
-- HOME team won. A fixture written the intuitive way would make the convention tests pass
-- against wrong data, which is worse than having no fixture at all.
--
-- Row 2 is a week-1 game: the pack trains on regular-season week 5 onward, so this is the
-- out-of-sample case that srv_edge_finder must label rather than render as actionable.
INSERT INTO raw.raw_model_prediction (source_file, model_version, prediction_ts, row_number, payload) VALUES
('linear_margin_predictions.csv', 'fixture00001', '2026-01-01T00:00:40Z', 0, '{
  "game_id": "9001", "season": "2024", "season_type": "regular", "week": "8",
  "home_team": "Alpha State", "away_team": "Beta Tech", "split": "test",
  "home_conference": "Test Conference", "away_conference": "Other Conference",
  "model_name": "linear_margin", "model_family": "linear_regression", "target": "margin",
  "home_points": "28", "away_points": "21", "actual_margin": "-7",
  "actual_total_points": "49", "actual_home_win": "True", "actual_winner": "Alpha State",
  "spread": "-4.5", "actual_home_cover": "True",
  "predicted_home_points": "26.5", "predicted_away_points": "22.1",
  "predicted_margin": "-4.4", "predicted_total_points": "48.6",
  "predicted_home_win_probability": "0.64", "raw_home_win_probability": "0.61",
  "calibrated_home_win_probability": "0.64", "predicted_home_win": "True",
  "predicted_winner": "Alpha State", "predicted_home_cover": "False",
  "market_implied_home_win_probability": "0.60",
  "home_win_probability_edge": "0.04", "home_cover_edge": "-0.1",
  "confidence_bucket": "medium", "margin_error": "2.6", "absolute_margin_error": "2.6",
  "home_win_correct": "True", "cover_correct": "False",
  "brier_score_component": "0.1296", "log_loss_component": "0.4463"}'::jsonb),
('linear_margin_predictions.csv', 'fixture00001', '2026-01-01T00:00:40Z', 1, '{
  "game_id": "9003", "season": "2024", "season_type": "regular", "week": "1",
  "home_team": "Beta Tech", "away_team": "Alpha State", "split": "test",
  "home_conference": "Test Conference", "away_conference": "Test Conference",
  "model_name": "linear_margin", "model_family": "linear_regression", "target": "margin",
  "home_points": "", "away_points": "", "actual_margin": "",
  "actual_total_points": "", "actual_home_win": "", "actual_winner": "",
  "spread": "3.0", "actual_home_cover": "",
  "predicted_home_points": "20.0", "predicted_away_points": "24.0",
  "predicted_margin": "4.0", "predicted_total_points": "44.0",
  "predicted_home_win_probability": "0.43", "raw_home_win_probability": "0.43",
  "calibrated_home_win_probability": "0.43", "predicted_home_win": "False",
  "predicted_winner": "Alpha State", "predicted_home_cover": "False",
  "market_implied_home_win_probability": "0.46",
  "home_win_probability_edge": "-0.03", "home_cover_edge": "-1.0",
  "confidence_bucket": "low", "margin_error": "", "absolute_margin_error": "",
  "home_win_correct": "", "cover_correct": "",
  "brier_score_component": "", "log_loss_component": ""}'::jsonb);

-- Broadcast media. TWO TV rows for one game on purpose: simulcasts are real (ABC and SEC
-- Network carry the same game), and joining them without deduplication multiplied 18 games
-- into two rows each in fct_game — a silent grain break that still built green. The fixture
-- carries the collision so the dedup is exercised rather than assumed.
INSERT INTO raw.raw_games_media (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-14-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"id": 9001, "season": 2024, "week": 1, "seasonType": "regular",
     "mediaType": "tv", "outlet": "ABC"},
    {"id": 9001, "season": 2024, "week": 1, "seasonType": "regular",
     "mediaType": "tv", "outlet": "SEC Network"},
    {"id": 9001, "season": 2024, "week": 1, "seasonType": "regular",
     "mediaType": "web", "outlet": "ESPN+"}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:26Z', now());

INSERT INTO raw.raw_manifest (endpoint, filename, params, status_code, row_count, fetched_at, loaded_at) VALUES
('games_media', '2026-01-01T00-00-14-001Z.json', '{"year": "2024"}', 200, 3, '2026-01-01T00:00:26Z', now());

-- Deploy drift. A STALE row on purpose: the alarm exists because production silently ran
-- old code for a day, so the fixture exercises the escalating branch rather than the
-- reassuring one.
INSERT INTO raw.raw_deploy_status
  (observed_at, deploy_sha, main_sha, commits_behind, severity, detail) VALUES
('2026-01-01T00:00:50Z', 'aaaa111', 'bbbb222', 7, 'error',
 'Deploy tree is 7 commits behind main (aaaa111 vs bbbb222). Airflow is running old code');

-- The five rating systems (B1).
--
-- SP+ carries a `nationalAverages` row, which is what CFBD actually returns and is NOT a
-- team. Left in, it would appear on the Teams index, get a team page, and sit in the
-- percentile denominator shifting every team's standing by an amount nobody would trace.
-- The fixture carries it so the exclusion is exercised rather than assumed.
--
-- 2024 ratings are MEASURED (the fixture's 2024 games are completed); the 2026 SP+ row is a
-- PROJECTION, because no 2026 game exists. Both branches of is_projection therefore run on
-- every build — which matters because in weeks 1 to 4 the projection branch is the only one
-- with any rows at all.
INSERT INTO raw.raw_ratings_sp (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-20-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "year": 2024,
   "team": "Alpha State",
   "conference": "Test Conference",
   "rating": 18.4,
   "ranking": 1,
   "secondOrderWins": 9.2,
   "sos": 0.61,
   "offense": {
    "ranking": 1,
    "rating": 34.1,
    "success": 0.44,
    "explosiveness": 1.21,
    "rushing": 3.1,
    "passing": 4.2,
    "standardDowns": 0.51,
    "passingDowns": 0.33,
    "runRate": 0.58,
    "pace": 27.4
   },
   "defense": {
    "ranking": 6,
    "rating": 39.1,
    "success": 0.49,
    "explosiveness": 1.71,
    "rushing": 3.6,
    "passing": 4.7,
    "standardDowns": 0.56,
    "passingDowns": 0.38,
    "havoc": {
     "total": 0.23,
     "frontSeven": 0.16,
     "db": 0.12
    }
   },
   "specialTeams": {
    "rating": 0.4
   }
  },
  {
   "year": 2024,
   "team": "Beta Tech",
   "conference": "Test Conference",
   "rating": 20.4,
   "ranking": 3,
   "secondOrderWins": 11.2,
   "sos": 0.63,
   "offense": {
    "ranking": 3,
    "rating": 36.1,
    "success": 0.46,
    "explosiveness": 1.41,
    "rushing": 3.3,
    "passing": 4.4,
    "standardDowns": 0.53,
    "passingDowns": 0.35,
    "runRate": 0.6,
    "pace": 29.4
   },
   "defense": {
    "ranking": 8,
    "rating": 41.1,
    "success": 0.51,
    "explosiveness": 1.91,
    "rushing": 3.8,
    "passing": 4.9,
    "standardDowns": 0.58,
    "passingDowns": 0.4,
    "havoc": {
     "total": 0.25,
     "frontSeven": 0.18,
     "db": 0.14
    }
   },
   "specialTeams": {
    "rating": 0.6
   }
  },
  {
   "year": 2024,
   "team": "nationalAverages",
   "conference": null,
   "rating": 10.8,
   "ranking": null,
   "secondOrderWins": null,
   "sos": null,
   "offense": {
    "ranking": 2,
    "rating": 35.1,
    "success": 0.45,
    "explosiveness": 1.31,
    "rushing": 3.2,
    "passing": 4.3,
    "standardDowns": 0.52,
    "passingDowns": 0.34,
    "runRate": 0.59,
    "pace": 28.4
   },
   "defense": {
    "ranking": 7,
    "rating": 40.1,
    "success": 0.5,
    "explosiveness": 1.81,
    "rushing": 3.7,
    "passing": 4.8,
    "standardDowns": 0.57,
    "passingDowns": 0.39,
    "havoc": {
     "total": 0.24,
     "frontSeven": 0.17,
     "db": 0.13
    }
   },
   "specialTeams": {
    "rating": 0.0
   }
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:31Z', now());

INSERT INTO raw.raw_ratings_srs (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-21-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"year": 2024, "team": "Alpha State", "conference": "Test Conference",
     "division": null, "rating": 11.1, "ranking": 1},
    {"year": 2024, "team": "Beta Tech", "conference": "Test Conference",
     "division": null, "rating": -2.4, "ranking": 2},
    {"year": 2024, "team": "Beta Tech", "conference": null,
     "division": null, "rating": -2.4, "ranking": 2}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:32Z', now());
-- The second Beta Tech row is NOT a typo. CFBD's /ratings/srs returns some schools twice —
-- once with a conference and once with `conference: null`, carrying an IDENTICAL rating.
-- Charlotte in 2024 and 2025, Troy in 2024. The rating is the same on both copies, so no
-- average moves and no value looks wrong; what moves is every count and every percentile
-- denominator. The fixture keeps the duplicate alive so the dedup runs on every build.

INSERT INTO raw.raw_ratings_elo (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-22-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"year": 2024, "team": "Alpha State", "conference": "Test Conference", "elo": 1712},
    {"year": 2024, "team": "Beta Tech", "conference": "Test Conference", "elo": 1489}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:33Z', now());

INSERT INTO raw.raw_ratings_fpi (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-23-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "year": 2024,
   "team": "Alpha State",
   "conference": "Test Conference",
   "fpi": 14.2,
   "resumeRanks": {
    "strengthOfRecord": 3,
    "fpi": 2,
    "averageWinProbability": 5,
    "strengthOfSchedule": 41,
    "remainingStrengthOfSchedule": null,
    "gameControl": 4
   },
   "efficiencies": {
    "overall": 58.9,
    "offense": 62.1,
    "defense": 71.3,
    "specialTeams": 50.2
   }
  },
  {
   "year": 2024,
   "team": "Beta Tech",
   "conference": "Test Conference",
   "fpi": 1.9,
   "resumeRanks": {
    "strengthOfRecord": 44,
    "fpi": 51,
    "averageWinProbability": 47,
    "strengthOfSchedule": 60,
    "remainingStrengthOfSchedule": null,
    "gameControl": 49
   },
   "efficiencies": {
    "overall": 49.6,
    "offense": 48.0,
    "defense": 52.5,
    "specialTeams": 49.1
   }
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:34Z', now());

INSERT INTO raw.raw_ratings_sp_conferences (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-24-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "year": 2024,
   "conference": "Test Conference",
   "rating": 5.04,
   "secondOrderWins": null,
   "sos": null,
   "offense": {
    "rating": 34.1,
    "success": 0.44,
    "explosiveness": 1.21,
    "rushing": 3.1,
    "passing": 4.2,
    "standardDowns": 0.51,
    "passingDowns": 0.33,
    "runRate": 0.58,
    "pace": 27.4
   },
   "defense": {
    "rating": 39.1,
    "success": 0.49,
    "explosiveness": 1.71,
    "rushing": 3.6,
    "passing": 4.7,
    "standardDowns": 0.56,
    "passingDowns": 0.38,
    "havoc": {
     "total": 0.23,
     "frontSeven": 0.16,
     "db": 0.12
    }
   },
   "specialTeams": {
    "rating": 0.15
   }
  },
  {
   "year": 2024,
   "conference": "Other Conference",
   "rating": 8.04,
   "secondOrderWins": null,
   "sos": null,
   "offense": {
    "rating": 37.1,
    "success": 0.47,
    "explosiveness": 1.51,
    "rushing": 3.4,
    "passing": 4.5,
    "standardDowns": 0.54,
    "passingDowns": 0.36,
    "runRate": 0.61,
    "pace": 30.4
   },
   "defense": {
    "rating": 42.1,
    "success": 0.52,
    "explosiveness": 2.01,
    "rushing": 3.9,
    "passing": 5.0,
    "standardDowns": 0.59,
    "passingDowns": 0.41,
    "havoc": {
     "total": 0.26,
     "frontSeven": 0.19,
     "db": 0.15
    }
   },
   "specialTeams": {
    "rating": 0.45
   }
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:35Z', now());

INSERT INTO raw.raw_ratings_srs_expanded (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-25-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "year": 2024,
   "team": "Alpha State",
   "classification": "fbs",
   "conference": "Test Conference",
   "division": null,
   "ranking": 1,
   "rating": 11.1
  },
  {
   "year": 2024,
   "team": "Beta Tech",
   "classification": "fbs",
   "conference": "Test Conference",
   "division": null,
   "ranking": 2,
   "rating": -2.4
  },
  {
   "year": 2024,
   "team": "Gamma College",
   "classification": "fcs",
   "conference": null,
   "division": null,
   "ranking": 88,
   "rating": -14.7
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:36Z', now());

INSERT INTO raw.raw_ratings_core (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-26-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "year": 2024,
   "throughSeasonType": "regular",
   "throughWeek": 12,
   "team": "Alpha State",
   "conference": "Test Conference",
   "overall": 30.1,
   "offense": 18.0,
   "defense": -12.1,
   "offensePlays": 790,
   "defensePlays": 770,
   "modelVersion": "core-v1"
  },
  {
   "year": 2024,
   "throughSeasonType": "postseason",
   "throughWeek": 1,
   "team": "Alpha State",
   "conference": "Test Conference",
   "overall": 37.25,
   "offense": 22.01,
   "defense": -15.24,
   "offensePlays": 836,
   "defensePlays": 813,
   "modelVersion": "core-v1"
  },
  {
   "year": 2024,
   "throughSeasonType": "postseason",
   "throughWeek": 1,
   "team": "Beta Tech",
   "conference": "Test Conference",
   "overall": 8.4,
   "offense": 4.1,
   "defense": -4.3,
   "offensePlays": 801,
   "defensePlays": 812,
   "modelVersion": "core-v1"
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:37Z', now());

INSERT INTO raw.raw_ppa_teams (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-27-001Z.json', '{
 "status_code": 200,
 "params": {
  "year": "2024"
 },
 "data": [
  {
   "season": 2024,
   "conference": "Test Conference",
   "team": "Alpha State",
   "offense": {
    "overall": 0.13,
    "passing": 0.08,
    "rushing": 0.15,
    "firstDown": -0.06,
    "secondDown": 0.02,
    "thirdDown": 0.43,
    "cumulative": {
     "total": 104.5,
     "passing": 12.36,
     "rushing": 95.5
    }
   },
   "defense": {
    "overall": 0.43,
    "passing": 0.38,
    "rushing": 0.45,
    "firstDown": 0.24,
    "secondDown": 0.32,
    "thirdDown": 0.73,
    "cumulative": {
     "total": 107.5,
     "passing": 15.36,
     "rushing": 98.5
    }
   }
  },
  {
   "season": 2024,
   "conference": "Test Conference",
   "team": "Beta Tech",
   "offense": {
    "overall": 0.23,
    "passing": 0.18,
    "rushing": 0.25,
    "firstDown": 0.04,
    "secondDown": 0.12,
    "thirdDown": 0.53,
    "cumulative": {
     "total": 105.5,
     "passing": 13.36,
     "rushing": 96.5
    }
   },
   "defense": {
    "overall": 0.53,
    "passing": 0.48,
    "rushing": 0.55,
    "firstDown": 0.34,
    "secondDown": 0.42,
    "thirdDown": 0.83,
    "cumulative": {
     "total": 108.5,
     "passing": 16.36,
     "rushing": 99.5
    }
   }
  }
 ]
}', 200, '{"year": "2024"}',
  '2026-01-01T00:00:38Z', now());
