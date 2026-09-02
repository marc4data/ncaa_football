{#
  A team's display name and slug, from the dimension where it exists and from the fact
  where it does not.

  THE DIMENSION DOES NOT COVER THE FACT'S KEY SPACE, and this is the rule worth writing
  down rather than patching one view at a time:

    /games is the authority on WHO PLAYED.
    /teams is the authority on WHO IS AN FBS PROGRAM.

  Those are different sets and the fact's is larger. A Division II visitor is legitimately
  in the first and legitimately absent from the second, so dim_team has no row for it —
  which is correct behaviour by dim_team and a trap for anything joining to it for a name.

  Measured, after the first instance was found on srv_game and swept for:

    srv_game      12,168 of 110,634    11.0%
    srv_team_game_log   12,552 of 221,268     5.7%
    srv_standings        7,482 of  30,475    24.6%
    srv_rankings           662 of  49,798     1.3%
    srv_today_edges            9 of     211     4.3%   <- the landing page

  Five views, four of them found only because the first one was swept for rather than
  fixed. A null display name renders as an em dash where a team should be; a null slug is
  a link to nowhere, which is worse than a row that was never clickable.

  The fallback slug resolves to a team page that honestly renders Empty. A team with no
  dim_team row genuinely has no season record, and Empty is the true answer.

  Args:
    dim_alias   the dim_team alias in the query
    fact_name   SQL expression for the name on the FACT side, which is never null
    prefix      column-name prefix, e.g. 'home_' — omit for an unprefixed pair
#}
{% macro team_identity(dim_alias, fact_name, prefix='') -%}
    coalesce({{ dim_alias }}.team_slug, {{ to_slug(fact_name) }})
        as {{ prefix }}team_slug,
    coalesce({{ dim_alias }}.team_display, {{ fact_name }})
        as {{ prefix }}team_display
{%- endmacro %}
