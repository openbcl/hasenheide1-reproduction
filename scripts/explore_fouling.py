"""
Optics-fouling exploration: how much apparent extinction remains AFTER the room
is ventilated clear (smoke gone -> true k ~ 0)? Any residual k is the fouling
offset of the optics (LEM sender/receiver, SICK sender/receiver/mirror).

Reference: each device was cleaned BEFORE the test, so k(t~0) is the clean
baseline; the fouling residual = k(end, room clear) - k(t~0).

Note: cleaning was usually not logged as an event and sometimes
happened mid-measurement. Such interventions show up as ABRUPT STEPS in k(t):
  - step DOWN  -> optics cleaned (fouling removed)
  - step UP    -> optics / beam path suddenly obscured
We detect both (any abrupt jump that stands out from the smooth smoke dynamics),
so the end residual can be read with care (use the value just before a late
step, flag affected runs).

Read-only w.r.t. the raw records. Despite the ``explore_`` name this is a
DATA-STAGE reducer: it writes committed paper CSVs -- results/measurement/fouling_residuals.csv
(the fouling term of the uncertainty budget) and results/measurement/fouling/fig_{curves,meta}.csv
(rendered by plot_fouling.py into the paper figure) -- alongside exploratory PNGs
in plots/exploratory/fouling/ (gitignored).
"""
import re
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import measurement_io as mio
from paths import SUB_PROCESSED, PLOTS_DIR
from plot_style import set_plot_style, figsize_single
set_plot_style(font_size=11)

# use the locally re-processed, UN-clipped records (scripts/reprocess_unclipped.py)
base_path = Path(__file__).resolve().parent.parent / "data" / "reprocessed"

SERIES = {
    "075 (160 mm, 75 g)":  ["Hep_160_S2_R1", "Hep_160_S2_R2", "Hep_160_S2_R3",
                            "Hep_160_S3_R1", "Hep_160_S3_R2",
                            "Hep_160_S4_R1", "Hep_160_S4_R2"],
    "150 (160 mm, 150 g)": ["Hep_160_S1_R1", "Hep_160_S1_R2", "Hep_160_S1_R3"],
    "220 (220 mm, 300 g)": ["Hep_220_S1_R1", "Hep_220_S1_R2",
                            "Hep_220_S1_R3", "Hep_220_S1_R4"],
}
RUNS = [r for v in SERIES.values() for r in v]
RUN2SERIES = {r: s for s, v in SERIES.items() for r in v}
T_START, T_END = -60, 3600   # generous; real record end is detected from the data

# step detection (post-ventilation quiet phase only; smoke-phase fluctuations
# are not cleaning). Cleaning was never earlier than vent+5 min; the person
# crossing the beam is at vent start.
W = 3              # s, short window over which an abrupt step completes
BURST_THRESH = 0.5 # 1/m, |jump| identifying a cleaning burst (beam blocked/freed)
STEP_FROM = 300    # s after vent: cleaning was never earlier than vent+5 min;
#                    this also skips the (longer) smoke-clearing turbulence of
#                    the bigger fires.
END_CLIP = 30      # s, ignore the very end (device shutdown transients)
MASK_ABOVE = 10.0  # 1/m, mask only the device-shutdown spikes (k->14.2 at T->0);
#                    keep real dense-smoke extinction of the big fires
# fouling-residual window: the LATE plateau, once smoke has fully cleared but
# before device shutdown (cleaning, if any, shows as a step and is handled).
RESID_AFTER_VENT = 450   # s after vent (075: from 1350 s)
RESID_END_PAD = 40       # s before record end


def device_cols(df):
    lem = [c for c in df.columns
           if re.match(r"Extinction LEM_.*\(1/m\)$", c)]
    sick = [c for c in df.columns
            if re.match(r"Extinction SICK_.*\(1/m\)_corr$", c)]
    return lem + sick


def short_label(col):
    m = re.search(r"(LEM|SICK)_\d?_?([A-Z0-9]+_[0-9.]+)", col)
    return col.replace("Extinction ", "").replace(" (1/m)", "").replace("_corr", "")


def detect_cleaning(t, k, t_from, t_to):
    """Cleaning = wiping the optics -> the beam is repeatedly blocked/freed ->
    large k oscillations (|jump| > BURST_THRESH over a few s). Return the
    (start, end) time of that burst for t in [t_from, t_to], or None. The very
    end (device shutdown) is excluded via t_to."""
    d = np.full_like(k, np.nan)
    d[W:] = k[W:] - k[:-W]
    big = (np.abs(d) > BURST_THRESH) & (t >= t_from) & (t <= t_to) & ~np.isnan(d)
    if not big.any():
        return None
    idx = np.where(big)[0]
    return float(t[idx[0]]), float(t[idx[-1]])


