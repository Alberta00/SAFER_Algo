from collections.abc import Callable

import pytest
from safer_core.models import Category, Message, QueueEntry, SchedulingContext
from safer_core.schedulers import Baseline


def context(messages: list[Message]) -> SchedulingContext:
    return SchedulingContext(
        tuple(QueueEntry(m, i, m.created_ms) for i, m in enumerate(messages)), 100, 8000, 1000
    )


def test_baseline_order_and_ties(message: Callable[..., Message]) -> None:
    messages = [
        message("history"),
        message("live", category=Category.LIVE_STATE),
        message("late", category=Category.EVENT, deadline=90),
        message("early", category=Category.EVENT, deadline=10),
    ]
    ctx = context(messages)
    assert Baseline("fifo").select_next(ctx) == "history"
    assert Baseline("priority").select_next(ctx) == "late"
    assert Baseline("edf").select_next(ctx) == "early"
    assert Baseline("edf").select_next(context(messages[:2])) == "history"


@pytest.mark.parametrize("algorithm", ["fifo", "priority", "edf"])
def test_common_eligibility(algorithm: str, message: Callable[..., Message]) -> None:
    ctx = context([message("first"), message("second")])
    ctx.pending[0].next_attempt_ms = 101
    assert Baseline(algorithm).select_next(ctx) == "second"
    ctx.pending[1].in_flight = True
    assert Baseline(algorithm).select_next(ctx) is None


def test_no_capacity(message: Callable[..., Message]) -> None:
    ctx = SchedulingContext((QueueEntry(message("h"), 0, 0),), 0, 0, 0)
    assert Baseline("fifo").select_next(ctx) is None
