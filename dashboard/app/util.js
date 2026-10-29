// Small DOM and formatting helpers shared by the views.

// Repository links for source files (the site itself serves only dashboard/).
export const REPO_REF = "main";

export function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

// Tests are shown as <series>_R<n> (meta.runs[].name, numbered in the order run); the package
// files keep their ids (Hep_160_S2_R1). Links may carry either.
export const testName = (meta, id) => (meta.runs.find(r => r.run === id) || {}).name || id;
export const testId = (meta, p) => (meta.runs.find(r => r.name === p || r.run === p) || {}).run;

export function fmtBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} kB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

export function repoLink(repo, path) {
  return h("a", { href: `${repo}/blob/${REPO_REF}/${path}`, rel: "noopener" }, h("code", {}, path));
}

// "Data: <path>, <path>" line under a view or figure.
export function sourceLine(repo, paths, label = "Data") {
  const list = [].concat(paths);
  const parts = [];
  list.forEach((p, i) => { if (i) parts.push(", "); parts.push(repoLink(repo, p)); });
  return h("p", { class: "source" }, `${label}: `, parts);
}

// Paper references of a view as chips, plus its kind: paper figures/tables, or package
// data without a paper figure (so an explorer view is never read as a published result).
export function refChips(view, REF) {
  return h("p", { class: "chips" },
    view.kind === "package"
      ? h("span", { class: "chip kind-package", title: "Data of the reproduction package; not a figure of the paper" }, "package data")
      : h("span", { class: "chip kind-paper", title: "Shows figures or tables of the paper" }, "paper"),
    (view.refs || []).map(k => h("span", { class: "chip" }, REF[k])));
}

export function viewHeader(view, REF) {
  return [h("h1", {}, view.title), refChips(view, REF)];
}

// "What this shows" box: short factual text plus the paper reference.
export function about(text, ref) {
  return h("section", { class: "about", "aria-label": "What this shows" },
    h("h2", {}, "What this shows"), h("p", {}, text, ref ? ` (${ref})` : ""));
}

// Symbol markup of the builder: X_{...} -> X<sub>...</sub>, X^{...} -> X<sup>...</sup>
// (formula symbols such as Y_{s}, ΔH_{ch}, C_{7}H_{16}, λ^{−1.0088}); other values pass through.
export function sym(text) {
  if (typeof text !== "string" || !/[_^]\{/.test(text)) return text;
  const out = [], re = /([_^])\{([^}]*)\}/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    out.push(h(m[1] === "_" ? "sub" : "sup", {}, m[2]));
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return h("span", {}, out);
}

export function table({ caption, header, rows, numeric = [] }) {
  return h("div", { class: "table-wrap", tabindex: "0", role: "region", "aria-label": caption || "table" },
    h("table", {},
      caption ? h("caption", {}, sym(caption)) : null,
      h("thead", {}, h("tr", {}, header.map((c, i) => h("th", { scope: "col", class: numeric.includes(i) ? "num" : null }, sym(c))))),
      h("tbody", {}, rows.map(r => h("tr", {}, r.map((c, i) => h("td", { class: numeric.includes(i) ? "num" : null }, sym(c))))))));
}

// ---------------------------------------------------------------- charts
// Plotly (vendor/, cartesian bundle) is loaded on first use only.
let plotlyPromise = null;
export function loadPlotly() {
  if (window.Plotly) return Promise.resolve(window.Plotly);
  if (!plotlyPromise) {
    plotlyPromise = new Promise((resolve, reject) => {
      const el = document.createElement("script");
      el.src = "vendor/plotly-cartesian-2.35.2.min.js";
      // subresource integrity of the vendored file (vendor/README.md)
      el.integrity = "sha384-gKF7EaMDoWW1zLWkouldmVWF5jqEKrAswAciW73iNzqlomabVVPO60XkJvL5q/Ie";
      el.onload = () => resolve(window.Plotly);
      el.onerror = () => { plotlyPromise = null; reject(new Error("could not load vendor/plotly-cartesian-2.35.2.min.js")); };
      document.head.append(el);
    });
  }
  return plotlyPromise;
}

