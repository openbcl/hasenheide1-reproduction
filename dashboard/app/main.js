// Entry point: navigation, hash routing (#/view?key=value), data loading, theme.
import { h } from "./util.js";

// The views in navigation order: as little as possible, as much as needed. Everything
// else stays in the Supplementary Material and the package (listed on the overview).
// `refs` are keys of REF (paper_refs.js); `kind` is "paper" (shows paper figures and
// tables) or "package" (package data without a paper figure). `module` is loaded on
// first use; views without one are planned and listed greyed out.
export const VIEWS = [
  { id: "start", title: "Overview", module: "./views/start.js", kind: "paper", refs: ["tabExperiments", "tabAmbient", "figApartment"],
    blurb: "Key result, the apartment and its instruments, test series" },
  { id: "extinction", title: "Extinction", module: "./views/extinction.js", kind: "paper", refs: ["figExtMeasured", "figExtFds"],
    blurb: "Per room and height: single tests, series mean ± SD and the FDS beam" },
  { id: "validation", title: "Validation", module: "./views/validation.js", kind: "paper", refs: ["figScatter"],
    blurb: "Measured vs predicted peaks, bias factor δ and model scatter σM, per sensor" },
  { id: "lemsick", title: "LEM vs SICK", module: "./views/lemsick.js", kind: "paper", refs: ["secWavelength", "secExpResults"],
    blurb: "The two co-located transmissometers, wavelength scaling, bias" },
  { id: "inputs", title: "Model inputs and sensitivity", module: "./views/inputs.js", kind: "paper", refs: ["figHrr", "tabCfdParams", "figTornado"],
    blurb: "The measured heat release and smoke parameters, and which input matters most" },
  { id: "explorer", title: "Test explorer", module: "./views/explorer.js", kind: "package",
    blurb: "Every channel and logged event of one test, with the FDS device at the same position" },
  { id: "data", title: "Data and numbers", module: "./views/data.js", kind: "package", refs: ["secDataAvailability"],
    blurb: "Every number macro with its source, downloads, checksums, citation" },
];

const cache = new Map();
const TS_KEEP = 8;                                  // per-test time series kept in memory (0.3-0.4 MB each)
export function load(name) {
  if (!cache.has(name)) {
    cache.set(name, fetch(`data/${name}`).then(r => {
      if (!r.ok) throw new Error(`data/${name}: HTTP ${r.status}`);
      return r.json();
    }).catch(err => { cache.delete(name); throw err; }));   // a failed load is retried next time
    const ts = [...cache.keys()].filter(k => k.startsWith("ts/"));
    for (const k of ts.slice(0, Math.max(0, ts.length - TS_KEEP))) cache.delete(k);   // oldest first
  } else if (name.startsWith("ts/")) {              // most recently used last
    const v = cache.get(name); cache.delete(name); cache.set(name, v);
  }
  return cache.get(name);
}

function parseHash() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [id, query] = raw.split("?");
  return { id: id || "start", params: Object.fromEntries(new URLSearchParams(query || "")) };
}

// Update the selection in the URL without adding a history entry.
export function setParams(updates) {
  const { id, params } = parseHash();
  const next = { ...params, ...updates };
  for (const k of Object.keys(next)) if (next[k] === null || next[k] === undefined || next[k] === "") delete next[k];
  const q = new URLSearchParams(next).toString();
  history.replaceState(null, "", `#/${id}${q ? "?" + q : ""}`);
}

function buildNav(current) {
  const nav = document.getElementById("nav");
  const list = h("ol");
  for (const v of VIEWS) {
    list.append(h("li", {}, v.module
      ? h("a", { href: `#/${v.id}`, "aria-current": v.id === current ? "page" : null }, v.title)
      : h("span", { title: "planned" }, v.title, " ", h("small", {}, "(planned)"))));
  }
  nav.replaceChildren(list);
}

let renderToken = 0;
async function route() {
  const { id, params } = parseHash();
  const view = VIEWS.find(v => v.id === id && v.module) || VIEWS[0];
  if (view.id !== id && id !== "start") history.replaceState(null, "", "#/start");   // unknown view: say where we are
  buildNav(view.id);
  document.getElementById("nav").classList.remove("open");
  document.getElementById("menu-btn").setAttribute("aria-expanded", "false");
  const main = document.getElementById("main");
  const token = ++renderToken;
  // release the charts of the previous view (resize listeners, data)
  main.querySelectorAll(".js-plotly-plot").forEach(el => window.Plotly && window.Plotly.purge(el));
  main.replaceChildren(h("p", { class: "loading" }, "Loading…"));
  try {
    const [mod, meta] = await Promise.all([import(view.module), load("meta.json")]);
    if (token !== renderToken) return;
    const frag = document.createDocumentFragment();
    const mounted = await mod.render(frag, { params, meta, load, setParams, views: VIEWS });
    if (token !== renderToken) return;
    main.replaceChildren(frag);
    // e.g. charts that size to their container; true when the view scrolled to a target
    const placed = typeof mounted === "function" ? await mounted() : false;
    document.title = view.id === "start" ? "Hasenheide smoke extinction" : `${view.title} · Hasenheide smoke extinction`;
    return placed === true;
  } catch (err) {
    console.error(err);
    main.replaceChildren(h("h1", {}, "Could not load this view"), h("p", {}, String(err.message || err)));
  }
}

function initTheme() {
  const btn = document.getElementById("theme-btn");
  const order = ["auto", "light", "dark"];
  let cur = document.documentElement.getAttribute("data-theme") || "auto";
  // "system" follows the operating system's light/dark setting (stored internally as "auto")
  const show = () => { btn.textContent = `Theme: ${cur === "auto" ? "system" : cur}`; };
  show();
  btn.addEventListener("click", () => {
    cur = order[(order.indexOf(cur) + 1) % order.length];
    if (cur === "auto") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", cur);
    try { cur === "auto" ? localStorage.removeItem("theme") : localStorage.setItem("theme", cur); } catch (e) { /* storage blocked */ }
    show();
    window.dispatchEvent(new Event("themechange"));
  });
  // following the OS: redraw charts when its setting changes
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (!document.documentElement.getAttribute("data-theme")) window.dispatchEvent(new Event("themechange"));
  });
}

// The skip link targets #main, which the hash router would read as a view: focus instead.
function initSkip() {
  document.querySelector(".skip").addEventListener("click", e => {
    e.preventDefault();
    document.getElementById("main").focus();
  });
}

function initMenu() {
  const btn = document.getElementById("menu-btn");
  btn.addEventListener("click", () => {
    const nav = document.getElementById("nav");
    const open = nav.classList.toggle("open");
    btn.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("keydown", e => {
    const nav = document.getElementById("nav");
    if (e.key === "Escape" && nav.classList.contains("open")) {
      nav.classList.remove("open");
      btn.setAttribute("aria-expanded", "false");
      btn.focus();
    }
  });
}

initTheme();
initMenu();
initSkip();
window.addEventListener("hashchange", () => {
  // a new view starts at the top, unless it scrolled to a target itself (#/start?open=...)
  route().then(placed => { if (!placed) window.scrollTo(0, 0); document.getElementById("main").focus({ preventScroll: true }); });
});
route();
