// Key result at a glance: the overview's summary after the paper's graphical abstract, drawn
// natively (SVG with the page's colour tokens, so it follows the theme) from the dashboard data:
// the 14 extinction peak pairs with 1:1, delta_k and the earlier corridor band (x2-5), a
// schematic plan with the smoke path and the transmissometer pairs, the statistics, and the
// change of the predicted peak k for three inputs (Fig. 7 cases, numbers checked at build time).
import { h, minus } from "./util.js";
import { REF } from "./paper_refs.js";

const NS = "http://www.w3.org/2000/svg";
function s(tag, attrs = {}, ...kids) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined) el.setAttribute(k, v);
  for (const c of kids.flat(Infinity)) if (c !== null && c !== undefined) el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return el;
}

// parity plot, log-log 0.1-1.5 1/m
function parity(g, delta) {
  const lo = 0.1, hi = 1.5, P = { l: 48, r: 10, t: 10, b: 42 }, W = 300, H = 300;
  const w = W - P.l - P.r, ht = H - P.t - P.b;
  const X = v => P.l + (Math.log10(v) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo)) * w;
  const Y = v => P.t + ht - (Math.log10(v) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo)) * ht;
  const line = (f, cls) => s("line", { x1: X(lo), y1: Y(f(lo)), x2: X(hi), y2: Y(f(hi)), class: cls });
  const band = [[lo, 2 * lo], [hi, 2 * hi], [hi, 5 * hi], [lo, 5 * lo]].map(([x, y]) => `${X(x)},${Y(y)}`).join(" ");
  const ticks = [0.2, 0.5, 1];
  return s("svg", { viewBox: `0 0 ${W} ${H}`, class: "glance-parity", role: "img",
                    "aria-label": `Measured against FDS peak extinction: ${g.pairs.length} pairs close to the bias line δk = ${delta}` },
    s("defs", {}, s("clipPath", { id: "glance-clip" }, s("rect", { x: P.l, y: P.t, width: w, height: ht }))),
    s("g", { "clip-path": "url(#glance-clip)" },
      s("polygon", { points: band, class: "g-band" }),
      line(x => x, "g-one"), line(x => delta * x, "g-delta")),
    s("rect", { x: P.l, y: P.t, width: w, height: ht, class: "g-frame" }),
    ticks.map(t => [s("text", { x: X(t), y: H - P.b + 16, class: "g-tick", "text-anchor": "middle" }, t),
                    s("text", { x: P.l - 6, y: Y(t) + 4, class: "g-tick", "text-anchor": "end" }, t)]),
    s("text", { x: P.l + 8, y: P.t + 18, class: "g-note" }, "earlier corridor"),
    s("text", { x: P.l + 8, y: P.t + 33, class: "g-note" }, "validation: ×2–5"),
    // labels clear of the points: 1:1 below its line near the top, delta_k above its line at the
    // low end, starting clear of the y axis and ending below the highest low pair
    s("text", { x: X(1.15) + 6, y: Y(1.15) + 16, class: "g-note", transform: `rotate(-45 ${X(1.15) + 6} ${Y(1.15) + 16})` }, "1:1"),
    s("text", { x: X(0.117), y: Y(0.117 * delta) - 14, class: "g-delta-label", transform: `rotate(-45 ${X(0.117)} ${Y(0.117 * delta) - 14})` },
      "δ", s("tspan", { "baseline-shift": "sub", "font-size": "75%" }, "k"), ` = ${delta}`),
    g.pairs.map(p => s("circle", { cx: X(p.exp), cy: Y(p.sim), r: 4.2, class: "g-pt" },
      s("title", {}, `${p.series}, ${p.sensor.replace(/^Extinction coefficient /, "")}: measured ${p.exp.toFixed(3)}, FDS ${p.sim.toFixed(3)} 1/m`))),
    s("text", { x: W - P.r - 4, y: H - P.b - 22, class: "g-note", "text-anchor": "end" }, `${g.pairs.length} peak pairs (638 nm)`),
    s("text", { x: W - P.r - 4, y: H - P.b - 8, class: "g-note", "text-anchor": "end" }, "3 rooms, 3 series"),
    s("text", { x: P.l + w / 2, y: H - 6, class: "g-axis", "text-anchor": "middle" }, "measured peak k / m⁻¹"),
    s("text", { x: 12, y: P.t + ht / 2, class: "g-axis", "text-anchor": "middle", transform: `rotate(-90 12 ${P.t + ht / 2})` }, "FDS peak k / m⁻¹"));
}

