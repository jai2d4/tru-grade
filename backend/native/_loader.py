"""Locate and load libtrugrade_core, or report honestly that it is absent.

Loading is attempted exactly once per process and the outcome is cached, failure
included. Nothing here raises on a missing library: the native core is an
accelerator, and every caller has a pure-Python path to fall back to. A
deployment that never ran the build still serves traffic — it just serves it
more slowly, and ``load_error()`` says why.
"""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path
from typing import Any

# Must match TG_ABI_VERSION in native/include/trugrade_core.h. A library built
# from an older checkout has different struct layouts, and reading those through
# today's ctypes definitions would return silent garbage rather than fail, so a
# mismatch is treated as "unavailable".
REQUIRED_ABI_VERSION = 1


class BBox(ctypes.Structure):
    _fields_ = [("x1", ctypes.c_double), ("y1", ctypes.c_double),
                ("x2", ctypes.c_double), ("y2", ctypes.c_double)]


class Detection(ctypes.Structure):
    _fields_ = [("bbox", BBox), ("confidence", ctypes.c_double)]


class TrackPoint(ctypes.Structure):
    _fields_ = [("track_id", ctypes.c_int32),
                ("center_x", ctypes.c_double), ("center_y", ctypes.c_double),
                ("velocity_x", ctypes.c_double), ("velocity_y", ctypes.c_double),
                ("speed_px", ctypes.c_double), ("direction", ctypes.c_double)]


class Position(ctypes.Structure):
    _fields_ = [("center_x", ctypes.c_double), ("center_y", ctypes.c_double),
                ("timestamp_ms", ctypes.c_int64),
                ("speed_px", ctypes.c_double), ("direction", ctypes.c_double),
                ("confidence", ctypes.c_double)]


class MovementMetrics(ctypes.Structure):
    _fields_ = [("max_speed_px", ctypes.c_double),
                ("max_acceleration_px_s2", ctypes.c_double),
                ("max_deceleration_px_s2", ctypes.c_double),
                ("direction_change_deg", ctypes.c_double),
                ("displacement_px", ctypes.c_double),
                ("confidence", ctypes.c_double)]


# tg_status values from the C header.
TG_OK = 0
TG_ERR_NULL_ARGUMENT = -1
TG_ERR_INVALID_COUNT = -2
TG_ERR_INSUFFICIENT_POINTS = -3
TG_ERR_BUFFER_TOO_SMALL = -4
TG_ERR_INTERNAL = -5

_STATUS_NAMES = {
    TG_ERR_NULL_ARGUMENT: "null argument",
    TG_ERR_INVALID_COUNT: "invalid count",
    TG_ERR_INSUFFICIENT_POINTS: "insufficient points",
    TG_ERR_BUFFER_TOO_SMALL: "output buffer too small",
    TG_ERR_INTERNAL: "internal error in the native core",
}


def status_message(status: int) -> str:
    return _STATUS_NAMES.get(status, f"unknown status {status}")


def _library_name() -> str:
    if sys.platform == "darwin":
        return "libtrugrade_core.dylib"
    if sys.platform == "win32":
        return "trugrade_core.dll"
    return "libtrugrade_core.so"


def _candidate_paths() -> list[Path]:
    """Where to look.

    TRUGRADE_NATIVE_LIB is authoritative rather than merely first: if it is set
    and that library cannot be loaded, the answer is "unavailable", not "here is
    a different one". Someone who names a specific build is usually trying to
    find out which library they are running, and silently substituting another
    is precisely the answer that misleads them.
    """
    override = os.getenv("TRUGRADE_NATIVE_LIB", "").strip()
    if override:
        return [Path(override)]

    name = _library_name()
    # backend/native/_loader.py -> repo root is two parents up.
    repo_root = Path(__file__).resolve().parent.parent.parent
    return [
        repo_root / "native" / "build" / name,
        repo_root / "native" / "build" / "Release" / name,  # multi-config generators
        repo_root / "lib" / name,
    ]


def _bind(library: ctypes.CDLL) -> None:
    """Declare every signature.

    ctypes defaults an unbound return type to int, which truncates a 64-bit
    pointer. Declaring restype on the tracker factory is what keeps the handle
    valid, so this is correctness rather than documentation.
    """
    library.tg_abi_version.argtypes = []
    library.tg_abi_version.restype = ctypes.c_uint32

    library.tg_version_string.argtypes = []
    library.tg_version_string.restype = ctypes.c_char_p

    library.tg_iou.argtypes = [ctypes.POINTER(BBox), ctypes.POINTER(BBox),
                               ctypes.POINTER(ctypes.c_double)]
    library.tg_iou.restype = ctypes.c_int

    library.tg_torso_orientation_deg.argtypes = [ctypes.c_double, ctypes.c_double,
                                                 ctypes.c_double, ctypes.c_double,
                                                 ctypes.POINTER(ctypes.c_double)]
    library.tg_torso_orientation_deg.restype = ctypes.c_int

    library.tg_movement_metrics_compute.argtypes = [ctypes.POINTER(Position), ctypes.c_int32,
                                                    ctypes.POINTER(MovementMetrics)]
    library.tg_movement_metrics_compute.restype = ctypes.c_int

    library.tg_tracker_create.argtypes = [ctypes.c_double, ctypes.c_double,
                                          ctypes.c_double, ctypes.c_int32]
    library.tg_tracker_create.restype = ctypes.c_void_p

    library.tg_tracker_destroy.argtypes = [ctypes.c_void_p]
    library.tg_tracker_destroy.restype = None

    library.tg_tracker_update.argtypes = [ctypes.c_void_p, ctypes.POINTER(Detection), ctypes.c_int32,
                                          ctypes.c_int32, ctypes.c_int64,
                                          ctypes.POINTER(TrackPoint), ctypes.c_int32,
                                          ctypes.POINTER(ctypes.c_int32)]
    library.tg_tracker_update.restype = ctypes.c_int


_library: Any = None
_load_error: str | None = None
_loaded = False


def _load() -> None:
    global _library, _load_error, _loaded
    if _loaded:
        return
    _loaded = True

    if os.getenv("TRUGRADE_DISABLE_NATIVE", "").strip().lower() in {"1", "true", "yes"}:
        _load_error = "disabled by TRUGRADE_DISABLE_NATIVE"
        return

    attempts: list[str] = []
    for path in _candidate_paths():
        if not path.exists():
            attempts.append(f"{path}: not found")
            continue
        try:
            library = ctypes.CDLL(str(path))
            _bind(library)
        except OSError as exc:
            attempts.append(f"{path}: {exc}")
            continue

        reported = library.tg_abi_version()
        if reported != REQUIRED_ABI_VERSION:
            attempts.append(f"{path}: ABI version {reported}, expected {REQUIRED_ABI_VERSION}")
            continue

        _library = library
        return

    _load_error = "; ".join(attempts) if attempts else "no candidate paths"


def library() -> Any:
    """The loaded CDLL, or None. Callers must branch on None, never assume."""
    _load()
    return _library


def is_available() -> bool:
    return library() is not None


def load_error() -> str | None:
    """Why the native core is unavailable, or None when it loaded."""
    _load()
    return _load_error


def version() -> str | None:
    handle = library()
    if handle is None:
        return None
    raw = handle.tg_version_string()
    return raw.decode("utf-8") if raw else None
