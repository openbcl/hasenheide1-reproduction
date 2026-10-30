"""Data builder for the interactive dashboard (dashboard/).

Reads only committed files of this package and writes the JSON files the static
website in dashboard/ loads, plus dashboard/app/style_tokens.js (the colours and
markers of scripts/plot_style.py). It derives no new quantity: every value is a
committed value, rounded for display, and every key number the dashboard prints is
compared with its macro in numbers.tex while building (the build aborts on a
mismatch). Further consistency checks compare the shipped curves with the files the
paper figures are drawn from (series means of the single tests = ext_lem.csv, FDS
beams = ext_fds.csv, per-run SICK = ext_sick.csv, pooled statistic = guide_pooled.csv).

  dashboard/data/manifest.json      sources (path, bytes, SHA-256) and outputs
  dashboard/data/meta.json          series, runs, events, channel dictionary, Tables 1/2, key numbers
  dashboard/data/ts/<run>.json      one measured test, 1 Hz, raw (not zeroed), t < test_end - 1 s
  dashboard/data/fds/<series>.json  FDS baseline devices at the instrument positions + HRR
  dashboard/data/matrices.json      series means and FDS beams of Figs. 4 and 6
  dashboard/data/validation.json    peak pairs, per-sensor metrics, pooled and per-series statistics
  dashboard/data/lemsick.json       LEM-SICK cross-check and Widmann exponent test
  dashboard/data/numbers.json       every macro of numbers.tex with class, source and status
  dashboard/data/geometry.json      room outlines and instrument positions (FDS input file coordinates)
  dashboard/data/inputs.json        heat release (Fig. 3), baseline parameters (Table 4, from the decks), sensitivity (Fig. 7)

Output is deterministic (sorted keys, fixed rounding, LF, no timestamps or git
hashes), so re-running it on unchanged data is a git no-op.

    python scripts/build_dashboard_data.py           # write the outputs
    python scripts/build_dashboard_data.py --check   # compare with the committed outputs, exit 1 on drift
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as P  # noqa: E402
import plot_style as PS  # noqa: E402
from guide_stats import guide_delta_sigma, SIGMA_E  # noqa: E402
from fds_validation_scatter import SIGNAL_MIN  # noqa: E402

REPO = P.REPO_ROOT
OUT = REPO / "dashboard"
DATA = OUT / "data"
SCHEMA = 1
SIG = 5                      # significant digits of displayed values
TS_DIR = "results/measurement/timeseries"
FDS_DIR = "results/simulation/timeseries"
SERIES = ("Hep_160_075", "Hep_160_150", "Hep_220_300")
FDS_CASE = {s: f"{s.lower()}_ysmatched" for s in SERIES}

_sources: dict[str, Path] = {}


# ----------------------------------------------------------------------------- helpers
def src(rel: str) -> Path:
    """Register a committed input file (repo-relative path) and return its path."""
    p = REPO / rel
    if not p.is_file():
        raise FileNotFoundError(rel)
    _sources[rel] = p
    return p


def read_csv(rel: str, **kw) -> pd.DataFrame:
    return pd.read_csv(src(rel), float_precision="round_trip", **kw)


def rnd(x, sig: int = SIG):
    """A float rounded to ``sig`` significant digits; NaN/inf -> None, -0 -> 0."""
    if x is None:
        return None
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    x = float(x)
    if not math.isfinite(x):
        return None
    v = float(f"{x:.{sig}g}")
    return 0.0 if v == 0 else v


def col(values, sig: int = SIG) -> list:
    return [rnd(v, sig) for v in np.asarray(values, dtype=float)]


def _cell(v, sig: int):
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (float, int, np.floating, np.integer)):
        return rnd(v, sig)
    return v


def records(df: pd.DataFrame, sig: int = SIG) -> list[dict]:
    return [{k: _cell(v, sig) for k, v in row.items()} for row in df.to_dict(orient="records")]


def dumps(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                       allow_nan=False) + "\n").encode("ascii")


def numbers_tex() -> dict[str, str]:
    text = src("numbers.tex").read_text(encoding="utf-8")
    return dict(re.findall(r"^\\newcommand\{\\(\w+)\}\{(.*)\}\s*$", text, flags=re.M))


MACROS: dict[str, str] = {}
KEY_NUMBERS: list[dict] = []


def key_number(macro: str, value: float, fmt: str, label: str, source: str, view: str) -> dict:
    """Format ``value`` as the paper prints it and assert it equals the macro."""
    shown = format(value, fmt)
    if MACROS.get(macro) != shown:
        raise AssertionError(f"key number {macro}: dashboard {shown!r} != numbers.tex {MACROS.get(macro)!r}")
    entry = {"macro": macro, "text": shown, "value": rnd(value, 8), "label": label,
             "source": source, "view": view}
    KEY_NUMBERS.append(entry)
    return entry


_CHECK: dict[str, dict] = {}


def paper_number(macro: str, view: str) -> dict:
    """A value as printed (numbers.tex) whose derivation check_numbers.py already verifies:
    taken over with its class and source, provided its check status is OK or documented."""
    if not _CHECK:
        nc = pd.read_csv(src("results/numbers_check.csv"), dtype=str, keep_default_na=False)
        _CHECK.update({r["macro"]: r for r in nc.to_dict(orient="records")})
    r = _CHECK[macro]
    assert r["status"] in ("OK", "documented") and r["value"] == MACROS[macro], macro
    entry = {"macro": macro, "text": MACROS[macro], "value": None, "label": f"as printed ({r['cls']})",
             "source": r["source"], "view": view}
    KEY_NUMBERS.append(entry)
    return entry


# LaTeX table fragment -> cells (the generated tables/*.tex are what the paper prints).
# Subscripts are kept as the markup X_{...}, which the site renders as <sub>; footnote
# marks (\tnote) are dropped, the notes themselves are in the paper.
_UNIT = {r"\milli": "m", r"\kilo": "k", r"\mega": "M", r"\hecto": "h", r"\metre": "m", r"\gram": "g",
         r"\second": "s", r"\joule": "J", r"\pascal": "Pa", r"\celsius": "°C", r"\percent": "%"}


def _si(units: str) -> str:
    out, square = "", False
    for tok in re.findall(r"\\[a-z]+", units):
        if tok == r"\per":
            out += "/"
        elif tok == r"\square":
            square = True
        else:
            out += _UNIT[tok] + ("²" if square and tok not in (r"\milli", r"\kilo", r"\mega", r"\hecto") else "")
            square = square and tok in (r"\milli", r"\kilo", r"\mega", r"\hecto")
    return out


def _unwrap(c: str, cmd: str, keep=lambda inner: inner) -> str:
    """Replace every \\cmd{...} (nested braces allowed) by keep(inner)."""
    key = "\\" + cmd + "{"
    while (i := c.find(key)) >= 0:
        depth, j = 0, i + len(key) - 1
        for j in range(i + len(key) - 1, len(c)):
            depth += {"{": 1, "}": -1}.get(c[j], 0)
            if depth == 0:
                break
        c = c[:i] + keep(c[i + len(key):j]) + c[j + 1:]
    return c


_TEX_SUBS = [
    (r"\\tnote\{[^}]*\}", ""), (r"\\si(\[[^]]*\])?\{([^}]*)\}", lambda m: _si(m[2])),
    (r"\$([^$]*)\$", r"\1"), (r"\\pm", "±"), (r"\\Delta ?", "Δ"), (r"\\infty", "∞"),
    (r"--", "–"), (r"~", " "), (r"_([^{\s])", r"_{\1}"),
]
_LITERAL_US = ""                               # a literal underscore (\_, e.g. Hep\_160\_075)


def _tex_cell(c: str) -> str:
    c = c.replace(r"\_", _LITERAL_US).replace(r"_\mathrm{", "_{")     # t_\mathrm{vent} -> t_{vent}
    for cmd in ("mathrm", "textit", "textbf"):
        c = _unwrap(c, cmd)
    for pat, rep in _TEX_SUBS:
        c = re.sub(pat, rep, c)
    return re.sub(r"\s+", " ", c).strip().replace(_LITERAL_US, "_")


def tex_table(rel: str) -> dict:
    body = src(rel).read_text(encoding="utf-8")
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line.endswith(r"\\"):
            continue
        cells = []
        for c in line[:-2].split("&"):
            c = c.strip()
            mc = re.fullmatch(r"\\multicolumn\{(\d+)\}\{[^}]*\}\{(.*)\}", c)
            span = int(mc[1]) if mc else 1
            c = _tex_cell(mc[2] if mc else c)
            if "\\" in c or re.search(r"(?<!_)\{", c):
                raise ValueError(f"{rel}: unconverted LaTeX in cell {c!r}")
            cells += [c] + [""] * (span - 1)
        rows.append(cells)
    return {"header": rows[0], "rows": rows[1:], "source": rel}


# ----------------------------------------------------------------------------- meta + time series
def test_names(runs: pd.DataFrame, ch: pd.DataFrame) -> pd.DataFrame:
    """Display name and instrument setup of each test. The package ids (Hep_160_S2_R1) count the
    repetitions within an instrument setup S1-S4, which the paper does not name; the dashboard shows
    <series>_R<n> instead, n counting the tests of a series in the order they were run, and states
    the setup by what it changed: the height of the tripod LEM in F2 and the room of the SICK."""
    start = pd.to_datetime(runs.date + " " + runs.t0_local)
    n = runs.loc[start.sort_values(kind="stable").index].groupby("series").cumcount() + 1
    runs = runs.assign(name=runs.series + "_R" + n.reindex(runs.index).astype(str))
    tab = tex_table("tables/experiments_overview.tex")   # Table 1: number of runs per series
    i = tab["header"].index("Runs")
    assert {r[0]: int(r[i]) for r in tab["rows"]} == runs.series.value_counts().to_dict(), "runs per series != Table 1"
    assert runs.name.is_unique and not set(runs.name) & set(runs.run)

    def setup(run: str) -> str:
        c = ch[ch.run == run]
        lem = c.loc[(c.instrument == "LEM1") & (c.room == "F2"), "z_m"].dropna().unique()
        sick = c.loc[c.instrument == "SICK", "room"].dropna().unique()
        assert len(lem) == 1 and len(sick) <= 1, f"{run}: setup not unique"
        # the paper deploys the SICK in the 160 mm tests only; there, a test may lack a valid record
        valid = ((c.instrument == "SICK") & (c.status != "excluded")).any()
        pan = int(runs.loc[runs.run == run, "pan_mm"].iloc[0])
        sick_text = (f"SICK in {sick[0]}" if valid else f"SICK in {sick[0]}, no valid record") if pan == 160 \
            else "no SICK (deployed in the 160 mm tests only)"
        return f"tripod LEM in F2 at {lem[0]:g} m, {sick_text}"

    runs = runs.assign(setup_text=runs.run.map(setup))
    return runs


def build_timeseries(files: dict) -> dict:
    runs = read_csv(f"{TS_DIR}/runs.csv")
    events = read_csv(f"{TS_DIR}/events.csv")
    ch = read_csv(f"{TS_DIR}/channels.csv", dtype={"note": str})
    src(f"{TS_DIR}/SHA256SUMS")
    shipped: dict[str, pd.DataFrame] = {}
    for run in runs["run"]:
        data = read_csv(f"{TS_DIR}/{run}.csv")
        t_end = float(events.loc[(events.run == run) & (events.event == "test_end"), "t_s"].iloc[0])
        data = data[data.t_s < t_end - 1].reset_index(drop=True)   # as load_test(until_test_end=True)
        rc = ch[ch.run == run].set_index("column")
        cols = {}
        for c in data.columns:
            if c in ("t_s", "time_local"):
                continue
            if rc.loc[c, "status"] == "excluded":
                assert data[c].isna().all(), f"{run}/{c} excluded but not NaN"
                continue
            cols[c] = col(data[c])
        assert (data.t_s == data.t_s.round()).all()
        i0 = data.index[data.t_s == 0]
        assert len(i0) == 1, f"{run}: no unique t = 0 sample"
        files[f"ts/{run}.json"] = {
            "schema": SCHEMA, "run": run, "cut_s": rnd(t_end - 1),
            "t": [int(t) for t in data.t_s], "zero_index": int(i0[0]), "columns": cols,
            "source": f"{TS_DIR}/{run}.csv",
            "note": "raw values as committed (not zeroed); records cut 1 s before the logged test_end",
        }
        shipped[run] = pd.DataFrame({"t_s": data.t_s, **{c: files[f"ts/{run}.json"]["columns"][c] for c in cols}})
    ch_keep = ["run", "column", "quantity", "unit", "instrument", "room", "z_m", "wavelength_nm",
               "path_length_m", "processing", "status", "note"]
    meta = {
        "runs": records(test_names(runs, ch)),
        "events": records(events),
        "channels": records(ch[ch.column.isin(["t_s", "time_local"]) == False][ch_keep]),  # noqa: E712
    }
    return meta, shipped


def build_fds(files: dict) -> dict:
    fch = read_csv(f"{FDS_DIR}/fds_channels.csv")
    src(f"{FDS_DIR}/SHA256SUMS")
    shipped = {}
    for s in SERIES:
        case = FDS_CASE[s]
        d = read_csv(f"{FDS_DIR}/{case}_devc.csv")
        h = read_csv(f"{FDS_DIR}/{case}_hrr.csv", header=1)
        rows = fch[fch.case == case]
        files[f"fds/{s}.json"] = {
            "schema": SCHEMA, "series": s, "case": case, "deck": f"fds_decks/{case}.fds",
            "t": col(d.t_s, 6),
            "columns": {c: col(d[c]) for c in d.columns if c != "t_s"},
            "channels": records(rows[rows.column != "t_s"].drop(columns=["case"])),
            "hrr": {"t": col(h.Time, 6), "HRR_kW": col(h.HRR)},
            "source": [f"{FDS_DIR}/{case}_devc.csv", f"{FDS_DIR}/{case}_hrr.csv"],
        }
        src(f"fds_decks/{case}.fds")
        shipped[s] = d
    return shipped


# ----------------------------------------------------------------------------- matrices
def build_matrices(files: dict, ts: dict, runs: pd.DataFrame, fds: dict) -> None:
    M = "results/validation/matrices"
    lem, sick, fdsk = read_csv(f"{M}/ext_lem.csv"), read_csv(f"{M}/ext_sick.csv"), read_csv(f"{M}/ext_fds.csv")
    meta = read_csv(f"{M}/ext_meta.csv")
    out = {"schema": SCHEMA, "ext_lem": {}, "ext_sick": {}, "ext_fds": {},
           "ext_meta": records(meta),
           "source": [f"{M}/ext_lem.csv", f"{M}/ext_sick.csv", f"{M}/ext_fds.csv", f"{M}/ext_meta.csv"],
           "note": "ext_lem: LEM ensemble mean and SD (Bessel) of the zeroed tests on a 1 s grid, "
                   "window -30..1500 s; ext_sick: per-run SICK at 638 nm, zeroed; ext_fds: FDS beam k. "
                   "Both measured files are shown up to 1 s before the logged test_end (the earliest of the "
                   "series for the mean), the rule of the per-test time series: the last sample of the "
                   "Hep_160_075 mean (t = 1500 s) contains the instrument switch-off of five tests",
           "cut_s": {}}
    # README rule for the records (up to 1 s before the logged test_end), applied to the files of Figs. 4/6:
    # the shipped single tests already end there, so their last time is the cut
    run_cut = {run: float(d.t_s.max()) for run, d in ts.items()}
    for (s, r), g in lem.groupby(["series", "room"], sort=True):
        cut = min(run_cut[x] for x in runs.loc[runs.series == s, "run"])
        g = g[g.t_s <= cut]
        out["cut_s"][s] = rnd(cut)
        out["ext_lem"].setdefault(s, {})[r] = {"t": col(g.t_s), "mean": col(g["mean"]), "std": col(g["std"])}
    for (s, r, run), g in sick.groupby(["series", "room", "run"], sort=True):
        g = g[g.t_s <= run_cut[run]]
        out["ext_sick"].setdefault(s, {}).setdefault(r, {})[run] = {"t": col(g.t_s), "k": col(g.sick)}
    for (s, r), g in fdsk.groupby(["series", "room"], sort=True):
        out["ext_fds"].setdefault(s, {})[r] = {"t": col(g.t_s, 6), "k": col(g.k)}
    files["matrices.json"] = out

    # --- consistency: shipped single tests vs. the figure files -------------------------
    room_col = {"F1": "k_LEM4_F1_z2.3_638nm_per_m", "F2": "k_LEM3_F2_z2.3_638nm_per_m",
                "F3": "k_LEM2_F3_z2.3_638nm_per_m"}
    grid = np.arange(-30, 1501, 1.0)
    worst = 0.0
    for s in SERIES:
        ids = runs.loc[runs.series == s, "run"].tolist()
        for room, c in room_col.items():
            per, cut = [], np.inf
            for run in ids:
                d = ts[run]
                y = np.asarray(d[c], float) if c in d else np.full(len(d), np.nan)
                y = y - y[np.flatnonzero(d.t_s.to_numpy() == 0)[0]]
                per.append(np.interp(grid, d.t_s.to_numpy(float), y, left=np.nan, right=np.nan))
                cut = min(cut, d.t_s.max())
            with np.errstate(all="ignore"):
                m = np.nanmean(per, axis=0)
            ref = lem[(lem.series == s) & (lem.room == room)].set_index("t_s")["mean"].reindex(grid).to_numpy()
            ok = grid <= cut
            diff = np.nanmax(np.abs(m[ok] - ref[ok]))
            worst = max(worst, diff)
            assert diff < 2e-4, f"ext_lem {s}/{room}: shipped tests differ from ext_lem.csv by {diff:.2e} 1/m"
    print(f"  check: series means of the shipped LEM tests = ext_lem.csv (max |diff| {worst:.1e} 1/m, display rounding)")
    worst = 0.0
    for (s, r, run), g in sick.groupby(["series", "room", "run"]):
        d = ts[run]
        c = f"k_SICK_{r}_z2.3_638nm_per_m"
        y = np.asarray(d[c], float)
        y = y - y[np.flatnonzero(d.t_s.to_numpy() == 0)[0]]
        ref = g.set_index("t_s")["sick"]
        z = pd.Series(y, index=d.t_s.to_numpy(float)).reindex(ref.index)
        ok = z.notna() & ref.notna()
        diff = float(np.max(np.abs(z[ok] - ref[ok])))
        worst = max(worst, diff)
        assert diff < 2e-4, f"ext_sick {run}/{r}: {diff:.2e}"
    print(f"  check: shipped SICK 638 nm (zeroed) = ext_sick.csv (max |diff| {worst:.1e} 1/m)")
    beam = {"F1": "LEM_LOS_F1_2_3_k", "F2": "LEM_LOS_F2_2_3_k", "F3": "LEM_LOS_F3_2_3_k"}
    for s in SERIES:
        for r, c in beam.items():
            ref = fdsk[(fdsk.series == s) & (fdsk.room == r)]
            assert np.allclose(ref.t_s.to_numpy(), fds[s].t_s.to_numpy(), rtol=0, atol=1e-9)
            assert np.allclose(ref.k.to_numpy(), fds[s][c].to_numpy(), rtol=0, atol=1e-12), f"ext_fds {s}/{r}"
    print("  check: FDS beam columns = ext_fds.csv (exact)")


# ----------------------------------------------------------------------------- validation
_SENSOR_RE = [
    (re.compile(r"^Plume Impingement Temperature$"), lambda m: ("F1", None, "TC ceiling", "TC_Ceiling_F1")),
    (re.compile(r"^Temp\. Tree (\d) \(([\d.]+) m\)$"),
     lambda m: (f"F{m[1]}", float(m[2]), "TC", f"TC_F{m[1]}_{m[2].replace('.', '_')}")),
    (re.compile(r"^Extinction coefficient (F\d) LEM ([\d.]+) m$"),
     lambda m: (m[1], float(m[2]), "LEM", f"LEM_LOS_{m[1]}_{m[2].replace('.', '_')}_k")),
    (re.compile(r"^Extinction coefficient (F\d) SICK ([\d.]+) m$"),
     lambda m: (m[1], float(m[2]), "SICK", f"SICK_LOS_{m[1]}_k")),
]


def build_validation(files: dict, fds_channels: pd.DataFrame) -> None:
    V = "results/validation/fds_metrics"
    pooled = read_csv(f"{V}/guide_pooled.csv")
    per_series = read_csv(f"{V}/guide_series.csv")
    pts, metrics = [], []
    for s in SERIES:
        key = s.lower()
        mr = read_csv(f"{V}/_Simulation_Comparison_{key}_ysmatched/metrics_report.csv")
        lm = read_csv(f"{V}/_Simulation_Comparison_{key}_ysmatched/layer_metrics.csv")
        fc = fds_channels[fds_channels.case == FDS_CASE[s]].set_index("column")
        for r in mr.to_dict(orient="records"):
            for rx, f in _SENSOR_RE:
                m = rx.match(r["Sensor"])
                if m:
                    room, z, inst, fcol = f(m)
                    break
            else:
                raise ValueError(f"unmapped sensor {r['Sensor']!r}")
            assert fcol in fc.index, f"{s}: FDS column {fcol} not in fds_channels.csv"
            group = "Temperature" if "°" in str(r["Unit"]) else "Extinction"
            sick = inst == "SICK"
            fin = all(math.isfinite(r[k]) and r[k] > 0 for k in ("Peak_exp", "Peak_sim"))
            in_stat = (not sick) and fin and r["Peak_exp"] >= SIGNAL_MIN[group]
            metrics.append({**{k: (rnd(v) if isinstance(v, float) else v) for k, v in r.items()},
                            "series": s, "room": room, "z": z, "instrument": inst,
                            "fds_column": fcol, "measured_column": fc.loc[fcol, "measured"]
                            if isinstance(fc.loc[fcol, "measured"], str) else None})
            pts.append({"series": s, "group": group, "sensor": r["Sensor"], "room": room, "z": z,
                        "instrument": inst, "exp": rnd(r["Peak_exp"]), "sim": rnd(r["Peak_sim"]),
                        "in_stat": bool(in_stat)})
        for r in lm.to_dict(orient="records"):
            fin = all(math.isfinite(r[k]) and r[k] > 0 for k in ("Peak_exp", "Peak_sim"))
            pts.append({"series": s, "group": r["Quantity"], "sensor": r["Sensor"], "room": r["Sensor"][:2],
                        "z": None, "instrument": "TC tree", "exp": rnd(r["Peak_exp"]), "sim": rnd(r["Peak_sim"]),
                        "in_stat": bool(fin and r["Peak_exp"] >= SIGNAL_MIN[r["Quantity"]])})
    # the selection reproduces the committed pooled statistic exactly (from the unrounded pairs)
    exact = []
    for s in SERIES:
        key = s.lower()
        mr = pd.read_csv(REPO / V / f"_Simulation_Comparison_{key}_ysmatched/metrics_report.csv")
        mr["Group"] = np.where(mr["Unit"].str.contains("°"), "Temperature", "Extinction")
        mr = mr[~mr.Sensor.str.contains("SICK")]
        lm = pd.read_csv(REPO / V / f"_Simulation_Comparison_{key}_ysmatched/layer_metrics.csv")
        lm["Group"] = lm["Quantity"]
        exact.append(pd.concat([mr, lm], ignore_index=True))
    ex = pd.concat(exact, ignore_index=True)
    for r in pooled.to_dict(orient="records"):
        g = ex[(ex.Group == r["Group"]) & np.isfinite(ex.Peak_exp) & np.isfinite(ex.Peak_sim)
               & (ex.Peak_exp > 0) & (ex.Peak_sim > 0) & (ex.Peak_exp >= SIGNAL_MIN[r["Group"]])]
        st = guide_delta_sigma(np.log(g.Peak_sim / g.Peak_exp), SIGMA_E[r["Group"]])
        n_flag = sum(1 for p in pts if p["group"] == r["Group"] and p["in_stat"])
        assert st["n"] == r["n"] == n_flag, f"{r['Group']}: n {st['n']}/{n_flag} vs {r['n']}"
        assert abs(st["delta"] - r["delta"]) < 1e-12 and abs(st["sigma_M"] - r["sigma_M"]) < 1e-12, r["Group"]
    print("  check: in_stat selection reproduces guide_pooled.csv (n, delta, sigma_M exact)")

    gkey = {"Temperature": "Temperature", "Upper-layer T": "UpperLayerT",
            "Layer height": "LayerHeight", "Extinction": "Extinction"}
    stats = []
    for r in pooled.to_dict(orient="records"):
        g = gkey[r["Group"]]
        stats.append({
            "group": r["Group"], "n": int(r["n"]), "floored": bool(r["floored"]),
            "delta": key_number(f"valFdsDelta{g}", r["delta"], ".2f", f"bias factor δ ({r['Group']})", f"{V}/guide_pooled.csv", "validation"),
            "sigma_M": key_number(f"valFdsSigmaM{g}", r["sigma_M"], ".2f", f"model σ_M ({r['Group']})", f"{V}/guide_pooled.csv", "validation"),
            "sigma_E": key_number(f"valFdsSigmaE{g}", r["sigma_E"], ".2f", f"experimental σ_E ({r['Group']})", f"{V}/guide_pooled.csv", "validation"),
        })
        key_number(f"valFdsN{g}", int(r["n"]), "d", f"peak pairs n ({r['Group']})", f"{V}/guide_pooled.csv", "validation")
    sname = {"Hep_160_075": "SevenFive", "Hep_160_150": "OneFifty", "Hep_220_300": "ThreeHundred"}
    ser = []
    for r in per_series.to_dict(orient="records"):
        s = next(k for k in SERIES if k.lower() == r["Series"])
        ser.append({"series": s, "n": int(r["n"]), "sigma_M": rnd(r["sigma_M"]),
                    "delta": key_number(f"valFdsDeltaExtSer{sname[s]}", r["delta"], ".2f",
                                        f"extinction bias δ_k, series {s}", f"{V}/guide_series.csv", "validation")})
    files["validation.json"] = {
        "schema": SCHEMA, "points": pts, "metrics": metrics, "pooled": stats, "per_series": ser,
        "signal_min": SIGNAL_MIN, "sigma_E": SIGMA_E,
        "source": [f"{V}/_Simulation_Comparison_<series>_ysmatched/metrics_report.csv",
                   f"{V}/_Simulation_Comparison_<series>_ysmatched/layer_metrics.csv",
                   f"{V}/guide_pooled.csv", f"{V}/guide_series.csv"],
        "note": "in_stat: the pairs of the pooled statistic (LEM only, finite positive peaks, "
                "measured peak at or above signal_min); SICK points are co-located with LEM points",
    }


# ----------------------------------------------------------------------------- LEM-SICK
def build_lemsick(files: dict) -> None:
    c = "results/measurement/crosscheck_lem_sick.csv"
    w = "results/measurement/widmann_exponent.csv"
    cc, wx = read_csv(c), read_csv(w)
    keys = {
        "mean_bias": key_number("valSickLemMeanBiasPct", float(cc.bias_pct.mean()), "+.0f",
                                "mean per-run SICK-LEM bias (%)", c, "lemsick"),
        "n_runs": key_number("valSickLemNRuns", int(len(cc)), "d", "co-located runs", c, "lemsick"),
        "med_dev_lo": key_number("valSickLemMedDevLoPct", float(cc.median_abs_pct.quantile(0.25)), ".0f",
                                 "per-run |median| deviation, lower quartile (%)", c, "lemsick"),
        "med_dev_hi": key_number("valSickLemMedDevHiPct", float(cc.median_abs_pct.quantile(0.75)), ".0f",
                                 "per-run |median| deviation, upper quartile (%)", c, "lemsick"),
    }
    s = wx.set_index("test").loc["lem_sick"]
    keys.update({
        "widmann_n": key_number("valWidmannExpSick", float(s.n_median), ".2f", "in-situ exponent (median)", w, "lemsick"),
        "widmann_lo": key_number("valWidmannExpSickLo", float(s.lo), ".2f", "in-situ exponent, lower quartile", w, "lemsick"),
        "widmann_hi": key_number("valWidmannExpSickHi", float(s.hi), ".2f", "in-situ exponent, upper quartile", w, "lemsick"),
        "factor_dev": key_number("valWidmannFactorDevPct", float(s.factor_dev_pct), ".0f",
                                 "largest normalisation-factor deviation (%)", w, "lemsick"),
    })
    files["lemsick.json"] = {"schema": SCHEMA, "crosscheck": records(cc), "widmann": records(wx),
                             "keys": keys, "widmann_factor": rnd((638.0 / 880.0) ** -1.0088),
                             "source": [c, w]}


# ----------------------------------------------------------------------------- numbers
def build_numbers(files: dict) -> None:
    rel = "results/numbers_check.csv"
    nc = pd.read_csv(src(rel), dtype=str, keep_default_na=False)
    bad = [r.macro for r in nc.itertuples() if MACROS.get(r.macro) != r.value]
    assert not bad, f"numbers_check.csv disagrees with numbers.tex: {bad}"
    assert set(nc.macro) == set(MACROS), "numbers_check.csv and numbers.tex list different macros"
    assert set(nc.status) <= {"OK", "documented"}, set(nc.status)
    files["numbers.json"] = {"schema": SCHEMA, "source": [rel, "numbers.tex"],
                             "rows": [{"macro": r.macro, "value": r.value, "recomputed": r.recomputed,
                                       "cls": r.cls, "source": r.source, "status": r.status}
                                      for r in nc.sort_values("macro").itertuples()]}


# ----------------------------------------------------------------------------- geometry
def _xyz(pos: str) -> list[float]:
    kind, vals = pos.split("=")
    return [float(v) for v in vals.split(",")]


def build_geometry(files: dict, fds_channels: pd.DataFrame) -> None:
    import plot_apartment_geometry as G   # drawing geometry of Fig. 1 (deck coordinates)
    src("scripts/plot_apartment_geometry.py")
    base = fds_channels[fds_channels.case == FDS_CASE[SERIES[0]]]
    for s in SERIES[1:]:
        other = fds_channels[fds_channels.case == FDS_CASE[s]]
        assert base.position.fillna("").tolist() == other.position.fillna("").tolist(), \
            f"device positions differ between {SERIES[0]} and {s}"
    # a beam's measured column sits on its derived <beam>_k row (path-mean k)
    k_measured = {r["column"][:-2]: r["measured"] for r in base.to_dict(orient="records")
                  if r["column"].endswith("_k") and isinstance(r["measured"], str)}
    devices = []
    for r in base.to_dict(orient="records"):
        if not isinstance(r["position"], str) or r["column"].endswith("_k"):
            continue
        kind = "beam" if r["position"].startswith("XB") else "point"
        measured = r["measured"] if isinstance(r["measured"], str) else k_measured.get(r["column"])
        devices.append({"id": r["column"], "quantity": r["quantity"], "unit": r["unit"], "room": r["room"],
                        "z": rnd(r["z_m"]) if isinstance(r["z_m"], float) else None, "kind": kind,
                        "coords": _xyz(r["position"]), "measured": measured})
    for room, x0, x1, y, zs in G.lem:   # the drawing geometry carries the deck beams
        for z in zs:
            d = next(d for d in devices if d["id"] == f"LEM_LOS_{room}_{str(z).replace('.', '_')}")
            assert d["coords"][:4] == [x0, x1, y, y], d["id"]
    files["geometry.json"] = {
        "schema": SCHEMA,
        "rooms": {k: v.tolist() for k, v in G.room_polys.items()},
        "room_height": 2.55,
        "doors": [{"xb": list(xb), "rooms": rooms} for xb, rooms in G.doors],
        "windows": [{"xb": list(xb), "room": room} for xb, room in G.windows],
        "sealed_doors": [list(G.sealed_door)] + [list(d) for d in G.fc_sealed_doors],
        "pan_xb": list(G.pan_xb), "load_cell_xb": list(G.load_cell_xb),
        "devices": devices,
        "axes": "FDS coordinates in m; x towards the facade (window walls), y along the room sequence F1-F2-FC-F3",
        "source": ["scripts/plot_apartment_geometry.py", f"{FDS_DIR}/fds_channels.csv"],
    }


# ----------------------------------------------------------------------------- model inputs, sensitivity
_TEX_PLAIN = [(r"\$", ""), (r"\\upmu", "µ"), (r"\\times", "×"), (r"\\approx", "≈"), (r"\\chi", "χ"), (r"~", " "), (r"\\[ ,]", " "),
              (r"_\{([^}]*)\}", r"\1"), (r"_(\w)", r"\1"), (r"[{}]", "")]


def _plain_tex(t: str) -> str:
    for pat, rep in _TEX_PLAIN:
        t = re.sub(pat, rep, t)
    return re.sub(r"\s+", " ", t).strip()


def _deck_params(case: str) -> dict:
    text = src(f"fds_decks/{case}.fds").read_text(encoding="utf-8")
    num = lambda k: float(re.search(rf"\b{k}\s*=\s*([-+0-9.Ee]+)", text)[1])  # noqa: E731
    return {k: num(k) for k in ("SOOT_YIELD", "HEAT_OF_COMBUSTION", "RADIATIVE_FRACTION", "CO_YIELD",
                                "MASS_EXTINCTION_COEFFICIENT")}


def build_inputs(files: dict) -> None:
    import plot_fds_sensitivity_tornado as T      # the bar logic of Fig. 7 (spans, exclusions, noise)
    src("scripts/plot_fds_sensitivity_tornado.py")
    H = "results/measurement/hrr/hrr_summary.csv"
    hs = read_csv(H)
    tag = {"hep_160_075": "Small", "hep_160_150": "Mid", "hep_220_300": "Large"}
    hrr = {}
    for s in SERIES:
        g = hs[hs.series == s.lower()].sort_values("t_s")
        peak = key_number(f"valHrrPeak{tag[s.lower()]}", int(float(g.hrr_mean.max()) + 0.5), "d",
                          f"peak of the series-mean heat release rate, {s} (kW)", H, "inputs")
        hrr[s] = {"t": col(g.t_s), "hrr_mean": col(g.hrr_mean), "hrr_std": col(g.hrr_std),
                  "m_mean": col(g.m_mean), "m_std": col(g.m_std), "peak": peak}

    # Table 4: baseline values as in the decks, each checked against the paper
    deck = {s: _deck_params(FDS_CASE[s]) for s in SERIES}
    for k in ("HEAT_OF_COMBUSTION", "RADIATIVE_FRACTION", "CO_YIELD", "MASS_EXTINCTION_COEFFICIENT"):
        assert len({d[k] for d in deck.values()}) == 1, f"{k} differs between the baseline decks"
    ys = {s: key_number(f"valRstYs{n}", deck[s]["SOOT_YIELD"], ".4f", f"soot yield of the {s} baseline deck (g/g)",
                        f"fds_decks/{FDS_CASE[s]}.fds", "inputs")
          for s, n in zip(SERIES, ("Small", "Large", "Huge"))}
    d0 = deck[SERIES[0]]
    dhc = key_number("valRstDhchHh", d0["HEAT_OF_COMBUSTION"] / 1000.0, ".3f", "effective heat of combustion (MJ/kg)",
                     f"fds_decks/{FDS_CASE[SERIES[0]]}.fds", "inputs")
    # constants printed as literals in Table 4 (not macros): the decks must carry them
    assert d0["MASS_EXTINCTION_COEFFICIENT"] == 7566.0 and d0["RADIATIVE_FRACTION"] == 0.4 and d0["CO_YIELD"] == 0.01, d0
    # provenance chain of the measured inputs: Table S4 runs -> macro -> deck
    R = "results/measurement/rst_apartment_runs.csv"
    rst = read_csv(R)
    cfg = rst.groupby(["pan_mm", "fuel_g"])["ys_gpg"].mean()
    for s, (pan, g) in zip(SERIES, ((160, 75), (160, 150), (220, 300))):
        assert format(cfg.loc[(pan, g)], ".4f") == ys[s]["text"], f"{s}: Table S4 configuration mean != deck soot yield"
    assert format(rst.loc[~rst.dhch_excluded, "dhch_mj"].mean(), ".3f") == dhc["text"], "Table S4 mean != deck heat of combustion"
    km = 4.8081 * 0.638 ** -1.0088                   # Widmann correlation (lambda in um) at the 638 nm reference
    assert format(km, ".3f") == "7.566" and d0["MASS_EXTINCTION_COEFFICIENT"] / 1000 == 7.566, km
    pn = {m: paper_number(m, "inputs") for m in (
        "valRstYsHh", "valRstYsHhSd", "valRstYsHhN", "valRstDhchHhN", "valCoreHeatSysLoPct", "valCoreHeatSysHiPct",
        "valCoreFuelSevenHcLo", "valCoreFuelSevenHcHi", "valCoreFuelSevenNhepPct", "valCoreFuelSevenMchPct",
        "valCoreFuelSevenDmcpPct", "valCoreFuelSevenIsoPct", "valCoreFuelSevenNaphLoPct",
        "valCoreFuelSevenNaphHiPct", "valCoreFuelSevenOpenPct", "valCoreFuelSevenFormulaHLo", "valCoreFuelSevenFormulaHHi",
        "valSfpeYsCoreFuelSevenLo", "valSfpeYsCoreFuelSevenHi", "valRstConfigSpreadHhPct",
        "valCoreHeatScaleFactor", "valCoreHeatScaleFactorErr")}
    t = lambda m: pn[m]["text"]  # noqa: E731
    # symbols with subscripts as X_{...} markup (rendered as <sub> by the site); provenance from Sections 2.4, 3.2, SM S3/S4
    table4 = {"header": ["Parameter", "FDS keyword", "Baseline value", "Where it comes from"], "rows": [
        ["Fuel surrogate", "FUEL", "'N-HEPTANE' (C_{7}H_{16})",
         f"FDS predefined single-species surrogate of the C7-UVCB fuel; its H/C ratio of 2.29 lies slightly above the "
         f"batch's {t('valCoreFuelSevenHcLo')}–{t('valCoreFuelSevenHcHi')} ({{REF:secCfdParams}})"],
        ["Soot yield Y_{s}", "SOOT_YIELD", f"{ys[SERIES[0]]['text']}–{ys[SERIES[1]]['text']} g/g",
         "measured photometrically in the furniture calorimeter on the same fuel batch; per series the mean of the two "
         "runs with the same pan and charge (configuration-matched, {REF:tabS_rst})"],
        ["Mass-specific extinction coefficient K_{m}", "MASS_EXTINCTION_COEFFICIENT", "7.566 m²/g",
         "Widmann correlation K_{m} = 4.8081 λ^{−1.0088} (λ in µm) at the 638 nm reference; the same correlation underlies "
         "the photometric soot yield, so the absolute K_{m} cancels in the predicted extinction ({REF:secCfdParams}, {REF:secDiscKm})"],
        ["Effective heat of combustion ΔH_{ch}", "HEAT_OF_COMBUSTION", f"{dhc['text']} MJ/kg",
         f"furniture calorimeter, same fuel batch: mean of the {t('valRstDhchHhN')} runs of the first calorimeter series "
         f"({{REF:tabS_rst}}; the second series differs in its heat-release scale by the factor k = {t('valCoreHeatScaleFactor')} ± "
         f"{t('valCoreHeatScaleFactorErr')}, so it is not pooled); two-sided systematic of about "
         f"{t('valCoreHeatSysLoPct').replace('-', '−')} % (generic oxygen-consumption constant) to {t('valCoreHeatSysHiPct')} % "
         "(scale of the calorimeter series) ({REF:secRst})"],
        ["Radiative fraction χ_{r}", "RADIATIVE_FRACTION", "0.40",
         "FDS default for n-heptane, representative of sooty pool fires at small scale (Beyler); 0.35 and 0.50 in the "
         "sensitivity study"],
        ["CO yield Y_{CO}", "CO_YIELD", "0.010 g/g",
         "Tewarson's tabulated reference value; negligible direct effect on the optical field, not varied"]],
        "series": [{"series": s, "ys": ys[s]["text"]} for s in SERIES],
        "pooled": f"{t('valRstYsHh')} ± {t('valRstYsHhSd')} g/g (n = {t('valRstYsHhN')})",
        "checks": "Y_{s} and ΔH_{ch} recomputed from {REF:tabS_rst} and K_{m} from the Widmann correlation; all values checked "
                  "against the FDS input files and the paper's numbers"}
    fuel = {"table_s2": tex_table("tables/core_fuel_composition.tex"),
            "table_s4": tex_table("tables/rst_apartment_runs.tex"),
            "numbers": {m: pn[m]["text"] for m in pn}}

    S = "results/simulation/fds_sensitivity.csv"
    N = "results/simulation/fds_seed_noise.csv"
    df = read_csv(S)
    df = df[(df.group != "Baseline") & ~df.run.isin(["pan175", "explchem_nodep_rh", "dhc_e127"])]   # as main() of Fig. 7
    noise = read_csv(N).set_index("quantity")["max_abs_dev_pct"].to_dict()
    groups = list(dict.fromkeys(df.group))
    width = lambda g: max(T.span(df[df.group == g], c, g)[1] - T.span(df[df.group == g], c, g)[0]  # noqa: E731
                          for _, c in T.EXT_ROOMS)
    groups = sorted(groups, key=width, reverse=True)
    bars = []
    for g in groups:
        rows = df[df.group == g]
        for qty, rooms in (("k", T.EXT_ROOMS), ("dTu", T.TMP_ROOMS)):
            for room, c in rooms:
                if c is None:
                    continue
                lo, hi = T.span(rows, c, g)
                bars.append({"group": g, "quantity": qty, "room": room, "lo": rnd(lo), "hi": rnd(hi),
                             "noise": rnd(noise[T.NOISE_QTY[c]]),
                             "cases": [{"case": _plain_tex(r["case"]), "run": r["run"], "pct": rnd(r[c]),
                                        "in_range": r["run"] not in T.EXCLUDE_FROM_RANGE} for r in rows.to_dict(orient="records")]})
    files["inputs.json"] = {
        "schema": SCHEMA, "hrr": hrr, "table4": table4, "fuel": fuel,
        "tornado": {"groups": groups, "bars": bars, "room_colors": T.ROOM_C,
                    "excluded": sorted(T.EXCLUDE_FROM_RANGE), "from_zero": sorted(T.SCENARIO_FROM_ZERO)},
        "source": [H, S, N, R, "tables/core_fuel_composition.tex", "tables/rst_apartment_runs.tex"]
                  + [f"fds_decks/{FDS_CASE[s]}.fds" for s in SERIES],
    }


# ----------------------------------------------------------------------------- key result at a glance
# The overview's summary after the paper's graphical abstract (scripts/plot_cga_validation.py of
# the paper repository): the same numbers, selected and checked the same way.
CGA_NUMERIC_BC_GROUPS = ("Grid resolution", "Turbulence model", "Radiative fraction",
                         "Leakage area", "Fire-source area", "Heat of combustion")
CGA_DEPOSITION_PHYSICAL = ("sootdep_d01_rh", "sootdep_d1_rh", "sootdep_binned_rh")


def build_glance(files: dict) -> dict:
    pairs = [p for p in files["validation.json"]["points"] if p["group"] == "Extinction" and p["in_stat"]]
    assert len(pairs) == int(MACROS["valFdsNExtinction"]) == 14
    S = "results/simulation/fds_sensitivity.csv"
    sens = read_csv(S).set_index("run")
    fuel = key_number("valSensFuelExtPct", float(sens.loc["ys015", "dk_mean_pct"]), "+.0f",
                      "change of the predicted peak k for a pure n-heptane soot yield (%)", S, "start")
    yshi = key_number("valSensYsExtHiPct", float(sens.loc["ys049", "dk_mean_pct"]), "+.0f",
                      "change of the predicted peak k for a handbook-level soot yield (%)", S, "start")
    # the handbook-level case as the graphical abstract labels it ("≈ 0.05 g/g"), from the case's yield
    ys_case = float(re.fullmatch(r"\$Y_s=([0-9.]+)\$", sens.loc["ys049", "case"])[1])
    ys_handbook = format(ys_case, ".2f")
    assert ys_case == 0.049 and ys_handbook == "0.05", ys_case
    nb = sens[sens.group.isin(CGA_NUMERIC_BC_GROUPS) | sens.index.isin(CGA_DEPOSITION_PHYSICAL)]
    vals = nb[["dk_F1_pct", "dk_F2_pct", "dk_F3_pct"]].to_numpy(float)
    nb_lo, nb_hi = float(vals.min()), float(vals.max())
    assert abs(vals).max() == nb_hi                  # "up to" is the largest magnitude
    hi = key_number("valSensGridExtMaxRoomPct", int(round(nb_hi)), "d",
                    "largest per-room change of the peak k over numerics and boundary conditions (%)", S, "start")
    wall = paper_number("valWallBcExtMaxPct", "start")
    nb_lo = min(nb_lo, -float(wall["text"]))           # cold-wall limit of the wall-BC bracket (SM S13)
    ratio = max(p["sim"] / p["exp"] for p in pairs)
    assert format(ratio, ".2f") == MACROS["valFdsExtMaxPairRatio"], ratio
    return {"pairs": [{k: p[k] for k in ("series", "sensor", "room", "z", "exp", "sim")} for p in pairs],
            "fuel": fuel["text"], "ys_hi": yshi["text"], "nb_lo": rnd(nb_lo), "nb_hi": rnd(nb_hi), "nb_text": hi["text"],
            "ys_handbook": ys_handbook, "source": [S, "results/validation/fds_metrics/"]}


# ----------------------------------------------------------------------------- meta / style
def build_meta(files: dict, meta: dict) -> None:
    ov = read_csv("results/measurement/experiments_overview.csv")
    amb = read_csv("results/measurement/ambient.csv")
    runs = pd.DataFrame(meta["runs"])
    series = []
    for s in SERIES:
        k = s.lower()
        series.append({"key": s, "style": k, "label": _plain(PS.SERIES_LABEL[k]),
                       "runs": runs.loc[runs.series == s, "run"].tolist(), "fds_case": FDS_CASE[s]})
    meta.update({
        "schema": SCHEMA,
        "series": series,
        "table1": tex_table("tables/experiments_overview.tex"),
        "table2": tex_table("tables/ambient.tex"),
        "experiments_overview": records(ov), "ambient": records(amb),
        "key_numbers": sorted(KEY_NUMBERS, key=lambda e: e["macro"]),
        "citation": _citation(),
    })
    files["meta.json"] = meta


def _plain(label: str) -> str:
    return label.replace(r"\,", " ")


def _citation() -> dict:
    text = src("CITATION.cff").read_text(encoding="utf-8")
    get = lambda k: (re.search(rf"^{k}:\s*\"?([^\"\n]*)\"?\s*$", text, flags=re.M) or [None, None])[1]  # noqa: E731
    return {"title": get("title"), "version": get("version"), "date_released": get("date-released"),
            "license": get("license"), "repository": get("repository-code"), "doi": get("doi")}


def style_tokens() -> bytes:
    import matplotlib.colors as mc
    marker = {"o": "circle", "s": "square", "^": "triangle-up", "D": "diamond"}
    tok = {
        "instrument": {k: {"color": mc.to_hex(c), "symbol": marker[m]} for k, (c, m) in PS.INSTRUMENT_STYLE.items()},
        "fds": {"color": mc.to_hex(PS.FDS_COLOR)},
        "fds_ideal": {"color": mc.to_hex(PS.FDS_IDEAL_STYLE["color"]), "dash": "dash"},
        "series": {k: {"color": mc.to_hex(PS.SERIES_COLOR[k]), "symbol": marker[PS.SERIES_MARKER[k]],
                       "label": _plain(PS.SERIES_LABEL[k])} for k in PS.SERIES_KEYS},
    }
    src("scripts/plot_style.py")
    body = json.dumps(tok, sort_keys=True, indent=2, ensure_ascii=True)
    return ("// Generated by scripts/build_dashboard_data.py from scripts/plot_style.py. Do not edit by hand.\n"
            f"export const TOKENS = {body};\n").encode("ascii")


# ----------------------------------------------------------------------------- main
def build() -> dict[str, bytes]:
    MACROS.update(numbers_tex())
    files: dict = {}
    meta, ts = build_timeseries(files)
    fds = build_fds(files)
    runs = pd.DataFrame(meta["runs"])
    fch = pd.read_csv(REPO / FDS_DIR / "fds_channels.csv")
    build_matrices(files, ts, runs, fds)
    build_validation(files, fch)
    build_lemsick(files)
    build_numbers(files)
    build_geometry(files, fch)
    build_inputs(files)
    meta["glance"] = build_glance(files)
    build_meta(files, meta)
    out = {f"data/{k}": dumps(v) for k, v in files.items()}
    out["app/style_tokens.js"] = style_tokens()
    out["data/manifest.json"] = dumps({
        "schema": SCHEMA,
        "generator": "scripts/build_dashboard_data.py",
        # text sources hashed with LF line ends, as git stores them (.gitattributes eol=lf), so the
        # manifest does not depend on how a working copy was checked out
        "sources": [{"path": rel, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
                    for rel, b in ((rel, p.read_bytes().replace(b"\r\n", b"\n")) for rel, p in sorted(_sources.items()))],
        "outputs": [{"path": f"dashboard/{k}", "bytes": len(v), "sha256": hashlib.sha256(v).hexdigest()}
                    for k, v in sorted(out.items())],
        # static files copied into the site (provenance in dashboard/vendor/README.md)
        "assets": [{"path": p.relative_to(REPO).as_posix(), "bytes": p.stat().st_size,
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in ASSETS],
    })
    return out


ASSETS = [OUT / "vendor" / "plotly-cartesian-2.35.2.min.js"]
for _a in ASSETS:
    assert _a.is_file(), f"missing static asset {_a.relative_to(REPO)}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="compare with the files on disk, write nothing")
    args = ap.parse_args()
    out = build()
    if args.check:
        bad = [k for k, v in sorted(out.items())
               if not (OUT / k).is_file() or (OUT / k).read_bytes() != v]
        expected = {OUT / k for k in out}
        extra = sorted(str(p.relative_to(OUT)) for p in DATA.rglob("*.json") if p not in expected)
        for k in bad:
            print(f"differs: dashboard/{k}")
        for k in extra:
            print(f"not generated: dashboard/{k}")
        print("dashboard data: " + ("up to date" if not bad and not extra else "OUT OF DATE"))
        return 1 if bad or extra else 0
    for k, v in sorted(out.items()):
        p = OUT / k
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.is_file() or p.read_bytes() != v:
            p.write_bytes(v)
    for p in sorted(DATA.rglob("*.json")):          # files of an earlier build that are no longer generated
        if p not in {OUT / k for k in out}:
            p.unlink()
            print(f"removed stale {p.relative_to(REPO)}")
    total = sum(len(v) for v in out.values())
    print(f"wrote {len(out)} files to dashboard/ ({total / 1e6:.2f} MB); "
          f"{len(KEY_NUMBERS)} key numbers match numbers.tex")
    return 0


if __name__ == "__main__":
    sys.exit(main())
