"""Size evolution of the binned (agglomerating) soot in the humid-air deposition run
hep_160_075_sootdep_binned_rh (data stage; needs the FDS output tree).

FDS tracks the soot in five size bins (bin diameters as printed in the .out file:
0.013, 0.050, 0.199, 0.791, 3.148 um; 0.01-10 um, particle density 1800 kg/m3) and
writes the airborne mass of each bin (LUMPED SOOT_1..5) to the _mass.csv file. This
reducer keeps those per-bin masses on a 10 s grid, the basis of the agglomeration
statements in Table S11 note d and the deposition paragraph of SM S13
(\valBinned* in numbers.tex).

Writes results/simulation/sootdep_binned_rh_bins.csv (t_s, m_bin1..5_g, m_total_g, d_mass_um).

    python scripts/reduce_binned_soot.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import paths as P

CHID = "hep_160_075_sootdep_binned_rh"
BIN_D_UM = np.array([0.013, 0.050, 0.199, 0.791, 3.148])
OUT = P.RESULTS_DIR / "simulation" / "sootdep_binned_rh_bins.csv"


def main() -> None:
    f = P.FDS_OUTPUT_ROOT / CHID / f"{CHID}_mass.csv"
    m = pd.read_csv(f, skiprows=1)
    m.columns = [c.strip() for c in m.columns]
    cols = [f"LUMPED SOOT_{k}" for k in range(1, 6)]
    t = m["Time"].to_numpy(float)
    grid = np.arange(0.0, float(t.max()) + 1e-6, 10.0)
    out = pd.DataFrame({"t_s": grid})
    for k, c in enumerate(cols, 1):
        out[f"m_bin{k}_g"] = np.interp(grid, t, m[c].to_numpy(float)) * 1e3
    bins = out[[f"m_bin{k}_g" for k in range(1, 6)]].to_numpy()
    out["m_total_g"] = bins.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out["d_mass_um"] = (bins * BIN_D_UM).sum(axis=1) / out["m_total_g"]
    # the SOOT column of _mass.csv is the sum of the bins: a consistency gate
    soot = np.interp(grid, t, m["SOOT"].to_numpy(float)) * 1e3
    if np.nanmax(np.abs(soot - out["m_total_g"])) > 1e-4:
        raise SystemExit("bin masses do not sum to the SOOT column")
    out.to_csv(OUT, index=False, float_format="%.6g", lineterminator="\n")
    print(f"wrote {OUT} ({len(out)} rows)")


if __name__ == "__main__":
    main()
