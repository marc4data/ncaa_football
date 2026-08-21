# cfdb prompt 020 — Marc's walkthrough: the deep-link contract was never built

Marc walked the site. Full notes in `../claude_work/cfdb_site_feedback.md`. **The headline is a global
contract item, not a page defect.**

---

```
Marc's answer to "what's the single worst thing about it right now" was one line: MISSING HYPERLINKS.

That is not a feature request. It is requirements section 0.3, and it was never built.

=== BLOCKER 1 — THE DEEP-LINK CONTRACT. Nothing on the site is clickable. ===

  [B!] Click a game row -> correct Matchup       "no hyperlink"
  [B!] Click a team name -> correct Team page    "no hyperlink"
  [M ] Teams: clicking a team should go to Team page
  [M ] Schedule: clicking a game should go to Matchup

Already specified, four places, all unmet:

  AC-2.5   Schedule: row click -> Matchup?game_id=. Team name click -> Team?team=. Visually distinct.
  AC-5.4   Standings: team click -> Team page
  AC-7.5   Teams: card click -> Team?team=&season=
  AC-8.7   Team page: game log rows click through to Matchup
  AC-G.13  Every clickable row navigates by WRITING QUERY PARAMS, never by mutating session state.
           Middle-click or copy-link on any row yields a working URL.

This is the single highest-value fix on the site. Every page is currently a terminus — a user lands,
reads, and has nowhere to go. It is also why Matchup looks broken (see below): nothing points at it,
so the only way to reach it is the nav entry, which was never meant to be the main route.

Do this before anything else in this document.

=== BLOCKER 2 — FILTERS DO NOT PERSIST, AND THEY ARE IN THE WRONG PLACE ===

  [B!] "When I chose Season = 2025 to see some results, then navigate to other pages, the Season
       filter reverts back to the 2026 default. Season should be a global filter."

AC-G.18 requires filter state to round-trip through the URL. Section 0.4 requires global filters to
persist across page navigation. Both unmet.

AND A REQUIREMENTS CHANGE, Marc's call and I agree with it:

  FILTERS MOVE TO THE TOP OF THE PAGE, ABOVE THE FOLD — a horizontal row under the page title, not
  the sidebar. Section 0.4 said sidebar; that was my call and it was wrong. Every sports site puts
  season/week controls at the top of the content because that is where the eye lands, and the
  sidebar is nav.

  Requirements amended. Global filters (season, week, division/classification) render as a persistent
  horizontal bar at the top of every data page, and they SURVIVE NAVIGATION.

=== BLOCKER 3 — MATCHUP FROM THE NAV IS BROKEN, AND I ARGUED FOR THAT NAV ENTRY ===

  [B] "If I navigate to this page directly, it has the top X games showing, looks like it's sorted
      by date desc. Totally not functional."
  [B] "Can't navigate within the shown dataset functionally... might be the argument for not having
      it show in the Nav pane. This is a drill-thru page that's only accessed when the gameid
      context is provided."

Marc is right and I was wrong. In wireframe v0.2 he questioned whether Matchup needed a nav slot and
I pushed back, arguing a decision surface should be directly reachable. The live page settles it: an
arbitrary list of games sorted by date is not a decision surface, it is a broken index.

TWO OPTIONS. My recommendation is (a):

  (a) KEEP IT IN NAV, MAKE IT A REAL PICKER. Arriving with no game_id renders a proper game selector —
      week filter, conference filter, searchable, grouped by day — that then routes to the matchup.
      This is AC-10.1 as amended, and it also fixes Marc's "[M] Filter for Week/Conference".
  (b) REMOVE FROM NAV. Drill-through only, reachable from any game row. Simpler, and honest about
      what the page is.

(a) is better because it gives the page a job when someone lands on it cold, and the picker is
mostly the Schedule page's filter row reused. But do NOT keep the current behaviour — an unfiltered
list is worse than either option.

Note this only became visible because nothing links to Matchup. Fix Blocker 1 first and this page
starts being reached the way it was designed to be.

=== SCOPE DECISION FROM MARC — THIS SIMPLIFIES THINGS ===

  "Should be an FBS website. We don't need any of the other levels. If a game includes an FBS and
   non-FBS team, it should be included."
  [A!] "There should be a global filter that defaults to FBS and includes games where either team
       is FBS."

So: FBS SPINE, and the inclusion rule for games is EITHER team FBS, not both. Non-FBS teams remain
as opponents — with names, colours and slugs, which is exactly the identity work you just did, so
none of that was wasted. They simply do not get their own index rows, standings rows or team pages.

This is a global filter with a default, not a hardcoded WHERE. Someone should still be able to widen
it.

=== TIME AND DATE — a requirements change, with an implementation wrinkle ===

  [C] "Times are US Eastern with the zone shown - should dynamically match end-user's timezone"
  [C] Today: "getting word wrap on the date time. Each date is a separate table, so no need for the
      long-form date in the kickoff field, reduce to H:MM AM/PM"
  "Date format Aug 20, 2026. Time format H:MM AM/PM PDT"

AC-G.34 said US Eastern, fixed. Amended: VIEWER-LOCAL TIMEZONE, with the zone abbreviation shown.

THE WRINKLE, and I would rather flag it than have you discover it: Streamlit renders server-side, so
the server does not know the viewer's timezone without help. Options, cheapest first —

  1. A small JS component that reads Intl.DateTimeFormat().resolvedOptions().timeZone once and
     stores it in a query param or session. One-time cost, correct thereafter.
  2. A timezone picker in the filter bar, defaulting to Eastern, persisted like other filters.
  3. Render UTC offsets client-side with a formatting hook.

Pick whichever is least fragile. If all three are more expensive than they look, say so and we keep
Eastern with the zone shown clearly — that is a defensible v1 for a US college football site.

Formats regardless: dates as "Aug 20, 2026". Times as "7:30 PM PDT". On a page already grouped by
day, the kickoff cell carries TIME ONLY — that fixes the word wrap.

=== FRONT OF HOUSE SHOULD NOT SPEAK IN TABLE NAMES ===

  [A!] "On each page, where the data model is indicated, it should be a hyperlink to the
       corresponding table in the Data Dictionary. Probably change the presentation to
       'Dataset: Schedule' instead of 'srv_schedule'."

Good, and it refines a rule of mine that was too blunt. AC-G.7 says a Degraded section must name the
missing object in code font. That is right for BACK OF HOUSE and wrong for front of house.

Amended: front-of-house pages show a FRIENDLY DATASET NAME, hyperlinked to that table's Data
Dictionary entry — "Dataset: Schedule". Back of house (System Overview) and Degraded states keep the
literal object name, because there the reader is a builder and the exact identifier is the point.

=== EVERYTHING ELSE, TRIAGED ===

WEEK-0 SMALL FIXES

  Footer: the CFBD attribution is not rendering as a hyperlink. Change the copy to "Data sourced
    from the CollegeFootballData API", linked.
  Add LinkedIn (https://www.linkedin.com/in/marc4data/) and https://marc4data.netlify.app/ to the
    footer. This site is a portfolio piece; the links are part of the point.
  Scores: margin shows a decimal - remove it. Integers.
  Scores: the Upset indicator eats too much width. Marc suggests "!", "!!", "!!!" by degree.
  Teams: remove the Mascot column, no value.
  Teams: [A!] conference filter missing.
  Team page: instead of an H/A column, prefix away games with "@ " before the opponent name. That is
    the universal convention and it saves a column.
  Dark theme: green reads too bright/high-contrast. Cincinnati's colour does not work on dark.
  Team page: [C] there is an "info" button next to the team name whose purpose is unclear — either
    give it a tooltip that explains itself or remove it.

EXCEL EXPORT — one real bug, and Marc likes the rest ("by and large, this is pretty awesome")

  Columns are not width-adjusted: some show ####### , others are far too wide. Marc's own suggested
  approach is sound — autofit, then insert the header rows, then freeze panes, so the header text
  does not blow out column 1. Cap max width so a long description column does not run to 200 chars.

BACKLOG — real value, not this week

  Scores: total points · last-snapshot spread · did-the-favourite-cover indicator · total yards
    (both teams) · a small win indicator next to the score
  Schedule: TV/network column is empty (raw/games_media is landed but unmodelled) · weather
    indicator with temp · a header note explaining that a negative spread means the home team is
    favoured
  Team page: a KPI banner of season totals on Overview · a bye-week row in the schedule tab · a
    glossary footer under the ratings table explaining each metric
  Teams: season totals for yards / rushing / passing, and the same allowed
  Data Dictionary: a "preview top N rows" button with a simple filter builder (field, operator,
    value). SCOPE IT — 100 rows max, no export, serving only. It is inside the publication boundary
    because everything in serving is publishable, but an unbounded version drifts toward the
    "pull the whole database" line the boundary exists to hold.
  DISTRIBUTION SPARKLINE — Marc asked for this twice, so it matters to him: alongside a percentile,
    an inline histogram of the metric across the population, 20 bins, the current row's bin
    highlighted, with labelled ticks at the lower bound, upper bound and midpoint. It pairs with
    rating_population — the histogram shows the shape, the n says how many. Good V1.5 candidate and
    genuinely differentiating.

QUESTION BACK TO YOU

  System Overview: Marc asks whether site usage stats belong there or whether Cloudflare should
  handle it. Cloudflare Web Analytics is free, needs no cookie banner and requires no code beyond a
  snippet — I think that is the right answer and System Overview stays about the PIPELINE. Confirm
  or push back.
```

---

## Two things that are mine, not Code's

**The Methodology page needs a correction, and Marc is right about the substance.** He flagged the
"what the model is and is not" section as inaccurate: the pack is a starting point, the model gets
tuned, and the predictions become cfdb's own.

That's true about **authorship**, and the copy should say so — "cfdb's own models, trained on a
licensed feature store" rather than anything implying the predictions are the pack's.

But it changes nothing about the **licence**, and the rewrite must not blur that: the training data
is still Rad Sports Analytics', commercial use is still prohibited without written permission, and
the outputs still may not be presented as official CollegeFootballData.com predictions. Tuning a
model doesn't relicense what it was trained on. I'll draft the replacement copy so both things stay
true.

**The auth friction is worth solving properly.** Email PIN on every session is genuinely bad, and
Cloudflare Access has better options for exactly this case: swap the one-time-PIN identity provider
for **Google sign-in** (or GitHub), which most of your group already has, and raise the session
duration — Access supports up to a month. That's a config change in the Access application, not
code. It keeps the allowlist model that the publication boundary leans on, so nothing about the
licence posture changes.
