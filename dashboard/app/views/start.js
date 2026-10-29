// View 1: overview -- the key result at a glance (after the graphical abstract) and the views; folded
// below them: the key result in the paper's words, the study (plan and section, Tables 1 and 2), the
// names, and what is only in the paper.
import { h, table, sourceLine, exportSvgElement } from "../util.js";
import { PAPER, REF } from "../paper_refs.js";
import { planSvg, sectionSvg, planLegend, exportFigure, PLAN_CAPTION } from "../plan.js";
import { glanceBlock } from "../glance.js";

export async function render(root, { meta, views, load }) {
  const geo = await load("geometry.json");
  const top = planSvg(geo), side = sectionSvg(geo);
  const kn = Object.fromEntries(meta.key_numbers.map(k => [k.macro, k]));
  const repo = meta.citation.repository;
  const v = m => kn[m].text;

  root.append(
    h("h1", {}, PAPER.title),
    h("p", { class: "lead" },
      `Interactive companion to the paper (${PAPER.authors}; DOI added on publication) and its reproduction package. ` +
      "It shows what the paper and the package contain: the measured and simulated curves, the validation " +
      "statistics and the data behind every number. Each view names the paper figures and tables it shows and links its data files."),
    glanceBlock(meta, geo),

    h("h2", {}, "Explore"),
    ...cards(views),

    h("div", { class: "folds" },
    fold("in-words", "The key result in the paper's words", "Abstract",
      h("blockquote", {},
        h("p", {}, "Against these we validated an a-priori Fire Dynamics Simulator (FDS) model whose soot yield and heat of " +
          "combustion were measured on the same fuel in a furniture calorimeter and whose heat release rate was prescribed " +
          "from the measured mass loss, with no smoke-side parameter tuned to the apartment data. With a matched " +
          `line-of-sight beam for each transmissometer, FDS reproduces the extinction to a bias factor of ${v("valFdsDeltaExtinction")}, ` +
          "well below the factor two-to-five of an earlier single-corridor validation, and follows the upper-layer " +
          `temperature and smoke-layer descent at bias factors of ${v("valFdsDeltaUpperLayerT")} and ${v("valFdsDeltaLayerHeight")}.`),
        h("footer", {}, "Abstract of the paper, verbatim; the values from numbers.tex, checked when the dashboard is built"))),

    fold("study", "The study: apartment, instruments and test series",
      `${REF.figApartment}, ${REF.tabExperiments}, ${REF.tabAmbient}`,
      h("p", {}, "Fourteen pool fires of a commercial ‘heptane’ (a C7 hydrocarbon mixture) in three series in a full-scale " +
        "three-room apartment, measured with line-of-sight transmissometers (LEM at 638 nm, SICK at 880 nm), " +
        "thermocouples and a platform scale, and compared with a-priori FDS simulations. The numbers are the " +
        `paper's values, as printed (${REF.secSetup}, ${REF.secCfdResults}).`),
      h("figure", { class: "figure" },
        h("div", { class: "plan-wrap", tabindex: "0", role: "region", "aria-label": "apartment plan and section" },
          h("div", { class: "plan-pair" }, top, side)), planLegend(), h("figcaption", { class: "caption" }, PLAN_CAPTION)),
      h("p", { class: "downloads" }, "Download: ",
        h("button", { type: "button", class: "linklike", onclick: () => exportFigure(top, "plan", "apartment_top_view", exportSvgElement) }, "top view with legend (SVG)"), " · ",
        h("button", { type: "button", class: "linklike", onclick: () => exportFigure(side, "section", "apartment_section", exportSvgElement) }, "section with legend (SVG)")),
      sourceLine(repo, ["scripts/plot_apartment_geometry.py", "results/simulation/timeseries/fds_channels.csv"], "Geometry"),
      h("div", { class: "table-row" },
        h("div", {},
          table({ caption: `${REF.tabExperiments}. Test series`, header: meta.table1.header, rows: meta.table1.rows,
                  numeric: [1, 2, 3, 4, 5, 6] }),
          sourceLine(repo, [meta.table1.source, "results/measurement/experiments_overview.csv"], "Table")),
        h("div", {},
          table({ caption: `${REF.tabAmbient}. Ambient conditions (mean ± SD)`, header: meta.table2.header, rows: meta.table2.rows,
                  numeric: [1, 2, 3, 4] }),
          sourceLine(repo, [meta.table2.source, "results/measurement/ambient.csv"], "Table")))),

    fold("names", "Names used here", "series, tests, rooms, instruments",
    h("dl", { class: "naming" },
      h("dt", {}, "Hep_160_075"), h("dd", {}, "a series: fuel, square pan of side 160 mm, fuel mass 75 g"),
      h("dt", {}, "Hep_160_075_R4"), h("dd", {}, "a test: the fourth test of that series, in the order run (the package files keep the ids " +
        "of the test log, such as Hep_160_S3_R1; ", h("a", { href: "#/data" }, "Data and numbers"), " lists both)"),
      h("dt", {}, "Hep"), h("dd", {}, "the commercial ‘heptane’, a C7 hydrocarbon mixture"),
      h("dt", {}, "F1, F2, FC, F3"), h("dd", {}, "fire room F1, room F2, corridor FC, room F3"),
      h("dt", {}, "LEM"), h("dd", {}, "custom-built laser extinction meter, 638 nm, optical path 0.81 m"),
      h("dt", {}, "SICK"), h("dd", {}, "commercial transmissometer (SICK FW 56-I), 880 nm, reflector 0.8 m away (double-pass path 1.6 m); " +
        "shown scaled to 638 nm unless stated"))),

    fold("more", "More in the paper", "Supplementary Material",
    h("p", { class: "note" }, "This dashboard keeps to the main results. The Supplementary Material (SM) and the " +
      "reproduction package hold the rest:"),
    h("ul", { class: "note" },
      h("li", {}, `${REF.smFloorPlan}, ${REF.figPhotos}, ${REF.figS_photos}: floor plan and photographs (in the paper only)`),
      h("li", {}, `${REF.smAirtightness}: envelope airtightness (blower door)`),
      h("li", {}, `${REF.smFuel}, ${REF.smSootYield}: fuel composition, calorimeter runs, n-heptane literature`),
      h("li", {}, `${REF.smHrr}: heat release from the mass loss`),
      h("li", {}, `${REF.smDevices}, ${REF.smFouling}, ${REF.smExtUncertainty}: instrument validation, optics fouling, uncertainty budget`),
      h("li", {}, `${REF.smSmokeAlarms}: smoke alarms`),
      h("li", {}, `${REF.smModelInputs}, ${REF.smSensitivity}: FDS model inputs, sensitivity cases, grid, run-to-run noise`),
      h("li", {}, `${REF.smTemperature}, ${REF.smFlowField}: temperature and flow fields`),
      h("li", {}, "The text: introduction, discussion, conclusions.")),
    h("p", { class: "note" }, "The FDS runs cover the pre-ventilation phase only (900 s for Hep_160_075, 1200 s otherwise).")),
    ),
  );
}

