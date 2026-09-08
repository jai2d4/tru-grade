# Claude Work Packet — Phase 16 UI Foundation

## Branch

Create `claude/full-app-phase16-ui-foundation` from the newest
`claude/pc-work-continuation-s4bv4c` only after the roadmap PR is merged.

## Objective

Migrate the existing `frontend/index.html` application to React, TypeScript,
and Vite while preserving its visual design and working behavior. This is a
structural migration, not a redesign and not permission to fabricate product
data.

## Owned paths

- `frontend/**`
- frontend-specific tests under `tests/` only when required
- a short UI migration note under `docs/`

Do not change backend code, Render configuration, Python dependencies,
database schema, position rules, grading math, or the official logo asset.

## Required work

1. Capture the current routes, views, copy, styles, and working interactions.
2. Create a normal Vite React TypeScript structure under `frontend/src/`.
3. Componentize the shell, sidebar, profile form, Film Analysis workspace,
   video/overlay, job progress, play timeline, Truth Report, and evidence panel.
4. Add real URL routing so reload/back/forward preserve the selected page.
5. Add a typed API client for the existing endpoints. Do not change endpoint
   shapes in this PR.
6. Preserve UNKNOWN handling, separate grade/confidence display, exact evidence
   timestamps, manual track confirmation, long-film upload, and job polling.
7. Replace free-text position with the 13 supported TruGrade positions.
8. Preserve all unfinished views as honest unavailable states; do not populate
   them with demo numbers or fake recruiting activity.
9. Make the sidebar responsive and add keyboard/focus/status accessibility.
10. Keep the official `assets/trugrade-logo.jpg` branding unchanged.

## Acceptance tests

- `npm run typecheck`
- `npm run build`
- route-level tests for Create Profile and Film Analysis
- upload and report requests use the same payloads as the current application
- browser refresh retains the active route
- mobile navigation is usable at 390 CSS pixels
- no `soon` screen presents generated data as real

## Pull request report

List files moved/created, behavior preserved, typecheck/build/test results, and
any current behavior that could not be preserved. Do not merge the PR.

