# Reply to Claude Code — the calibration finding has a consequence for Edge Finder

Paste the fenced block whole. Two acceptance criteria amended (`AC-G.32`, `AC-G.33`) — both were my
underspecification, not your implementation.

---

```
The alarm paid for itself in under a day, and the calibration numbers are the most interesting thing
either of us has found on this project. Both below. B1 is the right next thing.

=== A6 CAUGHT THE WORST CLASS OF FAILURE THERE IS ===

A stale deploy tree rebuilding serving from old model files would have reverted the logo fix, the tie
fix, the scoreboard columns and the ATS null — and the build would have SUCCEEDED. Green, silent,
destructive. Nobody investigates a passing job.

Two days ago that alarm was a paragraph in a build order. Worth stating what it actually
demonstrates: the pin protects production from dev, the alarm protects production from the pin, and
neither is optional. If you had shipped the pin without the alarm, tonight's build would have undone
a day's work and the first symptom would have been someone noticing the logos were gone again.

=== THE CALIBRATION FINDING — read this bit carefully, it has a consequence ===

xgboost_home_win_CALIBRATED is measurably miscalibrated, and it is worth saying that plainly because
the name asserts otherwise:

  80-90% band:  says 0.855  ->  actually won 0.929   UNDERconfident
  40-50% band:  says 0.459  ->  actually won 0.329   OVERconfident

Both points move the same way: predicted probabilities are COMPRESSED TOWARD 0.5. The model
understates favourites and overstates underdogs. That is the classic signature of over-regularisation,
or of a calibration step fitted on a different distribution than the one being scored.

THE CONSEQUENCE, and this is why it matters beyond the page:

  Edge = model probability - market probability.

  If model probabilities are systematically compressed toward 0.5, then that difference is
  systematically biased TOWARD UNDERDOGS. When Edge Finder goes live in Week 5, it will surface a
  disproportionate number of underdog "edges" that are artifacts of miscalibration rather than real
  value — and they will look exactly like the good ones.

  This is the single most plausible way this site loses Marc money, and it is invisible on any
  accuracy metric. 73.2% straight-up looks identical whether the model is calibrated or not, which
  is exactly the point you made.

WHAT I'D DO WITH IT — one check, then a decision:

  1. Pull the FULL probability-decile curve now that the segment exists — all ten bands, predicted
     vs actual, per model. Two points suggest compression; ten will show whether it is monotonic and
     how severe. If the curve is consistently inside the diagonal, it is systematic and fixable.

  2. If it is systematic, the honest options are, in order of preference:
       a. Recalibrate (isotonic or Platt on held-out data) and compute edge off the recalibrated
          probability. Store both, with a method column, the same way devig_method is stored.
       b. Ship as-is and put the miscalibration ON Edge Finder as a stated caveat, not just on
          Model Performance.
       c. Do not ship probability-based edges at all until it is fixed; spread edges are unaffected.

  Do NOT quietly adjust probabilities to make the curve look better. Store the raw model output, add
  the calibrated one alongside, and let the calibration plot show both.

  This is a modelling call and it is Marc's, not yours or mine. Put it in DECISIONS NEEDED with the
  full decile curve attached and let him choose.

One more thing worth putting on the page: the calibration plot is now the single most valuable chart
on the site, and it is the one that most justifies the project's "honest measurement" framing. A
model that says 85% and wins 93% is a better story than a model that says 73% accurate, because the
first is a claim you can check and the second is a number you have to trust.

=== TWO CRITERIA WERE MINE TO FIX, AND I HAVE ===

AC-G.33 was underspecified and it produced your ATS denominator bug. It said "renders with its n
adjacent" and did not say WHICH n. Amended: the n shown must be the denominator the rate was
actually computed over, not a neighbouring count.

Your description of it is the useful generalisation and I have written it into the doc: both numbers
were individually correct, and placing them adjacent asserted a relationship that did not hold. Same
class as the ->> silent null — every component behaves correctly, the assembly is wrong. COMPOSITION
DEFECTS are invisible to component-level testing by construction, which is why the criterion has to
name the relationship rather than the parts.

AC-G.32 was missing a state. It had null and zero; there is a third. Amended to three: null renders
em dash, zero renders 0, NOT-APPLICABLE renders n/a with a hover. You are right that a bare em dash
for cover_scored = 0 reads as missing data and invites "when will this fill in?" — the answer is
never. "We don't have it yet" and "this doesn't apply here" are different claims.

=== TWO THINGS YOU DID THAT I'D MAKE STANDING PRACTICE ===

The missing-conference test. A cut that vanishes from a union and says nothing is the same failure
as a signal that never fires — and you verified it by DELETING THE ROWS AND WATCHING IT FAIL, which
is the only way to know a test tests. That is the second time you have proven a guard by breaking it
deliberately. Make it the pattern for every guard.

Refusing to substitute * for {MEASURES}. "It proves the table exists and nothing about the columns,
which is the whole point" — exactly right, and it is the same reasoning as never rendering a number
the model did not produce. A check that passes for the wrong reason is worse than no check, because
it spends the credibility of the ones that work.

=== B1 NEXT — agreed ===

fct_team_week_rating is the last thing making pages partial: Team page Ratings and Trends, Matchup,
team profile percentiles. Everything else is either done or unblocked.

Build it from the CFBD ratings endpoints already landed in raw — /ratings/sp, /ratings/elo,
/ratings/srs, and the /wepa and /ppa families. NEVER from the pack's training_data.csv, which ships
5,133 games of exactly these features pre-assembled. That convenience is the trap the provenance
rule exists for, and this is the one model where it will actually be tempting.
```

---

## What changed in the requirements

| Criterion | Change |
|---|---|
| **AC-G.32** | Two states → **three**. Null `—`, zero `0`, **not-applicable `n/a`** with a hover |
| **AC-G.33** | Adds: the `n` shown **must be the denominator the rate was computed over** |

Both were gaps in my wording rather than in Code's implementation, and both are the same class —
a criterion that named the parts and not the relationship between them.
