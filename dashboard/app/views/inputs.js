// Model inputs and sensitivity: the measured heat release prescribed to FDS (Fig. 3), the
// baseline parameters of the decks (Table 4) and the single-parameter sensitivity (Fig. 7).
// The tornado bars are computed by the builder with the logic of the Fig. 7 script.
import { h, about, refChips, sourceLine, table, sym, loadPlotly, themeColors, rgba, baseLayout, latest, drawChart, vis } from "../util.js";
import { REF } from "../paper_refs.js";
import { TOKENS } from "../style_tokens.js";

const QTY = [{ key: "k", title: "Peak extinction k", rooms: ["F1", "F2", "F3"] },
             { key: "dTu", title: "Peak ΔT (upper layer)", rooms: ["F1", "F2"] }];

export async function render(root, { meta, load, views }) {
  const view = views.find(v => v.id === "inputs");
  const [inp, Plotly] = await Promise.all([load("inputs.json"), loadPlotly()]);
  const repo = meta.citation.repository;
  const hrrChart = h("div", { class: "chart half", role: "img", "aria-label": "heat release rate per series" });
  const massChart = h("div", { class: "chart half", role: "img", "aria-label": "normalised fuel mass per series" });
  const tornado = h("div", { class: "chart tornado", role: "img", "aria-label": "sensitivity of the peak values to single inputs" });

  root.append(
    h("h1", {}, view.title), refChips(view, REF),
    about("FDS is not tuned to the apartment: it takes the heat release rate from the measured fuel mass loss and the soot " +
      "yield and heat of combustion from furniture-calorimeter measurements on the same fuel. The sensitivity study then " +
      `varies one input at a time (${REF.figHrr}, ${REF.tabCfdParams}, ${REF.figTornado}).`),

    h("h2", {}, `Heat release (${REF.figHrr})`),
    h("div", { class: "chart-row" }, h("div", {}, hrrChart), h("div", {}, massChart)),   // each chart with its download bar
    h("p", { class: "chart-note" }, "Series mean ± SD of the heat release rate from the mass loss and of the fuel mass " +
      "normalised by the initial charge; the peaks of the series means are " +
      meta.series.map(s => `${inp.hrr[s.key].peak.text} kW (${s.label})`).join(", ") + "."),

    h("h2", {}, `Baseline parameters (${REF.tabCfdParams})`),
    h("p", {}, "The smoke-side inputs of FDS were not fitted to the apartment: the soot yield and the heat of combustion " +
      "were measured on the same fuel in a furniture calorimeter, the mass-specific extinction coefficient follows from " +
      "a published correlation, the rest are FDS defaults or tabulated values."),
    table({ caption: `${REF.tabCfdParams}. Baseline fuel, combustion and smoke parameters (FDS keywords on &REAC; K_{m} on &SPEC)`,
            header: inp.table4.header,
            rows: inp.table4.rows.map(r => [h("span", { class: "nowrap" }, sym(r[0])), h("code", {}, r[1]),
                                            h("span", { class: "nowrap" }, sym(r[2])), h("span", { class: "wrap wide" }, sym(r[3]))]) }),
    h("p", { class: "note" }, "Soot yield per series: ",
      inp.table4.series.map((s, i) => [i ? ", " : "", `${s.ys} g/g (${s.series})`]),
      `; pooled over all six calorimeter runs ${inp.table4.pooled}. `, sym(inp.table4.checks), "."),

    h("h3", {}, "Where Y", h("sub", {}, "s"), " and ΔH", h("sub", {}, "ch"), ` come from: the calorimeter runs (${REF.tabS_rst})`),
    h("p", {}, "Six burns of the apartment fuel batch in the open-hood, oxygen-consumption furniture calorimeter, with the " +
      "pans and charges of the three series. The soot yield follows photometrically from the total smoke production (TSP), " +
      `the effective heat of combustion from the total heat release (${REF.secRst}, ${REF.smSootYield}).`),
    table({ caption: `${REF.tabS_rst}. Calorimeter runs on the apartment fuel batch`, header: inp.fuel.table_s4.header,
            rows: inp.fuel.table_s4.rows, numeric: [0, 1, 2, 3, 4] }),
    h("p", { class: "note" }, "The two 220 mm runs belong to a second calorimeter series whose heat-release scale differs " +
      "from the first by a factor k; they are not pooled for ΔH", h("sub", {}, "ch"), ", while their soot yields stay in the " +
      "pool, since the soot channel does not depend on it (note b of the paper's table)."),

    h("h3", {}, `The fuel: C7-UVCB (${REF.tabS_fuel})`),
    h("blockquote", {},
      h("p", {}, "Its supplier classification, “Hydrocarbons, C7, n-alkanes, isoalkanes, cyclics”, identifies it as a UVCB " +
        "substance (Unknown or Variable composition, Complex reaction products, or Biological materials), and it is " +
        "denoted the C7-UVCB fuel throughout this paper."),
      h("footer", {}, `${REF.secSetup}, verbatim`)),
    fuelText(inp.fuel.numbers, inp.table4.series),
    table({ caption: `${REF.tabS_fuel}. C7 composition of the fuel batch (GC-FID) and the smoke yields tabulated in SFPE Handbook Table C.13`,
            header: inp.fuel.table_s2.header, rows: inp.fuel.table_s2.rows, numeric: [3, 5] }),
    h("p", { class: "note" }, `Notes a–d to the table entries: see ${REF.tabS_fuel} in the Supplementary Material.`),

    h("h2", {}, `Sensitivity (${REF.figTornado})`),
    h("blockquote", {},
      h("p", {}, "A sensitivity study identifies the fuel-specific soot loading, not the CFD numerics, as the dominant uncertainty: " +
        "a plausible pure-n-heptane value would roughly halve the prediction and handbook yields tabulated for the fuel's " +
        "constituents would raise it by about half, so the agreement holds only where the soot yield is measured on the fuel " +
        "and kept self-consistent with the mass-specific extinction coefficient."),
      h("footer", {}, "Abstract of the paper, verbatim")),
    tornado,
    h("p", { class: "chart-note" }, "Range of the deviation of the peak value from the baseline over the cases of each input, " +
      "per room; grey: run-to-run variability of the LES (largest deviation of three random-seed realisations). " +
      "The fuel substitution is a single scenario drawn from zero; the 10 µm deposition case is not part of the range. " +
      "The upper soot-yield bound is an illustrative K", h("sub", {}, "m"), "-proxy exploration above the measured " +
      `configuration range (${inp.fuel.numbers.valRstConfigSpreadHhPct} % across the pan/charge configurations), not a ` +
      `measured uncertainty (caption of ${REF.figTornado}). Hover a bar for its cases. Details: ${REF.smSensitivity}.`),
    sourceLine(repo, inp.source));

  const errBox = h("p", { class: "chart-note", "aria-live": "polite" });
  hrrChart.closest(".chart-row").before(errBox);
  const draw = latest(async stale => {
    const c = themeColors();
    errBox.textContent = "";
    // Fig. 3: heat release and normalised mass, all series
    const band = (t, m, s, color, name, group) => [
      { x: t, y: m.map((v, i) => v - s[i]), type: "scatter", mode: "lines", line: { width: 0 }, hoverinfo: "skip", showlegend: false, legendgroup: group },
      { x: t, y: m.map((v, i) => v + s[i]), type: "scatter", mode: "lines", line: { width: 0 }, fill: "tonexty",
        fillcolor: rgba(color, 0.2), hoverinfo: "skip", showlegend: false, legendgroup: group },
      { x: t, y: m, type: "scatter", mode: "lines", name, legendgroup: group, line: { color, width: 1.6 }, customdata: s, meta: "sd",
        hovertemplate: `${name}<br>t = %{x} s<br>%{y:.3g} ± %{customdata:.2g}<extra></extra>` }];
    const hrrT = [], massT = [];
    for (const s of meta.series) {
      const d = inp.hrr[s.key], col = vis(TOKENS.series[s.style].color);
      hrrT.push(...band(d.t, d.hrr_mean, d.hrr_std, col, s.label, s.key));
      massT.push(...band(d.t, d.m_mean, d.m_std, col, s.label, s.key));
    }
    await drawChart(hrrChart, hrrT, baseLayout(c, { xaxis: { title: { text: "t / s" }, range: [-30, 360] },
      yaxis: { title: { text: "heat release rate / kW" }, range: [0, 75] } }), "heat_release_rate",
      "series mean ± SD of the heat release rate in kW (Fig. 3)");
    await drawChart(massChart, massT, baseLayout(c, { xaxis: { title: { text: "t / s" }, range: [-30, 360] },
      yaxis: { title: { text: "m / m_fuel" }, range: [0, 1.02] } }), "fuel_mass_normalised",
      "series mean ± SD of the fuel mass normalised by the charge (Fig. 3)");
    if (stale()) return;

    // Fig. 7: two panels, groups top to bottom by width, rooms offset within a group; side by
    // side on wide screens, stacked on narrow ones (where the axis titles would collide)
    const groups = inp.tornado.groups, n = groups.length;
    const stacked = tornado.clientWidth < 640;
    tornado.style.height = stacked ? "860px" : "";
    const traces = [], shapes = [];
    QTY.forEach((q, qi) => {
      const xa = qi ? "x2" : "x", ya = qi && stacked ? "y2" : "y", offs = [0.25, 0, -0.25];
      for (const [ri, room] of q.rooms.entries()) {
        const bars = groups.map(g => inp.tornado.bars.find(b => b.group === g && b.quantity === q.key && b.room === room));
        const y = groups.map((_, gi) => n - 1 - gi + offs[ri]);
        bars.forEach((b, i) => shapes.push({ type: "rect", xref: xa, yref: ya, x0: -b.noise, x1: b.noise,
          y0: y[i] - 0.11, y1: y[i] + 0.11, line: { width: 0 }, fillcolor: rgba(c.muted, 0.3), layer: "below" }));
        traces.push({ type: "bar", orientation: "h", xaxis: xa, yaxis: ya, y, base: bars.map(b => b.lo), x: bars.map(b => b.hi - b.lo),
          width: 0.2, name: room, legendgroup: room, showlegend: qi === 0,
          marker: { color: vis(inp.tornado.room_colors[room]), line: { color: c.fg, width: 0.5 } },
          customdata: bars.map(b => `${b.group}, room ${room}<br>range ${fmt(b.lo)} … ${fmt(b.hi)} % (noise ±${b.noise.toFixed(1)} %)<br>` +
            b.cases.map(x => `${x.case}: ${fmt(x.pct)} %${x.in_range ? "" : " (not in the range)"}`).join("<br>")),
          hovertemplate: "%{customdata}<extra></extra>" });
      }
    });
    // legend entry for the grey noise bands (drawn as shapes)
    traces.push({ type: "bar", orientation: "h", x: [null], y: [null], name: "run-to-run variability",
                  marker: { color: rgba(c.muted, 0.3) }, hoverinfo: "skip" });
    const ticks = { tickvals: groups.map((_, gi) => n - 1 - gi), ticktext: groups, range: [-0.6, n - 0.4] };
    const axis2 = { gridcolor: c.border, linecolor: c.muted, tickcolor: c.muted, ticks: "outside", automargin: true };
    const lay = stacked
      ? { xaxis: { domain: [0, 1], anchor: "y", title: { text: `${QTY[0].title} deviation / %` }, zeroline: true, zerolinecolor: c.muted },
          xaxis2: { ...axis2, domain: [0, 1], anchor: "y2", title: { text: `${QTY[1].title} deviation / %` }, zeroline: true, zerolinecolor: c.muted },
          yaxis: { ...ticks, showgrid: false, domain: [0.56, 1] },
          yaxis2: { ...axis2, ...ticks, showgrid: false, domain: [0, 0.44], anchor: "x2" } }
      : { xaxis: { domain: [0, 0.48], title: { text: `${QTY[0].title} deviation / %` }, zeroline: true, zerolinecolor: c.muted },
          xaxis2: { ...axis2, domain: [0.52, 1], anchor: "y", title: { text: `${QTY[1].title} deviation / %` }, zeroline: true, zerolinecolor: c.muted },
          yaxis: { ...ticks, showgrid: false } };
    await drawChart(tornado, traces, baseLayout(c, { shapes, barmode: "overlay", margin: { l: stacked ? 120 : 140, r: 16, t: 30, b: 50 }, ...lay }),
      "sensitivity_tornado", "deviation of the peak from the baseline in %, per input and room (Fig. 7); y_low/y_high = range");
  }, err => { errBox.textContent = `Could not draw the charts: ${err.message}`; });

  return async () => {
    await draw();
    const onTheme = () => draw();
    let stacked = tornado.clientWidth < 640, timer = 0;          // redraw when the tornado layout must change
    const onResize = () => { clearTimeout(timer); timer = setTimeout(() => {
      if ((tornado.clientWidth < 640) !== stacked) { stacked = !stacked; draw(); } }, 200); };
    window.addEventListener("resize", onResize);
    window.addEventListener("themechange", onTheme);
    new MutationObserver((_, obs) => { if (!tornado.isConnected) {
      window.removeEventListener("themechange", onTheme); window.removeEventListener("resize", onResize); obs.disconnect(); } })
      .observe(document.getElementById("main"), { childList: true });
  };
}

