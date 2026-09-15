"""Check field-calibration accuracy against distances you already know.

The automatic calibration measures under a yard on synthetic footage
(backend/tests/test_field_calibration_accuracy.py), but synthetic footage
has no lens distortion, no players standing on the boundary and no
stadium in frame. Real-footage accuracy is unproven, and nothing in the
app can prove it by itself: the app has no independent source of truth to
check against — only you do, by knowing what actually happened in the
play.

So this asks you. Pick a play where you know the real distance from the
field markings (a run from the 30 to the 45 is 15 yards) and compare it
to what the engine computed.

    python scripts/check_calibration.py <video_id>
    python scripts/check_calibration.py <video_id> --track 3 --actual-yards 15

With no --actual-yards it just reports what the engine measured, so you
can see the numbers before deciding which play to verify.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

STORAGE = Path(os.getenv("TRUGRADE_STORAGE_DIR", Path(__file__).resolve().parent.parent / "backend" / "storage"))


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def describe_calibration(video_id: str) -> dict | None:
    calibration = _load(STORAGE / "calibrations" / f"{video_id}.json")
    print("=" * 66)
    print("FIELD CALIBRATION")
    print("=" * 66)
    if calibration is None:
        print("  No calibration for this video.")
        print("  Run automatic calibration from the Film Analysis screen, or")
        print("  confirm known field points manually, then re-run this.")
        return None

    status = calibration.get("status")
    print(f"  status      : {status}")
    print(f"  method      : {calibration.get('method')}")
    print(f"  confidence  : {calibration.get('confidence')}")
    print(f"  points used : {len(calibration.get('points', []))}")
    if status != "calibrated":
        print(f"  reason      : {calibration.get('reason')}")
        print("\n  Not calibrated, so no yard figure below can be trusted.")
        return calibration

    # Said plainly because the number invites the opposite reading.
    print("\n  NOTE: `confidence` describes how much of the frame the detected")
    print("  field covered — NOT how accurate the yard numbers are. Only the")
    print("  comparison below tells you that.")
    if calibration.get("measurement_quality") == "estimated":
        print("  This calibration is boundary-estimated. Confirming known field")
        print("  points yields verified yardage instead.")
    return calibration


def describe_tracks(video_id: str, only_track: int | None) -> list[dict]:
    tracks = _load(STORAGE / "vision" / video_id / "tracks.json") or []
    measured = [t for t in tracks if (t.get("movement") or {}).get("displacement_yards") is not None]

    print("\n" + "=" * 66)
    print("MEASURED MOVEMENT")
    print("=" * 66)
    if not tracks:
        print("  No tracks — analysis has not run for this video.")
        return []
    if not measured:
        print(f"  {len(tracks)} track(s), none with yard measurements.")
        print("  Movement in yards requires a calibration; see above.")
        return []

    print(f"  {'track':>6}  {'yards':>8}  {'top speed':>12}  {'mph':>7}")
    print(f"  {'-' * 6}  {'-' * 8}  {'-' * 12}  {'-' * 7}")
    for track in sorted(measured, key=lambda t: -(t["movement"].get("displacement_yards") or 0)):
        if only_track is not None and track.get("track_id") != only_track:
            continue
        move = track["movement"]
        print(f"  {track.get('track_id'):>6}  "
              f"{move.get('displacement_yards'):>8}  "
              f"{str(move.get('max_speed_yards_per_second')):>12}  "
              f"{str(move.get('field_speed_mph')):>7}")
    return measured


def compare(measured: list[dict], track_id: int, actual_yards: float) -> int:
    track = next((t for t in measured if t.get("track_id") == track_id), None)
    print("\n" + "=" * 66)
    print("ACCURACY CHECK")
    print("=" * 66)
    if track is None:
        print(f"  Track {track_id} has no yard measurement to compare.")
        return 1

    engine = float(track["movement"]["displacement_yards"])
    error = engine - actual_yards
    pct = abs(error) / actual_yards * 100 if actual_yards else float("inf")

    print(f"  you measured   : {actual_yards:.1f} yd")
    print(f"  engine measured: {engine:.1f} yd")
    print(f"  error          : {error:+.1f} yd  ({pct:.0f}%)")

    # Thresholds stated as judgements, not as a pass/fail the tool can
    # actually certify from one sample.
    print()
    if pct <= 5:
        print("  Within 5%. Consistent with usable calibration on this clip.")
    elif pct <= 15:
        print("  Off by 5-15%. Usable for relative comparisons, not for quoting")
        print("  absolute distances. Confirming known field points should improve it.")
    else:
        print("  Off by more than 15%. Do not rely on absolute yardage or speed")
        print("  from this clip. Most likely the visible field wasn't the whole")
        print("  field, or the camera moved. Confirm field points manually.")
    print("\n  One play is one data point. Repeat on a few plays, ideally at")
    print("  different parts of the field, before trusting the numbers.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video_id")
    parser.add_argument("--track", type=int, help="track id to check")
    parser.add_argument("--actual-yards", type=float,
                        help="the real distance you measured from field markings")
    args = parser.parse_args()

    if not (STORAGE / "vision" / args.video_id).is_dir():
        print(f"No analysis found for video {args.video_id} under {STORAGE}.")
        print("Check the id, or set TRUGRADE_STORAGE_DIR to the right location.")
        return 1

    describe_calibration(args.video_id)
    measured = describe_tracks(args.video_id, args.track)

    if args.actual_yards is not None:
        if args.track is None:
            print("\n--actual-yards needs --track, so it knows which player you measured.")
            return 1
        return compare(measured, args.track, args.actual_yards)

    print("\nTo check accuracy, pick a play whose real distance you can read off")
    print("the field markings, then run:")
    print(f"  python scripts/check_calibration.py {args.video_id} --track <id> --actual-yards <yards>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
