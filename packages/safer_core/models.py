"""Infrastructure-free message and scheduling contracts. Time is integer milliseconds."""

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite


class Category(StrEnum):
    EVENT = "EVENT"
    LIVE_STATE = "LIVE_STATE"
    HISTORY = "HISTORY"


def integer(name: str, value: int, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


@dataclass(frozen=True)
class Message:
    message_id: str
    device_id: str
    category: Category
    created_ms: int
    sequence_no: int
    payload_bytes: int
    payload_value: float = 0.0
    deadline_ms: int | None = None
    severity: str | None = None
    state_key: str | None = None
    sample_ms: int | None = None

    def __post_init__(self) -> None:
        if not self.message_id or not self.device_id or not isinstance(self.category, Category):
            raise ValueError("message_id, device_id and a valid Category are required")
        for name in ("created_ms", "sequence_no"):
            integer(name, getattr(self, name))
        integer("payload_bytes", self.payload_bytes, 1)
        if not isfinite(self.payload_value):
            raise ValueError("payload_value must be finite")
        if self.category == Category.EVENT:
            if self.deadline_ms is None or self.severity not in ("info", "warning", "critical"):
                raise ValueError("EVENT requires deadline_ms and severity")
            integer("deadline_ms", self.deadline_ms, self.created_ms)
        elif self.deadline_ms is not None or self.severity is not None:
            raise ValueError("event metadata is only allowed on EVENT")
        if self.category == Category.LIVE_STATE:
            if not self.state_key or self.sample_ms is None:
                raise ValueError("LIVE_STATE requires state_key and sample_ms")
            integer("sample_ms", self.sample_ms)
            if self.sample_ms > self.created_ms:
                raise ValueError("sample_ms cannot be after creation")
        elif self.state_key is not None or self.sample_ms is not None:
            raise ValueError("live metadata is only allowed on LIVE_STATE")


@dataclass
class QueueEntry:
    message: Message
    ordinal: int
    queued_ms: int
    attempt_count: int = 0
    next_attempt_ms: int = 0
    first_sent_ms: int | None = None
    committed_ms: int | None = None
    acked_ms: int | None = None
    in_flight: bool = False

    def eligible(self, now_ms: int) -> bool:
        return self.acked_ms is None and not self.in_flight and self.next_attempt_ms <= now_ms


@dataclass(frozen=True)
class SchedulingContext:
    pending: tuple[QueueEntry, ...]
    now_ms: int
    link_capacity_bps: int
    available_bytes: int
    recent_ack_ids: tuple[str, ...] = ()
    fairness_state: dict[str, float] = field(default_factory=dict)
    configuration: dict[str, float] = field(default_factory=dict)
