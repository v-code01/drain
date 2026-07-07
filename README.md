# drain: does an in-flight generation survive a pod deletion?

Pods are deleted constantly - rolling updates, scale-down, node drains. When it
happens Kubernetes sends SIGTERM to the container's PID 1, waits
`terminationGracePeriodSeconds`, then SIGKILL. For a millisecond request this is
invisible; for an LLM server 12-60 seconds into a generation it is the difference
between a clean completion and a truncated, dropped response. This measures what
actually happens to an in-flight long request on a real cluster, across three
SIGTERM behaviors and two grace periods - and surfaces two footguns that most
people get backwards.

Real single-node Kubernetes (minikube). A server whose handler holds a request
open for T = 12 s (a generation stand-in) then returns `done`; the client targets
the pod's IP directly so its request is served by exactly the pod we delete.

## Pre-registration

Four predictions were committed to git (`PREREG.md`) before the run: (P1) the
grace period is a hard deadline; (P2) exit-on-SIGTERM always drops the request;
(P3) a no-handler PID-1 server ignores SIGTERM; (P4) a drain handler terminates
early while a no-handler server lingers. **All four held.**

## Results

Request holds T = 12 s; the pod is deleted 4 s in. 3 trials per cell.

```
  SIGTERM mode            grace = 4 s  (< T)     grace = 30 s (> T)
                          outcome  shutdown      outcome  shutdown
  none  (no handler)      DROPPED   5.1 s        COMPLETED  31.4 s
  exit  (die on SIGTERM)  DROPPED   1.1 s        DROPPED     1.0 s
  drain (finish then exit) DROPPED  5.0 s        COMPLETED   9.0 s
```

(Outcome = did the client receive `done`; completion rate was 0.00 or 1.00 in
every cell - the mechanism is deterministic. Shutdown = time from delete to the
pod disappearing.)

1. **The grace period is a hard deadline on generation length. (P1, held - the
   headline.)** For the modes that do not die on SIGTERM (none, drain), the 12 s
   request completes when the grace period is 30 s (> 12) and is **killed
   mid-stream when the grace period is 4 s (< 12)** - SIGKILL fires at grace expiry
   regardless of how gracefully the server tries to shut down. To serve a
   generation of length T you must set `terminationGracePeriodSeconds > T`; the
   default is 30 s, and long generations exceed it.

2. **"Handle SIGTERM by exiting" drops every in-flight request. (P2, held.)** The
   exit mode - a handler that calls `exit()` on SIGTERM, an extremely common
   pattern - drops the request at *both* grace periods (it dies the instant SIGTERM
   arrives, shutdown ~1 s). A longer grace period does not help; the server threw
   the request away immediately. This is the opposite of graceful.

3. **A no-handler server ignores SIGTERM - the PID-1 footgun. (P3, held.)** The
   `none` server has no SIGTERM handler, and most people assume that means it dies
   on SIGTERM. It does not: as **PID 1 in the container, the kernel does not apply
   the default signal disposition**, so unhandled SIGTERM is *ignored*. The server
   survives, finishes the request (completed at grace 30 s), and is only stopped by
   SIGKILL at grace expiry. "No signal handling" behaves like "ignore SIGTERM,"
   not "exit on SIGTERM" - the reverse of the exit mode.

4. **Drain terminates early; no-handler lingers to SIGKILL. (P4, held.)** With a
   30 s grace period, the drain server exits **9.0 s** after delete (~8 s of request
   left after the 4 s delete, plus ~1 s to observe the pod gone - it drained then
   quit), while the none server lingers the
   **full 31 s** until SIGKILL (it never exits on its own). Both complete the
   request, but only the drain handler is a good citizen: it frees the pod as soon
   as its work is done instead of holding the slot for the whole grace period.

## The one-line finding

On a real cluster an in-flight generation survives pod deletion **only if it
finishes within `terminationGracePeriodSeconds`** (a 12 s request dies at a 4 s
grace, completes at 30 s); "handle SIGTERM by exiting" drops it instantly; a
server with no handler counterintuitively *ignores* SIGTERM because it is PID 1 and
survives to the grace deadline; and only a real drain handler both completes the
request and releases the pod early - so serving long generations requires a grace
period longer than the longest generation plus an actual drain, not the naive
"exit on SIGTERM."

## Reproduce

```
./reproduce.sh     # analyze + independently verify from committed trials (no cluster)
```

`results/trials.jsonl` records each trial's client exit code, body, and pod
shutdown time. `tools/verify.py` re-reads it, re-classifies each outcome and
recomputes the completion rates and shutdown times with its own logic (no shared
code with `src` or `analyze.py`), and re-asserts every prediction. To regenerate on
a real cluster: `python tools/run_bench.py` with kubectl pointed at a running
cluster (see `manifests/`).

## Limitations and falsifiers

- One cluster (minikube, single node), a fixed sleep as a generation stand-in (not
  a real model), one client, 3 trials per cell. The completion outcomes are
  deterministic (0.00/1.00 in every cell); the trials guard against pod-lifecycle
  races (the request targets the pod's IP directly and each trial waits for exactly
  one Ready pod, after an early run showed a stray request served by a replacement
  pod during recreation).
- This isolates the SIGTERM / grace-period / drain interaction; it is not a
  rolling-update, PodDisruptionBudget, or streaming-response study.
- Protocol note: the pre-registration says the pod is deleted 2 s into the request;
  the run deletes at 4 s (still well inside the 12 s handler). The change is
  immaterial - every prediction depends only on the request being in-flight when
  the pod is deleted, which holds for any delay in (0, 12) s - but is disclosed for
  completeness.
- **Falsifier (did not fire):** had the grace period not been a hard deadline, the
  12 s request would survive at a 4 s grace; instead it is SIGKILLed. Had PID 1 not
  ignored SIGTERM, the no-handler server would drop the request like the exit mode;
  instead it completes.

MIT licensed. Outcome is the client's own curl exit and body; all counts are exact.
No LLM judgement.
