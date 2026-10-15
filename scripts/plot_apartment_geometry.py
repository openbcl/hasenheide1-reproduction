"""Exploded isometric view of the apartment and its instrumentation (Figure 1).

The four rooms (fire room F1, F2, the corridor FC, and F3) are drawn as
transparent boxes, pulled apart along the connecting axis to expose the
doorways, and carry the windows, the sealed doorways, the fire source on its
load-cell platform, the thermocouple trees, the plume-impingement thermocouple,
and the LEM/SICK line-of-sight beams. A width-section inset through the
instrument-dense reference room F2 is drawn bottom-right.

Self-contained geometry (no external-drive dependency). Output -> plots/measurement/
(apartment_isometric_expfds.pdf).
Run:  python scripts/plot_apartment_geometry.py
"""
from pathlib import Path
import re
import shutil
import subprocess
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.colors import to_rgba
from matplotlib.lines import Line2D
from matplotlib.legend_handler import HandlerLine2D
from matplotlib.patches import Patch, Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection

from plot_style import set_plot_style, figsize_single

HERE = Path(__file__).resolve().parent
set_plot_style(preamble_path=HERE / "plot_preamble.tex", font_size=9)

# ---------------------------------------------------------------- geometry ---
# Room interiors as in the FDS deck, i.e. inside the wall OBSTs: the partition
# walls F1/F2 (y 4.2-4.4, Wall_05), F2/FC (7.7-7.85, Wall_03) and FC/F3
# (11.05-11.2, Wall_04) and the window walls (F1 x 4.15-4.25, Wall_06; F2/F3 x
# 4.5-4.6, Wall_07/08) have real thickness, so neighbouring rooms do not share a
# boundary plane. The chimney breasts in the F2 and F3 corners (Wall_01/02,
# 0.45 x 0.4 m) are cut out of the room outlines. Drawing-only geometry: no
# reported quantity is derived from it.
room_polys = {
    "F1": np.array([[0.0, 0.0], [4.15, 0.0], [4.15, 4.2], [0.0, 4.2]]),
    "F2": np.array([[0.45, 4.4], [4.5, 4.4], [4.5, 7.7], [0.0, 7.7], [0.0, 4.8],
                    [0.45, 4.8]]),
    "FC": np.array([[0.0, 7.85], [1.05, 7.85], [1.05, 11.05], [0.0, 11.05]]),
    "F3": np.array([[0.0, 11.2], [4.5, 11.2], [4.5, 14.5], [0.45, 14.5],
                    [0.45, 14.1], [0.0, 14.1]]),
}
room_z = {r: (0.0, 2.55) for r in room_polys}
doors = [
    ((0.82, 1.65, 4.15, 4.45, 0.0, 1.97), ["F1", "F2"]),
    ((0.13, 0.95, 7.65, 7.9, 0.0, 1.97), ["F2", "FC"]),
    ((0.11, 0.95, 11.0, 11.25, 0.0, 1.97), ["FC", "F3"]),
]
# drawn on the inner face of the window wall (the room outline); in the deck the
# glass sits at the outer face, 0.1 m further out
windows = [
    ((4.15, 4.15, 1.36, 2.65, 0.92, 2.14), "F1"),
    ((4.5, 4.5, 5.4, 6.69, 0.92, 2.14), "F2"),
    ((4.5, 4.5, 12.22, 13.55, 0.92, 2.23), "F3"),
]
fire_xb = (2.0, 2.15, 2.05, 2.2, 0.2, 0.2)       # burner (160 mm pan series), fuel surface
# load-cell platform with its calcium-silicate shield (deck OBST Load_cell, SURF
# SCALE; top 0.15 m) and the steel pan on it (outer envelope of
# the deck OBSTs Fire_pan_01..12, rim at 0.3 m)
load_cell_xb = (1.8, 2.35, 1.9, 2.35, 0.0, 0.15)
pan_xb = (1.975, 2.175, 2.025, 2.225, 0.15, 0.3)
# Flame: height = Heskestad mean flame height above the fuel surface,
# L = 0.235 Q^(2/5) - 1.02 D (Q in kW, D in m), for the 160 mm pan (area-equivalent
# D = 0.16 sqrt(4/pi) = 0.181 m) at the time-averaged heat release rate of the two
# 160 mm series (16 and 19 kW, numbers.tex valHrrAvgSmall/Mid; mean 17.5 kW)
# -> L = 0.55 m. Shape and width are schematic. (height, base radius, colour, alpha),
# outer to inner.
FLAME_Q_KW, FLAME_D_M = 17.5, 0.16 * np.sqrt(4.0 / np.pi)
FLAME_L = 0.235 * FLAME_Q_KW ** 0.4 - 1.02 * FLAME_D_M
FLAME_LAYERS = [(FLAME_L, 0.065, "#f28c28", 0.28), (0.55 * FLAME_L, 0.040, "#ffcf3f", 0.50)]
tc = [(3.65, 0.5, 0.01, 2.54, "F1"), (2.225, 5.9, 0.01, 2.54, "F2")]
# measured thermocouple positions on each tree (FDS DEVC TC_*), drawn as small
# symbols on the solid tree stem to suggest the individual sensors.
TC_HEIGHTS = [0.6, 1.2, 1.6, 1.8, 2.0, 2.2, 2.4, 2.5]
# plume-impingement thermocouple at the F1 ceiling above the fire
# (FDS DEVC TC_Ceiling_F1, XYZ=2.0625,2.1375,2.54); (x, y, z, room)
plume_tc = (2.0625, 2.1375, 2.54, "F1")
C_PLUME = "k"

