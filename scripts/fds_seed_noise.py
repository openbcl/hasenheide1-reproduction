"""LES noise floor of the FDS sensitivity study from random-seed replicates (SM S13, Fig. 7).

FDS is deterministic, so the baseline alone shows no run-to-run variability. The seed
replicates hep_160_075_seed<N> (fds_decks/README.md; identical to the baseline
except RND_SEED) decorrelate the turbulence; their spread around the baseline is the noise
floor, NOT a sensitivity axis. Every single-parameter case also decorrelates the
turbulence, so its delta to the baseline contains noise of this size.

Same peak method as fds_sensitivity_results.py (11-sample centred rolling mean over
[0, 900] s; LEM line-of-sight k at z = 2.3 m in F1-F3, upper-layer dT in F1/F2, F1
ceiling dT) and the same trace NRMSE as fds_sensitivity_nrmse.py.

Writes (used by the tornado figure and the \valSeed* macros, checked by scripts/check_numbers.py)
  results/simulation/fds_seed_noise.csv        per quantity: baseline, each seed, deviation, ensemble SD
  results/simulation/fds_seed_noise_axes.csv   per sensitivity case and quantity: |delta| vs the noise
  and prints the .out warning comparison of each seed run against the baseline.

    python scripts/fds_seed_noise.py [--seeds 101 202 303]
"""
from __future__ import annotations

import argparse
import glob
import re

import numpy as np
import pandas as pd

import paths as P
import fds_sensitivity_results as SR
import fds_sensitivity_nrmse as NR

OUT = P.SIM_RESULTS / "fds_seed_noise.csv"
OUT_AXES = P.SIM_RESULTS / "fds_seed_noise_axes.csv"
QTY = ["k_F1", "k_F2", "k_F3", "k_mean", "dTu_F1", "dTu_F2", "dTc"]
# column of results/simulation/fds_sensitivity.csv holding the case deviation of each quantity
CASE_COL = {"k_F1": "dk_F1_pct", "k_F2": "dk_F2_pct", "k_F3": "dk_F3_pct",
            "k_mean": "dk_mean_pct", "dTu_F1": "dTu_F1_pct", "dTu_F2": "dTu_F2_pct"}


def warnings(run: str) -> tuple[list[str] | None, bool]:
    files = glob.glob(str(P.FDS_OUTPUT_ROOT / f"hep_160_075_{run}" / "*.out"))
    if not files:
        return None, False
    txt = open(files[0], encoding="utf-8", errors="replace").read()
    w = sorted({re.sub(r"\s+", " ", m).strip() for m in re.findall(r"WARNING[^\n]*", txt)})
    return w, "FDS completed successfully" in txt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[101, 202, 303])
    args = ap.parse_args()
    t_amb = SR.ambient_T()
    base = SR.peaks("ysmatched", t_amb)
    if base is None:
        print("baseline output not found -- aborting")
        return 1
    runs = [f"seed{s}" for s in args.seeds]
    pk = {r: SR.peaks(r, t_amb) for r in runs}
    present = [r for r in runs if pk[r] is not None]
    missing = [r for r in runs if pk[r] is None]
    if missing:
        print(f"  no FDS output yet: {', '.join(missing)}")
    if not present:
        return 1

    # ---- run health: warnings and completion against the baseline -------------------
    wb, _ = warnings("ysmatched")
    for r in present:
        ws, done = warnings(r)
        new = sorted(set(ws or []) - set(wb or []))
        print(f"  {r}: completed={done}, warnings {len(ws or [])} (baseline {len(wb or [])}), "
              f"new: {len(new)}")
        for w in new[:10]:
            print(f"      + {w[:150]}")

    # ---- noise floor per quantity ----------------------------------------------------
    rows = []
    for q in QTY:
        vals = np.array([base[q]] + [pk[r][q] for r in present], float)
        devs = {r: (pk[r][q] / base[q] - 1) * 100.0 for r in present}
        rec = dict(quantity=q, baseline=base[q], n_realisations=len(vals),
                   ens_mean=float(vals.mean()),
                   ens_sd_pct=float(vals.std(ddof=1) / vals.mean() * 100.0) if len(vals) > 1 else np.nan,
                   max_abs_dev_pct=float(max(abs(v) for v in devs.values())))
        rec.update({f"{r}": pk[r][q] for r in present})
        rec.update({f"dev_{r}_pct": d for r, d in devs.items()})
        rows.append(rec)
    noise = pd.DataFrame(rows).set_index("quantity")

    # trace NRMSE of each seed against the baseline (same metric as the sensitivity NRMSE)
    tb, bser = NR.load_series("ysmatched", t_amb)
    for r in present:
        tc, cser = NR.load_series(r, t_amb)
        for key, q in (("k_F1", "k_F1"), ("k_F2", "k_F2"), ("k_F3", "k_F3"),
                       ("dT_F1", "dTu_F1"), ("dT_F2", "dTu_F2"), ("dT_ceil", "dTc")):
            cy = np.interp(tb, tc, cser[key])
            peak = float(np.nanmax(bser[key]))
            noise.loc[q, f"nrmse_{r}_pct"] = 100.0 * float(np.sqrt(np.nanmean((cy - bser[key]) ** 2))) / peak
    noise.reset_index().to_csv(OUT, index=False, lineterminator="\n")

    # ---- every sensitivity case against the noise floor ------------------------------
    sens = pd.read_csv(P.SIM_RESULTS / "fds_sensitivity.csv")
    sens = sens[sens["run"] != "ysmatched"]
    base_dTc = base["dTc"]
    out = []
    for _, c in sens.iterrows():
        for q in QTY:
            d = (c["dTc"] / base_dTc - 1) * 100.0 if q == "dTc" else float(c[CASE_COL[q]])
            sd = noise.loc[q, "ens_sd_pct"]
            mx = noise.loc[q, "max_abs_dev_pct"]
            out.append(dict(group=c["group"], case=c["case"], run=c["run"], quantity=q,
                            delta_pct=d, noise_sd_pct=sd, noise_maxdev_pct=mx,
                            ratio_to_2sd=abs(d) / (2 * sd) if sd and sd > 0 else np.nan,
                            above_2sd=bool(abs(d) > 2 * sd) if sd == sd else None,
                            above_maxdev=bool(abs(d) > mx)))
    axes = pd.DataFrame(out)
    axes.to_csv(OUT_AXES, index=False, lineterminator="\n")

    pd.set_option("display.width", 200)
    print(f"\nnoise floor ({', '.join(present)} vs baseline):")
    cols = ["baseline", "ens_sd_pct", "max_abs_dev_pct"] + [f"dev_{r}_pct" for r in present]
    print(noise[cols].to_string(float_format=lambda v: f"{v:.3g}"))
    print(f"\nwrote {OUT.relative_to(P.REPO_ROOT)} and {OUT_AXES.relative_to(P.REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
