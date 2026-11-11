"""Loaders and checksums for the committed time series.

  results/measurement/timeseries/   the 14 measured tests (export_timeseries.py)
  results/simulation/timeseries/    the three FDS baseline runs (export_fds_timeseries.py)

    from timeseries import load_test, load_fds
    t = load_test("Hep_160_S2_R1")      # t.data, t.channels, t.events, t.run (runs.csv row)
    t = load_test("Hep_160_S2_R1", until_test_end=True)   # without the switch-off artefacts
    m = load_fds(t.run["series"])       # m.data, m.channels, m.hrr

Values are read with float_precision="round_trip", so they are the exact doubles the
reductions use. ``python timeseries.py`` checks both directories against their
SHA256SUMS files.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent / "results"
MEAS_TS = ROOT / "measurement" / "timeseries"
FDS_TS = ROOT / "simulation" / "timeseries"
FDS_CASE = {"Hep_160_075": "hep_160_075_ysmatched", "Hep_160_150": "hep_160_150_ysmatched",
            "Hep_220_300": "hep_220_300_ysmatched"}


def _read(path: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(path, float_precision="round_trip", **kw)


def load_test(run: str, until_test_end: bool = False) -> SimpleNamespace:
    """One measured test: its time series, dictionary rows, events and runs.csv row.

    until_test_end: keep only t_s < test_end - 1 s. After the logged test_end the
    instruments are switched off (and in two tests cleaned), which produces
    extinction artefacts up to the 14.21 1/m ceiling; one test switches off 0.3 s
    before its logged test_end, hence the 1 s margin."""
    runs = _read(MEAS_TS / "runs.csv").set_index("run")
    if run not in runs.index:
        raise KeyError(f"{run!r} is not one of {sorted(runs.index)}")
    ch = _read(MEAS_TS / "channels.csv")
    ev = _read(MEAS_TS / "events.csv")
    ev = ev[ev.run == run].reset_index(drop=True)
    data = _read(MEAS_TS / f"{run}.csv")
    if until_test_end:
        t_end = float(ev.loc[ev.event == "test_end", "t_s"].iloc[0])
        data = data[data.t_s < t_end - 1].reset_index(drop=True)
    return SimpleNamespace(data=data, channels=ch[ch.run == run].reset_index(drop=True),
                           events=ev, run=runs.loc[run])


def load_fds(series: str) -> SimpleNamespace:
    """The FDS baseline run of a series: device time series, dictionary rows, HRR file."""
    case = FDS_CASE[series]
    ch = _read(FDS_TS / "fds_channels.csv")
    return SimpleNamespace(data=_read(FDS_TS / f"{case}_devc.csv"), channels=ch[ch.case == case].reset_index(drop=True),
                           hrr=_read(FDS_TS / f"{case}_hrr.csv", header=1), case=case)


def write_checksums(directory: Path) -> None:
    """SHA256SUMS over every other file in ``directory`` (sha256sum -c format)."""
    files = sorted(p for p in directory.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    with open(directory / "SHA256SUMS", "w", encoding="ascii", newline="\n") as fh:
        for p in files:
            fh.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")


def verify_checksums(directory: Path) -> list[str]:
    """Names of files whose SHA-256 differs from SHA256SUMS, that are missing, or that
    are present but not listed."""
    bad, listed = [], set()
    for line in (directory / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        digest, name = line.split("  ", 1)
        listed.add(name)
        p = directory / name
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            bad.append(name)
    bad += sorted(p.name + " (not listed)" for p in directory.iterdir()
                  if p.is_file() and p.name != "SHA256SUMS" and p.name not in listed)
    return bad


if __name__ == "__main__":
    status = 0
    for d in (MEAS_TS, FDS_TS):
        bad = verify_checksums(d)
        n = len((d / "SHA256SUMS").read_text(encoding="ascii").splitlines())
        print(f"{d.relative_to(ROOT.parent)}: {n - len(bad)}/{n} files OK" + (f", differ: {bad}" if bad else ""))
        status |= bool(bad)
    sys.exit(status)