function fmt(v) { const s = (v > 0 ? "+" : "") + v.toFixed(1); return s.replace(/^-/, "−"); }

// SM S3 in short, with the printed numbers (numbers.tex, checked by the builder)
function fuelText(n, series) {
  const ys = series.map(s => s.ys);
  return h("p", {},
    `Gas chromatography (GC-FID) of the batch assigns ${n.valCoreFuelSevenNhepPct} % to n-heptane, ` +
    `${n.valCoreFuelSevenMchPct} % to methylcyclohexane, ${n.valCoreFuelSevenDmcpPct} % to cis-1,3-dimethylcyclopentane and ` +
    `${n.valCoreFuelSevenIsoPct} % to branched C`, h("sub", {}, "7"), ` paraffins; the remaining ${n.valCoreFuelSevenOpenPct} % ` +
    "are C", h("sub", {}, "7"), " isomers whose class, paraffin or naphthene, the chromatogram does not assign, so the " +
    `naphthenic fraction is ${n.valCoreFuelSevenNaphLoPct}–${n.valCoreFuelSevenNaphHiPct} %. The fuel is aliphatic; its ` +
    "mean molecular formula lies between C", h("sub", {}, "7"), "H", h("sub", {}, n.valCoreFuelSevenFormulaHLo), " and C",
    h("sub", {}, "7"), "H", h("sub", {}, n.valCoreFuelSevenFormulaHHi), " (H/C ", `${n.valCoreFuelSevenHcLo}–${n.valCoreFuelSevenHcHi}). ` +
    "Mass-weighting the smoke yields of the SFPE Handbook over this composition gives about " +
    `${n.valSfpeYsCoreFuelSevenLo}–${n.valSfpeYsCoreFuelSevenHi} g/g, well above the yields measured on this batch ` +
    `(${Math.min(...ys.map(Number)).toFixed(4)}–${Math.max(...ys.map(Number)).toFixed(4)} g/g; ${REF.smFuel}).`);
}
