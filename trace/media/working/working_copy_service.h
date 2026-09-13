#pragma once

#include <cstdint>
#include <filesystem>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "core/common/result.h"
#include "core/common/time_utils.h"
#include "core/models/derived_asset.h"
#include "core/models/evidence.h"
#include "core/security/crypto.h"
#include "core/services/derived_asset_service.h"
#include "core/storage/storage_layout.h"

namespace trace {

/// The encoder a working copy is written with.
///
/// ## Why this list is so short, and why H.264 is not on it
///
/// The obvious choice is H.264, and TRACE will not use it. Every H.264 encoder
/// FFmpeg can reach is either a GPL library (`libx264`, `libxvid`) or hardware
/// specific (`h264_nvenc`, `h264_vaapi`, `h264_qsv`), and neither is acceptable
/// here:
///
/// - **GPL is a distribution problem, not a preference.** TRACE links FFmpeg
///   under the LGPL, which `docs/BUILDING.md` §2 states as a boundary. Calling
///   into `libx264` would put TRACE itself under the GPL the moment it is
///   distributed. The trap is that it is invisible in development: the Ubuntu
///   system FFmpeg is built `--enable-gpl` and offers `libx264`, so an
///   implementation that reached for it would build and pass every test on
///   Linux — and then fail on the Windows CI job, which resolves an LGPL build
///   that does not contain it at all. A green Linux run would have hidden a
///   licensing violation behind a portability bug.
/// - **A hardware encoder is not reproducible.** Two machines produce different
///   bytes from the same input, and a derived asset whose digest depends on
///   which GPU was in the workstation is not much of a provenance record.
///
/// `forbiddenEncoderReason()` enforces the first point in code rather than in a
/// comment, because the failure mode is a build that works.
///
/// What is left are FFmpeg's own native encoders, which are present in every
/// build, need no external library, and are LGPL. Both entries here are
/// **all-intra** — every frame is a keyframe — which is the property that
/// actually makes a working copy worth having: sampling an analysis run means
/// seeking thousands of times, and a source with a ten-second GOP decodes
/// several hundred frames for each one of those seeks.
enum class WorkingCopyCodec {
    /// Motion JPEG. Lossy. The smaller of the two, and the option to reach for
    /// when a working copy of a long recording would otherwise not fit.
    MotionJpeg,
    /// FFV1. **Mathematically lossless** — decoding the working copy gives back
    /// the exact pixels the original decoded to, so a detection found on it was
    /// found on the original's pixels and not on an approximation of them.
    /// `ALosslessCopyDecodesToTheOriginalsExactPixels` checks that rather than
    /// taking the codec's word for it.
    ///
    /// The default, because the size difference turned out to be smaller than
    /// the difference in what can be claimed. See the measurements below.
    Lossless,
};

/// ## What a working copy costs, measured
///
/// Both codecs are all-intra, so both are larger than a long-GOP original.
/// These are the only two measurements taken, both in the development
/// container, and neither is real CCTV footage:
///
/// | Source | Motion JPEG (q=3) | FFV1 (lossless) |
/// |---|---|---|
/// | `tests/fixtures/sample.mp4`, 320×240, 8s, ~163 kbps | **17.2×** | **18.4×** |
/// | 1080p25 H.264 CRF 23, synthetic `testsrc2`, 6s | **3.5×** | **5.1×** |
///
/// Two things follow, and the second is why `Lossless` is the default:
///
/// 1. **The multiple depends mostly on how hard the source was compressed**,
///    not on the working copy. A heavily compressed source produces a large
///    multiple because the denominator is small, which is why the two rows
///    differ by a factor of five. Neither number predicts what a given
///    recording will cost; both are here so the order of magnitude is not a
///    guess.
/// 2. **Lossless is not the expensive option it sounds like.** It cost 45% more
///    than Motion JPEG at 1080p and 7% more on the small fixture — against a
///    claim that is categorically stronger, since detections found on it were
///    found on the original's own pixels. For evidence work that trade is worth
///    making by default, and Motion JPEG remains one field away for the cases
///    where it is not.
///
/// Neither figure was measured on long footage, on a real camera's output, or
/// on this hardware's successor, and none should be quoted as though it were.

const char* toString(WorkingCopyCodec codec);
const char* toDisplayString(WorkingCopyCodec codec);
/// True when the codec reproduces the source pixels exactly.
bool isLossless(WorkingCopyCodec codec);

/// Why TRACE refuses to encode with a named encoder, or empty when it will.
///
/// Checked against the encoder *name* rather than against build flags, because
/// the flags of the FFmpeg that TRACE happens to be linked against are not the
/// question. The question is what TRACE may call into and still be distributable
/// under the terms `docs/BUILDING.md` states, and that answer is the same
/// whether or not the local build happens to offer it.
std::string forbiddenEncoderReason(const std::string& encoderName);

struct WorkingCopyRequest {
    std::string caseId;
    std::string caseNumber;
    Evidence evidence;
    WorkingCopyCodec codec = WorkingCopyCodec::Lossless;
    /// 2 (best) to 31 (worst), FFmpeg's own quantiser scale. Ignored by a
    /// lossless codec. The default is near the top of the useful range: a
    /// working copy exists to be analysed, and compression artefacts are
    /// exactly the kind of thing a detector will happily find an object in.
    int quality = 3;
    /// Stop after this much media. Zero converts the whole item. Used by tests
    /// to keep runs short, and by an operator who only needs a section.
    Microseconds convertUpToUs = 0;
    std::string notes;
    /// Needed only when the managed original is an encrypted container.
    const crypto::SecretKey* key = nullptr;
};

/// Progress of a conversion. Returning false cancels it, and a cancelled
/// conversion leaves no asset behind — a half-transcoded file is not a working
/// copy of anything.
struct WorkingCopyProgress {
    std::int64_t framesWritten = 0;
    Microseconds positionUs = 0;
    Microseconds durationUs = 0;
    double fractionComplete = 0.0;
};
using WorkingCopyProgressCallback = std::function<bool(const WorkingCopyProgress&)>;

/// What the conversion produced, and what it cost.
struct WorkingCopyOutcome {
    DerivedAsset asset;
    std::int64_t framesWritten = 0;
    Microseconds sourceDurationUs = 0;
    Microseconds coveredDurationUs = 0;
    std::int64_t sourceBytes = 0;
    std::int64_t workingCopyBytes = 0;
    std::string sourceCodec;
    std::string workingCopyCodec;
    bool lossless = false;
    bool audioCopied = false;
    /// Why audio is absent, when it is. Empty when audio was carried across or
    /// when the source had none.
    std::string audioDroppedReason;
    /// Every frame's presentation timestamp was checked against the original's.
    /// A working copy is only registered when this is true; see
    /// `verifyTimelineMatches`.
    bool timelineVerified = false;
    std::int64_t timestampsCompared = 0;

