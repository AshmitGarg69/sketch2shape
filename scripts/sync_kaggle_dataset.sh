#!/usr/bin/env bash
# Upload the current source tree as a new version of the private Kaggle dataset used by the kernels.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
rsync -a --exclude .git --exclude .venv --exclude .venv_gpu --exclude outputs_local --exclude kaggle_out --exclude third_party --exclude envs/triposr --exclude envs/instantmesh --exclude __pycache__ \
      --exclude .pytest_cache --exclude outputs --exclude weights --exclude 'kaggle_out*' "$ROOT/" "$STAGE/sketch2shape/"
echo '{"title": "sketch2shape-src", "id": "ashmitgarg69/sketch2shape-src", "licenses": [{"name": "other"}]}' > "$STAGE/dataset-metadata.json"
KAGGLE=${KAGGLE:-$(command -v kaggle || echo $ROOT/.venv_tools/bin/kaggle)}
$KAGGLE datasets version -p "$STAGE" -m "${1:-sync}" --dir-mode zip -q
for i in $(seq 1 20); do s=$($KAGGLE datasets status ashmitgarg69/sketch2shape-src 2>&1); [[ "$s" == *ready* ]] && break; sleep 10; done
echo "dataset: $s"; du -sh "$STAGE" | cut -f1 | sed "s/^/staged size: /"
