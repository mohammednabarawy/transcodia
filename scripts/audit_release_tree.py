"""Check the tracked source tree for publication mistakes; not a legal clearance tool."""
import argparse
from pathlib import Path
import re
import subprocess

EXECUTABLE_SUFFIXES = {".exe", ".dll", ".pyd", ".so", ".dylib", ".zip", ".db", ".p12", ".pfx"}
PERSONAL_PATH = re.compile(rb"(?i)[a-z]:[/\\]+Users[/\\]+[^/\\\s\"']+")
TOKEN = re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9_-]{30,})")


def audit(root):
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True)
    files = [Path(name) for name in result.stdout.decode("utf-8").split("\0") if name]
    issues = []
    for relative in files:
        parts = relative.parts
        if relative.suffix.lower() in EXECUTABLE_SUFFIXES:
            issues.append(f"Executable/archive/private file in source tree: {relative.as_posix()}")
        if parts[0] in {"artifacts", "build", "dist", ".venv"} or relative.name in {"transcodia.local.json", ".env", "icon_resources.json"}:
            issues.append(f"Local/generated file in source tree: {relative.as_posix()}")
        if relative.suffix.lower() in {".py", ".md", ".json", ".toml", ".yml", ".ps1", ".sh", ".spec"}:
            contents = subprocess.run(["git", "show", ":" + relative.as_posix()], cwd=root,
                                      capture_output=True, check=True).stdout
            if PERSONAL_PATH.search(contents):
                issues.append(f"Personal absolute path: {relative.as_posix()}")
            if TOKEN.search(contents):
                issues.append(f"Possible secret token: {relative.as_posix()}")
    return files, issues


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    files, issues = audit(args.root)
    for issue in issues:
        print(issue)
    print(f"Checked {len(files)} tracked source files; {len(issues)} publication issues.")
    raise SystemExit(bool(issues))
