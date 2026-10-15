"""Dimensioned 2D drawing of the two square steel pans on the platform scale
(Supplementary Material, Figure S3), with the FDS representation overlaid. Plan view (top row)
and centre section A-A (bottom row), 160 mm and 220 mm pan side by side at the
same scale.

As built, from the survey and photographs of the pans (not shipped):
  body     3 mm sheet box, interior a x a, H = 100 mm floor to rim top
  rim      steel angle round the top, vertical leg down against the outside of the
           wall, top flush with the wall edge; rim 25 mm from the inner face (measured:
           220 pan 270 mm across), so the horizontal leg is 25 - 3 = 22 mm;
           two long bars across the full width, two short ones between them;
           the feet sit under the long ones (photographs)
  base     steel angle round the bottom edge: vertical leg against the wall,
           horizontal leg under the floor plate, pointing inward
  feet     20 mm open square tube, welded against the two long-angle walls:
           proud of those walls (span a + 46), flush with the other two
           (span a + 6); rim top 150 mm above the board (measured, both pans)
Rim, height and sheet thickness measured by the authors; the rest are photo readings, +-2 mm.

FDS (fds_decks/hep_*_ysmatched.fds, OBST Fire_pan_*, Load_cell), on the 25 mm grid:
  burner 150 x 150 (160 pan) / 225 x 225 (220 pan) at z = 0.20, thin walls to
  z = 0.30, a 25 mm rim at z = 0.30, 25 mm feet at the four diagonal corners
  from the board (z = 0.15) to the rim; Load_cell 550 x 450 x 150 mm
  (scale + 50 mm calcium silicate board, SURF SCALE); the 160 pan is centred on it,
  the 220 pan half a cell off centre (grid-conformal burner).
As built the scale is 110 mm high (measured), so the board top is at 0.16 m and the
pan 10 mm higher than in the deck, which snaps board top, burner and rim to the
nearest cell faces (0.15 / 0.20 / 0.30); drawn at true height, the FDS outline sits
10 mm below the pan. Every as-built dimension lies within half a cell (12.5 mm) of
the deck, except the foot position across the flush direction (about one cell).

Initial fuel depth d_f = m / (rho a^2) from the charge mass and the certified density of
the batch (Shell Heptane Q1352/1010, despatch 03.11.2021, certificate of analysis:
0.7179 kg/l at 15 C, ASTM D4052): 4.1 / 8.2 mm (160 pan, 75 / 150 g) and 8.6 mm
(220 pan, 300 g). The h/D ranges of Table 1 follow from these depths
((H - d_f) / D with D = 2a/sqrt(pi): 0.53 / 0.51 / 0.37 at the start).

Printed 1:1: the PDF comes out 149 x 149 mm, i.e. at the 150 mm text width.
Output: plots/measurement/pan_drawing.pdf. Inputs are constants only (no external data).
Run: python scripts/plot_pan_drawing.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

from plot_style import COLUMN_WIDTH_MM, FDS_COLOR, MM_TO_INCH, SERIES_COLOR, set_plot_style

OUT = Path(__file__).resolve().parents[1] / "plots" / "measurement" / "pan_drawing"

T = 3.0          # sheet and angle thickness (measured: 3 mm sheet)
H = 100.0        # interior depth, floor to rim top (photo, both pans)
FOOT = 20.0      # square-tube feet (photo)
LEG_V = 25.0     # vertical leg of the rim and base angles (measured: 25)
BASE_H = 25.0    # horizontal leg of the base angle under the floor (measured: 25)
BOARD = 50.0     # calcium silicate board
SCALE_H = 110.0  # platform scale under the board (measured; survey: board top 0.16 m)
PLAT_X, PLAT_Y = 550.0, 450.0   # Load_cell footprint (deck; survey 560 x 440)

DX = 25.0        # FDS near-field cell
FDS_RIM = 25.0   # FDS rim width (one cell)


RHO_FUEL = 0.7179e-3  # g/mm^3: certified density of the batch at 15 C (ASTM D4052)


def _df(mass_g, a):  # initial fuel depth in mm: charge volume over the pan floor area
    return mass_g / RHO_FUEL / a ** 2


PANS = {  # a: interior; F = a + 2 x 25 rim; Z: rim top above board; b: FDS burner
    160: dict(F=210.0, Z=150.0, b=150.0, fuel={"hep_160_075": _df(75, 160),
                                                "hep_160_150": _df(150, 160)}),
    220: dict(F=270.0, Z=150.0, b=225.0, fuel={"hep_220_300": _df(300, 220)}),
}
# FDS heights are absolute in the deck (z above the room floor) and are drawn at their
# true height, i.e. relative to the as-built board top at SCALE_H + BOARD = 0.16 m:
# the deck puts the Load_cell top (= board top) at 0.15, the burner at 0.20 and the rim
# at 0.30, the cell faces nearest to the as-built 0.16 / 0.21 / 0.31, so the FDS
# outline sits 10 mm below the as-built pan.
Z_BOARD_TOP = SCALE_H + BOARD
FDS_LOADCELL, FDS_FLOOR, FDS_TOP = (z - Z_BOARD_TOP for z in (150.0, 200.0, 300.0))


C_CUT = "0.20"     # steel cut by the section plane
C_VIS = "0.80"     # steel seen beyond the plane
C_FLANGE = "0.80"  # rim in plan
C_BOARD = "0.92"
C_DIM = "0.15"
# Printed 1:1 at the 150 mm text width (A4, 3 cm margins): text follows plot_style
# (10 pt titles/tags, 9 pt legend), dimension figures one step smaller (8 pt) as in
# the apartment geometry figures; line weights graded outline > dimension > extension.
LW = 0.6          # visible outlines
LW_DIM = 0.45     # dimension lines
LW_EXT = 0.3      # extension lines
FS = 8            # dimension figures and labels
FS_TAG = 10       # panel tags, column titles
FS_LEG = 9        # legend, row labels
DIM_ARROW = dict(arrowstyle="<|-|>,head_length=0.55,head_width=0.18", mutation_scale=8)
FDS_KW = dict(color=FDS_COLOR, lw=0.9, ls=(0, (3.5, 1.8)), zorder=6)
# cut parts get a white hairline so that parts welded flush (wall + angle leg)
# still read as separate 3 mm members
CUT_KW = dict(fc=C_CUT, ec="white", lw=0.25)
HIDDEN_KW = dict(ls=(0, (2, 1.2)), lw=0.5, ec="0.25")

XLIM = (-182, 182)          # same scale in every panel; the platform is broken off
PLAN_YLIM = (-168, 176)
SEC_YLIM = (-BOARD - SCALE_H - 4, 180)


def dim(ax, p0, p1, text, off, horizontal=True, text_side=1, ext=True):
    """Dimension line between p0 and p1, offset by `off` (perpendicular)."""
    (x0, y0), (x1, y1) = p0, p1
    sg = 1 if off > 0 else -1
    arrow = dict(lw=LW_DIM, color=C_DIM, shrinkA=0, shrinkB=0, **DIM_ARROW)
    if horizontal:
        yd = y0 + off
        if ext:
            for x, y in ((x0, y0), (x1, y1)):
                ax.plot([x, x], [y + 2 * sg, yd + 3 * sg], color="0.35", lw=LW_EXT)
        ax.annotate("", (x0, yd), (x1, yd), arrowprops=arrow)
        ax.text((x0 + x1) / 2, yd + 2.5 * text_side, text, fontsize=FS, ha="center",
                va="bottom" if text_side > 0 else "top")
    else:
        xd = x0 + off
        if ext:
            for x, y in ((x0, y0), (x1, y1)):
                ax.plot([x + 2 * sg, xd + 3 * sg], [y, y], color="0.35", lw=LW_EXT)
        ax.annotate("", (xd, y0), (xd, y1), arrowprops=arrow)
        ax.text(xd + 2.5 * text_side, (y0 + y1) / 2, text, fontsize=FS, rotation=90,
                ha="right" if text_side < 0 else "left", va="center")


def rect(ax, x0, x1, y0, y1, **kw):
    kw.setdefault("lw", LW)
    kw.setdefault("ec", "0.15")
    ax.add_patch(Rectangle((min(x0, x1), min(y0, y1)), abs(x1 - x0), abs(y1 - y0), **kw))


def outline(ax, x0, x1, y0, y1, **kw):
    ax.plot([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0], **kw)


def plan(ax, a, F, b):
    h, f, w = a / 2, F / 2, a / 2 + T
    rect(ax, -f, f, -f, f, fc=C_FLANGE)
    for s in (-1, 1):  # two long rim angles (left/right, over the feet), short ones between
        ax.plot([s * h, s * h], [-f, -h], color="0.15", lw=0.4)
        ax.plot([s * h, s * h], [h, f], color="0.15", lw=0.4)
    rect(ax, -h, h, -h, h, fc="white")
    for sx in (-1, 1):  # feet, hidden under the rim
        for sy in (-1, 1):
            rect(ax, sx * w, sx * (w + FOOT), sy * w, sy * (w - FOOT), fc="none", **HIDDEN_KW)
    # FDS seen from above: burner/wall square and rim outer edge (the corner feet lie
    # entirely under the rim). Each edge is drawn once, so no two dash patterns overlap.
    hb, fb = b / 2, b / 2 + FDS_RIM
    outline(ax, -hb, hb, -hb, hb, **FDS_KW)
    outline(ax, -fb, fb, -fb, fb, **FDS_KW)
    # section line A-A
    xa = XLIM[1] - 12
    ax.plot([-xa, xa], [0, 0], color="0.3", lw=0.5, ls=(0, (8, 2, 1, 2)), zorder=7)
    for s in (-1, 1):
        ax.annotate("", (s * xa, -22), (s * xa, 0), arrowprops=dict(
            arrowstyle="-|>,head_length=0.55,head_width=0.2", lw=0.5, color=C_DIM,
            mutation_scale=8, shrinkA=0, shrinkB=0))
        ax.text(s * (xa - 10), -15, "A", fontsize=FS_LEG, ha="center", va="center")
    dim(ax, (-h, h), (h, h), rf"$a = {a:.0f}$", off=-44, text_side=1, ext=False)
    dim(ax, (-f, f), (f, f), f"{F:.0f}", off=10)
    dim(ax, (-w - FOOT, -f), (w + FOOT, -f), f"{a + 2 * T + 2 * FOOT:.0f}",
        off=-10, text_side=-1)


def _break(ax, x, z0, z1, s):
    """Vertical break line with one zigzag, at x from z0 (bottom) to z1 (top)."""
    zm = (z0 + z1) / 2
    ax.plot([x, x, x + 4 * s, x - 4 * s, x, x], [z0, zm - 6, zm - 2, zm + 2, zm + 6, z1],
            color="0.45", lw=LW_EXT + 0.1)


def section(ax, a, F, Z, b, fuel, show_labels):
    h, f, w = a / 2, F / 2, a / 2 + T
    z_floor = Z - H              # interior floor
    z_base = z_floor - 2 * T     # underside of the base angle
    xb = XLIM[1] - 6             # platform broken off here
    rect(ax, -xb, xb, -BOARD, 0, fc=C_BOARD, hatch="////", lw=0, ec="0.55")
    for y in (0, -BOARD, -BOARD - SCALE_H):
        ax.plot([-xb, xb], [y, y], color="0.45", lw=0.5)
    for s in (-1, 1):
        _break(ax, s * xb, -BOARD - SCALE_H, 0, s)
    for s in (-1, 1):  # feet (beyond the plane), standing proud of the walls up to the rim
        rect(ax, s * w, s * (w + FOOT), 0, Z - T, fc=C_VIS, ec="0.35", lw=0.5)
    # initial fuel layer per charge; several charges share the pan width side by side
    # (smallest left) so that their levels do not overlap
    depths = sorted(fuel.items(), key=lambda kv: kv[1])
    seg = a / len(depths)
    for i, (key, d) in enumerate(depths):
        x0 = -h + i * seg
        ax.add_patch(Rectangle((x0, z_floor), seg, d, fc=SERIES_COLOR[key], alpha=0.35, lw=0))
        ax.plot([x0, x0 + seg], [z_floor + d] * 2, color=SERIES_COLOR[key], lw=0.9)
    rect(ax, -w, w, z_floor - T, z_floor, **CUT_KW)               # floor plate
    for s in (-1, 1):
        rect(ax, s * h, s * w, z_floor - T, Z, **CUT_KW)           # wall, up to the rim top
        rect(ax, s * w, s * f, Z - T, Z, **CUT_KW)                 # rim angle, horiz. leg
        rect(ax, s * w, s * (w + T), Z - LEG_V, Z - T, **CUT_KW)   # rim angle, vert. leg
        rect(ax, s * w, s * (w + T), z_base, z_base + LEG_V, **CUT_KW)  # base, vert.
        rect(ax, s * (w + T), s * (w + T - BASE_H), z_base, z_base + T,
             **CUT_KW)                                             # base, horiz.
    # FDS: burner at z = 0.20, thin walls and rim to z = 0.30, corner feet from the
    # Load_cell top (0.15). One continuous path round burner, walls, rim and feet: shared
    # edges (foot/wall, foot/rim) are drawn once, so the dashes never double up into a
    # solid line; the Load_cell top is drawn only where no foot stands on it.
    hb, fb = b / 2, b / 2 + FDS_RIM
    zl = FDS_LOADCELL
    xs = [-hb, -hb, -fb, -fb, -hb, -hb, hb, hb, fb, fb, hb, hb]
    zs = [FDS_FLOOR, zl, zl, FDS_TOP, FDS_TOP, FDS_FLOOR, FDS_FLOOR, FDS_TOP, FDS_TOP, zl, zl,
          FDS_FLOOR]
    ax.plot(xs, zs, **FDS_KW)
    for x0, x1 in ((-xb, -fb), (-hb, hb), (fb, xb)):
        ax.plot([x0, x1], [zl, zl], **FDS_KW)
    # Load_cell bottom at z = 0, the room floor under the as-built scale as well
    ax.plot([-xb, xb], [-Z_BOARD_TOP] * 2, **FDS_KW)
    # dimensions: widths above, depth left, overall height right
    xl = -f - 12
    dim(ax, (-f, Z), (f, Z), f"{F:.0f}", off=10)
    dim(ax, (-h, z_floor), (h, z_floor), rf"$a = {a:.0f}$", off=H * 0.55, ext=False)
    dim(ax, (xl, z_floor), (xl, Z), r"$H = 100$", off=0, horizontal=False,
        text_side=-1, ext=False)
    for z, x_end in ((Z, -f), (z_floor, -h)):
        ax.plot([xl - 3, x_end - 2], [z, z], color="0.35", lw=LW_EXT)
    dim(ax, (f, 0), (f, Z), f"{Z:.0f}", off=12, horizontal=False, text_side=1)
    if show_labels:
        ax.text(-xb + 8, -BOARD / 2, "calcium silicate board",
                fontsize=FS, ha="left", va="center",
                bbox=dict(fc=C_BOARD, ec="none", pad=1.0))
        ax.text(-xb + 8, -BOARD - SCALE_H / 2, "platform scale",
                fontsize=FS, ha="left", va="center", color="0.25")
        dim(ax, (xb - 16, -BOARD), (xb - 16, 0), f"{BOARD:.0f}", off=0, horizontal=False,
            text_side=-1, ext=False)
        dim(ax, (xb - 16, -BOARD - SCALE_H), (xb - 16, -BOARD), f"{SCALE_H:.0f}", off=0,
            horizontal=False, text_side=-1, ext=False)


def main():
    set_plot_style()
    plt.rcParams["hatch.linewidth"] = 0.4
    w = COLUMN_WIDTH_MM * MM_TO_INCH
    hp, hs = PLAN_YLIM[1] - PLAN_YLIM[0], SEC_YLIM[1] - SEC_YLIM[0]
    fig, axs = plt.subplots(2, 2, figsize=(w, w * 1.015),  # same scale in both rows
                            gridspec_kw=dict(height_ratios=[hp, hs], hspace=0.06,
                                             wspace=0.03, left=0.035, right=0.995,
                                             top=0.965, bottom=0.06))
    for j, (a, p) in enumerate(PANS.items()):
        plan(axs[0, j], a, p["F"], p["b"])
        section(axs[1, j], a, p["F"], p["Z"], p["b"], p["fuel"], show_labels=(j == 0))
        axs[0, j].set_title(rf"\SI{{{a}}}{{\milli\metre}} pan", fontsize=FS_TAG, pad=3)
        axs[0, j].set_ylim(*PLAN_YLIM)
        axs[1, j].set_ylim(*SEC_YLIM)
    for ax in axs.flat:
        ax.set_xlim(*XLIM)
        ax.set_aspect("equal")
        ax.axis("off")
    for ax, tag in zip(axs.flat, "abcd"):
        ax.text(0.0, 1.0, f"({tag})", transform=ax.transAxes, fontsize=FS_TAG, va="top", ha="left")
    for ax, lab in ((axs[0, 0], "plan"), (axs[1, 0], r"section A--A")):
        ax.text(-0.02, 0.5, lab, transform=ax.transAxes, fontsize=FS_LEG, rotation=90,
                ha="right", va="center", color="0.3")
    handles = [Patch(fc=C_CUT, ec="none", label="steel, cut"),
               Patch(fc=C_VIS, ec="0.35", lw=0.5, label="steel, beyond"),
               Line2D([0], [0], ls=HIDDEN_KW["ls"], color=HIDDEN_KW["ec"], lw=HIDDEN_KW["lw"],
                      label="feet, hidden"),
               Line2D([0], [0], label=r"FDS obstructions ($\delta x = \SI{25}{\milli\metre}$)",
                      **{k: v for k, v in FDS_KW.items() if k != "zorder"})]
    fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False, fontsize=FS_LEG,
               bbox_to_anchor=(0.5, 0.06), handlelength=2.0, columnspacing=1.5)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
