// Test explorer (package data, not a paper figure): every channel of one measured test,
// grouped by quantity, with the logged events and, where fds_channels.csv maps one, the
// FDS device at the same position. Values as committed; optionally zeroed at t = 0 (as
// the paper's comparisons). Records end 1 s before the logged test_end.
import { h, about, refChips, sourceLine, segmented, checks, loadPlotly, themeColors, baseLayout, latest, rebuild, drawChart, vis,
         EXTRA_THEME_PAIRS, testName, testId, LEGEND, isDark, onLeave } from "../util.js";
import { REF } from "../paper_refs.js";

const GROUPS = [
  { value: "ext", label: "Extinction", quantities: ["light-extinction coefficient"], unit: "1/m", axis: "k / m⁻¹",
    key: "Instrument · room · height" },
  { value: "tau", label: "Transmission", quantities: ["transmission"], unit: "%", axis: "transmission / %", key: "Instrument · room · height" },
  { value: "temp", label: "Temperature", quantities: ["gas temperature", "ceiling temperature above the fire"], unit: "°C", axis: "T / °C",
    key: "Thermocouple · height" },
  { value: "mass", label: "Fuel mass", quantities: ["fuel mass on the platform scale (pan tared)"], unit: "kg", axis: "mass / kg", key: "" },
  { value: "alarm", label: "Smoke alarms", quantities: ["smoke alarm state (0/1)"], unit: "", axis: "alarm state", key: "Smoke alarm · room" },
];
// room colours of the instruments (the plan's); the tripod LEM in F2 brown, so it differs
// from the ceiling LEM in the same room; the SICK in its own red, as everywhere on the site
const ROOM_C = { F1: "#1f77b4", F2: "#ff7f0e", F3: "#2ca02c" };
const LEM1_C = { light: "#8c564b", dark: "#c49c94" };
// the 8 tree heights, low (cool) to high (warm): at least 4.7:1 against the background and
// clearly apart from each other (CIELAB distance >= 25) in both themes
const HEIGHT_C = { light: ["#3a1f8f", "#2457b8", "#0b7a99", "#13805f", "#4d7c0f", "#8a6100", "#b2470e", "#b3203c"],
                   dark: ["#a58bf2", "#6f9ff2", "#3ec3e2", "#3ed39c", "#a2d64c", "#e8b93c", "#f5904f", "#f4708a"] };
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

// exports use the light palette
HEIGHT_C.dark.forEach((d, i) => EXTRA_THEME_PAIRS.push([d, HEIGHT_C.light[i]]));
EXTRA_THEME_PAIRS.push([LEM1_C.dark, LEM1_C.light]);

// events closer than 60 s share one label, so the labels never overlap
function eventLabels(evs) {
  const out = [];
  for (const e of evs) {
    const last = out[out.length - 1];
    if (last && e.t_s - last.t1 < 60) { last.names.push(EVENT[e.event]); last.t1 = e.t_s; }
    else out.push({ t0: e.t_s, t1: e.t_s, names: [EVENT[e.event]] });
  }
  return out;
}

