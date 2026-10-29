// Apartment with its instruments as two aligned SVGs from geometry.json (FDS input file
// coordinates): a top view and a longitudinal section, sharing the horizontal axis (y,
// along F1-F2-FC-F3, F1 left). Top view as in Fig. 1: x (towards the facade) points down,
// i.e. svg (X, Y) = (y, x); x up would mirror the plan. Section: seen from the facade,
// svg (X, Y) = (y, H - z). Every instrument links to its data. The LEM and SICK beams are
// drawn schematically (one pair per room, equal length and depth); their exact coordinates
// are in Table S1 and the FDS input files.
import { REF } from "./paper_refs.js";

const NS = "http://www.w3.org/2000/svg";
function s(tag, attrs = {}, ...kids) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined) el.setAttribute(k, v);
  for (const c of kids.flat()) if (c) el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return el;
}
const H = 2.55;                                     // room height, m
const VIEW_X = [-0.75, 15.6];                       // shared horizontal origin and width of both views (y in m)
const BEAM_X = [2.75, 3.55];                        // schematic beam span (depth x), clear of alarms and trees
const PAIR = 0.13;                                  // half spacing of the LEM/SICK pair, m
const ROOM_LABEL = { F1: "F1 · fire room", F2: "F2", FC: "FC", F3: "F3" };
const yRange = poly => [Math.min(...poly.map(p => p[1])), Math.max(...poly.map(p => p[1]))];

// a linked instrument marker: <a> with tooltip, keyboard-focusable
function link(href, label, ...shapes) {
  return s("a", { href, class: "dev", "aria-label": label }, ...shapes, s("title", {}, label));
}
const explorer = q => `#/explorer?${q}`;

// instruments from the device list of the baseline deck (positions shared by all series)
function instruments(geo) {
  const dev = geo.devices;
  const beams = {};                                 // room -> {lem: [z], sick, y: anchor}
  for (const d of dev.filter(d => d.kind === "beam")) {
    const b = (beams[d.room] ??= { lem: [], sick: false, ys: [] });
    if (d.id.startsWith("LEM")) b.lem.push(d.z); else b.sick = true;
    b.ys.push(d.coords[2]);
  }
  for (const b of Object.values(beams)) {           // anchor: the mean of the room's beam positions
    b.y = b.ys.reduce((a, v) => a + v, 0) / b.ys.length;
    b.lem.sort((p, q) => p - q);
  }
  const trees = {};
  for (const d of dev.filter(d => /^TC_F\d_/.test(d.id) && d.measured))
    (trees[d.room] ??= { x: d.coords[0], y: d.coords[1], tcs: [] }).tcs.push({ z: d.z, column: d.measured });
  // drawn centred where the layout is centred (deck offsets of a grid cell or less): the
  // ceiling thermocouple over the pan (1.25 cm in x and y), the corridor alarm on the
  // corridor axis (2.5 cm); the room alarms stay at their deck positions next to the trees
  const [px0, px1, py0, py1] = geo.pan_xb;
  const c = dev.find(d => d.id === "TC_Ceiling_F1");
  const ceil = c && { coords: [(px0 + px1) / 2, (py0 + py1) / 2, c.coords[2]] };
  const fcX = poly => (Math.min(...poly.map(p => p[0])) + Math.max(...poly.map(p => p[0]))) / 2;
  const alarms = [];
  for (const d of dev.filter(d => d.id.startsWith("SD_") && d.measured))
    if (!alarms.some(a => a.column === d.measured))
      alarms.push({ room: d.room, x: d.room === "FC" ? fcX(geo.rooms.FC) : d.coords[0], y: d.coords[1], z: d.coords[2], column: d.measured });
  return { beams, trees, ceil, alarms };
}

const lemHref = (room, z) => `#/extinction?room=${room}&z=${z}`;
const sickHref = room => `#/extinction?room=${room}&z=2.3&layers=mean,sick,fds`;
const alarmLabel = a => `Smoke alarm, ${a.room === "FC" ? "corridor FC" : "room " + a.room}: activation in the test explorer`;

