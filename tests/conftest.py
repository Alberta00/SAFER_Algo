from collections.abc import Callable

import pytest
from safer_core.models import Category, Message


@pytest.fixture
def message() -> Callable[..., Message]:
    def make(
        mid: str,
        created: int = 0,
        category: Category = Category.HISTORY,
        size: int = 100,
        deadline: int | None = None,
        sample: int | None = None,
        key: str = "sensor/temperature",
    ) -> Message:
        return Message(
            mid,
            "sensor",
            category,
            created,
            0,
            size,
            deadline_ms=deadline if category == Category.EVENT else None,
            severity="critical" if category == Category.EVENT else None,
            state_key=key if category == Category.LIVE_STATE else None,
            sample_ms=(created if sample is None else sample)
            if category == Category.LIVE_STATE
            else None,
        )

    return make