export async function render(root, { params, meta, load, setParams, views }) {
  const view = views.find(v => v.id === "explorer");
  await loadPlotly();
  const repo = meta.citation.repository;
  const order = meta.series.flatMap(s => s.runs);
  // ?ch= sensors picked in the plan (column names or prefixes); only known ones are kept
  const known = p => meta.channels.some(x => x.column === p || x.column.startsWith(p));
  const asked = params.ch ? params.ch.split(",").filter(Boolean) : [];
  const picked = asked.filter(known);
  // default test: the first in the list; for a sensor picked in the plan, the first that recorded it
  const recorded = id => meta.channels.some(x => x.run === id && x.status !== "excluded" &&
                                              picked.some(p => x.column === p || x.column.startsWith(p)));
  const st = { run: testId(meta, params.run) || (picked.length && order.find(recorded)) || order[0],
               group: GROUPS.some(g => g.value === params.g) ? params.g : "ext",
               fds: params.fds !== "0", zero: params.zero !== "0", ch: picked.join(","),
               tree: params.tree === "F2" ? "F2" : "F1", sick: params.sick === "1" };
  // a link with an unknown test or sensor is said, not silently replaced (no link wording is echoed)
  let notice = [params.run && !testId(meta, params.run) ? `Unknown test; showing ${testName(meta, st.run)}.` : "",
                asked.length > picked.length ? "Unknown sensor in the link; showing all channels of this kind." : ""].join(" ").trim();

  const controls = h("div", { class: "controls" });
  const chart = h("div", { class: "chart", role: "img", "aria-label": "time series of the selected test" });
  const note = h("div", { class: "chart-note" });
  const status = h("p", { class: "sr-only", "aria-live": "polite" });
  const src = h("div");
  root.append(
    h("h1", {}, view.title), refChips(view, REF),
    about("Every channel of one test as recorded (the temperatures one thermocouple tree at a time, the SICK on request), " +
      "with the events logged during the test and, where one exists, the FDS device at the same position in the baseline " +
      "run of its series. This view shows the package's time series; it is not a figure of the paper. Values are zeroed " +
      "at t = 0 by default, as in the paper's comparisons; the FDS runs cover the pre-ventilation phase only."),
    controls, chart, note, status, src);

  const select = h("select", { "aria-label": "Test", onchange: e => { st.run = e.target.value; notice = ""; update(); } },
    meta.series.map(s => h("optgroup", { label: `${s.key} (${s.label})` },
      s.runs.map(r => h("option", { value: r, selected: r === st.run }, testName(meta, r))))));

  const update = latest(async stale => {
    const name = testName(meta, st.run);
    const g = GROUPS.find(x => x.value === st.group);
    const canFds = !["mass", "alarm", "tau"].includes(g.value);
    const optical = ["ext", "tau"].includes(g.value), temp = g.value === "temp", alarm = g.value === "alarm";
    // a selection from the plan overrides the tree and SICK choices
    const pick = st.ch ? st.ch.split(",") : null;
    setParams({ run: name, g: st.group === "ext" ? null : st.group, fds: st.fds ? null : "0", zero: st.zero ? null : "0", ch: st.ch || null,
                tree: temp && !pick && st.tree === "F2" ? "F2" : null, sick: optical && !pick && st.sick ? "1" : null });
    rebuild(controls, () => [
      h("fieldset", { class: "seg" }, h("legend", {}, "Test"), select),
      segmented("Channels", GROUPS, st.group, v => { st.group = v; st.ch = ""; update(); }),
      temp && !pick ? segmented("Thermocouple tree", [{ value: "F1", label: "F1 · fire room, with ceiling TC" }, { value: "F2", label: "F2" }],
                                st.tree, v => { st.tree = v; update(); }) : null,
      checks("Show", [
        // zeroing means nothing for an on/off alarm state
        ...(alarm ? [] : [{ value: "zero", label: "Zeroed at t = 0", checked: st.zero }]),
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
    const zs = [...new Set(shown.filter(x => x.quantity === "gas temperature").map(x => x.z_m))].sort((a, b) => a - b);
    const dark = isDark(), pal = HEIGHT_C[dark ? "dark" : "light"];
    const color = x => x.quantity === "gas temperature" ? pal[zs.indexOf(x.z_m) % pal.length]
      : x.quantity.startsWith("ceiling") || x.room === "FC" ? c.fg
      : x.instrument === "SICK" ? c.sick
      : x.instrument === "LEM1" ? LEM1_C[dark ? "dark" : "light"]
      : vis(ROOM_C[x.room] || c.fg);
    const dash = x => x.instrument === "SICK" ? (x.wavelength_nm === 880 ? "dot" : "dash") : "solid";
    const zero = (y, i0) => { const y0 = y[i0]; return st.zero && !alarm && y0 !== null ? y.map(v => v === null ? null : v - y0) : y; };

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
    const annotations = eventLabels(evs).map(l => ({ x: l.t0, y: 1, xref: "x", yref: "paper", text: l.names.join(" · "), textangle: -90,
      showarrow: false, xanchor: "right", yanchor: "top", font: { size: 10, color: c.muted } }));
    // legend at the side on wide charts, below the chart on narrower ones (a side legend would
    // squeeze the plot); on wide screens the chart grows with a long legend instead of scrolling it
    const narrow = chart.clientWidth < 1000;
    const rows = traces.length + (fdsTraces.length ? 3 : 2);   // entries, group titles, legend title
    const legendH = narrow ? 19 * rows + 30 : 0;
    chart.style.height = narrow ? `${340 + legendH}px` : "";
    if (!narrow && 21 * rows + 90 > chart.clientHeight) chart.style.height = `${21 * rows + 90}px`;
    const title = { text: g.key, font: { size: 12, color: c.muted } };
    const legend = { ...LEGEND, orientation: "v", yanchor: "top", tracegroupgap: 10, groupclick: "toggleitem", traceorder: "grouped", title,
                     grouptitlefont: { size: 12, color: c.muted } };
    // the height is set here, not measured by Plotly: a legend that grows from one entry to
    // many would otherwise send its automatic margins round in circles
    await drawChart(chart, traces, baseLayout(c, { shapes, annotations, hovermode: "closest", height: chart.clientHeight,
      legend: narrow ? { ...legend, x: 0, y: -65 / 280 } : { ...legend, x: 1.02, y: 1 },
      margin: { l: 60, r: 10, t: 10, b: 50 + legendH },
      xaxis: { title: { text: "t / s (t = 0: full minute of ignition)" } },
      yaxis: { title: { text: (st.zero && !alarm ? "Δ" : "") + g.axis },
               ...(alarm ? { tickvals: [0, 1], ticktext: ["off", "on"], range: [-0.15, 1.15] } : {}) } }),
      `${name}_${g.value}`, `${name}, ${g.label.toLowerCase()}${g.unit ? ` (${g.unit})` : ""}, ` +
      `${st.zero && !alarm ? "zeroed at t = 0" : "as recorded"}; package data`);

    const odd = chans.filter(x => x.status !== "ok");
    const ign = evs.find(e => e.event === "ignition");
    note.replaceChildren(
      ...(notice ? [h("p", {}, notice)] : []),
      ...(pick ? [h("p", {}, h("b", {}, "Selected in the plan: "), shown.length ? shown.map(label).join(", ") : "not recorded in this test",
        " · ", h("button", { type: "button", class: "linklike", onclick: () => {
          // keep the tree and the SICK of the plan's selection
          if (temp && shown.length && shown.every(x => x.room === "F2")) st.tree = "F2";
          if (optical && shown.some(x => x.instrument === "SICK")) st.sick = true;
          st.ch = ""; update(); } }, "show all channels"))] : []),
      h("p", {}, `${name}: series ${run.series}, ${run.fuel_mass_g} g in the ${run.pan_mm} mm pan, ${run.date} at ${run.t0_local.slice(0, 5)}; ` +
        `${run.setup_text}; package file ${st.run}.csv. Flame-out after ${run.burning_duration_s} s (t`, h("sub", {}, "flameout"),
        `, as in ${REF.tabExperiments}), ventilation from ${run.ventilation_start_s} s; record to ${d.cut_s} s (1 s before the logged end). ` +
        (ign ? `The logged ignition follows t = 0 by ${ign.t_s} s.` : "")),
      ...odd.map(x => h("p", {}, `${x.column}: ${x.status}${x.note ? ` (${x.note})` : ""}.`)));
    status.textContent = `Showing ${name}, ${g.label.toLowerCase()}${temp && !pick ? `, tree ${st.tree}` : ""}: ${shown.length} channel(s).`;
    src.replaceChildren(sourceLine(repo, [d.source, "results/measurement/timeseries/channels.csv", "results/measurement/timeseries/events.csv"]
      .concat(fds ? [fds.source[0], "results/simulation/timeseries/fds_channels.csv"] : [])));
  }, err => {
    // a failed load must not leave the previous test's chart under the new selection
    window.Plotly.purge(chart);
    note.replaceChildren(h("p", {}, `Could not draw the chart: ${err.message}`));
  });

  return async () => {
    await update();
    const onTheme = () => update();
    // the legend moves below the chart under 1000 px: redraw when the width crosses it
    let narrow = chart.clientWidth < 1000, timer = 0;
    const onResize = () => { clearTimeout(timer); timer = setTimeout(() => {
      if (chart.isConnected && (chart.clientWidth < 1000) !== narrow) { narrow = !narrow; update(); } }, 200); };
    window.addEventListener("themechange", onTheme);
    window.addEventListener("resize", onResize);
    onLeave(chart, () => { clearTimeout(timer); window.removeEventListener("themechange", onTheme); window.removeEventListener("resize", onResize); });
  };
}
