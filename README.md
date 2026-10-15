# Smoke light extinction in a multi-room compartment fire — reproduction package

Code, condensed data, FDS input decks, and reference outputs to reproduce the
figures and numbers of the paper *"Measuring and Modelling Smoke Light Extinction
in Well-Ventilated, Multi-Room Compartment Fires: Co-located Transmissometry and
A-priori FDS Validation"* (Osburg et al.).

It contains everything needed to regenerate the paper's figures and computational
tables from committed intermediate data, and the reduced data behind its reported
numbers (`numbers.tex`; `scripts/check_numbers.py` recomputes every macro or lists
it as one of 11 documented literals) — but not the manuscript prose.

## What's in here

`results/` and `plots/` are grouped by provenance, mirroring the paper's logic —
**`measurement/`** (experimental reduced data / figures), **`simulation/`** (FDS
reduced data / figures), **`validation/`** (measured-vs-modelled comparison), and
**`results/literature/`** (the pooled literature soot yield of *n*-heptane).

| Path | Content |
|------|---------|
| `scripts/` | analysis, reduction, and plotting code |
| `device_validation/` | LEM/SICK instrument validation against the PMMA filters (self-contained: data + code + figures) |
| `results/{measurement,simulation,validation,literature}/**/*.csv` | condensed intermediate data (the reduced CSVs the plots and tables consume) |
| `fds_decks/` | FDS input decks (`.fds`, line-of-sight beams) + notes |
| `plots/{measurement,simulation,validation}/**/*.pdf` | reference figure outputs |
| `numbers.tex`, `tables/*.tex` | the paper's numbers and tables as committed LaTeX fragments (see *Provenance* below) |
| `run_all.py`, `Makefile` | the reproduction orchestrator |

**Not included:** the manuscript sources, the bibliography, and the raw
measurement / FDS-output trees (hundreds of gigabytes). Only the *reduced* data is
redistributed here — which is what makes the figure stage runnable without those
archives.

## Reproduce

