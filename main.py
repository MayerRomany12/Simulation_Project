"""
main.py — Clean entry-point for the Pharmacy Inventory Simulation.

Replaces the long, messy Jupyter cells for running a standard simulation.
All parameters are read from config.py (single source of truth).

Usage
-----
    python main.py                   # run with default parameters
    python main.py --days 730        # override simulation length
    python main.py --save-plots      # save figures to ./plots/

Outputs
-------
  Console  : KPI summary table, stress-test comparison, t-test results
  Plots    : profit vs Q, convergence, demand histogram, inventory timeline,
             stress comparison (returned as Figure objects; shown or saved)
"""

import argparse
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')          # non-interactive backend; caller can override
import matplotlib.pyplot as plt

# -- Modular library ----------------------------------------------------------
from config import (
    GLOBAL_SEED, BASE_PARAMS,
    Q_A, Q_B, R_A, R_B,
    SIM_DAYS, WARMUP_DAYS,
    Q_VALUES, N_DAYS, P, C, S, PI, MU, SIGMA,
)
from demand import build_demand_series
from simulation import (
    run_multi_period_simulation,
    run_baseline_newsvendor_sim,
    run_stress_test,
    compare_stress_scenarios,
    convergence_analysis,
    compute_reorder_point,
    summarise,
)
from visualization import (
    plot_profit_vs_Q,
    plot_convergence,
    plot_demand_histogram,
    plot_inventory_over_time,
    plot_stress_comparison,
    plot_hypothesis_test_results,
)


# -- CLI ----------------------------------------------------------------------

def _parse_args():
    p = argparse.ArgumentParser(description='Pharmacy Inventory Simulation')
    p.add_argument('--days',       type=int,   default=SIM_DAYS,
                   help=f'Measurement days (default {SIM_DAYS})')
    p.add_argument('--warmup',     type=int,   default=WARMUP_DAYS,
                   help=f'Warm-up days discarded (default {WARMUP_DAYS})')
    p.add_argument('--seed',       type=int,   default=GLOBAL_SEED,
                   help=f'Master random seed (default {GLOBAL_SEED})')
    p.add_argument('--save-plots', action='store_true',
                   help='Save figures to ./plots/ instead of displaying')
    p.add_argument('--skip-stress', action='store_true',
                   help='Skip stress-test (faster runs for development)')
    return p.parse_args()


# -- Helpers ------------------------------------------------------------------

def _section(title: str):
    bar = '=' * 60
    print(f'\n{bar}\n  {title}\n{bar}')


def _show_or_save(fig, name: str, save: bool):
    """Display or save a matplotlib Figure."""
    if save:
        import os
        os.makedirs('plots', exist_ok=True)
        path = f'plots/{name}.png'
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f'  [OK]  Saved: {path}')
    else:
        plt.show()
    plt.close(fig)


# -- Main ---------------------------------------------------------------------

