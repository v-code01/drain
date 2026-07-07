# drain frontier (regenerate with tools/analyze.py)
#
# Request holds 12s (a generation stand-in); the pod is deleted 4s in.
# mode = SIGTERM behavior (none = PID-1 ignores it, exit = die immediately,
# drain = finish in-flight then exit). grace = terminationGracePeriodSeconds.
# completion_rate = fraction of in-flight requests that returned 'done';
# shutdown_s = mean time from delete to pod gone.

sleep_s 12
mode none grace 4 trials 3 completion_rate 0.000 mean_shutdown_s 5.1
mode none grace 30 trials 3 completion_rate 1.000 mean_shutdown_s 31.4
mode exit grace 4 trials 3 completion_rate 0.000 mean_shutdown_s 1.1
mode exit grace 30 trials 3 completion_rate 0.000 mean_shutdown_s 1.0
mode drain grace 4 trials 3 completion_rate 0.000 mean_shutdown_s 5.0
mode drain grace 30 trials 3 completion_rate 1.000 mean_shutdown_s 9.0
