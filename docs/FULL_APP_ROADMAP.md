# TruGrade Full Application Roadmap

Status: approved direction, September 8, 2026

This roadmap is based on the repository that actually exists. It does not
claim that placeholder screens or prototype computer-vision logic are finished.

## Non-negotiable product rules

1. External AI may describe evidence, but only the deterministic TruGrade
   engine may calculate official grades.
2. Unclear film is `unknown`; it is never converted to a fabricated event or
   a zero score.
3. Every scored event must link to the correct video, play, track, frames, and
   timestamp range.
4. A human correction must retain the original value, replacement value,
   timestamp, reason, and source.
5. Position traits and weights change only from owner-supplied methodology.
6. Player data from the internet is accepted only with sources. GPA,
   measurements, character, and academics are never inferred.
7. The current TruGrade visual language and official logo are preserved.
8. Learning AI may improve observation models, confidence calibration, and
   review prioritization. It may not rewrite official TruGrade rules or promote
   itself into production.

## Verified current state

- The live frontend is a single `frontend/index.html`, not React/Vite source.
- Film upload, frame extraction, generic YOLO detection, prototype tracking,
  cautious jersey selection, estimated field calibration, pose/ball/contact
  evidence, deterministic position rules, and a Phase 15 Truth Report exist.
- Twelve sidebar destinations are still labeled `soon` and are placeholders.
- The legacy `/api/v1` athlete/evaluation system uses PostgreSQL, while the V2
  `/api` film pipeline uses local JSON and files. They are not one data model.
- V2 routes are not protected by the legacy API-key dependency and do not have
  account or organization ownership.
- Long jobs run in the web process. Render has no durable V2 artifact storage,
  so a restart or deployment can lose film-analysis state.
- The V2 reasoner receives structured measurements but no selected frames or
  clips. Production assignment, route, block, coverage, and tackle reasoning is
  not complete.
- The current tracking, play segmentation, and automatic field calibration are
  prototypes and have no labeled-film accuracy benchmark.

## Team ownership

| Lane | Owner | Scope |
| --- | --- | --- |
| Integration and platform | Codex | API contracts, authentication boundary, tenancy, database, artifact storage, durable jobs, evidence enforcement, CI, releases |
| Product interface | Claude | React/TypeScript migration, saved-athlete workspace, report history, athlete and coach experiences, accessibility and responsive UI |
| Football vision | Grok | labeled-film benchmark, detector/tracker adapters, jersey identity, field/ball/pose association, play reconstruction, vision accuracy |

No AI merges another lane's pull request. Codex reviews integration, the owner
reviews product behavior, and GitHub CI must pass before a merge.

## Delivery phases

### Phase 16 — Production contract and parallel foundations

Codex:

- document and freeze versioned resource contracts;
- protect every V2 route and introduce owner/organization context;
- enforce evidence linkage before an event can affect a grade;
- add liveness/readiness separation and production-safe CORS configuration.

Claude, on a separate branch:

- migrate the existing static shell to React + TypeScript + Vite without a
  visual redesign or invented content;
- preserve the working Create Profile and Film Analysis flows;
- create a typed API client and real URL routes;
- keep unfinished destinations clearly unavailable.

Grok, on a separate branch:

- create an offline, dependency-light labeled-film benchmark contract;
- score detector, track continuity, jersey identity, calibration, ball/pose
  association, and play-boundary accuracy;
- add small synthetic fixtures only for harness tests, never for user reports.

Gate: three isolated PRs, green CI, no official rule-file changes, and an
integration smoke test against `backend.main:app`.

### Phase 17 — Durable athlete-to-report core

- one migration-managed data model for organizations, users, athletes, videos,
  jobs, tracks, assignments, plays, observations, events, grades, reports, and
  audit history;
- local artifact adapter for development and S3-compatible object storage for
  production;
- durable queue workers with idempotency, leases, retries, cancellation, stale
  job recovery, checkpoints, and per-account concurrency controls;
- saved Athlete → Film → Truth Report workspace, video/job resume, manual field
  calibration, play correction, observation override, and report history.

Gate: data survives a web-process restart; duplicate starts are idempotent;
cross-owner access is denied; a completed report can be reopened.

### Phase 18 — Production football vision

