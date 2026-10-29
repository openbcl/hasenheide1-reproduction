// Extinction: measured vs FDS per series, room and height (superset of Figs. 4 and 6).
// Everything shown is committed data: the series mean ± SD and the SICK runs from the
// files of Fig. 4 (ext_lem.csv, ext_sick.csv), the FDS beam of Fig. 6 (ext_fds.csv, or
// the FDS device file for the lower F2 heights), the single tests from the time series.
// Measured values are zeroed at t = 0 as in the paper; nothing else is computed.
import { h, about, refChips, sourceLine, segmented, checks, loadPlotly, themeColors, rgba, baseLayout, latest, rebuild, drawChart, testName } from "../util.js";
import { REF } from "../paper_refs.js";

const ROOMS = [{ value: "F1", label: "F1 · fire room" }, { value: "F2", label: "F2" }, { value: "F3", label: "F3" }];
const LAYERS = ["mean", "tests", "sick", "fds"];

export async function render(root, { params, meta, load, setParams, views }) {
  const view = views.find(v => v.id === "extinction");
  const [mx, Plotly] = await Promise.all([load("matrices.json"), loadPlotly()]);
  const repo = meta.citation.repository;
  const series = meta.series;

  // LEM channels at 638 nm per series, room and height: which runs measured them
  const lemRuns = {};                                     // series -> room -> z -> [{run, column}]
  const runSeries = Object.fromEntries(meta.runs.map(r => [r.run, r.series]));
  for (const c of meta.channels) {
    if (!/^LEM/.test(c.instrument || "") || c.wavelength_nm !== 638 || c.quantity !== "light-extinction coefficient" || c.status === "excluded") continue;
    const s = runSeries[c.run];
    ((lemRuns[s] ??= {})[c.room] ??= {})[c.z_m] ??= [];
    lemRuns[s][c.room][c.z_m].push({ run: c.run, column: c.column });
  }

  const st = {
    series: series.some(s => s.key === params.series) ? params.series : series[0].key,
    room: ROOMS.some(r => r.value === params.room) ? params.room : "F1",
    z: Number(params.z) || 2.3,
    layers: new Set((params.layers || "").split(",").filter(l => LAYERS.includes(l))),
    log: params.y === "log",
  };

  if (!st.layers.size) ["mean", "sick", "fds"].forEach(l => st.layers.add(l));   // default (also for invalid layers)

  const heights = () => Object.keys(lemRuns[st.series]?.[st.room] || {}).map(Number).sort((a, b) => a - b);
  const fixZ = () => { const hs = heights(); if (!hs.includes(st.z)) st.z = hs.includes(2.3) ? 2.3 : hs[hs.length - 1]; };
  fixZ();
  // a deep link to a height not measured in that series and room is said, not silently replaced
  // (only a well-formed number is echoed: a link cannot put its own wording on the page)
  let notice = /^\d+(\.\d+)?$/.test(params.z || "") && Number(params.z) !== st.z
    ? `z = ${Number(params.z)} m was not measured in this series and room; showing ${st.z} m. ` : "";

  const controls = h("div", { class: "controls" });
  const chart = h("div", { class: "chart", role: "img", "aria-label": "extinction coefficient over time" });
  const note = h("p", { class: "chart-note", "aria-live": "polite" });
  const srcBox = h("div");

  root.append(
    h("h1", {}, view.title), refChips(view, REF),
    about("The light-extinction coefficient k at 638 nm in the three rooms: the series mean ± SD of the LEM near the " +
      `ceiling with the SICK runs scaled to 638 nm (${REF.figExtMeasured}), and the FDS beam at the same position ` +
      `(${REF.figExtFds}). Measured values are zeroed at t = 0 as in the paper. The single tests and the lower F2 heights ` +
      "come from the per-test time series."),
    controls, chart, note, srcBox);

  function drawControls() {
    const hs = heights();
    const atCeiling = st.z === 2.3;
    const nSick = Object.keys(mx.ext_sick[st.series]?.[st.room] || {}).length;
    rebuild(controls,
      segmented("Series", series.map(s => ({ value: s.key, label: s.label, title: s.key })), st.series, v => { st.series = v; fixZ(); update(); }),
      segmented("Room", ROOMS, st.room, v => { st.room = v; fixZ(); update(); }),
      segmented("Height", [1.5, 1.9, 2.1, 2.3].map(z => ({ value: z, label: `${z} m`, disabled: !hs.includes(z),
                title: hs.includes(z) ? null : "not measured in this series and room" })), st.z, v => { st.z = Number(v); update(); }),
      checks("Show", [
        { value: "mean", label: "Mean ± SD", checked: st.layers.has("mean") && atCeiling, disabled: !atCeiling,
          title: atCeiling ? "LEM series mean ± SD (paper)" : "the paper gives the series mean for the ceiling LEMs only" },
        { value: "tests", label: "Single tests", checked: st.layers.has("tests") || !atCeiling, disabled: !atCeiling },
        { value: "sick", label: "SICK", checked: st.layers.has("sick") && atCeiling && nSick > 0, disabled: !atCeiling || !nSick,
          title: !atCeiling ? "the SICK was operated at 2.3 m" : nSick ? "SICK runs scaled to 638 nm (paper)" : "no valid SICK record in this series and room" },
        { value: "fds", label: "FDS", checked: st.layers.has("fds") },
      ], (k, on) => { on ? st.layers.add(k) : st.layers.delete(k); update(); }),
      segmented("Scale", [{ value: "lin", label: "linear" }, { value: "log", label: "log" }], st.log ? "log" : "lin",
                v => { st.log = v === "log"; update(); }));
  }

  async function traces() {
    const c = themeColors();
    const s = st.series, r = st.room, atCeiling = st.z === 2.3;
    const show = k => k === "tests" ? (st.layers.has("tests") || !atCeiling) : st.layers.has(k) && (k === "fds" || atCeiling);
    const out = [], sources = new Set();
    const metaRow = mx.ext_meta.find(m => m.series === s && m.room === r);

    if (show("tests")) {
      const runs = lemRuns[s][r][st.z];
      const data = await Promise.all(runs.map(x => load(`ts/${x.run}.json`)));
      data.forEach((d, i) => {
        const y = d.columns[runs[i].column], y0 = y[d.zero_index];
        out.push({ x: d.t, y: y.map(v => v === null ? null : v - y0), type: "scatter", mode: "lines",
                   name: testName(meta, runs[i].run), legendgroup: "tests", showlegend: i === 0,
                   line: { color: rgba(c.lem, 0.45), width: 0.9 },
                   hovertemplate: `${testName(meta, runs[i].run)}<br>t = %{x} s<br>k = %{y:.3f} 1/m<extra></extra>` });
        sources.add(d.source);
      });
      out[out.length - runs.length].name = `LEM single tests (n = ${runs.length})`;
    }
    if (show("mean")) {
      const m = mx.ext_lem[s][r];
      const lo = m.mean.map((v, i) => v === null || m.std[i] === null ? null : v - m.std[i]);
      const hi = m.mean.map((v, i) => v === null || m.std[i] === null ? null : v + m.std[i]);
      out.push({ x: m.t, y: lo, type: "scatter", mode: "lines", line: { width: 0 }, hoverinfo: "skip", showlegend: false, legendgroup: "mean" });
      out.push({ x: m.t, y: hi, type: "scatter", mode: "lines", line: { width: 0 }, fill: "tonexty", fillcolor: rgba(c.lem, 0.22),
                 hoverinfo: "skip", showlegend: false, legendgroup: "mean" });
      out.push({ x: m.t, y: m.mean, type: "scatter", mode: "lines", name: `LEM mean ± SD (n = ${metaRow.n_lem})`, legendgroup: "mean",
                 line: { color: c.lem, width: 1.6 }, customdata: m.std, meta: "sd",
                 hovertemplate: "LEM mean<br>t = %{x} s<br>k = %{y:.3f} ± %{customdata:.3f} 1/m<extra></extra>" });
      sources.add("results/validation/matrices/ext_lem.csv");
    }
    if (show("sick")) {
      const runs = Object.entries(mx.ext_sick[s]?.[r] || {});
      runs.forEach(([run, d], i) => out.push({
        x: d.t, y: d.k, type: "scatter", mode: "lines", name: i === 0 ? `SICK, scaled to 638 nm (n = ${runs.length})` : testName(meta, run),
        legendgroup: "sick", showlegend: i === 0, line: { color: rgba(c.sick, 0.7), width: 0.9 },
        hovertemplate: `SICK ${testName(meta, run)}<br>t = %{x} s<br>k = %{y:.3f} 1/m<extra></extra>` }));
      if (runs.length) sources.add("results/validation/matrices/ext_sick.csv");
    }
    if (show("fds")) {
      let x, y;
      if (atCeiling) { ({ t: x, k: y } = mx.ext_fds[s][r]); sources.add("results/validation/matrices/ext_fds.csv"); }
      else {
        const f = await load(`fds/${s}.json`);
        x = f.t; y = f.columns[`LEM_LOS_${r}_${String(st.z).replace(".", "_")}_k`];
        sources.add(f.source[0]);
      }
      out.push({ x, y, type: "scatter", mode: "lines", name: "FDS beam", line: { color: c.fds, width: 2 },
                 hovertemplate: "FDS<br>t = %{x:.0f} s<br>k = %{y:.3f} 1/m<extra></extra>" });
    }
    return { out, sources, metaRow, c };
  }

  const update = latest(async stale => {
    setParams({ series: st.series, room: st.room, z: st.z, layers: [...st.layers].join(","), y: st.log ? "log" : null });
    drawControls();
    const { out, sources, metaRow, c } = await traces();
    if (stale()) return;                            // a newer selection is already being drawn
    const shapes = [], annotations = [];
    if (metaRow) {
      shapes.push({ type: "rect", xref: "x", yref: "paper", x0: metaRow.m_vent, x1: 1500, y0: 0, y1: 1, line: { width: 0 },
                    fillcolor: rgba(c.window, 0.14), layer: "below" });
      shapes.push({ type: "line", xref: "x", yref: "paper", x0: metaRow.m_dur, x1: metaRow.m_dur, y0: 0, y1: 1,
                    line: { color: c.muted, width: 1, dash: "dash" } });
      annotations.push({ x: metaRow.m_dur, y: 1, xref: "x", yref: "paper", text: "mean flame-out", showarrow: false, xshift: 3,
                         xanchor: "left", yanchor: "top", font: { size: 11, color: c.muted } },
                       { x: metaRow.m_vent, y: 1, xref: "x", yref: "paper", text: "ventilation", showarrow: false, xshift: 3,
                         xanchor: "left", yanchor: "top", font: { size: 11, color: c.muted } });
    }
    const layout = baseLayout(c, {
      shapes, annotations,
      xaxis: { title: { text: "t / s" }, range: [-60, 1500] },
      // y range as in the paper (0-1.3 1/m); log: 0.001-3 1/m. Double-click resets to it.
      yaxis: { title: { text: "k at 638 nm / m⁻¹" }, type: st.log ? "log" : "linear", range: st.log ? [-3, 0.5] : [0, 1.3],
               ...(st.log ? { dtick: 1, exponentformat: "power" } : {}) },
    });
    await drawChart(chart, out, layout, `extinction_${st.series}_${st.room}_z${st.z}m`,
                    `extinction, ${st.series}, room ${st.room}, z = ${st.z} m, k at 638 nm in 1/m, zeroed at t = 0`);
    const ser = series.find(x => x.key === st.series);
    note.textContent = notice + `${ser.key} (${ser.label}), room ${st.room}, z = ${st.z} m. ` +
      (st.z === 2.3 ? "" : "The paper gives no series mean at this height; the tripod LEM was moved between setups. ") +
      "Shaded: ventilation phase from the mean ventilation start; dashed: mean flame-out (as in the paper). " +
      `The FDS run ends at ${st.series === "Hep_160_075" ? 900 : 1200} s, before the ventilation.` +
      (mx.cut_s[st.series] < 1500 ? ` The measured curves end at ${mx.cut_s[st.series]} s, 1 s before the earliest logged ` +
        "end of a test, as the time series do (the last sample of the paper's figure file contains the instrument switch-off)." : "");
    srcBox.replaceChildren(sourceLine(repo, [...sources]));
    notice = "";
  }, err => { note.textContent = `Could not draw the chart: ${err.message}`; });

  drawControls();
  // the chart is drawn once the view is in the document (Plotly sizes to its container)
  return async () => {
    await update();
    const onTheme = () => update();
    window.addEventListener("themechange", onTheme);
    new MutationObserver((_, obs) => { if (!chart.isConnected) { window.removeEventListener("themechange", onTheme); obs.disconnect(); } })
      .observe(document.getElementById("main"), { childList: true });
  };
}