# Line-of-sight extinction instruments. LEM: horizontal beam, transmitter ->
# detector; F2 carries a multi-height column. SICK: retro-reflective
# transmissometer, transmitter ... mirror.
#
# LEM and SICK beams exactly as in the FDS input file (DEVC ..._LOS_... PATH
# OBSCURATION), i.e. the same coordinate set as Table S1: one coordinate set for
# model, table and figure. (room, x0, x1, y, [heights]); x0..x1 span the
# L=0.81 m optical path.
lem = [
    ("F1", 2.745, 3.555, 3.725, [2.3]),               # LEM_LOS_F1_2_3
    ("F2", 1.870, 2.680, 6.275, [1.5, 1.9, 2.1]),     # LEM_LOS_F2_1_5/1_9/2_1 (tripod)
    ("F2", 1.870, 2.680, 6.325, [2.3]),               # LEM_LOS_F2_2_3
    ("F3", 1.870, 2.680, 12.775, [2.3]),              # LEM_LOS_F3_2_3
]
sick = [  # (room, x0, x1, y, z) as in the FDS input file (SICK_LOS_*). One SICK
          # per room: in F2 the modelled position (SICK_01); the second F2
          # position used in some runs is not modelled and not drawn.
    ("F1", 2.78, 3.58, 3.525, 2.285),     # SICK_02
    ("F2", 1.875, 2.675, 5.340, 2.315),   # SICK_01
    ("F3", 1.86, 2.66, 13.095, 2.255),    # SICK_04
]
C_LEM, C_SICK = "0.15", "#d62728"

# Sealed stairwell doorway (schematic): the envelope was sealed here with a
# plastic sheet, so it is a closed opening rather than a passage (the residual
# leakage is the distributed FDS pressure-zone model, not a discrete door). Drawn
# as a doorway outline with a cross. On the corridor (FC) outer
# wall. (x, y0, y1, z0, z1).
sealed_door = (0.0, 8.95, 9.75, 0.0, 1.97)
# The L-shaped corridor's narrow branch to the partitioned-off room and toilet
# was closed off with an OSB board, so FC is rectangular here rather than
# L-shaped. Its two former doorways (floor-plan labels "closed" and "sealed";
# closed leaf 0.73 m, sealed leaf 0.64 m) are shown on the
# FC->partitioned wall (x = 1.05) with the same crossed outline. (x, y0, y1, z0, z1)
fc_sealed_doors = [
    (1.05, 9.03, 9.75, 0.0, 1.97),
    (1.05, 10.30, 10.94, 0.0, 1.97),
]
# explosion along the connecting (y) axis; set per figure by draw_scene(gap=...)
GAP = 1.6
room_order = ["F1", "F2", "FC", "F3"]
y_shift = {}


def _set_gap(gap):
    acc = 0.0
    for r in room_order:
        y_shift[r] = acc
        acc += gap


