# cfdb prompt 023 — pre-flight scan before the repo goes public

**Do not change repo visibility until this reports clean.** Public is irreversible in practice —
forks, GH Archive and Software Heritage mean you cannot reliably un-publish.

---

```
Marc wants to make github.com/marc4data/ncaa_football public so recruiters can see it. Before that
happens, three things need checking, and only you can do them — I can reach cfdb_model_pack/ and
config/ over the device bridge, but not the repo root and not git history.

CONFIRMED BY MARC: THE REPO ROOT IS claude_code/, NOT ncaa_football/. Two consequences —

  1. cfdb_model_pack/ AND config/ ARE IN THE REPO, at the root. The pack therefore sits inside the
     published tree, and SCANS 1-3 below are the gating work.
  2. claude_work IS NOT IN THE REPO — and MARC WANTS THAT CHANGED. A curated slice comes in as
     docs/. That is PHASE 2 below, and it is the part that makes this repo worth looking at.

WHAT I ALREADY FOUND, so you know where to look hardest:

  THE ENTIRE LICENSED MODEL PACK IS PHYSICALLY INSIDE THE REPO TREE — 29 MB at
  <repo root>/cfdb_model_pack/, containing:

    training_data.csv            7.0 MB   the licensed dataset itself
    9 notebooks                  ~2 MB    00_ through 08_
    saved_models/                19 MB    6 trained model binaries
    model_outputs/               1 MB     6 prediction CSVs
    LICENSE, README, guides

  And the pack LICENSE says, verbatim:

    "You may not: ... Upload the pack files to a PUBLIC REPOSITORY, shared drive, data marketplace,
     or notebook platform."

  A public repository is named explicitly. This is not an interpretation.

  I could not see a root .gitignore from my mount, so I am NOT concluding it is absent — you can see
  it and I cannot. But the structural risk stands regardless: 29 MB of contractually
  un-publishable files sit inside the tree, and one `git add -A` against a broken or reordered
  ignore rule commits them permanently.

=== SCAN 1 — is any pack content in git history, at any commit, ever? ===

Not the working tree. HISTORY. A file committed once and removed later is still fully recoverable
from a public repo.

  git log --all --full-history --diff-filter=A --name-only -- '*cfdb_model_pack*'
  git rev-list --objects --all | grep -iE 'training_data|model_outputs|saved_models|\.joblib'
  git cat-file --batch-all-objects --batch-check='%(objecttype) %(objectsize) %(rest)' \
    | sort -k2 -n -r | head -50

That last one finds large blobs regardless of path — a 7 MB or 16 MB object in history is the
signature you are looking for even if the filename was different at the time.

REPORT: every pack-derived path that has ever existed in history, with the commit that added it.

=== SCAN 2 — secrets, across full history ===

Run gitleaks or trufflehog in history mode, not a working-tree grep:

  gitleaks detect --source . --log-opts="--all"        # or
  trufflehog git file://. --only-verified

Specifically hunt for:
  CFBD API key · transform Postgres password · serving droplet Postgres password · Databricks PAT
  and workspace host · Airflow Fernet key and webserver secret key · Cloudflare tunnel token ·
  THE PRIVATE HALF OF THE cfdb_publish DEPLOY KEY

ONE THAT NO SCANNER PATTERN WILL CATCH, and it is ours: the publication boundary doc records that
raw_manifest REQUEST URLS MAY EMBED THE API KEY. So grep every committed fixture, snapshot and
sample file for manifest rows and for the literal key format, not just for variable names:

  git grep -I -n -E 'api[_-]?key=|apiKey=|Authorization: Bearer' $(git rev-list --all) -- \
    'tests/*' 'fixtures/*' '*.json' '*.csv' 2>/dev/null | head -50

I scanned config/ and claude_work from my side and found nothing — two hits, both prose ABOUT
tokens rather than tokens. Good sign for those, and it says nothing about the rest of the tree or
about history.

=== SCAN 3 — bulk CFBD data ===

1,716 raw files, ~3M records. Almost certainly gitignored for size, but confirm it has ALWAYS been
gitignored. Committing those is redistribution as raw data, which both licences prohibit outright —
CFBD's as much as the pack's.

  git log --all --full-history --diff-filter=A --name-only -- 'raw/*' 'data/raw/*' '*.parquet'

=== IF ANYTHING IS FOUND ===

Order matters, and rotation comes first:

  1. ROTATE the credential. A leaked key that no longer works is inert, and rotation is the only
     mitigation that actually holds once something has been public.
  2. THEN decide about history. git filter-repo or BFG can excise it, but rewriting history breaks
     every clone and does nothing about anything already fetched. It is worth doing before going
     public and close to worthless after.
  3. For pack content specifically, rotation is not available — you cannot un-license a file. If
     pack content is in history, the honest options are a fresh repo with squashed history, or
     staying private.

=== A STRUCTURAL FIX WORTH MAKING EITHER WAY ===

MOVE cfdb_model_pack OUT OF THE REPO TREE. Put it somewhere like ~/cfdb_model_pack and point the
notebook and loader paths at it via an env var.

A gitignore is a rule someone can break by accident. A file that is not in the directory cannot be
committed by any accident at all. Given the licence names public repositories explicitly, the
stronger control is worth the twenty minutes — and it removes 29 MB from every clone.

Same argument for saved_models/ and model_outputs/, which are pack-DERIVED. The licence permits
generated outputs for "personal analysis, academic research, or private projects" — and a public
GitHub repo is not obviously a private project. That is the same question we deferred on the website,
arriving through a different door.

=== PHASE 2 — BRING THE STORY INTO THE REPO (Marc's call, and I agree) ===

Only after scans 1-3 report clean. Then, and this is the part a recruiter actually reads:

A repo of dbt models looks like every other data repo. WHAT MAKES THIS ONE DIFFERENT IS THE PAPER
TRAIL — a decision log that records being wrong and what changed, 215 numbered acceptance criteria,
a licence boundary reasoned in writing, and 23 rounds of prompts showing how AI-assisted engineering
actually works. Almost nobody publishes that.

CREATE docs/ AND COPY IN — do not move, do not symlink; claude_work stays the working copy:

  docs/
    README.md                       <- reading guide, spec below. Write this LAST.
    decision_log.md                 124 KB. The centrepiece
    requirements.md                 <- cfdb_site_requirements.md, v1.3, 215 ACs
    publication_boundary.md         Licence reasoning, both regimes
    request_register.md             Includes the section admitting 9 dropped requests
    roadmap.md
    model_reconciliation.md         Claude Code's own read-only audit
    phase1_model_spec.md
    srv_sample_review.md            Column-by-column profile of all 17 serving views
    site_ia_and_layouts.md          The ESPN / CBS / NCAA competitive review
    team_identity_spec.md
    wireframe_v03.html              Clickable, 18 pages, light/dark
    wireframe_feedback.md
    working_agreement.md            <- CLAUDE.md. How the two agents divided labour
    page_to_mart_matrix_v3.xlsx
    data_dictionary.xlsx
    prompts/                        000_index + 001-023, unchanged filenames
    feedback/                       site_feedback_01 through 04

DO NOT COPY:

  supporting_files/                 MARC'S OWN BETTING SPREADSHEETS. Personal wagering history.
                                    Nothing in this repo needs them and they are nobody's business
  archive/                          scratch
  .DS_Store
  setup_checklist.md                see the scrub note — contains a live Databricks workspace URL
  setup_execution_plan.md           machine setup, low signal, some infra detail
  cfdb_wireframe.html               v0.1, superseded
  cfdb_wireframe_v02.html           v0.2, superseded
  cfdb_page_to_mart_matrix*.xlsx    v0 and v2, superseded by v3

  The iteration story is told BY the decision log. It does not need 140 KB of superseded binaries
  to prove it happened.

SCRUB BEFORE COMMITTING — I found these from my side:

  1. setup_checklist.md line 35 carries a LIVE DATABRICKS WORKSPACE URL including the org id:
     <databricks-workspace-url>
     Not a credential, but it is an identifiable endpoint against Marc's account. If that file is
     ever included, this line goes. I have it excluded above for exactly this reason.

  2. Grep the whole docs/ set for droplet hostname, IP, the loopback port, UFW rules and the
     cfdb_publish.sh allowlist. Prompt 015 in particular discusses the deploy-key design in detail.
     None of it is secret and obscurity is not security — but there is no upside to publishing an
     attacker's starting map, and redaction costs nothing.

  3. Marc's email appears in four files. He is putting it in the site footer deliberately, so DEFAULT
     IS KEEP — flag it rather than removing it, and let him decide.

  4. LICENCE CHECK ON THE DOCS THEMSELVES, and this one matters: grep docs/ for anything that
     REPRODUCES pack content rather than describing it. Describing the 42-column export contract is
     fine. Reproducing Prediction_Export_Schema_2026.md, headers.md or a chunk of training_data.csv
     is publishing pack files by another route. Prompts 005 and 006 and the model-pack decision-log
     entries are where to look.

  5. The docs are CANDID — Cowork recording being wrong four times, Marc's frustration in his own
     words, the register naming nine dropped requests. My read is that this is an ASSET: it reads as
     a practitioner managing AI tooling critically, which is a rarer signal than clean code. But it
     is Marc's reputation, not mine. Flag the specific passages so he chooses rather than discovers.

docs/README.md — THE HIGHEST-VALUE FILE IN THE WHOLE REPO. Write it last, keep it under a page:

  - What cfdb is, in three sentences
  - THE FIVE THINGS WORTH READING, in order, with one line each on why. My suggestion:
      1. decision_log.md          how decisions got made and unmade
      2. requirements.md          215 testable acceptance criteria
      3. publication_boundary.md  two licences, and what may be published under each
      4. srv_sample_review.md     what auditing your own data actually looks like
      5. prompts/                 the full AI-assisted build, unedited
  - A one-paragraph "what went wrong and what we changed" — the silent-null class, the green-and-
    useless pattern, the guard scoped by the thing it guards. THAT PARAGRAPH IS THE HIRE SIGNAL.
  - A link to the live site and a note that it is behind Cloudflare Access, with how to request it.

Also update the ROOT README to point at docs/README.md in the first screenful. A recruiter lands on
the root README and gives it about ninety seconds.

=== REPORT BACK ===

  - Scan 1, 2 and 3 output, including "clean" where clean.
  - What the root .gitignore currently covers, and since which commit.
  - config/api-docs.json is 170 KB of CFBD's OpenAPI spec, committed. Publicly documented anyway,
    but check whether CFBD's terms say anything about redistributing the spec — if unclear,
    reference it by URL rather than vendoring it.
  - Your own read on anything infrastructure-revealing at HEAD: droplet hostname or IP, the loopback
    port, UFW rules, the cfdb_publish.sh allowlist. Not secrets, and obscurity is not security, but
    there is no upside to publishing them and scrubbing costs nothing.

  - For PHASE 2: the docs/ manifest as you actually built it, every scrub you made, and every
    passage you thought Marc should read before it goes public.

DO NOT CHANGE VISIBILITY, AND DO NOT COMMIT docs/ UNTIL SCANS 1-3 ARE CLEAN. Report first; Marc
decides.
```

