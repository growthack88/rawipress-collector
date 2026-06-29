#!/bin/bash
# Wrapper launchd invokes every 15 min. Activates the venv and runs a collect.
# Edit RAWI_HOME if the project lives elsewhere on the Saudi node.
set -euo pipefail

RAWI_HOME="${RAWI_HOME:-$HOME/Documents/RawiPress}"
cd "$RAWI_HOME"

# Prefer a project venv (projects/venv on the node, or a local .venv), else PATH.
if [ -x "${RAWI_HOME}/projects/venv/bin/python" ]; then
    PY="${RAWI_HOME}/projects/venv/bin/python"
elif [ -x "${RAWI_HOME}/.venv/bin/python" ]; then
    PY="${RAWI_HOME}/.venv/bin/python"
else
    PY="python3"
fi

# Secrets come from .env (loaded by core/env.py). `collect` = news + social once.
exec "$PY" app.py collect
