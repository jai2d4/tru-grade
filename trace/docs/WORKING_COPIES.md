# Working copies

A **working copy** is a re-encode of an original that analysis can run against
instead of the original. The original is never touched, its digest never
changes, and every working copy is a derived asset with its transcode
parameters recorded.

---

## 1. Why they exist

Analysis samples frames by timestamp, which means seeking — thousands of times
over an hour of footage. Some material makes that ruinous:

- **Long GOPs.** A ten-second keyframe interval costs a few hundred decoded
  frames for every seek. The decode work is quadratic in the wrong thing.
- **Proprietary CCTV codecs**, which are often slow, occasionally wrong, and
  sometimes both.

A working copy is **all-intra** — every frame is a keyframe — so a seek is a
demux and one decode. That is the entire point of the feature. Everything else
here exists to make it safe.

---

## 2. The timeline is the whole problem

A working copy is only useful if a detection at 00:05:12.340 in it means
00:05:12.340 in the original. Three rules follow, and the third is the one that
makes the first two believable:

1. **Timestamps are preserved, not recomputed.** Each frame is written with the
   source frame's own presentation timestamp, rescaled between time bases but
   never derived from a frame index and a frame rate.
2. **The frame rate is never changed; frames are never dropped or duplicated.**
   Converting variable-frame-rate material to a constant rate is the standard
   way to tidy a transcode, and it silently moves every frame in the recording.
   TRACE will not do it. A VFR source produces a VFR working copy.
3. **The result is verified against the original before the asset exists.**
   `verifyTimelineMatches` reopens both files and compares frame timestamps one
   by one. A mismatch deletes the file and fails the conversion.

### What the check accepts, and why

It compares both files **measured from their own first frame**, so a *uniform*
offset of the whole recording passes. That is deliberate, not a gap: TRACE never
reads absolute container time. `VideoDecoder` normalises so the first frame of a
stream is zero, and every position in the application — bookmarks, annotations,
detections — is on that clock. A uniform shift is unobservable to TRACE and
cannot misplace anything.

What it rejects is everything that *can*: a different frame count, and any frame
that moved relative to the rest. `TheTimelineCheckCatchesAStretchedTimeline`
covers the dangerous case, because it is the one that survives every cheaper
check — the same frames, in the same order, each moved by a different amount.
The file plays, a frame count matches, and every detection after the first is
increasingly wrong.

### A defect this caught

The first working implementation produced files whose video ran **23ms late**
against both its own audio and the original.

The cause is not obvious. A compressed audio track carries priming samples, so
its first packet sits *before* zero — AAC's 1024-sample delay puts it at
−23.2ms in `tests/fixtures/sample.mp4`. Matroska's default response to a
negative timestamp is to shift until nothing is negative, and what it actually
did was move the **video** forward by 23ms and leave the audio where it was.

Nothing about the picture would have looked wrong.

Two changes fix it, and the second matters more than the first:

- `avoid_negative_ts` is disabled on the output, and audio packets that would
  land before zero are dropped. A priming packet is encoder padding rather than
  recorded sound, and losing it must not be paid for by moving the timeline
  detections are measured against. The count is recorded in the asset's
  parameters.
- **The check stopped trusting `start_time`.** It had been normalising each file
  by its container's declared start time — so it compared each file against its
  own metadata, found both self-consistent, and passed. Measuring from the first
  frame actually present compares the two *recordings*, which is what was being
  claimed.

---

## 3. Which codecs, and the licensing boundary

Two, both native to FFmpeg:

| | Codec | Lossless | Notes |
|---|---|---|---|
| **Default** | FFV1 | **Yes** | Decodes to the original's exact pixels |
| | Motion JPEG | No | Smaller; quality on FFmpeg's 2–31 quantiser scale |

### H.264 is not on that list, deliberately

Every H.264 encoder FFmpeg can reach is either a GPL library (`libx264`,
`libxvid`) or hardware-specific (`h264_nvenc`, `h264_vaapi`, `h264_qsv`).

- **GPL is a distribution problem, not a preference.** TRACE links FFmpeg under
  the LGPL — [BUILDING.md §2](BUILDING.md). Calling into `libx264` would place
  TRACE itself under the GPL the moment it is distributed.
- **A hardware encoder is not reproducible.** Two machines produce different
  bytes from the same input, and a derived asset whose digest depends on which
  GPU was in the workstation is not much of a provenance record.

