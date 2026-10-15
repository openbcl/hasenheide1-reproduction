"""Reducer for the FDS sensitivity study (Supplementary Material: FDS sensitivity study).

For each single-parameter case (branched from the hep_160_075_ysmatched baseline) it
computes the peak validation quantities -- light extinction k at the LEM heights
(z = 2.3 m, rooms F1-F3) and the peak upper-layer / ceiling gas-temperature rise
above ambient -- and their relative deviation from the baseline. Peaks are taken
from an 11-sample centred rolling mean over the sealed-enclosure window.

Axis set: soot yield, fuel substitution,
radiative fraction, grid resolution, fire-source area, turbulence model, leakage
area, soot deposition; plus the heat-of-combustion case (fuel-specific
oxygen-consumption constant), which is reported in Table S13 and the text but is
not a tornado axis. The wall thermal BC is handled separately as a limiting-case bracket
(cold-wall / adiabatic, computed on FDS 6.11.1; see wallbc_span.py and
Supplementary Material S13), not as a single-parameter axis of this tornado.

Writes
  results/simulation/fds_sensitivity.csv          (per case: peaks + deviation vs baseline)
  results/simulation/fds_sensitivity_summary.csv  (dominant-axis headline values)

    python scripts/fds_sensitivity_results.py
"""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

import paths as P
from fds_io import add_los_extinction

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = REPO_ROOT / "results" / "simulation" / "fds_sensitivity.csv"
SUM_CSV = REPO_ROOT / "results" / "simulation" / "fds_sensitivity_summary.csv"

T_END = 900.0
ROLL = 11
# Extinction at the LEM z=2.3 m stations as as-built line-of-sight PATH
# OBSCURATION beams -> path-mean k (add_los_extinction, LEM L=0.81 m).
EXT = {"F1": "LEM_LOS_F1_2_3_k", "F2": "LEM_LOS_F2_2_3_k", "F3": "LEM_LOS_F3_2_3_k"}
EXT_RAW = {"LEM_LOS_F1_2_3", "LEM_LOS_F2_2_3", "LEM_LOS_F3_2_3"}  # obscuration cols to read
# upper-layer thermocouples (2.4 m) in the two rooms with an upper-layer
# comparison (F1 fire room, F2 remote), plus the F1 plume-impingement ceiling.
T_UP = {"F1": "TC_F1_2_4", "F2": "TC_F2_2_4"}
T_CEIL = "TC_Ceiling_F1"

# (group, case label, run suffix).  Baseline first.
CASES = [
    ("Baseline",         "baseline",            "ysmatched"),
    ("Soot yield",       "$Y_s=0.030$",         "ys030"),
    ("Soot yield",       "$Y_s=0.049$",         "ys049"),
    ("Fuel substitution", "$Y_s=0.015$",        "ys015"),
    ("Radiative fraction", "$\\chi_r=0.35$",    "chir035"),
    ("Radiative fraction", "$\\chi_r=0.50$",    "chir050"),
    ("Grid resolution",  "uniform $50$~mm",     "uni50"),
    ("Grid resolution",  "uniform $25$~mm",     "uni25"),
    ("Grid resolution",  "$12.5/25$~mm",        "dx12"),
    ("Fire-source area", "$175\\times175$~mm",  "pan175"),
    # fuel-specific oxygen-consumption constant (12.686 instead of
    # 13.1 MJ/kg O2) -> RAMP_Q and HEAT_OF_COMBUSTION x 0.968, fuel/soot rate unchanged
    ("Heat of combustion", "fuel-specific $E$", "dhc_e127"),
    ("Turbulence model", "Vreman",              "vreman"),
    ("Turbulence model", "dyn.\\ Smagorinsky",  "dynsmag"),
    ("Leakage area",     "sealed",              "sealed"),
    ("Leakage area",     "$n_{50}{\\approx}20$", "leak08"),
    # humid-air variants (*_rh): the explicit-chemistry decks carry the baseline's
    # background air (fds_decks/README.md); the control has deposition off
    ("Soot deposition",  "$d_p=0.1~\\upmu$m",   "sootdep_d01_rh"),
    ("Soot deposition",  "$d_p=1~\\upmu$m",     "sootdep_d1_rh"),
    ("Soot deposition",  "$d_p=10~\\upmu$m",    "sootdep_d10_rh"),
    ("Soot deposition",  "agglom.\\ (binned)",  "sootdep_binned_rh"),
    ("Soot deposition",  "control, no deposition", "explchem_nodep_rh"),
]


