"""Independent verification of the drain findings, sharing no code with src or
analyze.py. Re-reads results/trials.jsonl, re-classifies each trial with its own
outcome rule, recomputes the per-cell completion rate and mean shutdown time, and
re-asserts:

  P1  the grace period is a hard deadline: for none and drain, completion is 100%
      when grace > sleep and 0% when grace < sleep.
  P2  exit-on-SIGTERM always drops: exit mode completion is 0% at both graces.
  P3  a no-handler PID-1 server ignores SIGTERM: none mode completes at grace > sleep
      (it survives rather than dying).
  P4  drain terminates early, no-handler lingers: at grace > sleep, drain's mean
      shutdown is near the sleep time and far below the grace, while none's is near
      the full grace period.

Exit non-zero on mismatch.
"""
from __future__ import annotations

import json
import sys

SLEEP_S = 12
SHORT, LONG = 4, 30


def _i(x: object) -> int:
    assert isinstance(x, int)
    return x


def _f(x: object) -> float:
    assert isinstance(x, (int, float))
    return float(x)


def _s(x: object) -> str:
    assert isinstance(x, str)
    return x


def completed(exit_code: int, body: str) -> bool:
    return exit_code == 0 and "done" in body


def main() -> int:
    rows: list[dict[str, object]] = [json.loads(x) for x in open("results/trials.jsonl") if x.strip()]

    def cell(mode: str, grace: int) -> list[dict[str, object]]:
        return [r for r in rows if _s(r["mode"]) == mode and _i(r["grace"]) == grace]

    def cr(mode: str, grace: int) -> float:
        c = cell(mode, grace)
        return sum(1 for r in c if completed(_i(r["exit_code"]), _s(r["body"]))) / len(c)

    def sd(mode: str, grace: int) -> float:
        c = cell(mode, grace)
        return sum(_f(r["shutdown_s"]) for r in c) / len(c)

    ok = True
    for mode in ("none", "exit", "drain"):
        for grace in (SHORT, LONG):
            print(f"  [{mode} grace={grace}s] completion {cr(mode,grace):.2f} "
                  f"mean_shutdown {sd(mode,grace):.1f}s")

    # P1: none/drain complete iff grace > sleep
    p1 = (cr("none", LONG) == 1.0 and cr("drain", LONG) == 1.0
          and cr("none", SHORT) == 0.0 and cr("drain", SHORT) == 0.0)
    print(f"  [P1] grace-as-deadline: none/drain complete at {LONG}s, drop at {SHORT}s = {p1}")
    ok = ok and p1

    # P2: exit always drops
    p2 = cr("exit", SHORT) == 0.0 and cr("exit", LONG) == 0.0
    print(f"  [P2] exit-on-SIGTERM drops at both graces = {p2}")
    ok = ok and p2

    # P3: none survives (ignores SIGTERM) at grace > sleep
    p3 = cr("none", LONG) == 1.0
    print(f"  [P3] no-handler PID-1 ignores SIGTERM (none completes at {LONG}s) = {p3}")
    ok = ok and p3

    # P4: drain exits early (~sleep), none lingers (~grace)
    p4 = sd("drain", LONG) < 0.6 * LONG and sd("none", LONG) > 0.8 * LONG
    print(f"  [P4] drain shutdown {sd('drain',LONG):.1f}s (~sleep, << {LONG}) vs none "
          f"{sd('none',LONG):.1f}s (~grace) = {p4}")
    ok = ok and p4

    if ok:
        print("VERIFY OK: an in-flight long request survives pod deletion only if it finishes "
              "within terminationGracePeriodSeconds (grace as a hard deadline); exit-on-SIGTERM "
              "always drops it; a no-handler PID-1 server ignores SIGTERM and survives to the grace "
              "period; and a drain handler exits early after finishing while no-handler lingers to "
              "SIGKILL - recomputed independently.")
        return 0
    print("VERIFY FAILED", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
