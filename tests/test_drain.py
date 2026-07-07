import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import drain as dr


def test_outcome_completed() -> None:
    assert dr.outcome(0, "done\n") == "completed"


def test_outcome_dropped_nonzero_exit() -> None:
    assert dr.outcome(28, "done\n") == "dropped"


def test_outcome_dropped_no_body() -> None:
    assert dr.outcome(0, "") == "dropped"
    assert dr.outcome(52, "") == "dropped"


def test_completion_rate() -> None:
    assert dr.completion_rate(["completed", "completed", "dropped", "dropped"]) == 0.5
    assert dr.completion_rate(["dropped", "dropped"]) == 0.0
    assert dr.completion_rate(["completed"]) == 1.0


def test_mean() -> None:
    assert dr.mean([2.0, 4.0, 6.0]) == 4.0
