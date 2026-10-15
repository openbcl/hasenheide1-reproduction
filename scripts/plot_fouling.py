"""Optics-fouling Supplementary Material figure (figures stage, committed).

Renders the two-panel optics-fouling figure (plots/measurement/optics_fouling.pdf)
from the committed reduced curves results/measurement/fouling/fig_curves.csv +
fig_meta.csv (written by explore_fouling.py's dump_paper_figure_data), so it
regenerates without the raw measurement data. The drawing is a faithful transcription
of the original explore_fouling paper-figure routine and is verified
byte-identical against the committed reference. Curves are read with
float_precision='round_trip'.

Run:  python scripts/plot_fouling.py
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

from plot_style import set_plot_style, figsize_single
import paths as P

set_plot_style(font_size=11)

SEL = [("Hep_220_S1_R2", r"(a)\ \textit{Hep\_220\_300} (300 g, worst case)"),
       ("Hep_160_S1_R3", r"(b)\ \textit{Hep\_160\_150} (150 g)")]
XCFG = [(1150, 300, 2500),       # (a) 220: xmin, tick spacing, xmax
        (1100, 600, 3800)]       # (b) 150 (longer record)


# Room colours as in Figure 1 and Figure 7 (F1 C0, F2 C1, F3 C2). The second F2
# sensor (1.5 m) is set apart by a dashed plateau line and a light orange (distinct
# from every other sensor also in greyscale; its inset label in a stronger orange
# for legibility).
ROOM_COL = {"F1": "C0", "F2": "C1", "F3": "C2"}


def _style(label):
    """(data colour, label colour, plateau linestyle)."""
    room, height = [s.strip() for s in label.split(",")]
    if room == "F2" and height.startswith("1.5"):
        return "#fdae6b", "#e6550d", "--"
    return ROOM_COL[room], ROOM_COL[room], ":"


def main() -> None:
    d = P.RESULTS_DIR / "measurement" / "fouling"
    curves = pd.read_csv(d / "fig_curves.csv", float_precision="round_trip")
    meta = pd.read_csv(d / "fig_meta.csv", float_precision="round_trip")

    w, _ = figsize_single(aspect=1.0)
    fig, axes = plt.subplots(2, 1, figsize=(w, 0.9 * w))
    _bb = dict(facecolor='white', alpha=0.9, edgecolor='none', pad=0.5)
    FS = 6.5

    for (ax, (run, panel)), (xmin, xtick, xmax) in zip(zip(axes, SEL), XCFG):
        m = meta[meta['run'] == run].sort_values('dev_order')
        vt = float(m['vt'].iloc[0])
        info = []
        for _, r in m.iterrows():
            g = curves[(curves['run'] == run) & (curves['device'] == r['device'])]
            t = g['t_s'].to_numpy(float)
            k = g['k'].to_numpy(float)
            resid, post = r['resid'], r['post']
            clean = not np.isnan(r['clean_lo'])
            col, tcol, lsr = _style(r['label'])
            k_plot = k.copy()
            if clean:
                ax.axvspan(r['clean_lo'], r['clean_hi'], color=col, alpha=0.15)
                k_plot[(t >= r['clean_lo']) & (t <= r['clean_hi'])] = np.nan
            ax.scatter(t, k_plot, s=3, color=col, alpha=0.4, edgecolor='none',
                       zorder=3, rasterized=True)
            ax.plot([r['cw_lo'], r['cw_hi']], [resid] * 2,
                    color=col, ls=lsr, lw=1.4, zorder=4)
            info.append((r['label'], tcol, resid, post, bool(clean)))
        ymax = max(0.06, 2.5 * max(i[2] for i in info))
        ax.set_ylim(-0.01, ymax)
        ax.set_xlim(xmin, xmax)
        ax.xaxis.set_major_locator(MultipleLocator(xtick))
        ax.axhline(0, color='0.7', lw=0.6)
        ax.axvline(vt, color='C7', ls='--', lw=0.8)
        ax.text(vt, ymax * 0.99, 'vent', rotation=90, ha='right', va='top',
                fontsize=FS, color='C7')
        hdr = (r'fouling $\to$ post-wipe (\si{\per\meter}):' if any(i[4] for i in info)
               else r'fouling (\si{\per\meter}):')
        ax.text(0.655, 0.96, hdr, transform=ax.transAxes, ha='left', va='top',
                fontsize=FS, color='0.3', bbox=_bb, zorder=8)
        yy = 0.85
        for (rl, rc, rr, rp, rcl) in info:
            s = f"{rl}: {rr:+.3f}" + (f" $\\to$ {rp:+.3f}" if (rcl and not np.isnan(rp)) else "")
            ax.text(0.655, yy, s, transform=ax.transAxes, color=rc, fontsize=FS,
                    va='top', ha='left', fontweight='bold', bbox=_bb, zorder=8)
            yy -= 0.115
        ax.set_title(panel, fontsize=8, loc='left')
        ax.set_ylabel(r"$k$ / \si{\per\metre}")
        ax.grid(True, alpha=0.25)
    axes[-1].set_xlabel(r"$t$ / \si{\second}")
    fig.tight_layout()
    pdir = P.PLOTS_DIR / "measurement"
    pdir.mkdir(parents=True, exist_ok=True)
    target = pdir / "optics_fouling.pdf"
    fig.savefig(target, bbox_inches='tight')
    plt.close(fig)
    print(f"-> {target}")


if __name__ == "__main__":
    main()
