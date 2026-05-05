"""
visualization.py — All plotting for the pharmacy inventory simulation.

Design contract
---------------
Every public function returns a ``matplotlib.figure.Figure`` object and does
NOT call ``plt.show()``.  The caller decides whether to display, embed in a
GUI, or save.  Use ``_safe_save(save_path)`` before returning if persistence
is needed.

Functions
---------
plot_profit_vs_Q(results_df, Q_star, save_path)              → Figure
plot_convergence(running_avg, save_path)                     → Figure
plot_demand_histogram(demands_a, demands_b, mu_a, mu_b,
                      save_path)                             → Figure
plot_inventory_over_time(df, n_show, save_path)              → Figure
plot_stress_comparison(stress_results, save_path)            → Figure
plot_service_level_ci(results_df, save_path)                 → Figure
plot_hypothesis_test_results(comparisons, save_path)         → Figure
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


plt.rcParams.update({
    'figure.facecolor':  'white',
    'axes.facecolor':    '#f8f9fa',
    'axes.grid':         True,
    'grid.alpha':        0.4,
    'axes.spines.top':   False,
    'axes.spines.right': False,
    'font.size':         11,
})

_BLUE  = '#2563eb'
_RED   = '#dc2626'
_GREEN = '#16a34a'
_AMBER = '#d97706'


def _safe_save(save_path):
    """
    Save the current matplotlib figure to save_path.

    Creates parent directories automatically and catches all OS errors
    gracefully, printing a clear message instead of crashing the simulation.
    """
    if not save_path:
        return
    try:
        parent = os.path.dirname(save_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f'  ✅  Saved: {save_path}')
    except OSError as exc:
        print(f'  ⚠️  Could not save figure to {save_path!r}: {exc}')


# ---------------------------------------------------------------------------

def plot_profit_vs_Q(results_df, Q_star, save_path=None):
    """Line chart: average daily profit vs Q, with Q* highlighted.

    Returns
    -------
    fig : matplotlib.figure.Figure
    """
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(results_df['Q'], results_df['avg_profit'],
            'o-', color=_BLUE, lw=2.5, ms=7, label='Avg Total Profit (Simulation)')

    opt_row = results_df[results_df['Q'] == Q_star].iloc[0]
    ax.axvline(Q_star, color=_RED, ls='--', lw=1.8, label=f'Q* = {Q_star}')
    ax.scatter([Q_star], [opt_row['avg_profit']], color=_RED, s=140, zorder=5)

    ax.set_xlabel('Order Quantity Q (units)')
    ax.set_ylabel('Avg Daily Profit (EGP)')
    ax.set_title('Average Daily Profit vs Order Quantity Q',
                 fontsize=14, fontweight='bold')
    ax.legend()
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.0f'))
    plt.tight_layout()
    _safe_save(save_path)
    return fig


# ---------------------------------------------------------------------------

def plot_convergence(running_avg, save_path=None):
    """Running-average profit to demonstrate convergence.

    Returns
    -------
    fig : matplotlib.figure.Figure
    """
    final = running_avg[-1]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(np.arange(1, len(running_avg) + 1), running_avg,
            color=_BLUE, lw=1.5, label='Running Average Profit')
    ax.axhline(final, color=_RED, ls='--', lw=1.8,
               label=f'Converged ≈ {final:.1f} EGP')
    ax.set_xlabel('Measurement Day (after warm-up)')
    ax.set_ylabel('Running Avg Daily Profit (EGP)')
    ax.set_title('Convergence of Running Average Profit',
                 fontsize=14, fontweight='bold')
    ax.legend()
    plt.tight_layout()
    _safe_save(save_path)
    return fig


# ---------------------------------------------------------------------------

def plot_demand_histogram(demands_a, demands_b, mu_a, mu_b, save_path=None):
    """Dual histogram of realised demand for both products.

    Parameters
    ----------
    demands_a, demands_b : array-like   Realised daily demand series.
    mu_a, mu_b : float                  Theoretical mean (for reference line).
    save_path : str or None

    Returns
    -------
    fig : matplotlib.figure.Figure
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    items = [
        (axes[0], demands_a, mu_a, 'Ibuprofen (A)',   _BLUE),
        (axes[1], demands_b, mu_b, 'Paracetamol (B)', _GREEN),
    ]
    for ax, d, mu, label, color in items:
        ax.hist(d, bins=40, color=color, alpha=0.7, edgecolor='white')
        ax.axvline(mu,         color=_RED,   ls='--', lw=2,
                   label=f'μ = {mu}')
        ax.axvline(np.mean(d), color=_AMBER, ls=':',  lw=2,
                   label=f'Sample mean = {np.mean(d):.1f}')
        ax.set_xlabel('Daily Demand (units)')
        ax.set_ylabel('Frequency')
        ax.set_title(f'Demand Distribution — {label}',
                     fontsize=13, fontweight='bold')
        ax.legend()
    plt.tight_layout()
    _safe_save(save_path)
    return fig


# ---------------------------------------------------------------------------

def plot_inventory_over_time(df, n_show=365, save_path=None):
    """End-of-day on-hand inventory for both products over n_show days.

    Returns
    -------
    fig : matplotlib.figure.Figure
    """
    sub = df.head(n_show)
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(sub['day'], sub['inv_end_a'],
            color=_BLUE,  lw=1.2, label='Ibuprofen (A)')
    ax.plot(sub['day'], sub['inv_end_b'],
            color=_GREEN, lw=1.2, label='Paracetamol (B)', alpha=0.85)
    ax.set_xlabel('Simulation Day (after warm-up)')
    ax.set_ylabel('End-of-Day Inventory (units)')
    ax.set_title(f'Inventory Level Over Time (first {n_show} days shown)',
                 fontsize=13, fontweight='bold')
    ax.legend()
    plt.tight_layout()
    _safe_save(save_path)
    return fig


