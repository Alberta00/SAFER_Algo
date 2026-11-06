from dataclasses import dataclass
from math import isfinite

from safer_core.models import integer

SCENARIOS = ("S0", "S1", "S2", "S3", "S4", "S5", "S6")


@dataclass(frozen=True)
class SimulationConfig:
    scenario_id: str = "S0"
    seed: int = 42
    duration_ms: int = 720_000
    devices: int = 10
    interval_ms: int = 5_000
    event_probability: float = 0.1
    event_allowed_delay_ms: int = 5_000
    payload_min_bytes: int = 128
    payload_max_bytes: int = 512
    bandwidth_bps: int = 2_000_000
    degraded_bandwidth_bps: int = 128_000
    latency_ms: int = 40
    jitter_ms: int = 0
    loss_probability: float = 0.0
    ack_loss_probability: float = 0.0
    outage_start_ms: int = 10_000
    outage_duration_ms: int = 600_000
    flap_up_ms: int = 30_000
    flap_down_ms: int = 15_000
    ack_timeout_ms: int = 2_000
    retry_backoff_ms: int = 250
    retry_backoff_cap_ms: int = 8_000
    queue_limit: int = 1_000_000
    max_in_flight: int = 1

    def __post_init__(self) -> None:
        if self.scenario_id not in SCENARIOS:
            raise ValueError(f"scenario_id must be one of {SCENARIOS}")
        integer("seed", self.seed)
        for name in (
            "duration_ms",
            "devices",
            "interval_ms",
            "event_allowed_delay_ms",
            "payload_min_bytes",
            "payload_max_bytes",
            "bandwidth_bps",
            "degraded_bandwidth_bps",
            "flap_up_ms",
            "flap_down_ms",
            "ack_timeout_ms",
            "retry_backoff_ms",
            "retry_backoff_cap_ms",
            "queue_limit",
        ):
            integer(name, getattr(self, name), 1)
        for name in ("latency_ms", "jitter_ms", "outage_start_ms", "outage_duration_ms"):
            integer(name, getattr(self, name))
        for name in ("event_probability", "loss_probability", "ack_loss_probability"):
            value = getattr(self, name)
            if not isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be finite in [0, 1]")
        if self.payload_min_bytes > self.payload_max_bytes:
            raise ValueError("payload_min_bytes must be <= payload_max_bytes")
        if self.retry_backoff_cap_ms < self.retry_backoff_ms:
            raise ValueError("retry cap must be >= initial backoff")
        if type(self.max_in_flight) is not int or self.max_in_flight != 1:
            raise ValueError("M1 supports exactly one in-flight request")
