# Codex Work Packet — Phase 16 Production Contract

## Branch

`codex/trugrade-full-phase16-foundation`, based on the newest
`claude/pc-work-continuation-s4bv4c` after the roadmap PR is merged.

## Objective

Establish the security, resource, and evidence contracts that Claude's UI and
Grok's vision work can integrate with safely.

## Scope

- versioned API/resource contracts and compatibility adapters;
- temporary single-owner API-key identity mapped through a replaceable auth
  interface, with production fail-closed behavior;
- authorization on every V2 video/job/track/play/evidence/report route;
- configurable production CORS allowlist;
- evidence-range enforcement for every score-affecting reasoning event;
- liveness and dependency-aware readiness endpoints;
- HTTP integration tests against `backend.main:app`.

## Explicitly deferred

- choosing a public authentication vendor;
- changing official position weights or event values;
- durable queue/object storage implementation (Phase 17 after contracts);
- changing vision models;
- presenting any placeholder dashboard as complete.

## Acceptance tests

- production cannot start with an unprotected V2 API;
- missing/wrong credentials are rejected consistently;
- a non-unknown score-affecting event without in-play evidence is rejected or
  safely excluded;
- grade remains separate from confidence;
- `/api/health/live` does not depend on optional services;
- `/api/health/ready` reports required dependency failures;
- legacy request shapes remain usable during migration;
- full backend tests, frontend typecheck, and frontend build pass.

