"""Stable event heap, one-flight queue, first-commit dedup and application ACK model."""

import heapq
from bisect import bisect_right
from dataclasses import asdict, dataclass
from typing import Any

from safer_core.models import Category, QueueEntry, SchedulingContext
from safer_core.schedulers import Baseline, Scheduler

from safer_sim.trace import LinkSegment, Trace, variate


@dataclass
class Attempt:
    message_id: str
    attempt_no: int
    sent_ms: int
    serialization_end_ms: int
    commit_due_ms: int | None
    ack_due_ms: int | None
    timeout_ms: int
    fault: str | None
    committed: bool = False
    duplicate: bool = False
    acknowledged: bool = False
    timed_out: bool = False


@dataclass
class Recovery:
    restored_ms: int
    target_ids: tuple[str, ...]


@dataclass
class SimulationResult:
    trace: Trace
    algorithm: str
    entries: tuple[QueueEntry, ...]
    attempts: tuple[Attempt, ...]
    recoveries: tuple[Recovery, ...]
    series: list[dict[str, int]]

    def message_rows(self) -> list[dict[str, Any]]:
        return [
            {
                **asdict(e.message),
                "queued_ms": e.queued_ms,
                "first_sent_ms": e.first_sent_ms,
                "committed_ms": e.committed_ms,
                "acked_ms": e.acked_ms,
                "attempt_count": e.attempt_count,
                "status": "ACKED"
                if e.acked_ms is not None
                else ("IN_FLIGHT" if e.in_flight else "QUEUED"),
            }
            for e in self.entries
        ]


class LinkModel:
    def __init__(self, trace: Trace) -> None:
        self.links = trace.links
        self.starts = [s.start_ms for s in self.links]

    def at(self, time_ms: int) -> LinkSegment:
        return self.links[bisect_right(self.starts, time_ms) - 1]

    def up_between(self, start: int, end: int) -> bool:
        return all(s.up for s in self.links if s.end_ms > start and s.start_ms <= end)

    def serialize(self, start: int, payload_bytes: int) -> tuple[int, bool]:
        remaining = payload_bytes * 8_000  # bits * ms/second
        now = start
        for segment in self.links[bisect_right(self.starts, start) - 1 :]:
            if not segment.up:
                return now, False
            available = (segment.end_ms - now) * segment.bandwidth_bps
            if remaining <= available:
                duration = (remaining + segment.bandwidth_bps - 1) // segment.bandwidth_bps
                return now + max(1, duration), True
            remaining -= available
            now = segment.end_ms
        # Finish beyond observation; no scheduled completion is processed in this run.
        last = self.links[-1]
        extra = (remaining + last.bandwidth_bps - 1) // last.bandwidth_bps
        return now + max(1, extra), last.up


def simulate(trace: Trace, algorithm: str, scheduler: Scheduler | None = None) -> SimulationResult:
    return _Engine(trace, algorithm, scheduler or Baseline(algorithm)).run()


