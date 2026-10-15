"""Shared Matplotlib style for every figure in the reproduction package.

Single-sources the cross-figure palette and markers, renders text through LaTeX
(``text.usetex`` -- needs a TeX install with ``siunitx``), and pins
``SOURCE_DATE_EPOCH`` so regenerated figure PDFs are byte-identical to the
committed reference. Plotting scripts apply it via ``set_plot_style()``.
"""
from __future__ import annotations
import os
from pathlib import Path
import matplotlib as mpl


# ----------------------------
# Deterministic / reproducible PDF output
# ----------------------------
# matplotlib stamps each PDF with a wall-clock /CreationDate and derives the
# trailer /ID from it, so re-running a figure script yields byte-different PDFs
# even when the content is identical (noisy git diffs, no byte-level repro).
# Fixing SOURCE_DATE_EPOCH makes both the date and the /ID deterministic, so
# regenerating an unchanged figure is a no-op for git. Set at import time, before
# any savefig, and only if the caller has not already pinned it. 1136073600 =
# 2006-01-01 UTC (arbitrary fixed instant). pdfcrop / pdfTeX honour the same var.
REPRO_EPOCH = "1136073600"
os.environ.setdefault("SOURCE_DATE_EPOCH", REPRO_EPOCH)
# pdfTeX (invoked by pdfcrop on the geometry figures) only honours
# SOURCE_DATE_EPOCH for /CreationDate and the trailer /ID when this is set.
os.environ.setdefault("FORCE_SOURCE_DATE", "1")


# ----------------------------
# Single-column figure sizing
# ----------------------------

COLUMN_WIDTH_MM = 150.0  # <-- your column width
MM_TO_INCH = 1.0 / 25.4


def figsize_single(aspect: float = 0.62) -> tuple[float, float]:
    """
    aspect = height / width
    """
    width_in = COLUMN_WIDTH_MM * MM_TO_INCH
    return width_in, width_in * aspect


# ----------------------------
# Shared semantic palette (single source for cross-figure consistency)
# ----------------------------
# Line-of-sight reference instruments: (colour, marker).
INSTRUMENT_STYLE = {"LEM": ("black", "D"), "SICK": ("C3", "s")}
# FDS curves: the field / baseline colour, and a grey dashed reference style
# (used for the adopted leakage curve of the blower-door figure). C4 (purple)
# keeps FDS clear of the heavily-loaded blue (F2). Exception: the temperature matrix overlays two FDS
# curves and distinguishes them by room colour + dashed style, so it does not
# use FDS_COLOR.
FDS_COLOR = "C4"
FDS_IDEAL_STYLE = {"color": "0.55", "ls": "--"}
# Discrete line-of-sight reference markers (LEM/SICK) use a single size.
MS_REFERENCE = 5.0

# The three apartment fire series, wherever a figure resolves them. Kept here so
# the figures that resolve the series cannot drift apart in marker, colour or
# wording; the colours are the first three cycle entries, which is what
# the parity scatter used implicitly before this was hoisted. Charge/pan wording
# follows the parity scatter (readers meet it there first), not the run IDs.
SERIES_KEYS = ("hep_160_075", "hep_160_150", "hep_220_300")
SERIES_MARKER = {"hep_160_075": "o", "hep_160_150": "s", "hep_220_300": "^"}
SERIES_COLOR = {"hep_160_075": "C0", "hep_160_150": "C1", "hep_220_300": "C2"}
SERIES_LABEL = {
    "hep_160_075": r"75\,g / 160\,mm",
    "hep_160_150": r"150\,g / 160\,mm",
    "hep_220_300": r"300\,g / 220\,mm",
}


# ----------------------------
# Matplotlib / LaTeX style
# ----------------------------

# Default LaTeX preamble lives next to this module; resolve it relative to the
# file (not the cwd) so scripts work whether run from the repo root or scripts/.
_PREAMBLE_DEFAULT = Path(__file__).resolve().parent / "plot_preamble.tex"


def set_plot_style(
    *,
    preamble_path: str | Path | None = None,
    font_size: float = 10.0,
    dpi: int = 300,
) -> None:
    """
    Apply a consistent paper-style configuration.
    Call BEFORE creating figures.
    """
    preamble = Path(preamble_path or _PREAMBLE_DEFAULT).read_text(encoding="utf-8")

    mpl.rcParams.update({
        # Use LaTeX for all text
        "text.usetex": True,
        "text.latex.preamble": preamble,

        # Let LaTeX choose fonts
        "font.family": "serif",

        # Typography
        "font.size": font_size,
        "axes.labelsize": font_size,
        "axes.titlesize": font_size,
        "legend.fontsize": font_size - 1,
        "xtick.labelsize": font_size - 1,
        "ytick.labelsize": font_size - 1,

        # Lines and axes
        "lines.linewidth": 1.2,
        "lines.markersize": 4.0,
        "axes.linewidth": 0.8,

        # Ticks
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.minor.visible": True,
        "ytick.minor.visible": True,
        "xtick.major.size": 3.0,
        "ytick.major.size": 3.0,
        "xtick.minor.size": 1.5,
        "ytick.minor.size": 1.5,

        # Output
        "figure.dpi": dpi,
        "savefig.dpi": dpi,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,

        # Keep text as text in PDF
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def save_pdf(fig, stem: str | Path) -> Path:
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    out = stem.with_suffix(".pdf")
    fig.savefig(out)
    return out
