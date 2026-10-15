# Thin wrapper around run_all.py. See `python run_all.py list` for targets.
PY ?= python

.PHONY: all data figures figures-committed list dry

all:               ## data stage then figures stage
	$(PY) run_all.py all

data:              ## external raw measurement/simulation data -> committed CSVs
	$(PY) run_all.py data

figures:           ## committed CSVs/inputs -> paper figures + computational tables
	$(PY) run_all.py figures

figures-committed: ## only the subset needing no external drive
	$(PY) run_all.py figures --committed

list:              ## registry of targets and their reproducibility status
	$(PY) run_all.py list

dry:               ## print the figures plan without running anything
	$(PY) run_all.py figures --dry-run
