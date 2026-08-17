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
CREATE TABLE IF NOT EXISTS raw.raw_manifest (
    endpoint text NOT NULL, filename text NOT NULL, params jsonb, status_code int,
    row_count int, fetched_at timestamptz, loaded_at timestamptz,
    PRIMARY KEY (endpoint, filename)
);

TRUNCATE raw.raw_teams, raw.raw_games, raw.raw_manifest;

-- Teams, season-scoped. Only year-parameterized fetches feed stg_teams.
INSERT INTO raw.raw_teams (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-00-001Z.json', '{
  "status_code": 200, "params": {"year": "2024"},
  "data": [
    {"id": 1, "school": "Alpha State", "mascot": "Ones", "abbreviation": "ALP",
     "conference": "Test Conference", "division": null, "classification": "fbs",
     "location": {"city": "Alphaville", "state": "AA"}},
    {"id": 2, "school": "Beta Tech", "mascot": "Twos", "abbreviation": "BET",
     "conference": "Test Conference", "division": null, "classification": "fbs",
     "location": {"city": "Betaburg", "state": "BB"}}
  ]}', 200, '{"year": "2024"}', '2026-01-01T00:00:00Z', now()),
('2026-01-01T00-00-00-002Z.json', '{
  "status_code": 200, "params": {"year": "1900"},
  "data": [
    {"id": 1, "school": "Alpha State", "mascot": "Ones", "abbreviation": "ALP",
     "conference": "Old Conference", "division": null, "classification": "fbs",
     "location": {"city": "Alphaville", "state": "AA"}},
    {"id": 2, "school": "Beta Tech", "mascot": "Twos", "abbreviation": "BET",
     "conference": "Old Conference", "division": null, "classification": "fbs",
     "location": {"city": "Betaburg", "state": "BB"}}
  ]}', 200, '{"year": "1900"}', '2026-01-01T00:00:00Z', now()),
-- A failed fetch, landed as the raw layer always does. Staging must filter it out.
('2026-01-01T00-00-00-003Z.json', '{"status_code": 401, "params": {"year": "2024"}, "data": null}',
 401, '{"year": "2024"}', '2026-01-01T00:00:01Z', now());

-- Games. One completed matchup per season, so every reconciliation test has something to
-- reconcile: each game contributes exactly one win and one loss.
INSERT INTO raw.raw_games (filename, content, status_code, params, fetched_at, added_at) VALUES
('2026-01-01T00-00-01-001Z.json', '{
  "status_code": 200, "params": {"year": "2024", "seasonType": "regular"},
  "data": [
    {"id": 9001, "season": 2024, "week": 1, "seasonType": "regular",
     "startDate": "2024-09-07T23:30:00.000Z", "completed": true, "conferenceGame": true,
     "neutralSite": false, "homeId": 1, "homeTeam": "Alpha State", "homePoints": 28,
     "homeClassification": "fbs", "awayId": 2, "awayTeam": "Beta Tech", "awayPoints": 21,
     "awayClassification": "fbs", "venue": "Alpha Field", "attendance": 50000}
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
('games', '2026-01-01T00-00-01-001Z.json', '{"year": "2024", "seasonType": "regular"}', 200, 1, '2026-01-01T00:00:02Z', now()),
('games', '2026-01-01T00-00-01-002Z.json', '{"year": "1900", "seasonType": "regular"}', 200, 1, '2026-01-01T00:00:03Z', now()),
-- An endpoint that has never returned rows: legitimately empty, must not read as a loss.
('records', '2026-01-01T00-00-02-001Z.json', '{"year": "2026"}', 200, 0, '2026-01-01T00:00:04Z', now());