**Prerequisites:** Python 3.12 (the dependency pins are version-specific) and a
LaTeX installation with `siunitx` plus `pdfcrop` — the figures render their text
through LaTeX (`text.usetex`), so the figure stage needs a working TeX toolchain.
`pdfcrop` (used for Figure 1) is a Perl script and needs a Perl interpreter on
`PATH`. Linux, macOS and TeX Live provide one; with MiKTeX on Windows, install e.g.
Strawberry Perl or add the `perl.exe` of Git for Windows (`<Git>\usr\bin`) to `PATH`.

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run_all.py list                 # every target and its status
python run_all.py figures --committed  # regenerate the no-archive-needed subset
```

`python run_all.py figures --committed` regenerates the paper figures from the
committed CSVs alone, together with the tables that describe the FDS model
(Tables S1 and S8–S10, parsed from the input decks in `fds_decks/`), the device
validation table (Table S5), the heptane literature table (Table S3) and the data
tables (Tables 1, 2, S4, S7, S12, S13, from the reduced CSVs). As its last step it
recomputes the paper's numeric macros and compares them with `numbers.tex`
(`scripts/check_numbers.py`; per-macro report in `results/numbers_check.csv`). Since
every table fragment and every figure is regenerated in place, a hand-edited file
shows up afterwards in `git status`. The
figure PDFs use a pinned `SOURCE_DATE_EPOCH`, so their content is deterministic; a
couple of figures may differ from the committed reference by a few bytes of PDF
metadata padding (a `pdfcrop` artefact), not in content.

A few of the paper's figures are not computational and are **not** redistributed
here — they appear in the manuscript only: the photographs of the experimental
setup (the pool-fire pan and the line-of-sight instruments in room F2) and the CAD
floor plan of the apartment. Everything computational regenerates either from the
committed CSVs (the `figures --committed` subset) or, for the `data` stage, from
your own copies of the raw archives.

### Two-stage design

The pipeline has two stages: a `data` stage that reduces raw measurement / FDS
output into the committed CSVs, and a `figures` stage that renders everything from
those CSVs. **Only the `figures` stage runs from this repository** — the raw trees
(hundreds of gigabytes) are not redistributed. The `data` stage is included for
transparency; to run it you would point it at your own copies of the raw data via
these environment variables:

| Variable | Purpose |
|----------|---------|
| `HASENHEIDE_MEAS_ROOT` | measurement tree (processed run CSVs, smoke alarms) |
| `HASENHEIDE_ANALYSIS_ROOT` | analysis tree (extinction/temperature matrices, parent of `HRR/`) |
| `HASENHEIDE_HRR_ROOT` | per-series HRR ensemble CSVs (defaults under the analysis tree) |
| `HASENHEIDE_PREP_ROOT` | preparation tree (blower-door reports) |
| `HASENHEIDE_FDS_ROOT` | FDS output tree (device CSVs, 3D slices) |

The FDS input decks under `fds_decks/` are the line-of-sight beam decks that produced
the published results; run them with FDS 6.11.1 to regenerate the output tree.
The `data` stage reads the FDS slice output with fdsreader 1.11.7 (pinned in
`requirements.txt`), patched at runtime for its ghost-cell handling of cell-centred
3D slices (`scripts/fdsreader_patch.py`). fdsreader 1.12.1 fixes that issue
natively; re-extracting with it, unpatched, reproduces the flow-field arrays and the
point-vs-path statistics exactly.

### Provenance of the reported values

`numbers.tex` and the `tables/*.tex` fragments carry the paper's numbers and tables,
with the reduced CSVs under `results/` and the FDS decks as the data behind them.
Twelve of the thirteen `tables/*.tex` are regenerated here:
`device_validation_table.tex` (Table S5) by `device_validation/validate_devices.py`;
`instrument_positions.tex`, `model_meshes.tex`, `model_surfaces.tex` and
`model_materials.tex` (Tables S1, S8–S10) by `scripts/gen_model_tables.py` from the
production decks; `heptane_literature.tex` (Table S3) by
`scripts/heptane_literature.py`; and `experiments_overview.tex`, `ambient.tex`,
`rst_apartment_runs.tex`, `smoke_alarm.tex`, `grid_convergence.tex` and
`fds_sensitivity_results.tex` (Tables 1, 2, S4, S7, S12, S13) by
`scripts/gen_data_tables.py` from the reduced CSVs. Only Table S2
(`core_fuel_composition.tex`) is a **static reference copy**: its GC composition and
SFPE yields are documented inputs (see below).

`scripts/check_numbers.py` recomputes the numeric macros of `numbers.tex` with the
paper's rounding: 162 from the reduced data and the generated tables, 11 from
constants stated in the paper or below (net volume, the heat-of-combustion and
fire-area scaling factors, the experimental uncertainty `σ_E`), 28 from the two tables
of documented inputs (Table S2, and Table S4 with the apartment-batch calorimeter
runs; four of these also use the certified methylcyclohexane share or Tewarson's
predicted *n*-heptane yield), and it lists the remaining 11 as documented literals (the
pure-*n*-heptane reference, the charge check, the calorimeter light source, the
supplier certificate, the unreported GC share and Tewarson's predicted *n*-heptane
yield; see below). It fails on any difference.

The paper's fuel-side inputs were measured in the RST furniture-calorimeter
campaign and enter this paper as parameters:

- The **apartment-batch RST runs** behind Table S4 — the six per-run TSP / `Y_s` /
  `ΔH_ch` values and their pooled means (`Y_s = 0.0354 ± 0.0022 g/g`;
  `ΔH_ch = 41.345 ± 1.00 MJ/kg` over the four runs without the known heat-channel
  offset, the excluded 220 mm/300 g runs) — are shipped as `results/measurement/rst_apartment_runs.csv`,
  and `reduce_hrr_from_mass.py` re-derives `ΔH_ch` from it. The
  **configuration-matched yields** encoded in the FDS decks (0.0328 / 0.0376 / 0.0358,
  Table 4, note a) are the per-configuration means of the same file.
- The **pure-*n*-heptane reference** (0.0162, *n* = 2,
  SM S4), the **12-run charge check** (SM S4, `\valRstCharge*`) and the
  **composition of the C7-UVCB fuel** (SM S3, Table S2, `\valCoreFuel*`; GC-FID,
  semi-quantitative) come from the wider RST campaign and its fuel analysis, whose
  records are not redistributed here. The reference and the charge check are documented
  literals in `numbers.tex`; the composition is given in
  `tables/core_fuel_composition.tex`, from which `scripts/check_numbers.py` recomputes
  the `\valCoreFuel*` shares and the mean formula.
- The **tabulated comparison yields** (§4.2, SM S3, Table S2, `\valSfpeYs*`) are the
  smoke yields of SFPE Handbook, 6th ed. (2026), Table C.13 (identical to Table A.40 of
  the 5th ed.) for the fuel's constituents,
  mass-weighted over the GC composition: 0.048–0.049 g/g, depending on the stand-in for
  cis-1,3-dimethylcyclopentane (not listed; dimethylcyclohexane 0.066 or
  methylcyclopentane 0.070). The printed *n*-heptane entry (0.042) exceeds both the
  table's own smoke-point correlation and Tewarson's original prediction (0.037); with
  0.037 the mean is 0.047 (`\valSfpeYsCoreFuelCorr`).
- The ***n*-heptane literature pool** (§3.2, Table S3, `\valHeptaneMeta*`) is
  recomputed by `scripts/heptane_literature.py` from the ten literature values it
  tabulates (DerSimonian–Laird random effects; the tabulated ± read as 95 %
  half-widths).
- The **size evolution of the binned soot** (Table S11 note d, SM S13, `\valBinned*`) comes from
  `results/simulation/sootdep_binned_rh_bins.csv`, written by the `binned_soot` data target
  from the FDS output of `hep_160_075_sootdep_binned_rh`.
- The **run-to-run variability of the LES** (grey bands in Figure 7, Table S11 note e,
  SM S13, `\valSeed*`) comes from `results/simulation/fds_seed_noise.csv`, written by the
  `seed_noise` data target from the FDS output of the three seed realisations
  `hep_160_075_seed101/202/303` (the baseline with only `RND_SEED` changed): the largest
  peak deviation from the baseline per quantity, and the trace NRMSE.
- `results/measurement/crosscheck_lem_sick.csv` (SICK–LEM bias, §2.5) is a committed
  reduced output whose reducer is not shipped here.
  `results/validation/extinction_point_vs_path{,_summary}.csv` (path-vs-point
  statistics, SM S8) are regenerated by the `point_vs_path` data target from the FDS
  output tree.

A few presentation conventions and geometric parameters are carried as committed
literals rather than recomputed here, so a reproducer is not misled:

- Table 1's `h/D` is the freeboard-to-diameter ratio from the 100 mm pan depth and
  the per-charge fuel depth — a geometric parameter, not a reduced measurement.
- The per-metre obscuration figures of §1 (39–67 %/m) are `1 − exp(−k)` on the
  **displayed, 0.1-rounded** `k` (`0.5`→39 %, `1.1`→67 %); the raw `k` (0.46, 1.13)
  gives 37–68 %, so both are consistent once the rounding basis is known.
- The "≈13 %" within-series log-ratio scatter (§3.3) is the pooled residual
  standard deviation (`ddof = n − n_series`).
- The extinction measurement uncertainty `σ_E = 0.08` (SM S8 / Table S6) is a
  documented literal in `scripts/guide_stats.py`; the instrument and geometry terms
  of Table S6 are recomputed by `scripts/check_numbers.py` from Table S5 and the
  stated `u_L/L = 1.5 %`.
- Tables 3, 4 and S11 are descriptive / parameter tables with no `.tex` fragment;
  their values live in the FDS decks (`fds_decks/*.fds`) and `numbers.tex`.
- Air-tightness (SM S2, from `results/measurement/blowerdoor_summary.csv`):
  `n50 = q50 / V` with the net volumes 128 m³ (whole apartment, FDS mesh minus the
  wall/obstruction blocks), 44.4 / 37.4 / 37.9 m³ (rooms F1 / F2 / F3, same basis)
  and 130 m³ (reference flat, net floor-plan volume). The per-room leakage is a
  zonal decomposition of the pressurisation runs (F1 = test `F1`, F2 = `F1F2` − `F1`,
  F3 = `F3`); the exponent, the effective leakage area
  `A = (q50/3600) / sqrt(2·50 Pa / 1.194 kg m⁻³)` and the chimney leak
  (`F3` − `F3_chimney_sealed`) are taken from the whole-apartment / room
  pressurisation runs. The fire-induced zone pressures quoted there come from the
  FDS output tree, which is not reduced into this package.
- The optics-fouling exposure fraction at the validation peak (SM S8, Table S6 note b, 18 %) is the
  median over the run–sensor rows of `results/measurement/fouling_at_peak.csv`; the
  at-peak and end-of-run fouling values are the maxima.
- The pan drawing (Figure S3) is generated from constants in
  `scripts/plot_pan_drawing.py`: the as-built dimensions of the pans and the platform
  scale (survey and photographs, not shipped), the FDS obstructions of the decks, and
  the initial fuel depths from the charge mass and the certified density of the fuel
  batch (0.7179 kg/l at 15 °C, supplier's certificate of analysis), which reproduce the
  `h/D` ranges of Table 1.

## Versions

- **v0.2.0** (2026-10-15) — first public release; accompanies the revised manuscript.
  Changes against the unreleased v0.1.0 that matched the original submission
  (2026-08-24): heat-of-combustion sensitivity case
  (`fds_decks/hep_160_075_dhc_e127.fds`, Table S13); run-to-run variability of the LES
  from three random-seed realisations of the baseline
  (`fds_decks/hep_160_075_seed*.fds`, grey bands in Figure 7); soot-deposition cases recomputed
  with the baseline's humid background air, plus a matched no-deposition control
  (`fds_decks/*_rh.fds`); FDS model tables S1 and S8–S10
  generated from the decks; *n*-heptane literature pool and Table S3; fuel composition
  with tabulated SFPE yields (Table S2); dimensioned drawing of the fire pans on the
  platform scale with the FDS obstructions (Figure S3); Figure 1 and
  the point-vs-path check on the instrument coordinates of the FDS input files;
  revised figure styling (Figures 1, 5, 7, S4, S7–S10); Supplementary Material
  renumbered S1–S13.

## Citing

If you use this code or data, please cite both the paper and this software/data
record:

- Paper: *(DOI added on publication)*
- Software/data: Zenodo, [doi:10.5281/zenodo.23097800](https://doi.org/10.5281/zenodo.23097800)

A `CITATION.cff` accompanies the repository. See the paper's *Data Availability*
statement for the exact record that backs its figures.

## License

CC BY 4.0 (see `LICENSE`). Third-party Python dependencies retain their own
licenses; FDS is a NIST product in the public domain.
