"""Write .env from answers, without anyone hand-editing a config file.

Called by setup_trugrade.bat. Prompts only for what genuinely cannot be
derived — the Gemini key and the database URL — generates the shared API
secret rather than asking a person to invent one, and leaves every other
value at its documented default.

Run again any time to change an answer: existing values are offered as
the default, so pressing Enter keeps them.
"""
from __future__ import annotations

import re
import secrets
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"


def read_env() -> dict[str, str]:
    if not ENV.is_file():
        return {}
    values = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def set_key(text: str, key: str, value: str) -> str:
    """Replace KEY=... in place, preserving surrounding comments, or append
    it if the key isn't present."""
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(f"{key}={value}", text)
    return text.rstrip("\n") + f"\n{key}={value}\n"


def ask(prompt: str, current: str, *, secret_ok: bool = False) -> str:
    shown = ""
    if current:
        # Don't echo a whole credential back to the screen.
        shown = f" [{current[:6]}…]" if secret_ok and len(current) > 8 else f" [{current}]"
    answer = input(f"{prompt}{shown}\n> ").strip()
    return answer or current


def main() -> int:
    # Whether .env already existed decides if APP_ENV is a real choice the
    # operator made, or just the template's default carried along.
    had_env = ENV.is_file()
    if not had_env:
        shutil.copy(EXAMPLE, ENV)

    text = ENV.read_text(encoding="utf-8")
    current = read_env()

    print("=" * 62)
    print("TruGrade configuration")
    print("=" * 62)
    print("Two answers needed. Press Enter to keep an existing value.\n")

    print("1) Gemini API key — the only paid external API this app uses.")
    print("   Get one at: https://aistudio.google.com/apikey")
    gemini = ask("   Paste your Gemini API key:", current.get("GEMINI_API_KEY", ""), secret_ok=True)

    print("\n2) Database URL — where athletes, accounts and the job queue live.")
    print("   Render dashboard -> your database -> Connect -> External connection string.")
    print("   Leave blank to use a PostgreSQL running on this machine.")
    database = ask("   Paste your DATABASE_URL:", current.get("DATABASE_URL", ""))

    # Not asked: a shared secret is a worse password when a human invents
    # one, and there is nothing to look up. Generated once and kept.
    api_key = current.get("API_KEY", "")
    if not api_key or api_key in {"change_me", ""}:
        api_key = secrets.token_urlsafe(32)
        print("\n   Generated a random API_KEY for you (no need to remember it).")

    text = set_key(text, "GEMINI_API_KEY", gemini)
    text = set_key(text, "API_KEY", api_key)
    # The frontend bundle sends this as X-API-Key; it must match API_KEY
    # exactly or the deployed page cannot call its own API.
    text = set_key(text, "VITE_API_KEY", api_key)
    if database:
        text = set_key(text, "DATABASE_URL", database)
    # This script configures a real deployment serving real members, so a
    # first run lands on production — which is also what makes the app
    # refuse to start without API_KEY. An APP_ENV already chosen in an
    # existing .env is left alone.
    app_env = current.get("APP_ENV") if had_env else None
    text = set_key(text, "APP_ENV", app_env or "production")

    ENV.write_text(text, encoding="utf-8")

    print("\n" + "=" * 62)
    print(f"Wrote {ENV}")
    missing = [name for name, value in (("GEMINI_API_KEY", gemini),) if not value]
    if missing:
        print("STILL MISSING: " + ", ".join(missing))
        print("Film analysis will fail until it's set. Re-run this to add it.")
    else:
        print("Configuration complete.")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
