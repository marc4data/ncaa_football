# Team identity: logos and colours — gap resolution

**Gap:** `dim_team` carries no `logos`, `color` or `alternate_color`. They exist in the raw `/teams` payload and were never selected into `stg_teams`. Wireframe v0.2 uses mascot marks and team-coloured accents throughout, so every one of those elements currently has no source.

**Resolution:** add the columns — but with three constraints that matter more than the columns themselves. Getting this wrong produces a site that looks fine on a demo team and falls apart on the long tail.

---

## Decision 1 — Team colour is identity chrome, never a data encoding

This is the important one, and it is easy to get wrong because team colours *feel* like a natural palette.

They aren't one. A colour used to encode data has to satisfy properties team colours cannot:

- **Distinguishability is not guaranteed.** Alabama vs Oklahoma is crimson against crimson. Michigan vs West Virginia is navy-and-gold against navy-and-gold. On a matchup page, a two-series chart coloured by team can be two indistinguishable series.
- **Colourblind separation is not guaranteed.** Roughly 8% of men have red-green deficiency. Red vs green rivalry pairs are common and collapse entirely.
- **Contrast against the surface is not guaranteed.** Some schools are near-white (Penn State white, Colorado gold), some near-black. Either fails against one of the two theme surfaces.
- **It breaks the "colour follows the entity" rule in reverse.** In a filtered leaderboard, teams enter and leave; if colour carries meaning, meaning changes as the filter changes.

**The rule:**

| Use | Allowed? |
|---|---|
| Small fixed swatch or left rule beside a team name | ✅ Yes |
| Backdrop behind a logo mark | ✅ Yes |
| Selected/active state on a team row | ✅ Yes, with contrast check |
| Chart series colour | ❌ No — use the validated categorical palette |
| Edge / PTL / win-probability encoding | ❌ No — that is the diverging blue↔red scale |
| Cover / DNC / status chips | ❌ No — those are status colours |
| Text colour | ❌ No |
| Large background fills behind body text | ❌ No |

Identity chrome tells you *whose row this is*. Data encoding tells you *what the number means*. Keeping those separate is what stops a matchup page becoming unreadable when two crimson teams play each other.

---

## Decision 2 — Compute contrast-safe variants in dbt, not in the app

Streamlit is display-only. So the colour arithmetic belongs in the model.

Add to `dim_team`:

| Column | Type | Meaning |
|---|---|---|
| `color_raw` | text | Exactly as landed. Never modified. |
| `alt_color_raw` | text | Exactly as landed. |
| `color_on_light` | text | Hex guaranteed ≥ 3:1 against the light surface |
| `color_on_dark` | text | Hex guaranteed ≥ 3:1 against the dark surface |
| `color_source` | text | `primary` \| `alternate` \| `adjusted` \| `fallback` — how the safe variant was derived |

**Algorithm** (per team, per surface):

1. Compute WCAG relative luminance of `color_raw`, then contrast ratio against the surface (light `#fcfcfb`, dark `#1a1a19`).
2. If ≥ 3:1, use it. `color_source = 'primary'`.
3. Else try `alt_color_raw` the same way. `color_source = 'alternate'`.
4. Else darken (for light surface) or lighten (for dark surface) the primary in fixed steps until it clears 3:1, preserving hue. `color_source = 'adjusted'`.
5. Else neutral grey. `color_source = 'fallback'`.

`color_source` is not decoration — it is how you find the teams whose brand colour is being altered, and it belongs in a data-quality view. If a large share come back `adjusted` or `fallback`, the design assumption is wrong, not the data.

Test: every FBS team has a non-null `color_on_light` and `color_on_dark`, and both clear 3:1. A model that can emit an unreadable colour has a bug.

---

## Decision 3 — Cache logo images; never hotlink

`/teams` returns `logos` as an **array of URLs pointing at a third-party CDN**. Hotlinking them means:

- Your site breaks when their CDN changes paths or blocks referrers.
- Page load depends on a third party you have no relationship with.
- Every visitor's browser makes requests to a domain you don't control.

**Instead:** an ingestion task fetches each logo once, stores it locally (object storage or the repo's static assets), and `dim_team` carries `logo_path` pointing at *your* copy plus `logo_source_url` for provenance. Re-fetch on a slow cadence — logos change once a decade.

Add `logo_path` and `logo_source_url`; keep the raw `logos` array too, since some teams ship both light and dark variants and you may want the second later.

---

## Decision 4 — Define the degraded states now, not when they appear

The FBS-spine-plus-opponent-stubs decision guarantees teams with no identity data. Non-FBS opponents will have partial or empty `/teams` records. Define fallbacks once and use them everywhere:

| Missing | Fallback |
|---|---|
| Logo | Monogram — up to 3 letters from the abbreviation, ink-on-neutral, same circular footprint as a real mark so layout never shifts |
| Both colours | Neutral grey swatch (`--line-strong`) |
| Primary only, fails contrast | `color_on_*` handles it; the app never sees the problem |
| Team entirely absent | "TBD" label, neutral swatch — happens with unannounced non-conference opponents |

**The layout must not move between the real and degraded state.** A monogram occupying the same box as a logo means a page of FCS opponents looks deliberate rather than broken.

---

## What changes in the wireframe

Nothing structural. The v0.2 mascot circles and team-colour accents stay exactly where they are — they were already drawn as identity chrome rather than data encoding, which is the behaviour this spec makes explicit. Three clarifications:

1. The diverging red/blue on PTL and edge columns is the **data** scale and is unrelated to team colour. Both can appear in the same row without conflict, because one sits in the team cell and the other in a numeric cell.
2. The Matchup page's efficiency comparison uses the **categorical palette**, not the two teams' colours — for the two-crimson-teams reason above.
3. Team colour may appear as a **thin left rule** on team rows in tables. That reads as identity at a glance without competing with the status chips.

---

## Work items

| # | Item | Where | Size |
|---|---|---|---|
| 1 | Select `color`, `alternate_color`, `logos` into `stg_teams` | dbt staging | XS |
| 2 | Promote `stg_teams` → `dim_team` in marts | dbt marts | S |
| 3 | Contrast-safe colour computation + `color_source` | dbt marts (macro) | M |
| 4 | Contrast tests on every FBS team | dbt tests | S |
| 5 | Logo fetch-and-cache task + `logo_path` | ingestion | M |
| 6 | Monogram fallback component | Streamlit | S |
| 7 | `color_source` distribution on System Overview | serving view | XS |

Items 1–2 are near-free and unblock the Teams index and Team page. Item 3 is the one with real content. Item 5 can lag — monograms everywhere is an acceptable interim and looks intentional.

---

## Open question for Marc

**Should `color_source = 'adjusted'` be visible to users?** A purist would say never alter a school's brand colour. The counter-argument is that an unreadable colour serves nobody, and the alteration is small and hue-preserving.

My recommendation: adjust silently in the UI, but surface the distribution on System Overview so *you* can see how often it happens. If it turns out that a third of FBS teams need adjustment, that is a signal to drop colour accents entirely rather than to keep patching them.
