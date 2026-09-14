{#
  R-723. The three KPI slots on a player card, as twelve columns, for EITHER window.

  🚨 ONE MACRO BECAUSE THERE ARE NOW TWO CARDS AND THE RULE IS ONE RULE. A116 shipped these slots
  on the PREVIEW view — who leads the team going INTO this game — and A120 adds the POST-GAME twin,
  who led IN it. Same panels, same labels, same formats, different figures. A second copy of the
  `case panel when ...` expressions is precisely the drift this project has paid for four times in
  two weeks: B098's `metric`, B099's `_CARD_KPIS`, B100's two renderers, and the labels A116 moved
  into data to stop exactly this.

  ✅ A119's `matchup_outlook(gained, allowed)` is the pattern, one day older: the rule is identical
  across call sites and the thing that would drift is what the macro owns.

  ⚠️ THE TWO VIEWS READ DIFFERENT COLUMNS, so the macro takes COLUMN EXPRESSIONS rather than a
  table alias. The preview passes `l.receptions_through_prior_week`; the post-game twin passes its
  own per-game figure. The macro decides WHICH SLOT and WHAT IT IS CALLED, never where the number
  comes from.

  ⚠️ ARGUMENTS ARE INTERPOLATED SQL. Model code with trusted literals only, never reader input.

  ⚠️ AND IT MUST EMIT THE COLUMNS IN THE ORDER AND WITH THE NAMES A116 ALREADY PUBLISHED. The
  preview view is read by site/views/matchup.py today, so this refactor is §3.3's EXPAND with no
  MIGRATE: the expression moves, the column names and values do not. A120 proved that by diffing
  the view's output row-for-row before and after.

  panel        the column expression naming the panel ('passing' | 'rushing' | 'total')
  receptions   passing panel, slot 1
  carries      rushing panel, slot 1
  completions  total panel, slot 1 (paired with attempts)
  attempts     total panel, slot 1 secondary
  yards        every panel, slot 2 — the figure the ranking comes from
  touchdowns   passing and total panels, slot 3
  yards_per_carry  rushing panel, slot 3
#}
{% macro player_card_slots(panel, receptions, carries, completions, attempts,
                           yards, touchdowns, yards_per_carry) %}
    -- SLOT 1
    case {{ panel }} when 'passing' then 'Receptions'
                     when 'rushing' then 'Carries'
                     when 'total'   then 'Comp-Att'
    end as stat_1_label,
    case {{ panel }} when 'passing' then {{ receptions }}
                     when 'rushing' then {{ carries }}
                     when 'total'   then {{ completions }}
    end as stat_1_value,
    case {{ panel }} when 'total'   then {{ attempts }}
    end as stat_1_value_secondary,
    case {{ panel }} when 'total'   then 'pair' else 'integer'
    end as stat_1_format,
    -- SLOT 2 — the yards every panel ranks on, in the middle, so the number the ordering comes
    -- from sits where a reader looks first.
    'Yards'        as stat_2_label,
    {{ yards }}    as stat_2_value,
    null::numeric  as stat_2_value_secondary,
    'integer'      as stat_2_format,
    -- SLOT 3
    case {{ panel }} when 'passing' then 'TD'
                     when 'rushing' then 'Yds/Carry'
                     when 'total'   then 'TD'
    end as stat_3_label,
    case {{ panel }} when 'rushing' then {{ yards_per_carry }}
                     else {{ touchdowns }}
    end as stat_3_value,
    null::numeric as stat_3_value_secondary,
    case {{ panel }} when 'rushing' then 'decimal_1' else 'integer'
    end as stat_3_format
{% endmacro %}
