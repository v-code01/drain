#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
fail() { echo "GATE FAIL: $*" >&2; exit 1; }
if [ -x .venv/bin/ruff ]; then R=.venv/bin/ruff; M=.venv/bin/mypy; PY=.venv/bin/python; else R="python3 -m ruff"; M="python3 -m mypy"; PY=python3; fi
echo "== 1/6 ruff =="; $R check src tests tools || fail ruff; echo "   ok"
echo "== 2/6 mypy --strict =="; MYPYPATH=src $M --strict src tools/run_bench.py tools/analyze.py tools/verify.py || fail mypy; echo "   ok"
echo "== 3/6 pytest =="; $PY -m pytest -q || fail pytest
echo "== 4/6 pure-ASCII =="
bad=$(LC_ALL=C grep -rlP '[^\x00-\x7F]' src tests tools scripts manifests README.md claims.toml REVIEW.md PREREG.md bench_results docs 2>/dev/null || true)
[ -z "$bad" ] || { echo "$bad"; fail ascii; }; echo "   ok"
echo "== 5/6 no environment leak =="
pat='/Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+/'
[ -f scripts/.leakpatterns ] && pat="$pat|$(grep -vE '^\s*(#|$)' scripts/.leakpatterns | paste -sd'|' -)"
leak=$(grep -rniIE --exclude-dir=__pycache__ --exclude-dir=.venv "$pat" src tests tools manifests README.md claims.toml REVIEW.md PREREG.md reproduce.sh docs 2>/dev/null || true)
[ -z "$leak" ] || { echo "$leak"; fail "leak"; }; echo "   ok"
echo "== 6/6 analyze + independent verify =="
$PY tools/analyze.py >/dev/null || fail analyze
$PY tools/verify.py || fail verify
echo "   ok"
echo "ALL GATES PASS"
