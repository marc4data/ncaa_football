{#
  WCAG contrast helpers for team identity colours.

  Team colour is identity chrome, never a data encoding (cfdb_team_identity_spec.md D1), but
  chrome still has to be legible: a swatch or left rule must clear 3:1 against the surface it
  sits on. Some schools are near-white and some near-black, so one of the two theme surfaces
  always fails for part of the long tail.

  The arithmetic lives here rather than in the app because Streamlit is display-only, and
  because a value that can be unreadable is a data defect, not a rendering accident.

  TRAP: CFBD returns the literal string '#null' for a missing colour, not JSON null. Parsing
  that as hex yields garbage. `clean_hex` is the only thing that should ever feed the rest.
#}

{% macro clean_hex(col) -%}
    nullif(nullif(lower(trim({{ col }})), '#null'), '')
{%- endmacro %}


{# --- one channel of a #rrggbb string as an integer 0-255 ------------------------------ #}
{% macro hex_channel(col, start) -%}
    {{ return(adapter.dispatch('hex_channel', 'cfdb_dbt')(col, start)) }}
{%- endmacro %}

{% macro default__hex_channel(col, start) -%}
    ('x' || substr({{ col }}, {{ start }}, 2))::bit(8)::int
{%- endmacro %}

{% macro databricks__hex_channel(col, start) -%}
    cast(conv(substr({{ col }}, {{ start }}, 2), 16, 10) as int)
{%- endmacro %}


{# --- WCAG relative luminance of a #rrggbb string ------------------------------------- #}
{% macro relative_luminance(col) -%}
(
    0.2126 * {{ cfdb_dbt.channel_linear(col, 2) }}
  + 0.7152 * {{ cfdb_dbt.channel_linear(col, 4) }}
  + 0.0722 * {{ cfdb_dbt.channel_linear(col, 6) }}
)
{%- endmacro %}

{% macro channel_linear(col, start) -%}
(
    case
        when {{ hex_channel(col, start) }} / 255.0 <= 0.03928
            then ({{ hex_channel(col, start) }} / 255.0) / 12.92
        else power((({{ hex_channel(col, start) }} / 255.0) + 0.055) / 1.055, 2.4)
    end
)
{%- endmacro %}


{# --- contrast ratio of a colour against a surface of known luminance ------------------ #}
{% macro contrast_vs(col, surface_luminance) -%}
(
    case
        when {{ relative_luminance(col) }} > {{ surface_luminance }}
            then ({{ relative_luminance(col) }} + 0.05) / ({{ surface_luminance }} + 0.05)
        else ({{ surface_luminance }} + 0.05) / ({{ relative_luminance(col) }} + 0.05)
    end
)
{%- endmacro %}


{# --- blend a colour toward black (0) or white (255) by `factor` ----------------------
  Hue is not preserved exactly — a linear blend toward black or white shifts saturation —
  but it stays far closer to the brand colour than any palette substitution, and the
  alternative (leaving it unreadable) serves nobody.
#}
{% macro blend_hex(col, toward, factor) -%}
    {{ return(adapter.dispatch('blend_hex', 'cfdb_dbt')(col, toward, factor)) }}
{%- endmacro %}

{% macro default__blend_hex(col, toward, factor) -%}
(
    '#'
    || lpad(to_hex(round({{ hex_channel(col, 2) }} + ({{ toward }} - {{ hex_channel(col, 2) }}) * {{ factor }})::int), 2, '0')
    || lpad(to_hex(round({{ hex_channel(col, 4) }} + ({{ toward }} - {{ hex_channel(col, 4) }}) * {{ factor }})::int), 2, '0')
    || lpad(to_hex(round({{ hex_channel(col, 6) }} + ({{ toward }} - {{ hex_channel(col, 6) }}) * {{ factor }})::int), 2, '0')
)
{%- endmacro %}

{% macro databricks__blend_hex(col, toward, factor) -%}
(
    concat('#',
      lpad(conv(cast(round({{ hex_channel(col, 2) }} + ({{ toward }} - {{ hex_channel(col, 2) }}) * {{ factor }}) as int), 10, 16), 2, '0'),
      lpad(conv(cast(round({{ hex_channel(col, 4) }} + ({{ toward }} - {{ hex_channel(col, 4) }}) * {{ factor }}) as int), 10, 16), 2, '0'),
      lpad(conv(cast(round({{ hex_channel(col, 6) }} + ({{ toward }} - {{ hex_channel(col, 6) }}) * {{ factor }}) as int), 10, 16), 2, '0'))
)
{%- endmacro %}
