# TruGrade Learning AI Contract

## What "learning" means

TruGrade learns from verified human corrections and measured outcomes. It does
not treat its own predictions, internet claims, or synthetic demos as truth.
Production models remain fixed until a candidate passes evaluation and is
explicitly approved.

## Learnable components

- player and football detection;
- track continuity and player re-identification;
- jersey-number recognition and team association;
- field calibration and camera-motion handling;
- player/pose and player/ball association;
- play-boundary and snap estimation;
- football observation classification;
- confidence calibration and human-review prioritization.

## Components AI cannot rewrite

- official position trait names;
- TruGrade trait weights;
- deterministic scoring-event values;
- unknown-observation handling;
- evidence requirements;
- rules prohibiting character, academic, GPA, or measurement inference;
- the owner's final approval authority.

## Feedback record

Every learning example must include:

- organization, video, play, track, and player references;
- original prediction and confidence;
- human-confirmed value and correction reason;
- exact evidence timestamps/frame IDs;
- model, prompt, detector, tracker, and ruleset versions;
- corrector identity/role and correction timestamp;
- data-use consent, retention class, and deletion state.

## Release path

`correction → reviewed label → frozen dataset snapshot → offline training →`
`untouched benchmark → bias/regression review → owner approval → canary →`
`production champion or rollback`

## Required safeguards

1. Separate training, validation, and untouched test games by athlete/game so
   frames from the same play cannot leak between sets.
2. Never learn directly from an unreviewed AI output.
3. Keep private film tenant-isolated and encrypted; do not use it for another
   customer's model without explicit permission.
4. Remove deleted/revoked data from future dataset versions and retraining.
5. Benchmark by position, camera angle, film quality, uniform contrast, and
   demographic slices where lawful and relevant.
6. Preserve model/dataset lineage and one-click rollback.
7. Display the active model version and whether a result was human-confirmed.
8. Route low-confidence or model-disagreement cases to humans; never hide
   uncertainty behind an overall grade.

## Initial implementation sequence

1. Store corrections and model provenance durably in Phase 17.
2. Build Grok's objective vision benchmark in Phase 16.
3. Add Claude's review queue and evidence correction UX after the durable core.
4. Train only after enough owner-reviewed examples exist.
5. Start with confidence calibration and jersey/play-boundary candidates before
   attempting more complex football-responsibility classifiers.