def fouling_of(t, k, vt, t_max):
    """Fouling residual = plateau AFTER smoke clears but BEFORE any cleaning.
    The input k is ALREADY referenced to the clean t=0 state (load_runs zeroes
    every sensor column at the t=0 sample), so the residual is the plateau
    itself -- no further baseline subtraction (that would only re-add the
    +/-0.005 noise between the t=0 sample and the [-30,0] median). post = level
    after cleaning (should be ~0). Returns None if the device is absent."""
    k = np.asarray(k, float).copy()
    k[np.abs(k) > MASK_ABOVE] = np.nan                   # mask shutdown spikes
    if np.all(np.isnan(k)):
        return None
    clean = detect_cleaning(t, k, vt + STEP_FROM, t_max - END_CLIP)
    cw_lo = vt + RESID_AFTER_VENT
    cw_hi = (clean[0] - 20) if clean else (t_max - RESID_END_PAD)
    if cw_hi <= cw_lo:                                   # cleaning very early
        cw_lo = max(vt + 120, cw_hi - 180)
    cw = (t >= cw_lo) & (t <= cw_hi)
    resid = float(np.nanmedian(k[cw]))
    post = np.nan
    if clean:
        pc = (t >= clean[1] + 20) & (t <= t_max - END_CLIP)
        if pc.sum() > 5:
            post = float(np.nanmedian(k[pc]))
    return dict(k=k, b0=0.0, resid=resid, post=post, clean=clean,
                cw_lo=cw_lo, cw_hi=cw_hi)


print("Loading full records (incl. post-ventilation) ...")
exp, dur, vent = mio.load_runs(base_path, RUNS, T_START, T_END, SUB_PROCESSED)

out = PLOTS_DIR / "exploratory" / "fouling"
out.mkdir(parents=True, exist_ok=True)

print("\n=== Fouling residual (late plateau) + post-vent abrupt steps ===")
summary = []
_cur_series = None
for run in RUNS:
    df = exp.get(run)
    if df is None:
        continue
    if RUN2SERIES[run] != _cur_series:
        _cur_series = RUN2SERIES[run]
        print(f"\n################  SERIES {_cur_series}  ################")
    t = df['Time (s)'].values.astype(float)
    vt = vent.get(run, np.nan)
    cols = device_cols(df)

    # actual record end = last time with real data (the grid runs to T_END and
    # is NaN-padded beyond the record; np.nanmax(t) would give T_END, not the end)
    t_max = -np.inf
    for c in cols:
        kk = pd.to_numeric(df[c], errors='coerce').to_numpy(dtype=float, copy=True)
        kk[np.abs(kk) > MASK_ABOVE] = np.nan
        v = ~np.isnan(kk)
        if v.any():
            t_max = max(t_max, t[v].max())
    fig, ax = plt.subplots(figsize=figsize_single(aspect=0.5))
    print(f"\n{run}  (vent={vt:.0f}s, record ends {t_max:.0f}s)")
    pre_vals, n_cleaned, run_info = [], 0, []
    for c in cols:
        fo = fouling_of(t, pd.to_numeric(df[c], errors='coerce').values, vt, t_max)
        if fo is None:
            continue                                     # device not deployed
        k, b0, resid, post = fo['k'], fo['b0'], fo['resid'], fo['post']
        clean, cw_lo, cw_hi = fo['clean'], fo['cw_lo'], fo['cw_hi']

        lbl = short_label(c)
        ln, = ax.plot(t, k, lw=0.8, label=lbl)
        if clean:
            ax.axvspan(clean[0], clean[1], color=ln.get_color(), alpha=0.15)
            n_cleaned += 1
        pre_vals.append(k[(t >= 0) & (t <= vt)])
        # mark the fouling level with a dotted line at the pre-clean plateau;
        # the exact read-off values go into the table (rendered after the loop)
        lvl = resid + b0
        ax.plot([cw_lo, cw_hi], [lvl, lvl], color=ln.get_color(), ls=':', lw=1.4, zorder=4)
        run_info.append((lbl, ln.get_color(), resid, post, bool(clean)))
        clean_str = (f"CLEANED {clean[0]:.0f}-{clean[1]:.0f}s, post-clean={post:+.4f}"
                     if clean else "no in-record cleaning")
        print(f"   {lbl:18s} fouling={resid:+.4f} | {clean_str}")
        summary.append((run, lbl, b0, resid, post, bool(clean)))

    # clip y so the smoke peak + the small fouling plateau are visible; the
    # cleaning bursts shoot off-scale and are marked by the shaded bands.
    allpre = np.concatenate(pre_vals) if pre_vals else np.array([np.nan])
    speak = np.nanpercentile(allpre, 99.5) if np.isfinite(np.nanmax(allpre)) else 0.5
    ymax = max(0.2, 1.2 * speak)
    ax.set_ylim(-0.02, ymax)
    ax.axhline(0, color='0.7', lw=0.6)
    if not np.isnan(vt):
        ax.axvline(vt, color='C7', ls='--', lw=0.8)
        ax.text(vt, ymax, ' vent', color='C7', fontsize=7, va='top')
    # read-off value table (colored per device, white-backed so it stays legible
    # over the off-scale cleaning spikes) in the upper-right area
    _bb = dict(facecolor='white', alpha=0.75, edgecolor='none', pad=0.4)
    hdr = r'fouling' + (r' $\to$ post-wipe' if n_cleaned else '') + ' (1/m):'
    ax.text(0.67, 0.96, hdr, transform=ax.transAxes, ha='left', va='top',
            fontsize=6, color='0.3', bbox=_bb, zorder=8)
    yy = 0.87
    for (rl, rc, rr, rp, rcl) in run_info:
        tl = re.sub(r'^LEM_\d_', '', re.sub(r'^SICK_', 'SICK ', rl))
        s = f"{tl}: {rr:+.3f}" + (f" $\\to$ {rp:+.3f}" if (rcl and not np.isnan(rp)) else "")
        ax.text(0.67, yy, s, transform=ax.transAxes, color=rc, fontsize=6,
                va='top', ha='left', fontweight='bold', bbox=_bb, zorder=8)
        yy -= 0.10
    if n_cleaned:
        ax.text(0.005, 0.04, r'shaded = optics wiped ($k\to 0$ after)',
                transform=ax.transAxes, ha='left', va='bottom', fontsize=6,
                color='0.3', bbox=_bb)
    ax.set_title(f"{run}  —  {RUN2SERIES[run]};  fouling = pre-clean plateau (1/m)",
                 fontsize=8)
    ax.set_xlabel(r"$t$ / \si{\second}")
    ax.set_ylabel(r"$k$ / \si{\per\metre}")
    ax.legend(fontsize=5.5, ncol=2, frameon=False, loc='upper left')
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / f"fouling_{run}.png", dpi=150, bbox_inches='tight')
    plt.close(fig)

