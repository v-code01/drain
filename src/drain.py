"""Pure helpers for the pod-termination study: classify a client result as a
completed or dropped in-flight request, and aggregate completion rate and means.
No I/O."""
from __future__ import annotations


def outcome(exit_code: int, body: str) -> str:
    """A request completed iff the client exited 0 and received the `done` marker;
    a truncated, reset, or timed-out stream is a drop."""
    return "completed" if exit_code == 0 and "done" in body else "dropped"


def completion_rate(outcomes: list[str]) -> float:
    if not outcomes:
        return 0.0
    return sum(1 for o in outcomes if o == "completed") / len(outcomes)


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0
