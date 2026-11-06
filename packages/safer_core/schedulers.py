"""Only the selection policy varies; eligibility/transport belong to the engine."""

from typing import Protocol

from safer_core.models import Category, QueueEntry, SchedulingContext


class Scheduler(Protocol):
    def select_next(self, context: SchedulingContext) -> str | None: ...


class Baseline:
    def __init__(self, algorithm: str) -> None:
        if algorithm not in ("fifo", "priority", "edf"):
            raise ValueError(f"Unknown algorithm: {algorithm}")
        self.algorithm = algorithm

    def select_next(self, context: SchedulingContext) -> str | None:
        candidates = [e for e in context.pending if e.eligible(context.now_ms)]
        if context.link_capacity_bps <= 0 or not candidates:
            return None

        def key(entry: QueueEntry) -> tuple[float, int, int]:
            message = entry.message
            rank: float = 0
            if self.algorithm == "priority":
                rank = {
                    Category.EVENT: 0,
                    Category.LIVE_STATE: 1,
                    Category.HISTORY: 2,
                }[message.category]
            elif self.algorithm == "edf":
                rank = (
                    float(message.deadline_ms) if message.deadline_ms is not None else float("inf")
                )
            return rank, entry.queued_ms, entry.ordinal

        return min(candidates, key=key).message.message_id
