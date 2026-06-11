#!/bin/bash
set -e

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    exit 1
fi

PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON_BIN" ]; then
  apt-get update
  apt-get install -y python3 python3-pip python3-venv
  PYTHON_BIN="$(command -v python3 || command -v python || true)"
fi
if [ -z "$PYTHON_BIN" ]; then
  echo "Error: neither python3 nor python is available after install."
  echo 0 > /logs/verifier/reward.txt
  exit 1
fi

VENV_DIR="/tmp/htd-pytest-venv"
if "$PYTHON_BIN" -m venv "$VENV_DIR"; then
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  PYTHON_BIN="$VENV_DIR/bin/python"
fi

"$PYTHON_BIN" -m pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

set +e
"$PYTHON_BIN" -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
pytest_status=$?
set -e

if [ "$pytest_status" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
exit "$pytest_status"
