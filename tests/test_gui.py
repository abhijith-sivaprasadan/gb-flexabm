"""Real Streamlit execution and CLI equivalence; no live web or data APIs."""

from pathlib import Path

import pytest

testing = pytest.importorskip("streamlit.testing.v1", reason="Install the optional gui extra")

from gb_flexabm import workbench  # noqa: E402
from gb_flexabm.cli import compare_runs, run_demo  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("GBFLEX_GUI_RUNS", str(tmp_path / "gui"))
    monkeypatch.chdir(tmp_path)
    return testing.AppTest.from_file(
        Path(workbench.__file__).with_name("gui.py"), default_timeout=60
    ).run()


def run_small(app):
    app.number_input(key="years").set_value(2)
    app.number_input(key="count").set_value(1)
    app.number_input(key="demand").set_value(22.5)
    app.number_input(key="growth").set_value(1.5)
    app.number_input(key="payment").set_value(40.0)
    return app.button[0].click().run()


def test_gui_real_run_matches_cli_and_keeps_saved_assumptions(app, tmp_path):
    assert not app.exception
    assert not app.metric
    assert "uncalibrated" in app.warning[0].value
    run_small(app)
    assert not app.exception
    assert len(app.metric) == 3
    assert len(app.download_button) == 2
    output = Path(app.session_state["active_run"])
    _, config = workbench.read_result(output)
    assert config == workbench.scenario(24, 2, 22.5, 1.5, 40)
    run_demo(config, [11], tmp_path / "cli")
    compare_runs(output, tmp_path / "cli")
    app.number_input(key="demand").set_value(30.0).run()
    assert any("base demand 22.5 GW" in caption.value for caption in app.caption)
    assert Path(app.session_state["active_run"]) == output
    (output / "summary.csv").write_text("tampered")
    app.run()
    assert not app.exception
    assert not app.metric and not app.download_button
    assert any("could not be verified" in error.value for error in app.error)


def test_failed_gui_run_clears_previous_success(app, monkeypatch):
    run_small(app)
    assert app.metric

    def fail(*args):
        raise RuntimeError("deliberate test failure")

    monkeypatch.setattr(workbench, "create_run", fail)
    app.button[0].click().run()
    assert not app.exception
    assert not app.metric and not app.download_button
    assert any("Experiment failed" in error.value for error in app.error)


def test_gui_launcher_is_loopback_and_telemetry_off(tmp_path, monkeypatch):
    captured = {}

    def call(command, env):
        captured.update(command=command, env=env)
        return 0

    monkeypatch.setattr(workbench.subprocess, "call", call)
    assert workbench.launch(8501, tmp_path) == 0
    assert "--server.address=127.0.0.1" in captured["command"]
    assert "--browser.gatherUsageStats=false" in captured["command"]
    assert "--server.enableXsrfProtection=true" in captured["command"]
    assert captured["env"]["GBFLEX_GUI_RUNS"] == str(tmp_path.resolve())
