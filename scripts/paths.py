"""Central path configuration for the smoke-light-extinction analysis.

Two kinds of location:

* **Repo-relative outputs / committed data** (always inside the repo) -- the
  figure stage reads and writes only these, so it runs without any external data.
* **External raw-data roots** -- needed only by the *data* stage that reduces the
  raw measurement and FDS-output trees into the committed intermediate CSVs.

Each external root has an environment-variable override and defaults to a neutral
in-repo placeholder under ``data/``, so no absolute path is committed and the
committed figure stage runs with none of them set. Point the variables at your own
copies of the raw data to re-run the data stage.

    HASENHEIDE_MEAS_ROOT     -> measurement tree (processed run CSVs, smoke alarms)
    HASENHEIDE_ANALYSIS_ROOT -> analysis tree (parent of HRR/)
    HASENHEIDE_HRR_ROOT      -> per-series HRR ensemble CSVs
    HASENHEIDE_PREP_ROOT     -> preparation tree (blower-door reports)
    HASENHEIDE_FDS_ROOT      -> FDS output tree (device CSVs, 3D slices)

Use ``available(root)`` to guard data-stage steps so they skip cleanly when the
external data is not present.
"""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Repo-relative locations (committed or generated inside the repo)
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
PLOTS_DIR = REPO_ROOT / "plots"
# Figures are grouped by provenance (mirrors the paper: measure -> model -> validate).
MEAS_PLOTS = PLOTS_DIR / "measurement"
SIM_PLOTS = PLOTS_DIR / "simulation"
VAL_PLOTS = PLOTS_DIR / "validation"
FDS_DECK_DIR = REPO_ROOT / "fds_decks"
VALIDATION_DIR = REPO_ROOT / "device_validation"

DATA_DIR = REPO_ROOT / "data"
REPROCESSED_DIR = DATA_DIR / "reprocessed"

# Committed reduced intermediate CSVs (the reproducibility boundary): the data
# stage publishes here, the figure stage reads from here. Grouped by provenance.
RESULTS_DIR = REPO_ROOT / "results"
MEAS_RESULTS = RESULTS_DIR / "measurement"   # experimental (measured) reduced data
SIM_RESULTS = RESULTS_DIR / "simulation"     # FDS (simulation) reduced data
VAL_RESULTS = RESULTS_DIR / "validation"     # measured-vs-modelled comparison data
FDS_METRICS_DIR = VAL_RESULTS / "fds_metrics"

SUB_PROCESSED = "1_Processed_data"


# --------------------------------------------------------------------------
# External raw-data roots (data stage only; overridable via env vars; default to
# neutral in-repo placeholders so the committed figure stage needs none of them)
# --------------------------------------------------------------------------
def _env_path(var: str, default: str | Path) -> Path:
    """Return ``$var`` as a Path if set and non-empty, else ``default``."""
    val = os.environ.get(var)
    return Path(val) if val else Path(default)


_RAW = REPO_ROOT / "data" / "raw"
MEAS_ROOT = _env_path("HASENHEIDE_MEAS_ROOT", _RAW / "measurements")
ANALYSIS_ROOT = _env_path("HASENHEIDE_ANALYSIS_ROOT", _RAW / "analysis")
HRR_ROOT = _env_path("HASENHEIDE_HRR_ROOT", ANALYSIS_ROOT / "HRR")
PREP_ROOT = _env_path("HASENHEIDE_PREP_ROOT", _RAW / "preparation")
FDS_OUTPUT_ROOT = _env_path("HASENHEIDE_FDS_ROOT", REPO_ROOT / "data" / "fds_output")


def available(root: Path) -> bool:
    """True if an external root is present (its data has been supplied)."""
    try:
        return Path(root).exists()
    except OSError:
        return False
