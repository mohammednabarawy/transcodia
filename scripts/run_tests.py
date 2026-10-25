"""Run the regression suite and save machine-readable results. No desktop interaction."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--coverage", action="store_true", help="Also measure line and branch coverage")
parser.add_argument("--report-dir", default="artifacts/tests")
parser.add_argument("pytest_args", nargs="*", help="Optional test paths")
args = parser.parse_args()
reports = (ROOT / args.report_dir).resolve()
reports.mkdir(parents=True, exist_ok=True)
environment = os.environ.copy()
environment["QT_QPA_PLATFORM"] = "offscreen"
environment["PYTHONIOENCODING"] = "utf-8"
command = [sys.executable, "-m", "pytest"]
data = reports / ".coverage"
if args.coverage:
    tools = ROOT / "artifacts/test-tools"
    environment["PYTHONPATH"] = str(tools) + os.pathsep + environment.get("PYTHONPATH", "")
    check = subprocess.run([sys.executable, "-c", "import coverage"], env=environment, capture_output=True)
    if check.returncode:
        parser.error("Install coverage locally: python -m pip install --target artifacts/test-tools coverage")
    command = [sys.executable, "-m", "coverage", "run", "--branch", "--source=transcodia_app,transcodia_engine",
               "--omit=*/tests/*", f"--data-file={data}", "-m", "pytest"]
command += ["-q", "-o", "faulthandler_timeout=30", f"--junitxml={reports / 'junit.xml'}", *args.pytest_args]
print("Running regression tests; reports:", reports, flush=True)
result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
log = result.stdout + result.stderr
(reports / "pytest.log").write_text(log, encoding="utf-8")
print(log, end="")
summary = {"exit_code": result.returncode}
if (reports / "junit.xml").is_file():
    suites = ET.parse(reports / "junit.xml").getroot()
    entries = list(suites) if suites.tag == "testsuites" else [suites]
    for key in ("tests", "failures", "errors", "skipped"):
        summary[key] = sum(int(s.get(key, "0")) for s in entries)
    summary["seconds"] = sum(float(s.get("time", "0")) for s in entries)
if args.coverage:
    for options in (["report", "-m"], ["json", "-o", str(reports / "coverage.json")], ["html", "-d", str(reports / "coverage-html")]):
        subprocess.run([sys.executable, "-m", "coverage", *options, f"--data-file={data}"], cwd=ROOT, env=environment, check=True)
    totals = json.loads((reports / "coverage.json").read_text())["totals"]
    summary["line_coverage_percent"] = round(100 * totals["covered_lines"] / totals["num_statements"], 2)
    summary["branch_coverage_percent"] = round(100 * totals["covered_branches"] / totals["num_branches"], 2) if totals["num_branches"] else 100
(reports / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print("Summary:", json.dumps(summary))
sys.exit(result.returncode)
