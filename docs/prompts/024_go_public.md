# cfdb prompt 024 — green light, with three answers and one addition

Scans clean. Proceed. Answers to everything you raised, plus one control I want that neither of us
proposed.

---

```
GO. The scans clear the gate — nothing licensed, nothing secret, no bulk data has ever been
committed, and .gitignore has covered .env since commit 465cc60. Proceed with the infra scrub and
docs/, then Marc flips the switch.

=== YOUR METHOD WAS BETTER THAN THE ONE I SPECIFIED, AND IT IS WORTH KEEPING ===

I asked for gitleaks and pattern matching. You read the LIVE VALUES from .env and the deploy key and
searched all 557 historical blobs for those exact strings.

That is a materially stronger test and the difference matters: PATTERN MATCHING FINDS SECRET-SHAPED
THINGS; EXACT-VALUE MATCHING FINDS YOUR SECRETS. A key stored without a recognisable prefix, or
split across a line, or in a format no rule covers, is invisible to the first and unmissable by the
second. Make it the standard pre-publication check.

The path-blind blob check is the other one that actually settled it. "The largest object in the
entire history is 0.16 MB" is a complete answer to "is a 7 MB dataset in here" in a way that no
filename search is, because it does not depend on the file having kept its name. Same principle as
asserting what a selector RESOLVES to rather than that it ran.

And naming the five benign hits — smtp.gmail.com, cfdb_read, Marc's email — is the right way to
report a clean scan. A bare "clean" invites the question; a listed set of non-findings closes it.

=== 1. INFRA SCRUB — yes, do it ===

Droplet IP in three tracked files, eight occurrences, plus the loopback port, the UFW posture and
the full cfdb_publish.sh allowlist. You are right that none is a secret and that obscurity is not
security. Parameterise anyway.

The reason is not that it is dangerous — it is that it is a COMPLETE MAP with no upside. A reader
who wants to understand the architecture is served just as well by CFDB_DROPPLET_HOST from env with
a documented example. A reader who wants to probe it is served considerably better by the real
value. Twenty minutes, already env-var driven, no reason not to.

Keep deploy/cfdb_publish.sh in the repo with its allowlist visible. THAT FILE IS A CREDIT, NOT AN
EXPOSURE — a forced command with five fixed verbs and validated identifiers is the sort of thing a
hiring manager notices. Just not next to the host it points at.

=== 2. config/api-docs.json — untracked is right, but make it a DECISION ===

Agreed: reference CFBD's spec by URL rather than vendoring 170 KB of someone else's document.

But untracked is not the same as protected. Right now one `git add -A` commits it. ADD IT TO
.gitignore EXPLICITLY, so it is a recorded decision rather than an accident that has not happened
yet. Same reasoning as the deploy tree — a thing that depends on nobody making a mistake is not a
control.

That dangling 166 KB object is fine. Unreachable, gone at the next gc, never committed.

=== 3. THE *.xlsx CONFLICT — good catch, and my Phase 2 manifest was wrong ===

You are right and I did not check. `!docs/*.xlsx` is the correct fix — narrow, so the original rule
keeps doing its job everywhere else. The ignore exists because office documents live in Cowork; the
exception exists because two of them are deliberate deliverables.

Verify with `git check-ignore -v` after, the same way you found it.

=== 4. THE PACK — do NOT move it. Do this instead. ===

Your two reasons to ask first are both good, and the second is decisive: Marc is about to spend time
improving the models, so those paths are live. Breaking notebook paths and load_predictions.py in the
same week is a bad trade for a risk that has not materialised in the entire history of the repo.

BUT THE RISK PROFILE CHANGES THE MOMENT THE REPO IS PUBLIC. Today, a mistaken `git add -A` is an
embarrassing commit you amend. Once public, it is a licence breach you cannot take back — you can
rotate a key, you cannot un-publish a licensed file.

SO: A PRE-COMMIT HOOK THAT REFUSES ANY STAGED PATH UNDER cfdb_model_pack/.

  - Costs nothing, breaks no paths, survives the model work
  - Protects against the exact failure mode the move was meant to prevent
  - Fails loudly at the moment of the mistake rather than silently afterwards
  - Better than the move in one respect: it stays correct even if someone later re-creates the
    directory or points a path back at it

Do the same for training_data.csv and *.joblib by name, so the rule survives a rename of the
directory.

Then MOVE THE PACK OUT PROPERLY AFTER the model-tuning round, when the paths are not live. Twenty
minutes then, and the hook becomes belt-and-braces rather than the only control. Put it on the
register so it does not evaporate.

=== 5. docs/ — build it, per Phase 2 in prompt 023, with the xlsx exception ===

One addition on Marc's email. It appears in four files. He is deliberately putting it in the site
footer, so DEFAULT IS KEEP. Flag the occurrences in your report rather than removing them, and let
him overrule.

And when you write docs/README.md: WRITE IT LAST, KEEP IT UNDER A PAGE, and remember that the
"what went wrong and what we changed" paragraph is the one a hiring manager actually reads. The
silent-null class, the green-and-useless pattern, the guard scoped by the thing it guards. Three
sentences, no hedging.

=== REPORT BACK ===

  - The scrub: which files, which values parameterised, and the example values you documented
  - `git check-ignore -v` on both docs/*.xlsx files, proving the exception works
  - The pre-commit hook, and evidence it fires — stage a pack file deliberately and show the refusal.
    Fifth or sixth time now that proving a guard by breaking it has been the right move
  - The docs/ manifest as built, every scrub, and every passage you think Marc should read before
    it goes public

Then Marc flips it. Not you.
```

---

## What this leaves

**The gate was clean, which is the outcome worth stating plainly.** Nothing licensed, nothing secret,
no bulk data — and the `.gitignore` has held since the first commit, which is the part that means the
discipline was there from the start rather than retrofitted.

**Two decisions for Marc, both small.** The pack stays in the tree behind a pre-commit hook until the
model-tuning round is done — better than either option Code offered, because it protects against the
real failure mode without breaking live paths. And his email stays in `docs/` by default, since he's
publishing it on the site anyway.

**One item for the register:** move `cfdb_model_pack` out of the tree after model tuning. It's the
kind of thing that evaporates otherwise, which is exactly what the register exists to prevent.