function triangle(cx, cy, r, cls) {
  return s("polygon", { points: `${cx},${cy - r} ${cx + r},${cy + r * 0.8} ${cx - r},${cy + r * 0.8}`, class: cls });
}
function diamond(cx, cy, r, cls) {
  return s("polygon", { points: `${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}`, class: cls });
}

export function planSvg(geo) {
  const W = 0.06;
  const ins = instruments(geo);
  const svg = s("svg", { viewBox: `${VIEW_X[0]} -0.75 ${VIEW_X[1]} 6.0`, class: "plan fig", role: "img",
                         "aria-label": "Top view of the apartment with rooms F1, F2, corridor FC and F3 and the instruments" });
  for (const poly of Object.values(geo.rooms))
    svg.append(s("polygon", { points: poly.map(([x, y]) => `${y},${x}`).join(" "), class: "room", "stroke-width": W }));
  for (const d of geo.doors) {
    const [x0, x1, y0, y1] = d.xb;
    svg.append(s("rect", { x: y0, y: x0, width: y1 - y0, height: x1 - x0, class: "door" }));
  }
  for (const [x, y0, y1] of geo.sealed_doors)
    svg.append(s("g", { class: "sealed" }, s("line", { x1: y0, y1: x - 0.12, x2: y1, y2: x + 0.12 }),
                                           s("line", { x1: y0, y1: x + 0.12, x2: y1, y2: x - 0.12 })));
  for (const w of geo.windows) {
    const [x, , y0, y1] = w.xb;
    svg.append(s("line", { x1: y0, y1: x, x2: y1, y2: x, class: "window" }));
  }
  for (const [room, poly] of Object.entries(geo.rooms)) {
    // the corridor is narrow and carries an alarm and the sealed doorways: label at its left end
    const xs = poly.map(p => p[0]), [ya, yb] = yRange(poly), fc = room === "FC";
    svg.append(s("text", { x: fc ? ya + 0.15 : (ya + yb) / 2, y: fc ? (Math.min(...xs) + Math.max(...xs)) / 2 + 0.1 : Math.min(...xs) + 0.45,
                           class: "room-label", "text-anchor": fc ? "start" : "middle" }, ROOM_LABEL[room]));
  }
  // platform scale and fire
  const [lx0, lx1, ly0, ly1] = geo.load_cell_xb, [px0, px1, py0, py1] = geo.pan_xb;
  svg.append(link(explorer("g=mass"), "Platform scale under the fire: fuel mass in the test explorer",
                  s("rect", { x: ly0, y: lx0, width: ly1 - ly0, height: lx1 - lx0, class: "scale" })));
  svg.append(link("#/inputs", "Pool fire: heat release rate (Fig. 3)",
                  s("rect", { x: py0, y: px0, width: py1 - py0, height: px1 - px0, class: "fire" })));
  // schematic beam pairs: SICK towards F1, LEM towards F3, the same span in every room
  for (const [room, b] of Object.entries(ins.beams)) {
    if (b.sick) svg.append(link(sickHref(room), `SICK beam, room ${room}, z = 2.3 m: extinction`,
      s("line", { x1: b.y - PAIR, y1: BEAM_X[0], x2: b.y - PAIR, y2: BEAM_X[1], class: "beam sick" })));
    if (b.lem.length) svg.append(link(lemHref(room, b.lem[b.lem.length - 1]),
      `LEM beam${b.lem.length > 1 ? "s" : ""}, room ${room}, z = ${b.lem.join(", ")} m: extinction`,
      s("line", { x1: b.y + PAIR, y1: BEAM_X[0], x2: b.y + PAIR, y2: BEAM_X[1], class: "beam lem" })));
  }
  for (const [room, t] of Object.entries(ins.trees))
    svg.append(link(explorer(`g=temp&ch=T_${room}_`), `Thermocouple tree, room ${room} (${t.tcs.length} heights): temperatures in the test explorer`,
                    s("circle", { cx: t.y, cy: t.x, r: 0.13, class: "tree" })));
  if (ins.ceil) svg.append(link(explorer("g=temp&ch=T_ceiling_F1_C"), "Ceiling thermocouple above the fire, room F1: temperature in the test explorer",
                                s("circle", { cx: ins.ceil.coords[1], cy: ins.ceil.coords[0], r: 0.07, class: "ceiling" })));
  for (const a of ins.alarms)
    svg.append(link(explorer(`g=alarm&ch=${a.column}`), alarmLabel(a), triangle(a.y, a.x, 0.15, "alarm")));
  svg.append(s("text", { x: -0.6, y: -0.45, class: "axis-note" }, "corridor side"),
             s("text", { x: -0.6, y: 4.95, class: "axis-note" }, "facade (windows)"));
  return svg;
}

