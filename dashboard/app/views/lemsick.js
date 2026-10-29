// LEM vs SICK: the co-located transmissometers (Sections 2.3.4, 2.5). Per run the LEM at
// 638 nm, the SICK at 880 nm as measured and the SICK scaled to 638 nm (Widmann), zeroed at
// t = 0 as in the paper; the cross-check table and the exponent test as committed. The
// key numbers are the numbers.tex macros checked at build time.
import { h, about, refChips, sourceLine, segmented, table, loadPlotly, themeColors, baseLayout, latest, rebuild, drawChart } from "../util.js";
import { REF } from "../paper_refs.js";

export async function render(root, { params, meta, load, setParams, views }) {
  const view = views.find(v => v.id === "lemsick");
  const [ls, Plotly] = await Promise.all([load("lemsick.json"), loadPlotly()]);
  const repo = meta.citation.repository;
  const k = ls.keys;
  const runs = ls.crosscheck.map(r => r.run);
  const st = { run: runs.includes(params.run) ? params.run : runs[0] };

  const controls = h("div", { class: "controls" });
  const chart = h("div", { class: "chart", role: "img", "aria-label": "LEM and SICK extinction over time" });
  const note = h("p", { class: "chart-note", "aria-live": "polite" });
  const src = h("div");
  const w = ls.widmann.find(r => r.test === "lem_sick");

  root.append(
    h("h1", {}, view.title), refChips(view, REF),
    about("The LEM (638 nm, 0.81 m path) and the SICK (880 nm, 1.6 m double pass) measured the same smoke side by side " +
      "near the ceiling. The SICK extinction is rescaled to 638 nm with the Widmann correlation (factor " +
      `${ls.widmann_factor.toFixed(2)}); the co-located records also test that correlation (${REF.secWavelength}, ${REF.secExpResults}).`),
    h("div", { class: "tiles" },
      tile(`${minus(k.mean_bias.text)} %`, "mean SICK–LEM bias", `over the ${k.n_runs.text} runs with valid SICK data`, k.mean_bias.macro),
      tile(`${k.med_dev_lo.text}–${k.med_dev_hi.text} %`, "run-level median deviation", "interquartile range across the runs", `${k.med_dev_lo.macro}, ${k.med_dev_hi.macro}`),
      tile(k.widmann_n.text, h("span", {}, "effective exponent β (K", h("sub", {}, "m"), " ∝ λ", h("sup", {}, "−β"), ")"), `${k.widmann_lo.text}–${k.widmann_hi.text} across-run IQR; Widmann: 1.0088`, k.widmann_n.macro),
      tile(`≈ ${k.factor_dev.text} %`, "constraint on the 638 nm normalisation", "from the exponent test", k.factor_dev.macro)),
    h("h2", {}, "Per run"),
    controls, chart, note, src,
    h("h2", {}, "Cross-check per run"),
    table({ caption: "SICK (scaled to 638 nm) against the co-located LEM, per run (as committed)",
            header: ["Run", "Room", "Samples (1 Hz)", "Bias (%)", "Median |deviation| (%)", "RMS deviation (%)"], numeric: [2, 3, 4, 5],
            rows: ls.crosscheck.map(r => [r.run, r.room, String(r.n), fmt(r.bias_pct, 1), fmt(r.median_abs_pct, 1), fmt(r.rms_pct, 1)]) }),
    w ? h("p", { class: "note" }, `Exponent test over ${w.n} runs: median ${fmt(w.n_median, 3)}, interquartile range ` +
      `${fmt(w.lo, 3)}–${fmt(w.hi, 3)}, range ${fmt(w.n_min, 3)}–${fmt(w.n_max, 3)}.`) : null,
    sourceLine(repo, ls.source));

  const update = latest(async stale => {
    setParams({ run: st.run === runs[0] ? null : st.run });
    rebuild(controls, segmented("Run", ls.crosscheck.map(r => ({ value: r.run, label: `${r.run} · ${r.room}` })), st.run,
      v => { st.run = v; update(); }));
    const c = themeColors();
    const row = ls.crosscheck.find(r => r.run === st.run);
    const d = await load(`ts/${st.run}.json`);
    if (stale()) return;
    const lemCol = Object.keys(d.columns).find(n => new RegExp(`^k_LEM\\d_${row.room}_z2\\.3_638nm`).test(n));
    const zeroed = name => { const y = d.columns[name], y0 = y[d.zero_index]; return y.map(v => v === null ? null : v - y0); };
    const tr = (name, label, color, dash, width) => ({ x: d.t, y: zeroed(name), type: "scatter", mode: "lines", name: label,
      line: { color, dash, width }, hovertemplate: `${label}<br>t = %{x} s<br>k = %{y:.3f} 1/m<extra></extra>` });
    const traces = [
      tr(`k_SICK_${row.room}_z2.3_880nm_per_m`, "SICK at 880 nm (as measured)", c.sick, "dot", 1.2),
      tr(`k_SICK_${row.room}_z2.3_638nm_per_m`, "SICK scaled to 638 nm", c.sick, "solid", 1.5),
      tr(lemCol, "LEM at 638 nm", c.lem, "solid", 1.5),
    ];
    await drawChart(chart, traces, baseLayout(c, {
      xaxis: { title: { text: "t / s" } }, yaxis: { title: { text: "k / m⁻¹" }, rangemode: "tozero" } }),
      `lem_sick_${st.run}`, `${st.run}, room ${row.room}, LEM and SICK extinction in 1/m, zeroed at t = 0`);
    note.textContent = `${st.run}, room ${row.room}, z = 2.3 m, zeroed at t = 0; records up to 1 s before the logged end of the test.`;
    src.replaceChildren(sourceLine(repo, [d.source]));
  }, err => { note.textContent = `Could not draw the chart: ${err.message}`; });

  return async () => {
    await update();
    const onTheme = () => update();
    window.addEventListener("themechange", onTheme);
    new MutationObserver((_, obs) => { if (!chart.isConnected) { window.removeEventListener("themechange", onTheme); obs.disconnect(); } })
      .observe(document.getElementById("main"), { childList: true });
  };
}

// typographic minus for negative numbers
function minus(t) { return String(t).replace(/^-/, "−"); }
function fmt(v, n) { return v === null || v === undefined ? "–" : minus(Number(v).toFixed(n)); }

function tile(value, label, sub, macro) {
  return h("div", { class: "tile" }, h("div", { class: "v" }, value), h("div", { class: "k" }, label),
    h("div", { class: "k" }, sub), h("div", { class: "m mono" }, macro.split(", ").map(m => `\\${m}`).join(", ")));
}
