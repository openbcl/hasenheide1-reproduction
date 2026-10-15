"""Derive the apartment heat-release rate from the load-cell mass records.

This closes a reproducibility gap: the HRR is both a reported experimental result
and the FDS fire source, yet the mass -> HRR conversion (and with it the effective
heat of combustion) used to live in an unversioned notebook outside version
control. Here the chain is in-repo, with Delta H_ch an explicit, single-sourced
parameter.

Chain (per trial, validated against the original analysis to machine precision):
  1. cut the record to the burn window 0 <= t <= Burning_Duration
  2. centred 15 s rolling mean on the raw mass
  3. linear normalisation to m(0) = Fuel_mass, m(t_end) = 0
  4. backward difference x Delta H_ch
  5. clip negative HRR to zero (load-cell noise: the mass briefly rises)
  6. force the final sample to zero

Ensemble (per series):
  7. grid = integer steps to floor(mean burning duration), then that mean appended
  8. every trial zero-padded beyond its own burning duration
  9. mean / SD (Bessel) over trials
 10. trailing 21 s rolling mean PER TRIAL, endpoints zeroed, then each trial
     rescaled to its theoretical energy Fuel_mass x Delta H_ch, then averaged
 11. both endpoints of all four curves zeroed

Modes
  --ingest    copy the primary mass traces + metadata from the external
              measurement archive into results/measurement/hrr/ (run once; then no archive)
  (default)   reduce the committed traces -> results/measurement/hrr/hrr_summary.csv
  --validate  reduce with Delta H_ch pinned to the original reference value
              (41.07 MJ/kg) and compare against the original ensemble statistics;
              this is the permanent proof that the reimplementation is faithful

Run from the repo root:  python scripts/reduce_hrr_from_mass.py [--ingest|--validate]
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import paths as P

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results" / "measurement" / "hrr"
TRACES = OUT_DIR / "mass_trials.csv"
META = OUT_DIR / "mass_trials_meta.csv"

W_MASS = 15          # centred rolling mean on the mass [s]
W_HRR = 21           # trailing rolling mean on the HRR [s]
DHC_REF_MJ = 41.07   # Delta H_ch of the original reference analysis; --validate cross-check only
# Committed pooled Delta H_ch [MJ/kg]: the value tabulated in
# tables/rst_apartment_runs.tex and numbers.tex (\valRstDhchHh). Used as the
# fallback when results/measurement/rst_apartment_runs.csv is not present.
DHC_POOLED_MJ = 41.345


# --------------------------------------------------------------------------- #
#  Delta H_ch: single source
# --------------------------------------------------------------------------- #
def pooled_dhc_mj() -> float:
    """Effective heat of combustion [MJ/kg]: the apartment batch pooled over the
    RST furniture-calorimeter runs whose Delta H_ch is not excluded. Pooled rather
    than matched per configuration because the between-configuration spread of
    Delta H_ch does not exceed its replicate scatter (variance ratio < 1) -- unlike
    the soot yield, where it does (variance ratio ~ 8) and the decks are matched
    per configuration.

    Read from the committed six-run table results/measurement/rst_apartment_runs.csv (Table S4):
    the mean of the four runs not marked ``dhch_excluded`` (the excluded 220 mm/300 g
    runs carry a known heat-release-channel offset). Falls back to the committed
    constant DHC_POOLED_MJ if that file is absent."""
    csv = ROOT / "results" / "measurement" / "rst_apartment_runs.csv"
    if not csv.exists():
        return DHC_POOLED_MJ
    df = pd.read_csv(csv)
    vals = df.loc[~df["dhch_excluded"].astype(bool), "dhch_mj"]
    if vals.empty:
        sys.exit("no non-excluded Delta H_ch rows in results/measurement/rst_apartment_runs.csv")
    return float(vals.mean())


# --------------------------------------------------------------------------- #
#  Ingest (drive -> repo)
# --------------------------------------------------------------------------- #
def _meta_of(path: Path) -> dict:
    out = {}
    for line in path.open(encoding="utf-8-sig", errors="ignore"):
        if not line.lstrip().startswith("#"):
            break
        s = line.lstrip()[1:].strip()
        if ":" in s:
            k, v = s.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def ingest() -> int:
    meas = P.HRR_ROOT.parent.parent / "1_Measurements"
    if not meas.exists():
        sys.exit(f"measurement root not reachable: {meas}")
    traces, metas = [], []
    for f in sorted(meas.rglob("*_processed.csv")):
        md = _meta_of(f)
        if md.get("Fuel", "").strip().lower() != "heptane":
            continue                                   # other fuels are out of scope
        pan_mm = int(round(math.sqrt(float(md["Fuel_area"])) * 1000))
        charge_g = int(round(float(md["Fuel_mass"])))
        series = f"hep_{pan_mm}_{charge_g:03d}"
        trial = md["ID"]
        dur = float(md["Burning_Duration"])
        fuel_kg = float(md["Fuel_mass"]) / 1000.0
        df = pd.read_csv(f, comment="#", encoding="utf-8-sig")
        tc = next(c for c in df.columns if c.startswith("Time (s)"))
        mc = next(c for c in df.columns if c.startswith("Mass"))
        t = df[tc].to_numpy(float)
        m = df[mc].to_numpy(float)
        sel = (t >= 0) & (t <= dur)
        traces.append(pd.DataFrame({"series": series, "trial": trial,
                                    "t_s": t[sel], "mass_kg": m[sel]}))
        metas.append({"series": series, "trial": trial,
                      "fuel_mass_kg": fuel_kg, "burning_duration_s": dur})
    if not traces:
        sys.exit("no heptane trials found")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.concat(traces, ignore_index=True).to_csv(TRACES, index=False, lineterminator="\n")
    mdf = pd.DataFrame(metas).sort_values(["series", "trial"]).reset_index(drop=True)
    mdf.to_csv(META, index=False, lineterminator="\n")
    for s, g in mdf.groupby("series"):
        print(f"  {s:14s} {len(g)} trials  durations {g.burning_duration_s.min():.1f}"
              f"-{g.burning_duration_s.max():.1f} s")
    print(f"\n{len(mdf)} trials -> {TRACES.relative_to(ROOT)} / {META.relative_to(ROOT)}")
    return 0


# --------------------------------------------------------------------------- #
#  Reduction
# --------------------------------------------------------------------------- #
def trial_hrr(t: np.ndarray, mass: np.ndarray, fuel_kg: float, dhc_mj: float):
    m_sm = pd.Series(mass).rolling(W_MASS, center=True, min_periods=1).mean().to_numpy()
    m_norm = (m_sm - m_sm[-1]) / (m_sm[0] - m_sm[-1]) * fuel_kg
    q = np.zeros_like(m_norm)
    q[1:] = -np.diff(m_norm) * dhc_mj * 1000.0 / np.diff(t)
    q = np.maximum(q, 0.0)
    q[-1] = 0.0
    return m_norm, q


def build_series(trials: list, dhc_mj: float):
    """trials: list of (t, m_norm, q, fuel_kg, duration_s)."""
    durs = np.array([tr[4] for tr in trials], float)
    dur_mean = float(durs.mean())
    dt = float(min(np.diff(tr[0]).min() for tr in trials))
    tg = np.arange(0.0, math.floor(dur_mean / dt) * dt + 1e-9, dt)
    if len(tg) == 0 or abs(tg[-1] - dur_mean) > 1e-9:
        tg = np.append(tg, dur_mean)

    H = np.zeros((len(trials), len(tg)))
    M = np.zeros((len(trials), len(tg)))
    for i, (t, m_norm, q, fuel_kg, dur) in enumerate(trials):
        if abs(t[-1] - dur) > 1e-9:
            t2, h2 = np.append(t, dur), np.append(q, 0.0)
        else:
            t2, h2 = t.copy(), q.copy()
            h2[-1] = 0.0
        w = tg <= dur + 1e-9
        H[i, w] = np.interp(tg[w], t2, h2)
        H[i, 0] = 0.0
        # mass ensemble: fraction of the initial charge, zero-padded past the record
        frac = m_norm / (m_norm[0] if m_norm[0] > 0 else 1.0)
        wm = tg <= float(t[-1]) + 1e-12
        M[i, wm] = np.interp(tg[wm], t, frac)

    mean, std = H.mean(0), H.std(0, ddof=1) if len(trials) > 1 else np.zeros(len(tg))
    wpts = max(1, int(round(W_HRR / dt)))
    HR = np.zeros_like(H)
    for i, (t, m_norm, q, fuel_kg, dur) in enumerate(trials):
        HR[i] = pd.Series(H[i]).rolling(wpts, min_periods=1).mean().to_numpy()
        HR[i, 0] = HR[i, -1] = 0.0
        e_roll = float(np.trapezoid(HR[i], tg))
        if abs(e_roll) > 1e-6:
            HR[i] *= (fuel_kg * dhc_mj * 1000.0) / e_roll
            HR[i, 0] = HR[i, -1] = 0.0
    rm = HR.mean(0)
    rs = HR.std(0, ddof=1) if len(trials) > 1 else np.zeros(len(tg))
    for a in (mean, std, rm, rs):
        a[0] = a[-1] = 0.0
    m_mean = M.mean(0)
    m_std = M.std(0, ddof=1) if len(trials) > 1 else np.zeros(len(tg))
    return tg, mean, std, rm, rs, m_mean, m_std


def load_trials(dhc_mj: float) -> dict:
    if not (TRACES.exists() and META.exists()):
        sys.exit(f"missing ingested traces; run with --ingest first ({TRACES})")
    tr = pd.read_csv(TRACES)
    md = pd.read_csv(META).set_index(["series", "trial"])
    out: dict[str, list] = {}
    for (series, trial), g in tr.groupby(["series", "trial"], sort=True):
        info = md.loc[(series, trial)]
        t = g.t_s.to_numpy(float)
        m_norm, q = trial_hrr(t, g.mass_kg.to_numpy(float),
                              float(info.fuel_mass_kg), dhc_mj)
        out.setdefault(series, []).append(
            (t, m_norm, q, float(info.fuel_mass_kg), float(info.burning_duration_s)))
    return out


def reduce_all(dhc_mj: float) -> pd.DataFrame:
    rows = []
    for series, trials in sorted(load_trials(dhc_mj).items()):
        tg, mean, std, rm, rs, m_mean, m_std = build_series(trials, dhc_mj)
        rows.append(pd.DataFrame({"series": series, "t_s": tg, "hrr_mean": rm,
                                  "hrr_std": std, "m_mean": m_mean, "m_std": m_std}))
    return pd.concat(rows, ignore_index=True)


def validate() -> int:
    """Reproduce the reference ensemble with Delta H_ch pinned to its hard-coded value."""
    worst = 0.0
    n_compared = 0
    for series, trials in sorted(load_trials(DHC_REF_MJ).items()):
        ref_f = P.HRR_ROOT / f"{series}_hrr" / "HRR_ensemble_stats.csv"
        if not ref_f.exists():
            print(f"  {series}: reference ensemble not reachable, skipped")
            continue
        n_compared += 1
        tg, mean, std, rm, rs, _, _ = build_series(trials, DHC_REF_MJ)
        ref = pd.read_csv(ref_f)
        if len(ref) != len(tg):
            sys.exit(f"{series}: grid length {len(tg)} != drive {len(ref)}")
        print(f"  {series:14s} n={len(trials)}  grid {len(tg)} pts")
        for nm, mine, col in (("HRR_mean", mean, "HRR_mean_kW"),
                              ("HRR_std", std, "HRR_std_kW"),
                              ("HRR_roll_mean", rm, "HRR_roll_mean_kW"),
                              ("HRR_roll_std", rs, "HRR_roll_std_kW")):
            d = float(np.abs(mine - ref[col].to_numpy(float)).max())
            worst = max(worst, d)
            print(f"      {nm:15s} max|diff| = {d:.3e}")
    tol = 1e-8
    if n_compared == 0:
        print("\nno reference ensemble reachable (external HRR archive absent) "
              "-> nothing to validate")
        return 0
    print(f"\nworst deviation {worst:.3e} (tolerance {tol:g}) over {n_compared} "
          f"series -> {'PASS' if worst < tol else 'FAIL'}")
    return 0 if worst < tol else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ingest", action="store_true",
                    help="copy the primary mass traces from the raw records into results/measurement/hrr/")
    ap.add_argument("--validate", action="store_true",
                    help="check the chain against the reference reduction at its hard-coded 41.07 MJ/kg")
    a = ap.parse_args()
    if a.ingest:
        return ingest()
    if a.validate:
        return validate()
    dhc = pooled_dhc_mj()
    df = reduce_all(dhc)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "hrr_summary.csv"
    df.to_csv(out, index=False, lineterminator="\n")
    for s, g in df.groupby("series"):
        print(f"  {s:14s} peak {g.hrr_mean.max():6.2f} kW   n={len(g)} samples")
    print(f"\nDelta H_ch = {dhc:.3f} MJ/kg -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
