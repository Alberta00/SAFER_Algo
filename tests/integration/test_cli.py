import json
import os
import subprocess
import sys
from pathlib import Path

from safer_sim.cli import main


def test_cli_run_replay_identical_artifacts(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({"duration_ms": 2000, "devices": 2, "interval_ms": 100, "scenario_id": "S4"}),
        encoding="utf-8",
    )
    first, second, third = (tmp_path / name for name in ("one", "two", "edf"))
    assert (
        main(["run", "--config", str(config), "--algorithm", "fifo", "--output", str(first)]) == 0
    )
    assert (
        main(
            [
                "run",
                "--trace",
                str(first / "trace.json"),
                "--algorithm",
                "fifo",
                "--output",
                str(second),
            ]
        )
        == 0
    )
    for name in (
        "metrics.json",
        "trace.json",
        "series.json",
        "messages.csv",
        "attempts.csv",
        "backlog.csv",
    ):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    assert (
        main(
            [
                "run",
                "--trace",
                str(first / "trace.json"),
                "--algorithm",
                "edf",
                "--output",
                str(third),
            ]
        )
        == 0
    )
    fifo = json.loads((first / "metrics.json").read_text())
    edf = json.loads((third / "metrics.json").read_text())
    assert fifo["identity"]["trace_hash"] == edf["identity"]["trace_hash"]
    assert fifo["identity"]["mode"] == "simulated"


def test_module_command_works_in_fresh_process(tmp_path: Path) -> None:
    # Works for both source checkout (pytest pythonpath) and installed wheel.
    environment = dict(os.environ)
    packages = Path(__file__).resolve().parents[2] / "packages"
    environment["PYTHONPATH"] = str(packages)
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "safer_sim",
            "run",
            "--scenario",
            "S1",
            "--algorithm",
            "fifo",
            "--seed",
            "42",
            "--output",
            str(tmp_path / "run"),
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    metrics = json.loads((tmp_path / "run" / "metrics.json").read_text())
    assert metrics["metrics"]["generated_count"] == 1440
    assert metrics["config"]["outage_duration_ms"] == 600_000


def test_invalid_cli_config_is_actionable(tmp_path: Path) -> None:
    import pytest

    config = tmp_path / "bad.json"
    config.write_text('{"devices":0}', encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main(
            [
                "run",
                "--algorithm",
                "fifo",
                "--config",
                str(config),
                "--output",
                str(tmp_path / "run"),
            ]
        )
    assert error.value.code == 2
