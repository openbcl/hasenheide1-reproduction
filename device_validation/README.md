# Light-extinction device validation

Laboratory validation of the optical extinction instruments (LEM, SICK) against
the **same six spectrally measured PMMA reference filters**. The common quantity
is the spectroscopic reference transmission `T_ref(lambda)` at each device's
operating wavelength; every device's reading is compared to it. Supports the
device-validation section of the paper's Supplementary Material.

Reference: Schelhorn, *Analyse und Qualifizierung eines photometrischen
Low-Cost-Messsystems zur Bestimmung der Lichtextinktion bei Brandversuchen*,
Zenodo, 2026 — https://zenodo.org/records/19348863 (bib key `schelhorn_lem_2026`).

## Contents

- `pmma_spectra/` — the spectroscopic PMMA filter transmission spectra (`*.ASC`,
  merged visible+NIR, all six filters); the single reference used by every device.
- `lem/data_LEMV2_Reproduzierbarkeit.csv` — the 16 repeated LEM readings per filter
  (columns = filter IDs `0A000 … 8A570`).
- `sick/PMMA_Kalibrierung.csv` — the SICK readings per filter (5 repeats each);
  the SICK is a double-pass device, `m_i ~ a(λ)·T_i(λ)²`.
- `validate_devices.py` — the analysis: reads the shared spectra and the two
  device CSVs, derives `T_ref` at each device wavelength, fits the SICK effective
  wavelength (minimising the filter RMSE), and produces
  - `parity_validation.pdf` — measured vs. reference transmission, 1:1 line, both
    devices (paper plot style, `scripts/plot_style.py`);
  - `pmma_transmission.pdf` — the filter spectra `T(λ)` with the device operating
    wavelengths marked (LEM 638 nm, SICK 880 nm);
  - `sick_wavelength_fit.pdf` — the SICK filter-RMSE vs. wavelength, with the
    minimum at the effective 880 nm (scale `a ≈ 1.01`); supporting evidence for the
    prose in SM §S6.4, not a numbered paper figure;
  - `../tables/device_validation_table.tex` — slope / max|Δ| / reproducibility per
    device (paper Table S5).

Run:  `python device_validation/validate_devices.py`  (committed inputs only; also the
`validation_devices` target of `run_all.py`).

### Current results

| Device | λ [nm] | slope | max\|Δ\| | repro. SD |
|--------|-------:|------:|--------:|---------:|
| LEM    | 638    | 1.002 | 0.35 %  | 0.20 %   |
| SICK   | 880    | 1.006 | 1.69 %  | 0.04 %   |

(Reproducibility SD = mean per-filter SD over repeats: 16 for LEM, 5 for SICK.)

## Notes

Regenerable `*.png` are git-ignored; the reference `*.pdf` are kept. The
validation data is small and bundled, so this step needs no external data.
