from dataclasses import asdict, replace
from pathlib import Path

import pytest
from safer_metrics import calculate
from safer_sim.cli import write_json
from safer_sim.config import SCENARIOS, SimulationConfig
from safer_sim.engine import simulate
from safer_sim.trace import LinkSegment, Trace, generate_trace


def test_seed_replay_and_policy_inputs_identical(tmp_path: Path) -> None:
    config = SimulationConfig(scenario_id="S4", duration_ms=10000, devices=3, interval_ms=500)
    trace = generate_trace(config)
    assert trace.to_dict() == generate_trace(config).to_dict()
    assert trace.trace_hash != generate_trace(replace(config, seed=43)).trace_hash
    write_json(tmp_path / "trace.json", trace.to_dict())
    replay = Trace.load(tmp_path / "trace.json")
    assert replay == trace
    for algorithm in ("fifo", "priority", "edf"):
        result = simulate(replay, algorithm)
        assert result.trace.trace_hash == trace.trace_hash
        assert calculate(result) == calculate(simulate(trace, algorithm))


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_scenarios_are_bounded_and_reproducible(scenario: str) -> None:
    config = SimulationConfig(
        scenario_id=scenario,
        duration_ms=2000,
        interval_ms=200,
        devices=2,
        outage_start_ms=200,
        outage_duration_ms=1000,
        flap_up_ms=300,
        flap_down_ms=150,
    )
    trace = generate_trace(config)
    assert trace == generate_trace(config)
    assert trace.links[0].start_ms == 0 and trace.links[-1].end_ms == 2000
    for algorithm in ("fifo", "priority", "edf"):
        metrics = calculate(simulate(trace, algorithm))
        assert metrics["generated_count"] == len(trace.messages)
        assert metrics["acked_count"] <= metrics["remote_unique_count"] <= len(trace.messages)
        assert metrics["acked_count"] + metrics["pending_count"] == len(trace.messages)


def test_s1_really_has_600_second_disconnect() -> None:
    trace = generate_trace(SimulationConfig(scenario_id="S1"))
    downs = [s for s in trace.links if not s.up]
    assert len(downs) == 1
    assert downs[0].end_ms - downs[0].start_ms == 600_000


def test_generated_ids_sequence_and_category_metadata() -> None:
    trace = generate_trace(SimulationConfig(duration_ms=10000, devices=10, interval_ms=100))
    assert len({m.message_id for m in trace.messages}) == len(trace.messages)
    for device in range(10):
        messages = [m for m in trace.messages if m.device_id == f"virtual-sensor-{device:03d}"]
        assert [m.sequence_no for m in messages] == list(range(100))


@pytest.mark.parametrize(
    "change",
    [
        {"devices": 0},
        {"interval_ms": 0},
        {"seed": -1},
        {"duration_ms": True},
        {"event_probability": 1.1},
        {"loss_probability": float("nan")},
        {"ack_loss_probability": -0.1},
        {"max_in_flight": 2},
        {"payload_min_bytes": 20, "payload_max_bytes": 10},
        {"queue_limit": 0},
    ],
)
def test_invalid_config_rejected(change: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        SimulationConfig(**{**asdict(SimulationConfig()), **change})


def test_trace_rejects_gaps_and_duplicate_ids() -> None:
    config = SimulationConfig(duration_ms=1000)
    with pytest.raises(ValueError, match="contiguous"):
        Trace(config, (), (LinkSegment(0, 100), LinkSegment(101, 1000)))
    trace = generate_trace(config)
    with pytest.raises(ValueError, match="duplicate"):
        Trace(config, trace.messages + trace.messages, trace.links)
