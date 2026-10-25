"""
Bump the Transcodia version (single file: transcodia_app/version.py).

Updates the application's single version constant and reports the change.

Usage:
  python scripts/bump_version.py           # auto-bump minor  (0.9.4 -> 0.10.0)
  python scripts/bump_version.py 1.2.3     # set an explicit version
  python scripts/bump_version.py --print   # print the current version only
"""

import re
import sys
from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parents[1] / "transcodia_app" / "version.py"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
ASSIGNMENT_RE = re.compile(r'(APP_VERSION\s*=\s*")(\d+\.\d+\.\d+)(")')


def read_version() -> str:
    match = ASSIGNMENT_RE.search(VERSION_FILE.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"Could not find APP_VERSION in {VERSION_FILE}")
    return match.group(2)


def bump_minor(version: str) -> str:
    major, minor, _patch = version.split(".")
    return f"{major}.{int(minor) + 1}.0"


def write_version(new_version: str) -> None:
    text = VERSION_FILE.read_text(encoding="utf-8")
    updated, count = ASSIGNMENT_RE.subn(lambda m: f"{m.group(1)}{new_version}{m.group(3)}", text, count=1)
    if count != 1:
        raise SystemExit(f"Could not update APP_VERSION in {VERSION_FILE}")
    VERSION_FILE.write_text(updated, encoding="utf-8")


def main(argv: list) -> int:
    if argv == ["--print"]:
        print(read_version())
        return 0
    if len(argv) > 1:
        print("Usage: bump_version.py [VERSION | --print]", file=sys.stderr)
        return 1
    if argv:
        if not VERSION_RE.match(argv[0]):
            print(f"Error: '{argv[0]}' is not MAJOR.MINOR.PATCH", file=sys.stderr)
            return 1
        new_version = argv[0]
    else:
        new_version = bump_minor(read_version())
    old = read_version()
    write_version(new_version)
    print(f"{old} -> {new_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