// Longitudinal section, seen from the facade: svg (X, Y) = (y, H - z), heights to scale.
export function sectionSvg(geo) {
  const W = 0.06, Z = z => H - z;
  const ins = instruments(geo);
  const svg = s("svg", { viewBox: `${VIEW_X[0]} -0.55 ${VIEW_X[1]} 3.45`, class: "plan fig section", role: "img",
                         "aria-label": "Longitudinal section of the apartment with the instrument heights" });
  for (const [room, poly] of Object.entries(geo.rooms)) {
    const [ya, yb] = yRange(poly);
    svg.append(s("rect", { x: ya, y: 0, width: yb - ya, height: H, class: "room", "stroke-width": W }),
               s("text", { x: (ya + yb) / 2, y: -0.15, class: "room-label", "text-anchor": "middle" }, ROOM_LABEL[room]));
  }
  for (const d of geo.doors) {                       // openings in the partition walls
    const [, , y0, y1, z0, z1] = d.xb;
    svg.append(s("rect", { x: y0, y: Z(z1), width: y1 - y0, height: z1 - z0, class: "door" }));
  }
  for (const w of geo.windows) {                    // facade windows, in front of the section plane
    const [, , y0, y1, z0, z1] = w.xb;
    svg.append(s("rect", { x: y0, y: Z(z1), width: y1 - y0, height: z1 - z0, class: "window-pane" }));
  }
  for (const z of [0, 1, 2]) svg.append(s("text", { x: -0.12, y: Z(z) + 0.07, class: "axis-note", "text-anchor": "end" }, `${z} m`));
  // scale and fire
  const [, , ly0, ly1, lz0, lz1] = geo.load_cell_xb, [, , py0, py1, pz0, pz1] = geo.pan_xb;
  svg.append(link(explorer("g=mass"), "Platform scale under the fire: fuel mass in the test explorer",
                  s("rect", { x: ly0, y: Z(lz1), width: ly1 - ly0, height: lz1 - lz0, class: "scale" })));
  svg.append(link("#/inputs", "Pool fire: heat release rate (Fig. 3)",
                  s("rect", { x: py0, y: Z(pz1), width: py1 - py0, height: pz1 - pz0, class: "fire" }),
                  s("path", { d: `M${py0 + 0.02},${Z(pz1)} Q${(py0 + py1) / 2},${Z(pz1 + 0.75)} ${py1 - 0.02},${Z(pz1)} Z`, class: "flame" })));
  // thermocouple trees: stem + one linked marker per height
  for (const [room, t] of Object.entries(ins.trees)) {
    svg.append(s("line", { x1: t.y, y1: Z(0), x2: t.y, y2: Z(H), class: "stem" }));
    for (const tc of t.tcs)
      svg.append(link(explorer(`g=temp&ch=${tc.column}`), `Thermocouple, room ${room}, z = ${tc.z} m: temperature in the test explorer`,
                      s("circle", { cx: t.y, cy: Z(tc.z), r: 0.065, class: "tree" })));
  }
  if (ins.ceil) svg.append(link(explorer("g=temp&ch=T_ceiling_F1_C"), "Ceiling thermocouple above the fire, room F1: temperature in the test explorer",
                                s("circle", { cx: ins.ceil.coords[1], cy: Z(ins.ceil.coords[2]) + 0.05, r: 0.05, class: "ceiling" })));
  // beams (perpendicular to the section): LEM diamond, SICK square, at the schematic pair positions
  for (const [room, b] of Object.entries(ins.beams)) {
    for (const z of b.lem)
      svg.append(link(lemHref(room, z), `LEM beam, room ${room}, z = ${z} m: extinction`, diamond(b.y + PAIR, Z(z), 0.075, "lem-mark")));
    if (b.sick) {
      const r = 0.06;
      svg.append(link(sickHref(room), `SICK beam, room ${room}, z = 2.3 m: extinction`,
                      s("rect", { x: b.y - PAIR - r, y: Z(2.3) - r, width: 2 * r, height: 2 * r, class: "sick-mark" })));
    }
  }
  for (const a of ins.alarms)
    svg.append(link(explorer(`g=alarm&ch=${a.column}`), alarmLabel(a), triangle(a.y, Z(a.z) + 0.04, 0.09, "alarm")));
  return svg;
}

