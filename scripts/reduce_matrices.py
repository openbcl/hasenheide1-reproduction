"""Reducer for the 3x3 extinction matrices (measured, Fig. 4; with FDS, Fig. 6)
and the temperature-profile matrices (Supplementary Material).

Reads the measurement ensembles from the raw-data root (``MEAS_ROOT``; without
it, from the committed per-test time series, results/measurement/timeseries/) and
the FDS baselines from the FDS output tree (without it, from the committed baseline
time series, results/simulation/timeseries/), and writes the committed reduced curves the plotter (``plot_extinction_matrices.py``)
needs, so both matrix figures regenerate without the raw data:

  results/validation/matrices/ext_lem.csv    series, room, t_s, mean, std   (LEM ensemble)
  results/validation/matrices/ext_sick.csv   series, room, run, t_s, sick   (per-run SICK)
  results/validation/matrices/ext_meta.csv   series, room, n_lem, n_sick, m_dur, m_vent
  results/validation/matrices/temp_prof.csv  series, t_target, z, mean_f1, std_f1, mean_f2, std_f2
  results/validation/matrices/temp_ceil.csv  series, t_target, m_ceil, s_ceil

The load/aggregation logic is identical to the original combined script; only the
hand-off via CSV is new. CSVs are written with the shortest round-trip float repr
and read back with float_precision='round_trip' (see the plotter); a self-check
asserts bit-for-bit recovery (NaN-aware). Run: python reduce_matrices.py
"""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

import fds_io
from measurement_io import get_processed_file, load_runs, ensemble_stats, read_processed
import paths as P

REDUCED_DIR = P.RESULTS_DIR / "validation" / "matrices"
FDS_TIMESERIES = P.SIM_RESULTS / "timeseries"
BASE_PATH = P.MEAS_ROOT
SUB_PROCESSED = P.SUB_PROCESSED

SERIES_CONFIG = [
    {"name": "Hep_160_075",
     "ids": ["Hep_160_S2_R1", "Hep_160_S2_R2", "Hep_160_S2_R3", "Hep_160_S3_R1",
             "Hep_160_S3_R2", "Hep_160_S4_R1", "Hep_160_S4_R2"]},
    {"name": "Hep_160_150",
     "ids": ["Hep_160_S1_R1", "Hep_160_S1_R2", "Hep_160_S1_R3"]},
    {"name": "Hep_220_300",
     "ids": ["Hep_220_S1_R1", "Hep_220_S1_R2", "Hep_220_S1_R3", "Hep_220_S1_R4"]},
]

EXT_T_START, EXT_T_END = -30, 1500
ROOMS = ["F1", "F2", "F3"]
ROOM_TO_KEY = {
    "F1": "Extinction LEM_4_F1_2.3 (1/m)",
    "F2": "Extinction LEM_3_F2_2.3 (1/m)",
    "F3": "Extinction LEM_2_F3_2.3 (1/m)",
}

TARGET_TIMES = [150, 300, 450]
HEIGHTS = [0.6, 1.2, 1.6, 1.8, 2.0, 2.2, 2.4, 2.5]

# Common time grid (pre-ventilation window) for the full time-height temperature
# matrices that feed the S9/S10 heatmaps (measured and FDS reduced onto the SAME grid,
# so the plotter subtracts directly). 5 s is ample for a contour and keeps the CSV
# small; each run/series is interpolated onto it (NaN outside its extent).
FULL_T_GRID = np.arange(0.0, 901.0, 5.0)
TREE_PREFIX = {"F1": "Temp Tree 1", "F2": "Temp Tree 2"}

# FDS baseline overlay: extinction at z=2.3 m as as-built line-of-sight PATH
# OBSCURATION beams -> path-mean k (add_los_extinction, LEM L=0.81 m), the F1/F2
# thermocouples at the experiment heights, and the F1 ceiling thermocouple.
EXT_FDS_COL = {"F1": "LEM_LOS_F1_2_3_k", "F2": "LEM_LOS_F2_2_3_k", "F3": "LEM_LOS_F3_2_3_k"}


