# cfdb prompt 019 — one question on the SRS dedup, and a check of mine that fails your own rule

Short. Nothing here blocks skipped-test reporting or `sync_freshness`.

---

```
The sweep found a defect in a model you shipped an hour earlier. That is the part worth keeping:
RECENTLY WRITTEN IS THE LEAST-TESTED CODE, and the instinct runs the other way because it is fresh
in mind. Eleven of twelve clean and the twelfth an hour old is close to the ideal outcome for a
sweep — it proves the sweep is load-bearing rather than ceremonial.

And the signature was exactly as predicted, which is the more useful confirmation: identical rating
on both copies, so no average moved and no value looked wrong. What moved was a DENOMINATOR — SRS
percentiles over 266 rows for 265 teams. Nobody reviews a denominator.

=== ONE QUESTION: WHICH COPY WINS? ===

The duplicate rows differ in exactly one way — one carries a conference, one has conference: null,
same rating. So the dedup has a precedence question hiding in it, and I cannot tell from your report
whether it is answered:

  IF THE DEDUP PICKS ARBITRARILY — first row, min(sk), whatever the window function lands on — then
  some fraction of the time it keeps the NULL-CONFERENCE copy, and Charlotte silently loses its
  conference on the ratings page.

  The rule should be explicit: prefer the more complete record. Coalesce across copies if they ever
  disagree on anything other than completeness, and assert that they don't.

If you already did this, ignore me. If the dedup is `qualify row_number() over (...) = 1` with an
arbitrary order, that ordering is now load-bearing and should say so.

WORTH A LOOK WHILE YOU ARE THERE: this is the same shape as /teams versus /games — CFBD emitting a
PARTIAL record alongside a complete one for the same entity. Sweep 1 covered aggregate rows that are
not members. This is a different class: duplicate MEMBER rows of differing completeness. Your new
uniqueness test will now catch any of them at build time, so this is a question about precedence,
not detection.

=== YOUR FALSE-POSITIVE RULE APPLIES TO A CHECK I DESIGNED, AND IT FAILS IT ===

"A check that flags real data teaches you to skim its output" is the best line in this report, and
narrowing to a lowercase-initial identifier because every real school and player is a proper noun is
the right kind of fix — it distinguishes on what actually separates the classes rather than on a
substring that happens to correlate.

Now apply it to AC-16.6, which I wrote: every srv_ column must have a non-null description, set to
`warn` until coverage clears a threshold.

Coverage is 30.5%. So that check emits roughly 665 WARNINGS ON EVERY BUILD, none of which will
change tomorrow. By your own rule that is the noisiest thing in the project and it is actively
training both of us to scroll past build output. I designed a wallpaper generator.

THE FIX, and it keeps the intent: aggregate it. ONE warning per build —

  "documentation coverage 30.5% (292/957), target 60%, 665 columns undocumented"

One line that MOVES is readable. 665 lines that do not move are wallpaper. Same information, and it
now behaves like a metric rather than a fault list. Raise to `error` when it crosses the threshold,
as before.

While you are in there, it is worth asking the same question of every other check that can emit more
than a handful of rows at once. The test is not "is it correct" — all of ours are. The test is
"WOULD A HUMAN READ ALL OF ITS OUTPUT." If the answer is no, it needs aggregating, and a check
nobody reads is a check that is not running.

=== ON THE NAME ===

Noted, and thank you, but the credit runs the other way: I told you to check because I had already
been wrong four times by not checking, not because I suspected anything specific about ratings. The
instruction was a scar, not an insight. The fetch-log check was yours.

=== CARRY ON ===

Skipped-test reporting, then sync_freshness, then Standings takes the rating columns. Marc has the
walkthrough doc and is doing his pass — expect a batch of experience-level feedback rather than
data-level, which is the one class neither of us can generate.
```

---

## The one worth acting on regardless

**`rating_population` is the right shape and it should spread.** A percentile that renders "86% of 136" instead of "86%" is doing something the rest of the site mostly isn't — carrying the denominator alongside the number.

Every other rank and percentile on the site has the same exposure, and AC-G.33 already requires it in words. `rating_population` is the first place it's a *column* rather than a hope, and the team-stats percentiles are the obvious next candidate: the qualifying population there moves with the through-week filter, which is exactly the shifting denominator you flagged for ratings.
