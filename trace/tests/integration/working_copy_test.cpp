// Working copies — an analysis-safe re-encode of an original that shares its
// timeline, produced without touching the original.
//
// The case worth stating up front is `RefusesGplEncoders`. The Linux FFmpeg
// these tests run against is built --enable-gpl and offers libx264, so an
// implementation that reached for it would work here and fail only on the
// Windows CI job, which resolves an LGPL build without it. That would look like
// a portability bug and would actually be a licensing violation, so the refusal
// is asserted rather than left to a comment.
#include <gtest/gtest.h>

#include <cstdlib>
#include <functional>
#include <fstream>
#include <set>

#include "core/common/uuid.h"
#include "core/repositories/audit_repository.h"
#include "core/security/file_hasher.h"
#include "ai/detection/providers/mock_detection_provider.h"
#include "ai/detection/detection_provider_registry.h"
#include "ai/detection/models/model_manager.h"
#include "analysis/analysis_pipeline.h"
#include "media/ffmpeg/video_decoder.h"
#include "media/working/working_copy_service.h"
#include "tests/support/test_environment.h"

extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
}

namespace trace {
namespace {

constexpr std::int64_t kFrameDurationUs = 40'000;  // the sample is 25 fps

/// A case with one imported video and a working-copy service over it.
struct Fixture {
    testing::TemporaryDirectory dataRoot{"trace-working"};
    testing::TestStack stack = testing::TestStack::create(dataRoot.path());
    Case caseRecord;
    Evidence evidence;

    Fixture() {
        const auto incoming = dataRoot.path() / "incoming";
        std::filesystem::create_directories(incoming);
        const auto source = incoming / "sample.mp4";
        std::filesystem::copy_file(testing::sampleVideoPath(), source);

        CaseDraft draft;
        draft.caseNumber = "CASE-0001";
        draft.title = "Working copies";
        draft.investigator = "A. Analyst";
        caseRecord = stack.cases->createCase(draft).value();

        IngestRequest request;
        request.caseId = caseRecord.id;
        request.sourcePath = source;
        evidence = stack.evidence->ingest(request).value().evidence;
    }

    WorkingCopyService service() { return WorkingCopyService(*stack.layout, stack.derivedAssets); }

    WorkingCopyRequest request(WorkingCopyCodec codec = WorkingCopyCodec::MotionJpeg) {
        WorkingCopyRequest r;
        r.caseId = caseRecord.id;
        r.caseNumber = caseRecord.caseNumber;
        r.evidence = evidence;
        r.codec = codec;
        return r;
    }

