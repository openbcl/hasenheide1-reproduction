// Validation: measured vs predicted peaks (Fig. 5) in the FDS Validation Guide convention.
// Points, the pooled statistics and the per-series bias come from validation.json; the
// printed values (delta, sigma_M, sigma_E) are the numbers.tex macros checked at build
// time. Lines as in the paper: 1:1, delta, +-2 sigma_E about 1:1, +-2 sigma_M about delta.
import { h, about, refChips, sourceLine, segmented, checks, table, sym, loadPlotly, themeColors, rgba, baseLayout, latest, rebuild, drawChart, vis,
         insideLegend, LEGEND, onLeave } from "../util.js";
import { REF } from "../paper_refs.js";
import { TOKENS } from "../style_tokens.js";

// sub: the subscript of delta as Plotly markup (chart) and as text (page)
const GROUPS = [
  { value: "Extinction", label: "Extinction", sub: "k", axis: "peak k at 638 nm / m⁻¹", log: true, range: [0.1, 1.4], unit: "1/m", fmt: 3,
    ticks: [0.1, 0.2, 0.5, 1] },
  { value: "Upper-layer T", label: "Upper-layer temperature", sub: "T<sub>u</sub>", axis: "peak ΔT<sub>u</sub> / °C", log: true, range: [1, 100],
    unit: "°C", fmt: 1, ticks: [1, 2, 5, 10, 20, 50, 100] },
  { value: "Layer height", label: "Layer height", sub: "z", axis: "minimum z<sub>int</sub> / m", log: false, unit: "m", fmt: 2 },
];
// the same subscript on the page: T<sub>u</sub> -> T, <sub>u</sub>
const subNode = s => s.includes("<sub>") ? [s.split("<sub>")[0], h("sub", {}, s.split("<sub>")[1].replace("</sub>", ""))] : s;
// sensor names of the metric files, shortened for display
const sensorName = s => s.replace(/^Extinction coefficient /, "").replace(/^Temp\. Tree (\d) \((.*)\)$/, "TC tree $1, $2")
  .replace(/^Plume Impingement Temperature$/, "ceiling TC, F1").replace(/^(F\d) dT_u$/, "$1 upper layer").replace(/^(F\d) z_min$/, "$1 interface");
const PLOTLY_SYMBOL = { circle: "circle-open", square: "square-open", "triangle-up": "triangle-up-open", diamond: "diamond-open" };

