"""Point-vs-path extinction check (data stage; needs the FDS output tree).

How much does the single-point FDS extinction at each LEM/SICK position (the
``EXT_DEVC_*`` point devices) deviate from the *path-mean* over the ~0.8 m
optical path that a transmissometer integrates, k = -ln(tau)/L = (1/L) int k ds?

The 3D-EXT slice field is integrated along each beam of the FDS input file (field
integration), NOT via the FDS ``PATH OBSCURATION`` device -- the latter truncates
multi-mesh beams with descending endpoints (FDS issue #16338), so the field
path-mean is the reliable reference here.

Writes
  results/validation/extinction_point_vs_path.csv          (per series x path)
  results/validation/extinction_point_vs_path_summary.csv  (pooled over all paths/series;
                                                           -> \\valExtPathPoint* in numbers.tex)

Slow: reads the 3D-EXT slice of each baseline series (a few minutes each).

    python scripts/extinction_point_vs_path.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import paths as P
from fdsreader_patch import patch_fdsreader_3d_cell_centered

OUT_DIR = P.RESULTS_DIR / "validation"
OUT_CSV = OUT_DIR / "extinction_point_vs_path.csv"
SUM_CSV = OUT_DIR / "extinction_point_vs_path_summary.csv"

# Baseline runs (per-series matched soot yield, FDS 6.11.1) and the end of the
# evaluated window per series (s).
GRID = "ysmatched"
SERIES_T_END = {"hep_160_075": 900, "hep_160_150": 1200, "hep_220_300": 1200}

# LEM/SICK optical paths: horizontal beams along x, centred on the instrument
# position of the FDS input file (= the single-point device EXT_DEVC_* and the
# centre of the LOS PATH OBSCURATION beam), integrated over the *optical* path
# length L -- not the mounting span. LEM: single-pass L = 0.81 m. SICK FW 56-I:
# 0.8 m transmitter-reflector span (the beam double-passes the SAME 0.8 m chord,
# so the spatial extent is 0.8 m). Centres (x_c, y, z) are the deck coordinates,
# as in Table S1 and Figure 1.
# (label, instrument, room, x_centre, y, z, L)
L_LEM, L_SICK = 0.81, 0.80
PATHS = [
    ("LEM F1",      "LEM",  "F1", 3.150, 3.725,  2.30,  L_LEM),
    ("LEM F2 1.5m", "LEM",  "F2", 2.275, 6.275,  1.5,   L_LEM),
    ("LEM F2 1.9m", "LEM",  "F2", 2.275, 6.275,  1.9,   L_LEM),
    ("LEM F2 2.1m", "LEM",  "F2", 2.275, 6.275,  2.1,   L_LEM),
    ("LEM F2 2.3m", "LEM",  "F2", 2.275, 6.325,  2.3,   L_LEM),
    ("LEM F3",      "LEM",  "F3", 2.275, 12.775, 2.30,  L_LEM),
    ("SICK F1",     "SICK", "F1", 3.180, 3.525,  2.285, L_SICK),
    ("SICK F2",     "SICK", "F2", 2.275, 5.340,  2.315, L_SICK),
    ("SICK F3",     "SICK", "F3", 2.260, 13.095, 2.255, L_SICK),
]
N_PTS = 41        # samples along each path (~1 cell spacing)
K_MIN = 0.05      # only smoke-bearing instants (1/m)


def _sample_field(subslices, pts: np.ndarray) -> np.ndarray:
    """Nearest-cell values of the 3D slice at points pts (n, 3), all times.

    Returns array (n_times, n_pts). Each point is assigned to the first mesh
    whose bounding box contains it; lookup is nearest cell centre.
    """
    n_pts = len(pts)
    out = None
    assigned = np.zeros(n_pts, dtype=bool)
    for sub in subslices:
        nodes = sub.mesh.coordinates  # node coordinates per dimension
        lo = np.array([nodes[d][0] for d in "xyz"])
        hi = np.array([nodes[d][-1] for d in "xyz"])
        inside = ~assigned & np.all((pts >= lo) & (pts <= hi), axis=1)
        if not inside.any():
            continue
        data = sub.data  # (n_t, nx, ny, nz) cell values
        if out is None:
            out = np.full((data.shape[0], n_pts), np.nan, dtype=np.float32)
        idx = []
        for ax, d in enumerate("xyz"):
            i = np.searchsorted(nodes[d], pts[inside, ax], side="right") - 1
            idx.append(np.clip(i, 0, data.shape[1 + ax] - 1))
        out[:, inside] = data[:, idx[0], idx[1], idx[2]]
        assigned |= inside
        sub.clear_cache()
    if not assigned.all():
        raise RuntimeError(f"{(~assigned).sum()} sample points outside all meshes")
    return out


def run_series(series: str) -> tuple[list[dict], np.ndarray]:
    import fdsreader
    sim = fdsreader.Simulation(str(P.FDS_OUTPUT_ROOT / f"{series}_{GRID}"))
    slc = [s for s in sim.slices if s.id == "3D-EXT"][0]
    subs = list(slc.subslices)
    times = np.asarray(slc.times, float)
    tmask = times <= SERIES_T_END[series]
    rows, dev_pool = [], []
    # Sample all paths in one pass over the subslices (each mesh file is read once).
    all_pts = np.vstack([
        np.column_stack([np.linspace(xc - length / 2, xc + length / 2, N_PTS),
                         np.full(N_PTS, y), np.full(N_PTS, z)])
        for _, _, _, xc, y, z, length in PATHS])
    v_all = _sample_field(subs, all_pts)          # (n_t, n_paths * N_PTS)
    for i, (lab, inst, room, xc, y, z, length) in enumerate(PATHS):
        v = v_all[:, i * N_PTS:(i + 1) * N_PTS]   # (n_t, N_PTS)
        pm = v.mean(axis=1)                        # path-mean k (= (1/L) int k ds)
        pt = v[:, N_PTS // 2]                      # single-point k at path centre
        m = tmask & (pm > K_MIN)
        if not m.any():
            raise RuntimeError(f"{series} {lab}: no smoke-bearing samples "
                               f"(max path-mean k {np.nanmax(pm):.3g} 1/m) -- check the slice read")
        dev = (pm[m] - pt[m]) / pt[m] * 100.0
        dev_pool.append(dev)
        rows.append(dict(
            series=series, path=lab, instrument=inst, room=room,
            length_m=length, n=int(dev.size),
            k_path=float(pm[m].mean()), k_point=float(pt[m].mean()),
            median_pct=float(np.median(dev)),
            iqr_lo_pct=float(np.percentile(dev, 25)),
            iqr_hi_pct=float(np.percentile(dev, 75)),
            p95abs_pct=float(np.percentile(np.abs(dev), 95)),
            maxabs_pct=float(np.abs(dev).max()),
        ))
    return rows, np.concatenate(dev_pool)


def main() -> None:
    patch_fdsreader_3d_cell_centered()
    # Read the FDS output directly, not through fdsreader's <chid>.pickle cache in
    # the output directory: a stale cache can return NaN times and all-zero slice
    # data for a whole series without raising.
    import fdsreader.settings
    fdsreader.settings.ENABLE_CACHING = False
    all_rows, pool = [], []
    for series in SERIES_T_END:
        print(f"[{series}] reading 3D-EXT slice ...", flush=True)
        rows, dev = run_series(series)
        all_rows += rows
        pool.append(dev)
    pool = np.concatenate(pool)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(all_rows).to_csv(OUT_CSV, index=False)
    pd.DataFrame([dict(
        n=int(pool.size),
        median_pct=float(np.median(pool)),
        iqr_lo_pct=float(np.percentile(pool, 25)),
        iqr_hi_pct=float(np.percentile(pool, 75)),
        p95abs_pct=float(np.percentile(np.abs(pool), 95)),
        maxabs_pct=float(np.abs(pool).max()),
    )]).to_csv(SUM_CSV, index=False)
    print(f"wrote {OUT_CSV} ({len(all_rows)} rows)")
    print(f"wrote {SUM_CSV}")
    print(f"POOLED: median {np.median(pool):+.1f}%  "
          f"IQR [{np.percentile(pool, 25):+.1f},{np.percentile(pool, 75):+.1f}]%  "
          f"p95|.| {np.percentile(np.abs(pool), 95):.1f}%  max {np.abs(pool).max():.1f}%  n={pool.size}")


if __name__ == "__main__":
    main()