// schematic plan: rooms in their Fig. 1 colours, the fire, one transmissometer pair per room, smoke path
function miniPlan(geo) {
  const room = { F1: "g-f1", F2: "g-f2", FC: "g-fc", F3: "g-f3" };
  const yr = p => [Math.min(...p.map(q => q[1])), Math.max(...p.map(q => q[1]))];
  const len = Math.max(...Object.values(geo.rooms).flat().map(q => q[1]));
  const svg = s("svg", { viewBox: "-0.3 -1.3 15.1 6.2", class: "glance-plan fig", role: "img",
                         "aria-label": "Apartment top view: fire room F1, room F2, corridor FC and room F3, smoke path from F1 to F3" },
    s("defs", {}, s("marker", { id: "g-arrow", viewBox: "0 0 10 10", refX: 8, refY: 5, markerWidth: 4, markerHeight: 4, orient: "auto-start-reverse" },
      s("path", { d: "M0,0 L10,5 L0,10 z", class: "g-arrowhead" }))));
  for (const [r, poly] of Object.entries(geo.rooms)) {
    svg.append(s("polygon", { points: poly.map(([x, y]) => `${y},${x}`).join(" "), class: `g-room ${room[r]}` }));
    const [a, b] = yr(poly), xs = poly.map(q => q[0]);
    svg.append(s("text", { x: r === "FC" ? (a + b) / 2 : a + 0.25, y: r === "FC" ? Math.max(...xs) + 0.55 : Math.max(...xs) - 0.25,
                           class: `g-room-label ${room[r]}`, "text-anchor": r === "FC" ? "middle" : "start" }, r));
  }
  // overall length
  svg.append(s("line", { x1: 0, y1: -0.6, x2: len, y2: -0.6, class: "g-dim", "marker-start": "url(#g-arrow)", "marker-end": "url(#g-arrow)" }),
             s("text", { x: len / 2, y: -0.72, class: "g-dim-label", "text-anchor": "middle" }, `${len} m`));
  // fire
  const [px0, px1, py0, py1] = geo.pan_xb, fx = (py0 + py1) / 2, fy = (px0 + px1) / 2;
  svg.append(s("polygon", { points: `${fx},${fy - 0.35} ${fx + 0.32},${fy + 0.22} ${fx - 0.32},${fy + 0.22}`, class: "g-fire" }));
  // one LEM/SICK pair per room (schematic, as in the plan below)
  const ys = {};
  for (const d of geo.devices.filter(d => d.kind === "beam")) (ys[d.room] ??= []).push(d.coords[2]);
  for (const [r, v] of Object.entries(ys)) {
    const y = v.reduce((a, b) => a + b, 0) / v.length;
    svg.append(s("line", { x1: y - 0.13, y1: 2.75, x2: y - 0.13, y2: 3.55, class: "beam sick" }),
               s("line", { x1: y + 0.13, y1: 2.75, x2: y + 0.13, y2: 3.55, class: "beam lem" }));
  }
  // smoke path F1 -> F2 -> FC -> F3
  const path = (d) => s("path", { d, class: "g-path", "marker-end": "url(#g-arrow)" });
  svg.append(path("M2.9,2.3 Q3.6,1.4 4.6,1.25"), path("M5.6,1.6 Q6.6,0.6 7.6,0.5"), path("M8.4,0.45 L10.6,0.45"),
             path("M11.4,0.5 Q12.1,0.6 12.4,1.4"));
  return svg;
}

