{{ config(tags=['full_refresh_only']) }}
-- TAGGED `full_refresh_only`: excluded from cfbd_scores_refresh, which rebuilds `dim_team` and
-- NOT `srv_player_game_log`, so mid-refresh the two sides of this comparison are from different
-- builds and the test would fail on a legitimate state. Full authority on the weekly
-- +tag:production build, which rebuilds both. See dags/scores_refresh_dag.py TEST_EXCLUDE.
--
-- 🚨 THE STRADDLE GUARD FOUND THIS, NOT ME. `test_no_test_straddles_the_gated_dags_refresh_boundary`
-- read the manifest and named the pair. ⚠️ And the risk it describes is real but currently
-- invisible in the data — 0 of 775 teams change colour between seasons — which is exactly why a
-- structural guard beats an eyeball: the failure would have arrived on the first team that did.
--
-- A177 (cfdb-main-R-1767). The colour pair on the player game log must be the SAME pair
-- `dim_team` publishes for that team and season — the whole point of carrying it here rather
-- than inventing a second source.
--
-- 🚨 A NULL-RATE BOUND WOULD NOT CATCH THE FAILURE THIS GUARDS: the colour arriving from the
-- WRONG TEAM. The join carries a team id, and a row on this relation has two of them
-- (`team_id` and `opponent_team_id`) sitting four lines apart. Keyed on the wrong one the
-- column is 100% populated, every value is a real published colour, and every player on the
-- page wears the other side's kit.
--
-- ⚠️ AND THE BREAK THAT DOES **NOT** PROVE THIS WAS MEASURED, because an earlier draft of this
-- comment asserted it did. Dropping `season` from the join is a real defect — it fans the join
-- out — but it cannot be caught HERE: 📊 **0 of 775 teams in `dim_team` carry more than one
-- on-light colour across seasons**, so a wrong-season colour is the same string as the right
-- one and this test stays green. A uniqueness test is what sees that one. R-843's rule applied
-- to a guard's own prose: the value has to MOVE under the break you claim it catches.
--
-- ⚠️ INNER JOIN ON PURPOSE. 0.2-0.8% of player-game rows have no `dim_team` row for that
-- season and carry null colours; that absence is published and documented, and asserting on it
-- here would make this test fire on a known, handled state instead of on a broken join.
select
    l.player_game_stat_sk,
    l.season,
    l.team_id,
    l.color_on_light  as log_light,
    d.color_on_light  as team_light,
    l.color_on_dark   as log_dark,
    d.color_on_dark   as team_dark
from {{ ref('srv_player_game_log') }} l
join {{ ref('dim_team') }} d
  on d.season = l.season and d.team_id = l.team_id
where l.color_on_light is distinct from d.color_on_light
   or l.color_on_dark  is distinct from d.color_on_dark
