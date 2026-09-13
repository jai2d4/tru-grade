# Building TRACE

Everything needed to build, in one place. This existed scattered across the
README, `BUILD_WINDOWS.md` and the CI workflow, which meant assembling it took
three files and a guess.

Every version below is either the minimum the build enforces or one that has
actually been built and tested — nothing here is aspirational.

---

## 1. Toolchain

| | Minimum | Known good |
|---|---|---|
| CMake | **3.21** | 3.28.3 |
| Ninja | any | 1.11.1 |
| C++ compiler | **C++20** | GCC 13.3, MSVC 14.44 |
| pkg-config | — | required on Linux; see §3 for why Windows does not need it |

C++20 is not negotiable: `Result<T>`, the designated initialisers in the model
structs and several `constexpr` paths depend on it.

---

## 2. Required libraries

Nothing builds without these.

**Qt 6** — Core, Gui, Widgets, Concurrent, Multimedia. Built against 6.4.2 and
6.6.3. Multimedia is needed even headless: `QAudioSink` is referenced by
`trace_ui` whether or not a sound device exists.

**FFmpeg** — libavformat, libavcodec, libavutil, libswscale, libswresample.
Built against 6.1.1 (Linux) and n9.0 (Windows).

> **LGPL, not GPL.** TRACE links FFmpeg, so a GPL build carries GPL obligations
> into TRACE the moment it is distributed. The Windows CI job resolves the asset
> from the releases API and **fails rather than substituting a GPL build** if no
> LGPL one exists. This is a licensing boundary, not a preference.

**SQLite or SQLCipher** — exactly one. SQLCipher is a fork of SQLite that
exports the same symbol names, so linking both is an ODR violation that may or
may not show up as a crash. `FindEncryptionBackend.cmake` picks one and
`trace::sqlite` is whichever it picked.

**GoogleTest** — only when `TRACE_BUILD_TESTS=ON`, which is the default.

---

## 3. Optional libraries, and what each one costs

Every option here **degrades rather than failing**. A missing dependency
produces a TRACE that works and says what it cannot do, never one that silently
believes it can.

| Option | Default | Needs | Without it |
|---|---|---|---|
| `TRACE_WITH_ENCRYPTION` | `ON` | SQLCipher + OpenSSL (libcrypto only) | Unencrypted workspaces work; encrypted ones are refused with a stated reason |
| `TRACE_WITH_AVDEVICE` | `ON` | libavdevice | No USB cameras or capture cards. **Network cameras are unaffected** — they need only libavformat |
| `TRACE_WITH_ONNXRUNTIME` | `ON` | ONNX Runtime (§4) | Only the deterministic mock detection provider is registered |
| `TRACE_BUILD_DESKTOP` | `ON` | Qt 6 | Headless libraries only; Qt is not required at all |
| `TRACE_BUILD_TESTS` | `ON` | GoogleTest | No test suites |
| `TRACE_WITH_OPENCV` | `OFF` | OpenCV core, imgproc, imgcodecs | Optional helpers only |

TRACE speaks no TLS, so OpenSSL's `libssl` is never needed — only `libcrypto`.

The configure summary reports what was actually found:

```
--   SQLite ............. SQLCipher 4.5
--   Encryption ......... TRUE
--   Attached cameras ... libavdevice 60.3.100
--   FFmpeg (libav) ..... avformat 60.16.100, avcodec 60.31.102 (via pkg-config)
--   ONNX Runtime ....... ON
```

Read it. A build that degraded is not obvious from a successful compile, which
is exactly why the Windows CI job asserts on this text rather than trusting the
exit code.

---

## 4. Runtime assets — fetched, never committed

Two things the repository deliberately does not contain:

```bash
./scripts/fetch_onnxruntime.sh          # ONNX Runtime 1.17.3, ~16 MB
./scripts/fetch_onnxruntime.sh --gpu    # the CUDA build instead
./scripts/fetch_models.sh               # YOLOX-Tiny, ~20 MB, digest-verified
```

