# Phase 16 — UI foundation migration note

The single-file `frontend/index.html` application is now a Vite + React +
TypeScript app under `frontend/src/`. This is a structural migration: the
visual design, copy and working behaviour are carried over, and no endpoint
shape changed.

## What moved where

| Phase 15 | Phase 16 |
| --- | --- |
| `<style>` block, lines 15–333 | `src/styles/app.css` (verbatim, plus a marked Phase 16 block at the end) |
| SVG sprite | `src/components/IconSprite.tsx` — same `ic-*` ids |
| `.shell` + `.sidebar` markup | `src/components/AppShell.tsx`, `src/components/Sidebar.tsx`, `src/navigation.ts` |
| `#view-app` | `src/features/profile/CreateProfilePage.tsx` |
| `#report` rendering (`run`, `renderFilmAnalysis`) | `src/features/profile/TruthReportPanel.tsx` |
| `handleFile`, `handleYoutubeUrl`, `_submitFilm` | `src/features/profile/useFilmJob.ts` |
| `#view-filmanalysis` | `src/features/film/FilmAnalysisPage.tsx` |
| every `v2*` function | `src/features/film/useFilmAnalysis.ts` |
| `v2DrawOverlay` | `src/features/film/overlay.ts` |
| the 14 `soon` views | `src/pages/account.tsx`, `src/pages/athlete.tsx`, `src/pages/coach.tsx` |
| `MATRIX`, `LADDER`, `runSieve`, `tierStars` | `src/lib/metricSieve.ts` |
| `RANK_ORDER`, `gradeDown`, … | `src/lib/makeupGrade.ts` |
| every `fetch` call | `src/api/client.ts` + `src/api/types.ts` |
| base-URL rule | `src/api/base.ts` |

`frontend/scripts/check.mjs` and `frontend/scripts/build.mjs` are deleted; they
asserted on the inline-script structure that no longer exists.

## Routes

`showView()` toggled `hidden` on sixteen sibling divs, so every screen shared
one URL. Each now has a path:

- `/` — Create Profile (`/#report` scrolls to the Truth Report, as the sidebar
  entry always did)
- `/film-analysis` — Film Analysis
- `/login`, `/create-account`, `/account`
- `/athlete/dashboard`, `/athlete/film-report`, `/athlete/traits`,
  `/athlete/recruiting`, `/athlete/offers`, `/athlete/public-rating`
- `/coach/dashboard`, `/coach/board`, `/coach/player-profile`,
  `/coach/360-report`, `/coach/genesis`

An unknown path redirects to `/` rather than inventing an error screen.

## Behaviour preserved

- UNKNOWN traits render as `UNKNOWN`, never as `0`. A missing confidence renders
  as `Confidence —`.
- Grade and confidence stay separate readouts.
- Evidence rows keep exact timestamps and seek the video to them.
- Manual track confirmation still posts `reason: "Human confirmed identity in
  Film Analysis"`, and an uncertain automatic match still refuses to pick a
  track.
- Long-film upload still goes through the async job endpoint with the same 5s
  (Create Profile) and 3s (Film Analysis) poll intervals.
- The metric sieve is a line-for-line port, game-changer escape hatch included.
- No unfinished view fabricates data; each states that it holds none.

## Deliberate changes

1. **Position is now a select.** It was a free-text input, so a typo produced
   "Unsupported TruGrade position" from the Truth Report. The select offers the
   13 positions with a rules file in `backend/grading/rules/` — QB, RB, WR, Y,
   H, OT, IOL, DT, DE, JACK, LB, CB, SAFETY — and `normalizePosition()` mirrors
   `POSITION_ALIASES` so DB/DL/OL/TE/S still resolve.
2. **Profile fields moved into shared state.** `v2StartAutomaticIdentity` read
   `#playerNumber` and `#schoolColors` off the Create Profile view. With real
   routes those inputs no longer share a document, so both views read the same
   `ProfileContext`.
3. **PWA assets are files, not data URIs.** The icons and manifest were ~600KB
   of base64 in the head. The same image bytes now sit in `frontend/public/`,
   and the manifest references them by path. `index.html` went from 621,571
   bytes to 901.
4. **Responsive sidebar and accessibility.** Below 860px the rail becomes a
   drawer behind a Menu button (Escape and a scrim close it); there is a skip
   link, visible focus rings, and `role="status"` on the progress, lookup and
   assignment messages.

## Not preserved — needs a follow-up

**`GET /` no longer serves a working page.** `app/main.py` reads
`frontend/index.html` as text and returns it. That file is now a Vite entry
whose only script tag is `/src/main.tsx`, which a browser cannot resolve in
production. Backend changes are out of scope for this packet, so the follow-up
is a one-line change plus a static mount:

```python
app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")
_FRONTEND_PATH = Path(__file__).resolve().parent.parent / "frontend" / "dist" / "index.html"
```

and a `npm --prefix frontend ci && npm --prefix frontend run build` step in the
Docker build. Until that lands, the deployed `/` route will not render.

## Outside the packet's owned paths

`.github/workflows/ci.yml` called the two deleted scripts. Its frontend steps
now run `npm install`, `npm run typecheck`, `npm test` and `npm run build`.
`.gitignore` gained `node_modules/`.

## Sieve position on Create Profile

`run()` hardcoded `pos = "DB"`, and it still does. The sieve's taxonomy
(`app/services/metric_sieve.py`: QB, RB, WR, TE, OL, DL, DE, LB, DB) is a
different list from the 13 graded positions, and choosing one here would change
what the report claims about an athlete. Left as-is deliberately.
