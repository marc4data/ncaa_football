# cfdb prompt 015 — deploy key decided, publish DAG, then scores refresh

Answers the DECISIONS NEEDED block in Code's PR #21 report. Paste the fenced block whole.

---

```
DECIDED — dedicated restricted deploy key. Your recommendation, and Marc's call.

You were right to stop. Mounting a root key into a scheduler is not a thing to do without being
asked, and the fact that you flagged it rather than shipping it is worth more than the twenty
minutes it cost.

=== THE KEY — and one thing to check before you build it ===

New keypair, used only by Airflow, locked down in authorized_keys:

  command="/usr/local/bin/cfdb_publish.sh",no-pty,no-port-forwarding,no-agent-forwarding,
  no-X11-forwarding,from="<airflow-host-ip>" ssh-ed25519 AAAA... airflow-publish-only

The forced command is the part that matters. With it, the key cannot open a shell, cannot read a
file, cannot forward a port — it can run one script. Blast radius goes from "root on the droplet" to
"can trigger a publish." Revoked by deleting one line, with no effect on your own access.

CHECK THE PREMISE FIRST: does publish actually need root?

You described it as "an SSH key to the droplet as root." But publish_marts.py loads data into a
Postgres schema — that needs a POSTGRES role, not a Unix root. Root is very likely incidental: the
droplet was provisioned with root SSH and nobody changed it.

So before building anything, tell me what cfdb_publish.sh actually has to do. If it is
pg_dump | psql plus a schema swap, then:

  - create a dedicated cfdb_publish UNIX user, not root
  - give it exactly the filesystem access the script needs and nothing more
  - let the POSTGRES credentials do the real authorization, scoped to the serving schema

A forced command running as root is much better than a shell as root, but a forced command running
as a purpose-built user is better again, and it probably costs nothing here.

One more, and I genuinely do not know the answer: there is already a cloudflared tunnel to the
droplet for the website. If Cloudflare Tunnel is routing SSH, this could avoid exposing port 22 at
all. If it is not set up for that, do not build it now — six days out is the wrong time. Just say
which it is so the decision is recorded rather than assumed.

Store the private key as an Airflow Connection or a mounted secret, never in the repo, never in a
DAG file, and confirm it does not appear in task logs. A key that gets logged is a key that gets
committed eventually.

=== THEN: the publish DAG ===

Publish must run AS A DOWNSTREAM TASK OF THE DBT BUILD, not on its own schedule. That is the whole
argument against the host-cron option — a clock-triggered publish can fire mid-build and ship a
half-rebuilt serving layer, and it would succeed while doing it.

Same failure signature as the last two: green, silent, wrong.

Add a post-publish verification: row counts on the droplet compared against the transform tier for
each srv_ view, failing the task on mismatch. Publishing is now the last hop before a user sees
data, and it is currently the only hop with no check on it.

=== ON `+tag:production` RESOLVING TO SIX MODELS ===

This is the finding of the round and it deserves recording as a pattern, not just a fix.

The refresh fetched results, landed them in raw, rebuilt three legacy marts nothing reads, and
stopped. Not one srv_ view. Not fct_game. "The pipeline was scheduled right up to the point where it
stopped mattering" is exactly right, and every run was GREEN.

That is now three instances of the same shape in four days:

  1. Deploy tree 9 commits behind    a successful build that would have reverted a day's work
  2. `->> '0'` on a JSON array        a successful extraction returning null, masked by a fallback
  3. `+tag:production` = 6 models     a successful refresh that rebuilt nothing anyone reads

Every one of them was GREEN AND USELESS, and none was detectable from the run status. The common
cause is that all three checked that a thing RAN and never that it PRODUCED anything.

Worth a standing guard: assert what the production selector RESOLVES TO, not just that it succeeds.
A test that fails when the selector returns fewer than N models, or when any model backing a srv_
view is absent from it, would have caught this on the day the tag was introduced. You already built
exactly this shape for the missing conference segment — same idea, applied to the selector.

=== THE 11% UNNAMED TEAMS IS A DIMENSIONAL LESSON, NOT A BUG FIX ===

dim_team is built from /teams. fct_game's key space is /games. THOSE ARE DIFFERENT SETS, and the
fact table's is larger — 12,168 of 110,634 rows carried a team that /teams has never heard of.

The rule worth writing down: /games is the authority on WHO PLAYED. /teams is the authority on WHO
IS AN FBS PROGRAM. A Division II visitor is legitimately in the first and legitimately absent from
the second, and any model that assumes the dimension covers the fact's key space will be wrong by
about a tenth.

srv_schedule was right because it took the name from the game. srv_scoreboard was wrong because it
took it from the dimension. Same data, two sources, and only one of them is complete.

Two things to confirm you have covered:
  - Every OTHER view joining dim_team for a display name or slug has this same exposure. Sweep them.
    I flagged incomplete slug coverage from the sample at ~4%; the real figure is 11%, so my estimate
    was low by more than half.
  - Non-FBS stubs need a slug, or their rows link to nowhere. A clickable row with a null target is
    worse than an unclickable one.

And the winner re-derivation — Python computing from the sign of a nullable actual_margin while the
view already carried `winner`, disagreeing on 1 game in 295 — is AC-G.2 exactly. Two derivations of
one definition. The view wins.

=== WHAT THE REHEARSAL CLEARED IS WORTH AS MUCH AS WHAT IT FOUND ===

164/164 home wins carry a negative actual_margin ON SCREEN. Game log subject-team oriented on every
win. All seven box-score columns populate. Standings compute. Series reconciles.

That was the single largest untested surface on the site and it is now tested, with three completed
games pinned in CI permanently — including one against a team absent from raw_teams and one tie.
Both branches run every build. That is the "prove it by breaking it" pattern for the third time.

=== ORDER FROM HERE — your list, confirmed ===

  1. Deploy key + publish DAG + post-publish row-count verification
  2. Light scores-only refresh DAG. You are right that 31 API calls is too heavy hourly and a
     games-only fetch is 2. Note the timing problem stands regardless: cfbd_midweek_results at
     Thursday 12:00 UTC fires ten hours BEFORE Thursday's 22:00 kickoffs, so without the light DAG
     opening night sits unresolved until Sunday.
  3. Standings breadth — the eight missing columns
  4. B1 fct_team_week_rating

Calibration stays parked until Week 5.
```

---

## Why the premise check is in there

Code described the requirement as "an SSH key to the droplet **as root**." That may just be how the
droplet was provisioned rather than what publishing needs — loading a Postgres schema wants a
Postgres role, and the Unix user is incidental to it.

If that's right, the same twenty minutes buys a purpose-built `cfdb_publish` user instead of root,
and the forced command becomes belt-and-braces rather than the only thing standing between a
compromised scheduler and the droplet. If it's wrong and root really is needed, that's worth knowing
explicitly rather than by default.

## The pattern worth watching

Three findings in four days shared one shape: **green and useless.** A build that succeeded while
reverting work, an extraction that succeeded while returning null, a refresh that succeeded while
rebuilding nothing anyone reads.

None was visible from run status, because all three checked that something *ran* and never that it
*produced* anything. The publish DAG's row-count verification is the same guard applied to the last
hop — which, until now, was the only hop with no check on it at all.

