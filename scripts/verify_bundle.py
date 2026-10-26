"""Run a desktop bundle outside the checkout, without host FFmpeg or local settings."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def verify_bundle(executable: Path, report_path: Path, ffmpeg=None, require_bundled=False, media_source=None) -> dict:
    executable = executable.resolve(strict=True)
    environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "FFMPEG_PATH"):
        environment.pop(name, None)
    environment["PATH"] = (str(Path(environment["SYSTEMROOT"]) / "System32")
                           if os.name == "nt" else "/usr/bin:/bin")
    environment["QT_QPA_PLATFORM"] = "offscreen"
    if ffmpeg:
        environment["FFMPEG_PATH"] = str(Path(ffmpeg).resolve(strict=True))
    with tempfile.TemporaryDirectory(prefix="transcodia-bundle-check-") as folder:
        environment.update({"HOME": folder, "USERPROFILE": folder,
                            "XDG_CONFIG_HOME": folder, "APPDATA": folder,
                            "LOCALAPPDATA": folder})
        temporary_report = Path(folder) / "runtime.json"
        command = [str(executable), "--smoke-test", "--verify-runtime", str(temporary_report)]
        if media_source:
            command.extend(["--verify-media", str(Path(media_source).resolve(strict=True))])
        result = subprocess.run(
            command,
            cwd=folder, env=environment, capture_output=True, timeout=180 if media_source else 120)
        if not temporary_report.is_file():
            raise RuntimeError(f"Bundle exited {result.returncode} without a runtime report. "
                               + result.stderr.decode("utf-8", errors="replace")[-3000:])
        report = json.loads(temporary_report.read_text(encoding="utf-8"))
        report["exit_code"] = result.returncode
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if result.returncode or not report.get("ok") or not report.get("frozen"):
            raise RuntimeError(f"Packaged runtime verification failed: {report}")
        if require_bundled and not report.get("engine_bundled"):
            raise RuntimeError("Packaged verification used an external FFmpeg instead of the bundled engine.")
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--report", type=Path, default=Path("artifacts/bundle-verification.json"))
    parser.add_argument("--ffmpeg", type=Path, help="Independently installed engine used only for verification")
    parser.add_argument("--require-bundled", action="store_true", help="Fail if FFmpeg is not inside the package")
    parser.add_argument("--media-source", type=Path, help="Also verify a five-second clip from this source")
    args = parser.parse_args()
    print(json.dumps(verify_bundle(args.executable, args.report, args.ffmpeg, args.require_bundled, args.media_source), indent=2))
