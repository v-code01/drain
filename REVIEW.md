# Adversarial review: drain

A skeptic's pass over the claims, and why each survives.

## "Graceful shutdown is well documented - this is just SIGTERM 101."
The SIGTERM/grace mechanism is documented; the three things this measures are
routinely gotten backwards. That the grace period is a *hard deadline* on
generation length (a 12 s request dies at a 4 s grace), that a no-handler server
*ignores* SIGTERM as PID 1 rather than dying, and that the popular "exit on
SIGTERM" handler is the one pattern that always drops the request - are a
concrete, measured matrix, not folklore. Each contradicts a common assumption.

## "A fixed sleep is not a real generation."
It is a faithful stand-in for what matters here: a request that holds a connection
open for T seconds of server-side work. The pod-termination machinery -
SIGTERM, `terminationGracePeriodSeconds`, SIGKILL - does not know or care whether
those seconds are a token loop or a sleep; it kills the process at the deadline
either way. A real model would only add noise (variable generation length); the
sleep isolates the deadline behavior cleanly.

## "The PID-1 claim could be a Python quirk, not a kernel one."
It is the kernel's PID-1 special-casing: the kernel delivers a signal to PID 1
only if the process installed a handler for it, so an unhandled SIGTERM to PID 1
is dropped. This is why the `none` server (python as PID 1, no handler) survives
SIGTERM while the `exit` server (same python, a handler that exits) dies - same
runtime, opposite outcome, isolating the handler as the variable. Any language run
as PID 1 without an init wrapper behaves the same.

## "3 trials per cell is thin."
The completion outcome is deterministic - every cell is 0.00 or 1.00, not a rate
near a threshold - so 3 trials is confirmation, not estimation. The trials exist
mainly to guard against pod-lifecycle flakiness, which an early run exposed (a
stray request served by a replacement pod, provable because a 12 s request
"completed" in 1.2 s); the shipped runner targets the pod IP directly and waits
for exactly one Ready pod, and the re-run is clean across all 18 trials.

## "You changed the method after seeing a bad result - that is p-hacking."
The opposite: an early run had one physically-impossible data point (a 12 s
request completing in 1.2 s), which proved the request was served by a different
pod than the one deleted - a measurement bug, not a real outcome. Fixing the
measurement (target the exact pod, ensure a single Ready pod) and disclosing it is
correcting an artifact, not tuning for a result. The corrected matrix is fully
deterministic and matches the pre-registered predictions.

## "Single-node minikube is not representative."
The SIGTERM/grace/SIGKILL lifecycle and PID-1 signal handling are kubelet and
kernel behaviors identical on any node; node count does not enter them. Multi-node
would matter for scheduling and disruption budgets, which are out of scope.

## "verify.py just echoes analyze.py."
verify.py re-reads results/trials.jsonl, re-classifies each trial's outcome and
recomputes the completion rates and shutdown times with its own logic, sharing no
code with analyze.py or src. It asserts P1-P4 and exits non-zero on mismatch.

## Pre-registration honesty
All four predictions were committed before the run and all held; P1 (grace as
deadline) and P3 (the PID-1 footgun) were named the headline up front. Results,
including the disclosed early-run artifact and its fix, are reported as-is.
