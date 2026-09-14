# Database backup & restore

TruGrade's database (`tru-scouting-db`) is a paid Render Postgres instance
(plan `0.1c-256mb`, confirmed via the Render API — not the old, unsupported
free tier that gets no managed backups at all). Render's dashboard
(the `tru-scouting-db` page → **Backups**) is the actual source of truth
for what backup schedule and retention that plan includes — check there
directly rather than assuming a specific policy, since that detail isn't
exposed through the API this was verified with.

This document is a **second, independent** layer on top of whatever
Render provides: a portable, downloadable backup you control directly, so
a Render-side problem (an accidental database deletion, a lost account, a
plan change) isn't a single point of failure for every athlete record,
evaluation, and account TruGrade holds.

## What's here

- `scripts/backup_db.py` — dumps the database to a timestamped,
  gzip-compressed `.sql.gz` file using `pg_dump`.
- `scripts/restore_db.py` — replays a `.sql.gz` backup into a target
  database using `psql`.

Both read the exact same `DATABASE_URL` / `POSTGRES_*` environment
variables the app itself uses (`app/core/config.py`), so they always act on
whatever database you're currently pointed at — there's no separate backup
credential to keep in sync.

**Verified, not just written**: `tests/test_backup_restore.py` runs a real
backup → destroy the database → restore → verify drill against a live,
disposable Postgres database every time the test suite runs (see that file
for the mechanics). This isn't a description of what the scripts *should*
do — it's proof they actually round-trip real data correctly, checked on
every CI run.

## Taking a backup

Requires the `pg_dump` client tool (part of the `postgresql-client` package
on Debian/Ubuntu; already present anywhere `psql` is available).

```bash
# Against whatever POSTGRES_*/DATABASE_URL are currently set to:
python scripts/backup_db.py [output_dir]     # defaults to ./backups
```

To back up **production**, run this with production's connection info —
either by exporting Render's `DATABASE_URL` locally (copy it from the
`tru-scouting-db` page in the Render dashboard → Info → External
Connection String) or from a shell that already has those env vars set.
Render's dashboard is the only place that connection string is shown —
there's no API tool that returns it.

The result is a single portable `.sql.gz` file. Keep it somewhere that
doesn't depend on Render or GitHub being available (a local drive, cloud
storage you control) — the whole point is independence from any one
provider.

## Restoring a backup

```bash
python scripts/restore_db.py path/to/trugrade-backup-<timestamp>.sql.gz
```

**This is destructive** to whatever database the current connection info
points at — it replays every `CREATE TABLE` and `INSERT` in the dump, so it
expects an empty (or disposable) target. Practical uses:

- **Disaster recovery**: point the env vars at a fresh, empty database
  (a new Render Postgres instance, or any Postgres 16+ server) and restore
  into it.
- **Testing a backup is actually good**: restore into a throwaway local
  database (never production) and spot-check it — this is exactly what
  `tests/test_backup_restore.py` automates.

Never run `restore_db.py` against a database you want to keep as-is
without a fresh backup of *that* database first.

## Recommended cadence

Nothing here runs on a schedule automatically — running `backup_db.py`
periodically (a weekly cron on your own machine, or a scheduled Routine
that has a way to reach the production database) is a deliberate next step
if you want this layer to stay current without manual effort. Not wired up
yet, so it wasn't claimed as done.
