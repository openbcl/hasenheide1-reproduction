"""Optics fouling at the moment the validation peak is taken.

The uncertainty budget carries a fouling row for the 75/150 g fires, but the
only directly observable fouling number is the *end-of-experiment* residual:
during the fire the deposit is inseparable from the smoke signal, and it can
only be read once the room has been ventilated clear and the true extinction has
returned to zero. The budget's peak-time figure was therefore an assertion
resting on a monotonicity argument ("fouling accumulates, so it is smaller at
the earlier, higher-extinction instants") rather than a computed value.

This reducer computes it. Deposition onto the optics is, to first order,
proportional to the local soot concentration, so the deposit accumulated by time
t follows the exposure integral of the extinction coefficient:

    fouling(t) ~ R_end * int_0^t k dt' / int_0^t_vent k dt'

with the measured end-of-experiment residual R_end (results/measurement/fouling_residuals.csv)
setting the scale. Evaluated at the time of the validation peak, this converts
the asserted bound into a number, and expresses it relative to the peak k that
the validation statistic is actually built on.

CAVEATS, both of which push the estimate the same (conservative) way:
  * the measured k already contains the growing fouling, so the exposure
    integral is mildly self-referential -- negligible while fouling << k during
    the fire, which is the regime here;
  * the linear-in-exposure model has no saturation, whereas a real deposit
    layer shadows itself, so a true deposit grows sub-linearly and the estimate
    is an upper bound at the peak.

Integration runs to ventilation onset (the residual is read after that, but no
further deposition happens once the smoke is cleared).

Writes results/measurement/fouling_at_peak.csv. Reads the locally re-processed records in
data/reprocessed (scripts/reprocess_unclipped.py), not the raw records directly.
Run: python reduce_fouling_at_peak.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import measurement_io as mio
import paths as P
from paths import SUB_PROCESSED

BASE = Path(__file__).resolve().parent.parent / "data" / "reprocessed"
T_START, T_END = -60, 3600
ROLL = 11  # same centred rolling mean the validation peaks use

SERIES = {
    "075": ["Hep_160_S2_R1", "Hep_160_S2_R2", "Hep_160_S2_R3",
            "Hep_160_S3_R1", "Hep_160_S3_R2", "Hep_160_S4_R1", "Hep_160_S4_R2"],
    "150": ["Hep_160_S1_R1", "Hep_160_S1_R2", "Hep_160_S1_R3"],
    "220": ["Hep_220_S1_R1", "Hep_220_S1_R2", "Hep_220_S1_R3", "Hep_220_S1_R4"],
}
RUN2SERIES = {r: s for s, v in SERIES.items() for r in v}
RUNS = [r for v in SERIES.values() for r in v]


def main() -> int:
    resid_f = P.RESULTS_DIR / "measurement" / "fouling_residuals.csv"
    if not resid_f.exists():
        print(f"missing {resid_f} (run explore_fouling.py first)")
        return 1
    resid = pd.read_csv(resid_f).set_index(["run", "device"]).fouling_resid_1pm

    if not BASE.exists():
        print(f"re-processed records not present ({BASE}) -- skipping")
        return 0

    print("Loading full records ...")
    exp, dur, vent = mio.load_runs(BASE, RUNS, T_START, T_END, SUB_PROCESSED)

    rows = []
    for run in RUNS:
        df = exp.get(run)
        if df is None:
            continue
        t = df["Time (s)"].to_numpy(dtype=float)
        t_vent = float(vent.get(run, np.nan))
        for col in [c for c in df.columns if c.startswith("Extinction")]:
            # fouling_residuals.csv keys devices by the short label used in
            # explore_fouling.short_label, not by the raw column name
            device = col.replace("Extinction ", "").replace(" (1/m)", "").replace("_corr", "")
            key = (run, device)
            if key not in resid.index:
                continue
            k = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
            ks = pd.Series(k).rolling(ROLL, center=True, min_periods=1).mean().to_numpy()

            fire = np.isfinite(ks) & (t >= 0) & (t <= t_vent)
            if fire.sum() < 10:
                continue
            i_pk = np.nanargmax(np.where(fire, ks, np.nan))
            t_pk, k_pk = t[i_pk], ks[i_pk]

            up_to_peak = fire & (t <= t_pk)
            expo_pk = np.trapezoid(ks[up_to_peak], t[up_to_peak])
            expo_tot = np.trapezoid(ks[fire], t[fire])
            if not np.isfinite(expo_tot) or expo_tot <= 0:
                continue
            frac = expo_pk / expo_tot
            r_end = float(resid.loc[key])
            f_pk = r_end * frac

            rows.append({
                "run": run, "series": RUN2SERIES[run], "device": device,
                "t_peak_s": round(float(t_pk), 1), "k_peak_1pm": round(float(k_pk), 4),
                "resid_end_1pm": round(r_end, 4),
                "exposure_frac_at_peak": round(float(frac), 4),
                "fouling_at_peak_1pm": round(float(f_pk), 5),
                "fouling_at_peak_pct_of_k": round(100 * f_pk / k_pk, 2),
                "resid_end_pct_of_k": round(100 * r_end / k_pk, 2),
            })

    if not rows:
        print("nothing computed")
        return 1

    d = pd.DataFrame(rows)
    P.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    f = P.RESULTS_DIR / "measurement" / "fouling_at_peak.csv"
    d.to_csv(f, index=False)
    print(f"\n{len(d)} device-runs -> {f}\n")

    print("relative fouling at the validation peak [% of peak k]")
    print(d.groupby("series")[["fouling_at_peak_pct_of_k", "resid_end_pct_of_k"]]
          .max().round(1).rename(columns={
              "fouling_at_peak_pct_of_k": "at peak (max)",
              "resid_end_pct_of_k": "end-of-run (max)"}).to_string())
    small = d[d.series.isin(("075", "150"))]
    print(f"\n75/150 g fires: worst case at peak = "
          f"{small.fouling_at_peak_pct_of_k.max():.1f} % of the peak k "
          f"(budget row states < 5 %)")
    print(f"   mean exposure fraction reached at the peak: "
          f"{small.exposure_frac_at_peak.mean():.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