// A folded section: closed by default; whether a reader opened it is remembered for the
// session (in this browser only), so coming back to the overview keeps it as it was.
function fold(key, title, hint, ...body) {
  const id = `fold:${key}`;
  let open = false;
  try { open = sessionStorage.getItem(id) === "1"; } catch { /* storage blocked: start closed */ }
  const d = h("details", { class: "fold", open },
    h("summary", {}, h("h2", {}, title), hint ? h("span", { class: "fold-hint" }, hint) : null), ...body);
  d.addEventListener("toggle", () => { try { sessionStorage.setItem(id, d.open ? "1" : "0"); } catch { /* ignore */ } });
  return d;
}

// The views as cards, each with its paper references.
function cards(views) {
  const cur = h("div", { class: "cards" });
  const out = [cur];
  for (const x of views) {
    if (x.id === "start") continue;
    // on the cards only the exception is badged (package data); the view header shows all chips
    const body = [h("b", {}, x.title), h("span", {}, x.blurb),
      (x.refs || []).length ? h("small", { class: "refs" }, x.refs.map(k => REF[k]).join(" · ")) : null,
      x.kind === "package" ? h("small", { class: "chip kind-package" }, "package data") : null];
    cur.append(x.module
      ? h("a", { class: "card", href: `#/${x.id}` }, body)
      : h("div", { class: "card planned", title: "planned" }, body, h("span", { class: "badge" }, "planned")));
  }
  return out;
}