def ambient_T() -> float:
    d = pd.read_csv(P.RESULTS_DIR / "measurement" / "ambient.csv").set_index("series")
    return float(d.loc["Hep_160_075", "T_mean"])


def peaks(run: str, t_amb: float):
    files = glob.glob(str(P.FDS_OUTPUT_ROOT / f"hep_160_075_{run}" / "*_devc.csv"))
    if not files:
        return None  # FDS run not present yet (e.g. a freshly added case); skip
    f = files[0]
    need = EXT_RAW | set(T_UP.values()) | {T_CEIL}
    df = pd.read_csv(f, skiprows=1,
                     usecols=lambda c: c in need or c.lower().startswith("time") or c == "s")
    df = add_los_extinction(df)   # -> '<beam>_k' columns used by EXT
    tcol = [c for c in df.columns if c.lower().startswith("time") or c == "s"][0]
    df = df[df[tcol] <= T_END]

    def pk(col):
        return float(df[col].rolling(ROLL, center=True, min_periods=1).mean().max())

    out = {f"k_{r}": pk(c) for r, c in EXT.items()}
    out.update({f"dTu_{r}": pk(c) - t_amb for r, c in T_UP.items()})
    out["dTc"] = pk(T_CEIL) - t_amb
    out["k_mean"] = float(np.mean([out[f"k_{r}"] for r in EXT]))
    return out


def main() -> None:
    t_amb = ambient_T()
    pk = {run: peaks(run, t_amb) for _, _, run in CASES}
    absent = [r for r, p in pk.items() if p is None]
    if absent:
        print(f"  skipping cases without FDS output yet: {', '.join(absent)}")
    pk = {r: p for r, p in pk.items() if p is not None}
    base = pk["ysmatched"]

    def dev(p, key):
        return (p[key] / base[key] - 1) * 100.0

    rows = []
    for group, label, run in CASES:
        if run not in pk:
            continue
        p = pk[run]
        rows.append(dict(
            group=group, case=label, run=run,
            k_F1=p["k_F1"], k_F2=p["k_F2"], k_F3=p["k_F3"], k_mean=p["k_mean"],
            dTu_F1=p["dTu_F1"], dTu_F2=p["dTu_F2"], dTc=p["dTc"],
            dk_mean_pct=dev(p, "k_mean"),
            dk_F1_pct=dev(p, "k_F1"), dk_F2_pct=dev(p, "k_F2"), dk_F3_pct=dev(p, "k_F3"),
            dTu_F1_pct=dev(p, "dTu_F1"), dTu_F2_pct=dev(p, "dTu_F2"),
            # aliases for the F1 upper layer
            dTu=p["dTu_F1"], dTu_pct=dev(p, "dTu_F1"),
        ))
    df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    # dominant-axis headline: largest |peak-k| swing (excluding baseline)
    nb = df[df.run != "ysmatched"].copy()
    nb["abs_dk"] = nb["dk_mean_pct"].abs()
    top = nb.loc[nb["abs_dk"].idxmax()]
    pd.DataFrame([dict(
        dominant_axis=top["group"], dominant_case=top["case"],
        dominant_dk_mean_pct=float(top["dk_mean_pct"]),
        radfrac_dTu_span_pct=float(
            nb[nb.group == "Radiative fraction"]["dTu_pct"].abs().max()),
        max_abs_dTu_pct=float(nb["dTu_pct"].abs().max()),
    )]).to_csv(SUM_CSV, index=False)

    print(f"wrote {OUT_CSV} ({len(df)} rows)")
    show = df[["group", "case", "k_mean", "dk_mean_pct", "dTu", "dTu_pct"]]
    print(show.to_string(index=False, float_format="{:+.1f}".format))
    print(f"\nDominant extinction axis: {top['group']} ({top['case']}) "
          f"{top['dk_mean_pct']:+.1f}%")


if __name__ == "__main__":
    main()
