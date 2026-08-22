# cfdb prompt 016 — the parity-gate rule I owe you, and the Standings column list

Nothing here blocks the light scores DAG. Read it after that ships.

---

```
You caught a real flaw in a control I designed, and the fix went somewhere I did not see. Both worth
saying before anything else.

=== THE `sql <text>` VERB WAS MY ERROR, AND IT WAS THE WHOLE POINT ===

I sketched a forced command and then put an arbitrary-SQL verb inside it. That hands back exactly
the execution the forced command exists to remove — a padlock with the key taped to it. An allowlist
with a passthrough verb is not an allowlist.

Five fixed verbs with validated identifiers is the correct shape, and
`count serving; drop schema serving cascade; --` being refused at identifier validation is the proof
I could not have given you.

=== AND THE DEEPER ONE: `cfdb_publish` IN THE DOCKER GROUP WOULD HAVE BEEN THEATRE ===

I recommended "non-root user" without knowing the Docker socket was in the path. Docker group
membership is root — `docker run -v /:/host` and you own the machine. So my recommendation, followed
literally, would have produced a control that LOOKED like a privilege reduction and was materially
identical to what it replaced.

That is a worse failure than no control, because it spends the credibility of the real ones. It is
the same family as the monogram fallback firing 100% of the time: something that appears to be
working precisely because it never does anything.

Removing Docker from the path is the actual reduction. Loopback-bound Postgres on 127.0.0.1:5433,
UFW still 22/tcp only, `cfdb_publish` with no docker group reaching it by psql — blast radius is now
"what it can do to the serving database," which is what publishing is. Defence in depth where the
first layer is real rather than decorative.

The five attack attempts are the fourth time you have proven something by trying to break it. Make
that the standing practice for every control, not just security ones.

=== THE PARITY GATE NEEDS AN AMENDMENT, AND IT IS MINE ===

I specified the strangler cutover gate as "a dbt test proves each srv_ view is row-for-row identical
to the mart it replaces." That framing breaks the moment the new side gets BETTER, and it just did:

  mart_team_season_record.school inherited the dim_team null identity. srv_standings was fixed.
  The parity gate failed on 14,964 rows BECAUSE the serving view became more correct.

You read that correctly — "the parity test doing its job precisely." But my wording does not say
that, and under a literal reading the cheapest way to make a red gate green is to RE-INTRODUCE THE
BUG on the new side. That is a real hazard in a deadline week and it is the document's fault, not
yours.

THE RULE, amended:

  When parity fails, the question is WHICH SIDE IS RIGHT — never how to make them match.

  - New side wrong  -> fix the new side. Gate does its original job.
  - Old side wrong  -> fix the old side, or retire it. Record the divergence, with the row count and
                       the reason, as an EXPECTED DIVERGENCE. Do not weaken the new side.
  - Both wrong      -> fix both, and the gate was never the point.

  An expected divergence is recorded, not suppressed. A gate that can be silenced by making the new
  thing worse is worse than no gate.

For this specific case: mart_team_season_record has the null-identity defect and nothing should read
it once srv_standings is live. Either fix it or retire it — but do not un-fix srv_standings to make
the numbers agree.

=== THE SELECTOR GUARD — the ancestor assertion is the better half ===

"A view rebuilt from an input that wasn't looks fresh and isn't" is the subtler failure and I did not
think of it. My suggestion was a count threshold; you were right that a threshold drifts and gets
raised — the first time someone legitimately removes a model, the fix is to lower the number, and
then it protects nothing. Membership by name has no such escape hatch.

Verifying it by reconstructing this morning's manifest and confirming it names all seventeen serving
views as unreachable is the same prove-by-breaking pattern again.

=== THE PG_DUMP RULE IS WORTH KEEPING VERBATIM ===

"A client may be newer than the server it dumps from, never than the one it restores into."

Asking the server its version and picking the binary is the right general fix, not a workaround. Put
it somewhere it will be found — this will recur the next time an image is rebuilt.

=== STANDINGS BREADTH — the column list, with a caveat about my source ===

I diffed the requirements against srv_standings. CAVEAT FIRST: my copy of the view's columns comes
from srv_sample.xlsx dated 20 August, which is BEFORE your slug, logo and null-identity fixes. So
some of what my diff calls missing you have already shipped. Check before building — I have been
wrong from stale evidence enough times on this project that the warning is earned.

Naming only, built name wins, no work needed:
  wins / losses            = overall_wins / overall_losses
  school                   = team_display
  logo_source_url          = logo_url

Believed genuinely absent, and all seven derivable from fct_game_team TODAY:
  division                    ~8% populated post-realignment. AC-5.2 says group by division "where
                              a conference has them", so ABSENCE MUST RENDER AS NORMAL, not as
                              missing data. This is the one most likely to be mis-implemented.
  conference_win_pct
  current_streak_display
  last_5_display
  home_record_display
  away_record_display
  ats_record_display          exists on srv_team_overview already — carry it across, and carry the
                              null-not-zero fix with it. An ungraded season is null, never 0-0-0.

Deferred to B1, correctly:
  sp_plus_rating, elo_rating

So Standings breadth is NOT blocked on B1 — seven of nine ship now, and the page is substantially
more useful with streaks, splits and last-5 than without.

Records come from the view as pre-formatted strings per AC-5.3. Do not assemble "5-7" in Python from
two columns.

=== ORDER UNCHANGED ===

  1. Light scores-only refresh DAG — 2 API calls vs 31
  2. Standings breadth
  3. B1 fct_team_week_rating

Calibration parked until Week 5.
```

---

## The one thing I'd flag to Marc separately

The parity-gate amendment matters beyond this instance. Two of the three published marts still have
live parity pairs, and `mart_team_season_record` now has a known defect that `srv_standings` does
not. Under the old wording, a red gate looks like a blocker on the serving side when the actual
answer is that the mart should be retired.

Six days out, the temptation to make a red thing green the cheap way is at its highest. Worth having
the rule written down before that pressure arrives rather than after.
