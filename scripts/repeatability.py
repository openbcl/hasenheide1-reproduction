"""Run-to-run repeatability of the experimental measurements quantified for the
three ensemble figures: HRR (Fig.~3), temperature (Supplementary Material) and
extinction (Fig.~4). The metric is the run-to-run relative standard deviation (coefficient
of variation, Bessel-corrected) of the ensemble over the meaningful signal
window, reported per series.

  - HRR:         burn duration, mean Q-dot and peak Q-dot from the per-trial
                 summaries; plus the time-resolved Q-dot(t) band (rolled
                 ensemble std / mean over the burning phase).
  - Temperature: plume-impingement temperature rise dT, over t where the
                 ensemble mean exceeds 50% of its peak (relative threshold, so
                 it adapts to the different fire sizes).
  - Extinction:  LEM extinction at z = 2.3 m in each room, over the smoke-laden
                 phase (ensemble mean k > 0.05 1/m, before ventilation).

Read-only with respect to the raw records. Run:  python scripts/repeatability.py
"""
import numpy as np
import pandas as pd
from pathlib import Path
import measurement_io as mio
import paths as P

MEAS = P.MEAS_ROOT
HRR = P.HRR_ROOT

SERIES = {
    "075": ["Hep_160_S2_R1", "Hep_160_S2_R2", "Hep_160_S2_R3",
            "Hep_160_S3_R1", "Hep_160_S3_R2", "Hep_160_S4_R1", "Hep_160_S4_R2"],
    "150": ["Hep_160_S1_R1", "Hep_160_S1_R2", "Hep_160_S1_R3"],
    "220": ["Hep_220_S1_R1", "Hep_220_S1_R2", "Hep_220_S1_R3", "Hep_220_S1_R4"],
}
HRR_FOLD = {"075": "hep_160_075_hrr", "150": "hep_160_150_hrr",
            "220": "hep_220_300_hrr"}
LEM_23 = {"F1": "Extinction LEM_4_F1_2.3 (1/m)",
          "F2": "Extinction LEM_3_F2_2.3 (1/m)",
          "F3": "Extinction LEM_2_F3_2.3 (1/m)"}
VENT = {"075": 900, "150": 1200, "220": 1200}


def cv(x):
    """Relative standard deviation (%) across trials (Bessel-corrected)."""
    x = np.asarray(x, float)
    return np.std(x, ddof=1) / np.mean(x) * 100


def band_relsd(t, mean, std, window):
    """Median over `window` of |ensemble_std / ensemble_mean| in percent."""
    m, s = np.asarray(mean, float), np.asarray(std, float)
    g = window & np.isfinite(m) & np.isfinite(s) & (np.abs(m) > 1e-9)
    return np.nanmedian(np.abs(s[g] / m[g])) * 100 if g.sum() > 3 else np.nan


# --- HRR (Fig. 3) -----------------------------------------------------------
print("=== HRR (Fig. 3): run-to-run relative SD ===")
print("series  n | burn_dur | mean_Q | peak_Q | Q(t) band (median, burning)")
agg = {}
for s, fold in HRR_FOLD.items():
    ts = pd.read_csv(HRR / fold / "HRR_trial_summary.csv")
    en = pd.read_csv(HRR / fold / "HRR_ensemble_stats.csv")
    t = en["t_s"].values
    m, sd = en["HRR_roll_mean_kW"].values, en["HRR_roll_std_kW"].values
    dur = np.median(ts["burning_duration_s"])
    win = (t > 0) & (t <= dur) & (m > 0.2 * np.nanmax(m))
    bd, mq, pq = (cv(ts['burning_duration_s']), cv(ts['HRR_avg_kW']),
                  cv(ts['HRR_peak_kW']))
    qb = band_relsd(t, m, sd, win)
    agg[s] = dict(series=s, n=len(ts), burn_dur_cv_pct=bd, meanQ_cv_pct=mq,
                  peakQ_cv_pct=pq, Q_band_pct=qb)
    print(f"  {s}  {len(ts):2d} |  {bd:4.1f}%  |  {mq:4.1f}% | {pq:5.1f}% |  {qb:4.0f}%")

# --- Temperature (Supplementary) + Extinction (Fig. 4) ----------------------
print("\n=== Temperature (Suppl.) + Extinction (Fig. 4): run-to-run relative SD ===")
print("series  n | plume dT (>50% peak) | extinction k>0.05  F1 / F2 / F3")
for s, runs in SERIES.items():
    exp, _, _ = mio.load_runs(MEAS, runs, -30, 1200, "1_Processed_data")
    md, sd = mio.ensemble_stats(exp, -30, 1200)
    t = md["Time (s)"].values.astype(float)
    vt = VENT[s]
    # temperature: plume impingement, relative threshold
    col = "Plume Impingement Temperature (°C)"
    m = pd.to_numeric(md[col], errors="coerce").values
    sdc = pd.to_numeric(sd[col], errors="coerce").values
    pk = np.nanmax(m[(t >= 0) & (t <= 450)])
    t_relsd = band_relsd(t, m, sdc, (t >= 0) & (t <= 450) & (m > 0.5 * pk))
    # extinction: LEM 2.3 m per room, smoke-laden
    ext = []
    for room, c in LEM_23.items():
        if c in md.columns:
            mk = pd.to_numeric(md[c], errors="coerce").values
            ext.append(band_relsd(t, mk, pd.to_numeric(sd[c], errors="coerce").values,
                                   (t >= 0) & (t <= vt) & (mk > 0.05)))
        else:
            ext.append(np.nan)
    agg.setdefault(s, dict(series=s)).update(
        dict(temp_relsd_pct=t_relsd, ext_F1_pct=ext[0], ext_F2_pct=ext[1],
             ext_F3_pct=ext[2]))
    print(f"  {s}  {len(runs):2d} |        {t_relsd:4.0f}%        |  "
          + " / ".join(f"{x:3.0f}%" if np.isfinite(x) else " na" for x in ext))

# --- committed reduced CSV ------------------
P.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
_out = P.RESULTS_DIR / "measurement" / "repeatability.csv"
pd.DataFrame(list(agg.values())).to_csv(_out, index=False)
print(f"\n-> {_out}")
