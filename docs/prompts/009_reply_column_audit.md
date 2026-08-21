# Reply to Claude Code — column audit accepted, widen first

Paste the fenced block whole. `cfdb_site_requirements.md` is now **v1.2**; v1.2 changes carry
`[A 08-20b]`.

---

```
You're right, and you're right for the third time about the same thing. That's the part worth
naming before the specifics.

=== THE PATTERN, STATED PLAINLY ===

Three rounds, three times I took the cheapest available signal as evidence of readiness:

  1. Three object names      -> "fct_game_team is new"     -> it was production, 220,204 rows
  2. "the page renders"      -> "the view is built"        -> two views absent
  3. "the view exists"       -> "the page is buildable"    -> 104 of 135 columns absent

This isn't three unrelated slips. It's a standing willingness to treat the easiest observable as the
thing I actually need to know. "Check more carefully" has now failed three times, so v1.2 adds a
definition with a gate instead:

  A page is BUILDABLE only when: EXISTS (view in serving, both engines) + COMPLETE (every required
  column verified against information_schema, not by inspection) + PUBLISHED (on the droplet,
  readable by the app role). Anything less is NOT BUILDABLE and the page section says which of the
  three failed.

"Data ready" is withdrawn as a phrase. It meant only EXISTS and read as all three. Every page
section now carries three booleans instead.

AC-G.53 to AC-G.56 are new and encode it: a column-completeness check that is RUN, not eyeballed;
as_of_ts on every srv_ view, not_null-tested; team_slug in dim_team; and a rule that a stale
readiness line is a defect in the document rather than a detail.

=== THE WIDENING — decided: ONE PASS ===

Marc's call, and it settles your question: widen first, all seven views, one PR, one parity run.

Rationale for the shape: no partially-contracted serving layer, and no half-states to reason about
during cutover. The cost is accepted explicitly — nothing downstream is testable until it lands.
That also answers your foundation question in your favour. The shared foundation moves BEHIND the
widening, exactly as you argued: building the team-identity helper, attribution component and
query-param layer against views about to gain 104 columns means writing them twice.

Step 1 is one pass and includes:
  - Widen all seven built views to their specified columns.
  - team_slug, display names, contrast-safe colour columns into dim_team. This one is load-bearing
    beyond its size: AC-G.14 forbids deriving slugs in Python, so EVERY DEEP LINK ON THE SITE turns
    on it.
  - as_of_ts on every srv_ view. Absent from all seven and required by AC-G.35 on every page.
  - start_date_et where missing, per AC-G.34 - Eastern with the zone applied in dbt.
  - attribution + model_version_key onto the three prediction views. This was already flagged as a
    build item at AC-G.41; it is now folded in here rather than standing alone.
  - segment_type / segment_value structure onto srv_model_performance. You're right that AC-13.1 is
    correct about the numbers and wrong about the shape - 1 of 17 columns.
  - description_status on the dictionary chain. New column, not a rename - the view has only
    is_documented.
  - Build srv_team_overview and srv_odds_board to spec while you're in there.

=== THE FOUR SPECIFICS ===

1. serving is not on the droplet. Accepted, and it's now step 2 with its own note at AC-G.4.

   publish_marts.py shipping three tables into marts means AC-G.4's INVERSE is what's actually true:
   marts is the only thing the site can read. Extend publishing to serving, then scope cfdb_read to
   serving and revoke marts. Step 3 is impossible without it, so it goes ahead of the repoint.

2. The parity gate — you're right and I overstated it in the decision log. Corrected there and in
   Part 5.

   Met for srv_standings and srv_team_game_log. Not met for mart_data_freshness, and you're right
   that a parity test is the wrong instrument since srv_system_health unions four sources.

   DECIDED: retire the freshness banner rather than build a parity pair for it. AC-G.35 already
   requires per-page as_of_ts from each page's own view, and as_of_ts is in step 1 regardless - so
   the banner is redundant, and retiring it removes the last mart_* read. Detailed endpoint
   freshness is back-of-house content and belongs on System Overview, which is what AC-1.7 always
   said.

   The distinction I want kept: the gate applies to a CUTOVER, where a live element starts reading
   a different object. Retiring an element is not a cutover, so no proof is owed. Declaring
   srv_system_health a supersession WOULD have been one and would have needed a proof neither of us
   can produce - which is why that option was refused rather than taken as the fast path.

3. Page 16 corrected throughout.

   Both objects are 957; the "957 / 834" was two build times, not two objects. dim_field_metadata is
   a view over the live catalog, so its count moves whenever a model is added - noted, so nobody
   quotes it as fixed.

   Coverage restated at 30.5% (292 of 957), down from 41.6%. AC-16.3 amended to say the page renders
   the current figure whatever it is: a coverage metric that only ever goes up is a metric someone
   is managing rather than measuring. Your number went down because you added views faster than
   descriptions, which is the honest reason and the page should show it.

   AC-16.6 REWRITTEN. You're right it was trivially true - the view reads information_schema, so
   every serving column appears by construction and the test proved nothing. The criterion worth
   having is the one currently false: every srv_ column has a non-null description, failing for 69%.
   Set the test to WARN until coverage clears a threshold you pick, then raise to ERROR. A test that
   fails 665 times on day one gets muted; one that warns and is tracked gets paid down.

4. Page 18 corrected. fct_endpoint_freshness is mart_data_freshness and needs a serving equivalent;
   fct_pipeline_run does not exist, so that section renders Degraded per AC-18.7 and the source
   table no longer presents a non-existent object as if it were available.

=== WHAT I DID NOT CHANGE, AND WHY THAT MATTERS ===

Part 0 is untouched, on your assessment that it needs no changes. It has now survived two
reconciliations without amendment. That is the strongest evidence available that it is the part of
this document worth trusting - and it is also the part I wrote from first principles rather than
from observed state, which is worth noticing about where the errors have and haven't been.

=== PROCEED — step 1 ===

Serving completeness pass, one PR. Report:
  - The column-completeness check output, per view, present/missing against the required lists.
  - Parity across both engines after the widening.
  - Row counts before and after, so a widening that accidentally changed grain is visible.
  - Anything in the required column lists you think should not be built. 135 columns specified
    without database access will contain some that aren't worth the join.
```

---

## The one thing I'd watch on step 1

A widening pass that touches seven views and a shared dimension is the kind of change where **grain
can move silently**. `dim_team` gaining a slug is harmless; a view gaining a column via a join that
turns out not to be 1:1 is not, and it will show up as a row count rather than an error.

That's why the report asks for row counts **before and after**, not just after. `srv_matchup` at
110,634 and `srv_team_stats` at 177,876 should be identical on both sides of the widening. If either
moves, the widening introduced a fan-out, and finding that at the parity step is much cheaper than
finding it on a page that quietly double-counts.