def main():
    args = _parse_args()
    save = args.save_plots

    ss   = np.random.SeedSequence(args.seed)
    rng_a, rng_b = (np.random.default_rng(c) for c in ss.spawn(2))

    # -- 1. Reorder-point derivation ------------------------------------------
    _section('1. Reorder-Point Derivation  (R, Q) Policy')
    for label, mu_d, sig_d in [
        ('Ibuprofen (A)', BASE_PARAMS['mu_a'], BASE_PARAMS['sigma_a']),
        ('Paracetamol (B)', BASE_PARAMS['mu_b'], BASE_PARAMS['sigma_b']),
    ]:
        rp = compute_reorder_point(mu_d, sig_d, BASE_PARAMS['lead_time'])
        print(f'  {label}:  R = {rp["reorder_point"]}  '
              f'(SS = {rp["safety_stock"]:.1f}, z = {rp["z"]:.3f})')

    # -- 2. Main multi-product simulation -------------------------------------
    _section('2. Multi-Product Simulation')
    print(f'  Running {args.days} measurement days '
          f'(+{args.warmup} warm-up) …', end='  ', flush=True)

    df = run_multi_period_simulation(
        BASE_PARAMS, Q_A, Q_B, R_A, R_B,
        n_days=args.days, warmup_days=args.warmup,
        rng_a=rng_a, rng_b=rng_b,
    )
    kpis = summarise(df)
    print('done.')

    print(f'\n  {"KPI":<28} {"Value":>12}')
    print(f'  {"-"*42}')
    for key, val in kpis.items():
        if key.startswith('_'):
            continue
        print(f'  {key:<28} {val:>12}')

    # -- 3. Newsvendor validation ---------------------------------------------
    _section('3. Baseline Newsvendor Validation')
    seed_seq = np.random.SeedSequence(args.seed + 1)
    nv_df = run_baseline_newsvendor_sim(
        BASE_PARAMS, Q_VALUES[:8], n_days=N_DAYS, seed_seq=seed_seq
    )
    print(nv_df.to_string(index=False))
    max_pct = nv_df['pct_diff'].max()
    status = '[OK]' if max_pct < 2.0 else '[!!] '
    print(f'\n  {status}  Max analytical<->simulation divergence: {max_pct:.2f} %')

    # -- 4. Convergence -------------------------------------------------------
    _section('4. Convergence Analysis')
    profits = (df['profit_a'] + df['profit_b']).values
    running_avg = convergence_analysis(profits)
    print(f'  Converged avg daily profit: {running_avg[-1]:.2f} EGP')
    fig = plot_convergence(running_avg)
    _show_or_save(fig, '01_convergence', save)

    # -- 5. Demand histograms -------------------------------------------------
    _section('5. Demand Histograms')
    fig = plot_demand_histogram(
        df['demand_a'].values, df['demand_b'].values,
        mu_a=BASE_PARAMS['mu_a'], mu_b=BASE_PARAMS['mu_b'],
    )
    _show_or_save(fig, '02_demand_hist', save)

    # -- 6. Inventory timeline ------------------------------------------------
    fig = plot_inventory_over_time(df, n_show=min(365, args.days))
    _show_or_save(fig, '03_inventory_timeline', save)

    # -- 7. Stress test -------------------------------------------------------
    if not args.skip_stress:
        _section('7. Stress Test')
        stress = run_stress_test(
            BASE_PARAMS, Q_A, Q_B, R_A, R_B,
            n_days=args.days, warmup_days=args.warmup,
            global_seed=args.seed + 99,
        )
        print(f'  {"Scenario":<18} {"Avg Profit":>12} {"Service A":>10} {"Service B":>10}')
        print(f'  {"-"*52}')
        for name, s in stress.items():
            print(f'  {name:<18} {s["avg_profit"]:>12.2f} '
                  f'{s["service_level_a"]:>10.4f} {s["service_level_b"]:>10.4f}')

        fig = plot_stress_comparison(stress)
        _show_or_save(fig, '04_stress', save)

        comparisons = compare_stress_scenarios(stress)
        fig = plot_hypothesis_test_results(comparisons)
        _show_or_save(fig, '05_hypothesis', save)

    # -- 8. Final summary -----------------------------------------------------
    _section('8. Final Summary')
    print(f'  Avg daily profit : {kpis["avg_profit"]:.2f} EGP')
    print(f'  95% CI           : [{kpis["ci_lower"]:.2f}, {kpis["ci_upper"]:.2f}]')
    print(f'  Service level A  : {kpis["service_level_a"]*100:.1f} %')
    print(f'  Service level B  : {kpis["service_level_b"]*100:.1f} %')
    print(f'  Fill rate A      : {kpis["fill_rate_a"]*100:.1f} %')
    print(f'  Fill rate B      : {kpis["fill_rate_b"]*100:.1f} %')
    print(f'  Avg expired A    : {kpis["avg_expired_a"]:.2f} units/day')
    print(f'  Avg expired B    : {kpis["avg_expired_b"]:.2f} units/day')
    print()


if __name__ == '__main__':
    main()
