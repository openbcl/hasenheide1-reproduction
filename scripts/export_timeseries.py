"""Export the per-test measured time series (data stage).

Reads the consolidated run records written by ``reprocess_unclipped.py``
(``data/reprocessed/<run>/1_Processed_data/<run>_processed.csv``) and the event
logs of the measurement tree (``MEAS_ROOT/<run>/1_Processed_data/<run>_events.txt``)
and writes the committed per-test time series of the 14 heptane runs:

  results/measurement/timeseries/<run>.csv   one file per run, 1 Hz, t = 0 at the ignition
                                             reference (the full minute of ignition)
  results/measurement/timeseries/runs.csv    one row per run (configuration, durations, ambient)
  results/measurement/timeseries/events.csv  logged events per run, in s on the same axis
  results/measurement/timeseries/channels.csv  data dictionary: one row per run and column

The values are those of the consolidation, renamed to ASCII column names and
otherwise unchanged (no baseline correction; the reductions zero each record at
t = 0 themselves, ``measurement_io.load_runs``). Channels the consolidation sets to
NaN (no valid measurement in that test) are kept as NaN columns and marked
``excluded`` in channels.csv; channels with valid values over part of the record only
are marked ``partial``, with their valid range. Events are mapped to a fixed
vocabulary; other log entries are not exported. Run: python export_timeseries.py
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

import paths as P
from measurement_io import SUB_PROCESSED
from timeseries import write_checksums

OUT = P.MEAS_RESULTS / "timeseries"
LEM_PATH_LENGTH_M, SICK_PATH_LENGTH_M = 0.81, 1.6     # as in reprocess_unclipped.py
WIDMANN = (638 / 880) ** -1.0088                     # SICK 880 nm -> 638 nm

SERIES = {"Hep_160_S1": "Hep_160_150", "Hep_160_S2": "Hep_160_075", "Hep_160_S3": "Hep_160_075",
          "Hep_160_S4": "Hep_160_075", "Hep_220_S1": "Hep_220_300"}
TREE_ROOM = {"1": "F1", "2": "F2"}                    # thermocouple tree 1 in F1, tree 2 in F2
DETECTOR_ROOM = {"1": "F2", "2": "FC", "3": "F3"}     # ceiling smoke alarms

# event log text (lower-cased, stripped) -> exported event(s). Only these entries
# are exported; the others (start/stop of instruments outside this package) are
# counted, not exported.
EVENTS = {
    "zündung": ["ignition"],
    "feuer aus": ["flame_out"],
    "beginn lüftung": ["ventilation_start"], "beinn lüftung": ["ventilation_start"],
    "fenster raum 3 auf": ["window_F3_open"], "fenster rum 3 auf": ["window_F3_open"],
    "fenster raum 1 auf": ["window_F1_open"],
    "fenster raum 1 auf / lüfter ein": ["window_F1_open", "fan_on"],
    "lüfter ein": ["fan_on"], "lüfter an": ["fan_on"],
    "reinigung geräte": ["instrument_cleaning"],
    "erneute aufnahme deckentempertur": ["ceiling_tc_recording_resumed"],
    "versuchsende": ["test_end"],
}


def _header(path):
    meta = {}
    for line in open(path, encoding="utf-8-sig"):
        if not line.startswith("#"):
            break
        m = re.match(r"#\s*([^:]+):\s*(.*)$", line.strip())
        if m:
            meta[m.group(1).strip()] = m.group(2).strip()
    return meta


def _rename(col):
    """Consolidation column -> (ASCII name, dictionary row without run/column)."""
    if col == "Time (s)":
        return "t_s", dict(quantity="time from the ignition reference (t0_local in runs.csv)",
                           unit="s", instrument="",
                           processing="logger time minus the ignition reference, rounded to 1 s")
    if col == "Time Absolute":
        return "time_local", dict(quantity="local time", unit="", instrument="",
                                  processing="logger clock (CET)")
    if col == "Mass (kg)":
        return "mass_kg", dict(quantity="fuel mass on the platform scale (pan tared)", unit="kg",
                               instrument="platform scale", room="F1", processing="1 s average")
    if col.startswith("Plume Impingement Temperature"):
        return "T_ceiling_F1_C", dict(quantity="ceiling temperature above the fire", unit="degC",
                                      instrument="thermocouple", room="F1", processing="1 s average")
    m = re.match(r"Temp Tree (\d)_([\d.]+) \(", col)
    if m:
        room = TREE_ROOM[m.group(1)]
        # tree 2 below 2.0 m is logged separately (reprocess_unclipped.load_mb2_bottom)
        second = m.group(1) == "2" and float(m.group(2)) < 2.0
        return f"T_{room}_z{m.group(2)}_C", dict(
            quantity="gas temperature", unit="degC", instrument=f"thermocouple tree {m.group(1)}",
            room=room, z_m=float(m.group(2)),
            processing="separate logger, 0.1 degC resolution, merged onto the time axis "
                       "(nearest sample within 1 s)" if second else "1 s average")
    m = re.match(r"(Transm\.|Extinction) (LEM|SICK)_?(\d)?_(F\d)_([\d.]+)( IR)? \((%|1/m)\)(_corr)?$", col)
    if m:
        kind, dev, num, room, z, _, unit, corr = m.groups()
        name = f"LEM{num}" if dev == "LEM" else "SICK"
        L = LEM_PATH_LENGTH_M if dev == "LEM" else SICK_PATH_LENGTH_M
        wl = 638 if dev == "LEM" or corr else 880
        base = dict(instrument=name, room=room, z_m=float(z), path_length_m=L)
        if kind == "Transm.":
            src = "LEM 4: APD detector channel" if num == "4" else "as logged"
            return f"tau_{name}_{room}_z{z}_pct", dict(
                base, quantity="transmission", unit="%", wavelength_nm=638 if dev == "LEM" else 880,
                processing=f"{src}, 1 Hz")
        proc = "k = -ln(max(tau/100, 1e-5)) / L, negative values set to 0"
        if corr:
            proc += f"; x {WIDMANN:.4f} = (638/880)^-1.0088 (Widmann), 880 -> 638 nm"
        return f"k_{name}_{room}_z{z}_{wl}nm_per_m", dict(
            base, quantity="light-extinction coefficient", unit="1/m", wavelength_nm=wl, processing=proc)
    m = re.match(r"Smoke Detector (\d) \(Binary\)", col)
    if m:
        room = DETECTOR_ROOM[m.group(1)]
        return f"alarm_SD{m.group(1)}_{room}", dict(
            quantity="smoke alarm state (0/1)", unit="-", instrument=f"smoke alarm {m.group(1)}",
            room=room, processing="1 if the detector output exceeds 1.0 V")
    raise SystemExit(f"unmapped column: {col!r}")


def _events(run):
    f = P.MEAS_ROOT / run / SUB_PROCESSED / f"{run}_events.txt"
    rows, skipped = [], 0
    for line in open(f, encoding="utf-8", errors="replace"):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3 or not re.match(r"-?[\d.]+$", parts[1]):
            continue
        text = parts[2].lower()
        if text not in EVENTS:
            skipped += 1
            continue
        rows += [dict(run=run, t_s=float(parts[1]), event=e) for e in EVENTS[text]]
    if skipped:
        print(f"  {run}: {skipped} log entries not exported")
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    runs, events, channels = [], [], []
    for d in sorted(p for p in P.REPROCESSED_DIR.iterdir() if p.name.startswith("Hep_")):
        run = d.name
        src = d / SUB_PROCESSED / f"{run}_processed.csv"
        meta = _header(src)
        df = pd.read_csv(src, comment="#", encoding="utf-8-sig")
        names = {}
        for c in df.columns:
            new, row = _rename(c)
            if new in names.values():
                raise SystemExit(f"{run}: duplicate column {new}")
            names[c] = new
            values = pd.to_numeric(df[c], errors="coerce") if c != "Time Absolute" else df[c]
            excluded = c != "Time Absolute" and bool(values.isna().all())
            partial = c != "Time Absolute" and not excluded and bool(values.isna().any())
            note = ""
            if excluded:
                note = ("no valid measurement in this test; set to NaN by the consolidation "
                        "(reprocess_unclipped.py)")
            elif partial:
                tv = df.loc[values.notna(), "Time (s)"]
                gaps = int(values[(df["Time (s)"] >= tv.min()) & (df["Time (s)"] <= tv.max())].isna().sum())
                note = (f"valid for t_s = {int(tv.min())} to {int(tv.max())} s"
                        + (f" ({gaps} missing samples inside)" if gaps else ""))
            channels.append(dict(run=run, column=new, **row, source_column=c,
                                 status="excluded" if excluded else "partial" if partial else "ok",
                                 note=note))
        out = df.rename(columns=names)
        out["time_local"] = pd.to_datetime(out["time_local"]).dt.strftime("%Y-%m-%dT%H:%M:%S")
        out.to_csv(OUT / f"{run}.csv", index=False, lineterminator="\n")
        series = SERIES[run[:10]]
        runs.append(dict(
            run=run, series=series, setup=run.split("_")[2], pan_mm=int(run.split("_")[1]),
            fuel=meta["Fuel"].lower(), fuel_mass_g=float(meta["Fuel_mass"]),
            pan_area_m2=float(meta["Fuel_area"]), date=meta["Date"], t0_local=meta["Start_time"],
            burning_duration_s=float(meta["Burning_Duration"]),
            ventilation_start_s=float(meta["Start_ventilation"]), apartment_door=meta["Apartment_door"],
            ambient_T_C=float(meta["pre_T"]), ambient_RH_pct=float(meta["pre_H"]),
            ambient_p_hPa=float(meta["pre_BP"]),
            record_start_s=int(df["Time (s)"].min()), record_end_s=int(df["Time (s)"].max())))
        events += _events(run)
        print(f"  {run}: {len(df)} rows, {df.shape[1]} columns")
    pd.DataFrame(runs).to_csv(OUT / "runs.csv", index=False, lineterminator="\n")
    pd.DataFrame(events).to_csv(OUT / "events.csv", index=False, lineterminator="\n")
    cols = ["run", "column", "quantity", "unit", "instrument", "room", "z_m", "wavelength_nm",
            "path_length_m", "processing", "source_column", "status", "note"]
    pd.DataFrame(channels).reindex(columns=cols).to_csv(OUT / "channels.csv", index=False,
                                                        lineterminator="\n")
    write_checksums(OUT)
    print(f"-> {OUT.relative_to(P.REPO_ROOT)}: {len(runs)} runs, {len(events)} events, "
          f"{len(channels)} channel rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
