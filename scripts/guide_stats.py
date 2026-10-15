"""Shared FDS Validation-Guide log-normal model-error statistics.

Single source for the model bias factor delta and the relative model standard
deviation sigma_M from the log ratios ln(M/E) of predicted (M) and measured (E)
peak values, following the FDS Validation Guide (NIST SP 1018; Error chapter):

    ln(M/E) ~ N(ln delta - sigma_M^2/2 + sigma_E^2/2,  sigma_M^2 + sigma_E^2)
    Var[ln(M/E)] ~ sigma_M^2 + sigma_E^2   (constraint sigma_M >= sigma_E)
    delta        = exp(mean[ln(M/E)] + sigma_M^2/2 - sigma_E^2/2)

When Var[ln(M/E)] <= 2 sigma_E^2 the model scatter cannot be separated from the
experimental scatter, so sigma_M is reported at its floor (= sigma_E) and then
quantifies the measurement, not the model (``floored``).

Used by scripts/fds_validation_scatter.py (the canonical pooled statistic); the
caller supplies its own sigma_E and its own peak-pair selection.
"""
from __future__ import annotations

import numpy as np

# Canonical experimental relative standard uncertainties (1 sigma) per quantity
# group -- the single source for the guide statistic's sigma_E (used by
# fds_validation_scatter.py).
#
# Temperature / upper-layer T / layer height: FDS Validation Guide thermocouple
# value (0.05; Error chapter). The layer height is reduced from the TC profile
# and inherits that uncertainty.
# Extinction: the study's own line-of-sight MEASUREMENT budget (0.08; not the
# Guide's generic ~14% NIST/NRC laser value): the measurement-side terms only --
# PMMA device validation, run-to-run scatter, optics fouling -- combined in
# quadrature; see Supplementary Material S8 ("Measurement uncertainty of the
# extinction coefficient"), Table S6.
#
# The measured-input uncertainty (Y_s +/-8%, HRR 4-8%) is deliberately NOT in
# sigma_E. It is (i) a model-input uncertainty that perturbs the prediction M,
# not the measurement E, and (ii) systematic: Y_s, K_m and chi_r are the same for
# all three series, so it shifts every pooled pair together and contributes
# nothing to the point-to-point scatter that sigma_M^2 + sigma_E^2 decomposes.
# It is carried instead as a systematic band on the bias delta, quantified by the
# soot-yield sensitivity study (Supplementary Material section "FDS Sensitivity Study"). Folding it into
# sigma_E would inflate the floor and force sigma_M to it; kept out, sigma_M
# resolves normally and quantifies genuine model scatter. Same reasoning
# for systematic K_m.
SIGMA_E = {"Temperature": 0.05, "Upper-layer T": 0.05, "Layer height": 0.05,
           "Extinction": 0.08}


def guide_delta_sigma(ln_me, sigma_e: float) -> dict:
    """delta, sigma_M and diagnostics from the log ratios ln(M/E).

    ln_me:   array of ln(predicted/measured) over the peak pairs of one group.
    sigma_e: relative experimental standard uncertainty (1 sigma) of the group.
    """
    ln_me = np.asarray(ln_me, dtype=float)
    n = int(ln_me.size)
    mean_ln = float(np.mean(ln_me))
    var_ln = float(np.var(ln_me, ddof=1)) if n > 1 else 0.0
    sigma_m = float(np.sqrt(max(var_ln - sigma_e ** 2, sigma_e ** 2)))  # sigma_M >= sigma_E
    delta = float(np.exp(mean_ln + sigma_m ** 2 / 2 - sigma_e ** 2 / 2))
    floored = bool(var_ln <= 2 * sigma_e ** 2)
    return {"n": n, "mean_ln": mean_ln, "var_ln": var_ln,
            "sigma_M": sigma_m, "delta": delta, "floored": floored}
