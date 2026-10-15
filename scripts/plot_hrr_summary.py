"""HRR / normalised-mass ensemble summary (paper Fig. 3).

Three panels (one per test series): ensemble-mean mass-loss-derived heat release
rate with its +/-1 sigma band (left axis) and the normalised remaining mass
(right axis).

Plotter (figures stage, committed): the figure is rendered from the committed
reduced curves in results/measurement/hrr/ (written by the data target reduce_hrr,
scripts/reduce_hrr_from_mass.py), so plots/measurement/hrr_summary.pdf regenerates without the
raw mass records.

Run:  python scripts/plot_hrr_summary.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from plot_style import set_plot_style, figsize_single, save_pdf
import paths as P

SERIES = ["hep_160_075", "hep_160_150", "hep_220_300"]
LABELS = ["Hep_160_075", "Hep_160_150", "Hep_220_300"]

REDUCED_DIR = P.RESULTS_DIR / "measurement" / "hrr"

C_HRR, C_RST, C_MASS = "C0", "C1", "C3"


def load_reduced() -> list:
    """Per-series tuples from the committed reduced CSV, in the structure plot()
    expects (rst_* are None: the paper figure has no O2 overlay)."""
    df = pd.read_csv(REDUCED_DIR / "hrr_summary.csv", float_precision="round_trip")
    data = []
    for series in SERIES:
        g = df[df["series"] == series]
        data.append((g["t_s"].to_numpy(float),
                     g["hrr_mean"].to_numpy(float), g["hrr_std"].to_numpy(float),
                     g["m_mean"].to_numpy(float), g["m_std"].to_numpy(float),
                     None, None, None))
    return data


def plot(data: list, mass_as_fraction: bool, show_o2: bool,
         hide_inner: bool = True):
    import matplotlib.pyplot as plt

    w_single, h_single = figsize_single(aspect=0.4)
    fig, axs = plt.subplots(1, 3, figsize=(w_single, h_single), sharex=True)
    for k, (ax, (t, hrr_mean, hrr_std, m_mean, m_std,
                 rst_t, rst_mean, rst_std)) in enumerate(zip(axs, data)):
        ax.plot(t, hrr_mean, color=C_HRR, label="HRR (mass loss)")
        ax.fill_between(t, hrr_mean - hrr_std, hrr_mean + hrr_std,
                        facecolor=C_HRR, edgecolor="None", alpha=0.20,
                        label=r"HRR $\pm 1\sigma$")
        if show_o2:
            ax.plot(rst_t, rst_mean, color=C_RST, linestyle="--", linewidth=1.2,
                    label="HRR (O$_2$ cal., validation)")
            ax.fill_between(rst_t, rst_mean - rst_std, rst_mean + rst_std,
                            facecolor=C_RST, edgecolor="None", alpha=0.10)
        ax.set_xlim(-30, 360)
        ax.set_xticks([0, 100, 200, 300])
        ax.set_ylim(0, 75)
        ax.set_yticks([0, 15, 30, 45, 60, 75])
        ax.grid(alpha=0.25)
        ax.set_title(LABELS[k])
        ax.set_xlabel(r"Time / \si{\second}")
        if k == 0:
            ax.set_ylabel(r"$\dot Q$ / \si{\kilo\watt}", color=C_HRR)
        else:
            ax.set_ylabel("")
            if hide_inner:
                ax.tick_params(axis="y", labelleft=False)

        ax2 = ax.twinx()
        ax2.plot(t, m_mean, linestyle="--", color=C_MASS,
                 label=r"Mean $m/m_{\mathrm{fuel}}$" if mass_as_fraction else "Mean mass")
        ax2.fill_between(t, m_mean - m_std, m_mean + m_std,
                         facecolor=C_MASS, edgecolor="None", alpha=0.20)
        ax2.set_ylim(0, 1)
        if k == len(axs) - 1:
            ax2.set_ylabel(
                r"Normalised mass $m/m_{\mathrm{fuel}}$" if mass_as_fraction
                else r"Mass / \si{\gram}", color=C_MASS)
        else:
            ax2.set_ylabel("")
            if hide_inner:
                ax2.tick_params(axis="y", labelright=False)

    fig.tight_layout()
    out = save_pdf(fig, P.PLOTS_DIR / "measurement" / "hrr_summary")
    plt.close(fig)
    print(f"figure: {out}")
    return out


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    set_plot_style(
        preamble_path=Path(__file__).resolve().parent / "plot_preamble.tex",
        font_size=11,
    )
    data = load_reduced()
    plot(data, mass_as_fraction=True, show_o2=False)


if __name__ == "__main__":
    main()
