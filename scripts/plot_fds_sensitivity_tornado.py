"""Tornado chart of the FDS sensitivity study (Supplementary Material: FDS sensitivity study).

For each documented axis, the deviation of a peak validation quantity from the
baseline, resolved per room and spanning the range produced by that axis's
parameter variations: peak light extinction k in rooms F1-F3 (left) and peak
upper-layer temperature rise in the two rooms with an upper-layer comparison,
F1 and F2 (right; the F3 slot stays blank so the rooms line up across panels). Reads
results/simulation/fds_sensitivity.csv (scripts/fds_sensitivity_results.py) and renders plots/simulation/fds_sensitivity_tornado.pdf.

The non-physical 10 um soot-deposition case is excluded from the deposition range
(noted in the caption); the pure-heptane fuel substitution is a scenario, not an
uncertainty bound, and is drawn from zero.

    python scripts/plot_fds_sensitivity_tornado.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from plot_style import set_plot_style, figsize_single
import paths as P

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
OUT = REPO_ROOT / "plots" / "simulation" / "fds_sensitivity_tornado"

EXT_ROOMS = [("F1", "dk_F1_pct"), ("F2", "dk_F2_pct"), ("F3", "dk_F3_pct")]
# No gas temperature was measured in F3, so it has no upper-layer comparison. Its slot
# is kept (column None = left blank) so the room bars line up across the two panels.
TMP_ROOMS = [("F1", "dTu_F1_pct"), ("F2", "dTu_F2_pct"), ("F3", None)]
# room colours matched to the apartment isometry (Fig. 1; CE in
# plot_apartment_geometry.py): F1 blue, F2 orange, F3 green.
ROOM_C = {"F1": "#1f77b4", "F2": "#ff7f0e", "F3": "#2ca02c"}

EXCLUDE_FROM_RANGE = {"sootdep_d10_rh"}     # 10 um deposition is non-physical
# Run-to-run variability of the LES (results/simulation/fds_seed_noise.csv, scripts/fds_seed_noise.py):
# largest deviation of the seed realisations of the baseline, per room and quantity; drawn
# as a grey band behind each bar so effects inside it read as not resolved.
NOISE_QTY = {"dk_F1_pct": "k_F1", "dk_F2_pct": "k_F2", "dk_F3_pct": "k_F3",
             "dTu_F1_pct": "dTu_F1", "dTu_F2_pct": "dTu_F2"}
NOISE_C = "0.72"
SCENARIO_FROM_ZERO = {"Fuel substitution"}  # single scenario case, draw from 0


def span(rows: pd.DataFrame, col: str, group: str) -> tuple[float, float]:
    d = rows[~rows["run"].isin(EXCLUDE_FROM_RANGE)]
    vals = d[col].to_numpy(float)
    if group in SCENARIO_FROM_ZERO or vals.size == 1:
        return tuple(sorted([0.0, float(vals[0])]))
    return float(vals.min()), float(vals.max())


def panel(ax, df, groups, y, rooms, title, noise=None):
    n = len(rooms)
    offs = np.linspace(0.28, -0.28, n)      # F1 on top within each group slot
    h = 0.52 / n
    band = 0.75 * 0.56 / (n - 1)            # noise band: taller than the bar, gaps between rooms
    for i, gi in enumerate(y):              # alternating row bands aid axis mapping
        if i % 2 == 1:
            ax.axhspan(gi - 0.5, gi + 0.5, color="0.93", zorder=0)
    lo_all, hi_all = [0.0], [0.0]
    for (room, col), off in zip(rooms, offs):
        if col is None:                     # blank slot (room without this quantity)
            continue
        for gi, g in zip(y, groups):
            lo, hi = span(df[df.group == g], col, g)
            lo_all.append(lo)
            hi_all.append(hi)
            if noise is not None:
                r = noise[NOISE_QTY[col]]
                ax.barh(gi + off, 2 * r, left=-r, height=band, zorder=2,
                        color=NOISE_C, linewidth=0)
            ax.barh(gi + off, hi - lo, left=lo, height=h, zorder=3,
                    color=ROOM_C[room], edgecolor="black", linewidth=0.4)
    ax.axvline(0, color="0.3", lw=0.8, zorder=2)
    ax.grid(axis="x", color="0.85", lw=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.set_xlabel(title + r" deviation [\si{\percent}]")
    dmin, dmax = min(lo_all), max(hi_all)
    pad = 0.08 * (dmax - dmin)
    ax.set_xlim(dmin - pad, dmax + pad)


def main() -> None:
    set_plot_style(preamble_path=HERE / "plot_preamble.tex", font_size=10)  # dense multi-panel; one below the single-panel figures
    df = pd.read_csv(P.RESULTS_DIR / "simulation" / "fds_sensitivity.csv")
    df = df[df["group"] != "Baseline"]      # zero by definition; no bar
    df = df[df["run"] != "pan175"]          # fire-source area: grid-snap limiting bracket, prose-only (like wall-BC), not a tornado axis
    df = df[df["run"] != "explchem_nodep_rh"]  # deposition control (reference check), not a case
    df = df[df["run"] != "dhc_e127"]        # heat-of-combustion case: in Table S13 and the text, not a tornado axis

    groups = list(dict.fromkeys(df["group"]))
    # order by the widest per-room extinction range (largest sensitivity on top)
    def width(g):
        return max(span(df[df.group == g], c, g)[1] - span(df[df.group == g], c, g)[0]
                   for _, c in EXT_ROOMS)
    groups = sorted(groups, key=width, reverse=True)
    y = np.arange(len(groups))[::-1]

    w, h = figsize_single(aspect=0.72)
    fig, (a1, a2) = plt.subplots(1, 2, sharey=True, figsize=(w, h))
    nf = P.RESULTS_DIR / "simulation" / "fds_seed_noise.csv"
    noise = (pd.read_csv(nf).set_index("quantity")["max_abs_dev_pct"].to_dict()
             if nf.exists() else None)
    panel(a1, df, groups, y, EXT_ROOMS, r"Peak extinction $k$", noise)
    panel(a2, df, groups, y, TMP_ROOMS, r"Peak $\Delta T$ (upper layer)", noise)
    a1.set_yticks(y)
    a1.set_yticklabels(groups)
    a1.set_ylim(y.min() - 0.6, y.max() + 0.6)
    for ax in (a1, a2):                       # categorical y-axis: no minor ticks
        ax.tick_params(axis="y", which="minor", left=False, right=False)

    handles = [Patch(facecolor=ROOM_C[r], edgecolor="black", linewidth=0.4, label=r)
               for r in ("F1", "F2", "F3")]
    if noise is not None:
        handles.append(Patch(facecolor=NOISE_C, linewidth=0, label="run-to-run variability"))
    fig.legend(handles=handles, ncol=len(handles), loc="lower center",
               frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.05, 1, 1), pad=0.4)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT.with_suffix(".pdf"))
    print(f"wrote {OUT.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()
