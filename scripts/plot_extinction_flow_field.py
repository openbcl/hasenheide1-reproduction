#!/usr/bin/env python
"""Extinction-field + velocity flow/transport figures for the Supplementary.

One figure per baseline fire (75 g/160 mm, 150 g/160 mm, 300 g/220 mm). Each
figure stacks a plan view (horizontal K_z=2.0 m slice at t=100 s) above four
longitudinal sections (stepped y-z cut) at t = 100, 200, 300 and 600 s, with the
in-plane velocity field over-plotted as arrows. The stepped section follows
x=1.25 m through the fire and middle rooms (F1/F2) and x=0.55 m through the
corridor and downstream room (FC/F3) so it passes through every doorway; the
step is at the F2->FC wall (y=7.7 m) and is marked in both panels.

Data flow (mirrors the reduce -> plot split of the matrix figures): the heavy
fdsreader extraction from the FDS output tree is done once and cached as reduced
per-(fire, time) arrays under results/simulation/flow_field/ (committed, ~3.5 MB); the
figure then renders from those, so it regenerates without the FDS output tree.
Delete results/simulation/flow_field/ to force a re-extraction (requires the FDS output tree
at HASENHEIDE_FDS_ROOT).

Velocity vectors come from the VECTOR=T slices: fdsreader exposes the in-plane
components per sub-slice as ``subslice.vector_data`` -> {'u','v','w'}; 'v' is the
y-component and 'w' the z-component of the section plane. The two x-planes are
interpolated onto one regular grid (split at the step) so the arrow spacing is
uniform. Arrows below VMIN are dropped as still-layer noise.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.colors as mcolors
from scipy.interpolate import griddata

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_style import set_plot_style, save_pdf  # noqa: E402
import paths as P  # noqa: E402

REDUCED = Path(__file__).resolve().parent.parent / "results" / "simulation" / "flow_field"
PLOTS = Path(__file__).resolve().parent.parent / "plots" / "simulation"

YSTEP = 7.7          # F2 -> FC wall: section steps x=1.25 -> x=0.55 here
VMIN = 0.15          # m/s; arrows slower than this are hidden (still-layer noise)
GEO = "#1E90FF"      # dodgerblue: unified section-plane marking
OBST_CMAP = mcolors.ListedColormap(["0.6"])   # solid grey for masked obstruction (OBST) cells
TIMES = [100, 200, 300, 600]
# the two 160 mm-pan fires share a common colour scale for direct comparison;
# the 300 g (220 mm) fire is denser and keeps its own (per-99th-percentile) scale
VMAX = {"075": 0.7, "150": 0.7}
FIRES = [
    ("hep_160_075_ysmatched", "075", r"160\,mm, 75\,g"),
    ("hep_160_150_ysmatched", "150", r"160\,mm, 150\,g"),
    ("hep_220_300_ysmatched", "300", r"220\,mm, 300\,g"),
]


# --------------------------------------------------------------------------
# reduced-data extraction (only runs when results/simulation/flow_field/ is incomplete)
# --------------------------------------------------------------------------
def _rpath(tag, t):
    return REDUCED / f"ef_{tag}_t{int(t)}.npz"


def _plane(kx, vx):
    egx, gx = kx.to_global(masked=False, return_coordinates=True)
    egx_m = kx.to_global(masked=True, fill=np.nan)         # OBST cells -> nan (obstruction mask)
    y = np.asarray(gx['y']); z = np.asarray(gx['z']); tx = np.asarray(kx.times)
    subs = []
    for sub in vx.subslices:
        c = sub.get_coordinates()
        vd = sub.vector_data
        subs.append((np.asarray(c['y']), np.asarray(c['z']), vd['v'], vd['w']))
    return egx, egx_m, y, z, tx, subs, np.asarray(vx.times)


def _sec_at(egx, egx_m, y, z, tx, subs, tv, t):
    six = int(np.argmin(np.abs(tx - t)))
    K = egx[six] if egx[six].shape == (len(z), len(y)) else egx[six].T   # (z, y)
    Km = egx_m[six] if egx_m[six].shape == (len(z), len(y)) else egx_m[six].T
    obst = np.isnan(Km) & ~np.isnan(K)                                   # OBST cells (not no-data gaps)
    sixv = int(np.argmin(np.abs(tv - t)))
    yv, zv, vv, wv = [], [], [], []
    for yy, zz, V, W in subs:
        v = V[sixv]; w = W[sixv]
        if v.shape == (len(yy), len(zz)):
            v = v.T; w = w.T
        Yg, Zg = np.meshgrid(yy, zz)
        yv.append(Yg.ravel()); zv.append(Zg.ravel())
        vv.append(v.ravel()); wv.append(w.ravel())
    return (y, z, K, np.concatenate(yv), np.concatenate(zv),
            np.concatenate(vv), np.concatenate(wv), float(tx[six]), obst)


def extract(series, tag):
    """Extract the missing (series, time) reduced arrays from the FDS tree."""
    need = [t for t in TIMES if not _rpath(tag, t).exists()]
    if not need:
        return
    from fdsreader_patch import patch_fdsreader_3d_cell_centered
    patch_fdsreader_3d_cell_centered()
    import fdsreader
    print(f"extracting {series} (t={need}) from FDS tree ...")
    sim = fdsreader.Simulation(str(P.FDS_OUTPUT_ROOT / series))
    kz = [s for s in sim.slices if s.id == "K_z=2_00"][0]
    egz, gz = kz.to_global(masked=False, return_coordinates=True)
    egz_m = kz.to_global(masked=True, fill=np.nan)          # OBST cells -> nan
    xz = np.asarray(gz['x']); yz = np.asarray(gz['y']); tz = np.asarray(kz.times)
    p0 = _plane([s for s in sim.slices if s.id == "K_x=0_55"][0],
                [s for s in sim.slices if s.id == "VEL_x=0_55"][0])
    p1 = _plane([s for s in sim.slices if s.id == "K_x=1_25"][0],
                [s for s in sim.slices if s.id == "VEL_x=1_25"][0])
    REDUCED.mkdir(parents=True, exist_ok=True)
    for t in need:
        ti = int(np.argmin(np.abs(tz - t)))
        Kxy = egz[ti] if egz[ti].shape == (len(xz), len(yz)) else egz[ti].T
        Kxy_m = egz_m[ti] if egz_m[ti].shape == (len(xz), len(yz)) else egz_m[ti].T
        obstxy = np.isnan(Kxy_m) & ~np.isnan(Kxy)
        s0 = _sec_at(*p0, t)
        s1 = _sec_at(*p1, t)
        d = dict(x=xz, yP=yz, Kxy=Kxy, obstxy=obstxy, tsel=float(tz[ti]), tact=s1[7],
                 y0=s0[0], z0=s0[1], K0=s0[2], obst0=s0[8], yv0=s0[3], zv0=s0[4], vv0=s0[5], wv0=s0[6],
                 y1=s1[0], z1=s1[1], K1=s1[2], obst1=s1[8], yv1=s1[3], zv1=s1[4], vv1=s1[5], wv1=s1[6])
        d = {k: (v.astype(np.float32) if isinstance(v, np.ndarray) and v.dtype == np.float64 else v)
             for k, v in d.items()}
        np.savez_compressed(_rpath(tag, t), **d)
        print("  wrote", _rpath(tag, t).name)


# --------------------------------------------------------------------------
# figure
# --------------------------------------------------------------------------
def ceil_to(v, step):
    return float(np.ceil(v / step) * step)


def _section(ax, d, vmax):
    y0, z0, K0 = d['y0'], d['z0'], d['K0']
    y1, z1, K1 = d['y1'], d['z1'], d['K1']

    def masked(K, y, keep):
        Km = K.copy(); Km[:, ~keep] = np.nan; return Km
    pcm = ax.pcolormesh(y1, z1, masked(K1, y1, y1 < YSTEP), cmap="inferno",
                        shading="auto", vmin=0, vmax=vmax, rasterized=True)
    ax.pcolormesh(y0, z0, masked(K0, y0, y0 >= YSTEP), cmap="inferno",
                  shading="auto", vmin=0, vmax=vmax, rasterized=True)
    # masked obstruction (OBST) cells in grey, each plane only within its keep-region
    ax.pcolormesh(y1, z1, np.where(d['obst1'] & (y1 < YSTEP)[None, :], 1.0, np.nan),
                  cmap=OBST_CMAP, shading="auto", vmin=0, vmax=1, rasterized=True)
    ax.pcolormesh(y0, z0, np.where(d['obst0'] & (y0 >= YSTEP)[None, :], 1.0, np.nan),
                  cmap=OBST_CMAP, shading="auto", vmin=0, vmax=1, rasterized=True)

    ygr = np.arange(0.25, 14.5, 0.45); zgr = np.arange(0.15, 2.5, 0.22)
    YG, ZG = np.meshgrid(ygr, zgr)
    Vg = np.full(YG.shape, np.nan); Wg = np.full(YG.shape, np.nan)
    for yv, zv, vv, wv, reg in [
            (d['yv1'], d['zv1'], d['vv1'], d['wv1'], YG < YSTEP),
            (d['yv0'], d['zv0'], d['vv0'], d['wv0'], YG >= YSTEP)]:
        pts = np.column_stack([yv, zv])
        Vg[reg] = griddata(pts, vv, (YG, ZG), method="linear")[reg]
        Wg[reg] = griddata(pts, wv, (YG, ZG), method="linear")[reg]
    m = np.isfinite(Vg) & (np.hypot(Vg, Wg) >= VMIN)
    q = ax.quiver(YG[m], ZG[m], Vg[m], Wg[m], color="white", scale=22,
                  width=0.0032, alpha=0.95)
    q.set_path_effects([pe.withStroke(linewidth=0.7, foreground="black")])
    ax.axvline(YSTEP, color=GEO, lw=1.0, ls="--", alpha=0.9)
    ax.set_ylim(0, 2.55); ax.set_aspect("equal"); ax.set_yticks([0, 1, 2])
    ax.set_xlabel(""); ax.set_ylabel("")
    return pcm, q


def make_figure(tag, label):
    caches = {t: np.load(_rpath(tag, t)) for t in TIMES}
    Kall = np.concatenate(
        [np.concatenate([caches[t]['K0'].ravel(), caches[t]['K1'].ravel()]) for t in TIMES]
        + [caches[TIMES[0]]['Kxy'].ravel()])
    Kall = Kall[np.isfinite(Kall)]
    vmax = VMAX.get(tag, ceil_to(float(np.nanpercentile(Kall, 99)), 0.1))

    n = len(TIMES)
    dP = caches[TIMES[0]]
    xP, yP, Kxy = dP['x'], dP['yP'], dP['Kxy']
    xext = float(np.ptp(xP)); zext = 2.55
    fig = plt.figure(figsize=(6.8, 2.3 + 1.4 * n))
    gs = fig.add_gridspec(n + 1, 1, height_ratios=[xext] + [zext] * n, hspace=0.52)
    axP = fig.add_subplot(gs[0])
    axsec = [fig.add_subplot(gs[i + 1], sharex=axP) for i in range(n)]

    # plan view (z = 2.0 m), flipped on x=0
    pcmP = axP.pcolormesh(yP, xP, Kxy, cmap="inferno", shading="auto", vmin=0, vmax=vmax,
                          rasterized=True)
    axP.pcolormesh(yP, xP, np.where(dP['obstxy'], 1.0, np.nan), cmap=OBST_CMAP,
                   shading="auto", vmin=0, vmax=1, rasterized=True)
    axP.invert_yaxis()
    axP.plot([0, YSTEP], [1.25, 1.25], color=GEO, lw=1.0, ls="--")
    axP.plot([YSTEP, YSTEP], [1.25, 0.55], color=GEO, lw=1.0, ls="--")
    axP.plot([YSTEP, yP.max()], [0.55, 0.55], color=GEO, lw=1.0, ls="--")
    axP.text(0.2, 1.05, "section", color=GEO, fontsize=6.5, va="bottom")
    for lbl, yc, xc in [("F1", 2.0, 3.7), ("F2", 6.0, 3.7),
                        ("FC", 9.4, 0.55), ("F3", 13.0, 3.7)]:
        axP.text(yc, xc, lbl, color="white", fontsize=8, fontweight="bold", ha="center")
    axP.set_aspect("equal"); axP.set_yticks([0, 2, 4])
    axP.set_xlabel(""); axP.set_ylabel("")
    axP.tick_params(labelbottom=False)   # shared x-axis: only the bottom panel labels x
    axP.set_title(r"%s -- plan $z = 2.0$\,m, $t = %.0f$\,s" % (label, float(dP['tsel'])),
                  fontsize=9, loc="left")

    qlast = None
    for i, (t, ax) in enumerate(zip(TIMES, axsec)):
        _, qlast = _section(ax, caches[t], vmax)
        ttl = (r"longitudinal section, $t = %.0f$\,s" if i == 0 else r"$t = %.0f$\,s")
        ax.set_title(ttl % float(caches[t]['tact']), fontsize=8, loc="left")
        if i != n - 1:
            plt.setp(ax.get_xticklabels(), visible=False)
    axsec[-1].set_xlim(yP.min(), yP.max())

    # 1 m/s reference arrow: same quiver call/scale/width/halo as the data arrows
    axb = axsec[-1]
    ry, rz = 11.9, 0.30
    qref = axb.quiver([ry], [rz], [1.0], [0.0], color="white", scale=22,
                      width=0.0032, alpha=0.95, zorder=6)
    qref.set_path_effects([pe.withStroke(linewidth=0.7, foreground="black")])
    txt = axb.text(ry + 0.85, rz, r"1\,m\,s$^{-1}$", color="white", fontsize=7,
                   va="center", ha="left", zorder=6)
    txt.set_path_effects([pe.withStroke(linewidth=1.1, foreground="black")])

    cb = fig.colorbar(pcmP, ax=[axP] + axsec, pad=0.015, aspect=34,
                      ticks=np.round(np.arange(0, vmax + 1e-9, 0.1), 1))
    cb.set_label(r"extinction coefficient $k$ / m$^{-1}$", fontsize=8)

    for a in fig.axes:               # ticks outward (cleaner over the filled field)
        a.tick_params(which="both", direction="out")
    cb.ax.tick_params(which="both", direction="out")

    out = save_pdf(fig, PLOTS / f"extinction_flow_field_{tag}")
    plt.close(fig)
    print("wrote", out, "vmax=", vmax)


def main():
    if "notex" not in sys.argv:      # "notex" = dev layout check without LaTeX
        set_plot_style(font_size=9)
    only = [a for a in sys.argv[1:] if a in ("075", "150", "300")]
    for series, tag, label in FIRES:
        if only and tag not in only:
            continue
        extract(series, tag)
        make_figure(tag, label)


if __name__ == "__main__":
    main()
