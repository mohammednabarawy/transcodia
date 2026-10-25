"""Run a desktop bundle outside the checkout, without host FFmpeg or local settings."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def verify_bundle(executable: Path, report_path: Path, ffmpeg=None) -> dict:
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
        result = subprocess.run(
            [str(executable), "--smoke-test", "--verify-runtime", str(temporary_report)],
            cwd=folder, env=environment, capture_output=True, timeout=120)
        if not temporary_report.is_file():
            raise RuntimeError(f"Bundle exited {result.returncode} without a runtime report. "
                               + result.stderr.decode("utf-8", errors="replace")[-3000:])
        report = json.loads(temporary_report.read_text(encoding="utf-8"))
        report["exit_code"] = result.returncode
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if result.returncode or not report.get("ok") or not report.get("frozen"):
            raise RuntimeError(f"Packaged runtime verification failed: {report}")
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--report", type=Path, default=Path("artifacts/bundle-verification.json"))
    parser.add_argument("--ffmpeg", type=Path, help="Independently installed engine used only for verification")
    args = parser.parse_args()
    print(json.dumps(verify_bundle(args.executable, args.report, args.ffmpeg), indent=2))
