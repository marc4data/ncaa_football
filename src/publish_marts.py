"""Publish marts from the transform warehouse to the serving database (M5).

The serving contract: the site reads marts from serving Postgres and nothing else. This
moves them there.

**Why it goes over SSH rather than a database connection.** The droplet publishes no
ports — the firewall allows SSH only, and Postgres lives on an internal Docker network
where the site reaches it by service name. That is the settled access architecture, not an
oversight, so publishing dials in the one way that is open: `pg_dump` locally, streamed
over SSH, restored inside the container. Nothing about it requires opening a port.

Idempotent by construction: the dump carries `--clean --if-exists`, so a republish
replaces each mart rather than appending to it. Marts are derived data — rebuilding them
is always safe, which is what lets this be a blunt replace instead of a merge.

Source-agnostic by design: today it reads the transform Postgres; after the M4 cutover it
reads Databricks. Same contract, one flag.

Usage:
  python -m src.publish_marts --dry-run
  python -m src.publish_marts
  python -m src.publish_marts --marts mart_team_schedule
"""
import argparse
import contextlib
import getpass
import socket
import gzip
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Union

from dotenv import load_dotenv

load_dotenv()

# See deploy/README.md. No literal host in a tracked file.
DROPLET = os.getenv("SERVING_SSH_HOST", "")
STACK_DIR = "/opt/cfdb"

# The restricted publish identity. A dedicated Unix user with a forced command, no shell,
# and NO DOCKER GROUP — the last one is the point. `docker compose exec` was how this job
# reached Postgres, and Docker socket access is root by construction: `docker run -v /:/host`
# and you own the box. A "restricted" user in the docker group would have been theatre.
#
# Postgres is bound to 127.0.0.1:5433 on the droplet, so this identity reaches it with psql
# and nothing else. Its blast radius is the serving database, which is what publishing is.
#
# The key is passed by path and never read into this process. Airflow mounts it read-only;
# it is not in the repository and does not appear in a task log.
PUBLISH_HOST = os.getenv("SERVING_PUBLISH_HOST", "")
PUBLISH_KEY = os.getenv("SERVING_PUBLISH_KEY", "")
READ_ROLE = os.getenv("CFDB_READ_USER", "cfdb_read")


def _use_restricted() -> bool:
    """Use the restricted key when one is configured, the root path otherwise.

    Both transports are kept during the changeover on purpose: the root path is what has
    been publishing successfully for weeks, and switching a working production job with six
    days to the season on the strength of one green run is how the changeover becomes the
    incident.
    """
    return bool(PUBLISH_KEY)


# How long one publish verb may run before we give up on it.
#
# A HANGING RESTORE IS THE WORST CASE, so it gets a bound. On 29 August the 20:00 restore ran
# for 34 minutes before the worker was killed — long past Airflow's task-heartbeat timeout, so
# it died without a traceback, and the retry did not start until the ten-minute retry delay
# had also elapsed. A healthy restore of the same 333 MB dump takes two to ten minutes.
#
# Failing at twelve turns a 46-minute outage into a prompt, retryable error, and the retry is
# where recovery actually comes from. Paired with --single-transaction on the remote, a
# timeout now rolls back rather than leaving the site holding empty tables.
PUBLISH_TIMEOUT_SECONDS = int(os.getenv("SERVING_PUBLISH_TIMEOUT", "720"))

# The cheap verbs answer in seconds; only the restore streams a dump.
QUICK_VERB_TIMEOUT_SECONDS = 120

# gzip level for the dump. 6 is the default and the right trade here: level 9 spends roughly
# three times the CPU to save another few percent of a link that is already 5.6x quieter.
COMPRESS_LEVEL = 6


