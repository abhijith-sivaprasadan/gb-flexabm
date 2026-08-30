import json

import pytest

from gb_flexabm.cli import compare_runs, default_config, main, run_demo
from gb_flexabm.provenance import verify_run


def test_offline_end_to_end_replay_and_tamper_guard(tmp_path):
    config = default_config()
    config["hours"], config["years"] = 8, [2026, 2027, 2028]
    left, right = tmp_path / "left", tmp_path / "right"
    run_demo(config, [11], left)
    run_demo(config, [11], right)
    compare_runs(left, right)
    assert verify_run(left)["run_id"] == verify_run(right)["run_id"]
    with pytest.raises(FileExistsError):
        run_demo(config, [11], left)
    (left / "summary.csv").write_text("tampered")
    with pytest.raises(ValueError, match="checksum"):
        verify_run(left)


def test_offline_smoke_cli(capsys):
    assert main(["validate", "--suite", "smoke"]) == 0
    assert all(json.loads(capsys.readouterr().out).values())


def test_cli_errors_are_nonzero(tmp_path):
    assert main(["verify", "--run", str(tmp_path / "missing")]) == 2


def test_no_empirical_claim_is_enabled_by_configuration(tmp_path):
    file = tmp_path / "bad.yaml"
    file.write_text("schema_version: 1\nscientific_status: calibrated\n")
    assert main(["demo", "run", "--config", str(file), "--output", str(tmp_path / "bad")]) == 2


def test_direct_api_also_rejects_calibrated_claim(tmp_path):
    config = default_config()
    config["scientific_status"] = "calibrated"
    with pytest.raises(ValueError, match="exploratory_synthetic"):
        run_demo(config, [11], tmp_path / "bad")


@pytest.mark.parametrize("seeds", [[], [1, 1], [-1], [True]])
def test_invalid_seed_sets_rejected(tmp_path, seeds):
    with pytest.raises(ValueError, match="Seeds"):
        run_demo(default_config(), seeds, tmp_path / "bad")
