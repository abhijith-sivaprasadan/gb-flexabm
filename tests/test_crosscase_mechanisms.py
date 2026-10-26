"""Do not report completed evidence when cross-case source artifacts are missing."""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cli_fails_closed_without_the_five_original_cases(tmp_path):
    target = tmp_path / "unsanctioned_report.json"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.summarize_investor_mechanisms",
            "--root",
            str(tmp_path),
            "--output",
            str(target),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "FileNotFoundError" in proc.stderr
    assert not target.exists()
