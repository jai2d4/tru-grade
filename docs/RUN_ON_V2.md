# Running TruGrade on the V2 box

Everything on one machine: web, worker, film storage. Postgres stays
managed on Render (or move it here later).

## Why one machine

The storage layer has always assumed a single filesystem — tracks,
detections, biomechanics, plays, evidence, grades and the film itself are
all read straight off disk by both the API and the analysis pipeline.
Splitting web and worker across two hosts means rewriting all of that.
Putting both where the GPU and the disk already are avoids the problem
entirely, and removes three others at the same time:

- **No upload size limit.** Film is uploaded to this host directly, not
  through a PaaS proxy that rejects large request bodies. That was the
  original "can't upload mp4" failure.
- **Nothing is lost on deploy.** A real drive, not an ephemeral container
  filesystem.
- **No OOM.** The 512 MB web instance could not load torch (499 MB for
  the import alone). This machine can.

The tradeoff, plainly: this box becomes the single point of failure for
the public site. It stays up, or the site is down.

## Prerequisites

```
python scripts/check_env.py
```

Run this first. It reports the GPU and its CUDA version, free disk,
what's installed, and outbound reachability. The CUDA version decides the
torch wheel below.

You also need Docker (with the NVIDIA Container Toolkit for GPU access),
or Python 3.11+ if running without containers.

## 1. Configure

Copy `.env.example` to `.env` and set at minimum:

| Variable | What it's for |
| --- | --- |
| `GEMINI_API_KEY` | Module 1 film analysis (the only paid external API) |
| `API_KEY` | shared secret guarding the API; the app refuses to start in production without it |
| `VITE_API_KEY` | must equal `API_KEY` — baked into the frontend bundle at build time |
| `DATABASE_URL` | the Render Postgres external connection string |
| `MAX_UPLOAD_MB` | now genuinely yours to choose; 2048 is a reasonable start |

## 2. Run

```
docker compose -f docker-compose.v2.yml up -d --build
```

On a GPU machine, first uncomment the `deploy.resources` block under
`worker` in `docker-compose.v2.yml`, and build the worker against the
matching CUDA wheel:

```
docker compose -f docker-compose.v2.yml build \
  --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu121 worker
```

Replace `cu121` with whatever `check_env.py` reported. Without this it
builds the CPU wheel — the worker still runs, just slower.

Without Docker, two processes instead:

```
pip install -r requirements.txt -r requirements-worker.txt
python scripts/init_db.py
uvicorn backend.main:app --host 127.0.0.1 --port 8000   # terminal 1
python scripts/run_worker.py                            # terminal 2
```

## 3. Put it on the internet

The web container binds to `127.0.0.1:8000` deliberately — nothing is
publicly exposed until you decide it is, and a cloud desktop generally
has no public inbound address anyway. Cloudflare Tunnel handles both,
with no port forwarding and no static IP:

```
cloudflared tunnel login
cloudflared tunnel create trugrade
cloudflared tunnel route dns trugrade app.yourdomain.com
cloudflared tunnel run --url http://127.0.0.1:8000 trugrade
```

Then install it as a service so it survives reboot
(`cloudflared service install`).

## 4. Verify

```
curl http://127.0.0.1:8000/api/health/ready     # DB-aware readiness
docker compose -f docker-compose.v2.yml logs -f worker
```

The worker logs `analysis worker <id> starting` and then polls quietly.
Upload a short clip through the UI: the job should move through
`queued → claimed → extracting_frames → detecting → tracking → completed`.

If the worker is stopped, jobs sit at `queued` and the UI honestly shows
them as queued — no fake results.

## Operational notes

- **Frame cleanup is on** (`DISCARD_FRAMES_AFTER_IDENTITY=true`).
  Extracted frames are reclaimed once identification finishes; one
  keyframe is preserved so field calibration still works, and frames are
  re-derivable from the source video anyway.
- **`ANALYSIS_FPS=native`** processes every frame of the source video. For
  60 fps film that is a lot of frames — set a number (e.g. `30`) to trade
  detail for speed and disk.
- **A crashed worker is recoverable.** Jobs carry a heartbeat; one whose
  worker stopped responding is returned to the queue automatically rather
  than sitting claimed forever.
- **Backups** still apply — see `docs/BACKUP_RESTORE.md`. Note that the
  film and frames on this box are *not* covered by Render's database
  backups.
