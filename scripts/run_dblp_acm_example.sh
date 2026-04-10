#!/usr/bin/env bash
# Example: run bibliographic pipeline from repository root with a YAML profile.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-python2}"
CONFIG="${ROOT}/config/examples/dblp-acm1.yaml"
exec "${PY}" "${ROOT}/RELATER/run_relater.py" --config "${CONFIG}"
