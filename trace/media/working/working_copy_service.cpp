#include "media/working/working_copy_service.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <system_error>
#include <vector>

#include "core/common/logging.h"
#include "core/common/uuid.h"
#include "media/ffmpeg/encrypted_io.h"
#include "media/ffmpeg/ffmpeg_support.h"

extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/imgutils.h>
#include <libavutil/mathematics.h>
#include <libavutil/opt.h>
#include <libavutil/pixdesc.h>
#include <libswscale/swscale.h>
}

namespace trace {
namespace {

constexpr const char* kComponent = "working-copy";
constexpr AVRational kMicroseconds{1, 1'000'000};

/// Encoders TRACE will not call, and why.
///
/// All GPL. Listed by name because the check has to survive being linked
/// against a build that happily offers them — which the Ubuntu system FFmpeg
/// does, and which is exactly how this would otherwise go unnoticed until a
/// Windows build failed for what looks like an unrelated reason.
struct ForbiddenEncoder {
    const char* name;
    const char* licence;
};
constexpr std::array<ForbiddenEncoder, 6> kForbiddenEncoders{{
    {"libx264", "GPL"},
    {"libx264rgb", "GPL"},
    {"libx265", "GPL"},
    {"libxvid", "GPL"},
    {"libxavs", "GPL"},
    {"libdavs2", "GPL"},
}};

const char* encoderNameFor(WorkingCopyCodec codec) {
    switch (codec) {
        case WorkingCopyCodec::MotionJpeg: return "mjpeg";
        case WorkingCopyCodec::Lossless:   return "ffv1";
    }
    return "mjpeg";
}

Microseconds toMicroseconds(std::int64_t timestamp, AVRational timeBase) {
    if (timestamp == AV_NOPTS_VALUE) return AV_NOPTS_VALUE;
    return av_rescale_q(timestamp, timeBase, kMicroseconds);
}

/// Closes FFmpeg handles however the function exits, and releases the output
/// before the destructor would.
///
/// The early close is not tidiness: registering a derived asset rewrites the
/// file in place in an encrypted workspace, and Windows refuses to replace a
/// file that still has an open handle. `ClipExportService` carries the same
/// structure for the same reason.
struct TranscodeContexts {
    AVFormatContext* input = nullptr;
    AVFormatContext* output = nullptr;
    AVCodecContext* decoder = nullptr;
    AVCodecContext* encoder = nullptr;
    SwsContext* scaler = nullptr;
    AVFrame* decoded = nullptr;
    AVFrame* converted = nullptr;
    AVPacket* packet = nullptr;
    AVPacket* encodedPacket = nullptr;

    void closeOutput() {
        if (output == nullptr) return;
        if (output->pb != nullptr && (output->oformat->flags & AVFMT_NOFILE) == 0) {
            avio_closep(&output->pb);
        }
        avformat_free_context(output);
        output = nullptr;
    }

