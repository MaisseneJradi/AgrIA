"""Paired comparison of two models on the SAME photos (rule 5 of the improvement plan)."""
import numpy as np
from scipy.stats import binomtest


def mcnemar(a_right, b_right):
    """Exact McNemar test. a_right, b_right: booleans per photo (model A right, model B right), same order.
    Returns {"gains": photos B gets right and A wrong, "losses": the reverse, "p": two-sided exact p-value}."""
    a, b = np.asarray(a_right, dtype=bool), np.asarray(b_right, dtype=bool)
    if a.shape != b.shape:
        raise ValueError("both models must be scored on the same photos")
    gains, losses = int((~a & b).sum()), int((a & ~b).sum())
    p = binomtest(gains, gains + losses, 0.5).pvalue if gains + losses else 1.0
    return {"gains": gains, "losses": losses, "p": float(p)}
