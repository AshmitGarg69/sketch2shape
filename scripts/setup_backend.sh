#!/usr/bin/env bash
# Build one isolated env per backend (spec §7.1).  Usage: scripts/setup_backend.sh <name> [ENV_ROOT]
# Writes <ENV_ROOT>/<name>.build.json with build seconds and env size.
set -euo pipefail
NAME=$1; ROOT=$(cd "$(dirname "$0")/.." && pwd); ENV_ROOT=${2:-$ROOT/envs}
declare -A REPO=([triposr]=https://github.com/VAST-AI-Research/TripoSR [instantmesh]=https://github.com/TencentARC/InstantMesh)
declare -A COMMIT=([triposr]=107cefdc244c39106fa830359024f6a2f1c78871 [instantmesh]=08822c52fdc399b93ea00e4fa9e596344ed52ccc)
declare -A DIR=([triposr]=TripoSR [instantmesh]=InstantMesh)
UV=${UV:-uv}; PY=$ENV_ROOT/$NAME/bin/python; T0=$(date +%s)
retry() {  # network steps (GitHub/PyPI) fail transiently — measured on Kaggle: "Send failure: Broken pipe"
  local n=1
  until "$@"; do
    [ $n -ge 4 ] && { echo "FAILED after $n attempts: $*" >&2; return 1; }
    echo "attempt $n failed, retrying in $((n*15))s: $*" >&2; sleep $((n*15)); n=$((n+1))
  done
}
if [ ! -d "$ROOT/third_party/${DIR[$NAME]}/.git" ]; then
  retry git clone -q "${REPO[$NAME]}" "$ROOT/third_party/${DIR[$NAME]}"
fi
git -C "$ROOT/third_party/${DIR[$NAME]}" checkout -q "${COMMIT[$NAME]}"
$UV venv -q "$ENV_ROOT/$NAME" --python 3.10
# envs/<name>.lock.txt = `uv pip compile envs/<name>.requirements.txt + torch pins` (resolved, fully pinned)
retry $UV pip install -q --python "$PY" -r "$ROOT/envs/$NAME.lock.txt" \
    --extra-index-url https://download.pytorch.org/whl/cu121 --index-strategy unsafe-best-match
# setuptools<70 still ships pkg_resources (needed by torch 2.1 cpp_extension and lightning_fabric)
retry $UV pip install -q --python "$PY" "setuptools==69.5.1" wheel ninja
retry $UV pip install --python "$PY" --no-build-isolation -r "$ROOT/envs/$NAME.post.txt"
if [ "$NAME" = instantmesh ] && command -v nvidia-smi >/dev/null; then
  # nvdiffrast JIT-compiles its CUDA plugin on first use (~2 min measured on a T4); do it at setup, not on the first sketch.
  (cd "$ROOT/third_party/${DIR[$NAME]}" && "$PY" -c "import nvdiffrast.torch as dr; dr.RasterizeCudaContext(device='cuda'); print('nvdiffrast plugin compiled')") || echo "WARNING: nvdiffrast warm-up failed"
fi
SIZE=$(du -sm "$ENV_ROOT/$NAME" | cut -f1)
echo "{\"backend\": \"$NAME\", \"build_seconds\": $(( $(date +%s) - T0 )), \"env_size_mb\": $SIZE}" > "$ENV_ROOT/$NAME.build.json"
cat "$ENV_ROOT/$NAME.build.json"