# -------- extinction reduction --------
def reduce_extinction():
    lem_rows, sick_rows, meta_rows = [], [], []
    for series in SERIES_CONFIG:
        name = series["name"]
        print(f"\nloading (extinction): {name}")
        exp_data, durations, vent_times = load_runs(
            BASE_PATH, series["ids"], EXT_T_START, EXT_T_END, SUB_PROCESSED)
        if not exp_data:
            continue
        mean_df, std_df = ensemble_stats(exp_data, EXT_T_START, EXT_T_END)
        durs = [v for v in durations.values() if not np.isnan(v)]
        m_dur = (np.mean(durs) if durs else np.nan)
        vents = [v for v in vent_times.values() if not np.isnan(v)]
        m_vent = np.mean(vents) if vents else np.nan

        t_mean = mean_df["Time (s)"].to_numpy(float)
        for room in ROOMS:
            col_key = ROOM_TO_KEY[room]
            n_lem, n_sick = 0, 0
            # iterate runs in exp_data order (== ids order) for SICK draw order
            for run_id, df in exp_data.items():
                if col_key in df.columns and not df[col_key].dropna().empty:
                    n_lem += 1
                sick_cols = [c for c in df.columns
                             if "SICK" in c and room in c and "_corr" in c]
                if sick_cols and not df[sick_cols[0]].dropna().empty:
                    n_sick += 1
                    sick_rows.append(pd.DataFrame({
                        "series": name, "room": room, "run": run_id,
                        "t_s": df["Time (s)"].to_numpy(float),
                        "sick": pd.to_numeric(df[sick_cols[0]], errors="coerce").to_numpy(float),
                    }))
            if col_key in mean_df.columns:
                lem_rows.append(pd.DataFrame({
                    "series": name, "room": room, "t_s": t_mean,
                    "mean": mean_df[col_key].to_numpy(float),
                    "std": std_df[col_key].to_numpy(float),
                }))
            meta_rows.append({"series": name, "room": room, "n_lem": n_lem,
                              "n_sick": n_sick, "m_dur": m_dur, "m_vent": m_vent})

    lem = pd.concat(lem_rows, ignore_index=True) if lem_rows else pd.DataFrame()
    sick = pd.concat(sick_rows, ignore_index=True) if sick_rows else pd.DataFrame(
        columns=["series", "room", "run", "t_s", "sick"])
    meta = pd.DataFrame(meta_rows)
    return lem, sick, meta


# -------- temperature reduction --------
def load_data_for_profiles(selection_list):
    """Load DataFrames, zeroing the thermocouple columns at t=0."""
    loaded_data = {}
    for folder_id in selection_list:
        file_path = get_processed_file(BASE_PATH, folder_id, SUB_PROCESSED)
        if not file_path:
            continue
        try:
            df = read_processed(file_path)
            idx0 = (df["Time (s)"] - 0).abs().idxmin()
            temp_cols = [c for c in df.columns if "Temp" in c]
            df[temp_cols] = df[temp_cols] - df.loc[idx0, temp_cols]
            loaded_data[folder_id] = df
        except Exception as e:  # noqa: BLE001
            print(f"  failed: {folder_id}: {e}")
    return loaded_data


def get_profile_at_time(df, tree_prefix, t_target):
    idx = (df["Time (s)"] - t_target).abs().idxmin()
    out = []
    for h in HEIGHTS:
        col_name = f"{tree_prefix}_{h} (°C)"
        out.append(df.loc[idx, col_name] if col_name in df.columns else np.nan)
    return np.array(out)


def get_ceiling_point(df, t_target):
    idx = (df["Time (s)"] - t_target).abs().idxmin()
    col = "Plume Impingement Temperature (°C)"
    return df.loc[idx, col] if col in df.columns else np.nan