// change of the predicted peak k: two soot-yield cases and the numerics/boundary-condition span;
// HTML bars (positions in % of a fixed axis -110 ... +150 %, room for the labels), so the text keeps its size on phones
function bars(g) {
  const xmin = -110, xmax = 150, pc = v => (v - xmin) / (xmax - xmin) * 100;
  const rows = [
    { label: ["pure n-heptane Y", "s", ""], a: Number(g.fuel), b: 0, text: `${minus(g.fuel)} %`, cls: "g-bar" },
    { label: ["handbook-level Y", "s", ` (≈ ${g.ys_handbook} g/g)`], a: 0, b: Number(g.ys_hi), text: `${g.ys_hi} %`, cls: "g-bar" },
    { label: ["numerics, boundary conditions", "", ""], a: g.nb_lo, b: g.nb_hi, text: `up to ${g.nb_text} %`, cls: "g-bar-muted" },
  ];
  return h("ul", { class: "gbars" }, rows.map(r => {
    const l = pc(Math.min(r.a, r.b)), w = pc(Math.max(r.a, r.b)) - l;
    return h("li", { class: "gbar-row" },
      // the value is drawn next to the bar; screen readers get it with the label
      h("span", { class: "gbar-label" }, r.label[0], r.label[1] ? h("sub", {}, r.label[1]) : null, r.label[2],
        h("span", { class: "sr-only" }, `: ${r.text}`)),
      h("span", { class: "gbar-track", "aria-hidden": "true" },
        h("span", { class: "gbar-zero", style: `left:${pc(0).toFixed(2)}%` }),
        h("span", { class: `gbar ${r.cls}`, style: `left:${l.toFixed(2)}%;width:${w.toFixed(2)}%` }),
        // the value next to the bar's end: left of a negative-only bar, right of the others
        h("span", { class: `gbar-value ${r.cls}-text`, style: Math.max(r.a, r.b) <= 0
          ? `right:${(100 - l).toFixed(2)}%;padding-right:6px` : `left:${(l + w).toFixed(2)}%;padding-left:6px` }, r.text)));
  }));
}

export function glanceBlock(meta, geo) {
  const kn = Object.fromEntries(meta.key_numbers.map(k => [k.macro, k.text]));
  const g = meta.glance, delta = kn.valFdsDeltaExtinction;
  return h("section", { class: "glance", "aria-label": "Key result at a glance" },
    h("p", { class: "glance-head" }, "A-priori FDS reproduces full-scale, multi-room smoke extinction to about 10 %"),
    h("p", { class: "glance-sub" }, "… provided the soot yield is measured on the burned fuel"),
    h("p", { class: "glance-context" }, "3-room apartment “Hasenheide” · commercial C7 heptane mixture, " +
      `${kn.valHrrPeakSmall}–${kn.valHrrPeakLarge} kW pool fires · no tuning to these data`),
    h("div", { class: "glance-grid" },
      h("a", { href: "#/validation", class: "glance-cell", title: `Validation (${REF.figScatter})` }, parity(g, delta)),
      h("div", { class: "glance-right" },
        h("div", { class: "glance-top" },
          h("div", {},
            h("a", { href: "#/start?open=study", class: "glance-cell", title: "The apartment and its instruments (plan and section below)",
                     onclick: toPlan }, miniPlan(geo)),
            h("a", { href: "#/lemsick", class: "glance-cell glance-instr", title: `LEM vs SICK (${REF.secWavelength})` },
              h("b", {}, "638"), " / ", h("b", { class: "g-sick-text" }, "880 nm"),
              ` transmissometers: bias ${minus(kn.valSickLemMeanBiasPct)} %`)),
          h("a", { href: "#/validation", class: "glance-cell glance-stat", title: `Validation (${REF.figScatter})` },
            h("p", { class: "glance-delta" }, "δ", h("sub", {}, "k"), ` = ${delta}`),
            h("p", {}, "bias factor FDS / measured"),
            h("p", {}, "σ", h("sub", {}, "M"), ` = ${kn.valFdsSigmaMExtinction}   (σ`, h("sub", {}, "E"), ` = ${kn.valFdsSigmaEExtinction})`))),
        h("a", { href: "#/inputs?sec=sensitivity", class: "glance-cell", title: `Sensitivity (${REF.figTornado})` },
          h("p", { class: "glance-bars-title" }, "Change in predicted peak k – one input at a time, 75 g series"),
          bars(g)))),
    h("p", { class: "caption" }, "Key result at a glance, after the paper's graphical abstract. " +
      `Select a panel: the peak pairs and the bias factor open the validation (${REF.figScatter}), the plan opens the ` +
      `apartment's plan and section below, the transmissometer line the LEM–SICK comparison, the bars the sensitivity ` +
      `(${REF.figTornado}). Numbers from the dashboard data, checked against the paper when the dashboard is built.`));
}

// The mini plan opens the overview's folded plan and section and scrolls to it; its link
// (#/start?open=study) does the same when opened directly.
function toPlan(e) {
  const d = document.getElementById("fold-study");
  if (!d) return;
  e.preventDefault();
  d.open = true;
  d.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  d.querySelector("summary").focus({ preventScroll: true });
}
