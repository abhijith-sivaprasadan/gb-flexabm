import io
import json
import zipfile

import pytest

from gb_flexabm import workbench


def test_gui_scenario_units_and_seed_contract():
    config = workbench.scenario(24, 3, 22.5, 1.5, 40)
    assert config["years"] == [2026, 2027, 2028]
    assert config["base_demand_mw"] == 22500
    assert config["demand_growth_fraction"] == 0.015
    assert config["capacity_price_gbp_per_kw_year"] == 40
    assert config["scientific_status"] == "exploratory_synthetic"
    assert workbench.seed_set(11, 3) == [11, 12, 13]


@pytest.mark.parametrize(
    "args",
    [
        (8760, 6, 25, 2.5, 75),
        (24, 20, 25, 2.5, 75),
        (24, 6, float("nan"), 2.5, 75),
        (24, 6, 25, 99, 75),
        (24, 6, 25, 2.5, -1),
    ],
)
def test_gui_compute_and_input_bounds(args):
    with pytest.raises(ValueError):
        workbench.scenario(*args)


@pytest.mark.parametrize("first,count", [(-1, 1), (1, 0), (1, 11), (True, 1), (1, 1.5)])
def test_gui_seed_bounds(first, count):
    with pytest.raises(ValueError):
        workbench.seed_set(first, count)


def test_saved_runs_and_export_do_not_include_adjacent_files(tmp_path):
    config = workbench.scenario(24, 2, 25, 2.5, 75)
    output = workbench.create_run(tmp_path, config, [11])
    (output / "private-note.txt").write_text("not a run artifact")
    (tmp_path / "incomplete").mkdir()
    assert workbench.saved_runs(tmp_path) == [output]
    with zipfile.ZipFile(io.BytesIO(workbench.run_bundle(output))) as archive:
        assert "manifest.json" in archive.namelist()
        assert "summary.csv" in archive.namelist()
        assert "private-note.txt" not in archive.namelist()
    (output / "summary.csv").write_text("tampered")
    with pytest.raises(ValueError, match="checksum"):
        workbench.run_bundle(output)


def test_run_failure_releases_process_lock(tmp_path, monkeypatch):
    def fail(*args):
        raise RuntimeError("solver failed")

    monkeypatch.setattr(workbench, "run_demo", fail)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="solver failed"):
            workbench.create_run(tmp_path, {}, [11])
    assert workbench.saved_runs(tmp_path) == []


def test_displayed_files_require_manifest_entries(tmp_path):
    output = workbench.create_run(tmp_path, workbench.scenario(24, 2, 25, 2.5, 75), [11])
    manifest_path = output / "manifest.json"
    record = json.loads(manifest_path.read_text())
    del record["outputs"]["summary.csv"]
    manifest_path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="all be listed"):
        workbench.read_result(output)


def test_concurrent_session_is_rejected(tmp_path):
    with workbench._RUN_LOCK:
        with pytest.raises(RuntimeError, match="Another local experiment"):
            workbench.create_run(tmp_path, {}, [11])
