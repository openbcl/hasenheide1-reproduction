"""3x3 extinction matrices (measured, Fig. 4; with FDS, Fig. 6) and the
temperature-profile matrices (Supplementary Material).

Plotter (figures stage, committed): renders both matrix figures from the committed
reduced curves in results/validation/matrices/ (written by reduce_matrices.py), so the PDFs
regenerate without the raw measurement data. The drawing is a faithful transcription of
the original combined script -- same artists, order, styling -- and is verified
byte-identical against the committed reference. The reduced CSVs are read with
float_precision='round_trip' so the arrays reach the plot bit-for-bit identical.

Run:  python scripts/plot_extinction_matrices.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from plot_style import (set_plot_style, figsize_single, save_pdf,
                        INSTRUMENT_STYLE, FDS_COLOR)
import paths as P

REDUCED_DIR = P.RESULTS_DIR / "validation" / "matrices"
OUTPUT_PATH = P.PLOTS_DIR

SERIES_NAMES = ["Hep_160_075", "Hep_160_150", "Hep_220_300"]
ROOMS = ["F1", "F2", "F3"]
TARGET_TIMES = [150, 300, 450]
HEIGHTS = [0.6, 1.2, 1.6, 1.8, 2.0, 2.2, 2.4, 2.5]


def _rt(name):
    return pd.read_csv(REDUCED_DIR / name, float_precision="round_trip")


def _rt_opt(name, cols):
    """Like _rt but returns an empty frame if the file is absent, so the FDS
    overlay degrades gracefully when the baseline curves have not been reduced."""
    p = REDUCED_DIR / name
    return (pd.read_csv(p, float_precision="round_trip") if p.exists()
            else pd.DataFrame(columns=cols))


# -------- extinction matrix (measured Fig. 4 / with-FDS Fig. 6) --------
def plot_extinction_matrix_3x3(output_path, with_fds=False):
    import matplotlib.pyplot as plt

    lem = _rt("ext_lem.csv")
    sick = _rt("ext_sick.csv")
    meta = _rt("ext_meta.csv").set_index(["series", "room"])
    fds = _rt_opt("ext_fds.csv", ["series", "room", "t_s", "k"])

    fig, axes = plt.subplots(3, 3, figsize=figsize_single(aspect=1.05),
                             sharex=True, sharey=True)
    base_fs = plt.rcParams.get('font.size', 11)

    for row_idx, name in enumerate(SERIES_NAMES):
        m = meta.loc[name]
        m_dur = float(m["m_dur"].iloc[0]); m_vent = float(m["m_vent"].iloc[0])
        for col_idx, room in enumerate(ROOMS):
            ax = axes[row_idx, col_idx]
            n_lem = int(meta.loc[(name, room), "n_lem"])
            n_sick = int(meta.loc[(name, room), "n_sick"])

            # per-run SICK curves (experiment variant only; the validation
            # variant shows the LEM band + FDS for an uncluttered comparison)
            if not with_fds:
                s = sick[(sick["series"] == name) & (sick["room"] == room)]
                for _run, g in s.groupby("run", sort=False):
                    ax.plot(g["t_s"].to_numpy(float), g["sick"].to_numpy(float),
                            color=INSTRUMENT_STYLE["SICK"][0], lw=0.5, alpha=0.5, zorder=10)

            # LEM ensemble mean +/- std
            le = lem[(lem["series"] == name) & (lem["room"] == room)]
            if not le.empty:
                t = le["t_s"].to_numpy(float)
                mean = le["mean"].to_numpy(float)
                std = le["std"].to_numpy(float)
                ax.plot(t, mean, color='black', linewidth=1, zorder=5)
                ax.fill_between(t, mean - std, mean + std, facecolor='black',
                                alpha=0.3, zorder=5)

            # FDS baseline overlay (solid; only in the validation variant)
            if with_fds:
                fe = fds[(fds["series"] == name) & (fds["room"] == room)]
                if not fe.empty:
                    ax.plot(fe["t_s"].to_numpy(float), fe["k"].to_numpy(float),
                            color=FDS_COLOR, linestyle='-', linewidth=1.0, zorder=6)

            if m_dur:
                ax.axvline(m_dur, color='0.35', linewidth=0.9, ls=(0, (4, 2)),
                           alpha=0.9, zorder=2)
            if m_vent:
                ax.axvspan(m_vent, 1500, facecolor='C0', alpha=0.2, zorder=0)

            subplot_handles = []
            if n_lem > 0:
                subplot_handles.append(plt.Line2D([0], [0], color='black', lw=1,
                                                  label=f'n = {n_lem}'))
            if n_sick > 0 and not with_fds:
                subplot_handles.append(plt.Line2D([0], [0], color='C3', lw=0.5,
                                                  alpha=0.5, label=f'n = {n_sick}'))
            if subplot_handles:
                ax.legend(handles=subplot_handles, loc='upper right',
                          fontsize=base_fs - 3, frameon=False,
                          handlelength=1.0, handletextpad=0.5)

            if row_idx == 0:
                ax.set_title(f"Room {room}", fontsize=base_fs, fontweight='bold')
            if col_idx == 0:
                ax.set_ylabel(f"{name}\n" r"$k$ / \si{\per\metre}")
            if row_idx == 2:
                ax.set_xlabel(r"$t$ / \si{\second}")

            ax.set_xlim(-60, 1500)
            ax.set_xticks([0, 500, 1000, 1500])
            ax.set_ylim(0, 1.3)
            ax.grid(True, alpha=0.25)

    legend_elements = [
        plt.Line2D([0], [0], color='black', lw=1, label=r'LEM Mean $\pm\sigma$'),
    ]
    if with_fds:
        legend_elements.append(plt.Line2D([0], [0], color=FDS_COLOR, lw=1.0, label='FDS'))
    else:
        legend_elements.append(
            plt.Line2D([0], [0], color=INSTRUMENT_STYLE["SICK"][0], lw=0.5, alpha=0.5,
                       label='SICK (corr.)'))
    legend_elements += [
        plt.Line2D([0], [0], color='0.35', lw=0.9, ls=(0, (4, 2)), label='Mean flame-out'),
        plt.Rectangle((0, 0), 1, 1, facecolor='C0', alpha=0.15, label='Ventilation'),
    ]
    fig.legend(handles=legend_elements, loc='lower center', bbox_to_anchor=(0.5, 0.05),
               ncol=len(legend_elements), frameon=False, fontsize=base_fs - 1)
    fig.subplots_adjust(bottom=0.16, top=0.92, left=0.15, right=0.97,
                        hspace=0.15, wspace=0.15)
    out = save_pdf(fig, output_path / ("extinction_matrix_3x3_fds" if with_fds
                                       else "extinction_matrix_3x3"))
    plt.close(fig)
    return out


# -------- temperature matrix (Supplementary Material) --------
def plot_temperature_profile_matrix(output_path, with_fds=False):
    import matplotlib.pyplot as plt

    prof = _rt("temp_prof.csv")
    ceil = _rt("temp_ceil.csv").set_index(["series", "t_target"])
    fds = _rt_opt("temp_fds.csv", ["series", "t_target", "z", "f1", "f2"])
    fds_plume = _rt_opt("temp_fds_plume.csv", ["series", "t_target", "plume"])

    fig, axes = plt.subplots(3, 3, figsize=figsize_single(aspect=0.95),
                             sharex='col', sharey=True)
    base_fs = plt.rcParams.get('font.size', 11)

    for row_idx, name in enumerate(SERIES_NAMES):
        for col_idx, t_val in enumerate(TARGET_TIMES):
            ax = axes[row_idx, col_idx]
            g = prof[(prof["series"] == name) & (prof["t_target"] == t_val)]
            mean_f1 = g["mean_f1"].to_numpy(float)
            std_f1 = g["std_f1"].to_numpy(float)
            mean_f2 = g["mean_f2"].to_numpy(float)
            std_f2 = g["std_f2"].to_numpy(float)
            m_ceil = float(ceil.loc[(name, t_val), "m_ceil"])
            s_ceil = float(ceil.loc[(name, t_val), "s_ceil"])

            # room colours as in Figure 1 and Figure 7 (F1 C0, F2 C1)
            ax.plot(mean_f1, HEIGHTS, 'o-', color='C0', ms=3, lw=0.3, label='Room F1')
            ax.plot(mean_f2, HEIGHTS, 's-', color='C1', ms=3, lw=0.3, label='Room F2')
            if not np.isnan(m_ceil):
                ax.errorbar(m_ceil, 2.53, xerr=s_ceil, fmt='.', color='black',
                            ms=4, mew=1, capsize=2, elinewidth=0.5,
                            label='Plume Impingement F1')
            ax.fill_betweenx(HEIGHTS, mean_f1 - std_f1, mean_f1 + std_f1, color='C0',
                             alpha=0.3, edgecolor="None")
            ax.fill_betweenx(HEIGHTS, mean_f2 - std_f2, mean_f2 + std_f2, color='C1',
                             alpha=0.3, edgecolor="None")

            # FDS baseline overlay (dashed profiles + open ceiling/plume marker)
            if with_fds:
                gf = fds[(fds["series"] == name) & (fds["t_target"] == t_val)]
                if not gf.empty:
                    zf = gf["z"].to_numpy(float)
                    ax.plot(gf["f1"].to_numpy(float), zf, ls='--', color='C0', lw=1.0)
                    ax.plot(gf["f2"].to_numpy(float), zf, ls='--', color='C1', lw=1.0)
                pf = fds_plume[(fds_plume["series"] == name)
                               & (fds_plume["t_target"] == t_val)]
                if not pf.empty:
                    ax.plot(float(pf["plume"].iloc[0]), 2.53, marker='o', ls='none',
                            mfc='none', mec='black', ms=4, mew=1)

            if row_idx == 0:
                ax.set_title(f"$t = {t_val}$ " r"\si{\second}", fontsize=base_fs, fontweight='bold', pad=10)
            if col_idx == 0:
                ax.set_ylabel(f"{name}\n" r"$z$ / \si{\metre}", fontsize=base_fs)
            if row_idx == 2:
                ax.set_xlabel(r"$\Delta T$ / \si{\celsius}", fontsize=base_fs)

            if col_idx == 0:
                ax.set_xlim(-5, 100)
            elif col_idx == 1:
                ax.set_xlim(-5, 60)
            else:
                ax.set_xlim(-5, 30)

            ax.set_ylim(0, 2.7)
            ax.set_yticks([0, 0.5, 1.0, 1.5, 2.0, 2.5])
            ax.axhline(2.53, linestyle="dotted", lw=1, color="black")
            ax.grid(True, alpha=0.25)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    if with_fds:
        handles.append(plt.Line2D([0], [0], color='black', ls='--', lw=1.0))
        labels.append('FDS profile')
        handles.append(plt.Line2D([0], [0], marker='o', ls='none', mfc='none',
                                  mec='black', ms=4))
        labels.append('FDS plume')
        # five entries would overflow the figure width in one row, so shorten the
        # long plume label and wrap to two rows at a slightly smaller size
        labels = [l.replace('Plume Impingement F1', 'Plume F1') for l in labels]
        leg_ncol, leg_fs, leg_y, leg_bottom = 3, base_fs - 1, 0.03, 0.19
    else:
        leg_ncol, leg_fs, leg_y, leg_bottom = len(labels), base_fs, 0.04, 0.16
    fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(0.5, leg_y),
               ncol=leg_ncol, frameon=False, fontsize=leg_fs)
    fig.subplots_adjust(bottom=leg_bottom, top=0.92, left=0.15, right=0.97,
                        hspace=0.15, wspace=0.15)
    out = save_pdf(fig, output_path / ("temperature_matrix_3x3_fds" if with_fds
                                       else "temperature_matrix_3x3"))
    plt.close(fig)
    return out


def plot_temperature_heatmap_3x3(output_path, tree):
    """Time-height dT heatmap for one thermocouple tree: rows = the three fire
    series, columns = measured | FDS | difference (FDS - measured). The two
    absolute columns share a sequential scale (directly comparable); the
    difference column uses a symmetric diverging scale so the model bias (warm =
    over-prediction) is visible over the whole trajectory, not just the snapshots
    of the profile matrix. Reads the committed full time-height matrices."""
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    meas = _rt("temp_prof_full.csv")
    fds = _rt_opt("temp_fds_full.csv", ["series", "tree", "t_s", "z", "dT"])
    z = np.array(HEIGHTS, float)

    def _grid(df, name):
        g = df[(df["series"] == name) & (df["tree"] == tree)]
        p = g.pivot(index="z", columns="t_s", values="dT").reindex(z)
        return p.columns.to_numpy(float), p.to_numpy(float)   # t, M(z, t)

    M, vmax_abs, vmax_diff = {}, 0.0, 0.0
    for name in SERIES_NAMES:
        t, mm = _grid(meas, name)
        _, mf = _grid(fds, name)
        d = mf - mm
        M[name] = (t, mm, mf, d)
        for a in (mm, mf):
            if np.any(~np.isnan(a)):
                vmax_abs = max(vmax_abs, float(np.nanmax(a)))
        if np.any(~np.isnan(d)):
            vmax_diff = max(vmax_diff, float(np.nanmax(np.abs(d))))

    # Round, nonlinearly-spaced absolute levels (denser at low dT) so the smaller
    # fires are resolved rather than crushed into the dark end by the largest
    # fire's peak, with a round per-figure ceiling and round colourbar ticks; the
    # difference panel stays linear.
    _ladder = np.array([0, 2, 5, 8, 10, 15, 20, 30, 40, 50, 60, 80, 100], float)
    _top = float(_ladder[_ladder >= vmax_abs][0]) if np.any(_ladder >= vmax_abs) else vmax_abs
    lev_abs = _ladder[_ladder <= _top]
    abs_ticks = np.array([0, 5, 10, 20, 40, 80], float)
    abs_ticks = abs_ticks[abs_ticks <= _top]
    lev_diff = MaxNLocator(nbins=12).tick_values(-vmax_diff, vmax_diff)

    fig, axes = plt.subplots(3, 3, figsize=figsize_single(aspect=0.82),
                             sharex=True, sharey=True, constrained_layout=True)
    base_fs = plt.rcParams.get('font.size', 11)
    col_titles = ['Measured', 'FDS', r'FDS $-$ Measured']
    m_abs = m_diff = None
    for row, name in enumerate(SERIES_NAMES):
        t, mm, mf, d = M[name]
        m_abs = axes[row, 0].contourf(t, z, mm, levels=lev_abs, cmap='inferno', extend='both')
        axes[row, 1].contourf(t, z, mf, levels=lev_abs, cmap='inferno', extend='both')
        m_diff = axes[row, 2].contourf(t, z, d, levels=lev_diff, cmap='RdBu_r', extend='both')
        # thin isolines, dashed where FDS is lower: keeps the sign readable in
        # greyscale, where both ends of the diverging scale print equally dark
        axes[row, 2].contour(t, z, d, levels=[v for v in lev_diff if v != 0],
                             colors='k', linewidths=0.3, alpha=0.7,
                             negative_linestyles='dashed')
        axes[row, 0].set_ylabel(f"{name}\n" r"$z$ / \si{\metre}", fontsize=base_fs)
        for col in range(3):
            axes[row, col].set_xlim(0, 900)
            axes[row, col].set_ylim(0.6, 2.55)
            axes[row, col].set_yticks([1.0, 1.5, 2.0, 2.5])
            axes[row, col].grid(False)
    for col in range(3):
        axes[0, col].set_title(col_titles[col], fontsize=base_fs, fontweight='bold')
        axes[2, col].set_xlabel(r"Time / \si{\second}", fontsize=base_fs)

    cb1 = fig.colorbar(m_abs, ax=list(axes[:, :2].ravel()), location='right',
                       aspect=32, pad=0.02, ticks=abs_ticks)
    cb1.set_label(r"$\Delta T$ / \si{\celsius}", fontsize=base_fs)
    cb1.ax.set_yticklabels([f"{v:.0f}" for v in abs_ticks])
    cb2 = fig.colorbar(m_diff, ax=list(axes[:, 2]), location='right',
                       aspect=32, pad=0.02)
    cb2.set_label(r"$\Delta T_\mathrm{FDS}-\Delta T_\mathrm{meas}$ / \si{\kelvin}",
                  fontsize=base_fs)
    for y, va, s in ((1.075, 'bottom', 'FDS higher'), (-0.075, 'top', 'FDS lower')):
        cb2.ax.text(0.5, y, s, transform=cb2.ax.transAxes, ha='center', va=va,
                    fontsize=0.6 * base_fs)
    out = save_pdf(fig, output_path / f"temperature_heatmap_{tree}")
    plt.close(fig)
    return out


def main() -> None:
    set_plot_style(
        preamble_path=Path(__file__).resolve().parent / "plot_preamble.tex",
        font_size=11,
    )
    P.MEAS_PLOTS.mkdir(parents=True, exist_ok=True)
    P.VAL_PLOTS.mkdir(parents=True, exist_ok=True)
    # The measured-only extinction matrix (Fig. 4) is an experimental result; the
    # FDS-overlay variants (Fig. 6, S8-S10) are model-vs-measurement comparisons.
    plot_extinction_matrix_3x3(P.MEAS_PLOTS)
    plot_extinction_matrix_3x3(P.VAL_PLOTS, with_fds=True)
    print("-> extinction_matrix_3x3{,_fds}.pdf")
    # Only the FDS-overlay temperature matrix is a paper figure (Fig. S8); the
    # measurement-only variant has no counterpart in the paper and is not emitted.
    plot_temperature_profile_matrix(P.VAL_PLOTS, with_fds=True)
    print("-> temperature_matrix_3x3_fds.pdf")
    plot_temperature_heatmap_3x3(P.VAL_PLOTS, "F1")
    plot_temperature_heatmap_3x3(P.VAL_PLOTS, "F2")
    print("-> temperature_heatmap_{F1,F2}.pdf")


if __name__ == "__main__":
    main()