    ~TranscodeContexts() {
        if (packet != nullptr) av_packet_free(&packet);
        if (encodedPacket != nullptr) av_packet_free(&encodedPacket);
        if (decoded != nullptr) av_frame_free(&decoded);
        if (converted != nullptr) av_frame_free(&converted);
        if (scaler != nullptr) sws_freeContext(scaler);
        if (encoder != nullptr) avcodec_free_context(&encoder);
        if (decoder != nullptr) avcodec_free_context(&decoder);
        closeOutput();
        if (input != nullptr) avformat_close_input(&input);
    }
};

/// The full-range twin of a limited-range format, or NONE.
///
/// JPEG — and therefore Motion JPEG — is defined over full-range samples, and
/// FFmpeg still spells that as a separate `yuvj*` pixel format. The encoder
/// will take the limited-range format too, but only with
/// `strict_std_compliance` relaxed, which produces a file other tools are
/// entitled to read differently. Converting properly is the correct answer.
AVPixelFormat fullRangeTwin(AVPixelFormat limited) {
    switch (limited) {
        case AV_PIX_FMT_YUV420P: return AV_PIX_FMT_YUVJ420P;
        case AV_PIX_FMT_YUV422P: return AV_PIX_FMT_YUVJ422P;
        case AV_PIX_FMT_YUV444P: return AV_PIX_FMT_YUVJ444P;
        case AV_PIX_FMT_YUV440P: return AV_PIX_FMT_YUVJ440P;
        case AV_PIX_FMT_YUV411P: return AV_PIX_FMT_YUVJ411P;
        default:                 return AV_PIX_FMT_NONE;
    }
}

bool encoderAccepts(const AVCodec* encoder, AVPixelFormat format) {
    if (encoder->pix_fmts == nullptr) return true;
    for (const AVPixelFormat* p = encoder->pix_fmts; *p != AV_PIX_FMT_NONE; ++p) {
        if (*p == format) return true;
    }
    return false;
}

/// The pixel format to encode in, asked of the encoder itself rather than of a
/// table here that would drift out of step with FFmpeg.
///
/// The two codecs want opposite things, and the difference is not cosmetic:
///
/// - **Lossless must never convert.** Any resampling of chroma or of sample
///   range makes "identical pixels" untrue while leaving the picture still
///   looking right, which is the worst way for a claim like that to fail. So
///   the source format wins or the conversion is refused.
/// - **MJPEG must convert.** JPEG is defined over full-range samples. FFmpeg's
///   mjpeg encoder advertises the limited-range formats too, and then refuses
///   to open with them unless `strict_std_compliance` is relaxed — which would
///   produce a technically non-conforming JPEG that other tools are entitled to
///   read differently. Preferring the full-range twin is the standards-
///   compliant answer. It costs the out-of-gamut samples: source values outside
///   the limited range are clipped by the conversion, which is recorded in the
///   asset's parameters rather than left for someone to discover.
AVPixelFormat pixelFormatFor(const AVCodec* encoder, AVPixelFormat source, bool lossless) {
    if (encoder->pix_fmts == nullptr) return source;

    if (lossless) return encoderAccepts(encoder, source) ? source : AV_PIX_FMT_NONE;

    if (const AVPixelFormat full = fullRangeTwin(source);
        full != AV_PIX_FMT_NONE && encoderAccepts(encoder, full)) {
        return full;
    }
    if (encoderAccepts(encoder, source)) return source;
    return encoder->pix_fmts[0];
}

/// True for the deprecated `yuvj*` formats, which mean "full range".
bool isFullRange(AVPixelFormat format) {
    switch (format) {
        case AV_PIX_FMT_YUVJ420P:
        case AV_PIX_FMT_YUVJ422P:
        case AV_PIX_FMT_YUVJ444P:
        case AV_PIX_FMT_YUVJ440P:
        case AV_PIX_FMT_YUVJ411P:
            return true;
        default:
            return false;
    }
}

/// Reads every video presentation timestamp from a file, in order.
Result<std::vector<Microseconds>> readVideoTimestamps(const std::filesystem::path& file,
                                                      const crypto::SecretKey* key,
                                                      Microseconds upToUs) {
    using ResultType = Result<std::vector<Microseconds>>;
    EncryptedMediaIo io;
    AVFormatContext* format = nullptr;
    std::string url;
    if (auto status = io.prepare(&format, file, key, &url); !status) {
        return ResultType(status.error());
    }
    int rc = avformat_open_input(&format, url.empty() ? nullptr : url.c_str(), nullptr, nullptr);
    if (rc < 0) {
        return ResultType::failure(ErrorCode::MediaError,
                                   "Could not open " + file.filename().string() + ": " +
                                       ffmpegErrorString(rc));
    }
    struct Closer {
        AVFormatContext** f;
        ~Closer() { if (*f != nullptr) avformat_close_input(f); }
    } closer{&format};

    rc = avformat_find_stream_info(format, nullptr);
    if (rc < 0) {
        return ResultType::failure(ErrorCode::MediaError,
                                   "Could not read stream information from " +
                                       file.filename().string());
    }
    int videoStream = -1;
    for (unsigned int i = 0; i < format->nb_streams; ++i) {
        if (format->streams[i]->codecpar->codec_type == AVMEDIA_TYPE_VIDEO) {
            videoStream = static_cast<int>(i);
            break;
        }
    }
    if (videoStream < 0) {
        return ResultType::failure(ErrorCode::MediaError,
                                   file.filename().string() + " has no video stream");
    }

    const AVRational timeBase = format->streams[videoStream]->time_base;

    std::vector<Microseconds> timestamps;
    AVPacket* packet = av_packet_alloc();
    if (packet == nullptr) {
        return ResultType::failure(ErrorCode::Internal, "Out of memory allocating a packet");
    }
    while (av_read_frame(format, packet) >= 0) {
        if (packet->stream_index == videoStream && packet->pts != AV_NOPTS_VALUE) {
            timestamps.push_back(toMicroseconds(packet->pts, timeBase));
        }
        av_packet_unref(packet);
    }
    av_packet_free(&packet);

    // Packets arrive in decode order; presentation order is what a detection
    // timestamp means.
    std::sort(timestamps.begin(), timestamps.end());

    // Normalised against the first frame actually present, not against the
    // container's declared start_time.
    //
    // The distinction caught a real defect. Reading start_time here made the
    // check agree with a file whose video had been dragged 23ms forward by the
    // muxer, because the muxer had updated start_time to match — the check was
    // comparing each file against its own metadata and finding, unsurprisingly,
    // that both were self-consistent. Measuring from the first frame compares
    // the two recordings instead, and it is also the timeline TRACE itself
    // reads: VideoDecoder normalises so the first frame of the stream is zero,
    // so this is the same clock a detection timestamp is expressed on.
    if (!timestamps.empty()) {
        const Microseconds origin = timestamps.front();
        for (Microseconds& value : timestamps) value -= origin;
    }
    if (upToUs > 0) {
        timestamps.erase(std::remove_if(timestamps.begin(), timestamps.end(),
                                        [&](Microseconds t) { return t > upToUs; }),
                         timestamps.end());
    }
    return ResultType::success(std::move(timestamps));
}

}  // namespace

const char* toString(WorkingCopyCodec codec) {
    switch (codec) {
        case WorkingCopyCodec::MotionJpeg: return "mjpeg";
        case WorkingCopyCodec::Lossless:   return "ffv1";
    }
    return "mjpeg";
}

const char* toDisplayString(WorkingCopyCodec codec) {
    switch (codec) {
        case WorkingCopyCodec::MotionJpeg: return "Motion JPEG (all-intra, lossy)";
        case WorkingCopyCodec::Lossless:   return "FFV1 (all-intra, lossless)";
    }
    return "Motion JPEG (all-intra, lossy)";
}

bool isLossless(WorkingCopyCodec codec) { return codec == WorkingCopyCodec::Lossless; }

std::string forbiddenEncoderReason(const std::string& encoderName) {
    for (const auto& entry : kForbiddenEncoders) {
        if (encoderName == entry.name) {
            return std::string(entry.name) + " is " + entry.licence +
                   "-licensed. TRACE links FFmpeg under the LGPL, and calling into a " +
                   entry.licence +
                   " encoder would place TRACE itself under that licence when distributed. "
                   "Use an encoder native to FFmpeg instead.";
        }
    }
    return {};
}

Status WorkingCopyService::encoderAvailable(WorkingCopyCodec codec) {
    initialiseFFmpeg();
    const char* name = encoderNameFor(codec);
    if (std::string reason = forbiddenEncoderReason(name); !reason.empty()) {
        return Status::failure(ErrorCode::PermissionDenied, reason);
    }
    if (avcodec_find_encoder_by_name(name) == nullptr) {
        return Status::failure(ErrorCode::Unsupported,
                               std::string("This FFmpeg build has no ") + name +
                                   " encoder, so a " + toDisplayString(codec) +
                                   " working copy cannot be produced on this machine.");
    }
    return Status::success();
}

Result<std::int64_t> verifyTimelineMatches(const std::filesystem::path& original,
                                           const std::filesystem::path& workingCopy,
                                           const crypto::SecretKey* originalKey,
                                           const crypto::SecretKey* workingCopyKey,
                                           Microseconds toleranceUs,
                                           Microseconds compareUpToUs) {
    using ResultType = Result<std::int64_t>;
    initialiseFFmpeg();

    auto sourceTimes = readVideoTimestamps(original, originalKey, compareUpToUs);
    if (!sourceTimes) return ResultType(sourceTimes.error());
    auto copyTimes = readVideoTimestamps(workingCopy, workingCopyKey, compareUpToUs);
    if (!copyTimes) return ResultType(copyTimes.error());

    const auto& a = sourceTimes.value();
    const auto& b = copyTimes.value();

    if (b.size() != a.size()) {
        return ResultType::failure(
            ErrorCode::IntegrityFailure,
            "The working copy has " + std::to_string(b.size()) + " frames where the original has " +
                std::to_string(a.size()) +
                ". A working copy must contain exactly the frames of its source: dropping or "
                "duplicating any of them moves every detection timestamp after it.");
    }

    for (std::size_t i = 0; i < a.size(); ++i) {
        const Microseconds drift = std::llabs(b[i] - a[i]);
        if (drift > toleranceUs) {
            return ResultType::failure(
                ErrorCode::IntegrityFailure,
                "Frame " + std::to_string(i) + " is at " + formatTimecode(b[i]) +
                    " in the working copy but at " + formatTimecode(a[i]) +
                    " in the original, a difference of " + std::to_string(drift) +
                    "us. A detection found on this working copy would be reported at the "
                    "wrong moment in the original.");
        }
    }
    return ResultType::success(static_cast<std::int64_t>(a.size()));
}

WorkingCopyService::WorkingCopyService(StorageLayout layout,
                                       std::shared_ptr<DerivedAssetService> derivedAssets)
    : layout_(std::move(layout)), derivedAssets_(std::move(derivedAssets)) {}

Result<WorkingCopyOutcome> WorkingCopyService::create(
    const WorkingCopyRequest& request, const WorkingCopyProgressCallback& progress) {
    using ResultType = Result<WorkingCopyOutcome>;
    initialiseFFmpeg();

    if (request.quality < 2 || request.quality > 31) {
        return ResultType::failure(ErrorCode::InvalidArgument,
                                   "Quality must be between 2 (best) and 31 (worst)");
    }
    if (auto status = encoderAvailable(request.codec); !status) {
        return ResultType(status.error());
    }

    const auto source = layout_.resolve(request.evidence.storageRelPath);
    std::error_code ec;
    if (!std::filesystem::exists(source, ec)) {
        return ResultType::failure(ErrorCode::NotFound,
                                   "The managed original is missing: " + source.string());
    }

    const std::string assetId = generateUuid();
    // Matroska, because it carries every codec pairing this can produce and
    // stores timestamps at a resolution that does not force the frame timing to
    // be rounded into a grid.
    const std::string filename = StorageLayout::derivedFilename(
        request.evidence.evidenceNumber, "working", toString(request.codec), ".mkv", assetId);
    const auto destination = layout_.workingDirectory(request.caseId) / filename;
    std::filesystem::create_directories(destination.parent_path(), ec);

    // Nothing half-written survives this function.
    //
    // Every failure below returns early, and several of them happen after the
    // output file has been created — a rejected header, an allocation failure,
    // a pixel format that cannot be converted. Leaving those behind would put
    // partial files in working/ that look like working copies and are not,
    // which is the same property `CancellingKeepsNothing` asserts for a
    // cancelled run. One guard is harder to forget than a removal on each path.
    struct DiscardUnlessKept {
        std::filesystem::path file;
        bool keep = false;
        ~DiscardUnlessKept() {
            if (keep) return;
            std::error_code ignored;
            std::filesystem::remove(file, ignored);
        }
    } incomplete{destination, false};

    // Declared before `contexts`: the decrypting IO context must outlive the
    // format context pointing at it, and locals destroy in reverse order.
    EncryptedMediaIo io;
    TranscodeContexts contexts;

    WorkingCopyOutcome outcome;
    outcome.lossless = isLossless(request.codec);
    outcome.workingCopyCodec = toString(request.codec);

    // --------------------------------------------------------------- input
    std::string url;
    if (auto status = io.prepare(&contexts.input, source, request.key, &url); !status) {
        return ResultType(status.error());
    }
    int rc = avformat_open_input(&contexts.input, url.empty() ? nullptr : url.c_str(), nullptr,
                                 nullptr);
    if (rc < 0) {
        return ResultType::failure(ErrorCode::MediaError,
                                   "Could not open the managed original: " + ffmpegErrorString(rc));
    }
    rc = avformat_find_stream_info(contexts.input, nullptr);
    if (rc < 0) {
        return ResultType::failure(ErrorCode::MediaError,
                                   "Could not read stream information: " + ffmpegErrorString(rc));
    }

    int videoStream = -1;
    int audioStream = -1;
    for (unsigned int i = 0; i < contexts.input->nb_streams; ++i) {
        const AVMediaType type = contexts.input->streams[i]->codecpar->codec_type;
        if (type == AVMEDIA_TYPE_VIDEO && videoStream < 0) videoStream = static_cast<int>(i);
        if (type == AVMEDIA_TYPE_AUDIO && audioStream < 0) audioStream = static_cast<int>(i);
    }
    if (videoStream < 0) {
        return ResultType::failure(ErrorCode::MediaError,
                                   "This item has no video stream to make a working copy of");
    }

    AVStream* inVideo = contexts.input->streams[videoStream];
    const AVCodec* decoderCodec = avcodec_find_decoder(inVideo->codecpar->codec_id);
    if (decoderCodec == nullptr) {
        return ResultType::failure(
            ErrorCode::Unsupported,
            "No decoder for this item's video codec, so it cannot be converted. A working copy "
            "is produced by decoding and re-encoding, which needs a decoder that works.");
    }
    outcome.sourceCodec = decoderCodec->name;
    outcome.sourceDurationUs =
        contexts.input->duration == AV_NOPTS_VALUE
            ? 0
            : av_rescale_q(contexts.input->duration, AV_TIME_BASE_Q, kMicroseconds);
    outcome.sourceBytes = static_cast<std::int64_t>(std::filesystem::file_size(source, ec));
    if (ec) outcome.sourceBytes = 0;

    contexts.decoder = avcodec_alloc_context3(decoderCodec);
    if (contexts.decoder == nullptr) {
        return ResultType::failure(ErrorCode::Internal, "Out of memory allocating a decoder");
    }
    rc = avcodec_parameters_to_context(contexts.decoder, inVideo->codecpar);
    if (rc < 0) {
        return ResultType::failure(ErrorCode::MediaError,
                                   "Could not configure the decoder: " + ffmpegErrorString(rc));
    }
    contexts.decoder->pkt_timebase = inVideo->time_base;
    rc = avcodec_open2(contexts.decoder, decoderCodec, nullptr);
    if (rc < 0) {
        return ResultType::failure(ErrorCode::MediaError,
                                   "Could not open the decoder: " + ffmpegErrorString(rc));
    }

    // -------------------------------------------------------------- output
    rc = avformat_alloc_output_context2(&contexts.output, nullptr, "matroska",
                                        destination.string().c_str());
    if (rc < 0 || contexts.output == nullptr) {
        return ResultType::failure(ErrorCode::MediaError,
                                   "Could not create the working-copy container: " +
                                       ffmpegErrorString(rc));
    }

    const AVCodec* encoderCodec = avcodec_find_encoder_by_name(encoderNameFor(request.codec));
    contexts.encoder = avcodec_alloc_context3(encoderCodec);
    if (contexts.encoder == nullptr) {
        return ResultType::failure(ErrorCode::Internal, "Out of memory allocating an encoder");
    }

    const AVPixelFormat sourceFormat = contexts.decoder->pix_fmt;
    const AVPixelFormat targetFormat =
        pixelFormatFor(encoderCodec, sourceFormat, isLossless(request.codec));
    if (targetFormat == AV_PIX_FMT_NONE) {
        // Only reachable on the lossless path, and only for a source in a
        // format FFV1 cannot store. Reported rather than silently converted:
        // a "lossless" copy that had been through a pixel-format conversion
        // would be a false claim, and a quiet one.
        const char* name = av_get_pix_fmt_name(sourceFormat);
        return ResultType::failure(
            ErrorCode::Unsupported,
            std::string("A lossless working copy of ") + (name != nullptr ? name : "this format") +
                " is not possible: the encoder cannot store that pixel format, and converting it "
                "would make the copy lossy while still calling itself lossless. Use the Motion "
                "JPEG option instead, which is honestly labelled as lossy.");
    }

    contexts.encoder->width = contexts.decoder->width;
    contexts.encoder->height = contexts.decoder->height;
    contexts.encoder->pix_fmt = targetFormat;
    contexts.encoder->sample_aspect_ratio = contexts.decoder->sample_aspect_ratio;
    // Colour description carried across rather than left at "unspecified". A
    // working copy that decoded to different colours than its source would be
    // wrong in a way nobody would notice from a bounding box, and a player has
    // nothing but these fields to go on.
    contexts.encoder->colorspace = contexts.decoder->colorspace;
    contexts.encoder->color_primaries = contexts.decoder->color_primaries;
    contexts.encoder->color_trc = contexts.decoder->color_trc;
    contexts.encoder->color_range =
        isFullRange(targetFormat) ? AVCOL_RANGE_JPEG : contexts.decoder->color_range;
    // Microsecond time base throughout, so a source timestamp survives the
    // round trip without being quantised onto a frame grid. This is what makes
    // variable-frame-rate material come out the other side still variable
    // rather than silently regularised.
    contexts.encoder->time_base = kMicroseconds;
    // Deliberately left at its default (0/1, "unknown"): declaring a frame rate
    // invites muxers and players to assume constant timing, which for VFR
    // material is exactly the wrong assumption.
    contexts.encoder->framerate = AVRational{0, 1};
    // Every frame a keyframe. This is the property the whole feature exists for.
    contexts.encoder->gop_size = 1;
    contexts.encoder->max_b_frames = 0;

    if (!isLossless(request.codec)) {
        contexts.encoder->flags |= AV_CODEC_FLAG_QSCALE;
        contexts.encoder->global_quality = request.quality * FF_QP2LAMBDA;
    }
    if (contexts.output->oformat->flags & AVFMT_GLOBALHEADER) {
        contexts.encoder->flags |= AV_CODEC_FLAG_GLOBAL_HEADER;
    }

    rc = avcodec_open2(contexts.encoder, encoderCodec, nullptr);
    if (rc < 0) {
        return ResultType::failure(ErrorCode::MediaError,
                                   std::string("Could not open the ") + encoderCodec->name +
                                       " encoder: " + ffmpegErrorString(rc));
    }

    AVStream* outVideo = avformat_new_stream(contexts.output, nullptr);
    if (outVideo == nullptr) {
        return ResultType::failure(ErrorCode::MediaError, "Could not add the video stream");
    }
    rc = avcodec_parameters_from_context(outVideo->codecpar, contexts.encoder);
    if (rc < 0) {
        return ResultType::failure(ErrorCode::MediaError,
                                   "Could not describe the video stream: " + ffmpegErrorString(rc));
    }
    outVideo->time_base = contexts.encoder->time_base;

    // Audio is stream-copied rather than re-encoded: a working copy exists for
    // video analysis, and decoding and re-encoding the audio would add a
    // generation of loss to a track nothing here needs to touch.
    int audioOutIndex = -1;
    if (audioStream >= 0) {
        AVStream* outAudio = avformat_new_stream(contexts.output, nullptr);
        if (outAudio == nullptr) {
            outcome.audioDroppedReason = "could not add an audio stream to the container";
        } else {
            rc = avcodec_parameters_copy(outAudio->codecpar,
                                         contexts.input->streams[audioStream]->codecpar);
            if (rc < 0) {
                outcome.audioDroppedReason =
                    "the audio codec parameters could not be copied: " + ffmpegErrorString(rc);
            } else {
                outAudio->codecpar->codec_tag = 0;
                outAudio->time_base = contexts.input->streams[audioStream]->time_base;
                audioOutIndex = outAudio->index;
                outcome.audioCopied = true;
            }
        }
    }

    if ((contexts.output->oformat->flags & AVFMT_NOFILE) == 0) {
        rc = avio_open(&contexts.output->pb, destination.string().c_str(), AVIO_FLAG_WRITE);
        if (rc < 0) {
            return ResultType::failure(ErrorCode::IoError,
                                       "Could not write the working copy: " + ffmpegErrorString(rc));
        }
    }
    // Do not let the muxer move the timeline to keep timestamps non-negative.
    //
    // This is not a theoretical setting. A compressed audio track carries
    // priming samples, so its first packet sits *before* zero — in the test
    // fixture, AAC's 1024-sample delay puts it at -23.2ms. Matroska's default
    // response is to shift timestamps until nothing is negative, and what it
    // actually did was move the video forward by 23ms and leave the audio
    // where it was: a working copy whose video ran 23ms late against its own
    // audio, and 23ms late against the original it was made from. Nothing about
    // the picture would look wrong.
    //
    // With the shift disabled, the video keeps the timestamps written to it.
    // Audio that would land before zero is dropped below, because a priming
    // packet is encoder padding rather than recorded sound, and losing it must
    // not be paid for by moving the timeline detections are measured against.
    contexts.output->avoid_negative_ts = AVFMT_AVOID_NEG_TS_DISABLED;

    rc = avformat_write_header(contexts.output, nullptr);
    if (rc < 0) {
        return ResultType::failure(ErrorCode::MediaError,
                                   "Could not write the working-copy header: " +
                                       ffmpegErrorString(rc));
    }

    // ------------------------------------------------------------ convert
    contexts.packet = av_packet_alloc();
    contexts.encodedPacket = av_packet_alloc();
    contexts.decoded = av_frame_alloc();
    if (contexts.packet == nullptr || contexts.encodedPacket == nullptr ||
        contexts.decoded == nullptr) {
        return ResultType::failure(ErrorCode::Internal, "Out of memory allocating frame buffers");
    }

    if (targetFormat != sourceFormat) {
        contexts.scaler = sws_getContext(contexts.decoder->width, contexts.decoder->height,
                                         sourceFormat, contexts.decoder->width,
                                         contexts.decoder->height, targetFormat, SWS_BICUBIC,
                                         nullptr, nullptr, nullptr);
        if (contexts.scaler == nullptr) {
            return ResultType::failure(ErrorCode::MediaError,
                                       "Could not convert between pixel formats");
        }
        contexts.converted = av_frame_alloc();
        if (contexts.converted == nullptr) {
            return ResultType::failure(ErrorCode::Internal, "Out of memory allocating a frame");
        }
        contexts.converted->format = targetFormat;
        contexts.converted->width = contexts.decoder->width;
        contexts.converted->height = contexts.decoder->height;
        rc = av_frame_get_buffer(contexts.converted, 0);
        if (rc < 0) {
            return ResultType::failure(ErrorCode::Internal,
                                       "Could not allocate a conversion buffer: " +
                                           ffmpegErrorString(rc));
        }
    }

    const Microseconds streamStartUs =
        inVideo->start_time == AV_NOPTS_VALUE ? 0
                                              : toMicroseconds(inVideo->start_time,
                                                               inVideo->time_base);
    // Named for what it holds. Status is true when the operation succeeded, so
    // `!conversionStatus` reads as "it failed" throughout, as it does elsewhere
    // in this codebase.
    Status conversionStatus = Status::success();
    bool cancelled = false;
    bool reachedLimit = false;
    std::int64_t audioPacketsDropped = 0;

    // Sends one frame to the encoder and muxes whatever comes back. A null
    // frame flushes.
    const auto drainEncoder = [&](AVFrame* frame) -> Status {
        int sendRc = avcodec_send_frame(contexts.encoder, frame);
        if (sendRc < 0) {
            return Status::failure(ErrorCode::MediaError,
                                   "The encoder rejected a frame: " + ffmpegErrorString(sendRc));
        }
        while (true) {
            int recvRc = avcodec_receive_packet(contexts.encoder, contexts.encodedPacket);
            if (recvRc == AVERROR(EAGAIN) || recvRc == AVERROR_EOF) return Status::success();
            if (recvRc < 0) {
                return Status::failure(ErrorCode::MediaError,
                                       "The encoder failed: " + ffmpegErrorString(recvRc));
            }
            contexts.encodedPacket->stream_index = outVideo->index;
            av_packet_rescale_ts(contexts.encodedPacket, contexts.encoder->time_base,
                                 outVideo->time_base);
            // All-intra: saying so lets a demuxer seek to any frame rather than
            // scanning for the keyframes it was told to expect.
            contexts.encodedPacket->flags |= AV_PKT_FLAG_KEY;
            int writeRc = av_interleaved_write_frame(contexts.output, contexts.encodedPacket);
            av_packet_unref(contexts.encodedPacket);
            if (writeRc < 0) {
                return Status::failure(ErrorCode::IoError,
                                       "Failed while writing the working copy: " +
                                           ffmpegErrorString(writeRc));
            }
            ++outcome.framesWritten;
        }
    };

    // Where a decoded frame sits on the recording's timeline. Taken from the
    // frame's own timestamp, never from a frame counter and a frame rate.
    const auto frameTimestamp = [&](const AVFrame* frame) -> Microseconds {
        const std::int64_t best = frame->best_effort_timestamp != AV_NOPTS_VALUE
                                      ? frame->best_effort_timestamp
                                      : frame->pts;
        if (best == AV_NOPTS_VALUE) return outcome.coveredDurationUs;
        return toMicroseconds(best, inVideo->time_base) - streamStartUs;
    };

    // Converts one decoded frame and hands it to the encoder. Returns false
    // when the caller should stop pulling frames — either the requested limit
    // was passed, the operator cancelled, or something failed.
    const auto convertDecodedFrame = [&]() -> bool {
        const Microseconds ptsUs = frameTimestamp(contexts.decoded);
        if (request.convertUpToUs > 0 && ptsUs > request.convertUpToUs) {
            reachedLimit = true;
            return false;
        }

        AVFrame* toEncode = contexts.decoded;
        if (contexts.scaler != nullptr) {
            int scaled = sws_scale(contexts.scaler, contexts.decoded->data,
                                   contexts.decoded->linesize, 0, contexts.decoder->height,
                                   contexts.converted->data, contexts.converted->linesize);
            if (scaled < 0) {
                conversionStatus =
                    Status::failure(ErrorCode::MediaError, "Pixel format conversion failed");
                return false;
            }
            toEncode = contexts.converted;
        }
        // The source's own timestamp, carried across unchanged.
        toEncode->pts = ptsUs;
        toEncode->pkt_dts = AV_NOPTS_VALUE;

        if (Status encoded = drainEncoder(toEncode); !encoded) {
            conversionStatus = encoded;
            return false;
        }
        outcome.coveredDurationUs = std::max(outcome.coveredDurationUs, ptsUs);

        if (progress) {
            WorkingCopyProgress update;
            update.framesWritten = outcome.framesWritten;
            update.positionUs = ptsUs;
            update.durationUs = outcome.sourceDurationUs;
            update.fractionComplete =
                outcome.sourceDurationUs > 0
                    ? std::min(1.0, static_cast<double>(ptsUs) /
                                        static_cast<double>(outcome.sourceDurationUs))
                    : 0.0;
            if (!progress(update)) {
                cancelled = true;
                return false;
            }
        }
        return true;
    };

    // Pulls every frame the decoder is holding. Shared by the read loop and by
    // the flush that follows it, so a frame arriving during the flush goes
    // through exactly the same path — including the timestamp handling, which
    // is the part that must not have a second implementation.
    const auto drainDecoder = [&]() -> bool {
        while (true) {
            int receiveRc = avcodec_receive_frame(contexts.decoder, contexts.decoded);
            if (receiveRc == AVERROR(EAGAIN) || receiveRc == AVERROR_EOF) return true;
            if (receiveRc < 0) {
                conversionStatus = Status::failure(ErrorCode::MediaError,
                                                   "Decoding failed: " +
                                                       ffmpegErrorString(receiveRc));
                return false;
            }
            const bool keepGoing = convertDecodedFrame();
            av_frame_unref(contexts.decoded);
            if (!keepGoing) return false;
        }
    };

    while (conversionStatus && !cancelled && !reachedLimit &&
           av_read_frame(contexts.input, contexts.packet) >= 0) {
        const int stream = contexts.packet->stream_index;

        if (stream == audioStream && audioOutIndex >= 0) {
            AVStream* in = contexts.input->streams[audioStream];
            AVStream* out = contexts.output->streams[audioOutIndex];
            // Onto the same origin the video uses, so the two stay in the
            // relationship they had in the original.
            const std::int64_t originInAudio =
                av_rescale_q(streamStartUs, kMicroseconds, in->time_base);
            if (contexts.packet->pts != AV_NOPTS_VALUE) contexts.packet->pts -= originInAudio;
            if (contexts.packet->dts != AV_NOPTS_VALUE) contexts.packet->dts -= originInAudio;

            if (contexts.packet->pts != AV_NOPTS_VALUE && contexts.packet->pts < 0) {
                // Encoder priming, not recorded sound. Dropped rather than
                // allowed to drag the whole file forward.
                ++audioPacketsDropped;
                av_packet_unref(contexts.packet);
                continue;
            }
            av_packet_rescale_ts(contexts.packet, in->time_base, out->time_base);
            contexts.packet->stream_index = audioOutIndex;
            contexts.packet->pos = -1;
            rc = av_interleaved_write_frame(contexts.output, contexts.packet);
            av_packet_unref(contexts.packet);
            if (rc < 0) {
                conversionStatus = Status::failure(
                    ErrorCode::IoError, "Failed while writing audio: " + ffmpegErrorString(rc));
            }
            continue;
        }
        if (stream != videoStream) {
            av_packet_unref(contexts.packet);
            continue;
        }

        rc = avcodec_send_packet(contexts.decoder, contexts.packet);
        av_packet_unref(contexts.packet);
        if (rc < 0 && rc != AVERROR(EAGAIN)) {
            conversionStatus = Status::failure(
                ErrorCode::MediaError, "The source could not be decoded: " + ffmpegErrorString(rc));
            break;
        }
        drainDecoder();
    }

    // Frames still held by the decoder are part of the recording. Dropping them
    // would leave the working copy shorter than its source, which the timeline
    // check would then reject — correctly, but pointing at the wrong problem.
    if (conversionStatus && !cancelled && !reachedLimit) {
        if (avcodec_send_packet(contexts.decoder, nullptr) >= 0) drainDecoder();
    }
    if (conversionStatus && !cancelled) {
        if (Status flushed = drainEncoder(nullptr); !flushed) conversionStatus = flushed;
    }

    // Closes the file before returning so the guard above can remove it;
    // Windows will not delete a file that still has an open handle.
    const auto abandon = [&](const Status& status) {
        contexts.closeOutput();
        return ResultType(status.error());
    };

    if (!conversionStatus) return abandon(conversionStatus);
    if (cancelled) {
        return abandon(Status::failure(ErrorCode::Cancelled,
                                       "The conversion was cancelled. A partly converted file is "
                                       "not a working copy of anything, so nothing was kept."));
    }

    rc = av_write_trailer(contexts.output);
    if (rc < 0) {
        return abandon(Status::failure(ErrorCode::MediaError,
                                       "Could not finalise the working copy: " +
                                           ffmpegErrorString(rc)));
    }
    if (outcome.framesWritten == 0) {
        return abandon(Status::failure(ErrorCode::MediaError,
                                       "The source produced no decodable frames"));
    }

    // Release the handle before anything else touches the file: registering it
    // rewrites it in place in an encrypted workspace, and Windows refuses to
    // replace a file that is still open.
    contexts.closeOutput();

    outcome.workingCopyBytes = static_cast<std::int64_t>(std::filesystem::file_size(destination, ec));
    if (ec) outcome.workingCopyBytes = 0;

    // ---------------------------------------------------- verify the timeline
    //
    // Everything this feature claims rests on the working copy sharing its
    // source's timeline. That claim is checked here against the file that was
    // actually written, before the asset exists, so a working copy that would
    // misplace detections never becomes one.
    auto verified = verifyTimelineMatches(source, destination, request.key, nullptr, 1000,
                                          request.convertUpToUs);
    if (!verified) {
        return abandon(Status::failure(
            verified.error().code(),
            "The working copy does not share the original's timeline, so it was discarded. " +
                verified.error().message()));
    }
    outcome.timelineVerified = true;
    outcome.timestampsCompared = verified.value();

    // ------------------------------------------------------ register the asset
    DerivedAssetRegistration registration;
    registration.caseId = request.caseId;
    registration.caseNumber = request.caseNumber;
    registration.evidenceId = request.evidence.id;
    registration.evidenceNumber = request.evidence.evidenceNumber;
    registration.type = DerivedAssetType::WorkingCopy;
    registration.file = destination;
    registration.operationType = "working_copy";
    registration.mediaType = std::string("video/x-matroska");
    registration.sourceStartUs = 0;
    registration.sourceEndUs = outcome.coveredDurationUs;
    registration.notes = request.notes;
    registration.auditAction = AuditAction::WorkingCopyCreated;
    registration.auditDescription =
        std::string("Working copy of ") + request.evidence.evidenceNumber + " in " +
        toDisplayString(request.codec) + ", " + std::to_string(outcome.framesWritten) +
        " frames, timeline verified against the original";
    registration.libraryVersions = ffmpegLibraryVersions();
    registration.parameters =
        JsonValue::object()
            .set("method",
                 "decoded and re-encoded frame by frame; source presentation timestamps are "
                 "carried across unchanged and verified against the original afterwards")
            .set("codec", toString(request.codec))
            .set("codec_description", toDisplayString(request.codec))
            .set("lossless", outcome.lossless)
            .set("all_intra", true)
            .set("source_codec", outcome.sourceCodec)
            .set("width", contexts.decoder->width)
            .set("height", contexts.decoder->height)
            .set("scaled", false)
            .set("pixel_format", av_get_pix_fmt_name(targetFormat) != nullptr
                                     ? av_get_pix_fmt_name(targetFormat)
                                     : "unknown")
            .set("source_pixel_format", av_get_pix_fmt_name(sourceFormat) != nullptr
                                            ? av_get_pix_fmt_name(sourceFormat)
                                            : "unknown")
            .set("frame_rate_changed", false)
            .set("frames_written", outcome.framesWritten)
            .set("timeline_verified", true)
            .set("timestamps_compared", outcome.timestampsCompared)
            .set("timeline_tolerance_us", 1000)
            .set("audio_copied", outcome.audioCopied)
            .set("audio_priming_packets_dropped", audioPacketsDropped)
            .set("source_bytes", outcome.sourceBytes)
            .set("working_copy_bytes", outcome.workingCopyBytes)
            .set("source_sha256", request.evidence.sha256);
    if (!outcome.lossless) {
        registration.parameters.set("quality_scale", request.quality)
            .set("quality_scale_meaning", "FFmpeg quantiser scale, 2 is best and 31 is worst")
            .set("lossy_warning",
                 "This working copy is a lossy re-encode. Detections found on it were found on "
                 "re-compressed pixels, not on the original's.");
        if (isFullRange(targetFormat) && !isFullRange(sourceFormat)) {
            registration.parameters.set(
                "sample_range_converted",
                "The source is limited-range and JPEG is defined over full-range samples, so the "
                "sample range was expanded. Values outside the limited range - superblack and "
                "superwhite - are clipped by that conversion and are not recoverable from this "
                "copy.");
        }
    }
    if (!outcome.audioDroppedReason.empty()) {
        registration.parameters.set("audio_dropped_because", outcome.audioDroppedReason);
    }
    if (request.convertUpToUs > 0) {
        registration.parameters.set("converted_up_to_us", request.convertUpToUs)
            .set("partial",
                 "Only part of the source was converted; this working copy does not cover the "
                 "whole recording.");
    }

    auto registered = derivedAssets_->registerAsset(registration);
    if (!registered) return ResultType(registered.error());
    outcome.asset = registered.take();
    incomplete.keep = true;

    logInfo(kComponent, "Working copy created",
            JsonValue::object()
                .set("evidence", request.evidence.evidenceNumber)
                .set("file", filename)
                .set("codec", toString(request.codec))
                .set("lossless", outcome.lossless)
                .set("frames", outcome.framesWritten)
                .set("timestamps_compared", outcome.timestampsCompared)
                .set("size_ratio", outcome.sizeRatio()));

    return ResultType::success(std::move(outcome));
}

}  // namespace trace
