"""Loader behaviour, including the paths where the native core is absent.

These run whether or not the library was built — the point is that a missing or
unusable library degrades to Python cleanly, and that is exactly what cannot be
tested only on a machine where the build succeeded.

The env-var cases run in subprocesses because loading is cached per process for
the life of the interpreter, deliberately: re-probing the filesystem on every
frame would cost more than it could ever save.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from backend.native import _loader

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run(code: str, **env_overrides: str) -> str:
    """Execute `code` in a fresh interpreter rooted at the repo.

    Both TRUGRADE_ variables are stripped from the inherited environment first
    and only the overrides put back. Otherwise running the suite under
    TRUGRADE_DISABLE_NATIVE=1 — which is a supported way to run it, and what CI
    does — would leak that flag in and quietly answer a different question than
    the test is asking.
    """
    import os

    environment = {key: value for key, value in os.environ.items()
                   if key not in {"TRUGRADE_DISABLE_NATIVE", "TRUGRADE_NATIVE_LIB"}}
    environment["PYTHONPATH"] = str(REPO_ROOT)
    environment.update(env_overrides)

    result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, env=environment, cwd=REPO_ROOT, check=True)
    return result.stdout.strip()


def test_explicit_library_path_is_authoritative(monkeypatch):
    monkeypatch.setenv("TRUGRADE_NATIVE_LIB", "/somewhere/libtrugrade_core.so")
    assert _loader._candidate_paths() == [Path("/somewhere/libtrugrade_core.so")]


def test_default_search_covers_the_build_directory(monkeypatch):
    monkeypatch.delenv("TRUGRADE_NATIVE_LIB", raising=False)
    candidates = _loader._candidate_paths()
    assert candidates
    assert all(path.is_absolute() for path in candidates)
    assert any(path.parent.name == "build" for path in candidates)


def test_blank_override_falls_back_to_the_default_search(monkeypatch):
    """An unset variable and an empty one mean the same thing."""
    monkeypatch.setenv("TRUGRADE_NATIVE_LIB", "   ")
    assert len(_loader._candidate_paths()) > 1


def test_status_is_reportable_either_way():
    """The health endpoint renders this dict; it must be complete in both states."""
    from backend import native

    status = native.status()
    assert set(status) == {"available", "version", "reason"}
    assert isinstance(status["available"], bool)
    if status["available"]:
        assert status["version"] and status["reason"] is None
    else:
        assert status["version"] is None and status["reason"]


def test_disable_flag_forces_the_python_path():
    output = _run(
        "from backend import native;"
        "from backend.vision.tracker import ByteTrackTracker;"
        "print(native.is_available(), ByteTrackTracker().uses_native_core)",
        TRUGRADE_DISABLE_NATIVE="1",
    )
    assert output == "False False"


def test_a_missing_library_still_tracks():
    """The whole point of the fallback: results, not an exception."""
    output = _run(
        "from backend import native;"
        "from backend.vision.tracker import ByteTrackTracker;"
        "t = ByteTrackTracker();"
        "points = t.update({'frame': 0, 'timestamp_ms': 0, 'detections': ["
        "{'class': 'player', 'confidence': 0.9, 'bbox': [0, 0, 10, 20]}]});"
        "print(native.is_available(), points[0]['track_id'], points[0]['center_x'])",
        TRUGRADE_NATIVE_LIB="/nonexistent/libtrugrade_core.so",
    )
    assert output == "False 1 5.0"


def test_an_unloadable_library_reports_why():
    output = _run(
        "from backend import native;"
        "print(native.is_available());"
        "print(native.load_error())",
        TRUGRADE_NATIVE_LIB="/nonexistent/libtrugrade_core.so",
    )
    available, reason = output.splitlines()
    assert available == "False"
    assert "/nonexistent/libtrugrade_core.so" in reason
