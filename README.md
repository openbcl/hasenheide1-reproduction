# Smoke light extinction in a multi-room compartment fire — reproduction package

Code, condensed data, FDS input decks, and reference outputs to reproduce the
figures and numbers of the paper *"Measuring and Modelling Smoke Light Extinction
in Well-Ventilated, Multi-Room Compartment Fires: Co-located Transmissometry and
A-priori FDS Validation"* (Osburg et al.).

It contains everything needed to regenerate the paper's figures and computational
tables from committed intermediate data, and the reduced data behind its reported
numbers (`numbers.tex`; `scripts/check_numbers.py` recomputes every macro or lists
it as one of 13 documented literals) — but not the manuscript prose.

## What's in here

`results/` and `plots/` are grouped by provenance, mirroring the paper's logic —
**`measurement/`** (experimental reduced data / figures), **`simulation/`** (FDS
reduced data / figures), **`validation/`** (measured-vs-modelled comparison), and
**`results/literature/`** (the pooled literature soot yield of *n*-heptane).

| Path | Content |
|------|---------|
| `scripts/` | analysis, reduction, and plotting code |
| `device_validation/` | LEM/SICK instrument validation against the PMMA filters (self-contained: data + code + figures) |
| `results/{measurement,simulation,validation,literature}/**/*.csv` | condensed intermediate data (the reduced CSVs the plots and tables consume; the flow-field figures read the arrays `results/simulation/flow_field/*.npz`) |
| `results/measurement/timeseries/` | per-test measured time series of the 14 experiments (1 Hz, every LEM, SICK, gas and ceiling thermocouple, scale and smoke-alarm channel, with a data dictionary and `SHA256SUMS`; see *Time series* below) |
| `results/simulation/timeseries/` | the FDS baseline runs of the three series at the instrument positions, with a dictionary that maps each device to its measured column, and `SHA256SUMS` (see *Time series* below) |
| `fds_decks/` | FDS input decks (`.fds`, line-of-sight beams) + notes |
| `plots/{measurement,simulation,validation}/**/*.pdf` | reference figure outputs |
| `numbers.tex`, `tables/*.tex` | the paper's numbers and tables as committed LaTeX fragments (see *Provenance* below) |
| `run_all.py`, `Makefile` | the reproduction orchestrator |

**Not included:** the manuscript sources, the bibliography, and the raw
measurement / FDS-output trees (hundreds of gigabytes). Only the *reduced* data,
the per-test measured time series and the FDS baseline time series at the instrument
positions are redistributed here — which is what makes the figure stage, and part of
the data stage, runnable without those archives.

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
python run_all.py data                 # the data targets that run without the archives
                                       # (the others are skipped; see Two-stage design)
python scripts/timeseries.py           # check the time series against their SHA256SUMS
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
committed data (the `figures --committed` subset and the data targets listed under
*Two-stage design*) or, for the rest of the `data` stage, from your own copies of the
raw archives.

### Two-stage design

The pipeline has two stages: a `data` stage that reduces raw measurement / FDS
output into the committed CSVs, and a `figures` stage that renders everything from
those CSVs. **The `figures` stage runs from this repository**, and so do six
targets of the `data` stage: `reduce_hrr` (from the committed mass traces) and
`reduce_matrices` (measured and FDS curves), `reduce_fouling`,
`reduce_fouling_at_peak`, `reduce_smoke_alarm` and `reduce_ambient`, which without the
archives read the committed measured and FDS time series (see *Time series*) and
reproduce the committed CSVs exactly. The other `data` targets need the raw trees
(hundreds of gigabytes), which are not redistributed; `run_all.py` skips them when
their inputs are missing. They are included for transparency; to run them you would
point them at your own copies of the raw data via these environment variables:

| Variable | Purpose |
|----------|---------|
| `HASENHEIDE_MEAS_ROOT` | measurement tree (raw and processed run records, event logs, experiment metadata) |
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