- real ByteTrack adapter first, with interfaces for BoT-SORT/DeepSORT/ReID;
- camera-motion compensation and track reconciliation;
- multi-frame jersey OCR with team-roster constraints and human confirmation;
- field-line/hash/sideline calibration confidence;
- player-associated pose, dedicated football tracking, and contact geometry;
- pre-snap/snap/post-snap/dead-ball segmentation with manual correction.

Gate: agreed accuracy thresholds pass on owner-approved labeled film. No metric
is promoted from estimated to verified without calibration evidence.

### Phase 19 — Multimodal evidence and complete grading

- generate bounded evidence packets with selected frames/clips, structured
  measurements, quality signals, and allowed official traits;
- provider-neutral multimodal OpenAI/Google/Anthropic adapters;
- retries, rate-limit handling, cost accounting, model/prompt versioning, and
  strict schema validation;
- position-aware football reasoning, play events, all official traits, game
  grade, confidence, prospect profile, and evidence-linked Truth Report.

Gate: every non-unknown scored event opens the supporting play at its exact
timestamp; AI output alone cannot set or alter an official score.

### Phase 20 — Trusted learning AI

Codex owns the feedback, dataset, security, and model-release contracts; Grok
owns training/evaluation pipelines for vision models; Claude owns the human
review and correction interface.

- convert confirmed track identity, play-boundary, field-calibration,
  observation, and outcome corrections into immutable labeled examples;
- record who corrected what, the original prediction, evidence, model/prompt
  version, confidence, reason, consent, and timestamp;
- use tenant-isolated, permissioned dataset snapshots with provenance,
  retention, deletion, and train/test leakage protection;
- add an active-learning review queue that prioritizes uncertain or disputed
  plays for a qualified human;
- train candidate models offline for jersey recognition, identity continuity,
  play segmentation, calibration, ball/pose association, and confidence
  calibration;
- maintain a model registry with dataset version, code version, metrics,
  artifact checksum, approval state, and rollback target;
- compare champion/challenger models on untouched owner-approved film, then use
  staged canaries and monitoring before promotion;
- preserve accepted corrections when reprocessing old film and never train on
  GPA, academics, character, or inferred personal facts from game film.

Gate: no training example enters a dataset without provenance and permission;
no model promotes itself; every candidate must beat defined benchmark and
safety thresholds without regressing protected positions or film conditions.
The deterministic official grading engine remains unchanged.

### Phase 21 — Accounts, roles, and privacy

- owner-approved authentication provider;
- athlete, coach, scout, administrator, and organization roles;
- invitations, session management, password-reset/provider flows, quotas,
  retention, consent, export, and deletion;
- private-by-default film and signed, expiring access.

Gate: authorization and tenant-isolation tests pass. Authentication provider is
a deliberate owner decision, not an implementation guess.

### Phase 22 — Athlete product

- Athlete Dashboard, AI Film Report, Trait Breakdown, verified recruiting
  activity, public rating controls, report export, and share links;
- progress and history use persisted real records only.

`Offer Probability` remains unavailable until there is an owner-approved data
source, target definition, validation method, and honest uncertainty display.

### Phase 23 — Coach product

- Coach Dashboard, Recruitment Board, Watchlist, player comparison, Player
  Profile, Coach 360, notes, alerts, and organization workflows;
- Genesis search operates only over authorized, indexed, sourced records.

### Phase 24 — Operations and commercial release

- pinned builds and non-root container;
- migration, container-startup, backup/restore, concurrency, restart/resume,
  storage lifecycle, and representative-film CI;
- structured logs, tracing, model metrics, queue metrics, cost controls,
  alerts, staged deployment, rollback criteria, and incident runbooks;
- accessibility, responsive, privacy, security, load, and pilot acceptance
  testing.

Gate: release checklist signed off against a real pilot workflow. A successful
HTTP response is not treated as proof of football-evaluation accuracy.

## Merge protocol

1. Start every branch from `claude/pc-work-continuation-s4bv4c` after pulling
   its newest merge.
2. Use one branch and one pull request per phase/lane.
3. Do not edit another lane's owned files without recording the reason in the
   PR description.
4. Never change `backend/grading/rules/*.json` unless the owner supplies the
   methodology change in writing.
5. Include tests and a `PASS`/`FAIL` verification list in every PR.
6. Do not merge red CI, unresolved conflicts, placeholder data presented as
   real, or an unreviewed schema/API breaking change.
7. Codex performs the integration review after each lane PR; the owner performs
   the final merge action.