_set_gap(GAP)


def sy(y, room):
    return y + y_shift[room]


# Rooms take the Matplotlib default cycle in sequence (F1->C0, F2->C1, F3->C2)
# and the corridor FC->C4; C3 (red) is skipped as it denotes the SICK / fire.
CE = {"F1": "#1f77b4", "F2": "#ff7f0e", "F3": "#2ca02c", "FC": "#9467bd"}
CF = {"F1": "#d2e4f0", "F2": "#ffe5cf", "F3": "#d5ecd5", "FC": "#eae1f2"}
C_DOOR, C_WIN, C_FIRE, C_TC = ("#a98467", "#30bcd0", "#cc3333", "0.38")
C_SCALE, C_PAN = "#d8cdb8", "0.35"   # calcium-silicate shield (warm light grey), steel pan


# Legibility of co-located instruments (F2 column, F3, F1 near the ceiling):
# a thin white halo around beams and stems, and a fixed drawing order (see
# draw_scene). Both only affect rendering, not positions.
def _halo(lw):
    return [pe.withStroke(linewidth=lw + 1.4, foreground="w")]


def box_faces(x0, x1, y0, y1, z0, z1, room="F1", sides_only=False):
    """Faces of an axis-aligned box in room coordinates (exploded y)."""
    y0, y1 = sy(y0, room), sy(y1, room)
    c = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    faces = [[[*c[i], z0], [*c[(i + 1) % 4], z0], [*c[(i + 1) % 4], z1], [*c[i], z1]]
             for i in range(4)]
    if not sides_only:
        faces += [[[x, y, z0] for x, y in c], [[x, y, z1] for x, y in c]]
    return faces


def flame_faces(cx, cy, z0, r, h, n=16):
    """Schematic flame: a cone of base radius r at height z0, apex h above it."""
    t = np.linspace(0.0, 2.0 * np.pi, n + 1)
    ring = [[cx + r * np.cos(a), cy + r * np.sin(a), z0] for a in t]
    apex = [cx, cy, z0 + h]
    return [[ring[i], ring[i + 1], apex] for i in range(n)]


def extrude_faces(poly, z0, z1):
    n = len(poly)
    bot = [[x, y, z0] for x, y in poly]
    top = [[x, y, z1] for x, y in poly]
    faces = [bot, top]
    for i in range(n):
        j = (i + 1) % n
        faces.append([bot[i], bot[j], top[j], top[i]])
    return faces


def extrude_edges(poly, z0, z1):
    n = len(poly)
    edges = []
    for z in (z0, z1):
        for i in range(n):
            j = (i + 1) % n
            edges.append((np.array([poly[i][0], poly[i][1], z]),
                          np.array([poly[j][0], poly[j][1], z])))
    for i in range(n):
        edges.append((np.array([poly[i][0], poly[i][1], z0]),
                      np.array([poly[i][0], poly[i][1], z1])))
    return edges


