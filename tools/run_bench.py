"""Drive a real Kubernetes cluster to measure in-flight request survival on pod
termination. For each SIGTERM MODE and grace period, starts a long request, deletes
the pod mid-request, and records whether the client's request completed or was
dropped, plus the pod shutdown time. Writes results/trials.jsonl.

kubectl uses the current context/namespace; nothing operating-environment-specific
is in this file.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

MODES = ["none", "exit", "drain"]
GRACES = [4, 30]      # seconds; SLEEP_S = 12, so 4 < T < 30
TRIALS = 3
SLEEP_S = 12
DELETE_AFTER = 4.0    # start the request, wait this long (< SLEEP_S), then delete
ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "manifests" / "drain.yaml"


def kubectl(*args: str, timeout: int = 180, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["kubectl", *args], capture_output=True, text=True,
                          timeout=timeout, check=check)


def running_pods() -> list[tuple[str, str]]:
    """(name, podIP) for every Ready+Running drain pod with an assigned IP."""
    out = kubectl("get", "pods", "-l", "app=drain",
                  "--field-selector=status.phase=Running",
                  "-o", "jsonpath={range .items[?(@.status.containerStatuses[0].ready)]}"
                  "{.metadata.name} {.status.podIP}\n{end}").stdout
    return [(p[0], p[1]) for ln in out.splitlines() if len(p := ln.split()) == 2]


def wait_fresh_pod() -> tuple[str, str]:
    # rollout status guarantees the new ReplicaSet is fully available; then wait for
    # exactly one Ready Running pod (no terminating leftover a stray request could
    # hit), which also avoids kubectl-wait matching a terminating pod during rollout.
    kubectl("rollout", "status", "deployment/drain", "--timeout=120s", timeout=140)
    for _ in range(120):
        pods = running_pods()
        if len(pods) == 1:
            time.sleep(1)
            return pods[0]
        time.sleep(1)
    raise RuntimeError("no single fresh pod became ready")


def main() -> int:
    print("applying manifest...")
    kubectl("apply", "-f", str(MANIFEST))
    kubectl("wait", "--for=condition=ready", "pod/loadcli", "--timeout=180s", timeout=200)

    rows: list[dict[str, object]] = []
    for mode in MODES:
        kubectl("set", "env", "deployment/drain", f"MODE={mode}", f"SLEEP_S={SLEEP_S}")
        wait_fresh_pod()
        for grace in GRACES:
            for trial in range(TRIALS):
                pod, ip = wait_fresh_pod()
                # start the long request in the background, targeting the pod's IP
                # directly so it is served by exactly the pod we delete
                client = subprocess.Popen(
                    ["kubectl", "exec", "loadcli", "--", "sh", "-c",
                     f"curl -s -m 45 http://{ip}:7070/; echo \"EXIT:$?\""],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
                time.sleep(DELETE_AFTER)
                t0 = time.perf_counter()
                kubectl("delete", "pod", pod, f"--grace-period={grace}", "--wait=false")
                # poll until the pod is gone
                while kubectl("get", "pod", pod, check=False, timeout=20).returncode == 0:
                    time.sleep(0.5)
                shutdown_s = time.perf_counter() - t0
                out, _ = client.communicate(timeout=60)
                body, _, tail = out.rpartition("EXIT:")
                exit_code = int(tail.strip() or "1")
                rows.append({"mode": mode, "grace": grace, "trial": trial,
                             "exit_code": exit_code, "body": body.strip(),
                             "shutdown_s": round(shutdown_s, 2)})
                print(f"  mode={mode} grace={grace}s trial={trial}: "
                      f"exit={exit_code} shutdown={shutdown_s:.1f}s "
                      f"body={'done' if 'done' in body else '(none)'}")

    out_path = ROOT / "results" / "trials.jsonl"
    with open(out_path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(rows)} rows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
