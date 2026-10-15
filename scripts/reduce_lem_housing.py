"""LEM housing-temperature rise during the apartment fires (data stage -> results/).

The extinction-uncertainty analysis (Supplementary Material) bounds the thermal component of the LEM
drift by comparing the housing warming reached in these fires against the
ethanol stress test of the dedicated LEM characterisation (air rise up to
37.5 K at the beam, housing rise up to 10.3 K, transmission stable to 1.25 %).
That comparison needs our own housing rise as a measured number rather than a
hand-typed one, which is what this reducer supplies.

Source: the Dewesoft export in each run's ``0_Raw_data`` carries three
``Temperaturstatistik 1 s/Temp. LEM n/AVE/1s`` channels. Three, not four: the
fire-room LEM has no housing sensor, and its source-power drift is handled by a
monitor photodiode instead. The three instrumented housings are therefore
exactly the adjacent-room line-of-sight positions (LEM 1 = F2/1.5 m,
2 = F3/2.3 m, 3 = F2/2.3 m), which is the population the Supplementary Material's bound is
stated over.

WHAT THIS DOES NOT DO. It does not touch the ``*_V1.TXT`` logger that sits in
the same raw folder. That file also holds four ambient-start temperature
channels and is easy to mistake for the housings, but it is a different
instrument and reaches far higher rises; using it would overstate the housing
warming by more than a factor of two.

Baseline is the mean of the first 60 samples (1 Hz, pre-ignition); the rise is
max - baseline per channel.

Writes results/measurement/lem_housing.csv (one row per run and channel, plus a summary
row). Reads from the measurement root (HASENHEIDE_MEAS_ROOT-overridable).
Run: python reduce_lem_housing.py
"""
from __future__ import annotations

import io
import re
import sys

import numpy as np
import pandas as pd

import paths as P

BASELINE_SAMPLES = 60
CHANNEL_RE = re.compile(r"Temp\. LEM (\d)")
# housing channel -> the line-of-sight position it sits at (see module docstring)
POSITION = {"1": "F2/1.5 m", "2": "F3/2.3 m", "3": "F2/2.3 m"}


def run_channels(run_dir):
    """(channel id, baseline, rise) for every Temp. LEM channel of one run."""
    exports = sorted((run_dir / "0_Raw_data").glob("Messung_*.txt"))
    if not exports:
        return []
    lines = io.open(exports[0], encoding="latin-1", errors="replace").read().split("\n")
    try:
        hi = next(i for i, l in enumerate(lines) if l.startswith("Time ("))
    except StopIteration:
        return []
    cols = lines[hi].split(",")
    idx = {i: m.group(1) for i, c in enumerate(cols) if (m := CHANNEL_RE.search(c))}
    if not idx:
        return []

    rows = []
    for line in lines[hi + 1:]:
        p = line.split(",")
        if len(p) < len(cols):
            continue
        try:
            rows.append([float(p[i].replace(",", ".")) for i in idx])
        except ValueError:
            continue
    if len(rows) <= BASELINE_SAMPLES:
        return []

    a = np.asarray(rows)
    base = a[:BASELINE_SAMPLES].mean(axis=0)
    rise = a.max(axis=0) - base
    return [(ch, b, r) for ch, b, r in zip(idx.values(), base, rise)]


def main() -> int:
    if not P.MEAS_ROOT.exists():
        print(f"measurement root not available ({P.MEAS_ROOT}) -- skipping")
        return 0

    out = []
    for run in sorted(x for x in P.MEAS_ROOT.iterdir() if x.name.startswith("Hep_")):
        found = run_channels(run)
        if not found:
            print(f"  {run.name}: no Temp. LEM channels")
            continue
        series = re.match(r"(Hep_\d+)", run.name).group(1)
        for ch, base, rise in found:
            out.append({"run": run.name, "series": series, "channel": f"LEM {ch}",
                        "position": POSITION.get(ch, "?"),
                        "baseline_C": round(float(base), 3),
                        "rise_K": round(float(rise), 3)})

    if not out:
        print("no housing data found")
        return 1

    df = pd.DataFrame(out)
    worst = df.loc[df.rise_K.idxmax()]
    df = pd.concat([df, pd.DataFrame([{
        "run": "MAX", "series": worst.series, "channel": worst.channel,
        "position": worst.position, "baseline_C": worst.baseline_C,
        "rise_K": worst.rise_K}])], ignore_index=True)

    P.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    f = P.RESULTS_DIR / "measurement" / "lem_housing.csv"
    df.to_csv(f, index=False)

    print(f"\n{len(out)} channel-runs -> {f}")
    print(df[df.run != "MAX"].groupby("series").rise_K.max().round(2).to_string())
    print(f"\nmaximum housing rise: {worst.rise_K:.2f} K "
          f"({worst.run}, {worst.channel} at {worst.position})")
    print("ethanol stress test for comparison: 10.3 K (Schelhorn)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
