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

    {#
      ── A177 (cfdb-main-R-1773): A LOCAL BUILD MUST NOT REACH PRODUCTION ──────────────────
      A170 found this and nobody had scheduled the fix. The chain is ordinary and every link
      is correct on its own: a round builds a model against the warehouse to verify it (the
      charter calls that a read-and-build path); `dbt run` writes into the warehouse's OWN
      `serving` schema; and the scheduled publish copies that schema to the SERVING DATABASE
      the site reads, on its own cadence, WITHOUT ASKING WHETHER THE CODE IS MERGED.
      `srv_rankings_compare` went live that way inside the hour, before any PR.

      Nothing reconciles the publish against the deployed manifest -- verified by reading
      `src/publish_marts.py` and all three publishing DAGs. The deploy's single-flight lock
      does not cover it, because no deploy runs.

      ⚠️ WHAT SEPARATES A LAPTOP FROM PRODUCTION IS THE HOST, NOT THE TARGET NAME, and that was
      measured rather than assumed. Production runs `target: airflow` with
      `host: {{ '{{ env_var(\'PG_HOST\') }}' }}` = `warehouse` (read from the scheduler's own
      DBT_PROFILES_DIR). A laptop reaches the same database over an SSH local-forward, so its
      host is loopback. **Keying this on loopback means it CANNOT fire in production**, which
      matters more than the guard itself: this macro runs on every pipeline dbt invocation.

      ⚠️ AND ONLY FOR COMMANDS THAT BUILD. `dbt test`, `compile`, `parse`, `docs` and `ls` read
      or write nothing in `serving`, and a guard that blocked them would be routed around
      within a day.

      ✅ THE ESCAPE IS EXPLICIT AND NAMED: CFDB_ALLOW_LOCAL_SERVING=1. Deliberately awkward,
      because the point is to make publishing-by-accident impossible while leaving
      publishing-on-purpose one variable away.
    #}
    {#
      ⚠️ `flags` AND `selected_resources` ARE dbt's, NOT JINJA's, and this macro is rendered in
      a bare Jinja environment by tests/test_preflight_macro.py. Reaching for either
      unguarded raises `'flags' is undefined` and takes the whole on-run-start with it — which
      is how the existing tunnel test found this. Absent context means "not a build", which is
      the safe reading in both places.
    #}
    {% set which = flags.WHICH if flags is defined else none %}
    {% if target.name not in managed and host in loopback
          and which in ('run', 'build', 'seed', 'snapshot') %}
      {% set serving_selected = [] %}
      {% for uid in (selected_resources if selected_resources is defined else []) %}
        {% if uid.startswith('model.') and '.srv_' in uid %}
          {% do serving_selected.append(uid.split('.')[-1]) %}
        {% endif %}
      {% endfor %}
      {% if serving_selected and env_var('CFDB_ALLOW_LOCAL_SERVING', '0') != '1' %}
        {% do exceptions.raise_compiler_error(
          "cfdb preflight: REFUSING to build " ~ serving_selected | length ~ " serving model(s)"
          ~ " from a local target over an SSH tunnel (" ~ host ~ ":" ~ port ~ ") -- "
          ~ (serving_selected | sort | join(', ')) ~ ". THIS WOULD REACH PRODUCTION: dbt writes"
          ~ " into the warehouse's serving schema and the SCHEDULED PUBLISH copies that schema"
          ~ " to the live serving database on its own cadence, without asking whether the code"
          ~ " is merged (cfdb-main-R-1327, found by A170). Build it through a PR and the deploy"
          ~ " instead -- scripts/deploy_main.sh reconciles against the deployed manifest. To"
          ~ " verify SQL without building, use `dbt compile` and run the compiled SELECT."
          ~ " If you truly mean to publish from here, set CFDB_ALLOW_LOCAL_SERVING=1.") %}
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