def reduce_temperature():
    prof_rows, ceil_rows, prof_full_rows = [], [], []
    for series in SERIES_CONFIG:
        name = series["name"]
        print(f"\nloading (temperature): {name}")
        exp_data = load_data_for_profiles(series["ids"])
        if not exp_data:
            continue
        for t_val in TARGET_TIMES:
            profiles_f1, profiles_f2, ceiling_f1 = [], [], []
            for folder_id, df in exp_data.items():
                profiles_f1.append(get_profile_at_time(df, "Temp Tree 1", t_val))
                profiles_f2.append(get_profile_at_time(df, "Temp Tree 2", t_val))
                c1 = get_ceiling_point(df, t_val)
                if not np.isnan(c1):
                    ceiling_f1.append(c1)
            mean_f1 = np.nanmean(profiles_f1, axis=0)
            mean_f2 = np.nanmean(profiles_f2, axis=0)
            # ddof=1 (Bessel) to match the extinction ensemble (ensemble_stats,
            # groupby.std(ddof=1)) and the paper-wide Bessel-corrected convention;
            # a single-run height yields NaN (band not drawn), as for extinction.
            std_f1 = np.nanstd(profiles_f1, axis=0, ddof=1)
            std_f2 = np.nanstd(profiles_f2, axis=0, ddof=1)
            m_ceil = np.nanmean(ceiling_f1) if ceiling_f1 else np.nan
            s_ceil = np.nanstd(ceiling_f1, ddof=1) if len(ceiling_f1) > 1 else np.nan
            prof_rows.append(pd.DataFrame({
                "series": name, "t_target": t_val, "z": HEIGHTS,
                "mean_f1": mean_f1, "std_f1": std_f1,
                "mean_f2": mean_f2, "std_f2": std_f2,
            }))
            ceil_rows.append({"series": name, "t_target": t_val,
                              "m_ceil": m_ceil, "s_ceil": s_ceil})
        # full time-height ensemble-mean dT on FULL_T_GRID (for the S9/S10 heatmaps):
        # interpolate each run onto the grid per height, then mean over runs.
        for tree, prefix in TREE_PREFIX.items():
            per_run = []
            for df in exp_data.values():
                t = df["Time (s)"].to_numpy(float)
                m = np.full((len(HEIGHTS), len(FULL_T_GRID)), np.nan)
                for i, h in enumerate(HEIGHTS):
                    col = f"{prefix}_{h} (°C)"
                    if col in df.columns:
                        y = pd.to_numeric(df[col], errors="coerce").to_numpy(float)
                        ok = ~np.isnan(y)
                        if ok.sum() >= 2:
                            m[i] = np.interp(FULL_T_GRID, t[ok], y[ok],
                                             left=np.nan, right=np.nan)
                per_run.append(m)
            with np.errstate(all="ignore"):
                mean = np.nanmean(per_run, axis=0)
            for i, h in enumerate(HEIGHTS):
                prof_full_rows.append(pd.DataFrame({
                    "series": name, "tree": tree, "t_s": FULL_T_GRID,
                    "z": h, "dT": mean[i]}))
    prof = pd.concat(prof_rows, ignore_index=True) if prof_rows else pd.DataFrame()
    ceil = pd.DataFrame(ceil_rows)
    prof_full = (pd.concat(prof_full_rows, ignore_index=True)
                 if prof_full_rows else pd.DataFrame())
    return prof, ceil, prof_full


# -------- FDS baseline overlay --------
def _read_devc(path, cols: set) -> pd.DataFrame:
    """Time plus ``cols`` of an FDS device file, from the output tree or from the
    committed baseline time series (export_fds_timeseries.py; same values, written
    as round-trip floats, time column ``t_s``)."""
    path = Path(path)
    if path.parent.resolve() == FDS_TIMESERIES.resolve():
        d = pd.read_csv(path, usecols=lambda c: c == "t_s" or c in cols, float_precision="round_trip")
        return d.rename(columns={"t_s": "Time"})
    return fds_io.read_fds_devc(path, usecols=lambda c: c == "Time" or c in cols)