class _Engine:
    def __init__(self, trace: Trace, algorithm: str, scheduler: Scheduler) -> None:
        self.trace, self.algorithm, self.scheduler = trace, algorithm, scheduler
        self.config = trace.config
        self.link = LinkModel(trace)
        self.events: list[tuple[int, int, int, str, int]] = []
        self.event_order = 0
        self.now = 0
        self.entries: dict[str, QueueEntry] = {}
        self.attempts: list[Attempt] = []
        self.recoveries: list[Recovery] = []
        self.series: list[dict[str, int]] = []
        self.dispatch_times: set[int] = set()
        self.active: int | None = None
        self.wire_available = 0
        self.ack_ids: list[str] = []
        self.acked_bytes = 0
        for i, message in enumerate(trace.messages):
            self.schedule(message.created_ms, 1, "arrival", i)
        for i, segment in enumerate(trace.links):
            self.schedule(segment.start_ms, 0, "link", i)

    def schedule(self, time: int, phase: int, kind: str, index: int = 0) -> None:
        if time <= self.config.duration_ms:
            self.event_order += 1
            heapq.heappush(self.events, (time, phase, self.event_order, kind, index))

    def wake(self, time: int) -> None:
        if time not in self.dispatch_times and time <= self.config.duration_ms:
            self.dispatch_times.add(time)
            self.schedule(time, 5, "dispatch")

    def record(self) -> None:
        pending = [e for e in self.entries.values() if e.acked_ms is None]
        row = {
            "time_ms": self.now,
            "pending_count": len(pending),
            "pending_bytes": sum(e.message.payload_bytes for e in pending),
            "acked_bytes": self.acked_bytes,
            "oldest_pending_age_ms": max((self.now - e.queued_ms for e in pending), default=0),
        }
        if self.series and self.series[-1]["time_ms"] == self.now:
            self.series[-1] = row
        else:
            self.series.append(row)

    def run(self) -> SimulationResult:
        while self.events:
            time, _, _, kind, index = heapq.heappop(self.events)
            self.now = time
            if kind == "arrival":
                if len(self.entries) - len(self.ack_ids) >= self.config.queue_limit:
                    raise OverflowError(f"queue_limit exceeded at {time}ms; no messages discarded")
                message = self.trace.messages[index]
                self.entries[message.message_id] = QueueEntry(message, index, time)
                self.wake(time)
            elif kind == "link":
                segment = self.trace.links[index]
                if index and segment.up and not self.trace.links[index - 1].up:
                    target = tuple(
                        e.message.message_id
                        for e in self.entries.values()
                        if e.message.category == Category.HISTORY
                        and e.message.created_ms < time
                        and e.acked_ms is None
                    )
                    self.recoveries.append(Recovery(time, target))
                self.wake(time)
            elif kind == "dispatch":
                self.dispatch_times.remove(time)
                self.dispatch()
            elif kind == "commit":
                attempt = self.attempts[index]
                entry = self.entries[attempt.message_id]
                attempt.committed = True
                attempt.duplicate = entry.committed_ms is not None
                if entry.committed_ms is None:
                    entry.committed_ms = time
            elif kind == "ack":
                attempt = self.attempts[index]
                entry = self.entries[attempt.message_id]
                attempt.acknowledged = True
                if entry.acked_ms is None:
                    if entry.committed_ms is None:
                        raise AssertionError("ACK before commit")
                    entry.acked_ms = time
                    self.ack_ids.append(attempt.message_id)
                    self.acked_bytes += entry.message.payload_bytes
                if self.active is not None and (
                    self.attempts[self.active].message_id == attempt.message_id
                ):
                    self.active = None
                    entry.in_flight = False
                self.wake(max(time, self.wire_available))
            elif kind == "timeout":
                attempt = self.attempts[index]
                entry = self.entries[attempt.message_id]
                if not attempt.acknowledged:
                    attempt.timed_out = True
                if self.active == index:
                    self.active = None
                    entry.in_flight = False
                    if entry.acked_ms is None:
                        backoff = min(
                            self.config.retry_backoff_cap_ms,
                            self.config.retry_backoff_ms * 2 ** min(30, entry.attempt_count - 1),
                        )
                        entry.next_attempt_ms = time + backoff
                        self.wake(entry.next_attempt_ms)
                    self.wake(max(time, self.wire_available))
            self.record()
        self.now = self.config.duration_ms
        self.record()
        return SimulationResult(
            self.trace,
            self.algorithm,
            tuple(self.entries.values()),
            tuple(self.attempts),
            tuple(self.recoveries),
            self.series,
        )

    def dispatch(self) -> None:
        if self.active is not None or self.now >= self.config.duration_ms:
            return
        if self.now < self.wire_available:
            self.wake(self.wire_available)
            return
        segment = self.link.at(self.now)
        if not segment.up:
            return
        pending = tuple(e for e in self.entries.values() if e.acked_ms is None)
        context = SchedulingContext(
            pending,
            self.now,
            segment.bandwidth_bps,
            segment.bandwidth_bps // 8,
            tuple(self.ack_ids[-16:]),
        )
        selected = self.scheduler.select_next(context)
        if selected is None:
            return
        entry = self.entries.get(selected)
        if entry is None or not entry.eligible(self.now):
            raise ValueError("scheduler selected an unknown or ineligible message")
        entry.attempt_count += 1
        entry.in_flight = True
        if entry.first_sent_ms is None:
            entry.first_sent_ms = self.now
        serial_end, serialized = self.link.serialize(self.now, entry.message.payload_bytes)
        self.wire_available = serial_end
        ordinal = len(self.attempts)
        jitter = int((2 * variate(self.config.seed, ordinal, "jitter") - 1) * segment.jitter_ms)
        delay = max(0, segment.latency_ms + jitter)
        commit_due = serial_end + delay
        ack_due = commit_due + delay
        fault: str | None = None
        if not serialized or not self.link.up_between(self.now, commit_due):
            fault = "data_link_down"
        elif variate(self.config.seed, ordinal, "data_loss") < segment.loss_probability:
            fault = "data_loss"
        commit: int | None = commit_due if fault is None else None
        ack: int | None = ack_due if fault is None else None
        if ack is not None:
            if not self.link.up_between(commit_due, ack_due):
                fault, ack = "ack_link_down", None
            elif variate(self.config.seed, ordinal, "ack_loss") < segment.ack_loss_probability:
                fault, ack = "ack_loss", None
        timeout = serial_end + self.config.ack_timeout_ms
        attempt = Attempt(
            selected, entry.attempt_count, self.now, serial_end, commit, ack, timeout, fault
        )
        self.attempts.append(attempt)
        self.active = ordinal
        if commit is not None:
            self.schedule(commit, 2, "commit", ordinal)
        if ack is not None:
            self.schedule(ack, 3, "ack", ordinal)
        self.schedule(timeout, 4, "timeout", ordinal)
