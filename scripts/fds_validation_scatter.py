"""FDS-Validation-Guide-style scatter plot and model uncertainty (delta, sigma_M).

Pools the peak values (greatest rise above ambient) of all sensors and all
three test series from the committed per-series ``metrics_report.csv`` files
(results/validation/fds_metrics/) and evaluates, separately for temperature
rise and light extinction, the model bias factor delta and the model relative
standard deviation sigma_M following the FDS Validation Guide methodology
(McGrattan & Toman; Error chapter):

    Var[ln(M/E)] ~ sigma_M^2 + sigma_E^2
    delta        ~ exp( mean[ln(M/E)] + sigma_M^2/2 - sigma_E^2/2 )
    constraint     sigma_M >= sigma_E

The experimental relative uncertainties sigma_E are taken from the paper's
uncertainty budget (light extinction: the line-of-sight measurement budget of the
Supplementary Material section "Measurement uncertainty of the extinction coefficient"; the measured-input
uncertainty is systematic and rides on delta, not on sigma_E) and the Guide
thermocouple value for temperature (single source: guide_stats.SIGMA_E). Unlike the Guide, no
density-weighted regressogram is applied to the mean (point counts here are
small and reasonably spread).

Output: the paper scatter figure (plots/validation/fds_validation_scatter.pdf) + the pooled
and per-series guide statistics (results/validation/fds_metrics/guide_{pooled,series}.csv),
plus a console summary. Reads only the committed metrics.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_style import (  # noqa: E402
    set_plot_style, figsize_single, SERIES_LABEL, SERIES_MARKER, SERIES_COLOR,
)
from guide_stats import guide_delta_sigma, SIGMA_E  # noqa: E402
import paths as P  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = P.FDS_METRICS_DIR                            # committed metric CSVs (input)

SERIES = ("hep_160_075", "hep_160_150", "hep_220_300")
# SERIES_LABEL / SERIES_MARKER live in plot_style.py (single source for the
# series styling).

# The SICK points are co-located with LEM points and compare against the same
# FDS device column; including them would double-count those measurement
# locations (Guide statistics count each point-to-point comparison once).
# The pooled statistics change little either way (at sigma_E=0.08, on the
# committed pairs: delta_k 1.0985 (n=14) -> 1.0918 (n=18), a 0.61 % shift).
INCLUDE_SICK = False

# SIGMA_E (per-quantity experimental sigma_E) is the single source in
# guide_stats.py; the run-to-run scatter in layer_metrics.csv (SigmaE_rel) is
# kept for reference but is scenario/reduction variability, not the measurement
# sigma_E.

# Signal floor on the measured peak: points below are within instrument
# accuracy/drift (type-K over ~20 min ~ 1 K) and their log ratios are noise
# that would dominate the statistics (the two excluded temperature points
# have dT = 0.23/0.85 K with M/E = 3.9/2.9).
SIGNAL_MIN = {"Temperature": 1.0, "Upper-layer T": 1.0, "Layer height": 0.0,
              "Extinction": 0.02}
GROUP_AXIS = {
    "Temperature": r"peak $\Delta T$ / \si{\celsius}",
    "Upper-layer T": r"peak $\Delta T_u$ / \si{\celsius}",
    "Layer height": r"min $z_\mathrm{int}$ / \si{\meter}",
    "Extinction": r"peak $k$ / \si{\per\meter}",
}

# Bias-factor symbol per quantity, matching the paper's text notation.
GROUP_DELTA = {
    "Temperature": r"\delta_T",
    "Upper-layer T": r"\delta_{T_u}",
    "Layer height": r"\delta_z",
    "Extinction": r"\delta_k",
}


def load_points() -> pd.DataFrame:
    frames, layer = [], []
    for s in SERIES:
        d = SRC_DIR / f"_Simulation_Comparison_{s}_ysmatched"
        f = d / "metrics_report.csv"
        if f.exists():
            df = pd.read_csv(f); df["Series"] = s; frames.append(df)
        else:
            print(f"missing committed metrics file for {s}: {f}")
        lf = d / "layer_metrics.csv"            # upper-layer T + layer height
        if lf.exists():
            layer.append(pd.read_csv(lf))
    df = pd.concat(frames, ignore_index=True)
    df["Group"] = np.where(df["Unit"].str.contains("°"), "Temperature", "Extinction")
    if not INCLUDE_SICK:
        df = df[~df["Sensor"].str.contains("SICK")]
    if layer:
        ldf = pd.concat(layer, ignore_index=True)
        ldf["Group"] = ldf["Quantity"]
        df = pd.concat([df, ldf], ignore_index=True)
    df = df[np.isfinite(df["Peak_exp"]) & np.isfinite(df["Peak_sim"])
            & (df["Peak_exp"] > 0) & (df["Peak_sim"] > 0)]
    return df


def guide_stats(measured: np.ndarray, predicted: np.ndarray,
                sigma_e: float) -> dict:
    """delta and sigma_M from ln(M/E) following the Validation Guide.

    Thin wrapper over the shared guide_stats.guide_delta_sigma helper."""
    return guide_delta_sigma(np.log(predicted / measured), sigma_e)


def main() -> None:
    set_plot_style(
        preamble_path=Path(__file__).resolve().parent / "plot_preamble.tex",
        font_size=10,  # one point below the single-panel figures: keeps the
        #                labels from crowding the small sub-panels of this dense
        #                three-panel layout (the tornado uses 10 for the same reason)
    )
    df = load_points()

    ALL_GROUPS = ("Temperature", "Upper-layer T", "Layer height", "Extinction")
    # Plot the two hazard-relevant Validation-Guide quantities: extinction and the
    # Janssens-Tran upper-layer temperature. The per-thermocouple bulk "Temperature"
    # group is still pooled (-> guide_pooled.csv) but not plotted, as it is inflated
    # by near-ambient/interface sensors (small-denominator artefact; see Discussion).
    PLOT_GROUPS = ("Extinction", "Upper-layer T", "Layer height")

    # Statistics for every quantity (-> guide_pooled.csv / numbers.tex); the three
    # in PLOT_GROUPS are also shown. The layer (interface) height is a length rather
    # than an intensity, but the Guide reports it as a validation quantity in the
    # same delta/sigma_M form, and its bias is quoted in the abstract -- so it is
    # plotted rather than left as a bare number with no visible support.
    print(f"{'group':<14} {'n':>4} {'delta':>7} {'sigma_M':>8} {'sigma_E':>8}  note")
    pooled_rows, stats, gsel = [], {}, {}
    for group in ALL_GROUPS:
        g = df[(df["Group"] == group) & (df["Peak_exp"] >= SIGNAL_MIN[group])]
        sigma_e = SIGMA_E[group]
        st = guide_stats(g["Peak_exp"].to_numpy(), g["Peak_sim"].to_numpy(), sigma_e)
        note = "sigma_M at floor (not resolved from data)" if st["floored"] else ""
        print(f"{group:<14} {st['n']:>4} {st['delta']:>7.2f} "
              f"{st['sigma_M']:>8.2f} {sigma_e:>8.2f}  {note}")
        pooled_rows.append({"Group": group, "n": st["n"], "delta": st["delta"],
                            "sigma_M": st["sigma_M"], "sigma_E": sigma_e,
                            "floored": st["floored"]})
        stats[group], gsel[group] = (st, sigma_e), g

    # Figure: extinction, upper-layer temperature rise, layer height.
    fig, axes = plt.subplots(
        1, len(PLOT_GROUPS),
        # Panels are square (set_aspect("equal")); at 0.40 aspect they were
        # shrunk to fit the short canvas, so the (consistent, unchanged) font
        # dominated. A taller canvas lets the squares grow width-limited instead.
        figsize=(figsize_single()[0], figsize_single()[0] * 0.52),
    )
    axes = np.atleast_1d(axes)
    for ax, group in zip(axes, PLOT_GROUPS):
        g = gsel[group]
        st, sigma_e = stats[group]

        # Layer (interface) height is a length spanning a narrow linear range,
        # where a log axis just compresses the points onto "1"; the intensity
        # quantities (extinction, upper-layer T) span decades -> log-log.
        is_log = group != "Layer height"
        plot = ax.loglog if is_log else ax.plot

        # Defensive overlay: the full per-thermocouple temperature comparison
        # (all tree heights, incl. the noisy near-ambient/interface sensors)
        # shown faintly behind the hazard-relevant Janssens-Tran upper-layer
        # subset, so the tighter upper-layer statistic is not read as cherry-picked.
        extra = gsel["Temperature"] if group == "Upper-layer T" else None
        if extra is not None:
            dT = stats["Temperature"][0]["delta"]
            ax.loglog(extra["Peak_exp"], extra["Peak_sim"], "o", ms=2.2,
                      mfc="0.78", mec="0.6", mew=0.3, alpha=0.5, zorder=3,
                      label=rf"all thermocouples ($\delta_T = {dT:.2f}$)")

        # scatter on top of the reference/bias lines (zorder=5 vs. 1/2); colours
        # are set explicitly from SERIES_COLOR (not the cycle) so the faint cloud
        # above cannot shift them
        for s in SERIES:
            sel = g[g["Series"] == s]
            plot(sel["Peak_exp"], sel["Peak_sim"], SERIES_MARKER[s],
                 color=SERIES_COLOR[s], ms=4, mfc="none",
                 label=SERIES_LABEL[s], zorder=5)

        # Flag the single most-discrepant extinction pair -- the smallest fire's
        # lower-layer F2 sensor at z=1.5 m -- discussed in the text as the
        # interface / lower-layer over-filling signal.
        if group == "Extinction":
            rr = g["Peak_sim"].to_numpy() / g["Peak_exp"].to_numpy()
            j = int(np.argmax(rr))
            ax.annotate(r"F2, $z=1.5$ m",
                        xy=(g["Peak_exp"].to_numpy()[j], g["Peak_sim"].to_numpy()[j]),
                        xycoords="data",
                        xytext=(0.04, 0.72), textcoords="axes fraction",
                        fontsize=6, ha="left", va="center", zorder=6, color="0.3",
                        arrowprops=dict(arrowstyle="->", lw=0.5, color="0.5",
                                        connectionstyle="arc3,rad=0.25",
                                        shrinkA=2, shrinkB=3))

        dmin = min(g["Peak_exp"].min(), g["Peak_sim"].min())
        dmax = max(g["Peak_exp"].max(), g["Peak_sim"].max())
        if is_log:
            lo, hi = 0.7 * dmin, 1.5 * dmax          # multiplicative margin reads well in decades
        else:
            pad = 0.4 * (dmax - dmin)                # additive margin for the narrow linear range
            lo, hi = round(dmin - pad, 1), round(dmax + pad, 1)   # snap to full 0.1 (e.g. 0.9, 1.3)
        if group == "Extinction":
            lo, hi = 0.1, 1.4                         # round low; hi keeps the top pair (sim 1.22)
        if extra is not None:
            # fixed frame for the temperature panel: show the faint cloud's
            # near-ambient tail without fully widening to its highest sim
            # outliers, so the hazard-relevant upper-layer stays prominent
            lo, hi = 1.0, 100.0
        x = np.array([lo, hi])
        ax.plot(x, x, "k-", lw=0.6, zorder=1)
        ax.plot(x, x * np.exp(2 * sigma_e), "k--", lw=0.45, zorder=1)
        ax.plot(x, x * np.exp(-2 * sigma_e), "k--", lw=0.45, zorder=1)
        d, sm = st["delta"], st["sigma_M"]
        ax.plot(x, d * x, "r-", lw=0.65, zorder=2)
        # sigma_M band dotted (sigma_E band dashed): the two stay distinct in
        # greyscale print, where red and black differ only slightly in tone
        ax.plot(x, d * x * np.exp(2 * sm), "r:", lw=0.8, zorder=2)
        ax.plot(x, d * x * np.exp(-2 * sm), "r:", lw=0.8, zorder=2)

        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        ax.set_aspect("equal")
        if not is_log:
            # square panel -> identical ticks on both axes (0.2 steps: 1.0, 1.2)
            t = np.round(np.arange(np.ceil(lo / 0.2) * 0.2, hi + 1e-9, 0.2), 1)
            ax.set_xticks(t)
            ax.set_yticks(t)
        ax.set_xlabel("measured " + GROUP_AXIS[group])
        ax.set_ylabel("predicted " + GROUP_AXIS[group])
        # Two lines: at three panels the one-line form runs into its neighbours.
        ax.set_title(
            rf"${GROUP_DELTA[group]} = {d:.2f}$, $\sigma_M = {sm:.2f}$" "\n"
            rf"$\sigma_E = {sigma_e:.2f}$ ($n = {st['n']}$)")
        ax.grid(True, which="both", alpha=0.2)

    # one shared series legend below all three panels (the markers are common);
    # fontsize inherits the style hierarchy (legend = font_size - 1)
    handles, labels = axes[0].get_legend_handles_labels()
    for ax_ in axes:                       # append the faint per-thermocouple proxy
        for h, l in zip(*ax_.get_legend_handles_labels()):
            if l.startswith("all thermocouples") and l not in labels:
                handles.append(h)
                labels.append(l)
    fig.tight_layout(rect=(0, 0.11, 1, 1))
    # legend sits just under the panels (small, even gap) rather than pinned to
    # the very bottom edge with a large void above it
    fig.legend(handles, labels, loc="lower center", ncol=len(handles),
               frameon=False, bbox_to_anchor=(0.5, 0.085),
               columnspacing=0.7, handletextpad=0.25)
    paper_pdf = REPO_ROOT / "plots" / "validation" / "fds_validation_scatter.pdf"
    paper_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(paper_pdf)
    print(f"paper figure: {paper_pdf}")

    # pooled FDS Validation-Guide statistics (the figure's delta/sigma_M) ->
    # committed CSV (a source for the paper's reported numbers).
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(pooled_rows).to_csv(SRC_DIR / "guide_pooled.csv", index=False,
                                     lineterminator="\n")
    print(f"pooled guide stats: {SRC_DIR / 'guide_pooled.csv'}")

    # Per-series extinction bias (M1 configuration-matched baseline): each series
    # is simulated at its own furniture-calorimeter soot yield, so delta_k resolves
    # per series. The between-series scatter of the three delta_k is the residual
    # configuration bias NOT removed by matching; its standard uncertainty on the
    # pooled bias (SD/sqrt(n_series)) is the empirical, data-driven band that
    # replaces the earlier ad-hoc "soot-loading systematic" estimate. K_m and
    # chi_r are shared across series (systematic, common), so they do not enter
    # this between-series term but are carried as the residual-K_m bracket in prose.
    ext = df[(df["Group"] == "Extinction") & (df["Peak_exp"] >= SIGNAL_MIN["Extinction"])]
    se = SIGMA_E["Extinction"]
    srows = []
    for s in SERIES:
        g = ext[ext["Series"] == s]
        st = guide_stats(g["Peak_exp"].to_numpy(), g["Peak_sim"].to_numpy(), se)
        srows.append({"Series": s, "n": st["n"], "delta": st["delta"],
                      "sigma_M": st["sigma_M"]})
    sdf = pd.DataFrame(srows)
    sdf.to_csv(SRC_DIR / "guide_series.csv", index=False, lineterminator="\n")
    d3 = sdf["delta"].to_numpy()
    between_sd = float(np.std(d3, ddof=1))
    print(f"per-series extinction delta_k: "
          f"{', '.join(f'{r.Series}={r.delta:.3f}' for r in sdf.itertuples())}; "
          f"span {(d3.max()-d3.min())*100:.1f} pp, between-series SD {between_sd:.3f} "
          f"-> pooled-bias u {between_sd/np.sqrt(len(d3)):.3f}")
    print(f"per-series guide stats: {SRC_DIR / 'guide_series.csv'}")


if __name__ == "__main__":
    main()
