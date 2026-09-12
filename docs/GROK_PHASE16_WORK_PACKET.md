# Grok Work Packet — Phase 16 Vision Benchmark Foundation

## Branch

Create `grok/full-app-phase16-vision-benchmark` from the newest
`claude/pc-work-continuation-s4bv4c` only after the roadmap PR is merged.

## Objective

Create a reproducible offline benchmark for the football-vision pipeline before
changing models. TruGrade must know whether a change improves or damages
player identification and evidence quality.

## Owned paths

- `backend/evaluation/**`
- `backend/tests/test_vision_benchmark*.py`
- benchmark documentation and JSON schemas under `docs/vision/`
- tiny synthetic test fixtures under `backend/tests/fixtures/vision/`

Do not change frontend code, runtime detector/tracker behavior, Render config,
Python dependencies, database schema, AI providers, official grading rules, or
scoring values in this PR.

## Required work

1. Define a versioned ground-truth manifest for videos, frames, player boxes,
   track identity, jersey readings, field points, ball boxes, pose association,
   contact candidates, and play boundaries.
2. Define prediction adapters for the current stored detection, track,
   calibration, biomechanics, identity, and play JSON formats.
3. Calculate at minimum:
   - player precision/recall and IoU;
   - ID switches, fragmentation, and track coverage;
   - jersey top-1 accuracy plus abstention precision/recall;
   - field reprojection error and verified/estimated separation;
   - ball precision/recall and player-pose association accuracy;
   - contact-candidate precision/recall without calling proximity a tackle;
   - snap/end boundary error and play-detection precision/recall.
4. Emit machine-readable JSON and a readable summary.
5. Treat missing labels as excluded, not negative or zero.
6. Add deterministic unit tests with small synthetic fixtures.
7. Document how the owner can add private labeled film without committing film
   or personally identifying data to GitHub.

## Acceptance tests

- benchmark results are deterministic;
- unknown/missing labels do not lower an accuracy score;
- identity abstention is measured separately from wrong identification;
- estimated calibration cannot pass a verified-yardage gate;
- no benchmark fixture can enter a user-facing report path;
- existing tests remain green.

## Pull request report

Report schema version, metrics, commands, tests, and limitations. Do not claim
production accuracy from synthetic fixtures, and do not merge the PR.

