# Pre-registration: drain

Committed to git BEFORE the benchmark is run. Not edited afterward.

## What is measured

On a real single-node Kubernetes cluster (minikube), a server whose handler holds
a request open for T = 12 s (a long-generation stand-in) then responds `done`,
under three SIGTERM behaviors set by MODE: none (no handler; as PID 1 this ignores
SIGTERM), exit (handler exits immediately), drain (handler lets the in-flight
request finish then exits). For each MODE and each terminationGracePeriodSeconds G
in {4 s (< T), 30 s (> T)}, over several trials: start a request, wait 2 s, delete
the pod with grace G, and record the outcome (completed = client received `done`
with exit 0; else dropped) and the shutdown time (delete to pod gone).

## Predictions

**P1 - the grace period is a hard deadline.** For none and drain, the in-flight
request completes iff G > T and is dropped (SIGKILLed at grace expiry) when G < T.
*Falsifier:* a request survives with G < T, or is dropped with G > T, under
none/drain.

**P2 - exit-on-SIGTERM always drops.** The exit mode drops the in-flight request at
both grace periods. *Falsifier:* the exit mode ever completes the in-flight request.

**P3 - a no-handler PID-1 server ignores SIGTERM.** The none mode does not drop
immediately; with G > T it completes the request, demonstrating PID 1 ignores
unhandled SIGTERM. *Falsifier:* the none mode drops immediately like exit at G > T.

**P4 - drain terminates early, no-handler lingers.** With G > T, drain's pod
shutdown time is ~T (exits right after the request), far below the grace period,
while none lingers close to the full grace period. *Falsifier:* drain shutdown is
close to the grace period, or none shutdown is close to T.

## Commitment

P1 (the grace period is the deadline for a generation) and P3 (the PID-1
ignore-SIGTERM footgun) are the headline. Results are reported as-is, including any
falsified prediction.
