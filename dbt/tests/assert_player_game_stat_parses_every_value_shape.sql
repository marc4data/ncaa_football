-- Every box-score value must be either parsed or knowingly unparsed.
--
-- Three shapes exist in the source and each has a destination: a plain number goes to
-- stat_value, a made/attempted pair splits into stat_made and stat_attempted, and the
-- literal "--" (passing QBR, not computed) parses to nothing by design.
--
-- The failure this guards is a FOURTH shape arriving upstream and landing nowhere — a row
-- with a raw value, no parsed value, and no reason. That is indistinguishable from a genuine
-- absence unless something asserts the difference, which is why "--" is named explicitly
-- rather than lumped in with "anything we could not parse".
select game_id, player_id, stat_category, stat_type, stat_raw
from {{ ref('fct_player_game_stat') }}
where stat_value is null
  and stat_made is null
  and stat_raw is not null
  and stat_raw <> '--'
