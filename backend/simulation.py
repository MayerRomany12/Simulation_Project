"""
simulation.py — Monte Carlo orchestration for the pharmacy inventory simulation.

Public API
----------
run_multi_period_simulation(params, Q_a, Q_b, R_a, R_b,
                            n_days, warmup_days, rng_a, rng_b)
    Full two-product multi-period simulation.  First `warmup_days` rows
    are DISCARDED; statistics are computed on the remaining `n_days` rows.

summarise(df)
    Aggregate per-day DataFrame into a KPI summary dict.

run_baseline_newsvendor_sim(params, Q_values, n_days, seed_seq)
    Simplified single-product, no-lead-time, no-expiry, no-substitution
    simulation used ONLY for analytical validation.

convergence_analysis(profits)
    Running average of a profit series.

run_stress_test(base_params, Q_a, Q_b, R_a, R_b,
                n_days, warmup_days, global_seed)
    Three scenarios: Normal / Weekend-Heavy / Epidemic.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm as _norm, ttest_ind as _ttest

from backend.demand import build_demand_series
from backend.inventory import AgeBucketInventory, PipelineQueue, simulate_one_day


# ---------------------------------------------------------------------------
# Full multi-period simulation
# ---------------------------------------------------------------------------

def run_multi_period_simulation(params, Q_a, Q_b, R_a, R_b,
                                n_days, warmup_days, rng_a, rng_b):
    """
    Run TOTAL = n_days + warmup_days days; discard the first warmup_days.

    Parameters
    ----------
    params : dict
        Required keys: mu_a, sigma_a, mu_b, sigma_b, clip_low, clip_high,
        weekend_mult, lead_time, p, c, s, pi, disposal_cost, sub_rate, expiry_k.
    Q_a, Q_b : int   Order quantities for products A and B.
    R_a, R_b : int   Reorder points.
    n_days   : int   Measurement period (after warm-up).
    warmup_days : int
    rng_a, rng_b : numpy.random.Generator

    Returns
    -------
    df : pd.DataFrame   One row per measurement day.
    """
    total_days = n_days + warmup_days
    L = params['lead_time']

    demands_a = build_demand_series(
        total_days, params['mu_a'], params['sigma_a'],
        params['clip_low'], params['clip_high'],
        params['weekend_mult'], start_dow=0, rng=rng_a)

    demands_b = build_demand_series(
        total_days, params['mu_b'], params['sigma_b'],
        params['clip_low'], params['clip_high'],
        params['weekend_mult'], start_dow=0, rng=rng_b)

    # Initialise inventories at Q (first order fills immediately)
    inv_a = AgeBucketInventory(initial_qty=Q_a, initial_age=0)
    inv_b = AgeBucketInventory(initial_qty=Q_b, initial_age=0)
    pipe_a = PipelineQueue(L)
    pipe_b = PipelineQueue(L)

    records = []
    for day in range(total_days):
        m = simulate_one_day(
            inv_a, inv_b, pipe_a, pipe_b,
            demands_a[day], demands_b[day],
            Q_a, Q_b, R_a, R_b, params)

        if day >= warmup_days:          # ← warm-up gate
            m['day']      = day - warmup_days + 1
            m['demand_a'] = demands_a[day]
            m['demand_b'] = demands_b[day]
            records.append(m)

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# KPI summary
# ---------------------------------------------------------------------------

def summarise(df):
    """
    Compute KPI summary dict from per-day DataFrame.

    Extended metrics added (all additive — original keys preserved):
    - ci_lower / ci_upper       : 95 % CI for avg daily profit (CLT-based)
    - sl_a_ci_lower/upper       : Wilson 95 % CI for service-level product A
    - sl_b_ci_lower/upper       : Wilson 95 % CI for service-level product B
    - avg_inv_a / avg_inv_b     : mean end-of-day on-hand inventory
    - turnover_a / turnover_b   : inventory turnover  = sales / avg_inventory
    - waste_pct_a / waste_pct_b : expired units as % of total sales
    - n_days                    : number of measurement days used
    """
    total_demand_a = df['demand_a'].sum()
    total_demand_b = df['demand_b'].sum()
    profit = df['profit_a'] + df['profit_b']
    n      = len(df)

    # ── Original KPIs (unchanged) ─────────────────────────────────────────
    avg_p = profit.mean()
    std_p = profit.std(ddof=1)

    sl_a_rate = (df['lost_a'] == 0).mean()
    sl_b_rate = (df['lost_b'] == 0).mean()

    result = dict(
        avg_profit        = round(avg_p, 4),
        std_profit        = round(std_p, 4),
        service_level_a   = round(sl_a_rate, 4),
        service_level_b   = round(sl_b_rate, 4),
        fill_rate_a       = round(1 - df['lost_a'].sum() / max(total_demand_a, 1), 4),
        fill_rate_b       = round(1 - df['lost_b'].sum() / max(total_demand_b, 1), 4),
        avg_expired_a     = round(df['expired_a'].mean(), 4),
        avg_expired_b     = round(df['expired_b'].mean(), 4),
        avg_lost_a        = round(df['lost_a'].mean(), 4),
        avg_lost_b        = round(df['lost_b'].mean(), 4),
    )

    # ── Added: 95 % CI for average profit (CLT / z-interval) ─────────────
    margin = 1.96 * std_p / (n ** 0.5)
    result['ci_lower'] = round(avg_p - margin, 4)
    result['ci_upper'] = round(avg_p + margin, 4)

    # ── Added: Wilson 95 % CI for service-level proportions ──────────────
    # Wilson interval: more accurate than normal approx for proportions near 0/1
    def _wilson_ci(p_hat, n_, z=1.96):
        denom  = 1 + z**2 / n_
        centre = (p_hat + z**2 / (2 * n_)) / denom
        half   = z * ((p_hat * (1 - p_hat) / n_ + z**2 / (4 * n_**2)) ** 0.5) / denom
        return max(0.0, centre - half), min(1.0, centre + half)

    sl_a_lo, sl_a_hi = _wilson_ci(sl_a_rate, n)
    sl_b_lo, sl_b_hi = _wilson_ci(sl_b_rate, n)
    result['sl_a_ci_lower'] = round(sl_a_lo, 4)
    result['sl_a_ci_upper'] = round(sl_a_hi, 4)
    result['sl_b_ci_lower'] = round(sl_b_lo, 4)
    result['sl_b_ci_upper'] = round(sl_b_hi, 4)

    # ── Added: inventory turnover & waste % ───────────────────────────────
    avg_inv_a = df['inv_end_a'].mean() if 'inv_end_a' in df.columns else float('nan')
    avg_inv_b = df['inv_end_b'].mean() if 'inv_end_b' in df.columns else float('nan')
    total_sales_a = df['sales_a'].sum() if 'sales_a' in df.columns else float('nan')
    total_sales_b = df['sales_b'].sum() if 'sales_b' in df.columns else float('nan')
    total_exp_a   = df['expired_a'].sum()
    total_exp_b   = df['expired_b'].sum()

    result['avg_inv_a']     = round(avg_inv_a, 4)
    result['avg_inv_b']     = round(avg_inv_b, 4)
    result['turnover_a']    = round(total_sales_a / max(avg_inv_a * n, 1), 4)
    result['turnover_b']    = round(total_sales_b / max(avg_inv_b * n, 1), 4)
    result['waste_pct_a']   = round(total_exp_a / max(total_sales_a, 1) * 100, 4)
    result['waste_pct_b']   = round(total_exp_b / max(total_sales_b, 1) * 100, 4)
    result['n_days']        = n

    return result


# ---------------------------------------------------------------------------
# Baseline Newsvendor simulation  (analytical validation only)
# ---------------------------------------------------------------------------

def _analytical_profit_normal(Q, mu, sigma, p, c, s, pi):
    """
    Compute E[Profit(Q)] analytically using the Normal demand distribution.

    E[Profit] = p·E[min(Q,D)] - c·Q + s·E[max(Q-D,0)] - π·E[max(D-Q,0)]
    """
    # E[min(Q,D)] = Q - E[max(D-Q,0)]  ;  via Normal loss function
    z    = (Q - mu) / sigma
    phi  = _norm.pdf(z)
    Phi  = _norm.cdf(z)
    loss = sigma * phi - (Q - mu) * (1 - Phi)   # E[max(D-Q,0)]

    e_sales    = Q - loss                       # E[min(Q,D)]
    e_overstock = Q - mu + loss                 # E[max(Q-D,0)]
    e_profit   = p * e_sales - c * Q + s * e_overstock - pi * loss
    return e_profit


def run_baseline_newsvendor_sim(params, Q_values, n_days, seed_seq):
    """
    Simplified single-product, no-lead-time, no-expiry simulation
    for analytical validation against the Newsvendor formula.

    Parameters
    ----------
    params : dict  (uses mu_a, sigma_a, clip_low, clip_high, p, c, s, pi)
    Q_values : list[int]
    n_days : int
    seed_seq : numpy.random.SeedSequence   (parent; children spawned here)

    Returns
    -------
    df : pd.DataFrame  columns: Q, analytical_profit, sim_profit, pct_diff
    """
    mu    = params['mu_a']
    sigma = params['sigma_a']
    p, c, s, pi = params['p'], params['c'], params['s'], params['pi']

    child_seqs = seed_seq.spawn(len(Q_values))
    rows = []

    for i, Q in enumerate(Q_values):
        rng     = np.random.default_rng(child_seqs[i])
        demands = rng.normal(loc=mu, scale=sigma, size=n_days)
        demands = np.clip(np.round(demands),
                          params['clip_low'], params['clip_high']).astype(int)

        sales   = np.minimum(Q, demands)
        over    = np.maximum(Q - demands, 0)
        lost    = np.maximum(demands - Q, 0)
        profits = p * sales - c * Q + s * over - pi * lost

        ap = _analytical_profit_normal(Q, mu, sigma, p, c, s, pi)
        sp = profits.mean()

        rows.append(dict(
            Q                  = Q,
            analytical_profit  = round(ap, 2),
            sim_profit         = round(sp, 2),
            pct_diff           = round(abs(ap - sp) / max(abs(ap), 1e-9) * 100, 2),
        ))

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Convergence analysis
# ---------------------------------------------------------------------------

def convergence_analysis(profits_series):
    """
    Compute running average of profit over simulation days.

    Parameters
    ----------
    profits_series : array-like of float

    Returns
    -------
    running_avg : np.ndarray
    """
    arr = np.asarray(profits_series, dtype=float)
    return np.cumsum(arr) / np.arange(1, len(arr) + 1)


# ---------------------------------------------------------------------------
# Stress testing
# ---------------------------------------------------------------------------

def run_stress_test(base_params, Q_a, Q_b, R_a, R_b,
                    n_days, warmup_days, global_seed):
    """
    Run three demand scenarios and return summary KPIs for each.

    Scenarios
    ---------
    Normal        : base parameters, no weekend effect.
    Weekend-Heavy : weekend_mult = 1.3.
    Epidemic      : mu_a = mu_b = 150 (simulating demand surge).

    Fix note
    --------
    The Epidemic scenario now dynamically sets clip_high = mu_epidemic * 3
    so that the surge demand is not silently capped at the normal clip_high.
    Original clip_high is restored for Normal and Weekend-Heavy scenarios.

    Returns
    -------
    results : dict { scenario_name : summary_dict }
    """
    epidemic_mu = 150
    scenarios = {
        'Normal':        {'mu_a': base_params['mu_a'],
                          'mu_b': base_params['mu_b'],
                          'weekend_mult': 1.0},
        'Weekend-Heavy': {'mu_a': base_params['mu_a'],
                          'mu_b': base_params['mu_b'],
                          'weekend_mult': 1.3},
        # FIX: clip_high updated to accommodate the surge mean (was using base clip_high)
        'Epidemic':      {'mu_a': epidemic_mu,
                          'mu_b': epidemic_mu,
                          'weekend_mult': 1.0,
                          'clip_high': epidemic_mu * 3},
    }

    ss = np.random.SeedSequence(global_seed)
    child_seeds = ss.spawn(len(scenarios) * 2)  # 2 products × 3 scenarios
    results = {}

    for idx, (name, overrides) in enumerate(scenarios.items()):
        p       = {**base_params, **overrides}
        rng_a   = np.random.default_rng(child_seeds[idx * 2])
        rng_b   = np.random.default_rng(child_seeds[idx * 2 + 1])
        df      = run_multi_period_simulation(
                      p, Q_a, Q_b, R_a, R_b,
                      n_days, warmup_days, rng_a, rng_b)
        s       = summarise(df)
        s['scenario'] = name
        # Store the raw daily profit series for hypothesis testing
        s['_profit_series'] = (df['profit_a'] + df['profit_b']).values
        results[name] = s

    return results


# ---------------------------------------------------------------------------
# Hypothesis testing between stress-test scenarios
# ---------------------------------------------------------------------------

def compare_stress_scenarios(results, alpha=0.05):
    """
    Perform pairwise two-sample t-tests on daily profit between all scenario pairs.

    Uses the stored ``_profit_series`` key added by run_stress_test().

    Parameters
    ----------
    results : dict  as returned by run_stress_test()
    alpha   : float  significance level (default 0.05)

    Returns
    -------
    comparisons : list of dict  with keys:
        scenario_a, scenario_b, mean_a, mean_b, t_stat, p_value, significant
    """
    names = list(results.keys())
    comparisons = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            s_a  = results[a]['_profit_series']
            s_b  = results[b]['_profit_series']
            t, p = _ttest(s_a, s_b, equal_var=False)   # Welch t-test
            comparisons.append(dict(
                scenario_a  = a,
                scenario_b  = b,
                mean_a      = round(s_a.mean(), 2),
                mean_b      = round(s_b.mean(), 2),
                t_stat      = round(float(t), 4),
                p_value     = round(float(p), 6),
                significant = bool(p < alpha),
            ))
    return comparisons


# ---------------------------------------------------------------------------
# Reorder-point derivation helper
# ---------------------------------------------------------------------------

def compute_reorder_point(mu_daily, sigma_daily, lead_time, service_level=0.95):
    """
    Derive the reorder point R for an (R, Q) inventory policy.

    Formula
    -------
    During lead time L days demand is D_L ~ N(mu_L, sigma_L) where:
        mu_L    = mu_daily * L
        sigma_L = sigma_daily * sqrt(L)

    The reorder point with a target cycle service level CSL is:
        R = mu_L + z_{CSL} * sigma_L

    Safety stock SS = R - mu_L = z_{CSL} * sigma_L

    Parameters
    ----------
    mu_daily      : float   Mean daily demand (units/day).
    sigma_daily   : float   Std dev of daily demand.
    lead_time     : int     Lead time in days (L).
    service_level : float   Target cycle service level (default 0.95).

    Returns
    -------
    dict with keys: mu_L, sigma_L, z, safety_stock, reorder_point (all rounded).

    Examples
    --------
    >>> compute_reorder_point(mu_daily=60, sigma_daily=15, lead_time=3)
    {'mu_L': 180, 'sigma_L': 25.98, 'z': 1.645, 'safety_stock': 42.75,
     'reorder_point': 223}
    """
    mu_L     = mu_daily * lead_time
    sigma_L  = sigma_daily * (lead_time ** 0.5)
    z        = _norm.ppf(service_level)
    ss       = z * sigma_L
    R        = mu_L + ss
    return dict(
        mu_L          = round(mu_L, 2),
        sigma_L       = round(sigma_L, 2),
        z             = round(z, 3),
        safety_stock  = round(ss, 2),
        reorder_point = int(np.ceil(R)),   # round up to be conservative
    )
