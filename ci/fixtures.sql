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
CREATE TABLE IF NOT EXISTS raw.raw_ppa_teams (
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
         raw.raw_games_players, raw.raw_games_weather,
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

INSERT INTO raw.raw_records (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-07-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"year": 2024, "teamId": 1, "team": "Alpha State", "classification": "fbs",
     "total": {"games": 3, "wins": 2, "losses": 0, "ties": 1}},
    {"year": 2024, "teamId": 2, "team": "Beta Tech", "classification": "fbs",
     "total": {"games": 2, "wins": 0, "losses": 1, "ties": 1}},
    {"year": 2024, "teamId": 77, "team": "Gamma College", "classification": "ii",
     "total": {"games": 1, "wins": 0, "losses": 1, "ties": 0}}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:09Z', now()),
-- The legitimately-empty response already in the manifest. An endpoint that returns no rows
-- is not a failure, and nothing downstream may treat it as one.
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
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"year": 2024, "team": "Alpha State", "conference": "Test Conference", "rating": 18.4,
     "ranking": 1, "offense": {"rating": 34.1}, "defense": {"rating": 15.7},
     "specialTeams": {"rating": 0.4}, "sos": 0.61, "secondOrderWins": 9.2},
    {"year": 2024, "team": "Beta Tech", "conference": "Test Conference", "rating": 3.2,
     "ranking": 2, "offense": {"rating": 27.0}, "defense": {"rating": 23.8},
     "specialTeams": {"rating": -0.2}, "sos": 0.55, "secondOrderWins": 6.1},
    {"year": 2024, "team": "nationalAverages", "conference": null, "rating": 10.8,
     "ranking": null, "offense": {"rating": 30.5}, "defense": {"rating": 19.7},
     "specialTeams": {"rating": 0.0}, "sos": null, "secondOrderWins": null}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:30Z', now()),
('2026-01-01T00-00-20-002Z.json', '{
  "status_code": 200, "params": {"year": "2026"},
  "data": [
    {"year": 2026, "team": "Alpha State", "conference": "Test Conference", "rating": 12.0,
     "ranking": 1, "offense": {"rating": 31.0}, "defense": {"rating": 19.0},
     "specialTeams": {"rating": 0.1}, "sos": 0.50, "secondOrderWins": 8.0}
  ]}', 200, '{"year": "2026"}', '2026-01-01T00:00:31Z', now());

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
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"year": 2024, "team": "Alpha State", "conference": "Test Conference", "fpi": 14.2,
     "efficiencies": {"offense": 62.1, "defense": 71.3, "specialTeams": 50.2}},
    {"year": 2024, "team": "Beta Tech", "conference": "Test Conference", "fpi": 1.9,
     "efficiencies": {"offense": 48.0, "defense": 52.5, "specialTeams": 49.1}}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:34Z', now());

INSERT INTO raw.raw_ppa_teams (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-24-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"season": 2024, "team": "Alpha State", "conference": "Test Conference",
     "offense": {"overall": 0.31}, "defense": {"overall": 0.05}},
    {"season": 2024, "team": "Beta Tech", "conference": "Test Conference",
     "offense": {"overall": 0.12}, "defense": {"overall": 0.22}}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:35Z', now());
