# cfdb prompt 021 — Marc's second pass, and one thing that's now a `W!`

Four days to Week 0. Priority order below is deliberate: items 1–3 first, the rest as they fit.

---

```
The onclick finding is worth ten minutes before the list.

=== THE FRAMEWORK DELETED THE MECHANISM, AND THE CRITERION CAUGHT IT ANYWAY ===

Streamlit's markdown sanitiser strips event handlers, so onclick on a <tr> rendered a pointer cursor
attached to nothing. No error, no warning. That is the ->> '0' shape again — SOMETHING UPSTREAM
SILENTLY REMOVED A THING THAT LOOKED PRESENT.

Add it to the class list. It now has three members: an accessor that returns null on type mismatch,
a selector that narrows a guard out of existence, and a sanitiser that strips a handler. All three
leave the code looking correct.

But the part I want to record is that AC-G.13 WOULD HAVE FAILED IT EVEN IF IT HAD WORKED. The
criterion says middle-click or copy-link must yield a working URL — a property of the result, not a
description of the mechanism. A JS handler gives neither. That is the difference between a criterion
that specifies an OBSERVABLE and one that specifies an IMPLEMENTATION, and it is why this one held
up when several of mine have not. Worth copying the pattern.

And team_cell accepting slug_field and ignoring it for weeks is its own small class: A FUNCTION THAT
TAKES AN ARGUMENT IT DOES NOT USE. Nothing errors, the call site looks right, and the behaviour is
wrong. If flake8 is not already catching unused parameters, turning that on is cheap.

=== 1. THE FILTER IS NOW INVISIBLE STATE. That is worse than not persisting. ===

  Marc: "I filtered Standings on Season = 2025 then navigated to Stats and it's still filtered to
  2025, which I think is correct, but there's nothing on the page indicating the filter or the year.
  URL shows it, but we can do better than that."

He is right, and I would upgrade this from a note to a `W!`. A persistent filter that is not visible
is a TRAP: a user lands on Stats, sees 2025 numbers, and reads them as current. Not persisting was a
bug. Persisting silently is a way to be confidently wrong, which is the failure mode this whole
project is organised against.

REQUIRED, and it is small:
  - The filter bar renders CURRENT VALUES ALWAYS, on every page that has one — including values
    inherited from another page.
  - Any value that is NOT the default is visually marked — a highlight, a bolder chip, whatever
    reads at a glance.
  - A one-click "reset to current season" affordance when anything is off-default.

New criterion AC-G.18b, added to the requirements.

=== 2. TIMEZONE — DECIDED: Pacific. But make it a setting, not a constant. ===

Marc's call: default Pacific, and the "as of" timestamp in Pacific rather than UTC.

Your recommendation to defer viewer-local was right and I agree — a custom component is a new
failure mode four days out. But do NOT hardcode Pacific either. ONE CONFIGURED DEFAULT, read from
config, applied everywhere including the as-of stamp. Then viewer-local after Week 0 is a change to
how that value is resolved, not a hunt through the codebase.

Worth stating on the page, since it cuts against convention: ESPN and CBS publish kickoffs in
Eastern, so a user comparing tabs will see different numbers. That is fine as long as the zone
abbreviation is always shown — which AC-G.34 already requires. "7:30 PM PDT" is unambiguous;
"7:30 PM" is not.

=== 3. NAVIGATION — remove Team page from nav. Keep Matchup. ===

Marc: "Team page should not be in Nav Pane."

Agreed, and the distinction from Matchup is worth being explicit about, because we just went the
other way on that one:

  MATCHUP had no index. Nothing enumerated games as a way of choosing one, so removing it from nav
    would have left it unreachable except by luck. It got a picker.
  TEAM PAGE HAS an index. Teams IS the picker — searchable, conference-filtered, 681 cards. A nav
    entry that lands on an arbitrary team is strictly worse than the index that already exists.

So: remove from nav, reachable from Teams and from every team link on the site. The page count stays
18; this is a nav decision, not a scope one. AC-G.51 is about BLOCKED pages staying visible and does
not apply.

=== 4. DATA DICTIONARY — two changes, and one interaction to be careful about ===

  a. The "Dataset: Schedule" link must land ON THE TABLE, not the top of the page. Anchor per table,
     and the anchor is part of the URL contract per AC-G.10.

  b. Schema tabs across the top, ordered left to right by pipeline position: Raw -> Staging -> Marts
     -> Serving. Good idea — it makes the architecture legible to exactly the audience Marc says
     opens this page.

  CAREFUL, and this is the reason I am flagging it rather than just agreeing: Marc also asked
  earlier for a "preview top N rows" button on this page. SCHEMA TABS PLUS ROW PREVIEW IS A WAY TO
  READ raw.*, WHICH THE PUBLICATION BOUNDARY PROHIBITS OUTRIGHT — all 65 tables, no exceptions.

  The distinction that keeps both features: DESCRIPTIVE METADATA about any layer is permitted — the
  boundary doc says so explicitly, "descriptive metadata about fields, not the data itself." ROW
  PREVIEW IS THE DATA, and it is SERVING ONLY. So the tabs can show all four layers; the preview
  button renders only on the Serving tab, and is absent — not disabled — elsewhere.

  Build the tabs now. The preview is backlog, and when it comes it comes with that constraint.

=== 5. BYE WEEKS — your instinct is right and there is a wrinkle ===

Marc: build a season x week spine, left join from it.

That is the textbook answer: a conformed week dimension driving an outer join, so an absent game
becomes a rendered gap rather than a missing row. dim_week already exists.

THE WRINKLE, from the 2026-08-17 audit: /calendar HAS A HARD 2002 FLOOR. No data before then, while
stg_games covers 1869-2026. So a dim_week-driven spine gives correct bye weeks from 2002 forward and
nothing before it.

Options: derive the week spine from the games themselves for pre-2002 seasons, or scope bye-week
rendering to 2002+ and say so. I would take the second — nobody is studying Alabama's 1934 bye week,
and an honest scope note beats a synthesised spine.

=== 6. SCHEDULE / SCORES — the two-destination problem Marc surfaced ===

He offered two options. Take the second one:

  Row/game area -> Matchup, via an EXPLICIT AFFORDANCE — a small "Details" or box-score icon
  Team name    -> Team page

The reason: right now both destinations exist and a user cannot tell them apart, which is why he
proposed collapsing them. An explicit icon fixes discoverability without losing the team link. AC-2.5
already requires the two to be "visually distinct" — the icon is what makes that true rather than
asserted.

Do not take option one. Routing every team click to Matchup would make Team page unreachable from
the two most-visited pages on the site.

=== 7. SMALLER, MOSTLY MECHANICAL ===

  Scores: the Upset column header reads "!" — make it "Upset". The GLYPHS are !/!!/!!!; the HEADER
    is a word. A column whose header is a punctuation mark is a puzzle.
  Rankings: column headers do not sort. That is AC-2.8, which requires sortable headers everywhere,
    so it is a violation rather than a request. Add week tabs while you are in there so a reader can
    jump back to an earlier week's state.
  Teams: Oklahoma Panhandle renders its name twice with a circle that becomes "?" on hover. Two
    things — (a) the duplicate name looks like the monogram fallback also emitting text; (b) that
    hover circle is the same unexplained "info" affordance Marc flagged on Team page. MAKE THE TEAM
    NAME THE LINK AND DROP THE CIRCLE, consistently across the site. One affordance, one meaning.
    Note Oklahoma Panhandle is Division II, so the FBS spine may remove it from this page entirely —
    check whether the bug survives the filter before building a fix for it.
  Teams: standardise the column split across conferences so the grid does not reflow per group.
  Team page / Schedule: add total yards, rushing yards, passing yards, yards allowed and NET
    TURNOVERS. Most of these already populate in fct_game_team — you listed first_downs,
    total_yards, rushing_yards, passing_yards and turnovers as landing in the rehearsal. Net
    turnovers needs both sides of the game, so it is takeaways minus giveaways at team grain.

=== 8. BACKLOG, not this week ===

  Compact vs tiled toggle on Schedule and Scores, CBS-style. Good idea, real work.
  Distribution sparkline — still the most differentiating item on the list.
  Data Dictionary row preview, serving-only, per item 4.

=== STILL OUTSTANDING FROM BEFORE ===

Dark-theme green · skipped-test reporting · sync_freshness · Methodology copy (mine, drafting).

Agreed on Cloudflare Web Analytics — "mixing did-the-DAG-run with how-many-people-visited makes it
two dashboards wearing one hat" is exactly right and I am stealing that sentence.
```
