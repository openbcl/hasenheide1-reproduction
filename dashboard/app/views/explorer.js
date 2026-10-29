// Test explorer (package data, not a paper figure): every channel of one measured test,
// grouped by quantity, with the logged events and, where fds_channels.csv maps one, the
// FDS device at the same position. Values as committed; optionally zeroed at t = 0 (as
// the paper's comparisons). Records end 1 s before the logged test_end.
import { h, about, refChips, sourceLine, segmented, checks, loadPlotly, themeColors, rgba, baseLayout, latest, rebuild, drawChart, vis, EXTRA_THEME_PAIRS, testName, testId, LEGEND } from "../util.js";
import { REF } from "../paper_refs.js";

const GROUPS = [
  { value: "ext", label: "Extinction", quantities: ["light-extinction coefficient"], unit: "1/m", axis: "k / m⁻¹",
    key: "Instrument · room · height" },
  { value: "tau", label: "Transmission", quantities: ["transmission"], unit: "%", axis: "transmission / %", key: "Instrument · room · height" },
  { value: "temp", label: "Temperature", quantities: ["gas temperature", "ceiling temperature above the fire"], unit: "°C", axis: "T / °C",
    key: "Thermocouple · height" },
  { value: "mass", label: "Fuel mass", quantities: ["fuel mass on the platform scale (pan tared)"], unit: "kg", axis: "mass / kg", key: "" },
  { value: "alarm", label: "Smoke alarms", quantities: ["smoke alarm state (0/1)"], unit: "", axis: "alarm state (0/1)", key: "Smoke alarm · room" },
];
const ROOM_C = { F1: "#1f77b4", F2: "#ff7f0e", F3: "#2ca02c", FC: "#9467bd" };
// viridis for the 8 tree heights, each section at least 3:1 against its background (WCAG 1.4.11):
// light theme 0-0.53 of the map, dark theme 0.4-1.0
const HEIGHT_C = { light: ["#440154", "#481c6e", "#463480", "#3e4c8a", "#34608d", "#2c728e", "#25858e", "#1f978b"],
                   dark: ["#2a788e", "#228d8d", "#1fa187", "#32b67a", "#5ac864", "#8ed645", "#c8e020", "#fde725"] };
const EVENT = { ignition: "ignition", flame_out: "flame-out", ventilation_start: "ventilation", window_F3_open: "window F3",
                window_F1_open: "window F1", fan_on: "fan", instrument_cleaning: "cleaning", ceiling_tc_recording_resumed: "ceiling TC resumed" };

function label(c) {
  const z = c.z_m !== null && c.z_m !== undefined ? `, ${c.z_m} m` : "";
  if (c.quantity === "light-extinction coefficient")
    return `${c.instrument} ${c.room}${z} (${c.instrument === "SICK" ? (c.wavelength_nm === 880 ? "880 nm, as measured" : "scaled to 638 nm") : "638 nm"})`;
  if (c.quantity === "transmission") return `${c.instrument} ${c.room}${z} (${c.wavelength_nm} nm)`;
  if (c.quantity === "gas temperature") return `TC tree ${c.room}${z}`;
  if (c.quantity.startsWith("ceiling")) return "ceiling TC above the fire, F1";
  if (c.quantity.startsWith("smoke")) return `${c.instrument}, ${c.room}`;
  return "fuel mass (pan tared)";
}

// the shorter legend entry: the legend title names the parts
function keyLabel(c) {
  const z = c.z_m !== null && c.z_m !== undefined ? ` · ${c.z_m} m` : "";
  if (c.quantity === "light-extinction coefficient")
    return `${c.instrument} · ${c.room}${z}` + (c.instrument === "SICK" ? (c.wavelength_nm === 880 ? ", 880 nm as measured" : ", scaled to 638 nm") : "");
  if (c.quantity === "transmission") return `${c.instrument} · ${c.room}${z} · ${c.wavelength_nm} nm`;
  if (c.quantity === "gas temperature") return `${c.room} tree${z}`;
  if (c.quantity.startsWith("ceiling")) return "ceiling, above the fire · F1";
  if (c.quantity.startsWith("smoke")) return `${c.instrument} · ${c.room}`;
  return "fuel mass (pan tared)";
}

