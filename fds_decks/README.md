# FDS input decks

The line-of-sight beam decks that produced the paper's a-priori FDS validation
(run with **FDS 6.11.1**). Three production decks — one per fire series, at the
configuration-matched soot yield — plus single-parameter sensitivity variants,
each built on the `hep_160_075` base and isolating exactly one axis from it.

## Production baselines (`Y_s` configuration-matched)

| Deck | Fire series |
|------|-------------|
| `hep_160_075_ysmatched` | 160 mm pan, 75 g fuel (`Y_s = 0.0328`) |
| `hep_160_150_ysmatched` | 160 mm pan, 150 g |
| `hep_220_300_ysmatched` | 220 mm pan, 300 g |

## Single-parameter sensitivity decks (base: `hep_160_075`)

| Axis | Decks | Variation vs. base |
|------|-------|--------------------|
| Soot yield `Y_s` | `ys030`, `ys049` | 0.030 / 0.049 (base: matched 0.0328) |
| Fuel substitution | `ys015` | pure *n*-heptane yield 0.015 (a scenario, not an uncertainty bound) |
| Radiative fraction `χ_r` | `chir035`, `chir050` | 0.35 / 0.50 (base: 0.40) |
| Wall thermal BC | `adiabatic`, `inert` | adiabatic / cold walls held at ambient temperature (base: conducting walls) |
| Envelope airtightness | `sealed`, `leak08` | fully sealed / upper estimate `LEAK_AREA = 0.08 m²`, `n50 ≈ 20 1/h` (base: 0.035 m², `n50 ≈ 9 1/h`) |
| Grid resolution | `dx12`, `uni25`, `uni50` | near-field refined to 12.5 mm / uniform 25 mm / uniform 50 mm (base: locally-refined near-field) |
| Turbulence model | `dynsmag`, `vreman` | Dynamic Smagorinsky / Vreman (base: Deardorff) |
| Fire-source area | `pan175` | 175 × 175 mm burner at unchanged total heat release (base: 150 × 150 mm) |
| Heat of combustion | `dhc_e127` | heat-release ramp and `HEAT_OF_COMBUSTION` scaled by 0.9684 (fuel-specific oxygen-consumption constant 12.686 instead of 13.1 MJ/kg O₂; SM S4 quotes the tabulated 12.68), fuel and soot mass rates unchanged |
| Soot deposition | `sootdep_binned_rh`, `sootdep_d01_rh`, `sootdep_d1_rh`, `sootdep_d10_rh` | binned size distribution / monodisperse 0.1 / 1 / 10 µm; see the note below |
| Deposition control | `explchem_nodep_rh` | the explicit chemistry of the deposition decks without deposition (reference check, not a sensitivity case) |
| Run-to-run variability | `seed101`, `seed202`, `seed303` | the base with `&MISC RND_SEED = 101 / 202 / 303`, the random seed of the initial velocity perturbation; otherwise identical to `hep_160_075_ysmatched` (only `CHID` and `RND_SEED` differ). Not a parameter variation: FDS is deterministic, so only a changed seed exposes the run-to-run variability of the LES (Table S11 note e, Fig. 7) |

Each deck's `&HEAD` / `&MESH` / `&REAC` / `&SURF` blocks carry the actual
parameter values; this table only names the axis each deck isolates. Side changes
that come with an axis:

- The soot-deposition decks need soot as an explicitly transported species, so
  they replace the predefined simple-chemistry reaction by an explicit *n*-heptane
  reaction with the same soot and CO yields (0.0328 / 0.010), switch on the
  deposition physics, and add deposition outputs. FDS applies `HUMIDITY` only to
  its default background air, so these decks (suffix `_rh`) define the background
  `AIR` with the baseline's ambient composition (N2, O2, CO2, H2O) explicitly; the
  products include the components of the consumed air, and the net stoichiometry
  per mole of fuel equals that of the simple-chemistry baseline. The control
  `explchem_nodep_rh` reproduces the baseline peak extinction to −0.1 % on the room
  mean (Table S13).
- `uni50` coarsens the whole domain to 50 mm; the 25 mm pan-rim
  corner pieces (`Fire_pan_05`–`12`) are dropped because they are smaller than one cell.
- The prescribed heat-release ramp (`RAMP_Q`) of the variant decks agrees with the
  baseline to the fourth decimal (largest relative difference 3·10⁻⁵, from
  rounding when the decks were written) — immaterial to the results.

The decks are the input files of the reported runs. The edits made for this
package do not affect the solution: the tool-generated header and section-marker
comments were replaced, a few explanatory comments were shortened, the `inert` deck's
`TITLE` string and comment were brought
up to date with the FDS release used (6.11.1), and three output-only extinction
devices (vertical `EXT_STRIP_*` columns, not used in this paper) were removed.

`scripts/gen_model_tables.py` generates the paper's instrument-position, mesh,
surface and material tables (Tables S1, S8–S10) from the three production decks and
checks that they agree across the series.
