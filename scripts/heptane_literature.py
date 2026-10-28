"""n-Heptane soot-yield literature: DerSimonian-Laird random-effects pool and
Table S3 (figures stage, committed; no external data).

The ten study arms are open-pool/pan (and cone) fires of pure or near-pure
n-heptane under well-ventilated conditions, with the values and summary
uncertainties as reported in the cited sources (Table S3 of the Supplementary
Material). NIST TN 2133 is read from the vector graphics of its Fig. 7 (0.0162 +/-
0.0036, combined expanded uncertainty, k = 2; was 0.0140 +/- 0.0040 in v0.2.0, a
misreading). The two TN 2235 arms are NIST Fire Calorimetry Database records of
burns documented in TN 2235, which itself reports no soot yield.
The tabulated +/- are treated as 95 % CI half-widths, so the input
standard error is SE_i = unc / 1.96 (the one asymmetric interval is symmetrised
to its half-width first).

Writes
  results/literature/heptane_meta.csv       pooled mean, 95 % CI, Q, tau^2, I^2
                                            (-> \\valHeptaneMeta* in numbers.tex)
  results/literature/heptane_meta_arms.csv  per-arm value, SE, 95 % CI, RE weight
  tables/heptane_literature.tex             Table S3 (bare tabular)

Run: python scripts/heptane_literature.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import paths as P

OUT_DIR = P.RESULTS_DIR / "literature"
TABLES_DIR = P.REPO_ROOT / "tables"

# (label, Y_s [g/g], unc [g/g]) -- unc is the tabulated summary uncertainty
# (95 % CI half-width); SE_i = unc / 1.96.
CI_TO_SE = 1.0 / 1.96
ARMS = [
    ("Osburg & Busse",        0.0134, 0.0012),   # +0.0009/-0.0015 -> half-width
    ("Mulholland (60/85 mm)", 0.0120, 0.0032),
    ("Mulholland (310/500)",  0.0105, 0.0021),
    ("NIST TN 2133",          0.0162, 0.0036),   # Fig. 7, vector graphics; k = 2
    ("NIST TN 2162r1 (Sung)", 0.0169, 0.0005),
    ("NIST TN 2235 (pan)",    0.0233, 0.0022),
    ("NIST TN 2235 (pool)",   0.0147, 0.0020),
    ("Stage (160 mm)",        0.0157, 0.0009),
    ("Stage (240 mm)",        0.0175, 0.0003),
    ("Liu (150 mm)",          0.0150, 0.0019),
]

# Table S3 presentation: source (with the paper's citation keys), configuration,
# method (G gravimetric, P photometric; table note a in the paper), and an explicit
# value string where the source reports an asymmetric interval.
TABLE_ROWS = {
    "Osburg & Busse":        (r"Osburg and Busse\textsuperscript{b}~\cite{Osburg2013}",
                              r"cone, $D = {}$\SI{70}{\milli\metre}", "G",
                              r"$0.0134\,^{+0.0009}_{-0.0015}$"),
    "Mulholland (60/85 mm)": (r"Mulholland \textit{et al.}~\cite{mulholland_effect_scale_smoke}",
                              r"cone, $D = 60$, \SI{85}{\milli\metre}", "G", None),
    "Mulholland (310/500)":  (r"Mulholland \textit{et al.}~\cite{mulholland_effect_scale_smoke}",
                              r"pool, $D = 310$, \SI{500}{\milli\metre}", "G", None),
    "NIST TN 2133":          (r"NIST TN~2133~\cite{hu_character_residential_2021}",
                              r"pan, \SI{9.7}{\centi\metre}", "P", None),
    "NIST TN 2162r1 (Sung)": (r"NIST TN~2162r1~\cite{sung2024}",
                              r"burner, \SI{30.1}{\centi\metre}", "P", None),
    # TN 2235 documents the burns but reports no soot yield; the yields are records
    # of the NIST Fire Calorimetry Database (FCD), Table S3 note c
    "NIST TN 2235 (pan)":    (r"NIST FCD\textsuperscript{c}~\cite{nist_heptane_pan1,nist_heptane_pan2,nist_heptane_pan3}",
                              r"baking pan", "P", None),
    "NIST TN 2235 (pool)":   (r"NIST FCD\textsuperscript{c}~\cite{nist_heptane_pool_confirmation}",
                              r"six open pans", "P", None),
    "Stage (160 mm)":        (r"Stage \textit{et al.}~\cite{stage_soot_2023}",
                              r"pool, $D = {}$\SI{160}{\milli\metre}", "P", None),
    "Stage (240 mm)":        (r"Stage \textit{et al.}~\cite{stage_soot_2023}",
                              r"pool, $D = {}$\SI{240}{\milli\metre}", "P", None),
    "Liu (150 mm)":          (r"Liu \textit{et al.}~\cite{liu_ullage_height_heptane_2021}",
                              r"pool, $D = {}$\SI{150}{\milli\metre}", "P", None),
}


def dersimonian_laird(y, se):
    y = np.asarray(y, float)
    v = np.asarray(se, float) ** 2          # within-study variances
    w = 1.0 / v                             # fixed-effect weights
    mu_fixed = np.sum(w * y) / np.sum(w)
    Q = float(np.sum(w * (y - mu_fixed) ** 2))
    k = len(y)
    df = k - 1
    C = np.sum(w) - np.sum(w ** 2) / np.sum(w)
    tau2 = max(0.0, (Q - df) / C)
    ws = 1.0 / (v + tau2)                   # random-effects weights
    mu = float(np.sum(ws * y) / np.sum(ws))
    se_mu = float(np.sqrt(1.0 / np.sum(ws)))
    I2 = float(max(0.0, (Q - df) / Q)) * 100.0 if Q > 0 else 0.0
    return dict(k=k, mu=mu, se_mu=se_mu, ci_lo=mu - 1.96 * se_mu, ci_hi=mu + 1.96 * se_mu,
                Q=Q, df=df, tau2=tau2, I2=I2)


def write_table(arms: pd.DataFrame, meta: dict) -> None:
    lines = [r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}l l c c@{}}", r"\toprule",
             r"Source & Configuration & $Y_s \pm \mathrm{unc.}$ [\si[per-mode=symbol]{\gram\per\gram}]"
             r" & Method\textsuperscript{a} \\", r"\midrule"]
    for _, r in arms.iterrows():
        src, cfg, meth, val = TABLE_ROWS[r["label"]]
        val = val or f"${r['y']:.4f} \\pm {r['unc_tabulated']:.4f}$"
        lines.append(f"{src} & {cfg} & {val} & {meth} \\\\")
    lines += [r"\midrule",
              f"Random-effects pool~\\cite{{dersimonian_laird_1986}} & "
              f"$k = {int(meta['k'])}$, $I^2 = {{}}$\\SI{{{meta['I2']:.0f}}}{{\\percent}} & "
              f"${meta['mu']:.4f}$ [{meta['ci_lo']:.4f}, {meta['ci_hi']:.4f}] & -- \\\\",
              r"\bottomrule", r"\end{tabular*}"]
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    out = TABLES_DIR / "heptane_literature.tex"
    out.write_text("% Auto-generated by scripts/heptane_literature.py. Do not edit by hand.\n"
                   + "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"-> {out}")


def main() -> None:
    labels = [a[0] for a in ARMS]
    y = [a[1] for a in ARMS]
    se = [a[2] * CI_TO_SE for a in ARMS]
    r = dersimonian_laird(y, se)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([r]).to_csv(OUT_DIR / "heptane_meta.csv", index=False, lineterminator="\n")
    ws = 1.0 / (np.asarray(se, float) ** 2 + r["tau2"])
    arms = pd.DataFrame({
        "label": labels,
        "y": y,
        "unc_tabulated": [a[2] for a in ARMS],
        "se": se,
        "ci_lo": [yi - 1.96 * s for yi, s in zip(y, se)],
        "ci_hi": [yi + 1.96 * s for yi, s in zip(y, se)],
        "weight_pct": ws / ws.sum() * 100.0,
    })
    arms.to_csv(OUT_DIR / "heptane_meta_arms.csv", index=False, lineterminator="\n")
    write_table(arms, r)
    print(f"-> {OUT_DIR / 'heptane_meta.csv'}, {OUT_DIR / 'heptane_meta_arms.csv'}")
    print(f"  k = {r['k']}, pooled Y_s = {r['mu']:.4f} g/g, "
          f"95 % CI [{r['ci_lo']:.4f}, {r['ci_hi']:.4f}], I^2 = {r['I2']:.0f} %")


if __name__ == "__main__":
    main()