def reduce_fds():
    """FDS baseline curves for the matrix overlays: extinction at z=2.3 m, the
    F1/F2 thermocouple profiles at the experiment heights, and the F1 ceiling
    (plume-impingement) thermocouple -- temperatures as dT relative to the t=0
    value (matching the experiment's zeroing). Uses the THERMOCOUPLE devices
    (TC_F1_*, TC_F2_*, TC_Ceiling_F1), which match the measured TCs in both
    position and quantity. Only the needed devc columns are parsed (usecols)."""
    # LOS k columns are derived; read the raw obscuration columns (strip '_k').
    ext_set = {c[:-2] if c.endswith("_k") else c for c in EXT_FDS_COL.values()}
    f1_cols = [f"TC_F1_{h:.1f}".replace(".", "_") for h in HEIGHTS]
    f2_cols = [f"TC_F2_{h:.1f}".replace(".", "_") for h in HEIGHTS]
    plume_col = "TC_Ceiling_F1"
    temp_set = set(f1_cols) | set(f2_cols) | {plume_col}
    ext_rows, temp_rows, plume_rows, temp_fds_full_rows = [], [], [], []
    for series in SERIES_CONFIG:
        name = series["name"]
        cand = [p for p in glob.glob(
            str(P.FDS_OUTPUT_ROOT / f"{name.lower()}_ysmatched" / "*_devc.csv"))
            if "ctrl_log" not in p]
        committed = FDS_TIMESERIES / f"{name.lower()}_ysmatched_devc.csv"
        if cand:
            path = cand[0]
            print(f"\nloading (FDS baseline): {name}")
        elif committed.exists():
            path = committed
            print(f"\nloading (FDS baseline, committed time series): {name}")
        else:
            print(f"  no FDS baseline devc for {name} (skipped)")
            continue
        de = _read_devc(path, ext_set)
        de = fds_io.add_los_extinction(de)   # -> '<beam>_k' columns used by EXT_FDS_COL
        t = de["Time"].to_numpy(float)
        for room, col in EXT_FDS_COL.items():
            if col in de.columns:
                ext_rows.append(pd.DataFrame({"series": name, "room": room,
                                              "t_s": t, "k": de[col].to_numpy(float)}))
        dt = _read_devc(path, temp_set)
        tt = dt["Time"].to_numpy(float)
        a1, a2 = dt[f1_cols].to_numpy(float), dt[f2_cols].to_numpy(float)
        pl = dt[plume_col].to_numpy(float)
        for t_val in TARGET_TIMES:
            j = int(np.argmin(np.abs(tt - t_val)))
            temp_rows.append(pd.DataFrame({"series": name, "t_target": t_val,
                                           "z": HEIGHTS,
                                           "f1": a1[j] - a1[0], "f2": a2[j] - a2[0]}))
            plume_rows.append({"series": name, "t_target": t_val,
                               "plume": float(pl[j] - pl[0])})
        # full FDS time-height dT on FULL_T_GRID (for the S9/S10 heatmaps)
        for arr, tree in ((a1, "F1"), (a2, "F2")):
            d = arr - arr[0]            # dT per height, (nT_fds, nH)
            for i, h in enumerate(HEIGHTS):
                yi = np.interp(FULL_T_GRID, tt, d[:, i], left=np.nan, right=np.nan)
                temp_fds_full_rows.append(pd.DataFrame({
                    "series": name, "tree": tree, "t_s": FULL_T_GRID,
                    "z": h, "dT": yi}))
    ext = pd.concat(ext_rows, ignore_index=True) if ext_rows else \
        pd.DataFrame(columns=["series", "room", "t_s", "k"])
    temp = pd.concat(temp_rows, ignore_index=True) if temp_rows else \
        pd.DataFrame(columns=["series", "t_target", "z", "f1", "f2"])
    plume = pd.DataFrame(plume_rows) if plume_rows else \
        pd.DataFrame(columns=["series", "t_target", "plume"])
    temp_fds_full = (pd.concat(temp_fds_full_rows, ignore_index=True)
                     if temp_fds_full_rows else pd.DataFrame())
    return ext, temp, plume, temp_fds_full


def _assert_roundtrip(path, df, float_cols):
    rb = pd.read_csv(path, float_precision="round_trip")
    for c in float_cols:
        assert np.array_equal(df[c].to_numpy(float), rb[c].to_numpy(float), equal_nan=True), \
            f"{path.name}/{c} round-trip mismatch"


def main() -> None:
    REDUCED_DIR.mkdir(parents=True, exist_ok=True)
    lem, sick, meta = reduce_extinction()
    prof, ceil, prof_full = reduce_temperature()
    ext_fds, temp_fds, plume_fds, temp_fds_full = reduce_fds()

    paths = {
        "ext_lem.csv": (lem, ["t_s", "mean", "std"]),
        "ext_sick.csv": (sick, ["t_s", "sick"]),
        "ext_meta.csv": (meta, ["m_dur", "m_vent"]),
        "temp_prof.csv": (prof, ["z", "mean_f1", "std_f1", "mean_f2", "std_f2"]),
        "temp_prof_full.csv": (prof_full, ["t_s", "z", "dT"]),
        "temp_ceil.csv": (ceil, ["m_ceil", "s_ceil"]),
        "ext_fds.csv": (ext_fds, ["t_s", "k"]),
        "temp_fds.csv": (temp_fds, ["z", "f1", "f2"]),
        "temp_fds_full.csv": (temp_fds_full, ["t_s", "z", "dT"]),
        "temp_fds_plume.csv": (plume_fds, ["plume"]),
    }
    if ext_fds.empty:
        # no FDS output tree: keep the committed FDS overlay files as they are
        for fname in ("ext_fds.csv", "temp_fds.csv", "temp_fds_full.csv", "temp_fds_plume.csv"):
            del paths[fname]
            print(f"kept committed {REDUCED_DIR / fname} (no FDS output tree)")
    for fname, (df, fcols) in paths.items():
        p = REDUCED_DIR / fname
        df.to_csv(p, index=False, lineterminator="\n")
        _assert_roundtrip(p, df, fcols)
        print(f"wrote {p} ({len(df)} rows)")
    print("round-trip OK")


if __name__ == "__main__":
    main()
