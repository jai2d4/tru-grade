#!/usr/bin/env sh
# Build the optional C/C++ core into native/build/.
#
# Nothing in the backend requires this: backend/native falls back to the pure
# Python implementations when the library is missing, and the test suite skips
# its parity checks rather than failing. So this script exits 0 on a machine
# with no compiler — a missing toolchain is a slower deploy, not a broken one.
#
#   sh scripts/build_native.sh              release build, runs the self-tests
#   sh scripts/build_native.sh --debug      debug build with assertions
#   sh scripts/build_native.sh --no-tests   skip the self-tests
set -eu

BUILD_TYPE=Release
RUN_TESTS=1

for argument in "$@"; do
    case "$argument" in
        --debug) BUILD_TYPE=Debug ;;
        --no-tests) RUN_TESTS=0 ;;
        -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
        *) echo "unknown option: $argument" >&2; exit 2 ;;
    esac
done

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE_DIR="$ROOT/native"
BUILD_DIR="$SOURCE_DIR/build"

if ! command -v cmake >/dev/null 2>&1; then
    echo "cmake not found — skipping the native core; the backend will use its Python fallback." >&2
    exit 0
fi

echo "Configuring the native core ($BUILD_TYPE)..."
cmake -S "$SOURCE_DIR" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE="$BUILD_TYPE"

echo "Building..."
cmake --build "$BUILD_DIR" --parallel

if [ "$RUN_TESTS" -eq 1 ]; then
    echo "Running the native self-tests..."
    ctest --test-dir "$BUILD_DIR" --output-on-failure
fi

echo "Done. backend/native will pick the library up from $BUILD_DIR."
