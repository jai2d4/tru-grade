# Analysis worker — background and rationale

> **For setup instructions, see [RUN_ON_V2.md](RUN_ON_V2.md).** This
> document explains *why* the architecture is what it is. It was
> originally written to hand a two-machine split (web on Render, worker on
> a GPU box) to whoever built it; that split was superseded — see
> "Why one machine" below — but the measurements that drove it still
> explain the current design.

## The problem that started it

The V2 film pipeline (frame extraction → YOLO tracking → pose →
homography → grading) used to run **in-process on the web service**,
dispatched via `BackgroundTasks.add_task`. That could not work, and it was
measured rather than assumed:

| Fact | Value | How it was established |
| --- | --- | --- |
| Render instance memory limit | **512 MB** | Render metrics API |
| Idle usage (serving health checks) | **~101 MB** | Render metrics API |
| Headroom | **~410 MB** | difference of the two |
| `import torch` alone | **499 MB RSS** | measured directly |
| `import torch` + ultralytics | **539 MB RSS** | measured directly |

That is before model weights, easyocr, or a single decoded frame. The
first real film analysis would OOM-kill the container.

It went unnoticed because the CV imports are **lazy** (inside functions,
not at module scope), so the app boots fine and health checks stay green —
and because production logs showed **zero** requests to `/api/videos` or
`/api/analysis`, ever. The failure was latent, not observed, which is also
what made it safe to re-architect: no users to break, no in-flight jobs to
migrate.

A second, worse instance of the same bug lived in automatic jersey
identification: it loaded easyocr (hence torch) **and** decoded every
referenced frame into a dict before starting OCR — roughly 6 MB per 1080p
frame resident, so gigabytes for a few thousand frames.

## Why one machine

The obvious fix was web-on-Render plus worker-on-GPU-box. A sweep of every
web-mounted router killed that idea: the entire V2 API reads artifacts
straight off a shared local disk — videos, tracks, detections,
biomechanics, calibrations, plays, overrides, evidence, grades and report
jobs. Splitting the two hosts means rewriting the whole storage layer, not
adding a queue.

Running both where the GPU and the disk already are avoids that work and
removes three more problems at once:

- **Upload size.** Film is uploaded to the host directly, not through a
  PaaS proxy that rejects large request bodies — the original
  "can't upload mp4" failure.
- **Data loss.** Render's filesystem is ephemeral (no `disk:` block), so
  film and frames were destroyed on every deploy while the `film_uploads`
  rows survived, leaving the database claiming videos whose files were
  gone.
- **OOM.** The measurements above.

The tradeoff, plainly: that box becomes the single point of failure for
the public site.

The job queue still earns its place even on one machine — analysis no
longer blocks web requests, a crashed worker's jobs are recovered rather
than stuck, and a second worker can be added later without redesigning
anything.

## Design decisions worth keeping

- **The worker polls outbound.** Nothing has to reach *into* the worker,
  so it needs no inbound address, no port forwarding and no static IP.
  Jobs queue harmlessly whenever it's offline.
- **Claiming uses `SELECT ... FOR UPDATE SKIP LOCKED`.** Two workers can
  never take the same job; concurrent claimers skip locked rows instead of
  blocking or double-dispatching.
- **Heartbeats, not optimism.** A claimed job whose worker stopped
  responding is returned to the queue by `requeue_stale()`. Without it, a
  reboot mid-job leaves a member watching a progress bar that never moves.
- **Heavy imports stay inside the job function.** Importing
  `backend.jobs.worker` — which tests and the web service do — must never
  drag torch into a process that has no business loading it.
- **Frames are an intermediate artifact.** They're reclaimed once
  identification finishes; a single keyframe is preserved so field
  calibration still works, and the rest is re-derivable from the source
  video.

## Ground rules

- **Never fabricate data.** An ungraded trait stays UNKNOWN; an uncertain
  jersey match asks for human confirmation rather than guessing. If the
  worker is down, members see "queued" — not a fake result.
- **Verify, don't assume.** Every number in the table above was measured.
  Hold new work to the same standard.
- Both suites stay green: backend `pytest` (190 tests, idempotent — safe
  to re-run against the same database), frontend `npm test` (109 tests).
