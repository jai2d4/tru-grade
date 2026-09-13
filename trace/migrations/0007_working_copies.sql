-- Migration 0007 — recording when an analysis ran on a working copy.
--
-- A working copy is a re-encode of an original, made so that analysis has
-- something that decodes predictably and seeks in constant time. It is a
-- derived asset, and it may be lossy.
--
-- That makes "where did this detection come from" a question with two possible
-- answers, and the difference is not decorative. A box drawn on the original's
-- own pixels and a box drawn on a re-compressed approximation of them are
-- different claims about what was observed, and a case file that presented them
-- identically would overstate the second. Compression artefacts are exactly the
-- kind of structure a detector will happily find an object in.
--
-- So the run says which it analysed. NULL means the original, which is what
-- every run recorded before this migration did — no backfill is needed and none
-- would be honest, because the column means "this named derived asset" and
-- there was none.
--
-- ON DELETE SET NULL rather than CASCADE: deleting a working copy to reclaim
-- disk must not delete the analysis that ran on it. The run and its detections
-- are findings; the working copy is a convenience that can be regenerated from
-- the original and its recorded parameters. Losing the link degrades the
-- provenance chain, so the run also keeps source_description below, which
-- survives the asset row entirely.

ALTER TABLE analysis_runs ADD COLUMN source_asset_id TEXT
    REFERENCES derived_assets(id) ON DELETE SET NULL;

-- What was analysed, in words, independent of whether the asset row still
-- exists. A report has to be able to say "analysed on a lossy working copy"
-- years after somebody cleared out the working directory.
ALTER TABLE analysis_runs ADD COLUMN source_description TEXT;

CREATE INDEX IF NOT EXISTS idx_analysis_runs_source_asset
    ON analysis_runs(source_asset_id);