// Colours of the active theme (CSS tokens), so charts follow light/dark.
export function themeColors() {
  const cs = getComputedStyle(document.documentElement);
  const v = n => cs.getPropertyValue(n).trim();
  return { fg: v("--fg"), muted: v("--muted"), border: v("--border"), panel: v("--panel"), lem: v("--lem"),
           sick: v("--sick"), fds: v("--fds"), window: v("--window"), accent: v("--accent") };
}

export function rgba(hex, a) {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex.trim());
  return m ? `rgba(${parseInt(m[1], 16)},${parseInt(m[2], 16)},${parseInt(m[3], 16)},${a})` : hex;
}

// Legends: above the plot by default, with line samples long enough to tell dashes from
// dots. Views pass their own position as { ...LEGEND, x, y, ... }.
export const LEGEND = { orientation: "h", x: 0, xanchor: "left", y: 1.02, yanchor: "bottom", font: { size: 12 },
                        itemwidth: 40, tracegroupgap: 4, bgcolor: "rgba(0,0,0,0)" };
// a legend set inside the plot area, on a panel that hides the grid behind it
export const insideLegend = (c, pos) => ({ ...LEGEND, orientation: "v", bgcolor: rgba(c.panel, 0.88), bordercolor: c.border,
                                            borderwidth: 1, ...pos });

export function baseLayout(c, extra = {}) {
  const axis = { gridcolor: c.border, zerolinecolor: c.border, linecolor: c.muted, tickcolor: c.muted, ticks: "outside", automargin: true };
  return {
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: getComputedStyle(document.body).fontFamily, color: c.fg, size: 13 },
    margin: { l: 60, r: 16, t: 10, b: 50 }, hovermode: "closest",
    hoverlabel: { bgcolor: c.panel, bordercolor: c.border, font: { color: c.fg } },
    legend: LEGEND,
    ...extra,
    xaxis: { ...axis, ...(extra.xaxis || {}) }, yaxis: { ...axis, ...(extra.yaxis || {}) },
  };
}

export const PLOT_CONFIG = {
  responsive: true, displaylogo: false,
  modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
  toImageButtonOptions: { format: "png", scale: 2 },
};

// Segmented control (radio group) and checkboxes, keyboard-accessible.
let uid = 0;
export function segmented(label, options, value, onChange) {
  const name = `seg${++uid}`;
  return h("fieldset", { class: "seg" }, h("legend", {}, label),
    options.map(o => h("label", { class: o.disabled ? "disabled" : null, title: o.title || null },
      h("input", { type: "radio", name, value: o.value, checked: String(o.value) === String(value), disabled: o.disabled,
                   onchange: e => onChange(e.target.value) }),
      h("span", {}, o.label))));
}

export function checks(label, options, onChange) {
  return h("fieldset", { class: "seg checks" }, h("legend", {}, label),
    options.map(o => h("label", { class: o.disabled ? "disabled" : null, title: o.title || null },
      h("input", { type: "checkbox", value: o.value, checked: o.checked, disabled: o.disabled,
                   onchange: e => onChange(o.value, e.target.checked) }),
      h("span", {}, o.label))));
}

// ---------------------------------------------------------------- downloads
// Exports are always in the light (print) theme with an opaque white background, whatever
// the screen theme, so a figure saved in dark mode is readable on paper and slides.
const TOKEN_NAMES = ["--fg", "--muted", "--border", "--panel", "--bg", "--lem", "--sick", "--fds", "--window", "--accent"];
export const EXTRA_THEME_PAIRS = [];               // [darkHex, lightHex] registered by views (e.g. palettes)

function tokensFor(theme) {
  const root = document.documentElement, prev = root.getAttribute("data-theme");
  root.setAttribute("data-theme", theme);           // read synchronously and restore: no repaint in between
  const cs = getComputedStyle(root), v = Object.fromEntries(TOKEN_NAMES.map(n => [n, cs.getPropertyValue(n).trim().toLowerCase()]));
  prev === null ? root.removeAttribute("data-theme") : root.setAttribute("data-theme", prev);
  return v;
}
const rgbOf = hex => { const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex); return m ? m.slice(1).map(x => parseInt(x, 16)).join(",") : null; };

