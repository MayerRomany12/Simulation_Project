"""
demand.py — Demand generation for the pharmacy inventory simulation.

Functions
---------
generate_demand(n, mu, sigma, clip_low, clip_high, rng)
    Draw n daily demand values from N(mu, sigma), clipped + rounded to int.

apply_seasonality(demands, start_dow, weekend_mult)
    Scale weekend demand by weekend_mult (Saturday=5, Sunday=6).

build_demand_series(n, mu, sigma, clip_low, clip_high,
                    weekend_mult, start_dow, rng)
    Full pipeline: generate → seasonality.

Epidemic scenario is handled by the caller passing a higher mu.

RNG note
--------
All functions accept a ``numpy.random.Generator`` object (the modern API
introduced in NumPy 1.17).  Do NOT use the legacy ``np.random.seed()`` /
``np.random.normal()`` global-state API anywhere that calls these functions,
as that API is deprecated and produces non-reproducible results when combined
with the Generator-based approach.  Always pass an explicit Generator::

    rng = np.random.default_rng(seed=42)
    demands = build_demand_series(365, mu=60, sigma=15, rng=rng)

Weekend seasonality note
------------------------
``apply_seasonality`` uses modular arithmetic to map absolute day indices to
day-of-week.  Saturday = dow 5, Sunday = dow 6 (0=Monday … 6=Sunday).
The formula ``(np.arange(n) + start_dow) % 7 >= 5`` is correct for any
value of ``start_dow`` in [0, 6].
"""

import numpy as np


def generate_demand(n, mu, sigma, clip_low=5, clip_high=500, rng=None):
    """
    Generate n daily demand values from N(mu, sigma).

    Parameters
    ----------
    n : int
    mu, sigma : float   Normal distribution parameters.
    clip_low, clip_high : int   Hard bounds on realised demand.
    rng : numpy.random.Generator   (created internally if None)

    Returns
    -------
    demands : np.ndarray of int, shape (n,)
    """
    if rng is None:
        rng = np.random.default_rng()
    raw = rng.normal(loc=mu, scale=sigma, size=n)
    return np.clip(np.round(raw), clip_low, clip_high).astype(int)


def apply_seasonality(demands, start_dow=0, weekend_mult=1.2):
    """
    Apply a weekend demand multiplier.

    Saturday (dow 5) and Sunday (dow 6) → multiply by weekend_mult.
    Weekdays → multiplier = 1.0 (unchanged).

    Parameters
    ----------
    demands : np.ndarray of int
    start_dow : int   Day-of-week for index 0  (0=Monday … 6=Sunday).
    weekend_mult : float

    Returns
    -------
    adjusted : np.ndarray of int
    """
    day_indices = (np.arange(len(demands)) + start_dow) % 7
    is_weekend  = (day_indices >= 5).astype(float)
    multiplier  = 1.0 + (weekend_mult - 1.0) * is_weekend
    return np.clip(np.round(demands * multiplier), 1, None).astype(int)


def build_demand_series(n, mu, sigma, clip_low=5, clip_high=500,
                        weekend_mult=1.0, start_dow=0, rng=None):
    """
    Generate demand and apply seasonality in one call.

    Parameters
    ----------
    n : int
    mu, sigma : float
    clip_low, clip_high : int
    weekend_mult : float   1.0 means no weekend effect.
    start_dow : int        Day-of-week for day 0.
    rng : numpy.random.Generator

    Returns
    -------
    demands : np.ndarray of int, shape (n,)
    """
    demands = generate_demand(n, mu, sigma, clip_low, clip_high, rng)
    if weekend_mult != 1.0:
        demands = apply_seasonality(demands, start_dow, weekend_mult)
    return demands