// One legend for both views: each entry with its symbol as drawn in the top view and in the
// section (null where that view does not show it), in a 1 x 0.6 box with the drawing's classes.
const LEGEND = [
  { label: "LEM beam", note: "section: one marker per height", planText: "LEM beam (F2: 1.5–2.3 m)", sectionText: "LEM beam (one per height)",
    plan: () => s("line", { x1: 0.05, y1: 0.3, x2: 0.95, y2: 0.3, class: "beam lem" }), section: () => diamond(0.5, 0.3, 0.13, "lem-mark") },
  { label: "SICK beam", note: "one unit, moved between rooms", planText: "SICK beam (moved between rooms)", sectionText: "SICK beam (2.3 m)",
    plan: () => s("line", { x1: 0.05, y1: 0.3, x2: 0.95, y2: 0.3, class: "beam sick" }),
    section: () => s("rect", { x: 0.4, y: 0.2, width: 0.2, height: 0.2, class: "sick-mark" }) },
  { label: "thermocouple tree", plan: () => s("circle", { cx: 0.5, cy: 0.3, r: 0.18, class: "tree" }),
    section: () => s("g", {}, s("line", { x1: 0.5, y1: 0, x2: 0.5, y2: 0.6, class: "stem" }),
                     ...[0.12, 0.3, 0.48].map(y => s("circle", { cx: 0.5, cy: y, r: 0.07, class: "tree" }))) },
  { label: "ceiling thermocouple", plan: () => s("circle", { cx: 0.5, cy: 0.3, r: 0.09, class: "ceiling" }),
    section: () => s("circle", { cx: 0.5, cy: 0.3, r: 0.07, class: "ceiling" }) },
  { label: "smoke alarm", plan: () => triangle(0.5, 0.3, 0.2, "alarm"), section: () => triangle(0.5, 0.3, 0.14, "alarm") },
  { label: "platform scale", plan: () => s("rect", { x: 0.2, y: 0.08, width: 0.6, height: 0.44, class: "scale" }),
    section: () => s("rect", { x: 0.2, y: 0.42, width: 0.6, height: 0.14, class: "scale" }) },
  { label: "fire (pan)", plan: () => s("rect", { x: 0.36, y: 0.16, width: 0.28, height: 0.28, class: "fire" }),
    section: () => s("g", {}, s("rect", { x: 0.38, y: 0.42, width: 0.24, height: 0.14, class: "fire" }),
                     s("path", { d: "M0.4,0.42 Q0.5,-0.05 0.6,0.42 Z", class: "flame" })) },
  { label: "window", note: "section: in the facade", sectionText: "window (in the facade)",
    plan: () => s("line", { x1: 0.05, y1: 0.3, x2: 0.95, y2: 0.3, class: "window" }),
    section: () => s("rect", { x: 0.15, y: 0.08, width: 0.7, height: 0.44, class: "window-pane" }) },
  { label: "doorway", plan: () => s("g", {}, s("line", { x1: 0, y1: 0.3, x2: 0.3, y2: 0.3, class: "wall" }),
                                     s("line", { x1: 0.7, y1: 0.3, x2: 1, y2: 0.3, class: "wall" })),
    section: () => s("g", {}, s("line", { x1: 0.3, y1: 0.02, x2: 0.3, y2: 0.58, class: "wall" }),
                     s("line", { x1: 0.7, y1: 0.02, x2: 0.7, y2: 0.58, class: "wall" }),
                     s("line", { x1: 0.3, y1: 0.05, x2: 0.7, y2: 0.05, class: "wall" })) },
  { label: "sealed doorway", plan: () => s("g", { class: "sealed" }, s("line", { x1: 0.1, y1: 0.12, x2: 0.9, y2: 0.48 }),
                                            s("line", { x1: 0.1, y1: 0.48, x2: 0.9, y2: 0.12 })), section: null },
];