### Time series

`results/measurement/timeseries/` holds the measured records of all 14 heptane
experiments, so single tests, the scatter within a series and the evolution in time
can be compared directly, not only the series means and peaks the paper reports.
They are the re-consolidated records written by `scripts/reprocess_unclipped.py`
(the original consolidation of the archive, extended from 1800 s to at most 3600 s
after t = 0), exported by `scripts/export_timeseries.py` with ASCII column names and
otherwise unchanged values. In the common time range they are identical to the
original consolidation, so the reductions give the same results from either:

| File | Content |
|------|---------|
| `Hep_<pan>_S<n>_R<m>.csv` | one test: 1 Hz, `t_s` = time from the ignition reference `t0_local` (the full minute of ignition; the logged ignition follows 0.5–2.8 s later, see `events.csv`), from −60 s to the end of the record including the ventilation phase (Hep_160_S1_R3 is cut at 3600 s), local time, fuel mass on the platform scale (pan tared), the ceiling thermocouple above the fire, thermocouple trees 1 (F1) and 2 (F2), LEM and SICK transmission and extinction at every height installed in that test, and the three smoke alarms |
| `runs.csv` | one row per test: series, instrument setup S1–S4, pan, fuel mass, date, t = 0 reference time, burning duration, ventilation start, door state, ambient temperature / humidity / pressure, record extent |
| `events.csv` | logged events, in s on the same time axis: `ignition`, `flame_out`, `ventilation_start`, `window_F3_open`, `window_F1_open`, `fan_on`, `instrument_cleaning`, `ceiling_tc_recording_resumed`, `test_end` (as logged; not every log has every event) |
| `channels.csv` | data dictionary, one row per test and column: quantity, unit, instrument, room, height, wavelength, path length, the processing applied, the source column of the consolidation, and its status (`ok`, `partial` with the valid range, or `excluded`) |

Column names encode instrument, room, height and wavelength, e.g.
`k_LEM1_F2_z1.5_638nm_per_m` (LEM 1 in room F2 at 1.5 m) or
`k_SICK_F2_z2.3_880nm_per_m` and its Widmann-scaled counterpart
`k_SICK_F2_z2.3_638nm_per_m` (factor (638/880)^−1.0088 = 1.383). The LEMs near the
ceiling (2.3 m) of F1 (LEM 4), F2 (LEM 3) and F3 (LEM 2) were in place in every
test; the second LEM in F2 (LEM 1) was moved between the setups (1.5 m in S1/S2,
1.9 m in S3, 2.1 m in S4), and the SICK beam sat at 2.3 m in F2 (S1, S3), F1 (S2) or
F3 (S4). Extinction follows from the logged transmission as `k = −ln(τ)/L`
(L = 0.81 m for the LEMs, 1.6 m for the double-pass SICK); a transmission below
0.001 %, including the negative readings when an instrument is switched off, is held
at `τ = 10⁻⁵`, i.e. `k = 14.21 1/m` for a LEM. That ceiling appears in the last
seconds of every record and in isolated samples late in Hep_160_S1_R3 (2444–2687 s)
and Hep_220_S1_R2 (2013–2369 s; an instrument cleaning is logged at 1833 s); mask it
before plotting full records, as the fouling reduction does. Thermocouple tree 2 is
logged at 2.0–2.5 m with the other channels; its lower heights (0.6–1.8 m) come
from a separate logger (0.1 °C resolution), are missing in Hep_160_S1_R3 and
Hep_160_S2_R1, and end before the record in Hep_160_S4_R2 and Hep_220_S1_R3
(`partial`). The values are **not**
zeroed: the matrix and fouling reductions subtract each record's value at t = 0
themselves (`scripts/measurement_io.py`). Channels without a valid measurement in a
test (SICK in Hep_160_S1_R3 and in all four Hep_220_S1 tests, LEM 4 in Hep_220_S1_R1
and R4) are set to NaN by the consolidation, kept as NaN columns and marked
`excluded` in `channels.csv`. Values are written as the shortest round-trip
representation of the doubles the reductions use; read them with
`float_precision="round_trip"` (pandas) to recover them bit for bit.