---

## The finding that decides this

The pack licence prohibits uploading pack files **to a public repository**, in those words. Twenty-nine
megabytes of pack files currently sit inside the repository directory.

If they have never been committed, this is a twenty-minute fix and the repo can go public with a
genuinely strong portfolio story. If they have been committed even once, no amount of `.gitignore`
helps — history is the whole repo — and the choice narrows to a squashed fresh repo or staying
private.

**Nothing is exposed today.** The repo returns 404, so it is still private and there is time to check
properly.

## Phase 2 is what makes this repo worth finding

The scans are the gate. **`docs/` is the reason to open the gate at all.**

A repo of dbt models and a Streamlit app looks like every other data-engineering portfolio. What
almost nobody publishes is the paper trail: a decision log that records being wrong four times and
what changed each time, 215 numbered acceptance criteria, a licence boundary reasoned in writing
before anything was built, and 23 rounds of prompts showing how the work was actually driven.

**Two things are deliberately excluded and worth naming.** `supporting_files/` holds Marc's own
betting spreadsheets — personal wagering history, no engineering value, nobody's business. And the
superseded wireframes and matrices are 140 KB of binaries proving an iteration the decision log
already narrates better.

**One thing is a genuine judgement call, and it is Marc's.** These documents are candid — Cowork
recording its own errors, Marc's frustration in his own words, a register that names nine requests
that were dropped. My read is that it reads as a practitioner managing AI tooling critically, which
in 2026 is a rarer and more useful signal than tidy code. But it is his reputation on the page, so
Claude Code is asked to flag the specific passages rather than assume.

## And one piece of good news from the licence

> *"Reference your analysis in public writing or discussion without publishing the pack files."*

So the portfolio story is **explicitly permitted**. Marc can publish his own code, describe the
architecture, discuss the results, and write about what the models did — he simply cannot publish the
pack itself. The thing he actually wants to show a recruiter is allowed; the 29 MB he does not need
to show is what has to move.
