#!/bin/bash
# One-command deploy of the Rawi Press collector to the Saudi node.
#
#   bash deploy/deploy.sh
#
# What it does:
#   1. (first run) sets up an SSH key so future deploys need no password
#   2. rsyncs the code to saudi:~/Documents/RawiPress  (never touches the
#      node's data/, logs/, or projects/venv)
#   3. runs a remote smoke test: `python app.py collect` then `status`
#
# You may be prompted for the node password the FIRST time (for key setup).
# After that it's passwordless.
set -euo pipefail

HOST="${RAWI_HOST:-saudi}"                       # ssh alias from ~/.ssh/config
REMOTE_DIR="${RAWI_REMOTE_DIR:-Documents/RawiPress}"   # relative to remote $HOME
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Local : $LOCAL_DIR"
echo "==> Remote: $HOST:~/$REMOTE_DIR"

# 1. Ensure an SSH key exists and is installed on the node (idempotent).
if ! ssh -o BatchMode=yes -o ConnectTimeout=8 "$HOST" 'true' 2>/dev/null; then
    echo "==> No passwordless SSH yet — setting up a key (enter node password once)."
    [ -f "$HOME/.ssh/id_ed25519" ] || ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519"
    ssh-copy-id -i "$HOME/.ssh/id_ed25519.pub" "$HOST"
fi

# 2. Sync code. Excludes keep machine-local state on the node intact.
echo "==> Syncing code..."
rsync -az --human-readable \
    --exclude '.git' \
    --exclude '.venv' \
    --exclude 'projects' \
    --exclude 'data' \
    --exclude 'logs' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.DS_Store' \
    "$LOCAL_DIR"/ "$HOST:$REMOTE_DIR/"

# 3. Remote smoke test using the node's venv (falls back to python3).
#    dry-run (no POST) so deploys never push partial/test data — proves the
#    config loads and fetch+map works inside KSA. Run `app.py collect` manually
#    (or let launchd do it) once you're happy.
echo "==> Remote smoke test (list + dry-run, no POST)..."
ssh "$HOST" "bash -lc '
    set -e
    cd ~/$REMOTE_DIR
    PY=\$([ -x projects/venv/bin/python ] && echo projects/venv/bin/python || \
          { [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3; })
    echo \"using \$PY\"
    \$PY app.py list
    echo
    \$PY app.py dry-run arabnews >/dev/null && echo \"dry-run OK\"
'"

echo
echo "==> Done. To enable the 15-min schedule on the node, see deploy/com.rawipress.collector.plist"
