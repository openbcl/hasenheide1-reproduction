"""Example: one measured test against the FDS baseline of its series.

Not a paper figure; a starting point for working with the committed time series
(scripts/timeseries.py). Left: the LEM extinction near the ceiling (z = 2.3 m) in
each room. Right: the LEM extinction at every height measured in room F2 in that
test. Solid: measured; dashed: the FDS line-of-sight beam at the same position
(results/simulation/timeseries/, column ``measured`` of fds_channels.csv).

Run: python example_timeseries.py [RUN]      (default Hep_160_S4_R1)
Writes plots/exploratory/example_timeseries_<RUN>.png (not tracked).
"""
from __future__ import annotations

import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import paths as P  # noqa: E402
from timeseries import load_fds, load_test  # noqa: E402


def main(run: str = "Hep_160_S4_R1") -> int:
    t = load_test(run)
    m = load_fds(t.run["series"])
    ch = t.channels[t.channels.status == "ok"]
    lem = ch[ch.instrument.str.startswith("LEM") & (ch.quantity == "light-extinction coefficient")]
    model = m.channels.dropna(subset=["measured"]).set_index("measured")["column"]
    ev = t.events.set_index("event")["t_s"]

    plt.rcdefaults()
    win = t.data.t_s.between(-60, 1200)
    top = 1.15 * max(t.data.loc[win, list(lem["column"])].max().max(),
                     m.data[[model[c] for c in lem["column"] if c in model]].max().max())
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    panels = ((a, lem[lem.z_m == 2.3].sort_values("room"), "room"),
              (b, lem[lem.room == "F2"].sort_values("z_m"), "z_m"))
    for ax, rows, key in panels:
        for i, r in enumerate(rows.itertuples()):
            label = r.room if key == "room" else f"F2, z = {r.z_m} m"
            ax.plot(t.data.t_s, t.data[r.column], color=f"C{i}", lw=1, label=f"{label} measured")
            if r.column in model:
                ax.plot(m.data.t_s, m.data[model[r.column]], color=f"C{i}", lw=1, ls="--",
                        label=f"{label} FDS")
        for e in ("flame_out", "ventilation_start"):
            if e in ev:
                ax.axvline(ev[e], color="grey", lw=0.6, ls=":")
        ax.set_xlim(-60, 1200)
        ax.set_ylim(-0.02 * top, top)
        ax.set_xlabel("time from the ignition reference [s]")
        ax.legend(fontsize=7, frameon=False)
    a.set_ylabel("extinction coefficient $k$ [1/m] (638 nm)")
    a.set_title(f"{run}: rooms at z = 2.3 m, FDS baseline {m.case}", fontsize=9)
    b.set_title(f"{run}: room F2, all measured heights", fontsize=9)
    fig.tight_layout()
    out = P.PLOTS_DIR / "exploratory" / f"example_timeseries_{run}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:2]))
