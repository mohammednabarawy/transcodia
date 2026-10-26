"""Collect installed runtime dependency notices without copying executable code."""
import argparse
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import hashlib
import subprocess
import os

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]


def collect(destination):
    destination.mkdir(parents=True, exist_ok=True)
    pending = [Requirement(line).name for line in (ROOT / "requirements.txt").read_text().splitlines()
               if line.strip() and not line.startswith("#")]
    seen = set()
    records = []
    while pending:
        name = pending.pop()
        distribution = metadata.distribution(name)
        normalized = distribution.metadata["Name"].lower().replace("_", "-")
        if normalized in seen:
            continue
        seen.add(normalized)
        folder = destination / normalized
        folder.mkdir(exist_ok=True)
        notices = []
        for entry in distribution.files or []:
            relative = str(entry).replace("\\", "/")
            is_metadata = ".dist-info/" in relative
            is_notice = any(token in relative.lower() for token in ("license", "copying", "notice", "copyright"))
            is_vera_notice = relative.endswith("bitstream-vera-license.txt")
            if (is_metadata and is_notice) or is_vera_notice:
                source = Path(distribution.locate_file(entry))
                if source.is_file():
                    target = folder / relative.replace("/", "__")
                    shutil.copyfile(source, target)
                    notices.append(target.name)
        records.append({"name": distribution.metadata["Name"], "version": distribution.version,
                        "license": distribution.metadata.get("License-Expression") or distribution.metadata.get("License") or "See bundled notice files",
                        "notices": sorted(notices),
                        "project_urls": distribution.metadata.get_all("Project-URL") or []})
        for dependency in distribution.requires or []:
            requirement = Requirement(dependency)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.append(requirement.name)
    records.sort(key=lambda row: row["name"].lower())
    (destination / "manifest.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    return records


def collect_ffmpeg(folder, destination):
    folder = folder.resolve(strict=True)
    executable = folder / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    version = subprocess.run([str(executable), "-version"], capture_output=True, check=True, timeout=15)
    configuration = (version.stdout + version.stderr).decode("utf-8", errors="replace")
    if "--enable-nonfree" in configuration:
        raise ValueError("A non-redistributable FFmpeg build cannot be packaged.")
    license_result = subprocess.run([str(executable), "-L"], capture_output=True, check=True, timeout=15)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "BUILD.txt").write_text(configuration, encoding="utf-8")
    (destination / "LICENSE-output.txt").write_bytes(license_result.stdout + license_result.stderr)
    for filename in ("LICENSE", "LICENSE.txt", "README.txt"):
        source = folder.parent / filename
        if source.is_file():
            shutil.copyfile(source, destination / filename)
    shutil.copyfile(ROOT / "LICENSES" / "GPL-3.0.txt", destination / "GPL-3.0.txt")
    files = []
    for path in sorted(folder.iterdir()):
        if path.is_file() and (path.suffix.lower() == ".dll" or path.name.lower() in {"ffmpeg", "ffmpeg.exe", "ffprobe", "ffprobe.exe"}):
            with path.open("rb") as stream:
                digest = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            files.append({"name": path.name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()})
    (destination / "manifest.json").write_text(json.dumps({"version": configuration.splitlines()[0], "files": files}, indent=2), encoding="utf-8")
    return files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "dependency-notices")
    parser.add_argument("--ffmpeg-dir", type=Path, help="Also record the engine files and upstream notices")
    args = parser.parse_args()
    print(f"Collected {len(collect(args.output))} dependency notice records in {args.output}")
    if args.ffmpeg_dir:
        files = collect_ffmpeg(args.ffmpeg_dir, ROOT / "artifacts" / "ffmpeg-notices")
        print(f"Recorded {len(files)} bundled media runtime files and upstream notices")
