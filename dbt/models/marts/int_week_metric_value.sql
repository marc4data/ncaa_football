{{ config(materialized='table') }}

-- ONE GAME'S CONTRIBUTION TO ONE METRIC, AS OF TODAY. Long: one row per (game, metric).
--
-- ONE DEFINITION, TWO CONSUMERS. The distribution summary and its bin counts both need these
-- values, and computing them twice would be two definitions of one metric — the defect this
-- project has spent two rounds removing from the upset thresholds.
--
-- ⚠ A TABLE, AND IT USED TO BE A VIEW. THE VIEW BROKE THE PIPELINE EVERY TWO HOURS.
--
-- The reasoning below is still why this is not EPHEMERAL. What it missed is that a view has
-- a live dependency on its parents, and dbt's Postgres view materialisation ends with
--
--     drop view if exists <relation>__dbt_backup cascade
--
-- (`dbt/include/postgres/macros/relations/view/drop.sql`). Rebuilding a parent renames the
-- old relation to `__dbt_backup`, Postgres follows the rename on every dependent, and the
-- CASCADE then takes the dependents with it.
--
-- This model reads `fct_game_market`, which is a view, and which `cfbd_scores_refresh`
-- rebuilds every two hours as an ancestor of `+srv_game`. So every scores refresh silently
-- DROPPED this model, and the next `cfbd_lines_snapshot` failed on `dbt test` with the exact
-- error quoted below — after its own `dbt run` had created the model twenty minutes earlier.
-- Four consecutive lines runs failed that way on 2026-09-04, taking `publish_distributions`
-- with them and holding the dead-man's switch red.
--
-- A table has no dependency to cascade through: the rows are copied at build time. It costs
-- storage for 110k x 6 rows, which is the price of the model surviving its own parent being
-- rebuilt. Two DAGs touching one lineage is the normal case here, not the exception.
--
-- Ephemeral remains wrong for the original reason: it inlines cleanly but has no relation,
-- and dbt unit tests cannot introspect columns for a model that does not exist:
--
--     Not able to get columns for unit test 'int_week_metric_value' ...
--     because the relation doesn't exist
--
-- The bin model has one edge real data does not exercise — a value sitting exactly on
-- bin_max — and a unit test is the only way to prove it. A view costs nothing and makes the
-- test possible, which is a better trade than a defensive branch nobody can verify.
--
-- Layering is unaffected: `ci/check_layering.py` reads the layer from the PATH, so this is a
-- mart depending on marts.

{% set metrics = var('distribution_bins').keys() | list %}

with as_of as (
    select cast({{ dbt.current_timestamp() }} as date) as as_of_date
),

games as (
    select
        g.game_id, g.season, g.season_type, g.week,
        a.as_of_date,
        -- THE LOCK RULE, IN ONE PLACE. Kickoff is per GAME, so a game contributes its CLOSING
        -- number once it has started and its LIVE number before that. A week's row is
        -- therefore a mixture until the last game kicks off, which is the honest reading of
        -- "re-calc each day until kick-off then it's locked".
        g.start_date <= a.as_of_date + interval '1 day'          as has_kicked,
        case when g.start_date <= a.as_of_date + interval '1 day'
             then coalesce(c.spread_at_close, c.spread_current)
             else c.spread_current end                            as spread,
        case when g.start_date <= a.as_of_date + interval '1 day'
             then coalesce(c.total_at_close, c.total_current)
             else c.total_current end                             as total,
        w.temperature_f,
        w.is_indoors
    from {{ ref('fct_game') }} g
    -- The closing line, from the model that owns that rule. Extracted out of srv_game for
    -- exactly this: a mart cannot read a serving view, and copying the logic down a layer
    -- would have been a third implementation of one definition.
    left join {{ ref('fct_game_market') }} c on c.game_id = g.game_id
    left join {{ ref('fct_game_weather') }} w on w.game_id = g.game_id
    cross join as_of a
    -- FBS ONLY, and EITHER team FBS rather than both. That is the site's spine rule and what
    -- the Division filter means at its FBS setting, so a distribution built the other way
    -- would disagree with the games listed under it on the very page that shows it.
    -- The spine rule, spelled the way srv_game spells it (srv_game.sql:259) rather than
    -- read from a column that only exists downstream.
    where (g.home_classification = 'fbs' or g.away_classification = 'fbs')
),

valued as (
    select
        game_id, season, season_type, week, as_of_date, has_kicked, is_indoors,
        spread,
        abs(spread)                                              as spread_abs,
        total,
        -- THE SIGN DOES THE WORK — no favourite/underdog branch here or anywhere else.
        -- Verified on 1,930 games: implied_home + implied_away = total on every row, and
        -- greatest/least of the pair equals the abs() form on every row.
        greatest((total - spread) / 2.0, (total + spread) / 2.0) as market_implied_favorite_points,
        least((total - spread) / 2.0, (total + spread) / 2.0)    as market_implied_underdog_points,
        -- TEMPERATURE EXCLUDES INDOOR GAMES, and this is not a judgement call: CFBD reports
        -- conditions at the venue's LOCATION, not inside it, so a domed game carries ordinary
        -- outdoor readings. `fct_game_weather` says so in its own header. Including them puts
        -- a number in the distribution that is true about the car park.
        case when is_indoors is not true then temperature_f end  as temperature_f
    from games
)

{% for metric in metrics %}
select
    game_id, season, season_type, week, as_of_date, has_kicked, is_indoors,
    cast('{{ metric }}' as {{ dbt.type_string() }}) as metric,
    cast({{ metric }} as numeric)                   as value
from valued
{% if not loop.last %}union all{% endif %}
{% endfor %}