    std::filesystem::path managedOriginal() const {
        return stack.layout->resolve(evidence.storageRelPath);
    }
};

/// Every video packet's keyframe flag and presentation timestamp.
struct PacketFacts {
    std::int64_t total = 0;
    std::int64_t keyFrames = 0;
    std::vector<std::int64_t> presentationUs;
};

PacketFacts readPacketFacts(const std::filesystem::path& file) {
    PacketFacts facts;
    AVFormatContext* format = nullptr;
    if (avformat_open_input(&format, file.string().c_str(), nullptr, nullptr) < 0) return facts;
    if (avformat_find_stream_info(format, nullptr) < 0) {
        avformat_close_input(&format);
        return facts;
    }
    int videoStream = -1;
    for (unsigned int i = 0; i < format->nb_streams; ++i) {
        if (format->streams[i]->codecpar->codec_type == AVMEDIA_TYPE_VIDEO) {
            videoStream = static_cast<int>(i);
            break;
        }
    }
    if (videoStream < 0) {
        avformat_close_input(&format);
        return facts;
    }
    const AVRational timeBase = format->streams[videoStream]->time_base;
    AVPacket* packet = av_packet_alloc();
    while (av_read_frame(format, packet) >= 0) {
        if (packet->stream_index == videoStream) {
            ++facts.total;
            if ((packet->flags & AV_PKT_FLAG_KEY) != 0) ++facts.keyFrames;
            if (packet->pts != AV_NOPTS_VALUE) {
                facts.presentationUs.push_back(av_rescale_q(packet->pts, timeBase, {1, 1'000'000}));
            }
        }
        av_packet_unref(packet);
    }
    av_packet_free(&packet);
    avformat_close_input(&format);
    return facts;
}


/// Remuxes `source` into `destination`, transforming each video timestamp and
/// optionally dropping frames.
///
/// Built with libavformat rather than by shelling out to the ffmpeg CLI. The
/// CLI is not a declared build dependency and is not guaranteed to be on PATH
/// on every runner, so a test that called it would fail for a reason that had
/// nothing to do with the code under test — and would do it only on the machine
/// that lacked it. libavformat is already linked here.
///
/// Stream copy throughout: this deliberately does not re-encode, so the only
/// thing that differs from the input is the timing, which is what the check
/// being exercised looks at.
bool remuxWithTimestamps(const std::filesystem::path& source,
                         const std::filesystem::path& destination,
                         const std::function<std::int64_t(std::int64_t, std::int64_t)>& transform,
                         bool keepEveryOtherFrameOnly = false) {
    AVFormatContext* in = nullptr;
    if (avformat_open_input(&in, source.string().c_str(), nullptr, nullptr) < 0) return false;
    struct InCloser {
        AVFormatContext** f;
        ~InCloser() { if (*f != nullptr) avformat_close_input(f); }
    } inCloser{&in};
    if (avformat_find_stream_info(in, nullptr) < 0) return false;

    int videoStream = -1;
    for (unsigned int i = 0; i < in->nb_streams; ++i) {
        if (in->streams[i]->codecpar->codec_type == AVMEDIA_TYPE_VIDEO) {
            videoStream = static_cast<int>(i);
            break;
        }
    }
    if (videoStream < 0) return false;

    AVFormatContext* out = nullptr;
    if (avformat_alloc_output_context2(&out, nullptr, "matroska",
                                       destination.string().c_str()) < 0 ||
        out == nullptr) {
        return false;
    }
    struct OutCloser {
        AVFormatContext** f;
        ~OutCloser() {
            if (*f == nullptr) return;
            if ((*f)->pb != nullptr && ((*f)->oformat->flags & AVFMT_NOFILE) == 0) {
                avio_closep(&(*f)->pb);
            }
            avformat_free_context(*f);
            *f = nullptr;
        }
    } outCloser{&out};

    AVStream* outVideo = avformat_new_stream(out, nullptr);
    if (outVideo == nullptr) return false;
    if (avcodec_parameters_copy(outVideo->codecpar, in->streams[videoStream]->codecpar) < 0) {
        return false;
    }
    outVideo->codecpar->codec_tag = 0;
    outVideo->time_base = in->streams[videoStream]->time_base;

    if ((out->oformat->flags & AVFMT_NOFILE) == 0 &&
        avio_open(&out->pb, destination.string().c_str(), AVIO_FLAG_WRITE) < 0) {
        return false;
    }
    out->avoid_negative_ts = AVFMT_AVOID_NEG_TS_DISABLED;
    if (avformat_write_header(out, nullptr) < 0) return false;

    AVPacket* packet = av_packet_alloc();
    if (packet == nullptr) return false;
    std::int64_t index = 0;
    bool ok = true;
    while (av_read_frame(in, packet) >= 0) {
        if (packet->stream_index != videoStream) {
            av_packet_unref(packet);
            continue;
        }
        if (keepEveryOtherFrameOnly && (index % 2) != 0) {
            ++index;
            av_packet_unref(packet);
            continue;
        }
        if (packet->pts != AV_NOPTS_VALUE) packet->pts = transform(packet->pts, index);
        if (packet->dts != AV_NOPTS_VALUE) packet->dts = transform(packet->dts, index);
        packet->stream_index = outVideo->index;
        packet->pos = -1;
        if (av_interleaved_write_frame(out, packet) < 0) {
            ok = false;
            av_packet_unref(packet);
            break;
        }
        av_packet_unref(packet);
        ++index;
    }
    av_packet_free(&packet);
    if (ok) ok = av_write_trailer(out) >= 0;
    return ok;
}

// ─────────────────────────────────────────── the licensing boundary

TEST(WorkingCopyTest, RefusesGplEncodersByNameEvenWhenTheBuildOffersThem) {
    // Not hypothetical on this machine: the Ubuntu FFmpeg these tests link
    // against really does contain libx264.
    const bool buildHasLibx264 = avcodec_find_encoder_by_name("libx264") != nullptr;

    for (const char* name : {"libx264", "libx264rgb", "libx265", "libxvid"}) {
        const std::string reason = forbiddenEncoderReason(name);
        EXPECT_FALSE(reason.empty()) << name << " must be refused";
        EXPECT_NE(reason.find("GPL"), std::string::npos)
            << "the refusal must say why, so nobody 'fixes' it by adding the encoder";
        EXPECT_NE(reason.find("LGPL"), std::string::npos)
            << "and must name the licence TRACE actually links under";
    }

    if (buildHasLibx264) {
        SUCCEED() << "this FFmpeg offers libx264 and TRACE still refuses it, which is the point";
    }
}

TEST(WorkingCopyTest, AllowsTheEncodersItActuallyUses) {
    EXPECT_TRUE(forbiddenEncoderReason("mjpeg").empty());
    EXPECT_TRUE(forbiddenEncoderReason("ffv1").empty());
    // Both are native to FFmpeg, so any build TRACE can link has them and the
    // Windows LGPL build is not a special case.
    EXPECT_TRUE(WorkingCopyService::encoderAvailable(WorkingCopyCodec::MotionJpeg).ok())
        << "mjpeg is native to FFmpeg and must be present in every build";
    EXPECT_TRUE(WorkingCopyService::encoderAvailable(WorkingCopyCodec::Lossless).ok())
        << "ffv1 is native to FFmpeg and must be present in every build";
}

// ───────────────────────────────────────────────── the timeline claim

TEST(WorkingCopyTest, PreservesEveryFrameTimestampOfTheOriginal) {
    Fixture fixture;
    auto produced = fixture.service().create(fixture.request());
    ASSERT_TRUE(produced.ok()) << produced.error().toString();
    const WorkingCopyOutcome outcome = produced.take();

    EXPECT_TRUE(outcome.timelineVerified);
    EXPECT_EQ(outcome.framesWritten, 200) << "the sample has 200 frames and so must its copy";
    EXPECT_EQ(outcome.timestampsCompared, 200);

    // Independently of the service's own check: compare the two files here.
    const auto copy = fixture.stack.layout->resolve(outcome.asset.storageRelPath);
    const PacketFacts original = readPacketFacts(fixture.managedOriginal());
    const PacketFacts working = readPacketFacts(copy);

    ASSERT_EQ(working.presentationUs.size(), original.presentationUs.size());
    // Both measured from their own first frame, which is the clock TRACE reads:
    // VideoDecoder normalises so the first frame of a stream is zero, so that is
    // what a detection timestamp is expressed against.
    auto sortedOriginal = original.presentationUs;
    auto sortedWorking = working.presentationUs;
    std::sort(sortedOriginal.begin(), sortedOriginal.end());
    std::sort(sortedWorking.begin(), sortedWorking.end());
    for (auto& v : sortedWorking) v -= sortedWorking.front();
    for (auto& v : sortedOriginal) v -= sortedOriginal.front();
    for (std::size_t i = 0; i < sortedOriginal.size(); ++i) {
        EXPECT_NEAR(static_cast<double>(sortedWorking[i]), static_cast<double>(sortedOriginal[i]),
                    1000.0)
            << "frame " << i << " moved, so a detection on it would be reported at the wrong time";
    }
}

TEST(WorkingCopyTest, EveryFrameIsAKeyframeSoSeekingIsConstantTime) {
    Fixture fixture;
    auto produced = fixture.service().create(fixture.request());
    ASSERT_TRUE(produced.ok()) << produced.error().toString();

    const auto copy = fixture.stack.layout->resolve(produced.value().asset.storageRelPath);
    const PacketFacts working = readPacketFacts(copy);
    const PacketFacts original = readPacketFacts(fixture.managedOriginal());

    EXPECT_EQ(working.keyFrames, working.total)
        << "all-intra is the property the whole feature exists for";
    EXPECT_LT(original.keyFrames, original.total)
        << "the fixture must have a long GOP or this test proves nothing";
}

TEST(WorkingCopyTest, TheTimelineCheckCatchesAStretchedTimeline) {
    Fixture fixture;
    auto produced = fixture.service().create(fixture.request());
    ASSERT_TRUE(produced.ok()) << produced.error().toString();
    const auto copy = fixture.stack.layout->resolve(produced.value().asset.storageRelPath);

    // Against itself: no drift.
    auto same = verifyTimelineMatches(copy, copy);
    ASSERT_TRUE(same.ok()) << same.error().toString();
    EXPECT_EQ(same.value(), 200);

    // The dangerous distortion, because it survives every cheaper check: the
    // same 200 frames, in the same order, each one moved a different amount.
    // A frame-count comparison passes, the file plays, and every detection
    // after the first is reported at the wrong moment — increasingly so.
    const auto stretched = fixture.dataRoot.path() / "stretched.mkv";
    ASSERT_TRUE(remuxWithTimestamps(copy, stretched, [](std::int64_t ts, std::int64_t) {
        return (ts * 3) / 2;
    }));

    auto drifted = verifyTimelineMatches(fixture.managedOriginal(), stretched);
    ASSERT_FALSE(drifted.ok()) << "a stretched timeline must not pass as the same timeline";
    EXPECT_EQ(drifted.error().code(), ErrorCode::IntegrityFailure);
    EXPECT_NE(drifted.error().message().find("wrong moment"), std::string::npos)
        << "the message should say what the consequence is, not just that numbers differ";
}

TEST(WorkingCopyTest, AUniformOffsetIsDeliberatelyAccepted) {
    Fixture fixture;
    auto produced = fixture.service().create(fixture.request());
    ASSERT_TRUE(produced.ok()) << produced.error().toString();
    const auto copy = fixture.stack.layout->resolve(produced.value().asset.storageRelPath);

    // Moving the whole recording by a constant is the one distortion that
    // cannot misplace a detection, because TRACE never reads absolute container
    // time: VideoDecoder normalises so the first frame of a stream is zero, and
    // every position in the application is on that clock. Rejecting a uniform
    // offset would fail files that are, to TRACE, identical — so it is accepted
    // on purpose, and this test is here to say that it is a decision rather
    // than a gap.
    const auto offset = fixture.dataRoot.path() / "offset.mkv";
    ASSERT_TRUE(remuxWithTimestamps(copy, offset, [](std::int64_t ts, std::int64_t) {
        return ts + 2000;  // the copy's time base is milliseconds
    }));

    auto shifted = verifyTimelineMatches(fixture.managedOriginal(), offset);
    EXPECT_TRUE(shifted.ok()) << "a uniform offset is unobservable to TRACE and must not be "
                                 "reported as a broken timeline: "
                              << (shifted.ok() ? std::string{} : shifted.error().toString());
}

TEST(WorkingCopyTest, TheTimelineCheckCatchesAMissingFrame) {
    Fixture fixture;
    auto produced = fixture.service().create(fixture.request());
    ASSERT_TRUE(produced.ok()) << produced.error().toString();
    const auto copy = fixture.stack.layout->resolve(produced.value().asset.storageRelPath);

    // Half the frames, same timeline origin: the kind of thing a frame-rate
    // conversion produces, and the reason TRACE never does one.
    const auto decimated = fixture.dataRoot.path() / "decimated.mkv";
    ASSERT_TRUE(remuxWithTimestamps(
        copy, decimated, [](std::int64_t ts, std::int64_t) { return ts; }, true));

    auto dropped = verifyTimelineMatches(fixture.managedOriginal(), decimated);
    ASSERT_FALSE(dropped.ok());
    EXPECT_EQ(dropped.error().code(), ErrorCode::IntegrityFailure);
    EXPECT_NE(dropped.error().message().find("frames"), std::string::npos);
}

// ─────────────────────────────────────────────── lossless really is

TEST(WorkingCopyTest, ALosslessCopyDecodesToTheOriginalsExactPixels) {
    Fixture fixture;
    auto produced = fixture.service().create(fixture.request(WorkingCopyCodec::Lossless));
    ASSERT_TRUE(produced.ok()) << produced.error().toString();
    const WorkingCopyOutcome outcome = produced.take();
    EXPECT_TRUE(outcome.lossless);

    auto originalDecoder = VideoDecoder::open(fixture.managedOriginal());
    ASSERT_TRUE(originalDecoder.ok()) << originalDecoder.error().toString();
    auto copyDecoder =
        VideoDecoder::open(fixture.stack.layout->resolve(outcome.asset.storageRelPath));
    ASSERT_TRUE(copyDecoder.ok()) << copyDecoder.error().toString();

    // Several frames spread through the recording rather than only the first,
    // which any codec gets right.
    for (std::int64_t index : {0, 37, 99, 150}) {
        const Microseconds at = index * kFrameDurationUs;
        auto fromOriginal = originalDecoder.value()->frameAt(at);
        auto fromCopy = copyDecoder.value()->frameAt(at);
        ASSERT_TRUE(fromOriginal.ok()) << fromOriginal.error().toString();
        ASSERT_TRUE(fromCopy.ok()) << fromCopy.error().toString();
        EXPECT_EQ(fromCopy.value().rgb, fromOriginal.value().rgb)
            << "frame " << index << " differs, so this codec is not lossless after all";
    }
}

TEST(WorkingCopyTest, ALossyCopyIsHonestlyLabelledAsLossy) {
    Fixture fixture;
    auto produced = fixture.service().create(fixture.request(WorkingCopyCodec::MotionJpeg));
    ASSERT_TRUE(produced.ok()) << produced.error().toString();
    EXPECT_FALSE(produced.value().lossless);

    auto operations = fixture.stack.derivedAssets->operationsForEvidence(fixture.evidence.id);
    ASSERT_TRUE(operations.ok());
    ASSERT_FALSE(operations.value().empty());
    const std::string parameters = operations.value().back().parametersJson;
    EXPECT_NE(parameters.find("\"lossless\""), std::string::npos);
    EXPECT_NE(parameters.find("lossy_warning"), std::string::npos)
        << "a lossy working copy must carry the warning into its provenance, because a report "
           "citing a detection found on it is citing re-compressed pixels";
}

// ──────────────────────────────────────────────────────── provenance

TEST(WorkingCopyTest, IsRecordedAsADerivedAssetNamingTheTranscode) {
    Fixture fixture;
    auto produced = fixture.service().create(fixture.request());
    ASSERT_TRUE(produced.ok()) << produced.error().toString();
    const WorkingCopyOutcome outcome = produced.take();

    EXPECT_EQ(outcome.asset.type, DerivedAssetType::WorkingCopy);
    EXPECT_EQ(outcome.asset.evidenceId, fixture.evidence.id);
    EXPECT_TRUE(outcome.asset.sha256.has_value());
    EXPECT_EQ(outcome.asset.verificationState, VerificationState::Unverified)
        << "TRACE never marks its own output as verified";
    EXPECT_NE(outcome.asset.storageRelPath.find("working/"), std::string::npos)
        << "a working copy belongs in working/, not beside the originals";

    auto operations = fixture.stack.derivedAssets->operationsForEvidence(fixture.evidence.id);
    ASSERT_TRUE(operations.ok());
    const auto& operation = operations.value().back();
    EXPECT_EQ(operation.operationType, "working_copy");

    // The parameters have to be enough for someone to reproduce the file.
    for (const char* key : {"codec", "source_codec", "all_intra", "timeline_verified",
                            "timestamps_compared", "frame_rate_changed", "scaled", "width",
                            "height", "source_sha256"}) {
        EXPECT_NE(operation.parametersJson.find(std::string("\"") + key + "\""), std::string::npos)
            << key << " is missing from the provenance record";
    }
    EXPECT_NE(operation.parametersJson.find(fixture.evidence.sha256), std::string::npos)
        << "the provenance must name the digest of the original it came from";
}

TEST(WorkingCopyTest, IsAudited) {
    Fixture fixture;
    ASSERT_TRUE(fixture.service().create(fixture.request()).ok());

    AuditQuery query;
    query.caseId = fixture.caseRecord.id;
    query.action = AuditAction::WorkingCopyCreated;
    auto events = fixture.stack.audit->list(query);
    ASSERT_TRUE(events.ok()) << events.error().toString();
    EXPECT_EQ(events.value().size(), 1u)
        << "creating a working copy must be its own audit action, so 'which working copies "
           "exist' is answerable from the trail by filtering rather than by reading it";
    ASSERT_FALSE(events.value().empty());
    EXPECT_NE(events.value().front().description.find("timeline verified"), std::string::npos);
}

// ─────────────────────────────────────── the original is untouched

TEST(WorkingCopyTest, LeavesTheOriginalByteForByteUnchanged) {
    Fixture fixture;
    const auto original = fixture.managedOriginal();
    const auto before = hashFile(original);
    ASSERT_TRUE(before.ok());
    const auto sizeBefore = std::filesystem::file_size(original);

    ASSERT_TRUE(fixture.service().create(fixture.request()).ok());
    ASSERT_TRUE(fixture.service().create(fixture.request(WorkingCopyCodec::Lossless)).ok());

    const auto after = hashFile(original);
    ASSERT_TRUE(after.ok());
    EXPECT_EQ(after.value(), before.value());
    EXPECT_EQ(std::filesystem::file_size(original), sizeBefore);
    EXPECT_EQ(after.value(), fixture.evidence.sha256)
        << "and it still matches the digest recorded at ingestion";
}

// ─────────────────────────────────────────────── refusals and limits

TEST(WorkingCopyTest, CancellingKeepsNothing) {
    Fixture fixture;
    const auto workingDirectory = fixture.stack.layout->workingDirectory(fixture.caseRecord.id);

    auto produced = fixture.service().create(fixture.request(), [](const WorkingCopyProgress& p) {
        return p.framesWritten < 10;  // stop part-way
    });
    ASSERT_FALSE(produced.ok());
    EXPECT_EQ(produced.error().code(), ErrorCode::Cancelled);

    std::int64_t files = 0;
    if (std::filesystem::exists(workingDirectory)) {
        for (const auto& entry : std::filesystem::directory_iterator(workingDirectory)) {
            if (entry.is_regular_file()) ++files;
        }
    }
    EXPECT_EQ(files, 0) << "a half-converted file is not a working copy of anything";

    auto assets = fixture.stack.derivedAssets->listForEvidence(fixture.evidence.id);
    ASSERT_TRUE(assets.ok());
    for (const auto& asset : assets.value()) {
        EXPECT_NE(asset.type, DerivedAssetType::WorkingCopy)
            << "a cancelled conversion must not leave a row claiming one exists";
    }
}

TEST(WorkingCopyTest, ConvertingPartOfARecordingSaysSo) {
    Fixture fixture;
    auto request = fixture.request();
    request.convertUpToUs = 2'000'000;  // 2 of the sample's 8 seconds
    auto produced = fixture.service().create(request);
    ASSERT_TRUE(produced.ok()) << produced.error().toString();

    EXPECT_LT(produced.value().framesWritten, 200);
    EXPECT_GT(produced.value().framesWritten, 0);

    auto operations = fixture.stack.derivedAssets->operationsForEvidence(fixture.evidence.id);
    ASSERT_TRUE(operations.ok());
    EXPECT_NE(operations.value().back().parametersJson.find("\"partial\""), std::string::npos)
        << "a partial working copy must not read as a copy of the whole recording";
}

TEST(WorkingCopyTest, RejectsAQualityOutsideTheScale) {
    Fixture fixture;
    auto request = fixture.request();
    request.quality = 0;
    auto produced = fixture.service().create(request);
    ASSERT_FALSE(produced.ok());
    EXPECT_EQ(produced.error().code(), ErrorCode::InvalidArgument);
}

TEST(WorkingCopyTest, DefaultsToLossless) {
    // A decision, not an accident. Lossless cost 45% more than Motion JPEG at
    // 1080p in the only measurements taken, against a claim that is
    // categorically stronger: detections found on it were found on the
    // original's own pixels. The header records both numbers.
    WorkingCopyRequest request;
    EXPECT_EQ(request.codec, WorkingCopyCodec::Lossless);
    EXPECT_TRUE(isLossless(request.codec));
}

TEST(WorkingCopyTest, ReportsWhatTheCopyCost) {
    Fixture fixture;
    auto produced = fixture.service().create(fixture.request());
    ASSERT_TRUE(produced.ok()) << produced.error().toString();
    const WorkingCopyOutcome outcome = produced.take();

    EXPECT_GT(outcome.sourceBytes, 0);
    EXPECT_GT(outcome.workingCopyBytes, 0);
    EXPECT_GT(outcome.sizeRatio(), 0.0);
    EXPECT_EQ(outcome.sourceCodec, "h264");
    EXPECT_EQ(outcome.workingCopyCodec, "mjpeg");
}

// ───────────────────────── what a run over a working copy records

TEST(WorkingCopyTest, AnalysisOverAWorkingCopyRecordsThatItWasNotTheOriginal) {
    registerBuiltinDetectionProviders();
    Fixture fixture;

    auto produced = fixture.service().create(fixture.request(WorkingCopyCodec::MotionJpeg));
    ASSERT_TRUE(produced.ok()) << produced.error().toString();
    const DerivedAsset copy = produced.value().asset;

    AnalysisPipeline pipeline(fixture.stack.analysis, ModelManager(testing::modelsDirectory()),
                              *fixture.stack.layout);

    DetectionAnalysisRequest request;
    request.caseId = fixture.caseRecord.id;
    request.caseNumber = fixture.caseRecord.caseNumber;
    request.evidenceId = fixture.evidence.id;
    request.evidenceNumber = fixture.evidence.evidenceNumber;
    request.mediaPath = fixture.stack.layout->resolve(copy.storageRelPath);
    request.evidenceSha256 = fixture.evidence.sha256;
    request.providerId = MockDetectionProvider::kProviderId;
    request.quality = AnalysisQuality::Fast;
    request.analyseUpToUs = 1'000'000;
    request.sourceAssetId = copy.id;
    request.sourceDescription = "a lossy Motion JPEG working copy";

    auto outcome = pipeline.execute(request);
    ASSERT_TRUE(outcome.ok()) << outcome.error().toString();
    const AnalysisRun run = outcome.value().run;

    ASSERT_TRUE(run.sourceAssetId.has_value())
        << "a run over a working copy that did not say so would present detections from "
           "re-compressed pixels as though they came from the evidence";
    EXPECT_EQ(run.sourceAssetId.value(), copy.id);
    ASSERT_TRUE(run.sourceDescription.has_value());
    EXPECT_NE(run.sourceDescription.value().find("lossy"), std::string::npos);
    EXPECT_NE(run.configurationJson.find("\"analysed_the_original\""), std::string::npos);

    // The evidence digest is still the evidence's own. A working copy does not
    // change what the evidence is, and a report citing this run cites that.
    EXPECT_EQ(run.evidenceSha256, fixture.evidence.sha256);

    // And it survives a reload, because that is where a report reads it from.
    auto reloaded = fixture.stack.analysis->runsForEvidence(fixture.evidence.id);
    ASSERT_TRUE(reloaded.ok()) << reloaded.error().toString();
    ASSERT_FALSE(reloaded.value().empty());
    const AnalysisRun stored = reloaded.value().front();
    EXPECT_EQ(stored.id, run.id);
    EXPECT_EQ(stored.sourceAssetId.value_or(""), copy.id);
    EXPECT_NE(stored.sourceDescription.value_or("").find("lossy"), std::string::npos);
}

TEST(WorkingCopyTest, AnalysisOverTheOriginalLeavesTheSourceAssetUnset) {
    registerBuiltinDetectionProviders();
    Fixture fixture;

    AnalysisPipeline pipeline(fixture.stack.analysis, ModelManager(testing::modelsDirectory()),
                              *fixture.stack.layout);

    DetectionAnalysisRequest request;
    request.caseId = fixture.caseRecord.id;
    request.caseNumber = fixture.caseRecord.caseNumber;
    request.evidenceId = fixture.evidence.id;
    request.evidenceNumber = fixture.evidence.evidenceNumber;
    request.mediaPath = fixture.managedOriginal();
    request.evidenceSha256 = fixture.evidence.sha256;
    request.providerId = MockDetectionProvider::kProviderId;
    request.quality = AnalysisQuality::Fast;
    request.analyseUpToUs = 1'000'000;

    auto outcome = pipeline.execute(request);
    ASSERT_TRUE(outcome.ok()) << outcome.error().toString();

    // Unset means the original. Every run recorded before working copies
    // existed is unset, so this must keep meaning exactly that.
    EXPECT_FALSE(outcome.value().run.sourceAssetId.has_value());
    EXPECT_NE(outcome.value().run.configurationJson.find("the managed original evidence file"),
              std::string::npos);
}

}  // namespace
}  // namespace trace
