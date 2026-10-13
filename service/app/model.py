"""Frozen-parameter filters that reproduce rugarch and VineCopula.

The research pipeline (research/01_walkforward.R) estimates every model. This
module only runs the one-step-ahead recursions forward from the terminal state
at the freeze date, so live values use parameters fixed on training data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import special, stats


@dataclass
class MarginalState:
    r: float
    mu: float
    sigma: float
    z: float


def _abs_moment(dist: str, shape: float | None) -> float:
    """E|z| for the standardised innovation, used by the eGARCH news term."""
    if dist == "norm":
        return math.sqrt(2 / math.pi)
    nu = shape
    return (
        2
        * math.sqrt(nu - 2)
        * math.exp(special.gammaln((nu + 1) / 2) - special.gammaln(nu / 2))
        / ((nu - 1) * math.sqrt(math.pi))
    )


def pit(z: np.ndarray, dist: str, shape: float | None) -> np.ndarray:
    if dist == "std":
        u = stats.t.cdf(z * math.sqrt(shape / (shape - 2)), df=shape)
    else:
        u = stats.norm.cdf(z)
    return np.clip(u, 1e-6, 1 - 1e-6)


def filter_marginal(spec: dict, state: MarginalState, r: np.ndarray, vix: np.ndarray) -> dict:
    """ARMA(p<=1, q<=1) mean with sGARCH, gjrGARCH or eGARCH(1,1) variance."""
    c = spec["coef"]
    mu_c = c.get("mu", 0.0)
    ar = c.get("ar1", 0.0)
    ma = c.get("ma1", 0.0)
    omega, alpha, beta = c["omega"], c["alpha1"], c["beta1"]
    gamma = c.get("gamma1", 0.0)
    vx = c.get("vxreg1", 0.0) if spec["vix"] else 0.0
    shape = c.get("shape")
    kappa = _abs_moment(spec["dist"], shape)

    n = len(r)
    mu = np.empty(n)
    sigma = np.empty(n)
    prev_r, prev_eps, prev_sigma = state.r, state.r - state.mu, state.sigma
    prev_z = prev_eps / prev_sigma
    for t in range(n):
        mu[t] = mu_c + ar * (prev_r - mu_c) + ma * prev_eps
        if spec["model"] == "eGARCH":
            log_h = (
                omega
                + vx * vix[t]
                + alpha * prev_z
                + gamma * (abs(prev_z) - kappa)
                + beta * math.log(prev_sigma**2)
            )
            h = math.exp(log_h)
        else:
            leverage = gamma * prev_eps**2 if (spec["model"] == "gjrGARCH" and prev_eps < 0) else 0.0
            h = omega + vx * vix[t] + alpha * prev_eps**2 + leverage + beta * prev_sigma**2
        sigma[t] = math.sqrt(h)
        prev_eps = r[t] - mu[t]
        prev_r, prev_sigma = r[t], sigma[t]
        prev_z = prev_eps / prev_sigma
    z = (r - mu) / sigma
    return {"mu": mu, "sigma": sigma, "z": z, "u": pit(z, spec["dist"], shape)}


def _h_base(family: int, u1: np.ndarray, u2: np.ndarray, par: float, par2: float) -> np.ndarray:
    """h(u2 | u1) = P(U2 <= u2 | U1 = u1) for the unrotated families."""
    if family == 1:
        x1, x2 = stats.norm.ppf(u1), stats.norm.ppf(u2)
        return stats.norm.cdf((x2 - par * x1) / math.sqrt(1 - par**2))
    if family == 2:
        nu = par2
        x1, x2 = stats.t.ppf(u1, nu), stats.t.ppf(u2, nu)
        scale = np.sqrt((nu + x1**2) * (1 - par**2) / (nu + 1))
        return stats.t.cdf((x2 - par * x1) / scale, nu + 1)
    if family == 3:
        return u1 ** (-par - 1) * (u1**-par + u2**-par - 1) ** (-1 - 1 / par)
    if family == 4:
        a, b = (-np.log(u1)) ** par, (-np.log(u2)) ** par
        s = a + b
        cdf = np.exp(-(s ** (1 / par)))
        return cdf * s ** (1 / par - 1) * (-np.log(u1)) ** (par - 1) / u1
    if family == 5:
        e1, e2, e = np.expm1(-par * u1), np.expm1(-par * u2), np.expm1(-par)
        return np.exp(-par * u1) * e2 / (e + e1 * e2)
    raise ValueError(f"Unsupported copula family {family}")


def h_func(family: int, u1: np.ndarray, u2: np.ndarray, par: float, par2: float = 0.0) -> np.ndarray:
    if family in (13, 14):
        out = 1 - _h_base(family - 10, 1 - u1, 1 - u2, par, par2)
    else:
        out = _h_base(family, u1, u2, par, par2)
    return np.clip(out, 1e-10, 1 - 1e-10)


def conditional_probabilities(copula: dict, u: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return P(NED <= v | SBK = u) and P(SBK <= u | NED = v)."""
    fam, par, par2 = copula["family"], copula["par"], copula.get("par2", 0.0)
    return h_func(fam, u, v, par, par2), h_func(fam, v, u, par, par2)