def _publish_ssh(verb: str, *, stdin: bytes = b"",
                 stdin_file: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Invoke one verb of the forced command. The remote side chooses nothing.

    🚨 `stdin_file` IS THE PATH THE RESTORE TAKES, AND IT EXISTS BECAUSE OF AN OOM.
    A payload handed over as `bytes` has to exist in this process's memory in full; handed
    over as a FILE, ssh reads it straight off the descriptor and this process holds none of
    it. See `publish_schema` for the incident. `stdin` stays for the cheap verbs, which send
    nothing or a few bytes.
    """
    command = ["ssh", "-i", PUBLISH_KEY, "-o", "BatchMode=yes",
               "-o", "StrictHostKeyChecking=accept-new", PUBLISH_HOST, verb]
    timeout = (PUBLISH_TIMEOUT_SECONDS if (stdin or stdin_file is not None)
               else QUICK_VERB_TIMEOUT_SECONDS)
    try:
        if stdin_file is not None:
            with open(stdin_file, "rb") as payload:
                return subprocess.run(command, stdin=payload,
                                      capture_output=True, timeout=timeout)
        return subprocess.run(command, input=stdin, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        # Raised, not returned: a timed-out publish must fail the task so the retry runs.
        # Returning a non-zero result would be indistinguishable from a remote refusal, and
        # the distinction is what tells you whether to look at the droplet or the network.
        raise RuntimeError(
            f"publish verb '{verb.split()[0]}' timed out after {timeout}s. The remote "
            f"restore runs in one transaction, so the serving database has rolled back to "
            f"the previous good data rather than being left empty.")


# The site's contract. Staging views and raw tables deliberately do not travel: serving
# holds what the site reads, so a page cannot accidentally query a 1.7 GB raw table.
MARTS_SCHEMA = "marts"
SERVING_SCHEMA = "serving"

# The legacy contract. Still published so the running site keeps working until it is
# repointed; dropped only after that, per the strangler pattern.
DEFAULT_MARTS = [
    "mart_team_schedule",
    "mart_team_season_record",
    "mart_data_freshness",
]

# The serving contract — what the site reads after the cutover.
#
# srv_data_dictionary is LAST on purpose. It catalogues the serving layer, so publishing it
# before its siblings ships a dictionary describing the previous state. Measured during A1:
# built in DAG order it was 31 columns short of the layer it claimed to describe.
DEFAULT_SERVING = [
    "srv_game",
    "srv_game_team",
    "srv_standings",
    "srv_teams_index",
    "srv_team_overview",
    "srv_team_game_log",
    "srv_rankings",
    "srv_rankings_compare",
    "srv_team_stats",
    "srv_odds_board",
    "srv_edge_finder",
    "srv_model_performance",
    "srv_line_movement",
    "srv_system_health",
    "srv_team_rating",
    # Drive grain, for the Matchup page's Drives chart (R-369). In the HOT set, and BEFORE
    # srv_data_dictionary so the catalogue still describes a layer that contains it.
    #
    # Measured on the warehouse rather than guessed: 40 MB over 78,536 rows — 8.5% of the hot
    # set and smaller than four tables already in it (srv_game_team 112, srv_game 72,
    # srv_team_game_log 69, srv_team_stats 53). Nowhere near the heavy three, which are
    # 138-306 MB each and split out because the wire is the pipeline's failure point.
    #
    # Hot rather than weekly on cadence too: drives ACCUMULATE DURING a game, so the
    # two-hourly refresh is the point rather than an overhead — the same argument that puts
    # srv_game and srv_game_team here, and the opposite of the player tables, which change
    # when games are played rather than while they are.
    "srv_drive",
    # Team x week grain, for Looking Back's offense/defense scatter and — R-478 — for the
    # Matchup pairing session B will build on it. Placed BEFORE srv_data_dictionary on the
    # same reasoning as srv_drive above: the catalogue should describe a layer that contains
    # it.
    #
    # ⚠️ THAT REASONING IS ALREADY BEING IGNORED FURTHER DOWN. Six entries sit AFTER
    # srv_data_dictionary — srv_game_weather, the two distribution tables, srv_team_roster,
    # srv_game_travel and srv_edge_bucket_performance — so "the dictionary stays last" is a
    # convention this list stopped keeping some time ago. Following the stated intent here
    # rather than the observed practice, and recording the discrepancy rather than quietly
    # picking one.
    #
    # Small: one row per team per week per season, ~485k rows of narrow numerics, and it
    # rides the hot publish because it changes whenever a game completes.
    "srv_team_week",
    # R-621. The week's shared scatter axis. HOT because it is derived from srv_team_week's own
    # inputs and moves whenever a game completes; it is in scores_refresh_dag's selector for the
    # same reason, and ci/check_publish_build_agreement.py holds those two lists to each other.
    "srv_team_week_metric_distribution",
    "srv_data_dictionary",
    "srv_game_weather",
    # The weekly distributions. Small — one row per week per metric per day, and ten bin rows
    # under it — so they ride the hot publish rather than the weekly one: the numbers move
    # every time a line moves, and a week-old distribution on a live page is worse than none.
    "srv_week_metric_distribution",
    "srv_week_metric_distribution_bin",
    # A214. One row per week; it rides the hot publish for the same reason the distributions do
    # — every figure on it moves when a score lands.
    "srv_week_summary",
    "srv_team_roster",
    "srv_game_travel",
    "srv_edge_bucket_performance",
]

# THE PLAYER TABLES PUBLISH ON A SLOWER CADENCE, AND THE REASON IS THE WIRE.
#
# These three are 608 MB of the serving schema's 932 MB. Including them takes a publish from
# 59 MB to 182 MB gzipped — and the scores DAG publishes the whole serving schema EVERY TWO
# HOURS over a link that is already this pipeline's failure point. 59 MB has taken 13 to 17
# minutes when that link is busy, long enough for Airflow to disown the task as a zombie and
# kill it mid-stream; on 29 August that left the site serving nothing for 46 minutes on a
# game day. Tripling the payload would make that routine rather than occasional.
#
# Splitting is honest rather than merely cheap: player season totals, box scores and play
# attributions change when games are played, not every two hours. The scores DAG exists to
# move scores and lines quickly, and none of these three are that.
#
# Selective publishing needs no change to the fragile part. publish_schema already takes an
# explicit table list, and the dump carries --clean --if-exists, which drops only the tables
# IN the dump — so a hot publish leaves these three untouched rather than deleting them.
# ==========================================================================================
# WHY A HOT TABLE MAY BE REBUILT AND PUBLISHED WEEKLY. A079/R-533.
#
# 🚨 READ THIS FIRST — THE LIST'S MEANING CHANGED IN A184 AND THE PROSE DID NOT FOLLOW UNTIL
# A185 (cfdb-main-R-1908). Every sentence below used to argue that a table was SAFE TO SHIP
# HOT because its data only moves weekly. **Nothing ships these hot any anymore.** A184 gave each
# gated DAG its own publish list — exactly what that run built and tested — so a table nobody
# builds is a table nobody publishes on that cadence.
#
# ✅ SO WHAT THIS DICT NOW MEANS IS NARROWER AND STILL LOAD-BEARING: *this table is in
# `HOT_SERVING`, and it is DELIBERATE that no gated DAG rebuilds it.* It is the difference
# between a considered weekly cadence and a selector somebody forgot to extend, and
# `ci/check_publish_build_agreement.py` reads it to tell those two apart. **The justifications
# are still the evidence; they are just answering "why is this not in a gated selector?"
# rather than "why is it safe to ship unchanged?"**
#
# ⚠️ AND A STALE ENTRY IS AN ERROR, NOT A COMMENT. The guard fails if a table listed here IS
# rebuilt by a gated DAG — which is how A185 caught `srv_drive` the moment it joined
# SCORES_SELECTOR.
#
# ── the original reasoning, kept because it is why the dict exists ─────────────────────────
# HOT_SERVING was shipped whole on every gate-open run of cfbd_scores_refresh. A table in it
# that no gated DAG REBUILDS was therefore re-published, unchanged, several times a day —
# arriving on the site looking exactly as fresh as the rows beside it that genuinely moved.
# A078 found srv_team_week doing that and then measured the list: 18 of 24.
#
# ⚠️ THE POINT IS NOT THAT WEEKLY IS WRONG. It is that "weekly" must be a DECISION rather than
# an oversight, and until this dict existed there was no way to tell the two apart — the two
# lists that had to agree were HOT_SERVING and the DAG selectors, and nothing checked them
# against each other. ci/check_publish_build_agreement.py now does, and it reads this dict.
#
# To add a table here you must be able to finish the sentence "this is rebuilt weekly because
# its own data only changes weekly". If you cannot, put it in a selector instead.
#
# Every entry below was confirmed against the model's OWN lineage on 2026-09-09 — walking each
# view to its raw sources with mart_as_of's subtree excluded, because mart_as_of reaches
# fct_prediction and would otherwise put `model_prediction` and `lines` in every answer.
WEEKLY_BY_DESIGN = {
    "srv_data_dictionary":
        "Not endpoint-derived at all — it reads information_schema, so there is no fetch "
        "cadence to keep up with. Confirmed: zero raw sources in its lineage.",
    # 🚨 `srv_drive` WAS HERE AND A185 REMOVED IT, WHICH IS THE ENTRY WORTH REMEMBERING.
    # Its justification read: "Its subject is /drives, fetched only by cfbd_results_refresh
    # (Sunday) and cfbd_midweek_results (Thursday). Rebuilding hot would rebuild from raw
    # that has not moved." **Every word was true, and the premise was the defect.** That /drives
    # was fetched weekly is exactly what kept the Matchup drive panel off the site on a
    # Saturday night, so A185 put it on the game-day cadence and this entry had to go. The
    # guard failed the moment the selector changed, which is what it is for.
    "srv_rankings":
        "Its subject is /rankings, fetched by the Sunday and Tuesday weekly DAGs. Polls "
        "publish weekly; there is nothing between them to pick up.",
    "srv_rankings_compare":
        "Same source and same cadence as srv_rankings — /rankings only.",
    "srv_team_rating":
        "Its subject is ratings_sp / _srs / _elo / _fpi and ppa_teams, all in the weekly "
        "REVISIONIST bucket. A077 gave these their own `rating` as-of domain for the same "
        "reason. `games` appears only via the identity join.",
    "srv_team_stats":
        "Its subject is stats_season, weekly REVISIONIST.",
    "srv_team_roster":
        "Its subject is /roster, a reference endpoint. A077 measured it last loaded "
        "2026-08-15 and published that honestly rather than flattering it.",
    "srv_system_health":
        "Its subject is the pipeline's own ops tables — dbt_test_result, deploy_status, info, "
        "warehouse_usage — which the weekly DAGs' dbt_catalogue step already rebuilds.",
    "srv_game_travel":
        "Travel distance is a property of the FIXTURE, not of the result: it is computed from "
        "venue geography and the schedule, and does not change when a game finals. `games` is "
        "in the lineage because the fixture is, not because the score is.",
    # ⚠️ THE THREE PREDICTION VIEWS ARE JUSTIFIED TODAY AND THE JUSTIFICATION HAS AN EXPIRY.
    # A077/R-491 measured it: all 3,402 rows in fct_prediction are season 2025, every one for
    # a completed game, last generated 2026-08-19, and NO DAG produces them —
    # src/load_predictions.py is a hand-run load. So there is nothing for a rebuild to pick up.
    #
    # ⚠️ But their subject is model MINUS market, and the market half is /lines, fetched every
    # four hours. The moment predictions are generated again these three stop being
    # weekly-by-design and belong in a selector. Recorded here so that is a decision rather
    # than a thing nobody revisits.
    "srv_edge_finder":
        "No predictions have been generated since 2026-08-19 and no DAG produces them "
        "(A077/R-491), so there is nothing to rebuild. ⚠️ EXPIRES the moment the prediction "
        "pipeline runs — its market half is /lines, fetched four-hourly.",
    "srv_edge_bucket_performance":
        "Same as srv_edge_finder — no prediction pipeline. ⚠️ Same expiry.",
    "srv_model_performance":
        "Same as srv_edge_finder — no prediction pipeline. ⚠️ Same expiry.",
}

HEAVY_SERVING = [
    "srv_player_stats",
    "srv_player_game_log",
    "srv_player_play",
    # 🚨 `srv_game_team_leader` WAS PUBLISHED HERE AND CONTRACTED IN A132 (R-841/R-867). It was
    # 308,232 rows and 87 MB, republished every week, and after B110 removed Matchup's
    # `Game leaders` section it was read by NOTHING. §3.3's EXPAND → MIGRATE → CONTRACT: B
    # migrated the page, A dropped the object a round later.
    #
    # ⚠️ THE MART IS UNTOUCHED. `fct_player_game_stat` still carries every row; what went is the
    # serving copy and its weekly publish. Restoring it is one model file and one list entry.
    #
    # ⚠️ AND IT IS NOT THE VIEW THE POST-GAME CARDS READ. That is
    # `srv_game_team_leader_in_this_game`, which differs by a suffix, is published below, and
    # now draws every card including the defence.
    #
    # A106/R-687. The POINT-IN-TIME leaders — the three players leading a team going INTO a
    # game, as opposed to `srv_game_team_leader_in_this_game`, which answers who led IN one.
    #
    # HEAVY for the same reason as its sibling, and the reason is the FETCH rather than the
    # size: it is computed from player box scores, and /games/players is in the IMMUTABLE_WK
    # bucket, fetched only by cfbd_results_refresh (Sunday) and cfbd_midweek_results
    # (Thursday). The scores DAG fetches /games and nothing else, so a two-hourly rebuild
    # would rebuild this from raw that has not moved and produce identical rows. Hot
    # publishing cannot make a table fresher than its source endpoint.
    #
    # Size would have argued the same way rather than against it this time: 74,282 rows —
    # a QUARTER of the 308,232 the retired `srv_game_team_leader` carried — because the grain
    # is capped at three players per team per panel per game instead of one row per
    # category/type pair.
    #
    # ⚠️ THAT FIGURE READ 296,629 UNTIL A133 (R-873). A132 CONTRACTED THAT TABLE AND MEASURED
    # IT AT 308,232 IN THE SAME ROUND — and then rewrote the sentence around it while carrying
    # the stale number through. A number restated in a rewrite is not re-measured by the
    # rewrite, which is the whole failure this project keeps paying for, committed inside the
    # commit that was fixing the same class two lines above.
    "srv_game_team_leader_through_prior_week",
    # A107/R-694. Each leader's participation share in the games he had already played — the
    # series behind B092's circles.
    #
    # HEAVY for the same reason as the two leader tables above, and then some. It is computed from
    # `game/box/advanced`, which is registered `include=False` under "Per-game fan-out: opt-in
    # only" — ONE API CALL PER GAME — so no DAG fetches it at all. Every row came from a single
    # backfill on 2026-09-01. A two-hourly rebuild could not make it fresher than a source nothing
    # is pulling, which is the "arrives looking as fresh as the rows beside it" failure A078 and
    # A079 spent two rounds removing.
    "srv_game_team_leader_usage",
    # A120/R-723. The POST-GAME TWIN of srv_game_team_leader_through_prior_week — who led IN this
    # game, at the same (game, team, panel, leader_rank) grain, for the player cards Marc asked to
    # flank Box Score and Advanced.
    #
    # HEAVY FOR EXACTLY THE SAME REASON AS THE THREE ABOVE, AND THE REASON IS THE FETCH RATHER THAN
    # THE SIZE. It is computed from player box scores, and /games/players sits in the IMMUTABLE_WK
    # bucket — fetched by cfbd_results_refresh on Sunday and cfbd_midweek_results on Thursday, and
    # by nothing else. The two-hourly scores DAG fetches /games alone, so a hot rebuild would
    # recompute this from raw that has not moved and ship identical rows. Hot publishing cannot
    # make a table fresher than its source endpoint — A078 and A079 spent two rounds removing that
    # exact "arrives looking as fresh as the rows beside it" failure.
    #
    # Size argues the same way rather than against it: 67,248 rows, and 5.6% of the per-player
    # grain R-534 rejected — because the card asks for four panels and the HIGH end only rather
    # than fifty stat pairs and both extremes.
    #
    # ⚠️ A128 ADDED THE DEFENSIVE PANEL AND THE CADENCE ARGUMENT IS UNCHANGED BY IT — the
    # defensive box score arrives through `game/box/advanced` exactly as the offensive one does,
    # and the two-hourly scores DAG fetches neither. 53,873 -> 67,248 rows, of which 13,375 are
    # defensive; the extra 297 over a flat three-per-group are ties SHARING a rank, which this
    # view does deliberately on every panel.
    "srv_game_team_leader_in_this_game",
    # A121/R-724. The win-probability CURVE, per play — 291,548 rows, the sixth-largest serving
    # object. Marc: "We need win probability graphs for the games."
    #
    # HEAVY, AND HERE THE REASON IS BOTH SIZE AND FETCH. It is derived from `metrics/wp`, which
    # A115 put on a weekly cadence (R-716) in the IMMUTABLE_WK bucket — one call per completed
    # game, fetched by cfbd_results_refresh on Sunday and cfbd_midweek_results on Thursday. The
    # two-hourly scores DAG fetches /games alone, so a hot rebuild would recompute this from raw
    # that has not moved and ship 291,548 identical rows every two hours.
    #
    # ⚠️ AND THE CURVE OF A COMPLETED GAME NEVER CHANGES, which is the stronger half of the
    # argument: a game that finished on Saturday has one curve forever. Hot publishing cannot make
    # a table fresher than its source endpoint — A078 and A079 spent two rounds removing that
    # "arrives looking as fresh as the rows beside it" failure.
    "srv_game_win_probability_play",
    # A125/R-808. The box-score distribution — 18 measures at single-game team grain, 648 rows.
    #
    # ⚠️ I PUT THIS ON THE HOT LIST FIRST AND `ci/check_publish_build_agreement.py` REFUSED IT,
    # correctly. My reasoning was "a week's distribution moves every time a game completes" —
    # true of the GAMES, false of the DATA. It is computed from `fct_game_team` and
    # `fct_game_team_advanced`, which come from `/games/teams` and `game/box/advanced`, and those
    # are fetched by cfbd_results_refresh (Sunday) and cfbd_midweek_results (Thursday). The
    # two-hourly scores DAG fetches /games alone and does not rebuild this lineage at all.
    #
    # 🚨 SO A HOT PUBLISH WOULD SHIP A TABLE NO HOT DAG REBUILDS — which is exactly the
    # disagreement that guard exists to catch, and the same lesson A078, A079, A120 and A121 all
    # recorded: hot publishing cannot make a table fresher than its source endpoint.
    "srv_game_team_metric_distribution",
    # A143. WEEKLY FOR ITS SIBLING'S REASON, WHICH IS THE ONE STATED DIRECTLY ABOVE: it is
    # built from the same `int_game_team_metric_value` lineage, and the two-hourly scores DAG
    # does not rebuild that lineage at all. ⚠️ A CUMULATIVE WINDOW MAKES IT NO FRESHER — the
    # window only ever adds a COMPLETED week, so a hot publish would ship a table no hot DAG
    # rebuilt, which is exactly what ci/check_publish_build_agreement.py exists to refuse.
    "srv_game_team_metric_distribution_through_prior_week",
    # A124/R-766. The coach behind a game — 12,564 rows, one per (coach, team, season).
    #
    # ⚠️ WEEKLY BY THE SAME RULE A125 LEARNED AN HOUR EARLIER, and stated up front this time
    # rather than after ci/check_publish_build_agreement.py refused it: `/coaches` is registered
    # HISTORY_FULL with min_season=1886 and is fetched by the BACKFILL. No gated DAG fetches it
    # and no gated DAG rebuilds this lineage, so a hot publish would ship a table nothing hot
    # refreshes.
    #
    # 🚨 AND THE DATA ITSELF IS ANNUAL. A coach's season row changes when a season ends, not when
    # a game does. Hot publishing cannot make a table fresher than its source endpoint — A078,
    # A079, A120, A121 and A125 have all recorded that, and this is the sixth.
    "srv_coach_team_season",
]

# What the two-hourly publish ships: everything except the heavy three. Measured at 324 MB,
# which is exactly what it was before the player tables existed.
HOT_SERVING = [t for t in DEFAULT_SERVING if t not in HEAVY_SERVING]

# What a full publish ships. DEFAULT_SERVING stays the complete list so nothing that asks
# for "everything" silently gets a subset.
DEFAULT_SERVING = DEFAULT_SERVING + HEAVY_SERVING


# ── WHAT EACH GATED DAG PUBLISHES: EXACTLY WHAT THAT RUN BUILT AND TESTED ────────────────────
#
# 🚨 A184 (cfdb-main-R-1904). BOTH GATED DAGs CALLED `publish_all(hot=True)` AND SHIPPED ALL 25
# HOT TABLES WHILE BUILDING A FRACTION OF THEM — the scores DAG builds 11, the lines DAG builds
# 2. The other tables were copied out of whatever state the warehouse `serving` schema happened
# to be in, gated by tests that had never looked at them.
#
# 📊 AND IT REACHED THE SITE, WHICH IS WHY THIS IS A FIX RATHER THAN A TIDY-UP. A183 measured
# the weekly DAG refusing to publish on three failing tests, and found FIVE `srv_drive` rows
# with a NULL `drive_result_key` live on published serving anyway — put there by the two-hourly
# scores DAG, which publishes `srv_drive` and does not build or test it. The gate held and the
# data walked around it.
#
# 🚨 THE MECHANISM, NAMED, BECAUSE THE OLD JUSTIFICATION MISSED IT. `WEEKLY_BY_DESIGN` argues
# these tables are safe to ship hot because *their data only changes weekly*. That is an
# argument about FRESHNESS and it is true. **The gate is a different question**: the weekly
# DAG's `dbt_run` mutates the warehouse BEFORE its `dbt_test` decides whether to publish, so
# between a failed weekly test and its fix the warehouse holds exactly the rows the gate
# refused — and a two-hourly publish ships them.
#
# ✅ SO THE RULE IS: A TABLE IS PUBLISHED ONLY BY A RUN WHOSE TESTS COVERED IT, AGAINST THE
# STATE BEING PUBLISHED. Keyed on *built*, not on *has a test of its own*: what makes the state
# safe is that this run produced it and this run's test step gated it.
#
# ⚠️ AND IT COSTS NOTHING IN FRESHNESS, BY `WEEKLY_BY_DESIGN`'s OWN ARGUMENT. A table this run
# does not rebuild cannot be made fresher by publishing it — the same sentence that made these
# safe to ship hot is the sentence that makes shipping them pointless. `srv_system_health` is
# the case worth naming: it is rebuilt ONLY by the weekly DAG's `dbt_catalogue`, so the
# two-hourly publish has always been copying the same rows back.
#
# ⚠️ THE ALTERNATIVE — WIDENING EACH DAG's TESTS TO COVER ITS WHOLE PUBLISH LIST — WAS REJECTED
# ON AN EXISTING GUARD, not on taste. Testing a table this run did not rebuild compares a fresh
# source against a stale output, which is R-672 exactly and what
# `test_no_test_straddles_the_gated_dags_refresh_boundary` already refuses. It would also add
# minutes to a job that runs every two hours.
#
# 🚨 THESE LISTS ARE NOT MAINTAINED BY HAND — `ci/check_publish_build_agreement.py` resolves
# each DAG's selector with `dbt ls` and fails if a list and its selector disagree. Two lists
# that must agree and nothing checking them is the defect A078 found (R-492) and it is the
# reason that guard exists at all.
SCORES_HOT = [
    # A185 (cfdb-main-R-1909): the scores DAG builds and tests this now, so by the gate rule
    # above it publishes it. 47 MB, the smallest of the three tables that round added.
    "srv_drive",
    "srv_game",
    "srv_game_team",
    "srv_game_weather",
    "srv_line_movement",
    "srv_odds_board",
    "srv_standings",
    "srv_team_game_log",
    "srv_team_overview",
    "srv_team_week",
    "srv_team_week_metric_distribution",
    "srv_teams_index",
    # A214. Held equal to SCORES_SELECTOR by ci/check_publish_build_agreement.py — the guard
    # that exists because two lists which must agree had nothing checking that they did.
    "srv_week_summary",
]

# ⚠️ `srv_team_week_metric_distribution` IS DELIBERATELY NOT HERE. It looks like it belongs —
# same family, adjacent name — and `DISTRIBUTION_SELECTOR` does not build it; SCORES_SELECTOR
# does. Resolving the selector with `dbt ls` rather than reading the names is what caught that,
# and the CI guard below re-checks it on every PR.
DISTRIBUTION_HOT = [
    "srv_week_metric_distribution",
    "srv_week_metric_distribution_bin",
]


def publish_gated(tables: List[str], schema: str = SERVING_SCHEMA) -> dict:
    """Publish exactly the tables a gated run built and tested, under ONE lock.

    🚨 ONE LOCK FOR THE WHOLE PUBLISH, WHICH IS THE BUG THIS REPLACES (cfdb-main-R-1905).
    A181 published the hot set through `publish_all()` — which takes the lock and RELEASES it —
    and then called `publish_schema(extra, ...)` for the box relations OUTSIDE any lock. The
    second half could interleave with a deploy or the other gated DAG, which is the precise
    thing `publish_lock` exists to prevent, and it would have done so on exactly the busy
    Saturday runs the box work was written for.
    """
    with publish_lock():
        publish_schema(tables, schema)
    return {"serving": len(tables), "tables": list(tables)}


def local_pg_env() -> dict:
    env = os.environ.copy()
    env["PGPASSWORD"] = os.getenv("PG_PASSWORD", "cfdb")
    return env


# RETIRED 2026-09-05 (R-312). _direct_pg() used to choose between a direct psql/pg_dump and
# `docker compose exec -T postgres` — the second being the LAPTOP's local Postgres, which was
# decommissioned with the rest of the local stack (R-296). There is nothing on the other side
# of that branch any more.
#
# It is gone rather than left returning True, because a dead branch that still reads like a
# supported path is how somebody concludes the laptop route is available. Both callers now
# take the direct route unconditionally: Airflow reaches the warehouse by compose service
# name, a laptop reaches it through scripts/warehouse_tunnel.sh, and pg_params() refuses to
# guess when neither is configured.


def _pg_dump_binary() -> str:
    """A pg_dump no newer than the server being restored INTO.

    pg_dump 18 emits `SET transaction_timeout = 0`, a parameter added in Postgres 17, and a
    15 server rejects the whole restore with `unrecognized configuration parameter`. The
    direction matters: a newer client may dump FROM an older server, but the output is not
    guaranteed to load INTO one.

    The version is asked of the server rather than hardcoded, so upgrading the warehouse
    does not leave this silently pinned to a client that no longer matches.
    """
    override = os.getenv("PG_DUMP_BINARY")
    if override:
        return override
    try:
        probe = subprocess.run(
            ["psql"] + _local_psql_args() + ["-tAc", "show server_version_num"],
            capture_output=True, env=local_pg_env(), timeout=30)
        major = int(probe.stdout.decode().strip()) // 10000
    except Exception:                                              # noqa: BLE001
        return "pg_dump"
    versioned = f"/usr/lib/postgresql/{major}/bin/pg_dump"
    return versioned if os.path.exists(versioned) else "pg_dump"


def _local_psql_args() -> List[str]:
    # Same source, same refusal as everywhere else — see load_raw_to_postgres (R-312).
    from .load_raw_to_postgres import pg_params
    cfg = pg_params()
    return ["-h", cfg["host"], "-p", str(cfg["port"]),
            "-U", cfg["user"], "-d", cfg["dbname"]]


# How much the spooling copies move at a time. Big enough that the syscall count does not
# matter, small enough that it is noise beside anything else this process holds.
COPY_CHUNK = 1 << 20


def _spool_dir() -> Optional[str]:
    """Where the dump is spooled. Overridable, and NOT silently a RAM disk.

    🚨 A127 found `/dev/shm` breaking a rebuild for exactly this reason: a tmpfs looks like
    a directory and spends memory. The default is the platform temp directory, which is
    disk-backed on the droplet (overlay on /dev/vda1, 43 GB free) and on a laptop.
    """
    return os.getenv("CFDB_PUBLISH_SPOOL_DIR") or None


def dump_marts_to_file(marts: List[str], sink: Path,
                       schema: str = MARTS_SCHEMA) -> int:
    """pg_dump the named tables STRAIGHT TO DISK. Returns the bytes written.

    🚨 THE DESTINATION IS A FILE AND NOT A RETURN VALUE, AND THAT IS THE WHOLE POINT.
    `subprocess.run(capture_output=True)` accumulates the child's stdout in Python and then
    joins it, so it peaks at roughly TWICE the dump — and the serving dump is now 1.67 GB
    against a 3.9 GB droplet with 1.8 GB already in use. See `publish_schema`.
    """
    table_args = []
    for mart in marts:
        table_args += ["-t", f"{schema}.{mart}"]

    flags = ["--clean", "--if-exists", "--no-owner", "--no-privileges"]
    command = [_pg_dump_binary()] + _local_psql_args() + flags + table_args

    with open(sink, "wb") as handle:
        result = subprocess.run(command, stdout=handle, stderr=subprocess.PIPE,
                                env=local_pg_env())
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr.decode()[:400]}")
    return Path(sink).stat().st_size


def _gzip_file(source: Path, target: Path) -> int:
    """Compress one file into another a chunk at a time. Returns the compressed size.

    ⚠️ NOT `gzip.compress(blob)`: that needs the whole input in memory AND allocates the
    whole output beside it, which is the second of the two doublings that produced the OOM.
    """
    with open(source, "rb") as raw, gzip.open(target, "wb", COMPRESS_LEVEL) as packed:
        shutil.copyfileobj(raw, packed, COPY_CHUNK)
    return Path(target).stat().st_size


def dump_marts(marts: List[str], schema: str = MARTS_SCHEMA) -> bytes:
    """pg_dump the named tables and return them as bytes.

    ⚠️ KEPT FOR CALLERS THAT WANT THE BYTES — nothing in the publish path does any more, and
    nothing that handles the real serving dump should: 1.67 GB as a Python `bytes` is the
    defect `dump_marts_to_file` exists to avoid.
    """
    with tempfile.TemporaryDirectory(prefix="cfdb-dump-", dir=_spool_dir()) as tmp:
        sink = Path(tmp) / "dump.sql"
        dump_marts_to_file(marts, sink, schema)
        return sink.read_bytes()


def remote_sql(statement: str) -> None:
    r"""Run one SQL statement on the serving database over SSH.

    Kept separate from the streaming restore on purpose: `docker compose exec -T` consumes
    stdin, so chaining a `-c` call ahead of the dump on the same SSH channel makes the
    first command eat the dump — which surfaces as `invalid command \N`, a COPY-data
    error that says nothing about the actual cause.
    """
    remote = (
        f"cd {STACK_DIR} && set -a && . ./.env && set +a && "
        f'docker compose exec -T postgres psql -v ON_ERROR_STOP=1 '
        f'-U "$SERVING_PG_USER" -d "$SERVING_PG_DB" -c "{statement}"'
    )
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", DROPLET, remote],
                            capture_output=True, input=b"")
    if result.returncode != 0:
        raise RuntimeError(f"remote sql failed: {result.stderr.decode()[:400]}")


def restore_to_serving(dump: Union[bytes, Path, str],
                       schema: str = MARTS_SCHEMA) -> None:
    """Stream the dump into the serving database over SSH.

    🚨 `dump` IS A PATH IN THE PUBLISH PATH. Bytes are still accepted — a caller with a small
    dump in hand should not have to spool it itself — but the real serving dump is 1.67 GB
    and is never materialised. See `publish_schema` for the incident that moved it.
    """
    if isinstance(dump, (bytes, bytearray)):
        with tempfile.TemporaryDirectory(prefix="cfdb-restore-", dir=_spool_dir()) as tmp:
            spooled = Path(tmp) / "dump.sql"
            spooled.write_bytes(dump)
            restore_to_serving(spooled, schema)
        return

    source = Path(dump)
    # pg_dump -t emits no CREATE SCHEMA, so the target schema has to exist first.
    if _use_restricted():
        for verb in (f"ensure-schema {schema}", ):
            result = _publish_ssh(verb)
            if result.returncode != 0:
                raise RuntimeError(f"{verb} failed: {result.stderr.decode()[:400]}")
        # COMPRESS, BECAUSE THE WIRE IS THE BOTTLENECK AND THE WIRE IS WHAT FAILS.
        #
        # Measured in August: the dump was 334 MB, the link to the droplet runs at about
        # 20 Mbit/s, and a healthy publish took 135 seconds — which is, to within a few
        # seconds, exactly the time needed to upload 334 MB at that rate. The database work
        # is not the cost; the upload is essentially all of it.
        #
        # ⚠️ THE 334 MB IS STALE AND IS KEPT ONLY AS THE HISTORY. A137 measured the same dump
        # at 1,671,065,249 bytes — 1.67 GB, five times the figure this comment was written
        # against. The ratio argument still holds; the absolute number does not.
        #
        # That is why this job is fragile. When the link is busy the same publish takes 13 to
        # 17 minutes, which is long enough for Airflow to disown the task as a zombie and
        # kill it mid-stream. Postgres then logs a truncated COPY at a different random line
        # every time, which reads like data corruption and is really just a severed pipe.
        #
        # gzip -6 costs a few seconds of CPU per hundred MB. Same bytes land, same single
        # transaction wraps them; the window that was failing gets about 5.6x smaller.
        with tempfile.TemporaryDirectory(prefix="cfdb-payload-", dir=_spool_dir()) as tmp:
            payload = Path(tmp) / "payload.gz"
            packed = _gzip_file(source, payload)
            raw = source.stat().st_size
            print(f"  compressed to {packed / 1e6:.1f} MB "
                  f"({raw / max(packed, 1):.1f}x) for transfer")
            result = _publish_ssh(f"restore-gz {schema}", stdin_file=payload)
        if result.returncode != 0:
            raise RuntimeError(f"restore failed: {result.stderr.decode()[:400]}")
        return

    remote_sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    remote = (
        f"cd {STACK_DIR} && set -a && . ./.env && set +a && "
        'docker compose exec -T postgres psql -v ON_ERROR_STOP=1 '
        '-U "$SERVING_PG_USER" -d "$SERVING_PG_DB"'
    )
    with open(source, "rb") as handle:
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", DROPLET, remote],
            stdin=handle, capture_output=True,
        )
    if result.returncode != 0:
        raise RuntimeError(f"restore failed: {result.stderr.decode()[:400]}")


def grant_read_access(marts: List[str], schema: str = MARTS_SCHEMA) -> None:
    """Re-grant SELECT to the read-only role.

    `--clean` drops and recreates each table, and a recreated table does not inherit the
    old one's grants. Without this the site would break on the first republish with a
    permission error — the kind of failure that looks like a database problem and is
    actually a publish-job problem.
    """
    # Schema-level, per the layering decision: the serving database contains only marts,
    # so the boundary that matters is "this role cannot see upstream layers" — and a new
    # mart becomes readable on publish rather than needing a grant nobody remembers.
    if _use_restricted():
        result = _publish_ssh(f"grant {schema} {READ_ROLE}")
        if result.returncode != 0:
            raise RuntimeError(f"grant failed: {result.stderr.decode()[:400]}")
        return

    grants = (
        f'GRANT USAGE ON SCHEMA {schema} TO \\"$CFDB_READ_USER\\"; '
        f'GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO \\"$CFDB_READ_USER\\"; '
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} '
        f'GRANT SELECT ON TABLES TO \\"$CFDB_READ_USER\\";'
    )
    remote_sql(grants)


def verify(marts: List[str], schema: str = MARTS_SCHEMA) -> None:
    """Count rows on both sides and refuse to call a mismatch a success."""
    for mart in marts:
        count_sql = f"select count(*) from {schema}.{mart}"
        local_cmd = ["psql"] + _local_psql_args() + ["-tAc", count_sql]
        local = subprocess.run(local_cmd, capture_output=True, env=local_pg_env())
        if _use_restricted():
            remote = _publish_ssh(f"count {schema} {mart}")
        else:
            remote = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", DROPLET,
                 f"cd {STACK_DIR} && set -a && . ./.env && set +a && "
                 f'docker compose exec -T postgres psql -tAc '
                 f'"select count(*) from {schema}.{mart}" '
                 f'-U "$SERVING_PG_USER" -d "$SERVING_PG_DB"'],
                capture_output=True)
        left = local.stdout.decode().strip()
        right = remote.stdout.decode().strip()
        status = "ok" if left == right and left else "MISMATCH"
        print(f"  {mart:28} transform={left:>9} serving={right:>9}  {status}")
        if status == "MISMATCH":
            raise RuntimeError(f"{mart} did not publish cleanly")


def publish_schema(tables: List[str], schema: str) -> None:
    """Dump, restore, grant and verify one schema.

    🚨 THE DUMP GOES TO DISK AND NEVER INTO MEMORY — A137, cfdb-main-R-914, and the reason is
    an outage rather than tidiness.

    📊 WHAT HAPPENED. On 2026-09-15 `cfbd_pregame_refresh.publish_to_serving` was killed by
    the kernel on all three attempts, at the same point every time: the marts publish
    finished, `[serving] publishing 34 table(s)` printed, and the task died with SIGKILL.
    Airflow reported it as "Process terminated by signal. Likely out of memory error (OOM)."
    ⚠️ NO dbt TEST FAILED — that run captured 498 pass, 4 warn, 0 fail — so nothing about the
    data was wrong and nothing about the gate was wrong. The publisher simply could not fit.

    📊 THE ARITHMETIC, MEASURED RATHER THAN REASONED:

        the serving dump                 1,671,065,249 bytes (1.67 GB)
        the droplet                      3.9 GB total, 1.8 GB already in use, 2.1 GB free
        `capture_output=True`            accumulates the child's stdout in a list and JOINS
                                         it, so it peaks at about TWICE the dump
        `gzip.compress(dump)`            allocates the compressed copy WHILE the dump is
                                         still alive

    ⚠️ TWO INDEPENDENT DOUBLINGS ON A 1.67 GB PAYLOAD. There is no droplet size at which
    holding the whole dump in memory to hand it to a pipe is the right shape, which is why
    this is a code fix and not a capacity question.

    ✅ AND IT EXPLAINS WHY THE TWO-HOURLY PUBLISH KEPT WORKING: `hot=True` ships the 25
    fast-moving views, 569 MB against the full 1,527 MB, and that fitted. The failure was
    specific to the full publish, which is what the three weekly DAGs run.

    Nothing else about the publish changes: same tables, same bytes on the wire, same gzip,
    same single remote transaction, same row-count verification.
    """
    print(f"\n[{schema}] publishing {len(tables)} table(s)")
    with tempfile.TemporaryDirectory(prefix="cfdb-publish-", dir=_spool_dir()) as tmp:
        spooled = Path(tmp) / f"{schema}.sql"
        written = dump_marts_to_file(tables, spooled, schema)
        print(f"  dumped {written / 1e6:.1f} MB")
        restore_to_serving(spooled, schema)
    grant_read_access(tables, schema)
    print("  restored; verifying")
    verify(tables, schema)


# ==========================================================================================
# ONE PUBLISH AT A TIME (R-314). A POSTGRES ADVISORY LOCK ON THE WAREHOUSE.
#
# `pg_dump --clean --if-exists` against ONE serving Postgres, callable from every working
# copy and from Airflow. Two publishes overlapping means one dropping tables the other is
# restoring into, and the visible symptom is the site rendering an empty page.
#
# WHY NOT THE DROPLET LOCK scripts/deploy_main.sh USES. That one is a `mkdir` over root SSH.
# This job deliberately does not have root SSH: it goes through a forced-command identity
# with no shell, and "the remote side chooses nothing" is the security property that makes
# the restricted key worth having. Sending it an arbitrary mkdir would give that back.
#
# WHY AN ADVISORY LOCK RATHER THAN A LOCKFILE. It is held by a CONNECTION, so it is released
# when the connection ends — including when the process is killed, which is the case a
# lockfile gets wrong. On 29 August a restore ran 34 minutes and the worker was killed
# without a traceback; a lockfile would have survived that and blocked every retry
# afterwards. There is no stale advisory lock to clear, ever.
#
# The lock lives on the WAREHOUSE because that is the one instance every publisher already
# connects to — Airflow on the compose network, a laptop through the tunnel. The serving
# Postgres would be the more obvious home and is unreachable except through the forced
# command, which is the same reason as above.
#
# IT REFUSES, IT NEVER QUEUES. try_ rather than a blocking lock: a publish that waited would
# start by dumping a warehouse the first publish has since rebuilt, and ship it as current.
# ==========================================================================================
# Arbitrary but fixed. Advisory lock keys are a global namespace on the instance, so this is
# recorded here rather than computed, and changing it silently disables the lock.
PUBLISH_LOCK_KEY = 8_140_927_318


@contextlib.contextmanager
def publish_lock():
    """Hold the publish lock for the duration of the block, or refuse and say who holds it."""
    from .load_raw_to_postgres import get_conn

    connection = get_conn()
    connection.autocommit = True
    holder = f"{getpass.getuser()}@{socket.gethostname()} pid {os.getpid()}"
    try:
        with connection.cursor() as cursor:
            cursor.execute("select pg_try_advisory_lock(%s)", (PUBLISH_LOCK_KEY,))
            if not cursor.fetchone()[0]:
                cursor.execute("""
                    select coalesce(a.application_name, ''), a.usename, a.client_addr,
                           a.backend_start
                    from pg_locks l join pg_stat_activity a on a.pid = l.pid
                    where l.locktype = 'advisory' and l.objid = %s and l.granted
                """, (PUBLISH_LOCK_KEY % 2**32,))
                other = cursor.fetchone()
                detail = (f"held by {other[1]}@{other[2] or 'local'} since {other[3]}"
                          if other else "held by a connection this session cannot see")
                raise RuntimeError(
                    f"ANOTHER PUBLISH IS RUNNING — refusing rather than queueing.\n"
                    f"  lock   : advisory {PUBLISH_LOCK_KEY} on the warehouse\n"
                    f"  {detail}\n"
                    f"  this   : {holder}\n\n"
                    f"  A second publish would dump a warehouse the first one has already\n"
                    f"  rebuilt and ship it to the site as current. Wait for it to finish;\n"
                    f"  there is nothing to clear — the lock ends with its connection.")
            # Named so the refusal above can say who, without a table to keep in sync.
            cursor.execute("select set_config('application_name', %s, false)",
                           (f"cfdb_publish {holder}",))
        yield
    finally:
        connection.close()          # releases the advisory lock; no explicit unlock needed


def publish_all(schemas: Optional[List[str]] = None, hot: bool = False) -> dict:
    """Publish every contracted schema. The entry point Airflow calls.

    Returns a summary rather than printing only, so a task log carries the row counts that
    were verified. `verify` raises on any mismatch, so a green task means every table was
    counted on both sides and agreed — this is the last hop before a user sees data and,
    until it was scheduled, the only hop with no check on it at all.

    `hot=True` publishes only the fast-moving serving views, which is what the two-hourly
    scores refresh wants: the three player tables are 608 MB of the schema and change when
    games are played, not every two hours. See HEAVY_SERVING.
    """
    schemas = schemas or ["marts", "serving"]
    published = {}
    with publish_lock():
        for schema in schemas:
            if schema == SERVING_SCHEMA:
                # `hot` ships only the fast-moving views; see HEAVY_SERVING for why. The
                # default stays the full list, so a caller that says nothing gets everything.
                tables = HOT_SERVING if hot else DEFAULT_SERVING
            else:
                tables = DEFAULT_MARTS
            publish_schema(tables, schema)
            published[schema] = len(tables)
    transport = "restricted publish key" if _use_restricted() else "root ssh"
    print(f"Published via {transport}: "
          + ", ".join(f"{k}={v} table(s)" for k, v in published.items()))
    return {"schemas": published, "transport": transport}


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish marts to the serving database.")
    parser.add_argument("--marts", nargs="+", default=DEFAULT_MARTS)
    parser.add_argument("--serving", nargs="+", default=DEFAULT_SERVING)
    parser.add_argument("--schemas", nargs="+", default=["marts", "serving"],
                        choices=["marts", "serving"],
                        help="which schemas to publish; both by default")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    plan = []
    if "marts" in args.schemas:
        plan.append((args.marts, MARTS_SCHEMA))
    if "serving" in args.schemas:
        plan.append((args.serving, SERVING_SCHEMA))

    print(f"Publishing to {DROPLET}")
    if args.dry_run:
        for tables, schema in plan:
            for t in tables:
                print(f"  would publish {schema}.{t}")
        return 0

    # The same lock publish_all takes. main() is the HAND-RUN path — the one that exists in
    # every working copy — so it is the caller that most needs it, not the one to exempt.
    with publish_lock():
        for tables, schema in plan:
            publish_schema(tables, schema)

    print("\nPublish complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
