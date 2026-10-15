"""Four-grid convergence check for the hep_160_075 baseline (Supplementary
Material: FDS sensitivity study, "Grid resolution").

Compares the peak validation quantities -- light extinction k at the LEM heights
(z = 2.3 m, rooms F1-F3) and upper-layer / ceiling gas temperature -- across the
four-grid set: the 25/50 mm baseline (dx25), a uniform 25 mm grid (uni25), a
global 2x refinement to 12.5/25 mm (dx12), and a uniform 50 mm grid (uni50). Peaks are taken from an 11-sample
centred rolling mean to suppress single-sample spikes. The acceptance criterion
is that refinement (dx12) leaves extinction and upper-layer temperature
essentially unchanged relative to the model-measurement differences.

Writes
  results/simulation/grid_convergence.csv          (per quantity x grid + dx12/uni25 deviation)
  results/simulation/grid_convergence_summary.csv  (max/mean |dx12-dx25| per group)

    python scripts/grid_convergence.py
"""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

import paths as P
from fds_io import add_los_extinction

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = REPO_ROOT / "results" / "simulation" / "grid_convergence.csv"
SUM_CSV = REPO_ROOT / "results" / "simulation" / "grid_convergence_summary.csv"

GRIDS = {"dx25": "hep_160_075_ysmatched", "uni25": "hep_160_075_uni25",
         "dx12": "hep_160_075_dx12", "uni50": "hep_160_075_uni50"}
# uni50 (uniform 50 mm; near-field coarsened 25->50 mm) is included when its FDS
# output directory is present, otherwise skipped.
T_END = 900.0          # hep_160_075 sealed-enclosure window (s)
ROLL = 11              # centred rolling-mean window (samples) for the peak

# (group, label, device).  Extinction at the LEM height z=2.3 m as as-built
# line-of-sight PATH OBSCURATION beams -> path-mean k (add_los_extinction);
# temperature at the upper thermocouples (2.4 m) and the plume-impingement ceiling.
METRICS = [
    ("extinction", "F1",             "LEM_LOS_F1_2_3_k"),
    ("extinction", "F2",             "LEM_LOS_F2_2_3_k"),
    ("extinction", "F3",             "LEM_LOS_F3_2_3_k"),
    ("temperature", "F1 upper (2.4 m)", "TC_F1_2_4"),
    ("temperature", "F2 upper (2.4 m)", "TC_F2_2_4"),
    ("temperature", "F1 ceiling",       "TC_Ceiling_F1"),
    ("temperature", "F3 ceiling",       "TC_Ceiling_F3"),
]


def peaks(run: str) -> dict | None:
    files = glob.glob(str(P.FDS_OUTPUT_ROOT / run / "*_devc.csv"))
    if not files:
        return None                                # output not present yet
    f = files[0]
    # LOS k columns are derived; read their raw obscuration columns (strip '_k').
    need = {d[:-2] if d.endswith("_k") else d for *_, d in METRICS}
    df = pd.read_csv(f, skiprows=1,
                     usecols=lambda c: c in need or c.lower().startswith("time") or c == "s")
    df = add_los_extinction(df)
    tcol = [c for c in df.columns if c.lower().startswith("time") or c == "s"][0]
    df = df[df[tcol] <= T_END]
    return {d: float(df[d].rolling(ROLL, center=True, min_periods=1).mean().max())
            for *_, d in METRICS}


def main() -> None:
    pk = {g: peaks(run) for g, run in GRIDS.items()}
    have_uni50 = pk.get("uni50") is not None       # coarse case optional
    rows = []
    for group, label, dev in METRICS:
        v25, vu, v12 = pk["dx25"][dev], pk["uni25"][dev], pk["dx12"][dev]
        row = dict(group=group, quantity=label,
                   dx25=v25, uni25=vu, dx12=v12,
                   uni25_dev_pct=(vu / v25 - 1) * 100.0,
                   dx12_dev_pct=(v12 / v25 - 1) * 100.0)
        if have_uni50:
            vu50 = pk["uni50"][dev]
            row["uni50"] = vu50
            row["uni50_dev_pct"] = (vu50 / v25 - 1) * 100.0
        rows.append(row)
    df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    sums = []
    for group in ("extinction", "temperature"):
        gdf = df[df.group == group]
        d = gdf["dx12_dev_pct"].abs()
        srow = dict(group=group, max_abs_dev_pct=float(d.max()),
                    mean_abs_dev_pct=float(d.mean()))
        if have_uni50:
            u = gdf["uni50_dev_pct"].abs()
            srow["uni50_max_abs_dev_pct"] = float(u.max())
            srow["uni50_mean_abs_dev_pct"] = float(u.mean())
        sums.append(srow)
    pd.DataFrame(sums).to_csv(SUM_CSV, index=False)

    print(f"wrote {OUT_CSV} ({len(df)} rows)")
    print(f"wrote {SUM_CSV}")
    print(df.to_string(index=False,
          formatters={c: "{:.3f}".format for c in ("dx25", "uni25", "dx12")},
          float_format="{:+.1f}".format))
    print(pd.DataFrame(sums).to_string(index=False, float_format="{:.1f}".format))


if __name__ == "__main__":
    main()
