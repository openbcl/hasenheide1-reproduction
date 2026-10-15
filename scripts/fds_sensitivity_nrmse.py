"""Trace-level NRMSE of the FDS sensitivity cases vs the baseline (Table S13).

For each single-parameter case (branched from the hep_160_075_ysmatched baseline)
it computes the normalised RMSE over the pre-ventilation window between the case and
the baseline TIME SERIES -- complementing the peak-based deviations of
``fds_sensitivity_results.py``. Two quantities: the LEM line-of-sight path-mean
extinction k (rooms F1-F3) and the gas-temperature rise dT (upper-layer TC_F1_2_4,
TC_F2_2_4, and the plume-impingement TC_Ceiling_F1).

Metric details:
  A reference : each case vs the baseline (ysmatched), per sensor (FDS-vs-FDS)
  B sensors   : same as the peak analysis (fds_sensitivity_results.py)
  C window    : [0, T_END] = [0, 900] s (pre-ventilation)
  D smoothing : ROLL=11 centred rolling mean on BOTH traces before the RMSE
  E norm      : NRMSE = RMSE / baseline PEAK of that sensor  (reported as % of peak)
  F aggregate : per-room/-sensor NRMSE + a case mean across the k and dT sensors
  G grid      : the case is interpolated onto the baseline time grid

Writes results/simulation/fds_sensitivity_nrmse.csv (the NRMSE columns of Supplementary
Material Table S13) and prints a peak-vs-NRMSE comparison.

    python scripts/fds_sensitivity_nrmse.py
"""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

import paths as P
from fds_io import add_los_extinction

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "simulation" / "fds_sensitivity_nrmse.csv"
PEAK_CSV = REPO / "results" / "simulation" / "fds_sensitivity.csv"

T_END = 900.0
ROLL = 11
EXT = {"F1": "LEM_LOS_F1_2_3_k", "F2": "LEM_LOS_F2_2_3_k", "F3": "LEM_LOS_F3_2_3_k"}
EXT_RAW = {"LEM_LOS_F1_2_3", "LEM_LOS_F2_2_3", "LEM_LOS_F3_2_3"}
T_UP = {"F1": "TC_F1_2_4", "F2": "TC_F2_2_4"}
T_CEIL = "TC_Ceiling_F1"

# same CASES as fds_sensitivity_results.py (baseline first)
CASES = [
    ("Baseline",          "baseline",             "ysmatched"),
    ("Soot yield",        "$Y_s=0.030$",          "ys030"),
    ("Soot yield",        "$Y_s=0.049$",          "ys049"),
    ("Fuel substitution", "$Y_s=0.015$",          "ys015"),
    ("Radiative fraction", "$\\chi_r=0.35$",      "chir035"),
    ("Radiative fraction", "$\\chi_r=0.50$",      "chir050"),
    ("Grid resolution",   "uniform $50$~mm",      "uni50"),
    ("Grid resolution",   "uniform $25$~mm",      "uni25"),
    ("Grid resolution",   "$12.5/25$~mm",         "dx12"),
    ("Fire-source area",  "$175\\times175$~mm",   "pan175"),
    ("Heat of combustion", "fuel-specific $E$",   "dhc_e127"),
    ("Turbulence model",  "Vreman",               "vreman"),
    ("Turbulence model",  "dyn.\\ Smagorinsky",   "dynsmag"),
    ("Leakage area",      "sealed",               "sealed"),
    ("Leakage area",      "$n_{50}{\\approx}20$", "leak08"),
    # humid-air variants (*_rh): the explicit-chemistry decks carry the baseline's
    # background air (fds_decks/README.md); the control has deposition off
    ("Soot deposition",   "$d_p=0.1~\\upmu$m",    "sootdep_d01_rh"),
    ("Soot deposition",   "$d_p=1~\\upmu$m",      "sootdep_d1_rh"),
    ("Soot deposition",   "$d_p=10~\\upmu$m",     "sootdep_d10_rh"),
    ("Soot deposition",   "agglom.\\ (binned)",   "sootdep_binned_rh"),
    ("Soot deposition",   "control, no deposition", "explchem_nodep_rh"),
]


