# TruGrade API Contract 1.0

Status: frozen compatibility contract for the Phase 16 migration.

The deployed API keeps its existing unversioned `/api/...` paths while clients
migrate. `GET /api/contracts/v1` identifies that compatibility promise. Adding
fields is allowed; removing or changing existing fields requires a new contract
version and an explicit adapter.

## Resource families

- `/api/videos`: uploads, stored film, tracks, detections, calibration, and identity.
- `/api/analysis`: analysis job creation, status, and resume.
- `/api/videos/{video_id}/plays`: play boundaries and human corrections.
- `/api/observations`: immutable human observation overrides.
- `/api/players`: evidence, deterministic grades, and Truth Reports.

Every resource route above requires the replaceable identity dependency. The
Phase 16 adapter maps the existing `X-API-Key` to the single owner and
organization. A later account provider can replace that adapter without
changing these resource routes.

## Grading and evidence invariants

- External AI describes evidence; it never calculates the official grade.
- Every non-unknown score-affecting event carries an evidence timestamp inside
  one of its source observation's evidence ranges.
- Unknown observations are excluded from scoring when evidence is not linked.
- Grade and confidence remain separate values.

## Operational endpoints

- `/api/health/live` proves only that the web process can answer.
- `/api/health/ready` checks required database and writable-storage dependencies.
- `/api/v1/health` and `/api/health` remain legacy compatibility endpoints.
