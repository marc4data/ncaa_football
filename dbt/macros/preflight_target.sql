{#
  THE BACKSTOP. Wired to on-run-start in dbt_project.yml, so no `dbt run`, `dbt build` or
  `dbt test` can avoid it.

  scripts/preflight_env.py is the better error message -- it can say "you have no profile in
  this working copy", which nothing running INSIDE dbt can say, because dbt has already
  loaded a profile by the time a macro executes. But the preflight is a thing you have to
  remember to run, and this file is the answer to a bug caused by depending on somebody
  remembering. So the cheap version lives here, on the path that cannot be skipped.

  IT PRINTS ON SUCCESS TOO. One line naming the working copy, the target, the host and the
  database, on every single run. The bug this repository just paid for was not a dbt error;
  it was a dbt run that succeeded against the wrong database and said nothing. A banner is
  the cheapest thing that would have caught it.

  SCOPE: `ci` and `airflow` are managed targets whose hosts are correct as written --
  CI's Postgres service container answers to localhost, and the compose network answers to
  `postgres`. They are exempt BY NAME, and everything else is checked, so a hand-rolled
  target is guarded rather than assumed innocent. A guard that fails on every green run gets
  muted, and this project has done exactly that.
#}

{% macro preflight_target() %}
  {% if execute %}
    {% set managed = ['ci', 'airflow'] %}
    {% set host = (target.host | default('')) | string | trim %}
    {% set port = (target.port | default(0)) | int %}
    {% set loopback = ['localhost', '127.0.0.1', '::1', '0.0.0.0'] %}

    {% if target.name not in managed %}
      {% if target.type == 'postgres' %}

        {% if host == '' %}
          {% do exceptions.raise_compiler_error(
            "cfdb preflight: target '" ~ target.name ~ "' resolves to an EMPTY host. "
            ~ "libpq would fall back to a unix socket on this machine, which is the local "
            ~ "Postgres dropped on 2026-09-05 (R-296) by another name. "
            ~ "Set CFDB_WAREHOUSE_HOST -- see CLAUDE.md, 'Environments'.") %}
        {% endif %}

        {#
          Loopback on 5432 is the dropped database, verbatim, as the old profiles.yml.example
          shipped it. Loopback on any other port is an SSH local-forward to the droplet
          warehouse, which is the supported path -- so the port is what separates them, not
          the host. See scripts/preflight_env.py for the same rule and the longer argument.
        #}
        {% if host in loopback and port == 5432 %}
          {% do exceptions.raise_compiler_error(
            "cfdb preflight: target '" ~ target.name ~ "' points at " ~ host ~ ":5432 -- "
            ~ "THE DATABASE THAT WAS DROPPED ON 2026-09-05 (R-296). This is the stale "
            ~ "profiles.yml template. dbt builds in the droplet's warehouse; there is no "
            ~ "local warehouse. Fix THIS working copy: "
            ~ "cp dbt/profiles.yml.example dbt/profiles.yml, open scripts/warehouse_tunnel.sh, "
            ~ "then python scripts/preflight_env.py.") %}
        {% endif %}

      {% endif %}
    {% endif %}

    {% set via = 'ssh tunnel -> droplet warehouse' if (host in loopback) else 'direct' %}
    {% do log('cfdb | target=' ~ target.name ~ ' host=' ~ host ~ ':' ~ port
              ~ ' db=' ~ target.dbname ~ ' schema=' ~ target.schema
              ~ ' via=' ~ via ~ ' | ' ~ target.profile_name, info=True) %}
  {% endif %}
  {# on-run-start must yield SQL or nothing; an empty select is the no-op dbt accepts. #}
  select 1
{% endmacro %}