def draw_scene(elev, azim, inset_f2=False, gap=GAP):
    _set_gap(gap)
    fig = plt.figure(figsize=figsize_single(aspect=0.80))
    ax = fig.add_subplot(111, projection="3d")
    # Fixed drawing order instead of matplotlib's per-artist depth sort: the
    # instruments always lie on top of the translucent room boxes, and among them
    # the thermocouples on top of the beams (zorders below).
    ax.computed_zorder = False

    for name in room_order:                                   # rooms
        poly = room_polys[name].copy()
        poly[:, 1] += y_shift[name]
        z0, z1 = room_z[name]
        ax.add_collection3d(Poly3DCollection(
            extrude_faces(poly, z0, z1), facecolor=CF[name], alpha=0.07,
            edgecolor="none"))
        ax.add_collection3d(Poly3DCollection(                  # tinted floor
            [[[x, y, z0] for x, y in poly]], facecolor=CF[name], alpha=0.30,
            edgecolor="none", zorder=0))
        ax.add_collection3d(Line3DCollection(
            extrude_edges(poly, z0, z1), colors=CE[name], linewidths=0.55,
            alpha=0.70))
        ax.text(-0.4, 0.5 * (poly[:, 1].min() + poly[:, 1].max()), 2.55, r"\textbf{" + name + "}",
                fontsize=9, color=CE[name], ha="right", va="center", alpha=0.80)

    for xb, rlist in doors:                                   # doorways
        x1, x2, y1, y2, z1, z2 = xb
        ymid = 0.5 * (y1 + y2)
        for room in rlist:
            # draw the opening on the room's shared-boundary wall plane (the room
            # edge nearest the door), not at the door's own y-midpoint, so it sits
            # exactly on the room boundary rather than a fraction inside it
            ry0, ry1 = room_polys[room][:, 1].min(), room_polys[room][:, 1].max()
            by = ry0 if abs(ry0 - ymid) < abs(ry1 - ymid) else ry1
            ym = sy(by, room)
            r = [[x1, ym, z1], [x2, ym, z1], [x2, ym, z2], [x1, ym, z2], [x1, ym, z1]]
            ax.plot([p[0] for p in r], [p[1] for p in r], [p[2] for p in r],
                    color=C_DOOR, lw=0.5, alpha=0.50)

    for dx, dy0, dy1, dz0, dz1 in [sealed_door, *fc_sealed_doors]:  # sealed doorways:
        ym0, ym1 = sy(dy0, "FC"), sy(dy1, "FC")                     # same outline as the open
        frame = [[dx, ym0, dz0], [dx, ym1, dz0], [dx, ym1, dz1],    # doorways, plus a cross
                 [dx, ym0, dz1], [dx, ym0, dz0]]                    # (no fill, no hatch)
        ax.plot([p[0] for p in frame], [p[1] for p in frame], [p[2] for p in frame],
                color=C_DOOR, lw=0.5, alpha=0.60)
        ax.plot([dx, dx], [ym0, ym1], [dz0, dz1], color=C_DOOR, lw=0.5, alpha=0.60)
        ax.plot([dx, dx], [ym0, ym1], [dz1, dz0], color=C_DOOR, lw=0.5, alpha=0.60)

    for xb, room in windows:                                  # windows
        x1, _, y1, y2, z1, z2 = xb
        f = [[x1, sy(y1, room), z1], [x1, sy(y2, room), z1],
             [x1, sy(y2, room), z2], [x1, sy(y1, room), z2]]
        ax.add_collection3d(Poly3DCollection(
            [f], facecolor=C_WIN, alpha=0.25, edgecolor=C_WIN, linewidth=0.5))

    # fire source: load-cell platform with its calcium-silicate shield, the steel
    # pan on it, the burning fuel surface, and a schematic flame
    # One collection, so that matplotlib depth-sorts the individual faces and the
    # platform does not hide the pan (separate collections are sorted as wholes).
    fx1, fx2, fy1, fy2, _, fz = fire_xb
    fcx = 0.5 * (fx1 + fx2)
    fcy = 0.5 * (sy(fy1, "F1") + sy(fy2, "F1"))
    faces, fcs, ecs = [], [], []
    def _add(fl, fc, fa, ec, ea):
        faces.extend(fl)
        fcs.extend([to_rgba(fc, fa)] * len(fl))
        ecs.extend([to_rgba(ec, ea)] * len(fl))
    _add(box_faces(*load_cell_xb, room="F1"), C_SCALE, 0.75, "0.40", 0.9)  # load cell + shield
    _add(box_faces(*pan_xb, room="F1", sides_only=True), C_PAN, 0.55, "0.30", 1.0)  # pan walls
    _add([[[fx1, sy(fy1, "F1"), fz], [fx2, sy(fy1, "F1"), fz],               # fuel surface
           [fx2, sy(fy2, "F1"), fz], [fx1, sy(fy2, "F1"), fz]]], C_FIRE, 1.0, C_FIRE, 1.0)
    ax.add_collection3d(Poly3DCollection(faces, facecolors=fcs, edgecolors=ecs,
                                         linewidths=0.3, zorder=3))
    # Flame: drawn from the pan rim so the cones never cut the pan walls, with the
    # tip kept at the Heskestad height above the fuel surface; one collection per
    # layer, above the pan, inner layer on top.
    rim = pan_xb[5]
    for i, (h, r, col, al) in enumerate(FLAME_LAYERS):
        ax.add_collection3d(Poly3DCollection(
            flame_faces(fcx, fcy, rim, r, fz + h - rim), facecolor=col, alpha=al,
            edgecolor="none", zorder=3.5 + 0.1 * i))
    # no in-figure label: the legend entries identify the fire source and load cell

    for tx, ty, tz0, tz1, room in tc:                         # thermocouple trees
        s = sy(ty, room)
        ax.plot([tx, tx], [s, s], [tz0, tz1], color=C_TC, lw=0.7,
                alpha=0.85, zorder=4, path_effects=_halo(0.7))  # solid stem
        ax.scatter([tx] * len(TC_HEIGHTS), [s] * len(TC_HEIGHTS), TC_HEIGHTS,
                   marker="o", s=5, c=C_TC, edgecolors="w",    # sensor dots
                   linewidths=0.25, depthshade=False, zorder=7)
    px, py, pz, prm = plume_tc                                 # plume-impingement TC
    ax.scatter(px, sy(py, prm), pz, marker="v", s=22, c=C_PLUME,
               edgecolors="w", linewidths=0.3, depthshade=False, zorder=9)

    for room, x0, x1, y, zs in lem:                           # LEM beams (lines)
        yy = sy(y, room)
        for z in zs:
            ax.plot([x0, x1], [yy, yy], [z, z], color=C_LEM, lw=1.0, alpha=0.9,
                    solid_capstyle="round", zorder=5, path_effects=_halo(1.0))
            for xe in (x0, x1):                               # subtle end points
                ax.scatter(xe, yy, z, marker="o", s=3, c=C_LEM,
                           depthshade=False, zorder=6)
    for room, x0, x1, y, z in sick:                           # SICK beams (lines)
        yy = sy(y, room)
        ax.plot([x0, x1], [yy, yy], [z, z], color=C_SICK, lw=1.0, ls=(0, (3, 2)),
                alpha=0.9, zorder=5.5, path_effects=_halo(1.0))
        for xe in (x0, x1):
            ax.scatter(xe, yy, z, marker="o", s=3, c=C_SICK,
                       depthshade=False, zorder=6)

    # ---- axes (manual, segmented y per room with break marks) --------------
    ax.axis("off")
    y_max = max(sy(room_polys[r][:, 1].max(), r) for r in room_order)
    ax.set_xlim(-2.1, 5.2)
    ax.set_ylim(-1.2, y_max + 0.5)
    ax.set_zlim(-0.2, 2.9)
    # zoom 1.12: at the steep viewpoint a larger zoom pushes the x-axis label
    # below the figure edge
    ax.set_box_aspect([7.3, y_max + 1.7, 3.1], zoom=1.12)
    ax.view_init(elev=elev, azim=azim)

    ac, alw = "0.45", 0.4
    ax_ox, ax_oy, ax_oz = -1.25, -0.6, 0.0
    ax.plot([ax_ox, 4.8], [ax_oy, ax_oy], [ax_oz, ax_oz], color=ac, lw=alw, alpha=0.7)
    # x-axis label in line with the axis (below it would fall outside the figure)
    ax.text(4.95, ax_oy, ax_oz, r"$x$ / \si{\metre}", fontsize=7, color=ac, ha="left", va="center")
    for xt in [0, 1, 2, 3, 4]:
        ax.plot([xt, xt], [ax_oy, ax_oy], [ax_oz, ax_oz - 0.06], color=ac, lw=0.3, alpha=0.6)
        ax.text(xt, ax_oy, ax_oz - 0.12, str(xt), fontsize=6, color=ac, ha="center", va="top")
    ax.plot([ax_ox, ax_ox], [ax_oy, ax_oy], [ax_oz, 2.7], color=ac, lw=alw, alpha=0.7)
    ax.text(ax_ox, ax_oy, 2.78, r"$z$ / \si{\metre}", fontsize=7, color=ac, ha="center", va="bottom")
    for zt in [0, 1, 2]:
        ax.plot([ax_ox, ax_ox - 0.06], [ax_oy, ax_oy], [zt, zt], color=ac, lw=0.3, alpha=0.6)
        ax.text(ax_ox - 0.12, ax_oy, zt, str(zt), fontsize=6, color=ac, ha="right", va="center")
    # y-axis on the front (window-wall) side, x = x_front; ticks point outward.
    # Ticks carry the true coordinates of each room's own interior ends (0, 4.2 |
    # 4.4, 7.7 | 7.85, 11.05 | 11.2, 14.5 m); the break marks span the partition
    # wall plus the explosion gap, which adds no real distance.
    x_front = 4.9
    for name in room_order:
        p = room_polys[name]
        y0o, y1o = p[:, 1].min(), p[:, 1].max()
        y0p, y1p = sy(y0o, name), sy(y1o, name)
        ax.plot([x_front, x_front], [y0p, y1p], [ax_oz, ax_oz], color=ac, lw=alw, alpha=0.55)
        for yo, yp in [(y0o, y0p), (y1o, y1p)]:
            ax.plot([x_front, x_front + 0.06], [yp, yp], [ax_oz, ax_oz],
                    color=ac, lw=0.3, alpha=0.5)
        # number both ends of every room: the two faces of each partition wall
        # (e.g. 4.2 and 4.4) are labelled on either side of the gap
        labels = [(y0o, y0p), (y1o, y1p)]
        for yo, yp in labels:
            ax.text(x_front + 0.18, yp, ax_oz, f"{yo:g}", fontsize=6, color=ac,
                    ha="left", va="center")
        if name != room_order[-1]:                            # break marks at gaps
            nn = room_order[room_order.index(name) + 1]
            ye = y1p
            ys = sy(room_polys[nn][:, 1].min(), nn)
            ym = 0.5 * (ye + ys)
            dy = (ys - ye) * 0.15
            ax.plot([x_front, x_front + 0.04, x_front, x_front - 0.04, x_front],
                    [ye, ym - dy, ym, ym + dy, ys],
                    [ax_oz] * 5, color=ac, lw=0.3, alpha=0.4)
    ax.text(x_front, sy(room_polys["F3"][:, 1].max(), "F3") + 1.45, ax_oz - 0.25,
            r"$y$ / \si{\metre}", fontsize=7, color=ac, ha="center", va="bottom")

    # ---- legend ------------------------------------------------------------
    lem_h = Line2D([0, 1], [0, 0], color=C_LEM, lw=1.1, marker="o", ms=3,
                   mfc=C_LEM, mec=C_LEM, label="LEM (transmitter--detector)")
    sick_h = Line2D([0, 1], [0, 0], color=C_SICK, lw=1.1, ls=(0, (3, 2)), marker="o",
                    ms=3, mfc=C_SICK, mec=C_SICK, label="SICK (transmitter--reflector)")
    instr_handles = [
        Line2D([0], [0], color=C_TC, lw=0.9, marker="o", ms=3.5,
               mfc=C_TC, mec="w", mew=0.25, label="thermocouple tree"),
        Line2D([0], [0], marker="v", ls="", mfc=C_PLUME, mec="w", mew=0.3, ms=5,
               label="plume-impingement TC"),
    ]
    handles = [
        lem_h, sick_h,
        *instr_handles,
        Patch(facecolor=C_FIRE, alpha=0.85, edgecolor=C_FIRE, label="fire source (pan)"),
        Patch(facecolor=C_SCALE, alpha=0.75, edgecolor="0.40", label="load cell (shielded)"),
        Patch(facecolor=C_WIN, alpha=0.25, edgecolor=C_WIN, label="closed window (glass)"),
        Line2D([0], [0], color=C_DOOR, lw=0.8, label="doorway"),
        Line2D([0], [0], color=C_DOOR, lw=0.8, marker="x", ms=5, mew=0.9,
               label="sealed doorway"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.08, 0.84),
              fontsize=8, frameon=False, handlelength=1.4, labelspacing=0.30,
              borderaxespad=0.0,
              handler_map={lem_h: HandlerLine2D(numpoints=2),
                           sick_h: HandlerLine2D(numpoints=2)})

    fig.subplots_adjust(left=0.0, right=0.97, bottom=0.0, top=1.0)

    if inset_f2:                              # 2D width-section inset (bottom-right)
        axin = fig.add_axes([0.66, 0.135, 0.31, 0.27])
        _draw_f2_section(axin)

    return fig


