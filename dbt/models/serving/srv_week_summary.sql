-- THE KPI ROW'S ONE ROW. Everything the summary strip above Most Exciting needs, flattened so
-- the page reads a single relation in a single pass (G-2) with no arithmetic of its own.
--
-- 🚨 IT CARRIES EVERY DENOMINATOR, NOT JUST THE RATES. A216 will want to write "62% of
-- favorites covered" and a reader will want to know 62% of what — and the page cannot compute
-- it later from a rate alone. `fct_week_summary` explains why each one exists.
--
-- ⚠️ NAMING: these are the book's raw numbers and the outcomes they produced, so they take no
-- provenance prefix. `predicted_*` is reserved for this project's own model output and
-- `market_implied_*` for quantities DERIVED from a line — the licence boundary wearing a naming
-- convention (§4.3). A mean of published closing totals is neither.
select
    season,
    season_type,
    week,

    fbs_games,
    fbs_games_completed,

    over_under_mean,
    over_under_games,
    over_under_missing,

    favorite_straight_up_wins,
    favorite_straight_up_games,
    favorite_straight_up_pickems,
    favorite_straight_up_no_line,
    favorite_straight_up_rate,

    favorite_ats_covers,
    favorite_ats_games,
    favorite_ats_pushes,
    favorite_ats_no_line,
    favorite_ats_rate,

    overs,
    over_under_decided_games,
    total_pushes,
    total_no_line,
    over_rate,

    winning_points_mean,
    losing_points_mean,

    undefeated_teams_lost,
    undefeated_teams_entering
from {{ ref('fct_week_summary') }}
