# Shared Kaggle setup: parent env + backend envs + weights. Source from tasks.sh.
set -uo pipefail
export W=/tmp/s2s R=/tmp/s2s/repo OUT=/kaggle/working
export S2S_WEIGHTS=$W/weights HF_HOME=$W/weights/hf TORCH_HOME=$W/weights/torch U2NET_HOME=$W/weights/u2net
export CUDA_VISIBLE_DEVICES=0 PATH=/usr/local/cuda/bin:$HOME/.local/bin:$PATH UV_LINK_MODE=copy
mkdir -p $OUT/logs $S2S_WEIGHTS
cd $R
log() { echo -e "\n===== $* =====" ; }
pip install -q uv psutil 2>&1 | tail -1
setup_parent() {
  log parent env
  local t=$(date +%s)
  uv venv -q .venv --python 3.10 && uv pip install -q --python .venv/bin/python -r requirements.lock \
     --extra-index-url https://download.pytorch.org/whl/cu121 --index-strategy unsafe-best-match \
  && uv pip install -q --python .venv/bin/python --no-deps -e . && echo "parent env $(( $(date +%s) - t ))s $(du -sm .venv | cut -f1)MB"
}
setup_backend() {  # name
  log backend $1
  bash scripts/setup_backend.sh $1 $R/envs > $OUT/logs/setup_$1.log 2>&1; local rc=$?
  tail -5 $OUT/logs/setup_$1.log; cat envs/$1.build.json 2>/dev/null; return $rc
}
weights() {  # profile backends
  log weights $1 $2
  .venv/bin/python -m sketch2shape.cli weights --profile $1 --backends $2 2>&1 | tail -20
}
