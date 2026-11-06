from collections.abc import Callable

import pytest
from safer_core.models import Category, Message
from safer_metrics import calculate
from safer_sim.config import SimulationConfig
from safer_sim.engine import simulate
from safer_sim.trace import LinkSegment, Trace


def test_latency_and_expired_deadline_are_not_dropped(message: Callable[..., Message]) -> None:
    trace = Trace(
        SimulationConfig(duration_ms=300),
        (
            message("e1", category=Category.EVENT, deadline=120),
            message("e2", category=Category.EVENT, deadline=200),
        ),
        (LinkSegment(0, 300, bandwidth_bps=8000, latency_ms=20),),
    )
    result = simulate(trace, "fifo")
    assert [e.committed_ms for e in result.entries] == [120, 260]
    assert [e.acked_ms for e in result.entries] == [140, 280]
    event = calculate(result)["event"]
    assert event["latency_ms"] == {"mean": 190, "p50": 190, "p95": 253, "p99": 258.6}
    assert event["deadline_miss_count"] == 1
    assert event["deadline_miss_rate"] == 0.5
    assert calculate(result)["acked_bytes_per_second"] == pytest.approx(200 / 0.3)


def test_undelivered_deadlines_and_censoring(message: Callable[..., Message]) -> None:
    trace = Trace(
        SimulationConfig(duration_ms=100),
        (
            message("expired", category=Category.EVENT, deadline=50),
            message("future", category=Category.EVENT, deadline=150),
        ),
        (LinkSegment(0, 100, up=False),),
    )
    metrics = calculate(simulate(trace, "fifo"))
    assert metrics["event"]["deadline_miss_count"] == 1
    assert metrics["event"]["censored_count"] == 1
    assert metrics["event"]["deadline_miss_rate"] == 0.5
    assert metrics["event"]["latency_ms"]["mean"] is None
    assert metrics["pending_count"] == 2


def test_three_sample_aoi_hand_calculation(message: Callable[..., Message]) -> None:
    # commits 1000,3000,5000; sample times 0,2000,4000.
    # area = 4e6 + 4e6 + 1.5e6 = 9.5e6; coverage 5000 => mean 1900ms.
    trace = Trace(
        SimulationConfig(duration_ms=6000),
        tuple(message(str(i), created=i * 2000, category=Category.LIVE_STATE) for i in range(3)),
        (LinkSegment(0, 6000, bandwidth_bps=800, latency_ms=0),),
    )
    aoi = calculate(simulate(trace, "fifo"))["live_aoi"]
    assert aoi["mean_ms"] == 1900
    assert aoi["per_key"]["sensor/temperature"]["area_ms2"] == 9_500_000
    assert aoi["per_key"]["sensor/temperature"]["coverage_ms"] == 5000


def test_older_live_delivery_never_regresses_aoi(message: Callable[..., Message]) -> None:
    trace = Trace(
        SimulationConfig(duration_ms=1000),
        (
            message("new", created=100, category=Category.LIVE_STATE, sample=100, size=10),
            message("old", created=100, category=Category.LIVE_STATE, sample=0, size=10),
        ),
        (LinkSegment(0, 1000, bandwidth_bps=8000, latency_ms=0),),
    )
    aoi = calculate(simulate(trace, "fifo"))["live_aoi"]
    assert aoi["per_key"]["sensor/temperature"]["series"][-1]["aoi_ms"] == 900
    assert aoi["mean_ms"] == 455


def test_recovery_uses_pre_restore_snapshot(message: Callable[..., Message]) -> None:
    trace = Trace(
        SimulationConfig(duration_ms=200),
        (
            message("backlog", size=10),
            message("new", created=100, size=10),
        ),
        (LinkSegment(0, 100, up=False), LinkSegment(100, 200, bandwidth_bps=8000, latency_ms=0)),
    )
    result = simulate(trace, "fifo")
    recovery = calculate(result)["history"]["recoveries"][0]
    assert recovery["target_ids"] == ["backlog"]
    assert recovery["recovery_time_ms"] == 10
    assert recovery["completeness"] == 1
    assert [e.acked_ms for e in result.entries] == [110, 120]


def test_incomplete_recovery_is_not_zero_seconds(message: Callable[..., Message]) -> None:
    trace = Trace(
        SimulationConfig(duration_ms=105),
        (message("backlog"),),
        (
            LinkSegment(0, 100, up=False),
            LinkSegment(100, 105, bandwidth_bps=8000),
        ),
    )
    recovery = calculate(simulate(trace, "fifo"))["history"]["recoveries"][0]
    assert recovery["status"] == "incomplete"
    assert recovery["completeness"] == 0
    assert recovery["recovery_time_ms"] is None


def test_lost_ack_retries_without_double_counting(message: Callable[..., Message]) -> None:
    trace = Trace(
        SimulationConfig(duration_ms=1000, ack_timeout_ms=100, retry_backoff_ms=10),
        (message("h", size=10),),
        (
            LinkSegment(0, 50, bandwidth_bps=8000, latency_ms=10, ack_loss_probability=1),
            LinkSegment(50, 1000, bandwidth_bps=8000, latency_ms=10),
        ),
    )
    result = simulate(trace, "fifo")
    metrics = calculate(result)
    assert result.entries[0].committed_ms == 20
    assert result.entries[0].acked_ms == 150
    assert metrics["remote_unique_count"] == metrics["acked_count"] == 1
    assert metrics["attempt_count"] == 2
    assert metrics["duplicate_commit_attempts"] == 1
    assert result.attempts[0].fault == "ack_loss"


