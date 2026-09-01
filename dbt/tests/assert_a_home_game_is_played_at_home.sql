-- A non-neutral home game should be played at the team's own venue, so travel is ~0.
--
-- This is the internal consistency check on a DERIVED value. fct_game_travel has no
-- "this team's stadium" field to read — CFBD publishes none — so a team's home venue is the
-- venue it played most of its non-neutral home games at. Where that derivation is right, a
-- home game's travel_km is zero by construction. Where it is wrong, this fires.
--
-- SEVERITY IS WARN, AND THE CURRENT COUNT IS 19 OF 221,758.
--
-- Every one is a small non-FBS programme — Mary Hardin Baylor, Trinity (TX), Linfield — where
-- weather covers only one or two home games, so the "mode" is computed from a sample of one
-- and can land on an away venue. That is a coverage limit rather than a modelling error, and
-- there is no fix available inside this repo: the input simply is not there.
--
-- The test earns its keep as a growth detector. Nineteen rows concentrated in Division III is
-- the known shape; the same test reading several hundred, or naming an FBS programme, would
-- mean the home-venue derivation had genuinely broken and every travel figure for that team
-- was measured from the wrong origin.
{{ config(severity='warn') }}

select team, season, week, opponent, game_venue, travel_km
from {{ ref('fct_game_travel') }}
where is_home
  and not is_neutral_site
  and travel_km > 1
