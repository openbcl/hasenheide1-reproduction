"""Combined light-extinction device validation against the PMMA reference filters.

All instruments are checked against the same six spectrally characterised PMMA
filters (`pmma_spectra/*.ASC`). The common quantity is the spectroscopic
reference transmission T_ref(lambda) at each device's operating wavelength:

  - LEM  (638 nm): measured single-pass transmission (mean +/- SD over 16 repeats,
                   lem/data_LEMV2_Reproduzierbarkeit.csv) vs. T_ref(638).
  - SICK (880 nm): double-pass reading m ~ T^2 -> single-pass sqrt(m) vs. T_ref(880).

Produces one combined parity figure (measured vs. reference transmission, 1:1
line) in the paper plot style, and a summary metrics table (printed + LaTeX).

Run:  python device_validation/validate_devices.py   (from anywhere; paths are absolute)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from plot_style import set_plot_style, figsize_single, save_pdf  # noqa: E402

set_plot_style(font_size=11, preamble_path=str(SCRIPTS / "plot_preamble.tex"))

SPECTRA = HERE / "pmma_spectra"
FILTERS = ["0A000", "7A670", "7C22", "7C82", "7C83", "8A570"]


def load_spectrum(pid):
    """ASC spectrum -> (wavelength [nm], transmission [0..1]), sorted."""
    wl, T = [], []
    for line in open(SPECTRA / f"{pid}.ASC", encoding="latin-1"):
        s = line.strip()
        if not s or s.startswith(("#", ";", ">", "WL")):
            continue
        if "," in s:
            left, right = s.split(",", 1)
            wl_str = left.strip()
            rp = right.strip().split()
            if not rp:
                continue
            T_str = rp[0]
        else:
            parts = s.split()
            if len(parts) < 2:
                continue
            wl_str, T_str = parts[0], parts[1]
        try:
            wl.append(float(wl_str.replace(",", ".")))
            T.append(float(T_str.replace(",", ".")))
        except ValueError:
            continue
    wl, T = np.array(wl), np.array(T) / 100.0
    i = np.argsort(wl)
    return wl[i], T[i]


def T_ref(pid, lam):
    wl, T = load_spectrum(pid)
    return float(np.interp(lam, wl, T))


# --- LEM: single-pass transmission, mean +/- SD over repeats; reference at 638 nm
lem = pd.read_csv(HERE / "lem" / "data_LEMV2_Reproduzierbarkeit.csv")
lem_meas = np.array([lem[p].dropna().mean() / 100 for p in FILTERS])
lem_sd = np.array([lem[p].dropna().std(ddof=1) / 100 for p in FILTERS])
lem_ref = np.array([T_ref(p, 638) for p in FILTERS])

# --- SICK: double-pass reading m ~ T^2, 5 repeats/filter (sick/PMMA_Kalibrierung.csv)
sick_cal = pd.read_csv(HERE / "sick" / "PMMA_Kalibrierung.csv",
                       sep=";", decimal=",").set_index("PMMA ID")
sick_reps = {p: sick_cal.loc[p].iloc[1:].astype(float).values for p in FILTERS}  # skip 'mean'
sick_m = np.array([sick_reps[p].mean() for p in FILTERS])
sick_m_sd = np.array([sick_reps[p].std(ddof=1) for p in FILTERS])
# single-pass transmission T = sqrt(m); propagated SD sigma_T = sigma_m / (2 sqrt(m))
sick_meas = np.sqrt(sick_m)
sick_sd = sick_m_sd / (2 * np.sqrt(sick_m))
sick_ref = np.array([T_ref(p, 880) for p in FILTERS])


def metrics(ref, meas):
    """Through-origin slope and max |measured-reference| [%].

    R^2 is deliberately not reported: with n = 6 points spanning 7-92 %
    transmittance an OLS R^2 is ~1 by construction and carries no
    information beyond slope and max deviation."""
    slope0 = np.sum(ref * meas) / np.sum(ref * ref)
    maxd = np.max(np.abs(meas - ref)) * 100
    return slope0, maxd


devices = [
    ("LEM",  638, len(FILTERS), lem_ref,  lem_meas,  lem_sd),
    ("SICK", 880, len(FILTERS), sick_ref, sick_meas, sick_sd),
]

# ------------------------------------------------- PMMA filter spectra figure
# Reference transmission T(lambda) of the six filters, with the device operating
# wavelengths marked (where T_ref is sampled). Filters are labelled directly at
# the right edge; device wavelengths annotated along the top.
fig, ax = plt.subplots(figsize=figsize_single(aspect=0.55))
cmap = plt.cm.viridis(np.linspace(0.05, 0.9, len(FILTERS)))
ends = []
for col, pid in zip(cmap, FILTERS):
    wl, T = load_spectrum(pid)
    m = wl <= 1000
    ax.plot(wl[m], T[m] * 100, color=col, lw=1.3)
    ends.append([T[m][-1] * 100, pid, col])
# direct right-edge labels, spread apart so close endpoints don't collide
ends.sort()
for i in range(1, len(ends)):
    if ends[i][0] - ends[i - 1][0] < 3.4:
        ends[i][0] = ends[i - 1][0] + 3.4
for y, pid, col in ends:
    ax.annotate(pid, xy=(1002, y), va="center", ha="left", fontsize=7,
                color=col, annotation_clip=False)
# device operating wavelengths (colours as in the main-text figures)
for lam, name, col in [(638, "LEM", "k"), (880, "SICK", "C3")]:
    ax.axvline(lam, color=col, lw=0.9, ls="--", zorder=0)
    ax.text(lam, 101, name, ha="center", va="bottom", fontsize=7, color=col,
            clip_on=False)
ax.set_xlabel(r"Wavelength $\lambda$ / \si{\nano\metre}")
ax.set_ylabel(r"Transmittance $\tau$ / \si{\percent}")
ax.set_xlim(400, 1055)
ax.set_ylim(0, 100)
ax.grid(True, alpha=0.25)
save_pdf(fig, HERE / "pmma_transmission")
plt.close(fig)

# ---------------------------------------------------------------- parity figure
# Square plot rendered at its on-page size (0.62 column widths, matching the
# \includegraphics width used in the Supplementary Material) so its fonts match
# the full-width figures instead of being shrunk by down-scaling.
_w = figsize_single()[0] * 0.62
fig, ax = plt.subplots(figsize=(_w, _w))
ax.plot([0, 1], [0, 1], color="0.5", ls="--", lw=1, label="1:1", zorder=1)
# Device colours/markers as in the main-text figures:
# LEM = black diamond, SICK = red (C3) square.
styles = {"LEM": dict(color="black", marker="D"), "SICK": dict(color="C3", marker="s")}
for name, lam, n, ref, meas, sd in devices:
    st = styles[name]
    # alpha < 1 so coincident points (e.g. SICK 0A000 and 7C82, both ~91 % at
    # 880 nm) render as a denser marker rather than a single one.
    ax.errorbar(ref, meas, yerr=sd, fmt=st["marker"], color=st["color"],
                capsize=2, ms=6, lw=0, elinewidth=0.8, alpha=0.7,
                markeredgecolor="white", markeredgewidth=0.5,
                label=rf"{name} ({lam}~nm)", zorder=3)
# annotate the two coincident SICK points (0A000 and 7C82, both ~91 % at 880 nm)
_i = FILTERS.index("0A000")
ax.annotate("2 points", xy=(sick_ref[_i], sick_meas[_i] - 0.02),
            xytext=(sick_ref[_i], 0.70), ha="center", va="top", fontsize=7, color="C3",
            arrowprops=dict(arrowstyle="->", color="C3", lw=0.7, shrinkB=1))
ax.set_xlabel(r"Reference transmittance $\tau_\mathrm{ref}$")
ax.set_ylabel(r"Measured transmittance $\tau$")
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.set_aspect("equal")
ax.grid(True, alpha=0.25)
ax.legend(loc="upper left", frameon=False)
try:
    save_pdf(fig, HERE / "parity_validation")
except PermissionError:
    print("WARNING: parity_validation.pdf is locked (open in a viewer?) — skipped.")
plt.close(fig)

# ------------------------------------------------ SICK effective-wavelength fit
# Double-pass model m_i = a(lambda) * T_i(lambda)^2; minimise RMSE over wavelength.
lam_grid = np.arange(400, 1501, 1.0)
Xg = np.stack([np.interp(lam_grid, *load_spectrum(p)) ** 2 for p in FILTERS], axis=1)
a_lam = (Xg @ sick_m) / (Xg ** 2).sum(axis=1)
rmse_lam = np.sqrt(((sick_m - a_lam[:, None] * Xg) ** 2).sum(axis=1) / len(FILTERS))
lam_best = lam_grid[int(np.argmin(rmse_lam))]
fig, ax = plt.subplots(figsize=figsize_single(aspect=0.6))
ax.plot(lam_grid, rmse_lam, color="C3", lw=1.3)
ax.axvline(lam_best, color="0.4", ls="--", lw=0.9)
ax.text(lam_best + 15, rmse_lam.max() * 0.82, rf"$\lambda_\mathrm{{SICK}} = {lam_best:.0f}$~nm",
        color="0.3", fontsize=8)
ax.set_xlabel(r"Wavelength $\lambda$ / \si{\nano\metre}")
ax.set_ylabel("RMSE")
ax.set_xlim(400, 1500)
ax.set_ylim(bottom=0)
ax.grid(True, alpha=0.25)
save_pdf(fig, HERE / "sick_wavelength_fit")
plt.close(fig)
print(f"SICK effective-wavelength fit: lambda_best = {lam_best:.0f} nm")

# ----------------------------------------------------------------------- table
rows = []
print(f"\n{'Device':6s} {'lambda':>7s} {'n':>3s} {'slope':>7s} "
      f"{'max|d| %':>9s} {'repro SD %':>11s}")
for name, lam, n, ref, meas, sd in devices:
    slope0, maxd = metrics(ref, meas)
    repro = f"{np.mean(sd) * 100:.2f}" if sd is not None else "--"
    print(f"{name:6s} {lam:7d} {n:3d} {slope0:7.4f} {maxd:9.2f} {repro:>11s}")
    rows.append((name, lam, n, slope0, maxd, repro))

# LaTeX table snippet for the paper (kept alongside the other tables/)
tex = ROOT / "tables" / "device_validation_table.tex"
with open(tex, "w", encoding="utf-8", newline="\n") as f:
    f.write("% Auto-generated by device_validation/validate_devices.py\n")
    f.write("\\begin{tabular}{l c c c c c}\n\\toprule\n")
    f.write("Device & $\\lambda$ [nm] & $n$ & Slope & "
            "$\\max|\\Delta|$ [\\%] & Repro.\\ SD [\\%] \\\\\n\\midrule\n")
    for name, lam, n, slope0, maxd, repro in rows:
        f.write(f"{name} & {lam} & {n} & {slope0:.4f} & "
                f"{maxd:.2f} & {repro} \\\\\n")
    f.write("\\bottomrule\n\\end{tabular}\n")

print(f"\nWrote {HERE / 'parity_validation.pdf'}")
print(f"Wrote {tex}")
