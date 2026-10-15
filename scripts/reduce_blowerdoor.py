"""Data stage: reduce the blower-door reports to committed CSVs.

Reads the TEC Auto Test PDF reports (DIN EN ISO 9972) of the 2026-07-28 air-
tightness campaign on the test apartment ("Fluppe") and the neighbouring flat
("Bemme") from the measurement drive and writes two reduced CSVs into results/:

  blowerdoor_summary.csv : one row per test x direction (q50, exponent n, Cenv)
  blowerdoor_points.csv  : the individual (dp, Q) points of each pressure series

These committed CSVs are the reproducibility boundary; the figure stage
(plot_blowerdoor_leakage.py) reads only from them, so the
paper builds without the measurement drive. Re-run only when the raw reports
change:  python scripts/reduce_blowerdoor.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as P  # noqa: E402

SRC = P.PREP_ROOT / "26-07-28_BlowerDoor"
OUT = P.RESULTS_DIR / "measurement"

# report stem -> (test key, tested volume label, direction)
REPORTS = {
    "Hasenheide_versuch1":            ("fluppe", "Fluppe (whole)", "pressurization"),
    "Hasenheide_versuch1unterdruck":  ("fluppe", "Fluppe (whole)", "depressurization"),
    "Hasenheide_versuch2":            ("F1", "F1", "pressurization"),
    "Hasenheide_versuch2unterdruck":  ("F1", "F1", "depressurization"),
    "Hasenheide_versuch3":            ("F1F2", "F1+F2", "pressurization"),
    "Hasenheide_versuch3unterdruck":  ("F1F2", "F1+F2", "depressurization"),
    "Hasenheide_versuch4":            ("F3", "F3", "pressurization"),
    "Hasenheide_versuch4unterdruck":  ("F3", "F3", "depressurization"),
    "Hasenheide_versuch5":            ("F3_chimney_sealed", "F3, chimney sealed", "pressurization"),
    "Hasenheide_versuch5unterdruck":  ("F3_chimney_sealed", "F3, chimney sealed", "depressurization"),
    "Hasenheide_versuch6":            ("bemme", "Bemme (reference)", "pressurization"),
    "Hasenheide_versuch6unterdruck":  ("bemme", "Bemme (reference)", "depressurization"),
}


def _de(s: str) -> float:
    """German number '1.174,6' -> 1174.6."""
    return float(s.replace(".", "").replace(",", "."))


def main() -> None:
    from pypdf import PdfReader
    if not P.available(SRC):
        print(f"SKIP: measurement data not available ({SRC})")
        return
    summ, pts = [], []
    for stem, (key, vol, direction) in REPORTS.items():
        t = "".join(p.extract_text() or "" for p in PdfReader(str(SRC / f"{stem}.pdf")).pages)
        q50 = _de(re.search(r"q50:\s*m³/h \(Leckagestrom\)\s*([\d\.]+)", t).group(1))
        n = _de(re.search(r"Exponent \(n\):\s*([\d,]+)", t).group(1))
        cenv = _de(re.search(r"Str.{1,3}mungskoeffizient \(Cenv\):\s*([\d,]+)", t).group(1))
        summ.append(dict(test=key, volume=vol, direction=direction,
                         q50_m3h=round(q50, 1), n_exp=n, cenv=cenv))
        for m in re.finditer(r"(-?[\d.]+,\d+)\s+(-?[\d.]+,\d+)\s+(-?[\d.]+,\d+)\s+"
                             r"(-?[\d.]+,\d+)\s+([\d.]+,\d+)\s+Blende", t):
            pts.append(dict(test=key, direction=direction,
                            dp_pa=round(abs(_de(m.group(2))), 2), q_m3h=_de(m.group(5))))
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summ).to_csv(OUT / "blowerdoor_summary.csv", index=False)
    pd.DataFrame(pts).to_csv(OUT / "blowerdoor_points.csv", index=False)
    print(f"wrote {OUT/'blowerdoor_summary.csv'} ({len(summ)} rows) and "
          f"{OUT/'blowerdoor_points.csv'} ({len(pts)} rows)")


if __name__ == "__main__":
    main()
