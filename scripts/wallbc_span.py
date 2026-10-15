"""Wall thermal-BC bracket for the FDS sensitivity study (Supplementary Material: FDS sensitivity study).

The baseline uses thermally active (conducting) surfaces. This reducer brackets
the wall thermal boundary condition with two limiting cases -- perfectly
conducting cold walls held at ambient (INERT) and adiabatic walls (no heat loss)
-- and reports their peak-quantity deviation from the baseline. All three runs
(baseline + the two wall cases) are on the FDS 6.11.1 release, which fixes the
LEAK_PATH / fixed-temperature-wall interaction (firemodels/fds #16337), so the
comparison is build-consistent; the baseline here is the production
configuration-matched conducting run (hep_160_075_ysmatched, Y_s=0.0328), and the
two wall cases carry the identical soot yield, so the wall-BC deviation is
isolated from any soot-loading offset. Peaks: light extinction k at the LEM z=2.3 m stations as
line-of-sight PATH OBSCURATION beams (add_los_extinction), and the upper-layer /
ceiling gas-temperature rise above ambient. Taken from an 11-sample centred
rolling mean over the sealed-enclosure window.

Writes
  results/simulation/wallbc_span.csv          (per quantity: baseline/inert/adiabatic + deviation)
  results/simulation/wallbc_span_summary.csv  (headline max-|deviation| values for numbers.tex)

    python scripts/wallbc_span.py
"""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

import paths as P
from fds_io import read_fds_devc, add_los_extinction

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = REPO_ROOT / "results" / "simulation" / "wallbc_span.csv"
SUM_CSV = REPO_ROOT / "results" / "simulation" / "wallbc_span_summary.csv"

T_END = 900.0
ROLL = 11
RUNS = {"baseline": "hep_160_075_ysmatched", "inert": "hep_160_075_inert",
        "adiabatic": "hep_160_075_adiabatic"}
# extinction at the LEM z=2.3 m stations as line-of-sight beams -> path-mean k
EXT = {"k_F1": "LEM_LOS_F1_2_3_k", "k_F2": "LEM_LOS_F2_2_3_k", "k_F3": "LEM_LOS_F3_2_3_k"}
EXT_RAW = {"LEM_LOS_F1_2_3", "LEM_LOS_F2_2_3", "LEM_LOS_F3_2_3"}
# upper-layer (2.4 m) thermocouples and the F1 plume-impingement ceiling
TU = {"Tu_F1": "TC_F1_2_4", "Tu_F2": "TC_F2_2_4"}
TCEIL = {"Tceil_F1": "TC_Ceiling_F1"}


def ambient_T() -> float:
    d = pd.read_csv(P.RESULTS_DIR / "measurement" / "ambient.csv").set_index("series")
    return float(d.loc["Hep_160_075", "T_mean"])


def peaks(run: str, t_amb: float) -> dict:
    files = glob.glob(str(P.FDS_OUTPUT_ROOT / run / "*_devc.csv"))
    if not files:
        return {}
    need = EXT_RAW | set(TU.values()) | set(TCEIL.values())
    df = read_fds_devc(files[0], usecols=lambda c: c in need
                       or c.lower().startswith("time") or c == "s")
    df = add_los_extinction(df)
    tcol = [c for c in df.columns if c.lower().startswith("time") or c == "s"][0]
    df = df[df[tcol] <= T_END]

    def pk(col):
        return float(df[col].rolling(ROLL, center=True, min_periods=1).mean().max())

    out = {q: pk(c) for q, c in EXT.items()}
    out.update({q: pk(c) - t_amb for q, c in {**TU, **TCEIL}.items()})
    return out


def main() -> None:
    t_amb = ambient_T()
    pk = {name: peaks(chid, t_amb) for name, chid in RUNS.items()}
    absent = [n for n, p in pk.items() if not p]
    if absent:
        print(f"  wall-BC runs not present, skipping: {', '.join(absent)}")
        return
    base = pk["baseline"]

    quantities = list(EXT) + list(TU) + list(TCEIL)
    rows = []
    for q in quantities:
        rows.append(dict(
            quantity=q,
            group="extinction" if q.startswith("k_") else "temperature",
            baseline=round(base[q], 4),
            inert=round(pk["inert"][q], 4),
            adiabatic=round(pk["adiabatic"][q], 4),
            inert_dev_pct=round((pk["inert"][q] / base[q] - 1) * 100, 2),
            adiab_dev_pct=round((pk["adiabatic"][q] / base[q] - 1) * 100, 2),
        ))
    df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    ext = df[df["group"] == "extinction"]
    tu = df[df["quantity"].isin(TU)]        # upper-layer only (exclude ceiling)
    summary = dict(
        # extinction: max |deviation| over both wall cases and all rooms
        ext_max_abs_pct=round(float(np.max(np.abs(
            ext[["inert_dev_pct", "adiab_dev_pct"]].to_numpy()))), 1),
        # cold-wall (inert) upper-layer temperature: max |deviation|
        temp_cold_max_abs_pct=round(float(np.max(np.abs(tu["inert_dev_pct"]))), 1),
        # adiabatic upper-layer temperature: max deviation (the large positive bound)
        temp_adiab_max_pct=round(float(np.max(tu["adiab_dev_pct"])), 1),
    )
    pd.DataFrame([summary]).to_csv(SUM_CSV, index=False)
    print(df.to_string(index=False))
    print("\nsummary:", summary)
    print(f"\nwrote {OUT_CSV}\nwrote {SUM_CSV}")


if __name__ == "__main__":
    main()
