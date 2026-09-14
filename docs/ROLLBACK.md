# Rolling back a bad deploy

TruGrade auto-deploys to Render on every push to `claude/pc-work-continuation-s4bv4c`
(service `tru-scouting-engine`). This is what to do when a deploy turns out
to be broken.

## First: confirm it's actually broken

Don't roll back on a hunch — check the real signal first:

```
GET https://tru-scouting-engine.onrender.com/api/health/status
```

Returns `200` with `"status": "ready"` when the app and its database are
both genuinely healthy, `503` with `"status": "not_ready"` and per-check
detail when something's actually down. It also reports the exact deployed
`git_commit` — confirm that matches the commit you think just deployed
before concluding *that* deploy is the problem and not something else
(a Gemini outage, a database blip).

## Method 1: Render's own rollback (fastest, no code change)

Render keeps every previous deploy and can redeploy any of them directly:

1. **dashboard.render.com** → **tru-scouting-engine** → **Deploys**.
2. Find the last deploy that was known-good (the one *before* the bad one).
3. Click the **↺ Rollback** icon on that row.

This redeploys that exact prior build. It does **not** touch the database
or change what's in GitHub — `main`/the deploy branch still has the bad
commit at its tip until someone pushes past it or a git-level revert
happens. Use this when you need the site working again *right now* and can
sort out the code afterward.

## Method 2: git-level revert (when the branch itself needs to move too)

Use this when Method 1 alone isn't enough — e.g. you want the deploy
branch's history to actually reflect the rollback, not just Render's
running instance.

```bash
git fetch origin claude/pc-work-continuation-s4bv4c
git checkout claude/pc-work-continuation-s4bv4c
git revert <bad-commit-sha>       # creates a new commit undoing it
git push origin claude/pc-work-continuation-s4bv4c
```

Render auto-deploys the revert commit the same way it deploys anything
else — no manual trigger needed. Prefer `git revert` over `git reset
--hard` + force-push: a revert preserves history (what actually happened
is still visible) and never rewrites a branch another clone may have
already pulled.

## After either method: verify, don't assume

1. `GET /api/health/ready` → `200`.
2. `GET /api/health/status` → confirm `git_commit` is the SHA you expected
   to be running.
3. Exercise one real path end to end (e.g. load the site, check a known
   athlete's Player Profile) — a passing health check confirms the process
   and database are up, not that every feature works.

## What this does *not* cover

A code rollback undoes a bad **deploy**. It does not undo bad **data** —
if the broken deploy wrote incorrect rows before you caught it, rolling
back the code doesn't touch what's already in Postgres. That's what
[`docs/BACKUP_RESTORE.md`](./BACKUP_RESTORE.md) is for; the two are
separate tools for separate failure modes.
