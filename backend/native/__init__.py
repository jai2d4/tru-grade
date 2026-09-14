"""Optional C/C++ acceleration for the tracking and kinematics hot paths.

The backend never requires this. Every caller checks ``is_available()`` and
falls back to the pure-Python implementation it shadows; the two are asserted
identical in backend/tests/test_native_parity.py. Build it with
scripts/build_native.sh, or set TRUGRADE_DISABLE_NATIVE=1 to force the fallback.
"""
from __future__ import annotations

from ._loader import is_available, load_error, version
from .core import (
    NativeCoreError,
    NativeTracker,
    RawMovement,
    RawTrackPoint,
    iou,
    movement_metrics,
    torso_orientation_deg,
)

__all__ = [
    "NativeCoreError",
    "NativeTracker",
    "RawMovement",
    "RawTrackPoint",
    "iou",
    "is_available",
    "load_error",
    "movement_metrics",
    "torso_orientation_deg",
    "version",
]


def status() -> dict:
    """A small report for the health endpoint."""
    available = is_available()
    return {
        "available": available,
        "version": version() if available else None,
        "reason": None if available else load_error(),
    }
