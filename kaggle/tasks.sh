#!/usr/bin/env bash
# Phase 0c + Phase 1 on Kaggle T4: build envs (parallel), weights, calibrate backends, walking-skeleton runs.
source "$(dirname "$0")/common.sh"
T0=$(date +%s)
setup_backend triposr > $OUT/logs/b_triposr.txt 2>&1 &
setup_backend instantmesh > $OUT/logs/b_instantmesh.txt 2>&1 &
setup_parent > $OUT/logs/parent.txt 2>&1
cat $OUT/logs/parent.txt
weights balanced triposr,instantmesh > $OUT/logs/weights.txt 2>&1 &
wait
cat $OUT/logs/b_*.txt $OUT/logs/weights.txt
echo "setup total $(( $(date +%s) - T0 ))s"; du -sm $S2S_WEIGHTS/* envs/triposr envs/instantmesh .venv 2>/dev/null | tee $OUT/logs/disk_mb.txt

log calibrate
declare -A P0LABEL=([triposr]=default [instantmesh]=base_norembg)
for b in triposr instantmesh; do
  if .venv/bin/python -c "import yaml,sys;c=yaml.safe_load(open('config/backends.yaml'))['backends']['$b']['calibration'];sys.exit(0 if c['phase0_passed'] and c['handedness_checked'] else 1)"; then
    echo "calibrate $b: already calibrated, skipping"; continue; fi
  .venv/bin/python scripts/calibrate_backend.py $b --mark-phase0 docs/phase0/kaggle_t4_${b}_${P0LABEL[$b]}.json --out $OUT/calibration/$b \
     > $OUT/logs/calibrate_$b.txt 2>&1; echo "calibrate $b rc=$?"; tail -25 $OUT/logs/calibrate_$b.txt
done
cp config/backends.yaml $OUT/backends.yaml; cp -r $OUT/calibration $OUT/calibration_copy 2>/dev/null; true
.venv/bin/python -m sketch2shape.cli doctor | tee $OUT/logs/doctor.txt

log runs
.venv/bin/python scripts/batch_run.py kaggle/runs.txt --out $OUT/outputs 2>&1 | grep '^{'
echo "ALL DONE $(( $(date +%s) - T0 ))s"
