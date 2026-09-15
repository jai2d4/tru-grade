"""Environment probe for a prospective TruGrade analysis worker machine.

Run this on the machine you intend to use as the GPU worker (the V2 box):

    python check_env.py

It only reads — it installs nothing and changes nothing. Paste the whole
output back into the TruGrade chat; it's what decides how the worker gets
built (CUDA vs CPU torch, how many jobs can run at once, how the service
is installed, and whether a tunnel is needed for uploads).
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys


def line(label: str, value: object) -> None:
    print(f"{label:<28} {value}")


def run(cmd: list[str]) -> str | None:
    """Best-effort command capture; None when the tool isn't installed."""
    if not shutil.which(cmd[0]):
        return None
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).strip()
    except Exception as exc:  # a hung or broken tool shouldn't kill the probe
        return f"(failed: {exc})"


print("=" * 60)
print("TRUGRADE WORKER ENVIRONMENT PROBE")
print("=" * 60)

print("\n--- MACHINE ---")
line("OS", f"{platform.system()} {platform.release()}")
line("Version", platform.version())
line("Architecture", platform.machine())
line("Hostname", platform.node())
line("CPU cores (logical)", os.cpu_count())

# RAM — psutil isn't guaranteed present, so fall back to OS-specific probes.
try:
    import psutil  # type: ignore

    line("RAM total", f"{psutil.virtual_memory().total / 1e9:.1f} GB")
    line("RAM available", f"{psutil.virtual_memory().available / 1e9:.1f} GB")
except ImportError:
    if platform.system() == "Windows":
        mem = run(["wmic", "computersystem", "get", "TotalPhysicalMemory"])
        line("RAM total", mem or "(install psutil for detail)")
    else:
        mem = run(["free", "-h"])
        print(mem or "(install psutil for detail)")

print("\n--- DISK (where film and frames would live) ---")
for path in {os.path.abspath(os.sep), os.path.expanduser("~"), os.getcwd()}:
    try:
        usage = shutil.disk_usage(path)
        line(f"  {path}", f"{usage.free / 1e9:.0f} GB free of {usage.total / 1e9:.0f} GB")
    except Exception as exc:
        line(f"  {path}", f"(unreadable: {exc})")

print("\n--- GPU ---")
smi = run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
           "--format=csv,noheader"])
if smi:
    line("nvidia-smi", smi)
else:
    print("  No nvidia-smi found — either no NVIDIA GPU, or drivers aren't installed.")
    print("  (The worker still runs on CPU, just slower. This is the single")
    print("   biggest factor in how fast film gets analyzed.)")

print("\n--- PYTHON ---")
line("Executable", sys.executable)
line("Version", sys.version.split()[0])
line("Pip", (run([sys.executable, "-m", "pip", "--version"]) or "NOT FOUND").split(" (")[0])

print("\n--- RELEVANT PACKAGES (already installed?) ---")
for pkg in ("torch", "ultralytics", "cv2", "easyocr", "psycopg2", "asyncpg", "fastapi"):
    try:
        mod = __import__(pkg)
        version = getattr(mod, "__version__", "(no __version__)")
        extra = ""
        if pkg == "torch":
            try:
                extra = f"  CUDA available: {mod.cuda.is_available()}"
                if mod.cuda.is_available():
                    extra += f" ({mod.cuda.get_device_name(0)})"
            except Exception:
                extra = "  (CUDA check failed)"
        line(f"  {pkg}", f"{version}{extra}")
    except ImportError:
        line(f"  {pkg}", "not installed")

print("\n--- TOOLING ---")
for tool in ("git", "ffmpeg", "cloudflared", "docker"):
    found = shutil.which(tool)
    line(f"  {tool}", found or "not installed")

print("\n--- NETWORK (outbound reachability) ---")
# The worker needs outbound to: the Render app, the Render Postgres, and
# (for the YouTube path) youtube.com. Inbound is handled by a tunnel, so
# it is deliberately not tested here.
try:
    import urllib.request

    for name, url in [
        ("TruGrade on Render", "https://tru-scouting-engine.onrender.com/api/v1/health"),
        ("PyPI (installs)", "https://pypi.org"),
        ("YouTube", "https://www.youtube.com"),
    ]:
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                line(f"  {name}", f"reachable (HTTP {resp.status})")
        except Exception as exc:
            line(f"  {name}", f"FAILED: {type(exc).__name__}: {exc}")
except Exception as exc:
    print(f"  (network probe unavailable: {exc})")

print("\n" + "=" * 60)
print("Done. Paste this entire output back into the chat.")
print("=" * 60)