The trap is that the first point is **invisible in development**. The Ubuntu
system FFmpeg is built `--enable-gpl` and offers `libx264`, so an implementation
that reached for it would build and pass every test on Linux, then fail on the
Windows CI job — which resolves an LGPL build that does not contain it at all.
A green Linux run would have hidden a licensing violation behind what looks
like a portability bug.

So `forbiddenEncoderReason()` refuses those encoders **by name**, whether or not
the linked build offers them, and
`RefusesGplEncodersByNameEvenWhenTheBuildOffersThem` asserts it on a machine
where `libx264` is demonstrably present.

### What a working copy costs

Both codecs are all-intra, so both are larger than a long-GOP original. These
are the **only two measurements taken**, both in the development container, and
neither is real CCTV footage:

| Source | Motion JPEG (q=3) | FFV1 (lossless) |
|---|---|---|
| `tests/fixtures/sample.mp4`, 320×240, 8s, ~163 kbps | 17.2× | 18.4× |
| 1080p25 H.264 CRF 23, synthetic `testsrc2`, 6s | 3.5× | 5.1× |

Two things follow:

1. **The multiple depends mostly on how hard the source was compressed**, not on
   the working copy. A heavily compressed source produces a large multiple
   because the denominator is small — which is why the rows differ by a factor
   of five. Neither number predicts what a given recording will cost; both are
   here so the order of magnitude is not a guess.
2. **Lossless is not the expensive option it sounds like.** It cost 45% more
   than Motion JPEG at 1080p and 7% on the small fixture, against a claim that
   is categorically stronger. That is why it is the default.

Neither figure was measured on long footage, on a real camera's output, or on
other hardware, and none should be quoted as though it were.

---

## 4. A working copy is not evidence

It is a derived asset, and a lossy one carries a warning in its own provenance:

> This working copy is a lossy re-encode. Detections found on it were found on
> re-compressed pixels, not on the original's.

Compression artefacts are exactly the kind of structure a detector will happily
find an object in. So when analysis runs against a working copy, the run says
so — `analysis_runs.source_asset_id` names the asset and `source_description`
says what it was in words.

`source_description` is not redundant. `ON DELETE SET NULL` means deleting a
working copy to reclaim disk clears the id but keeps the run and its detections,
which are findings. Without the description, a run over a lossy copy would
silently become one that reads as having examined the original.

**NULL means the original.** Every run recorded before migration 0007 is NULL,
and no backfill would be honest: the column means "this named derived asset",
and there was none.

The evidence digest on the run is unchanged either way. A working copy does not
change what the evidence is.

### The sample range, for Motion JPEG

JPEG is defined over full-range samples. A limited-range source is expanded on
the way in, which **clips superblack and superwhite** — values outside the
limited range are not recoverable from the copy. It is recorded in the asset's
parameters as `sample_range_converted`.

The lossless path never converts anything: if FFV1 cannot store the source's
pixel format, the conversion is refused rather than quietly made lossy while
still calling itself lossless.

---

## 5. What is deliberately absent

**Scaling.** Downscaling would make analysis faster and is the obvious next
parameter. It is absent because every detection box would then be in
working-copy coordinates, and something would have to map them back — a
transform that is easy to get subtly wrong and impossible to notice, since wrong
boxes still look like boxes. It needs designing deliberately. Until then a
working copy has exactly the dimensions of its source, and `scaled: false` is in
every provenance record.

**Automatic creation.** Nothing decides on an operator's behalf that a recording
is awkward enough to need one. Choosing to analyse a derivative rather than the
evidence is a decision with consequences for what can be claimed, so it is made
by a person.

---

## 6. What has not been tested

- **No real CCTV footage**, and no proprietary codec — which is the case the
  feature is for. The fixture is H.264 and the 1080p measurement is synthetic.
- **No long recording.** The longest conversion measured is eight seconds. The
  size figures above are the reason to care: an hour is a very different
  proposition, and nothing here has met one.
- **The seek-cost claim is structural, not measured.** All-intra means a seek
  decodes one frame; `EveryFrameIsAKeyframeSoSeekingIsConstantTime` asserts the
  property, not a speedup against a long-GOP original on real material.
- **No variable-frame-rate source has been converted.** The rules in §2 are
  written to preserve VFR timing and the check would catch a violation, but the
  fixture is constant-rate, so the VFR path has never run.