Neither is committed, for two different reasons. The runtime is a large binary
artefact that does not belong in version control. The model is not committed
because **TRACE does not download models behind an operator's back** — the fetch
is a deliberate act, the digest is checked against the catalogue before the
model is ever loaded, and a mismatch blocks the run rather than warning.

`ONNXRUNTIME_VERSION=1.18.0 ./scripts/fetch_onnxruntime.sh` pins a different
version.

---

## 5. Linux

```bash
sudo apt-get install -y --no-install-recommends \
    cmake ninja-build g++ pkg-config \
    qt6-base-dev qt6-multimedia-dev \
    libavformat-dev libavcodec-dev libavutil-dev \
    libswscale-dev libswresample-dev libavdevice-dev \
    libsqlcipher-dev libssl-dev libgtest-dev
```

That is the set the Linux CI job installs, which is the configuration TRACE is
known to build in. Note `libsqlcipher-dev` **instead of** `libsqlite3-dev` — see
§2 on why both is wrong.

```bash
./scripts/fetch_onnxruntime.sh
./scripts/fetch_models.sh
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build
QT_QPA_PLATFORM=offscreen ctest --test-dir build --output-on-failure --timeout 400
```

`QT_QPA_PLATFORM=offscreen` is what lets the widget and acceptance suites run
without a display.

---

## 6. Windows

vcpkg, and `docs/BUILD_WINDOWS.md` has the detail. In short:

```powershell
vcpkg install sqlcipher:x64-windows openssl:x64-windows gtest:x64-windows
```

`sqlite3:x64-windows` is deliberately **not** installed alongside SQLCipher: with
both present the header search can land on the wrong `sqlite3.h`, and the find
module would then correctly refuse it and degrade — a safe outcome, and a
useless one.

Qt comes from the Qt installer or `install-qt-action`. FFmpeg must be an
**LGPL shared** build (§2).

No pkg-config is needed: `FindFFmpegPortable.cmake` and
`FindEncryptionBackend.cmake` both fall back to locating headers and import
libraries directly, which is the path Windows takes.

This is proven, not assumed — CI builds Windows with `TRACE_WITH_ENCRYPTION=ON`
and requires both that the configure summary reports encryption on and that the
encryption tests ran rather than skipped.

---

## 7. Building for a GPU

Beyond §5, exactly two things:

1. `./scripts/fetch_onnxruntime.sh --gpu` — the default package is CPU-only, and
   with it `cudaAvailable()` returns false and the CUDA path is never entered.
2. An NVIDIA driver new enough for the card.

**No CUDA toolkit is required.** The ONNX Runtime package ships what it needs,
and FFmpeg's NVDEC path goes through the driver.

`scripts/setup_gpu_server.sh` does all of §5 and §7 in one command, and refuses
to continue on a machine with no GPU rather than building anyway.

Two caveats worth knowing before you spend money on hardware:

- **Compute capability decides ONNX Runtime support.** 8.9 (Ada — L4, RTX
  40-series) is covered by prebuilt CUDA wheels. 12.x (Blackwell, RTX 50-series)
  is not at the time of writing; those wheels ship kernels only to sm_90 and the
  documented failure is a silent fall back to CPU. TRACE records the provider
  that actually ran rather than the one requested, so it will report the CPU
  honestly — but the GPU will not be doing the work.
- **Hardware decode is off by default**, and exported exhibits always decode in
  software regardless. See `docs/HARDWARE_DECODE.md` §2 for why that is a
  deliberate evidentiary choice rather than caution about speed.

---

## 8. What a successful build produces

```
build/bin/trace                      the desktop application
build/bin/trace_unit_tests           140 cases
build/bin/trace_integration_tests    175 cases
build/bin/trace_ui_unit_tests          6 cases
build/bin/trace_acceptance_*_test      4 workflows
```

319 registered tests. CI enforces a floor so the suite cannot silently shrink.

Some tests skip themselves and say why: no GPU, no sound device, no detection
model, no real footage. A skip is a stated absence, never a quiet pass — see
`docs/PHASE1_TESTING.md` and `docs/HARDWARE_DECODE.md` §0 for the full list of
what has and has not been executed.
