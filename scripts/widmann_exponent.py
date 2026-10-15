"""Differential test of the Widmann wavelength correlation from committed data.

The wavelength normalisation (measurement_io.widmann_norm_factor) rescales every
instrument to 638 nm assuming K_m ~ lambda^-1.0088 (Widmann 2003). After that
rescaling, any residual wavelength trend between co-located channels measures the
deviation of the smoke's effective exponent n_true from the Widmann value: a
normalised extinction scales as k_norm(lambda) ~ lambda^(N_W - n_true), so the
LEM/SICK ratio tests the exponent differentially while everything channel-common
(absolute K_m level, sampling geometry, a shared calibration factor) cancels.

LEM (638 nm) vs wavelength-corrected SICK (880 nm), co-located line-of-sight: per
run in results/validation/matrices/ext_sick.csv, the median smoke-bearing ratio to the LEM
ensemble mean gives n_true = N_W - ln(r)/ln(880/638). Median + IQR + range across
runs.

Writes results/measurement/widmann_exponent.csv:
  test, n, n_median, lo, hi, n_min, n_max, factor_dev_pct
where lo/hi is the across-run IQR and factor_dev_pct is the implied error of the
applied normalisation factors over the 638-880 nm span at the median exponent,
(880/638)^|n_median - N_W| - 1.

Run:  python widmann_exponent.py   (committed inputs only)
"""
import numpy as np
import pandas as pd

from paths import RESULTS_DIR

N_W = 1.0088                      # Widmann exponent (measurement_io.widmann_norm_factor)
LAM_LEM, LAM_SICK = 638.0, 880.0
K_THRESH = 0.10                   # smoke-bearing threshold
MIN_SAMPLES = 30                  # minimum paired samples per SICK run


def lem_sick_test() -> dict:
    """Per-run exponent from the co-located LEM/SICK ratio (638 vs 880 nm)."""
    lem = pd.read_csv(RESULTS_DIR / "validation" / "matrices" / "ext_lem.csv")
    sick = pd.read_csv(RESULTS_DIR / "validation" / "matrices" / "ext_sick.csv")
    meta = pd.read_csv(RESULTS_DIR / "validation" / "matrices" / "ext_meta.csv"
                       ).set_index(["series", "room"])
    lnspan = np.log(LAM_SICK / LAM_LEM)
    n_runs = []
    for (series, room, _run), g in sick.groupby(["series", "room", "run"]):
        lm = lem[(lem.series == series) & (lem.room == room)
                 ].set_index("t_s")["mean"]
        g = g.set_index("t_s")
        t = g.index.intersection(lm.index)
        t = t[(t > 0) & (t < meta.loc[(series, room), "m_vent"])]
        kl, ks = lm.loc[t].to_numpy(float), g.loc[t, "sick"].to_numpy(float)
        mask = (kl > K_THRESH) & (ks > 0)
        if mask.sum() < MIN_SAMPLES:
            continue
        r = float(np.median(ks[mask] / kl[mask]))
        n_runs.append(N_W - np.log(r) / lnspan)
    n_runs = np.asarray(n_runs, float)
    q1, med, q3 = np.percentile(n_runs, [25, 50, 75])
    return dict(test="lem_sick", n=int(n_runs.size), n_median=float(med),
                lo=float(q1), hi=float(q3),
                n_min=float(n_runs.min()), n_max=float(n_runs.max()),
                factor_dev_pct=100.0 * ((LAM_SICK / LAM_LEM)
                                        ** abs(float(med) - N_W) - 1.0))


def main() -> None:
    rows = [lem_sick_test()]
    df = pd.DataFrame(rows)
    out = RESULTS_DIR / "measurement" / "widmann_exponent.csv"
    df.to_csv(out, index=False, lineterminator="\n")
    print(f"Wrote {out}")
    for r in rows:
        print(f"  {r['test']:>9}: n={r['n']:3d}  n_med={r['n_median']:.3f} "
              f"[{r['lo']:.3f}, {r['hi']:.3f}]  range {r['n_min']:.3f}"
              f"-{r['n_max']:.3f}  factor dev {r['factor_dev_pct']:.1f}%"
              f"  (Widmann {N_W})")


if __name__ == "__main__":
    main()
