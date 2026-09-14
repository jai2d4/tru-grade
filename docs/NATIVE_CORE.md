# The native C/C++ core

TruGrade's tracking hot path is implemented twice: once in C++ behind a C ABI
(`native/`), and once in Python (`backend/vision/tracker.py`). The native one
runs when it has been built; otherwise the Python one does. They produce
identical output, and `backend/tests/test_native_parity.py` is what holds them
to that.

Nothing in the backend requires the library. A checkout that never compiles it
serves the same results, more slowly, and says so on `/api/health/status`.

## Why it exists

Association is the one genuinely hot loop in the video pipeline. Every frame,
every detection is compared against every live track — O(detections x tracks),
once per frame, for the length of the film. At 22 players over a half-hour of
footage that is tens of millions of IoU evaluations, and in Python each one
carries interpreter overhead that dwarfs the four comparisons and two
multiplications it actually performs.

Measured on this container (g++ 13.3, `-O3`, synthetic detections):

| workload | Python | native | speedup |
| --- | --- | --- | --- |
| 900 frames x 6 players | 70ms | 42ms | 1.7x |
| 900 frames x 12 players | 199ms | 80ms | 2.5x |
| 1800 frames x 22 players | 1124ms | 295ms | 3.8x |
| 3600 frames x 22 players | 2431ms | 623ms | 3.9x |

The gain grows with the workload, which is what you want from this: the short
clips were never the problem.

### Why movement metrics are *not* accelerated

`backend/football/movement.py` stays pure Python on purpose, and the comment at
the top of that file says so. The native core implements the same summary and is
tested against the Python one, but the Python path is the one that runs.

The reason is that the work is O(n) either way, so the only thing C++ can save
is interpreter overhead on a single pass — while the FFI crossing has to
marshal every position dict into a C struct first, which is itself a Python loop
over the same data. Measured on a 2000-point track: **2.26ms native against
1.08ms in Python**. Shipping it would have made the app slower.

This would change if the frame loop itself moved into C++ and positions never
had to be rebuilt per call. The C++ implementation is kept, and kept tested, for
that. The same logic explains why `tg_torso_orientation_deg` exists in the ABI
but nothing in `backend/vision/biomechanics.py` calls it: one `atan2` per pose
does not pay for a crossing. A batched call over a whole frame's poses would.

## How it is put together

```
native/include/trugrade_core.h     public C ABI - the only surface Python binds
native/include/trugrade_impl.h     internal C -> C++ bridge declarations
native/src/tg_abi.c                C11: argument validation, version reporting
native/src/capi.cpp                C++: exception firewall, POD marshalling
native/src/tracking.cpp            C++: the two-stage associator
native/src/kinematics.cpp          C++: movement summary (built, not wired in)
native/include/trugrade/*.hpp      C++ headers, std::span / constexpr / optional
native/tests/test_core.cpp         self-tests, driven through the C ABI
backend/native/_loader.py          ctypes discovery, ABI check, graceful failure
backend/native/core.py             typed wrappers
```

Three properties are deliberate:

**The boundary is C, not C++.** No C++ type appears in a signature, so the
shared library keeps a stable ABI across compilers and standard-library
versions, and `ctypes` has a flat surface to bind to.

**Validation happens in C, before any C++ runs.** `tg_abi.c` checks every
pointer and count. A null from a buggy caller becomes a `tg_status` rather than
a segfault that would take down the whole uvicorn worker — a Python-level
exception instead of a dead process.

**No exception crosses the boundary.** `capi.cpp` catches everything and
returns `TG_ERR_INTERNAL`. Unwinding into C is undefined behaviour.

### Rounding lives in Python

The native core returns **unrounded** values. `ByteTrackTracker._point` is the
single place either path rounds, so the C++ can never disagree with Python in
the last decimal place through a rounding rule (C's `round` is half-away-from-
zero; Python's is half-to-even). That is what lets the parity tests assert exact
equality rather than a tolerance.

For the same reason `-ffast-math` is **not** enabled: reassociating this
arithmetic would break bit-for-bit agreement for no measurable gain at these
loop sizes.

### Behaviour that had to be reproduced, not improved

The Python associator has quirks that are load-bearing because output is
compared exactly:

- `_iou` guards only an exactly-zero union, letting a negative one through as a
  negative score. Reproduced.
- `max()` over an insertion-ordered dict keeps the **first** of a tied pair, so
  the C++ uses a strictly-greater comparison over an insertion-ordered vector.
  `test_tracker_matches_python_when_boxes_tie` fails if this is changed to `>=`.
- Elapsed time is floored at `1e-6`, and a track's first sighting reports zero
  velocity rather than an extrapolated one.

## Building it

```sh
sh scripts/build_native.sh              # release, runs the self-tests
sh scripts/build_native.sh --debug      # assertions on
sh scripts/build_native.sh --no-tests
```

Requires CMake 3.16+ and a C11 / C++20 compiler. With no CMake the script exits
0 and says the backend will use its fallback — a missing toolchain is a slower
deploy, not a failed one. Output lands in `native/build/` (git-ignored).

In Docker this happens in its own `native-build` stage, so the ~400MB of
toolchain never reaches the runtime image; only the `.so` is copied across.

## Environment variables

| variable | effect |
| --- | --- |
| `TRUGRADE_DISABLE_NATIVE=1` | Force the Python fallback. Useful for confirming a bug is not the native path. |
| `TRUGRADE_NATIVE_LIB` | Absolute path to the library. Authoritative: when set, no other location is tried, so naming a build that cannot be loaded reports unavailable rather than quietly running a different one. |

## Checking which path is live

```sh
curl -s localhost:8000/api/health/status | jq .native_core
```

```json
{ "available": true, "version": "0.1.0", "reason": null }
```

When `available` is false, `reason` gives the loader's account of every path it
tried. It names filesystem paths only, never a secret — that endpoint is
public and unauthenticated.

In Python:

```python
from backend import native
native.is_available()   # bool
native.status()         # the dict the health endpoint reports
```

`ByteTrackTracker.uses_native_core` reports the same for one tracker instance.

## Changing it

The two implementations are a standing invitation to drift, so:

1. Change both paths.
2. Run `sh scripts/build_native.sh` — the C++ self-tests run through the C ABI.
3. Run `pytest backend/tests/test_native_parity.py`, which compares the two on
   fixed cases and on seeded random streams, demanding exact equality.
4. Run the suite both ways: once normally, once with
   `TRUGRADE_DISABLE_NATIVE=1`.

If you change a struct layout or a signature in `trugrade_core.h`, bump
`TG_ABI_VERSION` and `REQUIRED_ABI_VERSION` in `backend/native/_loader.py`
together. The loader refuses a library whose version does not match, because
reading an old layout through today's `ctypes` definitions would return silent
garbage rather than fail.
