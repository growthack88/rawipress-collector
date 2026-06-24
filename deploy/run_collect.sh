#!/bin/bash
# Wrapper launchd invokes every 15 min. Activates the venv and runs a collect.
# Edit RAWI_HOME if the project lives elsewhere on the Saudi node.
set -euo pipefail

RAWI_HOME="${RAWI_HOME:-$HOME/Documents/RawiPress}"
VENV_PY="${RAWI_HOME}/projects/venv/bin/python"

cd "$RAWI_HOME"

if [ -x "$VENV_PY" ]; then
    exec "$VENV_PY" app.py collect
else
    # fall back to whatever python3 is on PATH
    exec python3 app.py collect
fi
