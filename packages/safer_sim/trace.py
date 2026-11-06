"""Serializable immutable inputs shared by every policy."""

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from safer_core.models import Category, Message, integer

from safer_sim.config import SimulationConfig


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def variate(seed: int, attempt: int, field: str) -> float:
    raw = hashlib.sha256(f"{seed}:{attempt}:{field}".encode()).digest()
    # Exactly representable 53-bit fraction: never rounds up to 1.0.
    return (int.from_bytes(raw[:8], "big") >> 11) / 2**53


@dataclass(frozen=True)
class LinkSegment:
    start_ms: int
    end_ms: int
    up: bool = True
    bandwidth_bps: int = 2_000_000
    latency_ms: int = 40
    jitter_ms: int = 0
    loss_probability: float = 0.0
    ack_loss_probability: float = 0.0

    def __post_init__(self) -> None:
        integer("start_ms", self.start_ms)
        integer("end_ms", self.end_ms, self.start_ms + 1)
        integer("bandwidth_bps", self.bandwidth_bps, 1)
        integer("latency_ms", self.latency_ms)
        integer("jitter_ms", self.jitter_ms)
        if type(self.up) is not bool:
            raise ValueError("up must be boolean")
        for probability in (self.loss_probability, self.ack_loss_probability):
            if not 0 <= probability <= 1:
                raise ValueError("link probability must be in [0,1]")


@dataclass(frozen=True)
class Trace:
    config: SimulationConfig
    messages: tuple[Message, ...]
    links: tuple[LinkSegment, ...]

    def __post_init__(self) -> None:
        if not self.links or self.links[0].start_ms != 0:
            raise ValueError("link trace must start at 0")
        if self.links[-1].end_ms != self.config.duration_ms:
            raise ValueError("link trace must end at observation end")
        if any(a.end_ms != b.start_ms for a, b in zip(self.links, self.links[1:], strict=False)):
            raise ValueError("link segments must be contiguous and nonoverlapping")
        if len({m.message_id for m in self.messages}) != len(self.messages):
            raise ValueError("duplicate message_id in trace")
        if any(m.created_ms >= self.config.duration_ms for m in self.messages):
            raise ValueError("messages must be created before observation end")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "config": asdict(self.config),
            "messages": [asdict(m) for m in self.messages],
            "links": [asdict(link) for link in self.links],
        }

    @property
    def trace_hash(self) -> str:
        return digest(self.to_dict())

    @classmethod
    def load(cls, path: Path) -> "Trace":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("unsupported trace schema")
        messages = []
        for raw in data["messages"]:
            item = dict(raw)
            item["category"] = Category(item["category"])
            messages.append(Message(**item))
        return cls(
            SimulationConfig(**data["config"]),
            tuple(messages),
            tuple(LinkSegment(**item) for item in data["links"]),
        )


def generate_links(config: SimulationConfig) -> tuple[LinkSegment, ...]:
    end = config.duration_ms
    start = min(config.outage_start_ms, end)
    restore = min(start + config.outage_duration_ms, end)
    boundaries = {0, end}
    if config.scenario_id in ("S1", "S5"):
        boundaries.update((start, restore))
    if config.scenario_id == "S2":
        boundaries.update((end // 3, 2 * end // 3))
    if config.scenario_id == "S3":
        period = config.flap_up_ms + config.flap_down_ms
        for point in range(0, end, period):
            boundaries.update((point, min(point + config.flap_up_ms, end)))
    points = sorted(boundaries)
    links = []
    for a, b in zip(points, points[1:], strict=False):
        up = True
        bandwidth = config.bandwidth_bps
        latency, jitter, loss = config.latency_ms, config.jitter_ms, config.loss_probability
        if config.scenario_id in ("S1", "S5"):
            up = not start <= a < restore
        if config.scenario_id == "S2" and end // 3 <= a < 2 * end // 3:
            bandwidth = config.degraded_bandwidth_bps
        if config.scenario_id == "S3":
            up = a % (config.flap_up_ms + config.flap_down_ms) < config.flap_up_ms
        if config.scenario_id == "S4":
            latency, jitter, loss = max(latency, 350), max(jitter, 150), max(loss, 0.05)
        if config.scenario_id == "S6":
            bandwidth = config.degraded_bandwidth_bps
        links.append(
            LinkSegment(a, b, up, bandwidth, latency, jitter, loss, config.ack_loss_probability)
        )
    return tuple(links)


def generate_trace(config: SimulationConfig) -> Trace:
    rng = random.Random(f"workload:{config.seed}")
    messages = []
    interval = config.interval_ms
    if config.scenario_id == "S6":
        interval = min(interval, 100)  # Explicit overload workload; recorded in trace/config.
    restore = config.outage_start_ms + config.outage_duration_ms
    for created in range(0, config.duration_ms, interval):
        for device in range(config.devices):
            sequence = created // interval
            device_id = f"virtual-sensor-{device:03d}"
            burst = config.scenario_id == "S5" and restore <= created < restore + 5_000
            category = (
                Category.EVENT
                if burst or rng.random() < config.event_probability
                else (Category.LIVE_STATE if sequence % 2 == 0 else Category.HISTORY)
            )
            messages.append(
                Message(
                    message_id=str(UUID(int=rng.getrandbits(128), version=4)),
                    device_id=device_id,
                    category=category,
                    created_ms=created,
                    sequence_no=sequence,
                    payload_bytes=rng.randint(config.payload_min_bytes, config.payload_max_bytes),
                    payload_value=round(25 + rng.uniform(-5, 5), 4),
                    deadline_ms=created + config.event_allowed_delay_ms
                    if category == Category.EVENT
                    else None,
                    severity="critical" if category == Category.EVENT else None,
                    state_key=f"{device_id}/temperature"
                    if category == Category.LIVE_STATE
                    else None,
                    sample_ms=created if category == Category.LIVE_STATE else None,
                )
            )
    return Trace(config, tuple(messages), generate_links(config))