export async function render(root, { params, meta, load, setParams, views }) {
  const view = views.find(v => v.id === "validation");
  const [val, Plotly] = await Promise.all([load("validation.json"), loadPlotly()]);
  const excludedIn = q => val.points.some(p => p.group === q && !p.in_stat && p.exp > 0 && p.sim > 0);
  const repo = meta.citation.repository;
  const label = Object.fromEntries(meta.series.map(s => [s.key, s.label]));
  const st = { group: GROUPS.some(g => g.value === params.q) ? params.q : "Extinction", excluded: params.excl === "1" };

  const controls = h("div", { class: "controls" });
  const title = h("p", { class: "stat-line" });
  const chart = h("div", { class: "chart square", role: "img", "aria-label": "measured versus predicted peak values" });
  const note = h("p", { class: "chart-note" });
  const status = h("p", { class: "sr-only", "aria-live": "polite" });
  const tables = h("div");

  root.append(
    h("h1", {}, view.title), refChips(view, REF),
    about(sym("Peak values predicted by FDS against the measured ones, pooled over the three series: the bias factor δ " +
      "(FDS / measured, estimated from the log ratios) and the relative model standard deviation σ_{M} in the convention " +
      `of the FDS Validation Guide, with the experimental uncertainty σ_{E} (for the extinction: ${REF.smExtUncertainty}). The extinction ` +
      "statistic uses the LEM positions only; the co-located SICK beams would count those positions twice."),
      `${REF.secCfdResults}, ${REF.figScatter}`),
    controls, title, chart, note, status, tables,
    sourceLine(repo, ["results/validation/fds_metrics/"].concat(val.source.filter(s => !s.includes("<series>")))));

  function drawControls() {
    const any = excludedIn(st.group);
    rebuild(controls,
      segmented("Quantity", GROUPS, st.group, v => { st.group = v; update(); }),
      checks("Show", [{ value: "excl", label: "Excluded pairs", checked: st.excluded && any, disabled: !any,
        title: any ? "pairs outside the pooled statistic: the co-located SICK beams" : "no pair of this quantity is excluded" }],
        (_, on) => { st.excluded = on; update(); }));
  }

  const update = latest(async stale => {
    setParams({ q: st.group === "Extinction" ? null : st.group, excl: st.excluded ? "1" : null });
    drawControls();
    const c = themeColors();
    const g = GROUPS.find(x => x.value === st.group);
    const stat = val.pooled.find(p => p.group === st.group);
    const pts = val.points.filter(p => p.group === st.group);
    const inS = pts.filter(p => p.in_stat), outS = pts.filter(p => !p.in_stat && p.exp > 0 && p.sim > 0);

    // axis range: as in the paper (fixed for the two log panels; the layer height padded
    // by 40 % of the data span and snapped to 0.1)
    let [lo, hi] = g.range || [];
    if (!g.range) {
      const v = inS.flatMap(p => [p.exp, p.sim]);
      const mn = Math.min(...v), mx = Math.max(...v), pad = 0.4 * (mx - mn);
      lo = Math.round((mn - pad) * 10) / 10; hi = Math.round((mx + pad) * 10) / 10;
    }
    const xs = g.log ? Array.from({ length: 50 }, (_, i) => lo * Math.pow(hi / lo, i / 49)) : [lo, hi];
    const d = stat.delta.value, sm = stat.sigma_M.value, se = stat.sigma_E.value;
    // two keys: the points inside the plot, top left, where a parity plot has no data; the
    // reference lines in one row above the plot (bottom right is crossed by the lower band
    // where the bias factor is below 1)
    const line = (f, name, color, dash, width, show = false) => ({
      x: xs, y: xs.map(f), type: "scatter", mode: "lines", name, showlegend: show, hoverinfo: "skip",
      line: { color, dash, width }, legend: "legend2", legendgroup: name || undefined });
    const traces = [
      line(x => x, "1:1", c.fg, "solid", 1, true),
      line(x => x * Math.exp(2 * se), "±2σ<sub>E</sub> about 1:1", c.fg, "dash", 0.8, true),
      line(x => x * Math.exp(-2 * se), "", c.fg, "dash", 0.8),
      line(x => d * x, `δ<sub>${g.sub}</sub> = ${stat.delta.text}`, c.fds, "solid", 1.2, true),
      line(x => d * x * Math.exp(2 * sm), `±2σ<sub>M</sub> about δ<sub>${g.sub}</sub>`, c.fds, "dot", 1.3, true),
      line(x => d * x * Math.exp(-2 * sm), "", c.fds, "dot", 1.3),
    ];
    // the unnamed lower bands toggle with their upper partners
    traces[2].legendgroup = traces[1].name; traces[5].legendgroup = traces[4].name;
    if (st.group === "Upper-layer T") {
      // the paper shows all thermocouples faintly behind the upper-layer statistic
      const all = val.points.filter(p => p.group === "Temperature" && p.in_stat);
      const dT = val.pooled.find(p => p.group === "Temperature").delta.text;
      traces.push({ x: all.map(p => p.exp), y: all.map(p => p.sim), type: "scatter", mode: "markers",
        name: `all thermocouples (δ<sub>T</sub> = ${dT})`, legendrank: 1010, marker: { size: 5, color: rgba(c.muted, 0.35), line: { width: 0 } },
        text: all.map(p => `${sensorName(p.sensor)}<br>${p.series}`), hovertemplate: "%{text}<br>measured %{x:.1f}, FDS %{y:.1f} °C<extra></extra>" });
    }
    if (st.excluded && outS.length) {
      traces.push({ x: outS.map(p => p.exp), y: outS.map(p => p.sim), type: "scatter", mode: "markers", name: "excluded pairs", legendrank: 1020,
        marker: { symbol: "x-thin-open", size: 8, color: c.muted, line: { width: 1.3, color: c.muted } },
        text: outS.map(p => `${sensorName(p.sensor)}<br>${p.series} · ${p.instrument === "SICK" ? "co-located SICK" : "below the signal floor"}`),
        hovertemplate: `%{text}<br>measured %{x:.${g.fmt}f}, FDS %{y:.${g.fmt}f} ${g.unit}<extra></extra>` });
    }
    for (const s of meta.series) {
      const sel = inS.filter(p => p.series === s.key), tok = TOKENS.series[s.style];
      traces.push({ x: sel.map(p => p.exp), y: sel.map(p => p.sim), type: "scatter", mode: "markers", name: s.label,
        marker: { symbol: PLOTLY_SYMBOL[tok.symbol], size: 10, color: vis(tok.color), line: { width: 1.6 } },
        text: sel.map(p => sensorName(p.sensor)), customdata: sel.map(p => p.sim / p.exp),
        hovertemplate: `%{text}<br>${s.key}<br>measured %{x:.${g.fmt}f}, FDS %{y:.${g.fmt}f} ${g.unit}<br>FDS / measured %{customdata:.2f}<extra></extra>` });
    }
    const annotations = [];
    if (st.group === "Extinction") {
      // the most discrepant pair, flagged in the paper
      const j = inS.reduce((b, p, i) => p.sim / p.exp > inS[b].sim / inS[b].exp ? i : b, 0);
      annotations.push({ x: Math.log10(inS[j].exp), y: Math.log10(inS[j].sim), text: `${inS[j].room}, z = ${inS[j].z} m`,
        ax: -50, ay: -30, arrowcolor: c.muted, arrowwidth: 1, font: { size: 11, color: c.muted } });
    }
    const ax = { title: { text: "measured " + g.axis }, type: g.log ? "log" : "linear",
                 range: g.log ? [Math.log10(lo), Math.log10(hi)] : [lo, hi], ...(g.ticks ? { tickvals: g.ticks } : {}) };
    const font = { size: chart.clientWidth < 500 ? 11 : 12 };
    const layout = baseLayout(c, {
      annotations, margin: { l: 70, r: 16, t: 10, b: 70 },
      legend: insideLegend(c, { x: 0.02, xanchor: "left", y: 0.98, yanchor: "top", font }),
      legend2: { ...LEGEND, font },
      xaxis: { ...ax, constrain: "domain" },
      yaxis: { ...ax, title: { text: "predicted " + g.axis }, scaleanchor: "x", scaleratio: 1, constrain: "domain" },
    });
    if (stale()) return;
    await drawChart(chart, traces, layout, `validation_${g.label.toLowerCase().replace(/[^a-z]+/g, "_")}`,
                    `Measured (x) vs FDS (y) peaks, ${g.label.toLowerCase()} (${g.unit}): δ<sub>${g.sub}</sub> = ${stat.delta.text}, ` +
                    `σ<sub>M</sub> = ${stat.sigma_M.text}, σ<sub>E</sub> = ${stat.sigma_E.text}, n = ${stat.n}`);
    // the square axes are centred in the plot area, legends are placed on it: move both keys
    // onto the axes actually drawn
    const xd = chart._fullLayout.xaxis.domain, yd = chart._fullLayout.yaxis.domain;
    if (xd[0] > 0.001 || yd[1] < 0.999)
      await Plotly.relayout(chart, { "legend.x": xd[0] + 0.02 * (xd[1] - xd[0]), "legend.y": yd[1] - 0.02 * (yd[1] - yd[0]),
                                     "legend2.x": xd[0], "legend2.y": yd[1] + 0.02 });

    title.replaceChildren(h("b", {}, "δ", h("sub", {}, subNode(g.sub)), ` = ${stat.delta.text}`),
      ", σ", h("sub", {}, "M"), ` = ${stat.sigma_M.text}, σ`, h("sub", {}, "E"), ` = ${stat.sigma_E.text} (n = ${stat.n})`,
      ...(stat.floored ? [" · σ", h("sub", {}, "M"), " at its floor (= σ", h("sub", {}, "E"), "): not resolved from the data"] : []));
    note.textContent = "Hover a point for its sensor and series; select a legend entry (mouse or touch) to hide or show it. " +
      (st.group === "Extinction"
        ? "Excluded: the co-located SICK beams (no extinction pair falls below the package's floor of " +
          `${val.signal_min.Extinction} 1/m). Annotated: the most discrepant pair, discussed in ${REF.secDiscHeight}.`
        : outS.length ? `Excluded: ${outS.length} pair(s) below the signal floor (${REF.secCfdResults}).`
        : `No pair of this quantity is excluded (n = ${stat.n}).`);
    status.textContent = `${g.label}: bias factor ${stat.delta.text}, n = ${stat.n}.`;

    // per-series bias (extinction) and the pairs of this panel
    const rows = pts.filter(p => p.exp > 0 && p.sim > 0).sort((a, b) => a.series.localeCompare(b.series) || a.sensor.localeCompare(b.sensor))
      .map(p => [p.series, sensorName(p.sensor), p.exp.toFixed(g.fmt), p.sim.toFixed(g.fmt), (p.sim / p.exp).toFixed(2),
                 p.in_stat ? "yes" : (p.instrument === "SICK" ? "no (co-located SICK)" : "no (below signal floor)")]);
    tables.replaceChildren(...[
      st.group === "Extinction" ? h("div", {},
        h("h2", {}, "Bias per series"),
        table({ caption: "Extinction bias factor δ_{k} per series (paper values)", header: ["Series", "", "δ_{k}", "n"], numeric: [2, 3],
                rows: val.per_series.map(s => [s.series, label[s.series], s.delta.text, String(s.n)]) })) : null,
      h("h2", {}, "Pairs"),
      table({ caption: `Measured and predicted peaks, ${g.label.toLowerCase()} (${g.unit})`,
              header: ["Series", "Sensor", "Measured", "FDS", "FDS / measured", "In the statistic"], numeric: [2, 3, 4], rows }),
    ].filter(Boolean));
  }, err => { note.textContent = `Could not draw the chart: ${err.message}`; });

  drawControls();
  return async () => {
    await update();
    const onTheme = () => update();
    // the keys follow the axes: redraw once the width has settled
    let timer = 0, width = chart.clientWidth;
    const onResize = () => { clearTimeout(timer); timer = setTimeout(() => {
      if (chart.isConnected && chart.clientWidth !== width) { width = chart.clientWidth; update(); } }, 250); };
    window.addEventListener("themechange", onTheme);
    window.addEventListener("resize", onResize);
    onLeave(chart, () => { clearTimeout(timer); window.removeEventListener("themechange", onTheme); window.removeEventListener("resize", onResize); });
  };
}

