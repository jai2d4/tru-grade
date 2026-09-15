# Analysis Worker — setup brief

**Read this first if you are a Claude Code session running on the V2 Cloud
machine.** It carries the context from the session that diagnosed the
problem, so you don't have to rediscover it.

---

## Why this exists

TruGrade's V2 Film Analysis pipeline (frame extraction → YOLO tracking →
pose → homography → grading) currently runs **in-process on the Render web
service**, dispatched via `BackgroundTasks.add_task` in
`backend/api/analysis.py`. That cannot work in production, and it was
measured rather than assumed:

| Fact | Value | How it was established |
| --- | --- | --- |
| Render instance memory limit | **512 MB** | Render metrics API |
| Idle usage (serving health checks) | **~101 MB** | Render metrics API |
| Headroom | **~410 MB** | difference of the two |
| `import torch` alone | **499 MB RSS** | measured directly |
| `import torch` + ultralytics | **539 MB RSS** | measured directly |

That is before model weights, easyocr, or a single decoded frame. The
first real film analysis on the live site OOM-kills the container.

It has never been caught because the models are **lazily imported** (inside
functions, not at module scope), so the app boots fine and health checks
stay green — and because production logs show **zero** requests to
`/api/videos` or `/api/analysis`, ever. The failure is latent, not
observed. That also makes this the safest possible moment to re-architect:
there are no users to break and no in-flight jobs to migrate.

Two related findings:

- **No CPU/GPU split in dependencies.** Nothing pins CPU-only torch, so the
  Render image pulls the entire CUDA stack (~19 nvidia packages) onto a
  CPU-only box. On the V2 worker, CUDA torch is correct and wanted — which
  is exactly why requirements need to split in two.
- **No persistent disk and no frame cleanup.** `render.yaml` has no `disk:`
  block, so Render's filesystem is ephemeral: uploaded film and extracted
  frames are destroyed on every deploy, while the `film_uploads` rows
  survive in Postgres (the DB claims a video exists when the file is gone).
  Nothing in the codebase ever deletes extracted frames, and they are
  written at native FPS with `cv2.imwrite`'s default quality (95).
  Measured: a 1080p frame is ~1.3 MB at that quality on synthetic
  worst-case input — real footage compresses better, but a 10-minute
  60 fps clip is still multiple GB, and a full game is catastrophically
  worse.

## Target architecture

Decided with the product owner. Members upload their own film, so this has
to work for everyone, 24/7 — local-only processing was considered and
ruled out for that reason.

```
Member's phone/browser
        │  (direct HTTPS upload, signed token)
        ▼
  V2 Cloud box ──────────────┐   film lands on the V2 drive;
  • upload endpoint          │   storage and compute are the SAME
  • analysis worker (GPU)    │   machine, so there is no transfer step
        │                    │
        │ polls for jobs     │ writes results
        ▼                    ▼
   Render Postgres  ◄──── shared job queue
        ▲
        │
  Render web service — accounts, board, reports, share links.
  NO torch / ultralytics / easyocr / opencv once this lands.
```

Key decisions and the reasoning behind them:

- **The worker polls outbound.** The V2 box is behind NAT with no public
  inbound IP. Polling needs no port forwarding and no static IP, and jobs
  simply queue if the worker is ever down.
- **Uploads bypass Render entirely.** The original "can't upload mp4"
  complaint was Render's proxy rejecting large request bodies before they
  reached the app. Routing uploads straight to V2 removes Render from that
  path instead of working around it. The existing
  `POST /api/videos/upload-from-youtube` path stays as a convenience, not
  as the only way to get large phone film in.
- **The upload endpoint must be authenticated.** It is public-facing via
  the tunnel. Render issues a short-lived signed upload token; the V2
  service verifies it before accepting bytes. Reuse the HMAC pattern
  already in `app/routers/auth.py` (password-reset tokens) — do not invent
  a new scheme, and do not accept unauthenticated uploads even temporarily.
- **Cloudflare Tunnel** (or Tailscale Funnel) gives the V2 upload endpoint
  a public HTTPS hostname without a public IP. Free tier covers this.

## Build order

Each step is safe on its own; do them in order.

1. **Job state → Postgres.** Today it is JSON files in
   `storage/jobs/*.json` (`_write_job`/`_read_job` in
   `backend/api/analysis.py`). A worker on another machine cannot see
   those. Add a real table in `db/init_schema.sql` + an ORM model in
   `app/models/orm.py`, with a status enum and a claim mechanism that is
   safe against two workers grabbing the same job (`SELECT ... FOR UPDATE
   SKIP LOCKED` is the standard approach).
2. **Worker process.** Replace `BackgroundTasks.add_task` with enqueue-only
   on the web side; the worker polls, claims, runs the existing pipeline
   (`backend/vision/*`, unchanged), and writes results back. Must survive
   reboot — a Windows Service / Task Scheduler entry, or systemd.
3. **Upload endpoint on V2 + tunnel.** Signed-token verification, a body
   size limit set by us (not Render's proxy), and writing into the V2
   drive layout the worker reads from.
4. **Split requirements.** `requirements.txt` (web: no torch/ultralytics/
   easyocr/opencv) and `requirements-worker.txt` (CUDA torch matching the
   box's driver). Add frame cleanup once analysis completes, and stop
   writing quality-95 JPEGs — the tracking pipeline gains nothing from
   them.

## Before writing code on the V2 box

Run the probe and work from its real numbers, not assumptions:

```
python scripts/check_env.py
```

It reports GPU model and VRAM, free disk, whether CUDA torch is usable,
what is already installed, and outbound reachability. The CUDA version it
reports decides which torch wheel goes in `requirements-worker.txt`.

## Ground rules carried over from the main session

- **Never fabricate data.** An ungraded trait stays UNKNOWN; an uncertain
  jersey match asks for human confirmation rather than guessing. If the
  worker is down, members see "queued" — not a fake result.
- **Verify, don't assume.** Every claim in the table above was measured.
  Hold new work to the same standard.
- Existing test suites must stay green: backend `pytest` (172 tests, and
  they are idempotent — safe to re-run against the same database),
  frontend `npm test` (109 tests).