def _room_bbox(name):
    p = room_polys[name]
    return p[:, 0].min(), p[:, 0].max(), p[:, 1].min(), p[:, 1].max()


def _draw_f2_section(ax):
    """Orthographic width-section (x-z plane) of the reference room F2, projected
    along the apartment length, for the isometric inset. F2 is the
    instrument-dense room carrying the multi-height LEM column. Shows the LEM
    heights, the SICK beam, the window, and the thermocouple tree. Shares the
    figure legend -- no separate legend, identical colours/symbols to the
    isometric."""
    nm = "F2"
    x1, x2, _, _ = _room_bbox(nm)
    z0, z1 = room_z[nm]
    ax.add_patch(Rectangle((x1, z0), x2 - x1, z1 - z0, fill=False,        # room
                           edgecolor=CE[nm], lw=1.0, alpha=0.85, zorder=1))
    for xb, rlist in doors:                                              # door to FC
        if not ("F2" in rlist and "FC" in rlist):
            continue
        dx1, dx2, _, _, dz1, dz2 = xb
        ax.add_patch(Rectangle((dx1, dz1), dx2 - dx1, dz2 - dz1,
                               facecolor=C_DOOR, edgecolor=C_DOOR, lw=0.4,
                               alpha=0.30, zorder=1))
    for xb, rn in windows:                                               # window
        if rn != nm:
            continue
        wx, _, _, _, wz1, wz2 = xb
        ax.plot([wx, wx], [wz1, wz2], color=C_WIN, lw=2.2, alpha=0.75,
                solid_capstyle="butt", zorder=2)
    for tx, _, tz0, tz1, rn in tc:                                       # TC tree
        if rn != nm:
            continue
        ax.plot([tx, tx], [tz0, tz1], color=C_TC, lw=0.8, alpha=0.85, zorder=3)
        ax.plot([tx] * len(TC_HEIGHTS), TC_HEIGHTS, ls="", marker="o",
                ms=2.6, mfc=C_TC, mec="w", mew=0.25, zorder=4)
    lem_x = next(((b[1], b[2]) for b in lem if b[0] == nm), None)        # LEM x-range
    for rn, bx0, bx1, _, zs in lem:                                      # LEM column
        if rn != nm:
            continue
        for z in zs:
            ax.plot([bx0, bx1], [z, z], color=C_LEM, lw=1.1, alpha=0.9,
                    solid_capstyle="round", zorder=6)
            ax.plot([bx0, bx1], [z, z], ls="", marker="o", ms=2.2,
                    mfc=C_LEM, mec=C_LEM, zorder=7)
            ax.text(bx1 + 0.16, z, rf"\SI{{{z:.1f}}}{{\metre}}", fontsize=5,
                    color=C_LEM, ha="left", va="center", zorder=8)
    for rn, _, _, _, z in sick:                       # SICK beam, aligned to LEM x
        if rn != nm:
            continue
        sx0, sx1 = lem_x
        ax.plot([sx0, sx1], [z, z], color=C_SICK, lw=1.0, ls=(0, (3, 2)),
                alpha=0.9, zorder=6)
        ax.plot([sx0, sx1], [z, z], ls="", marker="o", ms=2.2,
                mfc=C_SICK, mec=C_SICK, zorder=7)
    # ---- axes (manual x and z, dimensioned to match the isometric) ---------
    ac, alw = "0.45", 0.4
    ax_x0, ax_z0 = -0.18, -0.12   # z-axis at x=ax_x0; x-axis baseline at z=ax_z0
    ax.plot([ax_x0, 4.8], [ax_z0, ax_z0], color=ac, lw=alw, alpha=0.7,   # x-axis
            zorder=1)
    ax.text(4.95, ax_z0, r"$x$ / \si{\metre}", fontsize=5, color=ac,
            ha="left", va="center")
    for xt in [0, 1, 2, 3, 4]:
        ax.plot([xt, xt], [ax_z0, ax_z0 - 0.08], color=ac, lw=0.3, alpha=0.6,
                zorder=1)
        ax.text(xt, ax_z0 - 0.14, str(xt), fontsize=5, color=ac, ha="center",
                va="top")
    ax.plot([ax_x0, ax_x0], [ax_z0, 2.6], color=ac, lw=alw, alpha=0.7,   # z-axis
            zorder=1)
    ax.text(ax_x0, 2.68, r"$z$ / \si{\metre}", fontsize=5, color=ac,
            ha="center", va="bottom")
    for zt in [0, 1, 2]:
        ax.plot([ax_x0, ax_x0 - 0.08], [zt, zt], color=ac, lw=0.3, alpha=0.6,
                zorder=1)
        ax.text(ax_x0 - 0.14, zt, str(zt), fontsize=5, color=ac, ha="right",
                va="center")

    ax.set_xlim(-0.55, 5.1)
    ax.set_ylim(-0.4, 2.9)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(r"section through F2", fontsize=7, color=CE[nm], pad=1.5)


