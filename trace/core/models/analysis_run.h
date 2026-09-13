#pragma once

#include <cstdint>
#include <optional>
#include <string>

namespace trace {

/// Lifecycle of an analysis run.
///
/// A run that did not finish its work is never Completed. Cancelled and Partial
/// are distinct outcomes and both are honest: Cancelled means the operator
/// stopped it, Partial means it stopped itself part-way (a decode failure after
/// some frames had already been analysed) and kept what it had.
enum class AnalysisRunStatus {
    Queued,
    Running,
    Paused,
    Completed,
    Cancelled,
    Failed,
    Partial,
};

const char* toString(AnalysisRunStatus status);
const char* toDisplayString(AnalysisRunStatus status);
AnalysisRunStatus analysisRunStatusFromString(const std::string& text,
                                              AnalysisRunStatus fallback = AnalysisRunStatus::Queued);
/// True when the run reached a state it will not leave.
bool isTerminal(AnalysisRunStatus status);
/// True when the run produced results that can be trusted as complete.
bool producedCompleteResults(AnalysisRunStatus status);

/// One execution of an analysis over one evidence item.
///
/// This record is the provenance anchor for every detection it produced: it
/// names the provider, the model, the model version and the SHA-256 of the exact
/// model file, alongside the digest the evidence had when the run started.
struct AnalysisRun {
    std::string id;
    std::string caseId;
    std::string evidenceId;
    std::string analysisType = "object_detection";

    std::string providerName;
    std::string providerVersion;
    std::string runtime;               ///< e.g. "ONNX Runtime 1.17.3"
    std::string modelName;
    std::string modelVersion;
    std::optional<std::string> modelSha256;
    std::optional<std::string> modelRelPath;

    std::string deviceRequested = "auto";
    std::string deviceUsed;
    std::string configurationJson = "{}";

    AnalysisRunStatus status = AnalysisRunStatus::Queued;
    std::optional<std::string> startedAt;
    std::optional<std::string> completedAt;

    std::int64_t framesAnalyzed = 0;
    std::optional<std::int64_t> framesExpected;
    std::int64_t detectionsStored = 0;
    std::optional<std::int64_t> analyzedDurationUs;
    /// Minimum spacing between analysed frames, in microseconds; 0 means every
    /// decoded frame was analysed.
    std::optional<std::int64_t> samplingIntervalUs;
    std::optional<std::int64_t> sourceWidth;
    std::optional<std::int64_t> sourceHeight;
    /// The digest the *evidence* had when the run started, whatever was
    /// actually decoded. A working copy does not change what the evidence is.
    std::string evidenceSha256;

    /// The working copy this run analysed, when it did not analyse the
    /// original. Empty means the original, which is the only thing runs
    /// recorded before working copies existed could have meant.
    ///
    /// A detection found on a lossy working copy was found on re-compressed
    /// pixels, so this is not bookkeeping: it is the difference between two
    /// claims about what was observed, and a report has to be able to tell them
    /// apart.
    std::optional<std::string> sourceAssetId;
    /// The same fact in words, kept because it has to outlive the asset row.
    /// Deleting a working copy to reclaim disk clears `sourceAssetId` but must
    /// not turn a run over a lossy copy into one that reads as having examined
    /// the original.
    std::optional<std::string> sourceDescription;

    std::optional<std::string> errorMessage;
    std::string warningsJson = "[]";
    std::string createdBy;
    std::string createdAt;
};

}  // namespace trace