// exports use the light palette for the heights
HEIGHT_C.dark.forEach((d, i) => EXTRA_THEME_PAIRS.push([d, HEIGHT_C.light[i]]));

export async function render(root, { params, meta, load, setParams, views }) {
  const view = views.find(v => v.id === "explorer");
  const Plotly = await loadPlotly();
  const repo = meta.citation.repository;
  const st = { run: testId(meta, params.run) || meta.runs[0].run,
               group: GROUPS.some(g => g.value === params.g) ? params.g : "ext",
               fds: params.fds !== "0", zero: params.zero !== "0", ch: params.ch || "",
               tree: params.tree === "F2" ? "F2" : "F1", sick: params.sick === "1" };

  const controls = h("div", { class: "controls" });
  const chart = h("div", { class: "chart", role: "img", "aria-label": "time series of the selected test" });
  const note = h("div", { class: "chart-note", "aria-live": "polite" });
  const src = h("div");
  root.append(
    h("h1", {}, view.title), refChips(view, REF),
    about("Every channel of one test as recorded (the temperatures one thermocouple tree at a time, the SICK on request), " +
      "with the events logged during the test and, where one exists, the FDS device at the same position in the baseline " +
      "run of its series. This view shows the package's time series; it is " +
      "not a figure of the paper. Values are zeroed at t = 0 by default, as in the paper's comparisons; the FDS runs end " +
      "before the ventilation."),
    controls, chart, note, src);

  const select = h("select", { "aria-label": "Test", onchange: e => { st.run = e.target.value; update(); } },
    meta.series.map(s => h("optgroup", { label: `${s.key} (${s.label})` },
      s.runs.map(r => h("option", { value: r, selected: r === st.run }, testName(meta, r))))));

  const update = latest(async stale => {
    const name = testName(meta, st.run);
    const g = GROUPS.find(x => x.value === st.group);
    const canFds = !["mass", "alarm", "tau"].includes(g.value);
    const optical = ["ext", "tau"].includes(g.value), temp = g.value === "temp";
    // the plan links to single sensors: ch = exact column names or prefixes, comma-separated;
    // such a selection overrides the tree and SICK choices
    const pick = st.ch ? st.ch.split(",") : null;
    setParams({ run: name, g: st.group === "ext" ? null : st.group, fds: st.fds ? null : "0", zero: st.zero ? null : "0", ch: st.ch || null,
                tree: temp && !pick && st.tree === "F2" ? "F2" : null, sick: optical && !pick && st.sick ? "1" : null });
    rebuild(controls, () => [
      h("fieldset", { class: "seg" }, h("legend", {}, "Test"), select),
      segmented("Channels", GROUPS, st.group, v => { st.group = v; st.ch = ""; update(); }),
      temp && !pick ? segmented("Thermocouple tree", [{ value: "F1", label: "F1 · fire room, with ceiling TC" }, { value: "F2", label: "F2" }],
                                st.tree, v => { st.tree = v; update(); }) : null,
      checks("Show", [
        { value: "zero", label: "Zeroed at t = 0", checked: st.zero },
        ...(optical && !pick ? [{ value: "sick", label: "SICK", checked: st.sick,
                                  title: "the SICK transmissometer (880 nm as measured and scaled to 638 nm)" }] : []),
        { value: "fds", label: "FDS at the same position", checked: st.fds && canFds, disabled: !canFds,
          title: canFds ? "FDS baseline device mapped in fds_channels.csv" : "no FDS device of the same quantity" },
      ], (k, on) => { st[k] = on; update(); })].filter(Boolean));

    const c = themeColors();
    const run = meta.runs.find(r => r.run === st.run);
    const d = await load(`ts/${st.run}.json`);
    if (stale()) return;
    const chosen = x => pick ? pick.some(p => x.column === p || x.column.startsWith(p))
      : temp ? x.room === st.tree || (st.tree === "F1" && x.quantity.startsWith("ceiling"))
      : !(optical && x.instrument === "SICK" && !st.sick);
    const chans = meta.channels.filter(x => x.run === st.run && g.quantities.includes(x.quantity) && chosen(x));
    const shown = chans.filter(x => d.columns[x.column]);
    const fds = st.fds && canFds ? await load(`fds/${run.series}.json`) : null;
    if (stale()) return;
    const fdsBy = fds ? Object.fromEntries(fds.channels.filter(x => x.measured).map(x => [x.measured, x.column])) : {};
    const zs = [...new Set(shown.map(x => x.z_m).filter(z => z !== null))].sort((a, b) => a - b);
    const pal = HEIGHT_C[document.documentElement.getAttribute("data-theme") ||
      (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")];
    const color = x => g.value === "temp" && x.z_m !== null ? pal[zs.indexOf(x.z_m) % pal.length] : vis(ROOM_C[x.room] || c.fg);
    const dash = x => x.instrument === "SICK" ? (x.wavelength_nm === 880 ? "dot" : "dash") : x.instrument === "LEM1" ? "dashdot" : "solid";
    const zero = (y, i0) => { const y0 = y[i0]; return st.zero && y0 !== null ? y.map(v => v === null ? null : v - y0) : y; };

    // the legend in two groups, measured and FDS, each entry hiding or showing its own line
    const MEAS = { legendgroup: "measured", legendgrouptitle: { text: "Measured" } };
    const SIM = { legendgroup: "fds", legendgrouptitle: { text: "FDS baseline, same position" } };
    const traces = [], fdsTraces = [];
    for (const x of shown) {
      traces.push({ x: d.t, y: zero(d.columns[x.column], d.zero_index), type: "scatter", mode: "lines", name: keyLabel(x), ...MEAS,
        line: { color: color(x), dash: dash(x), width: 1.3 },
        hovertemplate: `${label(x)}<br>t = %{x} s<br>%{y:.4g} ${g.unit}<extra>${x.column}</extra>` });
      const fc = fdsBy[x.column];
      if (fds && fc) {
        const i0 = fds.t.findIndex(t => t >= 0);
        fdsTraces.push({ x: fds.t, y: zero(fds.columns[fc], i0), type: "scatter", mode: "lines", name: keyLabel(x), ...SIM,
          line: { color: color(x), width: 2.6, dash: "longdash" },  // full colour (>= 3:1); long dashes are used by no measured line
          hovertemplate: `FDS ${fc}<br>t = %{x:.0f} s<br>%{y:.4g} ${g.unit}<extra></extra>` });
      }
    }
    traces.push(...fdsTraces);
    const evs = meta.events.filter(e => e.run === st.run && EVENT[e.event]);
    const shapes = evs.map(e => ({ type: "line", xref: "x", yref: "paper", x0: e.t_s, x1: e.t_s, y0: 0, y1: 1,
                                   line: { color: c.muted, width: 1, dash: "dot" } }));
    // labels of events closer than 60 s are staggered downwards so they do not overlap
    let lastT = -Infinity, level = 0;
    const annotations = evs.map(e => {
      level = e.t_s - lastT < 60 ? level + 1 : 0; lastT = e.t_s;
      return { x: e.t_s, y: 1 - 0.2 * (level % 4), xref: "x", yref: "paper", text: EVENT[e.event], textangle: -90,
               showarrow: false, xanchor: "right", yanchor: "top", font: { size: 10, color: c.muted } };
    });
    // legend at the side on wide screens, below the chart on narrow ones
    const narrow = chart.clientWidth < 700;
    // the plot area stays 280 px high: the extra height is all legend room below the axis title
    // rows of the legend: entries, group titles and the legend title; on wide screens the chart
    // grows with a long legend instead of scrolling it
    const rows = traces.length + (fdsTraces.length ? 3 : 2);
    const legendH = narrow ? 19 * rows + 30 : 0;
    chart.style.height = narrow ? `${340 + legendH}px` : "";
    if (!narrow && 21 * rows + 90 > chart.clientHeight) chart.style.height = `${21 * rows + 90}px`;
    const title = { text: g.key, font: { size: 12, color: c.muted } };
    const legend = { ...LEGEND, orientation: "v", yanchor: "top", tracegroupgap: 10, groupclick: "toggleitem", traceorder: "grouped", title,
                     grouptitlefont: { size: 12, color: c.muted } };
    await drawChart(chart, traces, baseLayout(c, { shapes, annotations, hovermode: "closest",
      legend: narrow ? { ...legend, x: 0, y: -65 / 280 } : { ...legend, x: 1.02, y: 1 },
      margin: { l: 60, r: 10, t: 10, b: 50 + legendH },
      xaxis: { title: { text: "t / s (from the ignition reference)" } },
      yaxis: { title: { text: (st.zero && g.value !== "alarm" ? "Δ" : "") + g.axis } } }),
      `${name}_${g.value}`, `${name}, ${g.label} (${g.unit}), ${st.zero ? "zeroed at t = 0" : "as recorded"}; package data`);

    const odd = chans.filter(x => x.status !== "ok");
    note.replaceChildren(
      ...(pick ? [h("p", {}, h("b", {}, "Selected in the plan: "), shown.length ? shown.map(label).join(", ") : "not recorded in this test",
        " · ", h("button", { type: "button", class: "linklike", onclick: () => {
          // keep the tree and the SICK of the plan's selection
          if (temp && shown.length && shown.every(x => x.room === "F2")) st.tree = "F2";
          if (optical && shown.some(x => x.instrument === "SICK")) st.sick = true;
          st.ch = ""; update(); } }, "show all channels"))] : []),
      h("p", {}, `${name}: series ${run.series}, ${run.fuel_mass_g} g in the ${run.pan_mm} mm pan, ${run.date} at ${run.t0_local.slice(0, 5)}; ` +
        `${run.setup_text}; package file ${st.run}.csv. Burning ${run.burning_duration_s} s, ventilation from ${run.ventilation_start_s} s; record to ${d.cut_s} s ` +
        "(1 s before the logged end). The time axis starts at the full minute of ignition; the logged ignition follows " +
        `${(evs.find(e => e.event === "ignition") || { t_s: "?" }).t_s} s later.`),
      ...odd.map(x => h("p", {}, `${x.column}: ${x.status}${x.note ? ` (${x.note})` : ""}.`)));
    src.replaceChildren(sourceLine(repo, [d.source, "results/measurement/timeseries/channels.csv", "results/measurement/timeseries/events.csv"]
      .concat(fds ? [fds.source[0], "results/simulation/timeseries/fds_channels.csv"] : [])));
  }, err => { note.replaceChildren(h("p", {}, `Could not draw the chart: ${err.message}`)); });

  return async () => {
    await update();
    const onTheme = () => update();
    // the legend moves below the chart on narrow screens: redraw when the width crosses 700 px
    let narrow = chart.clientWidth < 700, timer = 0;
    const onResize = () => { clearTimeout(timer); timer = setTimeout(() => {
      if ((chart.clientWidth < 700) !== narrow) { narrow = !narrow; update(); } }, 200); };
    window.addEventListener("themechange", onTheme);
    window.addEventListener("resize", onResize);
    new MutationObserver((_, obs) => { if (!chart.isConnected) {
      window.removeEventListener("themechange", onTheme); window.removeEventListener("resize", onResize); obs.disconnect(); } })
      .observe(document.getElementById("main"), { childList: true });
  };
}
