# One-command paths (spec §13): make setup && make weights PROFILE=balanced && make demo
PROFILE ?= balanced
BACKENDS ?= $(if $(filter balanced,$(PROFILE)),triposr instantmesh,triposr)
EXTRAS ?=
UV ?= uv
PY := .venv/bin/python

.PHONY: setup parent backends weights demo test doctor calibrate

setup: parent backends

parent:
	pip install -q -U uv
	$(UV) venv .venv --python 3.10
	for i in 1 2 3; do $(UV) pip install --python $(PY) -r requirements.lock --extra-index-url https://download.pytorch.org/whl/cu121 --index-strategy unsafe-best-match && break || sleep 20; done
	$(UV) pip install --python $(PY) --no-deps -e .

backends:
	@for b in $(BACKENDS); do UV=$(UV) bash scripts/setup_backend.sh $$b || echo "WARNING: backend $$b failed to build — the app will fall back to the others"; done

weights:
	$(PY) -m sketch2shape.cli weights --profile $(PROFILE) --backends "$(shell echo $(BACKENDS) | tr ' ' ',')" --extras "$(EXTRAS)"

demo:
	HF_HUB_OFFLINE=1 $(PY) -m sketch2shape.cli serve $(if $(SHARE),--share,)

doctor:
	$(PY) -m sketch2shape.cli doctor

test:
	$(PY) -m pytest -q

calibrate:
	@for b in $(BACKENDS); do $(PY) scripts/calibrate_backend.py $$b; done
