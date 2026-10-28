"""Smoke-alarm activation analysis for the Hasenheide heptane experiments.

Parses the binary smoke-alarm channels and the co-located LEM extinction from the
processed experiment CSVs and reports, per run and aggregated per series:
  - activation time of each alarm,
  - the LEM extinction coefficient in the same room at the activation instant.

Detector -> room mapping (confirmed; see the paper's instrumentation section):
    Smoke Detector 1 = room F2,  Detector 2 = room FC,  Detector 3 = room F3.
The corridor alarm (FC) has no co-located LEM, so only F2 and F3 are cross-checked.

This is a data-stage step: it reads the processed experiment CSVs under
``MEAS_ROOT`` (set HASENHEIDE_MEAS_ROOT to your copy of the measurement tree);
without that tree it reads the committed per-test time series instead.
"""
import re
import numpy as np
import pandas as pd
from pathlib import Path

import paths as P  # data roots (env-overridable; default to in-repo placeholders)
import measurement_io as mio

BASE = P.MEAS_ROOT


def series_of(name: str):
    if name.startswith("Hep_220_S1"):
        return "Hep_220_300"
    if name.startswith("Hep_160_S1"):
        return "Hep_160_150"
    if re.match(r"Hep_160_S[234]", name):
        return "Hep_160_075"
    return None


def first_activation(t, b):
    idx = np.where(np.asarray(b, float) >= 0.5)[0]
    return float(t[idx[0]]) if len(idx) else None


def value_at(t, k, tq):
    if tq is None:
        return None
    t, k = np.asarray(t, float), np.asarray(k, float)
    return float(k[int(np.argmin(np.abs(t - tq)))])


def ext_col(df, room):
    for c in df.columns:
        if c.startswith("Extinction LEM") and f"_{room}_2.3" in c:
            return c
    return None


def collect() -> pd.DataFrame:
    """Per-run activation times (tF2/tFC/tF3) and co-located LEM extinction at
    activation (kF2/kF3), with the series label. Reused by the FDS comparison."""
    rows = []
    for name in mio.list_runs(BASE):
        s = series_of(name)
        if not s:
            continue
        pf = mio.get_processed_file(BASE, name)
        if not pf:
            continue
        df = mio.read_processed(pf)
        t = df["Time (s)"].to_numpy(float)
        dets = sorted([c for c in df.columns if re.match(r"Smoke Detector \d", c)],
                      key=lambda c: int(re.search(r"\d", c).group()))
        acts = [first_activation(t, df[c]) for c in dets]            # D1=F2, D2=FC, D3=F3
        cF2, cF3 = ext_col(df, "F2"), ext_col(df, "F3")
        kF2 = value_at(t, df[cF2], acts[0]) if cF2 else None
        kF3 = value_at(t, df[cF3], acts[2]) if cF3 else None
        rows.append(dict(run=name, series=s, tF2=acts[0], tFC=acts[1], tF3=acts[2],
                         kF2=kF2, kF3=kF3))
    return pd.DataFrame(rows)


def main():
    res = collect()
    pd.set_option("display.width", 120)
    print(res.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    def ms(v):
        v = v.dropna()
        if len(v) == 0:
            return "--"
        sd = v.std(ddof=1) if len(v) > 1 else 0.0
        return f"{v.mean():.0f}+-{sd:.0f}"

    def msk(v):
        v = v.dropna()
        if len(v) == 0:
            return "--"
        sd = v.std(ddof=1) if len(v) > 1 else 0.0
        return f"{v.mean():.3f}+-{sd:.3f}"

    print("\nPaper table (mean +/- SD; times in s, k in 1/m):")
    print(f"{'series':13s} | {'t_F2':>9s} {'t_FC':>9s} {'t_F3':>9s} | {'k_F2':>13s} {'k_F3':>13s} | n")
    for s in ["Hep_160_075", "Hep_160_150", "Hep_220_300"]:
        g = res[res.series == s]
        print(f"{s:13s} | {ms(g.tF2):>9s} {ms(g.tFC):>9s} {ms(g.tF3):>9s} | "
              f"{msk(g.kF2):>13s} {msk(g.kF3):>13s} | {len(g)}")

    for room, col in [("F2", "kF2"), ("F3", "kF3")]:
        v = res[col].dropna()
        k = v.mean()
        print(f"  ALL {room} (n={len(v)}): k={k:.3f}+-{v.std(ddof=1):.3f} 1/m "
              f"-> {100*(1-np.exp(-k)):.1f} %/m, {4.343*k:.2f} dB/m")

    # --- committed reduced CSV: the smoke-alarm table numbers ---
    import paths as P

    def _ms(v):
        v = v.dropna()
        if len(v) == 0:
            return np.nan, np.nan
        return float(v.mean()), float(v.std(ddof=1) if len(v) > 1 else 0.0)

    rows = []
    for s in ["Hep_160_075", "Hep_160_150", "Hep_220_300"]:
        g = res[res.series == s]
        row = {"series": s, "n": len(g)}
        for nm, col in [("tF2", "tF2"), ("tFC", "tFC"), ("tF3", "tF3"),
                        ("kF2", "kF2"), ("kF3", "kF3")]:
            row[f"{nm}_mean"], row[f"{nm}_sd"] = _ms(g[col])
        rows.append(row)
    P.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = P.RESULTS_DIR / "measurement" / "smoke_alarm_table.csv"
    pd.DataFrame(rows).to_csv(out, index=False, lineterminator="\n")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
