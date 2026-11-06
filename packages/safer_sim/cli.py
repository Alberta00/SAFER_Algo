"""File CLI. Wall-clock metadata deliberately stays outside deterministic artifacts."""

import argparse
import csv
import json
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from safer_metrics import calculate

from safer_sim.config import SCENARIOS, SimulationConfig
from safer_sim.engine import SimulationResult, simulate
from safer_sim.trace import Trace, canonical, digest, generate_trace


def write_json(path: Path, value: object) -> None:
    path.write_text(canonical(value) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        if not rows:
            return
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def export(
    result: SimulationResult,
    directory: Path,
    git_commit: str | None = None,
    run_started_at: str | None = None,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    config = asdict(result.trace.config)
    identity = {
        "mode": "simulated",
        "schema_version": 1,
        "algorithm": result.algorithm,
        "algorithm_version": "baseline-v1",
        "engine_version": "discrete-event-v1",
        "epoch_utc": "2026-11-06T00:00:00Z",
        "scenario_id": result.trace.config.scenario_id,
        "seed": result.trace.config.seed,
        "config_hash": digest(config),
        "trace_hash": result.trace.trace_hash,
    }
    identity["run_id"] = digest(identity)[:24]
    write_json(
        directory / "metrics.json",
        {
            "identity": identity,
            "config": config,
            "metrics": calculate(result),
        },
    )
    write_json(directory / "trace.json", result.trace.to_dict())
    write_json(directory / "series.json", result.series)
    write_csv(directory / "messages.csv", result.message_rows())
    write_csv(directory / "attempts.csv", [asdict(a) for a in result.attempts])
    write_csv(directory / "backlog.csv", list(result.series))
    write_json(
        directory / "metadata.json",
        {
            "run_started_at": run_started_at or datetime.now(UTC).isoformat(),
            "git_commit": git_commit,
            "note": "Wall-clock/provenance metadata excluded from deterministic comparison",
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SAFER deterministic simulation (M1 baselines)")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Generate or replay input and run a baseline")
    run.add_argument("--scenario", choices=SCENARIOS, default=None)
    run.add_argument("--algorithm", choices=("fifo", "priority", "edf"), required=True)
    run.add_argument("--seed", type=int, default=None)
    run.add_argument("--config", type=Path, help="JSON object of SimulationConfig fields")
    run.add_argument(
        "--trace", type=Path, help="Replay trace.json; cannot combine config overrides"
    )
    run.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    run_started_at = datetime.now(UTC).isoformat()
    try:
        if args.trace:
            if args.config or args.scenario is not None or args.seed is not None:
                raise ValueError("--trace cannot combine with --config, --scenario or --seed")
            trace = Trace.load(args.trace)
        else:
            values = json.loads(args.config.read_text(encoding="utf-8")) if args.config else {}
            if not isinstance(values, dict):
                raise ValueError("config must be a JSON object")
            if args.scenario is not None:
                values["scenario_id"] = args.scenario
            if args.seed is not None:
                values["seed"] = args.seed
            trace = generate_trace(SimulationConfig(**values))
        result = simulate(trace, args.algorithm)
        try:
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            commit = revision.stdout.strip() if revision.returncode == 0 else None
        except FileNotFoundError:
            commit = None
        export(result, args.output, commit, run_started_at)
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as error:
        parser.exit(2, f"error: {error}\n")
    print(f"simulated {args.algorithm}: {len(result.entries)} messages -> {args.output}")
    return 0
