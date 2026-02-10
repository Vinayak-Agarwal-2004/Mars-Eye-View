#!/usr/bin/env python3
"""
Single controller for running GDELT-Streamer test suite.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
REPORTS = ROOT / "reports"


def run_pytest(args: list[str]) -> int:
    cmd = [sys.executable, "-m", "pytest"] + args
    return subprocess.call(cmd, cwd=str(ROOT))


def run_manual_scripts() -> int:
    manual_dir = TESTS / "manual"
    if not manual_dir.exists():
        print("No tests/manual/ directory found")
        return 0
    scripts = sorted(manual_dir.glob("*.py"))
    if not scripts:
        print("No manual scripts found")
        return 0
    failed = 0
    for script in scripts:
        if script.name.startswith("_"):
            continue
        print(f"\n--- Running {script.name} ---")
        ret = subprocess.call([sys.executable, str(script)], cwd=str(ROOT))
        if ret != 0:
            failed += 1
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GDELT-Streamer tests")
    parser.add_argument(
        "--tier",
        choices=["unit", "integration", "full", "manual"],
        default="unit",
        help="Test tier: unit (fast), integration, full (incl e2e/slow), manual",
    )
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--ci", action="store_true", help="CI mode: junit XML + coverage XML")
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel (pytest-xdist)")
    parser.add_argument("--manual", action="store_true", help="Also run manual verification scripts")
    parser.add_argument("pytest_args", nargs="*", help="Extra args passed to pytest")
    opts = parser.parse_args()

    if opts.tier == "manual":
        return run_manual_scripts()

    pytest_args: list[str] = opts.pytest_args.copy()

    if opts.tier == "unit":
        pytest_args.extend(["-m", "unit"])
    elif opts.tier == "integration":
        pytest_args.extend(["-m", "integration"])
    elif opts.tier == "full":
        pytest_args.extend(["-m", "unit or integration or e2e"])

    if opts.coverage:
        pytest_args.extend([
            "--cov=server.app.services",
            "--cov=ingestion_engine",
            "--cov-report=term-missing",
            "--cov-report=html:reports/coverage",
        ])
        REPORTS.mkdir(parents=True, exist_ok=True)

    if opts.ci:
        REPORTS.mkdir(parents=True, exist_ok=True)
        pytest_args.extend([
            f"--junitxml={REPORTS / 'junit.xml'}",
            "--cov=server.app.services",
            "--cov=ingestion_engine",
            "--cov-report=xml",
            f"--cov-fail-under=0",
        ])

    if opts.parallel:
        pytest_args.append("-n=auto")

    ret = run_pytest(pytest_args)

    if opts.manual and ret == 0:
        ret = run_manual_scripts()

    return ret


if __name__ == "__main__":
    sys.exit(main())
