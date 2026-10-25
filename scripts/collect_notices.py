"""Collect installed runtime dependency notices without copying executable code."""
import argparse
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "dependency-notices")
    args = parser.parse_args()
    print(f"Collected {len(collect(args.output))} dependency notice records in {args.output}")