def test_late_commit_and_ack_survive_timeout(message: Callable[..., Message]) -> None:
    trace = Trace(
        SimulationConfig(duration_ms=100, ack_timeout_ms=5, retry_backoff_ms=1),
        (message("h", size=1),),
        (LinkSegment(0, 100, bandwidth_bps=8000, latency_ms=20),),
    )
    result = simulate(trace, "fifo")
    assert result.entries[0].committed_ms == 21
    assert result.entries[0].acked_ms == 41
    assert len(result.attempts) > 1
    assert calculate(result)["remote_unique_count"] == 1


def test_bandwidth_change_during_serialization(message: Callable[..., Message]) -> None:
    trace = Trace(
        SimulationConfig(duration_ms=200),
        (message("h"),),
        (
            LinkSegment(0, 50, bandwidth_bps=8000, latency_ms=0),
            LinkSegment(50, 200, bandwidth_bps=16000, latency_ms=0),
        ),
    )
    assert simulate(trace, "fifo").entries[0].committed_ms == 75


@pytest.mark.parametrize("outage_start", [50, 110])
def test_outage_interrupts_serialization_or_propagation(
    outage_start: int,
    message: Callable[..., Message],
) -> None:
    trace = Trace(
        SimulationConfig(duration_ms=300, ack_timeout_ms=20, retry_backoff_ms=1),
        (message("h"),),
        (
            LinkSegment(0, outage_start, bandwidth_bps=8000, latency_ms=20),
            LinkSegment(outage_start, 200, up=False),
            LinkSegment(200, 300, bandwidth_bps=80000, latency_ms=0),
        ),
    )
    result = simulate(trace, "fifo")
    assert result.attempts[0].fault == "data_link_down"
    assert result.entries[0].committed_ms == 210


def test_total_loss_is_bounded_retry_and_no_ack(message: Callable[..., Message]) -> None:
    trace = Trace(
        SimulationConfig(duration_ms=100, ack_timeout_ms=10, retry_backoff_ms=10),
        (message("h", size=1),),
        (LinkSegment(0, 100, latency_ms=0, loss_probability=1),),
    )
    metrics = calculate(simulate(trace, "fifo"))
    assert metrics["remote_unique_count"] == metrics["acked_count"] == 0
    assert 1 < metrics["attempt_count"] < 10


def test_queue_overflow_fails_loudly(message: Callable[..., Message]) -> None:
    trace = Trace(
        SimulationConfig(duration_ms=100, queue_limit=1),
        (message("a"), message("b")),
        (LinkSegment(0, 100, up=False),),
    )
    with pytest.raises(OverflowError, match="no messages discarded"):
        simulate(trace, "fifo")


def test_priority_can_starve_history(message: Callable[..., Message]) -> None:
    messages = [message("history", size=10)] + [
        message(f"e{i}", category=Category.EVENT, size=10, deadline=100) for i in range(10)
    ]
    trace = Trace(
        SimulationConfig(duration_ms=50),
        tuple(messages),
        (LinkSegment(0, 50, bandwidth_bps=8000, latency_ms=0),),
    )
    assert simulate(trace, "priority").entries[0].acked_ms is None
    assert simulate(trace, "fifo").entries[0].acked_ms == 10


def test_outage_after_commit_loses_ack_but_preserves_remote_record(
    message: Callable[..., Message],
) -> None:
    trace = Trace(
        SimulationConfig(duration_ms=300, ack_timeout_ms=100, retry_backoff_ms=10),
        (message("h", size=10),),
        (
            LinkSegment(0, 25, bandwidth_bps=8000, latency_ms=10),
            LinkSegment(25, 100, up=False),
            LinkSegment(100, 300, bandwidth_bps=8000, latency_ms=10),
        ),
    )
    result = simulate(trace, "fifo")
    assert result.attempts[0].fault == "ack_link_down"
    assert result.entries[0].committed_ms == 20
    assert result.entries[0].acked_ms == 150
    assert calculate(result)["remote_unique_count"] == 1


def test_unobserved_live_key_is_reported_without_invented_initial_state(
    message: Callable[..., Message],
) -> None:
    trace = Trace(
        SimulationConfig(duration_ms=100),
        (message("live", category=Category.LIVE_STATE),),
        (LinkSegment(0, 100, up=False),),
    )
    aoi = calculate(simulate(trace, "fifo"))["live_aoi"]
    assert aoi["mean_ms"] is None
    assert aoi["observed_keys"] == 0
    assert aoi["unobserved_keys"] == 1


def test_history_already_acked_is_excluded_from_restore_target(
    message: Callable[..., Message],
) -> None:
    trace = Trace(
        SimulationConfig(duration_ms=100),
        (message("h", size=1),),
        (
            LinkSegment(0, 20, bandwidth_bps=8000, latency_ms=0),
            LinkSegment(20, 50, up=False),
            LinkSegment(50, 100),
        ),
    )
    recovery = calculate(simulate(trace, "fifo"))["history"]["recoveries"][0]
    assert recovery["target_count"] == 0
    assert recovery["status"] == "empty"
    assert recovery["completeness"] is None


def test_empty_workload_has_no_invented_percentages() -> None:
    trace = Trace(SimulationConfig(duration_ms=100), (), (LinkSegment(0, 100),))
    metrics = calculate(simulate(trace, "fifo"))
    assert metrics["generated_count"] == metrics["pending_count"] == 0
    assert metrics["event"]["deadline_miss_rate"] is None
    assert metrics["history"]["all_generated_completeness"] is None