    /// Ratio of working-copy size to source size. Greater than one is normal
    /// and is the price of an all-intra format.
    double sizeRatio() const {
        return sourceBytes > 0 ? static_cast<double>(workingCopyBytes) /
                                     static_cast<double>(sourceBytes)
                               : 0.0;
    }
};

/// Produces an analysis-safe copy of an original, without touching the original.
///
/// ## What problem this solves
///
/// Analysis samples frames by timestamp, which means seeking — thousands of
/// times over a long recording. Some material makes that ruinous: a long GOP
/// costs hundreds of decoded frames per seek, and proprietary CCTV codecs are
/// often slow, occasionally wrong, and sometimes both. A working copy is a
/// re-encode into a format that decodes predictably and seeks in constant time,
/// so the analysis runs against something known.
///
/// ## The timeline is the whole problem
///
/// A working copy is only useful if a detection at 00:05:12.340 in it means
/// 00:05:12.340 in the original. Everything else here follows from that:
///
/// - **Timestamps are preserved exactly.** Each frame is written with the
///   source's own presentation timestamp, rescaled but never recomputed.
/// - **The frame rate is never changed, and frames are never dropped or
///   duplicated.** Converting variable-frame-rate material to a constant rate
///   is the standard way to make a transcode tidy, and it silently moves every
///   frame in the recording. TRACE will not do it. A VFR source produces a VFR
///   working copy.
/// - **The result is verified, not asserted.** After writing, the working copy
///   is reopened and its frame timestamps are compared one by one against the
///   original's. A mismatch deletes the file and fails the conversion. That
///   check is the only reason anyone should believe the two paragraphs above.
///
/// ## Deliberately not implemented: scaling
///
/// Downscaling would make analysis faster and is the obvious next parameter.
/// It is absent because every detection box would then be in working-copy
/// coordinates, and something would have to map them back — a transform that is
/// easy to get subtly wrong and impossible to notice, since wrong boxes still
/// look like boxes. It needs designing deliberately, and until it is, a working
/// copy has exactly the dimensions of its source.
///
/// ## What this is not
///
/// A working copy is **not evidence**. It is a derived asset, recorded as one,
/// with the transcode parameters in its provenance. The original's digest is
/// unchanged and the original is never written to. When analysis runs against a
/// working copy, the run says so — `analysis_runs.source_asset_id` names it —
/// because a detection found on a re-encoded derivative is a different claim
/// from one found on the original, and a lossy working copy makes that
/// difference real.
class WorkingCopyService {
public:
    WorkingCopyService(StorageLayout layout, std::shared_ptr<DerivedAssetService> derivedAssets);

    Result<WorkingCopyOutcome> create(const WorkingCopyRequest& request,
                                      const WorkingCopyProgressCallback& progress = {});

    /// Whether the linked FFmpeg can encode this codec at all.
    ///
    /// Separate from `forbiddenEncoderReason` and asked in addition to it: one
    /// says whether TRACE is permitted to use an encoder, the other whether
    /// this build contains it. Both are reported by name rather than as a
    /// generic failure, because "your FFmpeg has no FFV1 encoder" and "TRACE
    /// will not encode with libx264" send an operator to entirely different
    /// places.
    static Status encoderAvailable(WorkingCopyCodec codec);

private:
    StorageLayout layout_;
    std::shared_ptr<DerivedAssetService> derivedAssets_;
};

/// Compares the frame timestamps of two media files.
///
/// Exposed rather than kept private because it is the check that makes a
/// working copy trustworthy, and a check nobody can run independently is not
/// much of a check. The tests drive it directly, including against deliberately
/// mistimed files.
///
/// `toleranceUs` allows for the rounding that rescaling between time bases
/// genuinely causes; it does not allow for a shifted or resampled timeline,
/// which is what this exists to catch.
Result<std::int64_t> verifyTimelineMatches(const std::filesystem::path& original,
                                           const std::filesystem::path& workingCopy,
                                           const crypto::SecretKey* originalKey = nullptr,
                                           const crypto::SecretKey* workingCopyKey = nullptr,
                                           Microseconds toleranceUs = 1000,
                                           Microseconds compareUpToUs = 0);

}  // namespace trace