The model counterparts are in `results/simulation/timeseries/`: for the baseline run
of each series (`hep_160_075_ysmatched`, `hep_160_150_ysmatched`,
`hep_220_300_ysmatched`; decks in `fds_decks/`) the devices at the instrument
positions — thermocouples at the tree heights in F1–F3 and below the ceiling of F1
and F3, point extinction, the LEM and SICK line-of-sight beams (`PATH OBSCURATION` in
%, plus the path-mean extinction `<beam>_k` = −ln(1 − OBS/100)/L, the conversion
behind the paper's FDS curves) and the smoke-alarm devices — as written by FDS
(`<case>_devc.csv`, ≈1 s steps, 900 s or 1200 s), and the HRR file (`<case>_hrr.csv`).
`fds_channels.csv` gives each column's quantity, unit, room, height, the device
position in the deck, and in `measured` the column of the measured time series it
corresponds to. It is blank for the F3 thermocouples, the F3 ceiling thermocouple
and the point-extinction devices, which have no measured counterpart (no gas
temperature was measured in F3), and for the raw `PATH OBSCURATION` columns, whose
`<beam>_k` columns carry the mapping. FDS uses one mass-specific extinction
coefficient, so its `k` is compared with the 638 nm measured columns. Vertical
profiles and other device lines of the FDS output are not included.

Both directories carry a `SHA256SUMS` file (`sha256sum -c SHA256SUMS` inside each
directory, or `python scripts/timeseries.py`, which checks both and also reports
files that are not listed). `scripts/timeseries.py` also loads
a test and its model counterpart in one call:

```python
from timeseries import load_test, load_fds      # run from scripts/
t = load_test("Hep_160_S2_R1")    # t.data, t.channels, t.events, t.run (its runs.csv row)
m = load_fds(t.run["series"])     # m.data, m.channels, m.hrr
```

`scripts/example_timeseries.py [RUN]` plots one test against the FDS baseline of its
series: the LEM extinction near the ceiling of each room and at every height measured
in F2, each with the FDS beam at the same position (an orientation plot, not a paper
figure; written to `plots/exploratory/`).

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
paper's rounding: 168 from the reduced data and the generated tables (five of these
with the documented calorimeter-series factor below), 12 from constants stated in the
paper or below (net volume, the heat-of-combustion and fire-area scaling factors, the
experimental uncertainty `σ_E`), 30 from the two tables of documented inputs
(Table S2, and Table S4 with the apartment-batch calorimeter runs; three of these also
use the certified methylcyclohexane share or Tewarson's predicted *n*-heptane yield),
and it lists the remaining 13 as documented literals (the pure-*n*-heptane reference,
the charge check, the calorimeter light source, the supplier certificate, Tewarson's
predicted *n*-heptane yield and the calorimeter-series factor; see below). It fails on
any difference.

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
  **composition of the C7-UVCB fuel** (SM S3, Table S2, `\valCoreFuelSeven*`; GC-FID
  as percentages of the total peak area, all constituents taken as C7 hydrocarbons, a
  24 % share of C7 isomers whose class the chromatogram does not assign) come from the
  wider RST campaign and its fuel analysis, whose records are not redistributed here.
  The reference and the charge check are documented literals in `numbers.tex`; the
  composition is given in `tables/core_fuel_composition.tex`, from which
  `scripts/check_numbers.py` recomputes the `\valCoreFuelSeven*` shares, the naphthenic
  fraction and the range of the mean formula (C7H14.8–C7H15.3, the unassigned share
  taken as naphthene or paraffin).
- The **tabulated comparison yields** (§4.2, SM S3, Table S2, `\valSfpeYs*`) are the
  smoke yields of SFPE Handbook, 6th ed. (2026), Table C.13 (identical to Table A.40 of
  the 5th ed.) for the fuel's constituents, mass-weighted over the GC composition:
  0.045–0.054 g/g, the range spanning the unassigned share taken as paraffin
  (Methylhexane, 0.037) or naphthene (Methylcyclopentane, 0.070), with the bracket for
  the unlisted cis-1,3-dimethylcyclopentane (dimethylcyclohexane 0.066 or
  methylcyclopentane 0.070) moving with it. The branched-paraffin row (0.038) is
  weighted over the Methylhexane and Dimethylpentane entries by compound; that split is
  not reproduced here, the row enters as printed. The printed *n*-heptane entry (0.042)
  exceeds both the table's own smoke-point correlation and Tewarson's original
  prediction (0.037); with 0.037 the mean is 0.044–0.052
  (`\valSfpeYsCoreFuelSevenCorr*`).
- The **heat-release scale factor between the two calorimeter series**
  (`k = 1.081 ± 0.030`, §2.4, SM S4, `\valCoreHeatScale*`; matched *n*-heptane burns of
  both series, with a TSP difference of 0.6 %) comes from the second series' records,
  which are not redistributed here, and is a documented literal. From it
  `scripts/check_numbers.py` derives the two-sided systematic on the prescribed `ΔH_ch`
  (−3 % from the oxygen-consumption constant alone, +5 % with that correction times `k`;
  `\valCoreHeatSys*`) and the heat-of-combustion case of Table S13 scaled linearly to
  the upper end (`\valSensDhcUp*`).
- The ***n*-heptane literature pool** (§3.2, Table S3, `\valHeptaneMeta*`) is
  recomputed by `scripts/heptane_literature.py` from the ten literature values it
  tabulates (DerSimonian–Laird random effects; the tabulated ± read as 95 %
  half-widths): 0.0156 g/g, 95 % CI 0.0144–0.0169. The NIST TN 2235 rows are records
  of the NIST Fire Calorimetry Database for burns that TN 2235 documents (the report
  itself gives no soot yield).
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

- **v0.3.0** (unreleased) — follows the paper's next revision. NIST TN 2133 in the
  *n*-heptane literature pool corrected to 0.0162 ± 0.0036 g/g (Fig. 7, read from the
  vector graphics; v0.2.0 carried 0.0140 ± 0.0040, a misreading), which moves the
  pooled yield from 0.0155 to 0.0156 g/g (95 % CI 0.0144–0.0169), and the TN 2235 rows
  labelled as NIST Fire Calorimetry Database records (Table S3); Table S2 recast as the
  C7 composition with a share of unassigned class, so the mass-weighted SFPE yield
  becomes a range, 0.045–0.054 g/g (`\valCoreFuelSeven*`, `\valSfpeYsCoreFuelSeven*`
  replace the earlier `\valCoreFuel*` shares and `\valSfpeYsCoreFuel*`); the
  heat-release scale factor between the two calorimeter series as a documented literal,
  with the two-sided `ΔH_ch` systematic and the scaled heat-of-combustion case derived
  from it (`\valCoreHeat*`, `\valSensDhcUp*`); the fuel-substitution case read at the
  pooled mean itself (`\valSensFuelAtMuPct`). New: the per-test measured time series
  of the 14 experiments (`results/measurement/timeseries/`, data target
  `export_timeseries`) and the FDS baseline runs at the instrument positions
  (`results/simulation/timeseries/`, data target `export_fds_timeseries`), with
  checksums, a loader (`scripts/timeseries.py`) and an example
  (`scripts/example_timeseries.py`); the measurement reductions `reduce_matrices`,
  `reduce_fouling`, `reduce_fouling_at_peak`, `reduce_smoke_alarm` and
  `reduce_ambient` now run from them without the archive and reproduce the
  committed CSVs exactly, `reduce_matrices` including its FDS overlay files.
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