# ---------------------------------------------------------------------------

def plot_stress_comparison(stress_results, save_path=None):
    """Grouped bar comparing avg profit across stress scenarios.

    Returns
    -------
    fig : matplotlib.figure.Figure
    """
    names   = list(stress_results.keys())
    profits = [stress_results[n]['avg_profit'] for n in names]
    colors  = [_BLUE, _AMBER, _RED]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(names, profits, color=colors[:len(names)],
                  edgecolor='white', width=0.5)
    for bar, val in zip(bars, profits):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(profits) * 0.01,
                f'{val:.1f}', ha='center', va='bottom', fontsize=11)
    ax.set_ylabel('Avg Daily Profit (EGP)')
    ax.set_title('Stress Test — Average Profit by Scenario',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()
    _safe_save(save_path)
    return fig


# ---------------------------------------------------------------------------
# NEW: Service-Level Confidence Interval Plot
# ---------------------------------------------------------------------------

def plot_service_level_ci(results_df, save_path=None):
    """
    Plot cycle service level with Wilson 95 % confidence intervals for both
    products across all tested Q values.

    Parameters
    ----------
    results_df : pd.DataFrame
        Must contain columns: Q, service_level_a, sl_a_ci_lower, sl_a_ci_upper,
        service_level_b, sl_b_ci_lower, sl_b_ci_upper.
        These are produced by summarise() when called per-Q and assembled externally,
        OR passed in directly if the caller builds a per-Q summary table.
    save_path : str or None
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    Q = results_df['Q']

    # Product A
    ax.plot(Q, results_df['service_level_a'],
            'o-', color=_BLUE, lw=2.2, ms=6, label='Service Level A (Ibuprofen)')
    ax.fill_between(Q,
                    results_df['sl_a_ci_lower'],
                    results_df['sl_a_ci_upper'],
                    alpha=0.15, color=_BLUE, label='95 % CI — Product A')

    # Product B
    ax.plot(Q, results_df['service_level_b'],
            's-', color=_GREEN, lw=2.2, ms=6, label='Service Level B (Paracetamol)')
    ax.fill_between(Q,
                    results_df['sl_b_ci_lower'],
                    results_df['sl_b_ci_upper'],
                    alpha=0.15, color=_GREEN, label='95 % CI — Product B')

    ax.set_xlabel('Order Quantity Q (units)')
    ax.set_ylabel('Cycle Service Level')
    ax.set_title('Service Level with 95 % Wilson CI vs Order Quantity Q',
                 fontsize=13, fontweight='bold')
    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1, decimals=0))
    ax.legend(fontsize=9)
    plt.tight_layout()
    _safe_save(save_path)
    return fig


# ---------------------------------------------------------------------------
# NEW: Hypothesis-Test Results Plot
# ---------------------------------------------------------------------------

def plot_hypothesis_test_results(comparisons, save_path=None):
    """
    Visualise pairwise Welch t-test results from compare_stress_scenarios().

    Displays a bar chart of |t-statistics| with significance markers and a
    table of p-values, making it easy to see which scenario differences are
    statistically meaningful.

    Parameters
    ----------
    comparisons : list of dict
        As returned by simulation.compare_stress_scenarios().
        Keys: scenario_a, scenario_b, mean_a, mean_b, t_stat, p_value, significant.
    save_path : str or None
    """
    labels  = [f"{c['scenario_a']}\nvs\n{c['scenario_b']}" for c in comparisons]
    t_stats = [abs(c['t_stat']) for c in comparisons]
    p_vals  = [c['p_value'] for c in comparisons]
    sig     = [c['significant'] for c in comparisons]
    colors  = [_RED if s else _AMBER for s in sig]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Left: |t-statistic| bar chart
    bars = ax1.bar(labels, t_stats, color=colors, edgecolor='white', width=0.5)
    for bar, p, s in zip(bars, p_vals, sig):
        marker = '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'ns'
        ax1.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + max(t_stats) * 0.02,
                 marker, ha='center', va='bottom', fontsize=13,
                 color=_RED if s else _AMBER)
    ax1.set_ylabel('|t-statistic| (Welch t-test)')
    ax1.set_title('Pairwise Scenario Comparison\n(* p<0.05  ** p<0.01  *** p<0.001)',
                  fontsize=12, fontweight='bold')

    # Right: p-value table
    ax2.axis('off')
    col_labels = ['Pair', 'Mean A', 'Mean B', 'p-value', 'Sig?']
    table_data = [
        [f"{c['scenario_a']} vs {c['scenario_b']}",
         f"{c['mean_a']:.1f}",
         f"{c['mean_b']:.1f}",
         f"{c['p_value']:.4f}",
         'YES' if c['significant'] else 'NO']
        for c in comparisons
    ]
    tbl = ax2.table(cellText=table_data, colLabels=col_labels,
                    loc='center', cellLoc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.scale(1, 1.8)
    ax2.set_title('p-value Summary Table', fontsize=12, fontweight='bold')

    plt.tight_layout()
    _safe_save(save_path)
    return fig
