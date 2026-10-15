"""Figure: blower-door air-tightness of the test apartment (log-log Q vs dp).

Reads the committed reduced CSVs (results/measurement/blowerdoor_{summary,points}.csv) and
plots the pressurisation/depressurisation series with their power-law fits
against the a-priori leakage boundary condition adopted in the FDS model.
Output: plots/measurement/blowerdoor_leakage.pdf (paper figure, Fig. S4).

Run after scripts/reduce_blowerdoor.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_style import set_plot_style, figsize_single, FDS_IDEAL_STYLE  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
RES = REPO / "results"
V_FLUPPE = 128.0  # net air volume [m^3]: FDS mesh minus the wall/obstruction
#                   blocks (SM S2); the reference volume for V50/n50.

# (test key, label, colour, linewidth) in plot order; fluppe emphasised
SERIES = [("fluppe", "Fluppe (whole)", "C3", 2.0),
          ("F1", "F1", "C0", 1.0),
          ("F1F2", "F1+F2", "C1", 1.0),
          ("F3", "F3", "C2", 1.0),
          ("bemme", "Bemme (ref.)", "0.55", 1.0)]


def main() -> None:
    set_plot_style(preamble_path=Path(__file__).resolve().parent / "plot_preamble.tex",
                   font_size=11)
    summ = pd.read_csv(RES / "measurement" / "blowerdoor_summary.csv")
    pts = pd.read_csv(RES / "measurement" / "blowerdoor_points.csv")

    fig, ax = plt.subplots(figsize=(figsize_single()[0], figsize_single()[0] * 0.72))
    xx = np.logspace(0, np.log10(65), 60)   # extend fits down to 1 Pa (extrapolation)
    ends = []                               # (flow at 65 Pa, label, colour) for direct labels
    for key, lab, col, lw in SERIES:
        so = summ[(summ.test == key) & (summ.direction == "pressurization")].iloc[0]
        ax.loglog(xx, so.cenv * xx ** so.n_exp, "-", color=col, lw=lw,
                  label=rf"{lab} ($n={so.n_exp:.2f}$)")
        ends.append((so.cenv * 65 ** so.n_exp, lab.split(" (")[0], col))
        po = pts[(pts.test == key) & (pts.direction == "pressurization")]
        ax.loglog(po.dp_pa, po.q_m3h, "o", color=col, ms=4, mfc="none")
        pu = pts[(pts.test == key) & (pts.direction == "depressurization")]
        ax.loglog(pu.dp_pa, pu.q_m3h, "s", color=col, ms=4, mfc="none", alpha=.7)

    ax.loglog(xx, 9 * V_FLUPPE * (xx / 50) ** 0.65, lw=1.4,
              label=r"adopted ($n_{50}{=}9$, $n{=}0.65$)", **FDS_IDEAL_STYLE)
    ends.append((9 * V_FLUPPE * (65 / 50) ** 0.65, "adopted", FDS_IDEAL_STYLE.get("color", "0.5")))
    # Direct labels at the right end of each fit line, so the curves stay
    # identifiable in greyscale print (the room colours print as similar greys).
    # Labels closer than MIN_DEC decades are pushed apart symmetrically.
    MIN_DEC = 0.065
    ends.sort()
    ly = [np.log10(q) for q, _, _ in ends]
    for _ in range(50):
        for i in range(1, len(ly)):
            gap = ly[i] - ly[i - 1]
            if gap < MIN_DEC:
                ly[i - 1] -= (MIN_DEC - gap) / 2
                ly[i] += (MIN_DEC - gap) / 2
    for (q, lab, col), y in zip(ends, ly):
        ax.text(67, 10 ** y, lab, fontsize=7, color=col, ha="left", va="center",
                clip_on=False)
    # fire regime (FDS zone pressure, up to ~6 Pa); grey, since C1 is room F2's colour
    ax.axvspan(1, 6, color="0.5", alpha=.10)
    ax.text(2.4, 1050, "fire\nregime", fontsize=8, color="0.35", ha="center", va="top")
    ax.set_xlabel(r"building pressure difference $\Delta p$ / Pa")
    ax.set_ylabel(r"air flow $Q$ / (m$^{3}$\,h$^{-1}$)")
    ax.legend(loc="lower right"); ax.grid(True, which="both", alpha=.25); ax.set_xlim(1, 65)
    fig.tight_layout()

    paper = REPO / "plots" / "measurement" / "blowerdoor_leakage.pdf"
    paper.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(paper)
    print(f"paper figure: {paper}")


if __name__ == "__main__":
    main()
