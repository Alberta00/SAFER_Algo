"""Message-level metrics derived solely from simulation timestamps."""

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from safer_core.models import Category, QueueEntry

if TYPE_CHECKING:
    from safer_sim.engine import SimulationResult


def percentile(values: list[int], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def live_aoi(entries: tuple[QueueEntry, ...], end_ms: int) -> dict[str, Any]:
    keys = {e.message.state_key for e in entries if e.message.category == Category.LIVE_STATE}
    grouped: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    for entry in entries:
        m = entry.message
        if m.state_key is not None and m.sample_ms is not None and entry.committed_ms is not None:
            grouped[m.state_key].append((entry.committed_ms, entry.ordinal, m.sample_ms))
    per_key: dict[str, Any] = {}
    averages = []
    for key in sorted(grouped):
        updates = sorted(grouped[key])
        start, _, latest_sample = updates[0]
        cursor, twice_area = start, 0
        series = [{"time_ms": start, "aoi_ms": start - latest_sample}]
        for commit, _, sample in updates[1:]:
            dt = commit - cursor
            twice_area += 2 * (cursor - latest_sample) * dt + dt * dt
            latest_sample = max(latest_sample, sample)
            cursor = commit
            series.append({"time_ms": commit, "aoi_ms": commit - latest_sample})
        dt = end_ms - cursor
        twice_area += 2 * (cursor - latest_sample) * dt + dt * dt
        series.append({"time_ms": end_ms, "aoi_ms": end_ms - latest_sample})
        coverage = end_ms - start
        average = twice_area / (2 * coverage) if coverage else None
        if average is not None:
            averages.append(average)
        per_key[key] = {
            "coverage_ms": coverage,
            "coverage_fraction": coverage / end_ms,
            "area_ms2": twice_area / 2,
            "time_average_ms": average,
            "series": series,
        }
    return {
        "mean_ms": sum(averages) / len(averages) if averages else None,
        "generated_keys": len(keys),
        "observed_keys": len(grouped),
        "unobserved_keys": len(keys) - len(grouped),
        "per_key": per_key,
    }


def calculate(result: "SimulationResult") -> dict[str, Any]:
    end = result.trace.config.duration_ms
    entries = result.entries
    events = [e for e in entries if e.message.category == Category.EVENT]
    latencies = [
        e.committed_ms - e.message.created_ms for e in events if e.committed_ms is not None
    ]
    misses, censored = 0, 0
    for e in events:
        deadline = e.message.deadline_ms
        assert deadline is not None
        if e.committed_ms is not None:
            misses += e.committed_ms > deadline
        elif deadline <= end:
            misses += 1
        else:
            censored += 1
    by_id = {e.message.message_id: e for e in entries}
    recoveries = []
    for recovery in result.recoveries:
        targets = [by_id[mid] for mid in recovery.target_ids]
        acks = [e.acked_ms for e in targets if e.acked_ms is not None]
        complete = len(acks) == len(targets)
        recoveries.append(
            {
                "restored_ms": recovery.restored_ms,
                "target_ids": list(recovery.target_ids),
                "target_count": len(targets),
                "acked_count": len(acks),
                "completeness": len(acks) / len(targets) if targets else None,
                "recovery_time_ms": max(acks) - recovery.restored_ms
                if targets and complete
                else None,
                "status": "empty" if not targets else ("complete" if complete else "incomplete"),
            }
        )
    acked = [e for e in entries if e.acked_ms is not None]
    pending = [e for e in entries if e.acked_ms is None]
    history = [e for e in entries if e.message.category == Category.HISTORY]
    return {
        "generated_count": len(entries),
        "remote_unique_count": sum(e.committed_ms is not None for e in entries),
        "acked_count": len(acked),
        "pending_count": len(pending),
        "attempt_count": len(result.attempts),
        "retry_count": sum(max(0, e.attempt_count - 1) for e in entries),
        "duplicate_commit_attempts": sum(a.duplicate for a in result.attempts),
        "event": {
            "generated_count": len(events),
            "committed_count": len(latencies),
            "deadline_miss_count": misses,
            "censored_count": censored,
            "deadline_miss_rate": misses / len(events) if events else None,
            "latency_ms": {
                "mean": sum(latencies) / len(latencies) if latencies else None,
                "p50": percentile(latencies, 0.5),
                "p95": percentile(latencies, 0.95),
                "p99": percentile(latencies, 0.99),
            },
        },
        "live_aoi": live_aoi(entries, end),
        "history": {
            "generated_count": len(history),
            "acked_count": sum(e.acked_ms is not None for e in history),
            "all_generated_completeness": (
                sum(e.acked_ms is not None for e in history) / len(history) if history else None
            ),
            "recoveries": recoveries,
        },
        "acked_bytes": sum(e.message.payload_bytes for e in acked),
        "acked_bytes_per_second": sum(e.message.payload_bytes for e in acked) * 1000 / end,
        "max_wait_ms": max(
            ((e.acked_ms if e.acked_ms is not None else end) - e.queued_ms for e in entries),
            default=0,
        ),
        "oldest_pending_age_ms": max((end - e.queued_ms for e in pending), default=0),
    }
