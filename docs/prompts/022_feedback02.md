# cfdb prompt 022 — feedback 02, itemised

Source: `../claude_work/cfdb_site_feedback_02.md`. **Every item has an ID.** `cfdb_site_feedback_03.md`
checks them back by the same ID, so please report against these numbers.

---

```
Marc's second pass. Items are numbered F2-01 upward and grouped by priority. The verification doc
uses the same IDs, so report by number.

Two framing notes before the list.

FIRST: THEME AND TIMEZONE ARE ONE PROBLEM, NOT TWO.

  "It's night and the site reverts back to System/Dark even though I explicitly chose Light. Once I
   choose it, it should stick."
  "Is there a config/user situation where once somebody logs in and chooses MDT, future visits go
   MDT, and them choosing MDT doesn't impact other users that might want PDT or EDT?"

Both are PER-VIEWER PERSISTENT PREFERENCE, which Streamlit does not give you: session state dies
with the session, and anything server-side is shared. Solve it once —

  A single preferences store, per browser, holding at minimum: theme, timezone, and (worth
  considering) default season/week. Written on change, read on load, defaulting to the configured
  site defaults when absent.

  Mechanism is yours. A query param survives a bookmark but not a fresh visit; browser storage via a
  small component survives both. Whichever you pick, ONE store for all preferences — three
  independent mechanisms is how they drift.

  Marc's question answered: yes, per-viewer is exactly right, and it is the whole point. One user
  choosing Mountain must not move anyone else's clock. That falls out of client-side storage for
  free and is impossible with a server-side setting.

SECOND: I WAS WRONG ABOUT MATCHUP IN THE NAV, TWICE. TAKE IT OUT.

Marc asked for this in wireframe v0.2 and I pushed back. He asked again in feedback 01 and I
recommended keeping it with a picker. You built the picker. He has now used it and still says:

  "Take it out of the Nav pane. It doesn't need to be searchable, it's a click-through asset."

He has used the thing and I have not. Remove it. Keep the picker code — arriving at
/matchup with no game_id should still show it rather than erroring — but the page comes out of the
nav, same as Team page. Both are drill-throughs with real indexes pointing at them (Schedule and
Scores for games, Teams for teams).

=== P0 — BLOCKERS. Filters and preferences are still broken. ===

F2-01  FILTER PERSISTENCE IS STILL BROKEN. "I chose 2025 and Week 12 on Scores, navigated to
       Rankings, and it resets to current week (2026 W1)." Prompt 021 reported this fixed via
       GameScope.link(). It holds on some routes and not others — Rankings at minimum. Find the
       routes that drop it, and add a test that walks Scores -> Rankings -> Stats -> Teams asserting
       scope survives each hop.

F2-02  FILTER STATE IS STILL INVISIBLE. Stats: "No filters shown or declared, even if it's filtered
       from the previous page I navigated from." This is AC-G.18b and it is the one I flagged
       hardest. A page showing 2025 data with nothing on it saying "2025" is a way to be confidently
       wrong.

F2-03  THE FILTER BAR MUST RENDER ON EVERY DATA PAGE, even where a given filter does not apply.
       Marc asks for filters on Today (F2-13), Rankings (F2-21) and a week filter on Teams (F2-26).
       Teams is team x season grain so a week filter has no meaning there — but its ABSENCE is what
       makes the page feel broken. Render the bar consistently; show inapplicable filters DISABLED
       WITH A REASON on hover, not missing. Consistency of chrome beats per-page optimisation.

F2-04  THEME DOES NOT PERSIST. See the preferences store above.

F2-05  DATA DICTIONARY LINKS DO NOT DEEP-LINK. Reported on Schedule, Scores, Rankings and Teams.
       Prompt 021 item 4a asked for a per-table anchor. Either it did not land or the anchor is not
       resolving. On ODDS BOARD the dataset name is not a link at all (F2-33).

=== P1 — THE MOST-REPEATED COMPLAINT IN THE DOCUMENT ===

F2-06  COLUMN WIDTHS ARE INCONSISTENT ACROSS TABLES ON THE SAME PAGE. Marc raises this FIVE TIMES —
       Today, Stats, Teams, Team page, and again in cross-cutting: "If there are multiple tables on
       the same page and they have the same field layout, keep the column widths consistent."

       By frequency this is the number one item in the pass. When a page renders several tables of
       the same shape — Today and Schedule sub-grouped by date, Teams grouped by conference — every
       group reflows to its own content and the page reads as ragged. FIX IT ONCE, IN THE SHARED
       TABLE COMPONENT: a column layout computed from the full dataset before grouping, then applied
       to every group. Not per-table autofit.

       Same fix answers F2-14 (Today), F2-25 (Stats), F2-27 (Teams), F2-30 (Team page).

F2-07  DUPLICATE TEAM NAME WHERE THERE IS NO LOGO. Ohio Dominican and Northwestern (IA) render the
       name twice with the hover circle. Same bug as Oklahoma Panhandle in pass 01, and note the FBS
       filter did NOT remove these — they are opponents, so they legitimately appear. The monogram
       fallback appears to emit text alongside the name. MAKE THE TEAM NAME THE LINK, DROP THE
       CIRCLE, one affordance sitewide.

F2-08  FOOTER, part 1. "Built by Marc Alexander" + website link + email icon (marc4data@gmail.com) +
       LinkedIn icon.

F2-09  FOOTER, part 2. Replace "Attribution is optional under their terms; cfdb provides it anyway."
       with "Really cool site, check it out!"
       CAREFUL: that replaces the SENTENCE ABOUT attribution, not the attribution itself. The
       CollegeFootballData link stays — AC-G.43 requires it on every page. Marc is cutting the
       meta-commentary and replacing it with a plug, which is better copy. Do not remove the link.

=== P1 — MATCHUP AND ODDS BOARD, both structural ===

F2-10  MATCHUP HEADER LAYOUT IS WRONG. "Have a team on the left, then venue in the middle, then name
       of the home team on the right. Not natural." Use the universal convention: AWAY @ HOME, away
       on the left. Keep venue. ADD WEATHER. Show a team's ranking where it has one.

F2-11  MATCHUP OUT OF NAV. See above.

F2-12  ODDS BOARD NEEDS TO BE A DENSE BOARD, NOT A SET OF CARDS. Marc's full note is the spec:
         - a radio button to pick ONE provider, then
         - REMOVE the per-game sub-grouping — one row per game
         - no start/end time sub-grouping
         - matchup detail becomes an inline link or icon on the row
         - filters/sorting to look at sections of the market — spread, total, moneyline
       Rationale worth keeping: "This page will be accessed in the days leading into kickoff." It is
       a scanning surface. AC-11.8 already says table not cards; this is what that means in practice.

=== P2 — PAGE-LEVEL, mostly small ===

F2-13  Today: needs the standard filter bar (see F2-03)
F2-14  Today: consistent column widths across the date sub-tables (F2-06)
F2-15  Today: kickoff cell shows the date again — TIME ONLY, the group header carries the day
F2-16  Today: the dataset name is repeated on every sub-table. ONE at the top of the page is enough
F2-17  Today: no TV / media data. raw/games_media is landed and unmodelled — small staging model
F2-18  Schedule: REMOVE the venue column. Venue belongs on Matchup
F2-19  Schedule: add a neutral-site indicator column
F2-20  Schedule: weather icon (sun / cloud / wind / snow) plus expected temperature
F2-21  Rankings: needs the filter bar (F2-03)
F2-22  Rankings: Compare tab headers must sort. This is AC-2.8, still unmet — a violation, not a request
F2-23  Scores: add a winner indicator, e.g. a caret beside the winning team
F2-24  Scores: THE UPSET SCALE IS UNDOCUMENTED. "What's the split between !, !!, !!! — where does the
       end-user see that?" A glyph nobody can decode is decoration. Give the column header a tooltip
       or the page a one-line legend stating the thresholds, and put the definition in the Data
       Dictionary entry
F2-25  Stats: consistent column widths (F2-06)
F2-26  Teams: filter bar present, week disabled with a reason (F2-03)
F2-27  Teams: consistent column widths (F2-06)
F2-28  Team page: bye-week row. Season x week spine, left join. NOTE: dim_week has a hard 2002 floor
       from /calendar, so scope bye weeks to 2002+ and say so rather than synthesising earlier ones
F2-29  Team page, Schedule tab: per-game stats — yards (total / rush / pass), yards allowed (total /
       rush / pass), net turnovers, penalty yards. Most are in fct_game_team already; net turnovers
       is takeaways minus giveaways at team grain
F2-30  Team page: consistent column widths (F2-06)

=== P3 — REAL WORK, not this week ===

F2-31  STANDINGS BY WEEK, AND THE BUMP CHART. Marc: "No Week filter in Standings. Is it possible? If
       so, then we should be able to add a bump chart to show how the season unfolds."
       Possible, and it is a MODEL CHANGE not a UI toggle. srv_standings is team x season. Standings
       as-of-week needs team x season x week, cumulative from fct_game_team. That is a new fact or a
       windowed view over an existing one, and it unlocks the bump chart for free. Worth doing —
       "how did the SEC actually unfold" is a genuinely good page — but it is not a filter.

F2-32  DATA DICTIONARY SCOPE. Marc: "Don't understand why anything below srv_ is included... can't
       violate the concept that only fully processed and curated data is available on this site."
       He is right about the PROMISE even though the licence permits descriptive metadata about any
       layer. If the site says it serves only curated data, a dictionary listing raw tables invites
       "so where is that?"
       RESOLUTION: the Data Dictionary defaults to SERVING ONLY. Other layers move behind an
       explicit toggle, or to System Overview where the reader is a builder. And the architecture
       story gets told by F2-34 instead, which tells it better anyway.

F2-33  Odds Board: the dataset name is not a link at all — fix with F2-05

F2-34  A PIPELINE DIAGRAM. Marc asks for this twice — as dbt lineage on Data Dictionary, and as a
       visual on Methodology covering "data flowing through the pipelines, DQ checks,
       transformations, API calls vs Droplet, security."
       THIS IS COWORK'S, NOT YOURS. I am drafting it as a Mermaid diagram you can drop into the page
       — one source, rendered on Methodology, referenced from Data Dictionary. It resolves F2-32
       neatly: the DIAGRAM shows the whole pipeline including raw, the DICTIONARY documents only what
       is served. Architecture story told, promise intact.

=== NOT REPORTED, AND WORTH NOTING ===

Edge Finder, Model Performance, Line Movement, System Overview and Players were marked "didn't get
to it" — so we still have no read on four pages, two of which Marc named as the ones he would show a
recruiter. The device matrix is blank for the second pass running. Neither is a criticism; it just
means those are unknowns rather than fine.

Excel: "The column width changes are good... this is a great start and proves what's possible."
```
