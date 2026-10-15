"""Shared I/O helpers for FDS output files.

The FDS device file ``<CHID>_devc.csv`` has two header rows -- row 0 holds the
units, row 1 the device IDs -- followed by one row per output time. These files
are wide (here ~5000 device columns), so the read is centralised here instead of
being duplicated across the analysis scripts.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def read_fds_devc(path, usecols=None) -> pd.DataFrame:
    """Read an FDS ``*_devc.csv`` (units on row 0, device IDs on row 1).

    usecols: optional column selector forwarded to pandas (e.g. a name list or
    a callable) to read only a subset of the ~5000 device columns.

    The FDS output tree lives on an external data drive that can intermittently
    drop the session (OSError errno 22); retry the read with backoff before
    giving up.
    """
    import time
    path = Path(path)
    for attempt in range(8):
        try:
            return pd.read_csv(path, header=1, usecols=usecols)
        except OSError:
            if attempt == 7:
                raise
            time.sleep(min(30.0, 3.0 * (attempt + 1)))


# ---------------------------------------------------------------------------
# Line-of-sight extinction: PATH OBSCURATION (%) -> extinction coefficient k
# ---------------------------------------------------------------------------
# The re-run decks carry the LEM/SICK instruments as as-built line-of-sight
# ``PATH OBSCURATION`` beams (percent) instead of single-point extinction
# devices. The path-mean extinction coefficient is k = -ln(1 - OBS/100) / L,
# the same operator applied to the physical transmittance readings. Path length
# L: LEM single pass 0.81 m; SICK 0.80 m (the 2 x 0.80 m double pass cancels in
# the transmittance, so the single-pass 0.80 m is used). IDs match the FDS deck
# LOS block; F2 LEM 3 (z=2.3) sits 5 cm off the LEM 1 column, as built.
LOS_BEAM_L = {
    "LEM_LOS_F1_2_3": 0.81, "LEM_LOS_F2_1_5": 0.81, "LEM_LOS_F2_1_9": 0.81,
    "LEM_LOS_F2_2_1": 0.81, "LEM_LOS_F2_2_3": 0.81, "LEM_LOS_F3_2_3": 0.81,
    "SICK_LOS_F1": 0.80, "SICK_LOS_F2": 0.80, "SICK_LOS_F3": 0.80,
}


def path_obscuration_to_k(obs_pct, L: float) -> np.ndarray:
    """Convert PATH OBSCURATION [%] to path-mean extinction k [1/m] over length L."""
    obs = np.clip(np.asarray(obs_pct, float), 0.0, 99.999)
    return -np.log1p(-obs / 100.0) / L


def add_los_extinction(df: pd.DataFrame) -> pd.DataFrame:
    """Add a ``<beam>_k`` column [1/m] for each LOS PATH OBSCURATION beam present
    in the device frame, leaving the raw obscuration columns untouched."""
    for beam, L in LOS_BEAM_L.items():
        if beam in df.columns:
            df[beam + "_k"] = path_obscuration_to_k(df[beam], L)
    return df