const mark = shape => s("svg", { viewBox: "0 0 1 0.6", class: "legend-mark fig", "aria-hidden": "true" }, shape);

// on the page: one legend under both views, the top-view and the section symbol side by side
export function planLegend() {
  const wrap = document.createElement("p");
  wrap.className = "plan-legend";
  for (const it of LEGEND) {
    const span = document.createElement("span"), sym = document.createElement("span");
    sym.className = "sym";
    sym.title = [it.plan && "top view", it.section && "section"].filter(Boolean).join(" · ");
    sym.append(...[it.plan, it.section].filter(Boolean).map(f => mark(f())));
    span.append(sym, " ", it.label + (it.note ? ` (${it.note})` : ""));
    wrap.append(span);
  }
  return wrap;
}

// SVG download of one view with its legend below the drawing (the view's own symbols)
export function exportFigure(svg, view, filename, exportSvgElement) {
  const vb = svg.getAttribute("viewBox").split(" ").map(Number);
  const items = LEGEND.filter(it => it[view]), cols = 3, colW = (vb[2] - 0.6) / cols, rowH = 0.55;
  const g = s("g", { class: "legend-export" });
  items.forEach((it, i) => {
    const x = vb[0] + 0.3 + (i % cols) * colW, y = vb[1] + vb[3] + 0.15 + Math.floor(i / cols) * rowH;
    g.append(s("g", { transform: `translate(${x},${y})` }, it[view]()),
             s("text", { x: x + 1.15, y: y + 0.38, class: "legend-text" }, it[`${view}Text`] || it.label));
  });
  const h = Math.ceil(items.length / cols) * rowH + 0.25;
  svg.append(g);                                    // added and removed synchronously: never painted
  svg.setAttribute("viewBox", `${vb[0]} ${vb[1]} ${vb[2]} ${vb[3] + h}`);
  try { exportSvgElement(svg, filename); }
  finally { g.remove(); svg.setAttribute("viewBox", vb.join(" ")); }
}

export const PLAN_CAPTION = `Top view, oriented as in ${REF.figApartment} (corridor side at the top, facade at the bottom; ` +
  `the paper's floor plan and section: ${REF.figS_floorPlan}), and a ` +
  "longitudinal section seen from the facade, aligned with it; heights to scale. Instruments at the positions of the " +
  "FDS input files; the ceiling thermocouple is drawn centred over the fire and the corridor alarm on the corridor axis " +
  "(offsets of 1–3 cm), and the LEM and SICK beams schematically as one pair per room; exact coordinates in " +
  `${REF.tabS_positions} and the FDS input files. ` +
  "Select any instrument to see its data: beams open the extinction, the other sensors the test explorer, the fire " +
  "the heat release rate.";
