"""Reducer for the metadata-derived paper tables (data stage).

Reads the experiment metadata from the raw measurement data
(``MEAS_ROOT/experiment_metadata.txt``, ';'-separated) and writes two committed
CSVs so the corresponding paper tables (tab:ambient, tab:experiments_overview)
can be generated without the raw data:

  results/measurement/ambient.csv               series, n, T_mean, T_sd, BP_mean, BP_sd, RH_mean, RH_sd
  results/measurement/experiments_overview.csv  series, pan_mm, mass_g, runs, flameout_mean, flameout_sd, vent_s

Per-series statistics are the mean and Bessel-corrected SD over the replicate
heptane runs of each series. Pre-test ambient columns: pre_T (degC), pre_BP (hPa),
pre_H (rel. humidity %). Run: python reduce_ambient.py
"""
from __future__ import annotations

import csv

import numpy as np
import pandas as pd

import paths as P

# series label -> ID prefixes of its replicate runs in the metadata file
SERIES = {
    "Hep_160_075": ["Hep_160_S2", "Hep_160_S3", "Hep_160_S4"],
    "Hep_160_150": ["Hep_160_S1"],
    "Hep_220_300": ["Hep_220_S1"],
}
PAN_MM = {"Hep_160_075": 160, "Hep_160_150": 160, "Hep_220_300": 220}


def _rows():
    f = P.MEAS_ROOT / "experiment_metadata.txt"
    return list(csv.DictReader(open(f, encoding="utf-8"), delimiter=";"))


def main() -> None:
    rows = _rows()
    amb, ovr = [], []
    for label, prefixes in SERIES.items():
        rs = [r for r in rows if any(r["ID"].startswith(p) for p in prefixes)]
        n = len(rs)
        T = np.array([float(r["pre_T"]) for r in rs])
        BP = np.array([float(r["pre_BP"]) for r in rs])   # hPa
        RH = np.array([float(r["pre_H"]) for r in rs])
        dur = np.array([float(r["Burning_Duration"]) for r in rs])
        vents = {r["Start_ventilation"] for r in rs}
        assert len(vents) == 1, f"{label}: non-unique ventilation onset {vents}"
        masses = {r["Fuel_mass"] for r in rs}
        assert len(masses) == 1, f"{label}: non-unique fuel mass {masses}"

        def ms(a):
            return float(a.mean()), float(a.std(ddof=1))
        Tm, Ts = ms(T); BPm, BPs = ms(BP); RHm, RHs = ms(RH); Dm, Ds = ms(dur)
        amb.append(dict(series=label, n=n, T_mean=Tm, T_sd=Ts,
                        BP_mean=BPm, BP_sd=BPs, RH_mean=RHm, RH_sd=RHs))
        ovr.append(dict(series=label, pan_mm=PAN_MM[label], mass_g=int(next(iter(masses))),
                        runs=n, flameout_mean=Dm, flameout_sd=Ds,
                        vent_s=int(next(iter(vents)))))

    P.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(amb).to_csv(P.RESULTS_DIR / "measurement" / "ambient.csv", index=False)
    pd.DataFrame(ovr).to_csv(P.RESULTS_DIR / "measurement" / "experiments_overview.csv", index=False)
    print(f"wrote {P.RESULTS_DIR / 'measurement' / 'ambient.csv'} and {P.RESULTS_DIR / 'measurement' / 'experiments_overview.csv'}")


if __name__ == "__main__":
    main()
