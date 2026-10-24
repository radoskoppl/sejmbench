#!/usr/bin/env bash
# Push SejmBench to github.com/radoskoppl/sejmbench and verify origin/main == HEAD.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .git ]; then
  echo "not a git repo: $(pwd)" >&2
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin git@github.com:radoskoppl/sejmbench.git
fi

export GIT_SSH_COMMAND="ssh -i /opt/data/workspace/.ssh/id_ecdsa -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"

git push -u origin main
git fetch origin main >/dev/null

if [ "$(git rev-parse origin/main)" = "$(git rev-parse HEAD)" ]; then
  echo "VERIFY_OK: origin/main == $(git rev-parse --short HEAD)"
else
  echo "VERIFY_MISMATCH: origin/main != HEAD" >&2
  exit 1
fi
