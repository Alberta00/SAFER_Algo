from dataclasses import asdict

import pytest
from safer_core.models import Category, Message


@pytest.mark.parametrize(
    "change",
    [
        {"message_id": ""},
        {"category": "INVALID"},
        {"created_ms": -1},
        {"payload_bytes": 0},
        {"payload_value": float("inf")},
        {"category": Category.EVENT},
        {"category": Category.EVENT, "severity": "critical", "deadline_ms": -1},
        {"category": Category.LIVE_STATE},
        {"category": Category.LIVE_STATE, "state_key": "x", "sample_ms": 1},
        {"deadline_ms": 100},
        {"state_key": "x"},
    ],
)
def test_invalid_message_rejected(change: dict[str, object]) -> None:
    base = asdict(Message("id", "device", Category.HISTORY, 0, 0, 1))
    with pytest.raises(ValueError):
        Message(**{**base, **change})