def ambient_T() -> float:
    d = pd.read_csv(P.RESULTS_DIR / "measurement" / "ambient.csv").set_index("series")
    return float(d.loc["Hep_160_075", "T_mean"])


def load_series(run: str, t_amb: float):
    """(time, {sensor: ROLL-smoothed series}) over [0, T_END], or None if absent."""
    files = glob.glob(str(P.FDS_OUTPUT_ROOT / f"hep_160_075_{run}" / "*_devc.csv"))
    if not files:
        return None
    need = EXT_RAW | set(T_UP.values()) | {T_CEIL}
    df = pd.read_csv(files[0], skiprows=1,
                     usecols=lambda c: c in need or c.lower().startswith("time") or c == "s")
    df = add_los_extinction(df)
    tcol = [c for c in df.columns if c.lower().startswith("time") or c == "s"][0]
    df = df[df[tcol] <= T_END].reset_index(drop=True)
    t = df[tcol].to_numpy()

    def sm(series):
        return series.rolling(ROLL, center=True, min_periods=1).mean().to_numpy()

    out = {f"k_{r}": sm(df[c]) for r, c in EXT.items()}
    for r, c in T_UP.items():
        out[f"dT_{r}"] = sm(df[c] - t_amb)
    out["dT_ceil"] = sm(df[T_CEIL] - t_amb)
    return t, out


def main() -> None:
    t_amb = ambient_T()
    base = load_series("ysmatched", t_amb)
    if base is None:
        print("  baseline (ysmatched) output not present -- aborting")
        return
    tb, bser = base
    bpeak = {k: float(np.nanmax(v)) for k, v in bser.items()}
    sensors = list(bser.keys())

    rows = []
    absent = []
    for group, label, run in CASES:
        if run == "ysmatched":
            continue
        s = load_series(run, t_amb)
        if s is None:
            absent.append(run)
            continue
        tc, cser = s
        rec = dict(group=group, case=label, run=run)
        for key in sensors:
            cy = np.interp(tb, tc, cser[key])            # onto baseline grid (G)
            rmse = float(np.sqrt(np.nanmean((cy - bser[key]) ** 2)))
            rec[f"nrmse_{key}"] = 100.0 * rmse / bpeak[key] if bpeak[key] else np.nan
        rec["nrmse_k_mean"] = float(np.nanmean([rec[f"nrmse_k_{r}"] for r in EXT]))
        rec["nrmse_dT_mean"] = float(np.nanmean(
            [rec["nrmse_dT_F1"], rec["nrmse_dT_F2"], rec["nrmse_dT_ceil"]]))
        rows.append(rec)

    if absent:
        print(f"  skipping cases without FDS output yet: {', '.join(absent)}")
    nr = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    nr.to_csv(OUT, index=False)

    # side-by-side with the peak-based deviations
    if PEAK_CSV.exists():
        peak = pd.read_csv(PEAK_CSV)
        m = nr.merge(peak[["run", "dk_mean_pct", "dk_F1_pct", "dk_F2_pct",
                           "dk_F3_pct", "dTu_pct"]], on="run", how="left")
        print("\n=== peak deviation (signed) vs trace NRMSE (unsigned, % of baseline peak) ===")
        print(f"{'case':<22} {'dk_peak%':>9} {'NRMSE_k%':>9} | "
              f"{'dTu_peak%':>10} {'NRMSE_dT%':>10}")
        for _, r in m.iterrows():
            print(f"{r['case']:<22} {r['dk_mean_pct']:+9.1f} {r['nrmse_k_mean']:9.1f} | "
                  f"{r['dTu_pct']:+10.1f} {r['nrmse_dT_mean']:10.1f}")

    print(f"\nwrote {OUT} ({len(nr)} cases)")


if __name__ == "__main__":
    main()
