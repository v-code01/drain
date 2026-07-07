"""Analyze results/trials.jsonl: per SIGTERM mode and grace period, the in-flight
request completion rate and the mean pod shutdown time. Writes
bench_results/frontier.md."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import drain as dr  # noqa: E402

MODES = ["none", "exit", "drain"]
GRACES = [4, 30]
SLEEP_S = 12


def _i(x: object) -> int:
    assert isinstance(x, int)
    return x


def _f(x: object) -> float:
    assert isinstance(x, (int, float))
    return float(x)


def _s(x: object) -> str:
    assert isinstance(x, str)
    return x


def load() -> list[dict[str, object]]:
    path = Path(__file__).resolve().parent.parent / "results" / "trials.jsonl"
    return [json.loads(x) for x in open(path) if x.strip()]


def main() -> int:
    rows = load()
    lines: list[str] = [
        "# drain frontier (regenerate with tools/analyze.py)",
        "#",
        f"# Request holds {SLEEP_S}s (a generation stand-in); the pod is deleted 4s in.",
        "# mode = SIGTERM behavior (none = PID-1 ignores it, exit = die immediately,",
        "# drain = finish in-flight then exit). grace = terminationGracePeriodSeconds.",
        "# completion_rate = fraction of in-flight requests that returned 'done';",
        "# shutdown_s = mean time from delete to pod gone.",
        "",
        f"sleep_s {SLEEP_S}",
    ]
    for mode in MODES:
        for grace in GRACES:
            cell = [r for r in rows if _s(r["mode"]) == mode and _i(r["grace"]) == grace]
            outcomes = [dr.outcome(_i(r["exit_code"]), _s(r["body"])) for r in cell]
            shutdowns = [_f(r["shutdown_s"]) for r in cell]
            lines.append(
                f"mode {mode} grace {grace} trials {len(cell)} "
                f"completion_rate {dr.completion_rate(outcomes):.3f} "
                f"mean_shutdown_s {dr.mean(shutdowns):.1f}")
    out = Path(__file__).resolve().parent.parent / "bench_results" / "frontier.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
