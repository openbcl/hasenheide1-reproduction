"""Export the FDS baseline time series at the instrument positions (data stage).

Reads the device and HRR output of the three baseline runs
(``FDS_OUTPUT_ROOT/<case>/<case>_devc.csv`` and ``_hrr.csv``, one per series) and
writes the committed model counterparts of the measured time series:

  results/simulation/timeseries/<case>_devc.csv   the devices at the instrument
      positions: thermocouples F1-F3 at the tree heights and below the ceiling of F1
      and F3, point extinction, the LEM and SICK line-of-sight beams (PATH OBSCURATION,
      plus the path-mean extinction <beam>_k), and the smoke-alarm devices. The F3
      thermocouples, the F3 ceiling thermocouple and the point-extinction devices have
      no measured counterpart (blank ``measured`` in fds_channels.csv)
  results/simulation/timeseries/<case>_hrr.csv    the HRR file as written by FDS
  results/simulation/timeseries/fds_channels.csv  data dictionary: device, quantity,
      unit, room, height, the device coordinates from the input deck, and the
      measured column it corresponds to (results/measurement/timeseries/)

Values are the FDS output as read by fds_io.read_fds_devc (pandas' default parser, the
same values reduce_matrices.py reads from the output tree), written as round-trip
floats; <beam>_k uses fds_io.path_obscuration_to_k, the same conversion as
reduce_matrices.py. The other device lines of the output
(vertical profiles, other instruments) are not exported.
Run: python export_fds_timeseries.py
"""
from __future__ import annotations

import re

import pandas as pd

import fds_io
import paths as P
from timeseries import write_checksums

OUT = P.SIM_RESULTS / "timeseries"
CASES = {"hep_160_075_ysmatched": "Hep_160_075", "hep_160_150_ysmatched": "Hep_160_150",
         "hep_220_300_ysmatched": "Hep_220_300"}
DEVICE = re.compile(r"^(TC_F\d_\d_\d|TC_Ceiling_F\d|EXT_DEVC_F\d_\d_\d|LEM_LOS_F\d_\d_\d|SICK_LOS_F\d"
                    r"|SD_F[C\d]_(EXT|Hes|P1|P2))$")
LEM_BY_ROOM_Z = {("F1", 2.3): "LEM4", ("F2", 2.3): "LEM3", ("F3", 2.3): "LEM2",
                 ("F2", 1.5): "LEM1", ("F2", 1.9): "LEM1", ("F2", 2.1): "LEM1"}
DETECTOR = {"F2": "SD1", "FC": "SD2", "F3": "SD3"}
SD_KIND = {"EXT": "EXTINCTION COEFFICIENT at the alarm",
           "Hes": "CHAMBER OBSCURATION, PROP 'Heskestad Ionization' in the deck",
           "P1": "CHAMBER OBSCURATION, PROP 'Optical Smoke Detector P1' in the deck",
           "P2": "CHAMBER OBSCURATION, PROP 'Optical Smoke Detector P2' in the deck"}


def _deck_positions(case):
    """DEVC ID -> 'XYZ=..' or 'XB=..' string from the input deck."""
    pos = {}
    for line in open(P.REPO_ROOT / "fds_decks" / f"{case}.fds", encoding="utf-8"):
        m = re.search(r"&DEVC\s+ID='([^']+)'.*?\b(XYZ|XB)\s*=\s*([-\d.,\s]+?)\s*/", line)
        if m:
            pos[m.group(1)] = f"{m.group(2)}={m.group(3).replace(' ', '')}"
    return pos