# Viewpoint and explosion gap of Figure 1, chosen by a symbol-clearance scan over
# elevation 25-50 deg, azimuth -50 to -75 deg and gaps 1.6-2.2 m: no instrument touches another room's box (the corridor FC no longer
# sits on the F2 column), the F1 thermocouple tree stays clear of the fire, and
# (from 50 deg) the front ceiling edge of F1 no longer crosses the fire source.
VIEW, GAP_FIG = (50, -65), 1.9


def crop_pdf(pdf_path):
    """Trim the white margins to the ink bounding box with pdfcrop (in place).

    matplotlib's bbox_inches="tight" leaves a sizeable border around 3D axes
    because the axes bounding box includes empty space; pdfcrop removes it.
    """
    exe = shutil.which("pdfcrop")
    if not exe:
        print("  (pdfcrop not found -- skipping margin crop)")
        return
    tmp = pdf_path.with_suffix(".crop.pdf")
    res = subprocess.run([exe, "--hires", "--margins", "2 2 2 2",
                          str(pdf_path), str(tmp)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                         text=True, errors="replace")
    if res.returncode != 0:
        tail = "\n    ".join((res.stderr or "").strip().splitlines()[-5:])
        raise RuntimeError(
            f"pdfcrop failed (exit {res.returncode}):\n    {tail}\n"
            "  pdfcrop is a Perl script: on Windows/MiKTeX a Perl interpreter must be on "
            "PATH (e.g. Strawberry Perl, or perl.exe from Git for Windows in "
            "<Git>\\usr\\bin).")
    tmp.replace(pdf_path)
    _make_pdf_deterministic(pdf_path)


def _make_pdf_deterministic(pdf_path):
    """Remove pdfcrop's two non-deterministic stamps so cropped PDFs are
    byte-identical across runs (clean git diffs, true reproducibility).

    pdfcrop's pdfTeX pass honours SOURCE_DATE_EPOCH for /CreationDate but still
    leaves two run-dependent fields:
      1. the trailer /ID (a content+time hash) -- the two tokens are fixed-length
         hex, zeroed in place;
      2. /PTEX.FileName (./tmp-pdfcrop-<PID>-img.pdf) -- the temp name carries the
         process id; canonicalised and right-padded with spaces so the total byte
         length is unchanged (PDF treats the padding as inter-token whitespace).
    Both edits preserve every byte offset, so the xref table stays valid.
    """
    data = pdf_path.read_bytes()
    data = re.sub(
        rb"(/ID\s*\[\s*<)([0-9A-Fa-f]+)(>\s*<)([0-9A-Fa-f]+)(>\s*\])",
        lambda m: m.group(1) + b"0" * len(m.group(2)) + m.group(3)
        + b"0" * len(m.group(4)) + m.group(5),
        data,
    )

    def _ptex(m):
        canon = b"(./tmp-pdfcrop-img.pdf)"
        pad = len(m.group(0)) - len(canon)
        return canon + b" " * pad if pad >= 0 else m.group(0)

    data = re.sub(rb"\(\./tmp-pdfcrop-\d+-img\.pdf\)", _ptex, data)
    pdf_path.write_bytes(data)


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "plots" / "measurement"
    out.mkdir(parents=True, exist_ok=True)
    elev, azim = VIEW
    fig = draw_scene(elev=elev, azim=azim, inset_f2=True, gap=GAP_FIG)
    stem = out / "apartment_isometric_expfds"
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    crop_pdf(stem.with_suffix(".pdf"))
    print(f"-> {stem}.pdf")