print(f"\nPlots -> {out}")

# committed reduced CSV: line-of-sight fouling residuals
import paths as _PATHS  # noqa: E402
_PATHS.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
pd.DataFrame(summary, columns=["run", "device", "baseline", "fouling_resid_1pm",
                               "post_wipe_1pm", "cleaned"]).to_csv(
    _PATHS.RESULTS_DIR / "measurement" / "fouling_residuals.csv", index=False, lineterminator="\n")
print(f"-> {_PATHS.RESULTS_DIR / 'measurement' / 'fouling_residuals.csv'}")


def dump_paper_figure_data():
    """Reduce the optics-fouling paper figure to committed CSVs: the full k(t)
    curves of the two plotted runs (per device) plus the per-device read-off
    metadata (residual, post-wipe, cleaning window, residual-window, vent). The
    committed plotter (plot_fouling.py) renders optics_fouling.pdf from these with
    no drive. The data computation matches the per-device fouling read-off used in
    the Supplementary Material figure (now rendered by plot_fouling.py)."""
    import paths as _P
    sel = ["Hep_220_S1_R2", "Hep_160_S1_R3"]
    crows, mrows = [], []
    for run in sel:
        df = exp[run]
        vt = vent.get(run, np.nan)
        t = df['Time (s)'].values.astype(float)
        cols = device_cols(df)
        t_max = -np.inf
        for c in cols:
            kk = np.array(pd.to_numeric(df[c], errors='coerce').values, float)
            kk[np.abs(kk) > MASK_ABOVE] = np.nan
            if np.isfinite(kk).any():
                t_max = max(t_max, t[np.isfinite(kk)].max())
        ci = 0
        for c in cols:
            fo = fouling_of(t, pd.to_numeric(df[c], errors='coerce').values, vt, t_max)
            if fo is None:
                continue
            k, resid, post, clean = fo['k'], fo['resid'], fo['post'], fo['clean']
            lbl = re.sub(r'(F\d)_([\d.]+)', r'\1, \2 m',
                         re.sub(r'^LEM_\d_', '', re.sub(r'^SICK_', 'SICK ', short_label(c))))
            crows.append(pd.DataFrame({"run": run, "device": c, "t_s": t, "k": k}))
            mrows.append(dict(run=run, device=c, dev_order=ci, label=lbl,
                              resid=resid, post=post,
                              clean_lo=(clean[0] if clean else np.nan),
                              clean_hi=(clean[1] if clean else np.nan),
                              cw_lo=fo['cw_lo'], cw_hi=fo['cw_hi'], vt=vt))
            ci += 1
    cdf = pd.concat(crows, ignore_index=True)
    mdf = pd.DataFrame(mrows)
    d = _P.RESULTS_DIR / "measurement" / "fouling"
    d.mkdir(parents=True, exist_ok=True)
    cdf.to_csv(d / "fig_curves.csv", index=False, lineterminator="\n")
    mdf.to_csv(d / "fig_meta.csv", index=False, lineterminator="\n")
    rb = pd.read_csv(d / "fig_curves.csv", float_precision="round_trip")
    assert np.array_equal(cdf["t_s"].to_numpy(float), rb["t_s"].to_numpy(float), equal_nan=True)
    assert np.array_equal(cdf["k"].to_numpy(float), rb["k"].to_numpy(float), equal_nan=True)
    print(f"-> {d / 'fig_curves.csv'} ({len(cdf)} rows), {d / 'fig_meta.csv'} ({len(mdf)} rows)")


dump_paper_figure_data()