def _describe(dev):
    """Dictionary row for one FDS device column."""
    m = re.match(r"TC_(F\d)_(\d)_(\d)$", dev)
    if m:
        z = float(f"{m.group(2)}.{m.group(3)}")
        meas = f"T_{m.group(1)}_z{z}_C" if m.group(1) in ("F1", "F2") else ""
        return dict(quantity="THERMOCOUPLE", room=m.group(1), z_m=z, measured=meas)
    m = re.match(r"TC_Ceiling_(F\d)$", dev)
    if m:
        return dict(quantity="THERMOCOUPLE (below the ceiling)", room=m.group(1), z_m="",
                    measured="T_ceiling_F1_C" if m.group(1) == "F1" else "")
    m = re.match(r"(EXT_DEVC|LEM_LOS)_(F\d)_(\d)_(\d)(_k)?$", dev)
    if m:
        room, z = m.group(2), float(f"{m.group(3)}.{m.group(4)}")
        lem = LEM_BY_ROOM_Z[(room, z)]
        q = {"EXT_DEVC": "EXTINCTION COEFFICIENT (point)", "LEM_LOS": "PATH OBSCURATION"}[m.group(1)]
        if m.group(5):
            q = "path-mean extinction coefficient from PATH OBSCURATION, L = 0.81 m"
        return dict(quantity=q, room=room, z_m=z, measured=f"k_{lem}_{room}_z{z}_638nm_per_m"
                    if m.group(1) == "LEM_LOS" and m.group(5) else "")
    m = re.match(r"SICK_LOS_(F\d)(_k)?$", dev)
    if m:
        q = ("path-mean extinction coefficient from PATH OBSCURATION, L = 0.80 m (single pass)"
             if m.group(2) else "PATH OBSCURATION")
        return dict(quantity=q, room=m.group(1), z_m=2.3,
                    measured=f"k_SICK_{m.group(1)}_z2.3_638nm_per_m" if m.group(2) else "")
    m = re.match(r"SD_(F[C\d])_(EXT|Hes|P1|P2)$", dev)
    if m:
        return dict(quantity=SD_KIND[m.group(2)], room=m.group(1), z_m="",
                    measured=f"alarm_{DETECTOR[m.group(1)]}_{m.group(1)}")
    raise SystemExit(f"undescribed device {dev}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for case, series in CASES.items():
        src = P.FDS_OUTPUT_ROOT / case
        units = pd.read_csv(src / f"{case}_devc.csv", nrows=1, header=None).iloc[0].tolist()
        names = pd.read_csv(src / f"{case}_devc.csv", skiprows=1, nrows=0).columns.tolist()
        unit_of = dict(zip(names, units))
        keep = ["Time"] + [c for c in names if DEVICE.match(c)]
        d = fds_io.read_fds_devc(src / f"{case}_devc.csv", usecols=keep)[keep]
        d = fds_io.add_los_extinction(d)
        d = d.rename(columns={"Time": "t_s"})
        f = OUT / f"{case}_devc.csv"
        d.to_csv(f, index=False, lineterminator="\n")
        f = OUT / f"{case}_hrr.csv"               # byte copy, line endings normalised to LF
        f.write_bytes((src / f"{case}_hrr.csv").read_bytes().replace(b"\r\n", b"\n"))
        pos = _deck_positions(case)
        for c in d.columns:
            if c == "t_s":
                rows.append(dict(case=case, series=series, column=c, quantity="time", unit="s"))
                continue
            dev = c[:-2] if c.endswith("_k") else c
            row = _describe(c)
            if dev.startswith("SICK_LOS"):           # beam height as built (XB z), not nominal
                row["z_m"] = float(pos[dev].split("=")[1].split(",")[4])
            rows.append(dict(case=case, series=series, column=c, **row,
                             unit="1/m" if c.endswith("_k") else unit_of[dev], position=pos.get(dev, "")))
        print(f"  {case}: {len(d)} rows, {d.shape[1]} columns")
    cols = ["case", "series", "column", "quantity", "unit", "room", "z_m", "position", "measured"]
    f = OUT / "fds_channels.csv"
    pd.DataFrame(rows).reindex(columns=cols).to_csv(f, index=False, lineterminator="\n")
    write_checksums(OUT)
    print(f"-> {OUT.relative_to(P.REPO_ROOT)}: {len(CASES)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