const isDark = () => (document.documentElement.getAttribute("data-theme") ||
  (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark";

// a JSON-able copy of the figure; in the dark theme every dark colour is replaced by its
// light counterpart in one pass (hex and the rgba() triplets), so replacements never chain
function printFigure(gd) {
  let json = JSON.stringify({ data: gd.data, layout: gd.layout });
  if (isDark()) {
    const dark = tokensFor("dark"), light = tokensFor("light"), hex = new Map(), rgb = new Map();
    for (const [d, l] of TOKEN_NAMES.map(n => [dark[n], light[n]]).concat(EXTRA_THEME_PAIRS)) {
      if (!d || !l || d.toLowerCase() === l.toLowerCase() || hex.has(d.toLowerCase())) continue;
      hex.set(d.toLowerCase(), l);
      if (rgbOf(d) && rgbOf(l)) rgb.set(rgbOf(d), rgbOf(l));
    }
    json = json.replace(/#[0-9a-f]{6}\b/gi, m => hex.get(m.toLowerCase()) || m)
               .replace(/rgba\((\d+,\d+,\d+),/g, (m, t) => rgb.has(t) ? `rgba(${rgb.get(t)},` : m);
  }
  const fig = JSON.parse(json);
  fig.layout.paper_bgcolor = "#ffffff"; fig.layout.plot_bgcolor = "#ffffff";
  return fig;
}

function saveBlob(blob, filename) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = filename;
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

export async function exportImage(gd, format, filename) {
  const fig = printFigure(gd), full = gd._fullLayout;
  const url = await window.Plotly.toImage(fig, { format, width: full.width, height: full.height, scale: format === "png" ? 2 : 1 });
  saveBlob(dataUrlToBlob(url), `${filename}.${format}`);
}

// data: URL -> Blob without fetch() (the CSP's connect-src does not allow data: URLs)
function dataUrlToBlob(url) {
  const i = url.indexOf(","), head = url.slice(5, i), body = url.slice(i + 1);
  const type = head.split(";")[0];
  if (head.endsWith(";base64")) {
    const bin = atob(body), bytes = new Uint8Array(bin.length);
    for (let k = 0; k < bin.length; k++) bytes[k] = bin.charCodeAt(k);
    return new Blob([bytes], { type });
  }
  return new Blob([decodeURIComponent(body)], { type });
}

// the plotted data in long format: one row per point of every named trace
export function chartCsv(gd, source) {
  const rows = [["trace", "x", "y", "y_low", "y_high", "label"]];
  for (const t of gd.data) {
    if (!t.name || t.hoverinfo === "skip" && !t.base) continue;
    const ys = t.y || [], xs = t.x || [];
    for (let i = 0; i < Math.max(xs.length, ys.length); i++) {
      if (t.type === "bar") rows.push([t.name, ys[i], "", t.base[i], t.base[i] + xs[i], (t.customdata || [])[i] || ""]);
      else if (xs[i] !== null && xs[i] !== undefined) {
        const sd = t.meta === "sd" && ys[i] !== null && t.customdata[i] !== null ? t.customdata[i] : null;   // mean ± SD traces
        rows.push([t.name, xs[i], ys[i] ?? "", sd === null ? "" : ys[i] - sd, sd === null ? "" : ys[i] + sd,
                   (Array.isArray(t.text) ? t.text[i] : "") || ""]);
      }
    }
  }
  const esc = v => { const s = String(v ?? "").replace(/<br>/g, "; "); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  return `# ${source}\n` + rows.map(r => r.map(esc).join(",")).join("\n") + "\n";
}

// Plotly config with the download buttons: PNG and SVG (print theme) and the data as CSV
export function plotConfig(filename, source = "Hasenheide dashboard; data from the reproduction package") {
  const btn = (name, title, icon, click) => ({ name, title, icon, click });
  const P = window.Plotly;
  return {
    ...PLOT_CONFIG,
    modeBarButtonsToRemove: [...PLOT_CONFIG.modeBarButtonsToRemove, "toImage"],
    modeBarButtonsToAdd: [
      btn("png", "Download as PNG (print colours)", P.Icons.camera, gd => exportImage(gd, "png", filename)),
      btn("svg", "Download as SVG (print colours)", P.Icons.camera_retro || P.Icons.camera, gd => exportImage(gd, "svg", filename)),
      btn("csv", "Download the plotted data (CSV)", P.Icons.disk, gd => saveBlob(new Blob([chartCsv(gd, source)], { type: "text/csv" }), `${filename}.csv`)),
    ],
  };
}

// SVG figures of the page (plan, section): computed styles inlined, print theme, white background
export function exportSvgElement(svg, filename) {
  const root = document.documentElement, prev = root.getAttribute("data-theme");
  root.setAttribute("data-theme", "light");
  const clone = svg.cloneNode(true);
  const props = ["fill", "fill-opacity", "stroke", "stroke-width", "stroke-dasharray", "stroke-linecap", "opacity",
                 "font-family", "font-size", "font-weight"];
  const src = [svg, ...svg.querySelectorAll("*")], dst = [clone, ...clone.querySelectorAll("*")];
  src.forEach((el, i) => {
    const cs = getComputedStyle(el);
    dst[i].setAttribute("style", props.map(p => `${p}:${cs.getPropertyValue(p)}`).join(";"));
  });
  prev === null ? root.removeAttribute("data-theme") : root.setAttribute("data-theme", prev);
  const vb = svg.viewBox.baseVal;
  const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  for (const [k, v] of Object.entries({ x: vb.x, y: vb.y, width: vb.width, height: vb.height, fill: "#ffffff" })) bg.setAttribute(k, v);
  clone.insertBefore(bg, clone.firstChild);
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", `${Math.round(vb.width * 100)}`); clone.setAttribute("height", `${Math.round(vb.height * 100)}`);
  clone.querySelectorAll("a").forEach(a => a.removeAttribute("href"));
  saveBlob(new Blob([new XMLSerializer().serializeToString(clone)], { type: "image/svg+xml" }), `${filename}.svg`);
}

// ---------------------------------------------------------------- view helpers
// Only the latest call of an async redraw may draw, so quick selection changes cannot be
// overtaken by an older, slower one; errors are shown instead of failing silently.
export function latest(fn, onError) {
  let seq = 0;
  return async (...args) => {
    const my = ++seq;
    try { await fn(() => my !== seq, ...args); }
    catch (err) { console.error(err); if (my === seq) onError(err); }
  };
}

// Replace a container's controls and give the focus back to the same control (identified
// by its group legend or aria-label and its value), so keyboard users keep their place.
function focusKey(el) {
  const group = (el.closest("fieldset")?.querySelector("legend")?.textContent) || el.getAttribute("aria-label") || "";
  return `${el.tagName}|${group}|${el.type === "radio" || el.type === "checkbox" ? el.value : ""}`;
}
// Pass a function that builds the children: it runs after the focused control is noted
// (building may move a reused element, e.g. a <select>, out of the document).
export function rebuild(container, ...children) {
  const a = document.activeElement, key = a && container.contains(a) ? focusKey(a) : null;
  container.replaceChildren(...(typeof children[0] === "function" ? [].concat(children[0]()) : children));
  if (key) [...container.querySelectorAll("input, select, button")].find(e => focusKey(e) === key)?.focus();
}

// Colours below 3:1 against the light background are darkened there (WCAG 1.4.11): the
// orange of plot_style.py (150 g series, room F2). The dark theme keeps the original.
const LIGHT_DARKER = { "#ff7f0e": "#c25e00" };
export function vis(hex) { return isDark() ? hex : (LIGHT_DARKER[String(hex).toLowerCase()] || hex); }

// Draw a chart with keyboard-operable downloads below it (the Plotly toolbar is mouse-only)
// and a text alternative naming its content.
export async function drawChart(el, traces, layout, filename, source) {
  await window.Plotly.react(el, traces, layout, plotConfig(filename, source));
  el.setAttribute("aria-label", `Chart: ${source}. The plotted data can be downloaded as CSV below the chart.`);
  let bar = el.nextElementSibling;
  if (!bar || !bar.classList.contains("chart-downloads")) { bar = h("p", { class: "downloads chart-downloads" }); el.after(bar); }
  const b = (label, title, fn) => h("button", { type: "button", class: "linklike", title, onclick: fn }, label);
  bar.replaceChildren("Download: ",
    b("PNG", "image in print colours", () => exportImage(el, "png", filename)), " · ",
    b("SVG", "vector image in print colours", () => exportImage(el, "svg", filename)), " · ",
    b("data (CSV)", "the plotted data", () => saveBlob(new Blob([chartCsv(el, source)], { type: "text/csv" }), `${filename}.csv`)));
}
