#!/usr/bin/env python
"""One-command regeneration of the paper's figures and computational tables.

Two stages, in dependency order:

  data     external raw measurement / simulation data -> committed intermediate
           CSVs. Depends on external archives; each step is guarded and skips
           cleanly when its archive is not available.
  figures  committed CSVs / committed inputs -> the paper figures. The committed
           subset needs no external archive at all.

  all = data then figures.

Usage:
    python run_all.py list                 # registry of targets + repro status
    python run_all.py figures              # regenerate every figure target
    python run_all.py figures --committed  # only the no-archive-needed subset
    python run_all.py data                 # rebuild the intermediate CSVs
    python run_all.py all
    python run_all.py --only geometry hrr  # run named targets, any stage
    python run_all.py figures --dry-run    # print the plan, run nothing

Design notes
------------
* Idempotent: every target overwrites fixed output paths; figure PDFs are
  byte-deterministic (SOURCE_DATE_EPOCH, see scripts/plot_style.py).
* Each target declares the external roots it needs (paths.available guards them)
  and whether it is reproducible from committed data alone.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
import paths as P  # noqa: E402

REPO = P.REPO_ROOT
# committed per-test time series; the measurement reductions read them when the
# measurement archive is not present
TIMESERIES = P.MEAS_RESULTS / "timeseries" / "runs.csv"


@dataclass
class Target:
    key: str
    stage: str                       # "data" | "figures"
    title: str
    artefact: str                    # what it (re)generates
    cmd: list[str] | None = None     # argv after the python executable; None = not runnable yet
    cwd: Path = REPO
    requires: list = field(default_factory=list)   # external roots that must be present
    committed: bool = False           # reproducible from committed data alone?
    note: str = ""


def _scripts(*argv: str) -> list[str]:
    return list(argv)


TARGETS: list[Target] = [
    # ---------------- data stage (external-archive-dependent) ----------------
    Target(
        "reprocess", "data",
        "Re-process measurement runs un-clipped -> data/reprocessed",
        "data/reprocessed/*/1_Processed_data/*_processed.csv",
        cmd=_scripts(str(REPO / "scripts" / "reprocess_unclipped.py")),
        cwd=REPO / "scripts", requires=[P.MEAS_ROOT],
        note="feeds the per-test time series export",
    ),
    Target(
        "export_timeseries", "data",
        "Export the per-test measured time series -> results/measurement/timeseries/",
        "results/measurement/timeseries/{Hep_*.csv, runs.csv, events.csv, channels.csv}",
        cmd=_scripts(str(REPO / "scripts" / "export_timeseries.py")),
        cwd=REPO / "scripts", requires=[P.REPROCESSED_DIR, P.MEAS_ROOT],
        note="needs the `reprocess` step first; the measurement reductions below read "
             "these files when the measurement archive is absent",
    ),
    Target(
        "export_fds_timeseries", "data",
        "Export the FDS baseline time series at the instrument positions -> results/simulation/timeseries/",
        "results/simulation/timeseries/{hep_*_ysmatched_devc.csv, hep_*_ysmatched_hrr.csv, fds_channels.csv}",
        cmd=_scripts(str(REPO / "scripts" / "export_fds_timeseries.py")),
        cwd=REPO / "scripts", requires=[P.FDS_OUTPUT_ROOT],
        note="the devices of the three baseline runs at the instrument positions",
    ),
    Target(
        "reduce_hrr", "data",
        "Derive the HRR from the committed mass traces -> results/measurement/hrr/hrr_summary.csv",
        "results/measurement/hrr/hrr_summary.csv",
        cmd=_scripts(str(REPO / "scripts" / "reduce_hrr_from_mass.py")),
        cwd=REPO / "scripts", committed=True,
        requires=[REPO / "results" / "measurement" / "hrr" / "mass_trials.csv"],
        note="feeds the committed HRR figure; needs no external data (the mass "
             "traces are committed and the effective heat of combustion is a constant)",
    ),
    Target(
        "reduce_matrices", "data",
        "Reduce extinction/temperature matrices -> results/validation/matrices/*.csv",
        "results/validation/matrices/ext_lem.csv, ext_sick.csv, ext_meta.csv, temp_prof.csv, "
        "temp_ceil.csv, ext_fds.csv, temp_fds.csv, temp_fds_plume.csv",
        cmd=_scripts(str(REPO / "scripts" / "reduce_matrices.py")),
        cwd=REPO / "scripts", requires=[TIMESERIES], committed=True,
        note="feeds the committed matrices figures; round-trip-exact CSVs. Measured "
             "and FDS curves from the archives or, without them, from the committed "
             "measured and FDS baseline time series",
    ),
    Target(
        "fds_sensitivity", "data",
        "FDS single-parameter sensitivity peaks -> results/simulation/fds_sensitivity.csv",
        "results/simulation/fds_sensitivity.csv, results/simulation/fds_sensitivity_summary.csv",
        cmd=_scripts(str(REPO / "scripts" / "fds_sensitivity_results.py")),
        cwd=REPO / "scripts", requires=[P.FDS_OUTPUT_ROOT],
        note="feeds the committed tornado figure + the peak columns of Table S13",
    ),
    Target(
        "fds_sensitivity_nrmse", "data",
        "FDS sensitivity trace NRMSE -> results/simulation/fds_sensitivity_nrmse.csv",
        "results/simulation/fds_sensitivity_nrmse.csv",
        cmd=_scripts(str(REPO / "scripts" / "fds_sensitivity_nrmse.py")),
        cwd=REPO / "scripts", requires=[P.FDS_OUTPUT_ROOT],
        note="feeds the NRMSE columns of Table S13 (complements fds_sensitivity)",
    ),
    Target(
        "seed_noise", "data",
        "LES run-to-run variability (RND_SEED realisations) -> results/simulation/fds_seed_noise.csv",
        "results/simulation/fds_seed_noise.csv, results/simulation/fds_seed_noise_axes.csv",
        cmd=_scripts(str(REPO / "scripts" / "fds_seed_noise.py")),
        cwd=REPO / "scripts", requires=[P.FDS_OUTPUT_ROOT],
        note="grey noise bands of the tornado figure + the run-to-run values of SM S13 "
             "(needs fds_sensitivity first)",
    ),
    Target(
        "grid_convergence", "data",
        "FDS four-grid convergence peaks -> results/simulation/grid_convergence.csv",
        "results/simulation/grid_convergence.csv, results/simulation/grid_convergence_summary.csv",
        cmd=_scripts(str(REPO / "scripts" / "grid_convergence.py")),
        cwd=REPO / "scripts", requires=[P.FDS_OUTPUT_ROOT],
        note="feeds the grid-convergence table",
    ),
    Target(
        "binned_soot", "data",
        "Size evolution of the binned soot -> results/simulation/sootdep_binned_rh_bins.csv",
        "results/simulation/sootdep_binned_rh_bins.csv",
        cmd=_scripts(str(REPO / "scripts" / "reduce_binned_soot.py")),
        cwd=REPO / "scripts", requires=[P.FDS_OUTPUT_ROOT],
        note="per-bin airborne soot mass of the agglomerating deposition case (Table S11 note d, SM S13)",
    ),
    Target(
        "wallbc_span", "data",
        "FDS wall thermal-BC bracket peaks -> results/simulation/wallbc_span.csv",
        "results/simulation/wallbc_span.csv, results/simulation/wallbc_span_summary.csv",
        cmd=_scripts(str(REPO / "scripts" / "wallbc_span.py")),
        cwd=REPO / "scripts", requires=[P.FDS_OUTPUT_ROOT],
        note="feeds the wall thermal-BC numbers",
    ),
    Target(
        "point_vs_path", "data",
        "FDS point vs path-mean extinction along the LEM/SICK beams -> "
        "results/validation/extinction_point_vs_path*.csv",
        "results/validation/extinction_point_vs_path.csv, "
        "results/validation/extinction_point_vs_path_summary.csv",
        cmd=_scripts(str(REPO / "scripts" / "extinction_point_vs_path.py")),
        cwd=REPO / "scripts", requires=[P.FDS_OUTPUT_ROOT],
        note="integrates the 3D extinction slice along each beam of the FDS input file (SM S8)",
    ),
    Target(
        "reduce_blowerdoor", "data",
        "Reduce blower-door pressurisation series -> results/measurement/blowerdoor_*.csv",
        "results/measurement/blowerdoor_summary.csv, results/measurement/blowerdoor_points.csv",
        cmd=_scripts(str(REPO / "scripts" / "reduce_blowerdoor.py")),
        cwd=REPO / "scripts", requires=[P.PREP_ROOT],
        note="feeds the committed airtightness figure",
    ),
    Target(
        "reduce_fouling", "data",
        "Reduce optics-fouling residuals + figure curves -> results/measurement/fouling/",
        "results/measurement/fouling_residuals.csv, results/measurement/fouling/fig_*.csv",
        cmd=_scripts(str(REPO / "scripts" / "explore_fouling.py")),
        cwd=REPO / "scripts", requires=[TIMESERIES], committed=True,
        note="reads data/reprocessed or the committed time series; feeds the committed "
             "fouling figure",
    ),
    Target(
        "reduce_ambient", "data",
        "Reduce experiment metadata -> results/measurement/ambient.csv, experiments_overview.csv",
        "results/measurement/ambient.csv, results/measurement/experiments_overview.csv",
        cmd=_scripts(str(REPO / "scripts" / "reduce_ambient.py")),
        cwd=REPO / "scripts", requires=[TIMESERIES], committed=True,
        note="reads the archive's metadata or the committed runs.csv; feeds the committed "
             "ambient + experiments-overview tables",
    ),
    Target(
        "reduce_smoke_alarm", "data",
        "Reduce smoke-alarm activation table -> results/measurement/smoke_alarm_table.csv",
        "results/measurement/smoke_alarm_table.csv",
        cmd=_scripts(str(REPO / "scripts" / "analyze_smoke_alarms.py")),
        cwd=REPO / "scripts", requires=[TIMESERIES], committed=True,
        note="reads the archive or the committed time series; feeds the committed "
             "smoke-alarm table",
    ),
    Target(
        "reduce_repeatability", "data",
        "Reduce run-to-run repeatability -> results/measurement/repeatability.csv",
        "results/measurement/repeatability.csv",
        cmd=_scripts(str(REPO / "scripts" / "repeatability.py")),
        cwd=REPO / "scripts", requires=[P.MEAS_ROOT, P.HRR_ROOT],
        note="feeds the repeatability numbers",
    ),
    Target(
        "reduce_lem_housing", "data",
        "LEM housing-temperature rise during the fires -> results/measurement/lem_housing.csv",
        "results/measurement/lem_housing.csv",
        cmd=_scripts(str(REPO / "scripts" / "reduce_lem_housing.py")),
        cwd=REPO / "scripts", requires=[P.MEAS_ROOT],
        note="the three adjacent-room LEM housing channels; bounds the thermal drift",
    ),
    Target(
        "reduce_fouling_at_peak", "data",
        "Optics fouling at the validation peak -> results/measurement/fouling_at_peak.csv",
        "results/measurement/fouling_at_peak.csv",
        cmd=_scripts(str(REPO / "scripts" / "reduce_fouling_at_peak.py")),
        cwd=REPO / "scripts",
        requires=[TIMESERIES, P.RESULTS_DIR / "measurement" / "fouling_residuals.csv"],
        committed=True,
        note="scales the measured end-of-run residual by the soot-exposure fraction "
             "reached at the peak (after reduce_fouling; reads data/reprocessed or the "
             "committed time series)",
    ),

    # ---------------- figures stage: committed-data subset (no external archive) ----------------
    Target(
        "geometry", "figures",
        "Apartment exploded isometric with instrumentation",
        "plots/measurement/apartment_isometric_expfds.pdf",
        cmd=_scripts(str(REPO / "scripts" / "plot_apartment_geometry.py")),
        cwd=REPO / "scripts", committed=True,
    ),
    Target(
        "pan_drawing", "figures",
        "Dimensioned drawing of the two fire pans on the platform scale, FDS overlay (Fig. S3)",
        "plots/measurement/pan_drawing.pdf",
        cmd=_scripts(str(REPO / "scripts" / "plot_pan_drawing.py")),
        cwd=REPO / "scripts", committed=True,
        note="constants only (as-built survey + FDS deck geometry), no external data",
    ),
    Target(
        "validation_devices", "figures",
        "PMMA device validation (parity, transmission, SICK wavelength) + device table",
        "device_validation/{pmma_transmission,parity_validation,sick_wavelength_fit}.pdf, "
        "tables/device_validation_table.tex",
        cmd=_scripts(str(REPO / "device_validation" / "validate_devices.py")),
        cwd=REPO / "device_validation", committed=True,
    ),
    Target(
        "model_tables", "figures",
        "FDS model tables from the production decks (Tables S1, S8-S10)",
        "tables/instrument_positions.tex, tables/model_meshes.tex, "
        "tables/model_surfaces.tex, tables/model_materials.tex",
        cmd=_scripts(str(REPO / "scripts" / "gen_model_tables.py")),
        cwd=REPO / "scripts", committed=True,
        requires=[P.FDS_DECK_DIR / "hep_160_075_ysmatched.fds"],
        note="parses fds_decks/*_ysmatched.fds and cross-checks the three series",
    ),
    Target(
        "heptane_literature", "figures",
        "n-Heptane soot-yield literature pool + Table S3",
        "results/literature/heptane_meta.csv, results/literature/heptane_meta_arms.csv, "
        "tables/heptane_literature.tex",
        cmd=_scripts(str(REPO / "scripts" / "heptane_literature.py")),
        cwd=REPO / "scripts", committed=True,
        note="DerSimonian-Laird pool of the ten literature arms tabulated in the script",
    ),
    Target(
        "widmann_exponent", "figures",
        "Differential Widmann-correlation exponent test -> results/measurement/widmann_exponent.csv",
        "results/measurement/widmann_exponent.csv",
        cmd=_scripts(str(REPO / "scripts" / "widmann_exponent.py")),
        cwd=REPO / "scripts", committed=True,
        requires=[P.RESULTS_DIR / "validation" / "matrices" / "ext_sick.csv"],
        note="LEM/SICK exponent bounds for the wavelength-normalisation section",
    ),
    Target(
        "tornado", "figures",
        "FDS single-parameter sensitivity tornado (Fig. 7)",
        "plots/simulation/fds_sensitivity_tornado.pdf",
        cmd=_scripts(str(REPO / "scripts" / "plot_fds_sensitivity_tornado.py")),
        cwd=REPO / "scripts", committed=True,
        requires=[P.RESULTS_DIR / "simulation" / "fds_sensitivity.csv",
                  P.RESULTS_DIR / "simulation" / "fds_seed_noise.csv"],
        note="from results/simulation/fds_sensitivity.csv and fds_seed_noise.csv "
             "(data targets fds_sensitivity, seed_noise)",
    ),
    Target(
        "blowerdoor_leakage", "figures",
        "Blower-door envelope-leakage figure (Fig. S4)",
        "plots/measurement/blowerdoor_leakage.pdf",
        cmd=_scripts(str(REPO / "scripts" / "plot_blowerdoor_leakage.py")),
        cwd=REPO / "scripts", committed=True,
        requires=[P.RESULTS_DIR / "measurement" / "blowerdoor_summary.csv"],
        note="from results/measurement/blowerdoor_summary.csv (data target reduce_blowerdoor)",
    ),
    Target(
        "fouling", "figures",
        "Optics-fouling figure (Fig. S7)",
        "plots/measurement/optics_fouling.pdf",
        cmd=_scripts(str(REPO / "scripts" / "plot_fouling.py")),
        cwd=REPO / "scripts", committed=True,
        requires=[P.RESULTS_DIR / "measurement" / "fouling" / "fig_curves.csv"],
        note="plots from committed results/measurement/fouling/fig_*.csv (reduce_fouling); byte-identical",
    ),
    Target(
        "fds_scatter", "figures",
        "FDS validation-guide scatter + pooled bias/scatter statistics (Fig. 5)",
        "plots/validation/fds_validation_scatter.pdf, results/validation/fds_metrics/guide_pooled.csv",
        cmd=_scripts(str(REPO / "scripts" / "fds_validation_scatter.py")),
        cwd=REPO / "scripts", committed=True,
        requires=[P.FDS_METRICS_DIR / "_Simulation_Comparison_hep_160_075_ysmatched"
                  / "metrics_report.csv"],
        note="reads the committed per-series FDS metrics",
    ),
    Target(
        "matrices", "figures",
        "Extinction and temperature matrices (Figs. 4, 6, S8-S10)",
        "plots/measurement/extinction_matrix_3x3.pdf, plots/validation/extinction_matrix_3x3_fds.pdf, "
        "plots/validation/temperature_matrix_3x3_fds.pdf, plots/validation/temperature_heatmap_F1.pdf, "
        "plots/validation/temperature_heatmap_F2.pdf",
        cmd=_scripts(str(REPO / "scripts" / "plot_extinction_matrices.py")),
        cwd=REPO / "scripts", committed=True,
        requires=[P.RESULTS_DIR / "validation" / "matrices" / "ext_lem.csv"],
        note="plots from committed results/validation/matrices/*.csv; byte-identical",
    ),
    Target(
        "hrr", "figures",
        "HRR / normalised-mass ensemble summary (Fig. 3)",
        "plots/measurement/hrr_summary.pdf",
        cmd=_scripts(str(REPO / "scripts" / "plot_hrr_summary.py")),
        cwd=REPO / "scripts", committed=True,
        requires=[P.RESULTS_DIR / "measurement" / "hrr" / "hrr_summary.csv"],
        note="plots from the committed reduced CSV (reduce_hrr data target); byte-identical",
    ),
    Target(
        "flow_field", "figures",
        "Extinction-field + velocity flow/transport sections (Figs. S11-S13)",
        "plots/simulation/extinction_flow_field_075.pdf, plots/simulation/extinction_flow_field_150.pdf, "
        "plots/simulation/extinction_flow_field_300.pdf",
        cmd=_scripts(str(REPO / "scripts" / "plot_extinction_flow_field.py")),
        cwd=REPO / "scripts", committed=True,
        requires=[P.RESULTS_DIR / "simulation" / "flow_field" / "ef_075_t100.npz"],
        note="renders from the committed reduced arrays in results/simulation/flow_field/*.npz; "
             "delete them to force re-extraction from the FDS output tree",
    ),
    Target(
        "data_tables", "figures",
        "Data tables (Tables 1, 2, S4, S7, S12, S13) from the committed reduced CSVs",
        "tables/experiments_overview.tex, tables/ambient.tex, tables/rst_apartment_runs.tex, "
        "tables/smoke_alarm.tex, tables/grid_convergence.tex, tables/fds_sensitivity_results.tex",
        cmd=_scripts(str(REPO / "scripts" / "gen_data_tables.py")),
        cwd=REPO / "scripts", committed=True,
        requires=[P.RESULTS_DIR / "simulation" / "fds_sensitivity.csv"],
        note="byte-identical to the committed fragments",
    ),
    Target(
        "numbers_check", "figures",
        "Recompute the paper's numeric macros and compare with numbers.tex",
        "results/numbers_check.csv",
        cmd=_scripts(str(REPO / "scripts" / "check_numbers.py")),
        cwd=REPO / "scripts", committed=True,
        requires=[P.REPO_ROOT / "numbers.tex"],
        note="every macro recomputed from results/ and tables/ or listed as a documented "
             "literal; fails on any mismatch (run after the table targets)",
    ),
]

BY_KEY = {t.key: t for t in TARGETS}


def _status(t: Target) -> str:
    if t.cmd is None:
        return "NEEDS_CONVERSION"
    missing = [str(r) for r in t.requires if not P.available(Path(r))]
    if missing:
        return "SKIP (missing input)"
    return "committed" if t.committed else "ready (external data)"


def cmd_list() -> None:
    print(f"{'KEY':<24} {'STAGE':<8} {'STATUS':<24} ARTEFACT")
    print("-" * 100)
    for t in TARGETS:
        print(f"{t.key:<24} {t.stage:<8} {_status(t):<24} {t.artefact}")
    print("\nLegend: committed = no external archive needed; "
          "ready (external data) = runnable once the raw archives are supplied;\n"
          "        SKIP = a needed input is not present.")


def run_target(t: Target, dry: bool) -> str:
    label = f"[{t.stage}:{t.key}]"
    if t.cmd is None:
        print(f"{label} SKIP - {t.note or 'not runnable yet'}")
        return "skip"
    missing = [str(r) for r in t.requires if not P.available(Path(r))]
    if missing:
        print(f"{label} SKIP - missing input(s): {', '.join(missing)}")
        return "skip"
    argv = [sys.executable, *t.cmd]
    print(f"{label} {t.title}")
    print(f"        -> {t.artefact}")
    if t.note:
        print(f"        note: {t.note}")
    if dry:
        print(f"        (dry-run) {' '.join(argv)}  [cwd={t.cwd}]")
        return "dry"
    t0 = time.time()
    # Force UTF-8 in children: several scripts print non-ASCII (raw-data labels,
    # degree/sigma) which crashes on a cp1252 console under subprocess.
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    res = subprocess.run(argv, cwd=str(t.cwd), env=env)
    dt = time.time() - t0
    ok = res.returncode == 0
    print(f"        {'OK' if ok else 'FAILED'} ({dt:.1f}s)")
    return "ok" if ok else "fail"


def select(stage: str | None, only: list[str], committed: bool) -> list[Target]:
    if only:
        unknown = [k for k in only if k not in BY_KEY]
        if unknown:
            sys.exit(f"unknown target(s): {', '.join(unknown)}")
        return [BY_KEY[k] for k in only]
    order = ["data", "figures"] if stage == "all" else [stage]
    sel = [t for t in TARGETS if t.stage in order]
    if committed:
        sel = [t for t in sel if t.committed]
    return sel


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", nargs="?", default="list",
                    choices=["list", "data", "figures", "all"])
    ap.add_argument("--only", nargs="+", default=[], metavar="KEY",
                    help="run only the named target(s), in the given order")
    ap.add_argument("--committed", action="store_true",
                    help="restrict to targets reproducible from committed data")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.stage == "list" and not args.only:
        cmd_list()
        return

    sel = select(args.stage, args.only, args.committed)
    results: dict[str, str] = {}
    for t in sel:
        results[t.key] = run_target(t, args.dry_run)

    counts: dict[str, int] = {}
    for v in results.values():
        counts[v] = counts.get(v, 0) + 1
    print("\n=== summary ===")
    print("  " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    if counts.get("fail"):
        sys.exit(1)


if __name__ == "__main__":
    main()
