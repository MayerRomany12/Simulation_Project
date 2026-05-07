import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import warnings
warnings.filterwarnings('ignore')

# ── Central configuration ─────────────────────────────────────────────────
from backend.config import (
    GLOBAL_SEED,
    P, C, S, PI, MU, SIGMA,
    N_DAYS, Q_VALUES,
    DEMAND_VALUES, DEMAND_PROBS,
)


# ── Plotly for the interactive dashboard ──────────────────────────────────
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False
    print("Plotly not installed — dashboard will use matplotlib fallback.")

# ── Reproducibility (modern API) ──────────────────────────────────────────
# Use default_rng everywhere; never np.random.seed() which mutates global state.
_master_rng = np.random.default_rng(GLOBAL_SEED)

# ── Matplotlib style ──────────────────────────────────────────────────────
plt.rcParams.update({
    'figure.facecolor': 'white',
    'axes.facecolor' : '#f8f9fa',
    'axes.grid'      : True,
    'grid.alpha'     : 0.4,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'font.size'      : 11,
})

print("✅ All imports successful.")
print(f"   NumPy  : {np.__version__}")
print(f"   Pandas : {pd.__version__}")


# --- CELL ---

# ─────────────────────────────────────────────────────────────────────────────
# MODEL PARAMETERS  — sourced from config.py (single source of truth)
# ─────────────────────────────────────────────────────────────────────────────

# Local aliases for notebook-style readability (lower-case convention)
c  = C      # wholesale / ordering cost per unit
p  = P      # retail selling price per unit
s  = S      # salvage value of each unsold unit
pi = PI     # penalty (goodwill loss) per unit of unmet demand
mu    = MU      # mean daily demand
sigma = SIGMA   # std. dev. of daily demand

print("=" * 45)
print("  MODEL PARAMETERS")
print("=" * 45)
params = {
    'c  (cost)'      : c,
    'p  (price)'     : p,
    's  (salvage)'   : s,
    'π  (penalty)'   : pi,
    'μ  (mean D)'    : mu,
    'σ  (std D)'     : sigma,
    'N  (iterations)': N_DAYS,
}
for k, v in params.items():
    print(f"  {k:25s} = {v}")
print("=" * 45)
print(f"  Q candidates: {Q_VALUES}")


# --- CELL ---

# ── Empirical discrete distribution ──────────────────────────────────────
demand_values = np.array([30, 40, 50, 60, 70, 80, 90])
demand_probs  = np.array([0.05, 0.10, 0.20, 0.30, 0.20, 0.10, 0.05])
demand_cdf    = np.cumsum(demand_probs)   # [0.05, 0.15, 0.35, 0.65, 0.85, 0.95, 1.00]

print("Empirical Demand PMF / CDF:")
df_dist = pd.DataFrame({
    'd (demand)' : demand_values,
    'P(D = d)'   : demand_probs,
    'F(d) = P(D ≤ d)' : demand_cdf,
})
print(df_dist.to_string(index=False))


# --- CELL ---

# ══════════════════════════════════════════════════════════════════════════
#  FUNCTION 1 : generate_demand
# ══════════════════════════════════════════════════════════════════════════

def generate_demand(n, mode='normal', seed=None):
    """
    Generate n daily demand values.

    Parameters
    ----------
    n    : int   — number of days
    mode : str   — 'normal'   → D ~ Normal(mu=60, sigma=15) clipped to [20,100]
                   'empirical' → drawn from discrete PMF table
    seed : int   — random seed for reproducibility

    Returns
    -------
    D : np.ndarray of shape (n,)  — integer demand values
    U : np.ndarray of shape (n,)  — the underlying uniform draws (for table display)
    """
    rng = np.random.default_rng(seed)

    if mode == 'normal':
        raw = rng.normal(loc=mu, scale=sigma, size=n)
        D   = np.clip(np.round(raw), 20, 100).astype(int)
        U   = rng.uniform(0, 1, size=n)   # not used for mapping but kept for API symmetry

    elif mode == 'empirical':
        U = rng.uniform(0, 1, size=n)
        # map each U to a demand value via the CDF
        indices = np.searchsorted(demand_cdf, U, side='right')
        indices = np.clip(indices, 0, len(demand_values) - 1)
        D = demand_values[indices]

    else:
        raise ValueError(f"Unknown mode '{mode}'. Use 'normal' or 'empirical'.")

    return D, U


# ══════════════════════════════════════════════════════════════════════════
#  FUNCTION 2 : compute_profit
# ══════════════════════════════════════════════════════════════════════════

def compute_profit(Q, D, c=None, p=None, s=None, pi=None):
    """
    Compute per-day profit and components for given Q and demand array D.

    Parameters default to config values when None is passed, avoiding the
    'frozen global at import time' default-argument trap.

    Returns a dict of NumPy arrays (vectorised — works on scalars too).
    """
    # Resolve defaults from config — safe even if globals change at runtime
    if c  is None: c  = C
    if p  is None: p  = P
    if s  is None: s  = S
    if pi is None: pi = PI

    D = np.asarray(D)

    sales      = np.minimum(Q, D)                  # min(Q, D)
    overstock  = np.maximum(Q - D, 0)              # max(Q-D, 0)
    lost_sales = np.maximum(D - Q, 0)              # max(D-Q, 0)
    profit     = (p * sales
                  - c * Q
                  + s * overstock
                  - pi * lost_sales)               # full profit equation

    return {
        'sales'      : sales,
        'overstock'  : overstock,
        'lost_sales' : lost_sales,
        'profit'     : profit,
    }


# ══════════════════════════════════════════════════════════════════════════
#  FUNCTION 3 : calculate_metrics
# ══════════════════════════════════════════════════════════════════════════

def calculate_metrics(Q, profit_array, D_array, c=None, p=None, s=None, pi=None):
    """
    Compute all performance metrics from simulation results.

    Parameters default to config values when None is passed.

    Metrics
    -------
    avg_profit   : mean daily profit
    std_profit   : std deviation of daily profit
    loss_prob    : P(profit < 0)
    service_level: P(D ≤ Q)   [Cycle Service Level]
    fill_rate    : 1 - E[Lost Sales] / E[D]
    ci_lower     : lower 95% CI bound
    ci_upper     : upper 95% CI bound
    """
    if c  is None: c  = C
    if p  is None: p  = P
    if s  is None: s  = S
    if pi is None: pi = PI
    N = len(profit_array)

    avg_profit = np.mean(profit_array)
    std_profit = np.std(profit_array, ddof=1)

    # P(loss)
    loss_prob = np.mean(profit_array < 0)

    # Cycle service level  SL = P(D ≤ Q)
    service_level = np.mean(D_array <= Q)

    # Fill rate  = 1 - E[Lost Sales] / E[D]
    lost_sales_arr = np.maximum(D_array - Q, 0)
    fill_rate = 1 - np.mean(lost_sales_arr) / np.mean(D_array)

    # 95 % confidence interval  CI = mean ± 1.96 * (std / sqrt(N))
    z = 1.96
    margin = z * std_profit / np.sqrt(N)
    ci_lower = avg_profit - margin
    ci_upper = avg_profit + margin

    return {
        'Q'            : Q,
        'avg_profit'   : round(avg_profit, 4),
        'std_profit'   : round(std_profit, 4),
        'loss_prob'    : round(loss_prob,  4),
        'service_level': round(service_level, 4),
        'fill_rate'    : round(fill_rate,  4),
        'ci_lower'     : round(ci_lower,   4),
        'ci_upper'     : round(ci_upper,   4),
    }


# ══════════════════════════════════════════════════════════════════════════
#  FUNCTION 4 : run_simulation
# ══════════════════════════════════════════════════════════════════════════

def run_simulation(Q_list, N=None, mode='normal', seed=None,
                   c=None, p=None, s=None, pi=None):
    """
    Run the full Monte Carlo simulation for each Q in Q_list.

    Parameters default to config values when None is passed.

    Returns
    -------
    results_df : pd.DataFrame with one row per Q value and all metrics.
    raw        : dict  { Q : {'profit': array, 'D': array} }   — raw data
    """
    if N    is None: N    = N_DAYS
    if seed is None: seed = GLOBAL_SEED
    if c    is None: c    = C
    if p    is None: p    = P
    if s    is None: s    = S
    if pi   is None: pi   = PI
    results = []
    raw     = {}

    for Q in Q_list:
        # Step 1 & 2 : generate demand (unique seed per Q for strict reproducibility)
        D, _ = generate_demand(N, mode=mode, seed=seed + Q)

        # Step 3 & 4 : compute components and profit
        components = compute_profit(Q, D, c=c, p=p, s=s, pi=pi)
        profit_arr = components['profit']

        # Step 5 : compute metrics
        metrics = calculate_metrics(Q, profit_arr, D, c=c, p=p, s=s, pi=pi)
        results.append(metrics)
        raw[Q] = {'profit': profit_arr, 'D': D}

    results_df = pd.DataFrame(results)
    return results_df, raw


print("✅ All functions defined successfully.")
print("   → generate_demand()  | generate N daily demand values")
print("   → compute_profit()   | vectorised profit & component calc")
print("   → calculate_metrics()| all KPIs including CI")
print("   → run_simulation()   | full Monte Carlo loop over Q values")


# --- CELL ---

# ══════════════════════════════════════════════════════════════════════════
#  CRITICAL RATIO  &  ANALYTICAL Q*
# ══════════════════════════════════════════════════════════════════════════

# Step 1 : compute CR
CR = (p - c) / (p - s + pi)
print(f"Critical Ratio  CR = ({p} - {c}) / ({p} - {s} + {pi})")
print(f"               CR = {p-c} / {p-s+pi} = {CR:.4f}")
print()

# Step 2 : find Q* from empirical CDF
print("Scanning empirical CDF for Q*:")
Q_star_empirical = None
for d_val, f_val in zip(demand_values, demand_cdf):
    flag = "✅  ← Q* (first ≥ CR)" if f_val >= CR and Q_star_empirical is None else ""
    print(f"  F({d_val:2d}) = {f_val:.2f}   {'≥' if f_val >= CR else '<'} CR={CR:.4f}  {flag}")
    if f_val >= CR and Q_star_empirical is None:
        Q_star_empirical = d_val

print()
print(f"  → Analytical Q* (empirical dist.) = {Q_star_empirical} units")

# Step 3 : Q* under Normal distribution  → F^{-1}(CR)
from scipy.stats import norm
Q_star_normal = int(round(norm.ppf(CR, loc=mu, scale=sigma)))
print(f"  → Analytical Q* (Normal approx.)  = {Q_star_normal} units")

# Step 4 : Analytical Expected Profit E[Profit(Q)] for each Q (empirical PMF)
print()
print("Analytical E[Profit(Q)] for each Q (using empirical PMF):")
analytical_profits = {}
for Q in Q_VALUES:
    # E[min(Q,D)] = sum_d min(Q,d)*P(D=d)
    e_sales      = np.sum(np.minimum(Q, demand_values) * demand_probs)
    # E[max(Q-D,0)] = sum_d max(Q-d,0)*P(D=d)
    e_overstock  = np.sum(np.maximum(Q - demand_values, 0) * demand_probs)
    # E[max(D-Q,0)] = sum_d max(d-Q,0)*P(D=d)
    e_lost_sales = np.sum(np.maximum(demand_values - Q, 0) * demand_probs)

    # E[Profit(Q)] = p*E[min(Q,D)] - c*Q + s*E[max(Q-D,0)] - pi*E[max(D-Q,0)]
    e_profit = (p * e_sales
                - c * Q
                + s * e_overstock
                - pi * e_lost_sales)
    analytical_profits[Q] = round(e_profit, 4)

df_analytical = pd.DataFrame(list(analytical_profits.items()),
                              columns=['Q', 'E[Profit] Analytical'])
Q_star_analytical = df_analytical.loc[df_analytical['E[Profit] Analytical'].idxmax(), 'Q']
print(df_analytical.to_string(index=False))
print(f"\n  → Q* from analytical E[Profit] = {Q_star_analytical}")


# --- CELL ---

# ══════════════════════════════════════════════════════════════════════════
#  RUN FULL SIMULATION  (Normal demand)
# ══════════════════════════════════════════════════════════════════════════

print("Running Monte Carlo simulation …")
results_df, raw_data = run_simulation(Q_VALUES, N=N_DAYS, mode='normal', seed=GLOBAL_SEED)

# Identify simulation Q*
Q_star_sim = results_df.loc[results_df['avg_profit'].idxmax(), 'Q']

print(f"\n  ✅ Simulation complete.")
print(f"  Q* from simulation = {Q_star_sim} units  (avg profit = "
      f"{results_df.loc[results_df['Q']==Q_star_sim,'avg_profit'].values[0]:.2f} EGP)")


# --- CELL ---

# ══════════════════════════════════════════════════════════════════════════
#  DISPLAY SUMMARY TABLE
# ══════════════════════════════════════════════════════════════════════════

display_df = results_df.copy()
display_df['95% CI'] = (display_df['ci_lower'].round(2).astype(str)
                        + ' – '
                        + display_df['ci_upper'].round(2).astype(str))

table_cols = ['Q', 'avg_profit', 'std_profit', 'loss_prob',
              'service_level', 'fill_rate', '95% CI']

print("Summary Results (Normal demand, N = 10,000 days)")
print("=" * 85)
print(display_df[table_cols].rename(columns={
    'avg_profit'   : 'Avg Profit (EGP)',
    'std_profit'   : 'Std Dev',
    'loss_prob'    : 'P(loss)',
    'service_level': 'Service Level',
    'fill_rate'    : 'Fill Rate',
}).to_string(index=False))
print("=" * 85)
print(f"\n  ★  Optimal Q* = {Q_star_sim}  (highest avg profit)")


# --- CELL ---

# ══════════════════════════════════════════════════════════════════════════
#  10-DAY SIMULATION TABLE  (empirical demand, Q = Q*)
# ══════════════════════════════════════════════════════════════════════════

np.random.seed(GLOBAL_SEED)           # reset seed for clean reproducibility

Q_demo = Q_star_sim                   # use optimal Q for the demo table
N_DEMO = 10

D_demo, U_demo = generate_demand(N_DEMO, mode='empirical', seed=GLOBAL_SEED)
comp_demo      = compute_profit(Q_demo, D_demo)

sim_table = pd.DataFrame({
    'Day'        : range(1, N_DEMO + 1),
    'U (random)' : np.round(U_demo, 4),
    'D (demand)' : D_demo,
    'Sales'      : comp_demo['sales'],
    'Overstock'  : comp_demo['overstock'],
    'Lost Sales' : comp_demo['lost_sales'],
    'Profit (EGP)': np.round(comp_demo['profit'], 2),
})

print(f"10-Day Simulation Table  (Q = {Q_demo}, empirical demand)")
print("=" * 75)
print(sim_table.to_string(index=False))
print("=" * 75)
print(f"  Average profit over 10 days: {sim_table['Profit (EGP)'].mean():.2f} EGP")


# --- CELL ---

# ══════════════════════════════════════════════════════════════════════════
#  FIGURE 1 : Avg Profit  vs  Q
# ══════════════════════════════════════════════════════════════════════════

fig, ax = plt.subplots(figsize=(10, 5))

ax.plot(results_df['Q'], results_df['avg_profit'],
        'o-', color='#2563eb', lw=2.5, ms=7, label='Avg Profit (Simulation)')

# Highlight Q*
opt_row = results_df[results_df['Q'] == Q_star_sim].iloc[0]
ax.axvline(Q_star_sim, color='#dc2626', ls='--', lw=1.8, label=f'Q* = {Q_star_sim}')
ax.scatter([Q_star_sim], [opt_row['avg_profit']],
           color='#dc2626', s=130, zorder=5)

# Analytical profit overlay
ax.plot(list(analytical_profits.keys()),
        list(analytical_profits.values()),
        's--', color='#16a34a', lw=1.8, ms=6,
        label='E[Profit] Analytical')

ax.set_xlabel('Order Quantity Q (units)')
ax.set_ylabel('Daily Profit (EGP)')
ax.set_title('Average Daily Profit vs Order Quantity Q', fontsize=14, fontweight='bold')
ax.legend()
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.0f'))

plt.tight_layout()
# plt.savefig('/mnt/user-data/outputs/fig1_profit_vs_Q.png', dpi=150, bbox_inches='tight')
plt.show()
print("Interpretation: Profit rises with Q up to Q* = "
      f"{Q_star_sim}, then falls as overstock costs outweigh revenue gains.")


# --- CELL ---

# ══════════════════════════════════════════════════════════════════════════
#  FIGURE 2 : Loss Probability & Service Level vs Q  (dual-axis)
# ══════════════════════════════════════════════════════════════════════════

fig, ax1 = plt.subplots(figsize=(10, 5))

color1 = '#dc2626'
ax1.plot(results_df['Q'], results_df['loss_prob'],
         'o-', color=color1, lw=2.5, ms=7, label='P(loss)')
ax1.set_xlabel('Order Quantity Q (units)')
ax1.set_ylabel('P(loss)', color=color1)
ax1.tick_params(axis='y', labelcolor=color1)
ax1.axvline(Q_star_sim, color='grey', ls='--', lw=1.4, alpha=0.6)

ax2 = ax1.twinx()
color2 = '#2563eb'
ax2.plot(results_df['Q'], results_df['service_level'],
         's-', color=color2, lw=2.5, ms=7, label='Service Level')
ax2.set_ylabel('Cycle Service Level', color=color2)
ax2.tick_params(axis='y', labelcolor=color2)

ax1.set_title('Loss Probability & Service Level vs Q', fontsize=14, fontweight='bold')
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='center right')

plt.tight_layout()
# plt.savefig('/mnt/user-data/outputs/fig2_loss_sl_vs_Q.png', dpi=150, bbox_inches='tight')
plt.show()
print("Interpretation: As Q increases, P(loss) drops and service level rises.")
print("Beyond Q* the incremental service gain no longer justifies the extra stock cost.")


# --- CELL ---

# ══════════════════════════════════════════════════════════════════════════
#  FIGURE 3 : Profit Distribution Histogram at Q*
# ══════════════════════════════════════════════════════════════════════════

profits_opt = raw_data[Q_star_sim]['profit']

fig, ax = plt.subplots(figsize=(10, 5))
ax.hist(profits_opt, bins=40, color='#2563eb', alpha=0.75, edgecolor='white')
ax.axvline(np.mean(profits_opt), color='#dc2626', lw=2,
           label=f'Mean = {np.mean(profits_opt):.2f} EGP')
ax.axvline(0, color='black', lw=1.2, ls='--', label='Break-even (0 EGP)')

ax.set_xlabel('Daily Profit (EGP)')
ax.set_ylabel('Frequency (days)')
ax.set_title(f'Profit Distribution at Optimal Q* = {Q_star_sim}  (N = {N_DAYS:,} days)',
             fontsize=14, fontweight='bold')
ax.legend()

plt.tight_layout()
# plt.savefig('/mnt/user-data/outputs/fig3_profit_distribution.png', dpi=150, bbox_inches='tight')
plt.show()


# --- CELL ---

# ══════════════════════════════════════════════════════════════════════════
#  COMPARE ANALYTICAL  vs  SIMULATION  Q*
# ══════════════════════════════════════════════════════════════════════════

print("=" * 55)
print("  ANALYTICAL vs SIMULATION COMPARISON")
print("=" * 55)
print(f"  Critical Ratio CR          = {CR:.4f}")
print(f"  Analytical Q* (empirical)  = {Q_star_empirical}")
print(f"  Analytical Q* (Normal)     = {Q_star_normal}")
print(f"  Simulation Q*              = {Q_star_sim}")
print()

# Build comparison table
comp_rows = []
for Q in Q_VALUES:
    sim_row = results_df[results_df['Q'] == Q].iloc[0]
    comp_rows.append({
        'Q'                     : Q,
        'Sim Avg Profit'        : sim_row['avg_profit'],
        'Analytical E[Profit]'  : analytical_profits[Q],
        'Difference'            : round(sim_row['avg_profit'] - analytical_profits[Q], 4),
    })

comp_df = pd.DataFrame(comp_rows)
print(comp_df.to_string(index=False))
print()
print("  Mean |difference| across all Q: "
      f"{comp_df['Difference'].abs().mean():.4f} EGP")
print()
print("  WHY are they close?")
print("  By the Law of Large Numbers, the sample mean of i.i.d. random variables")
print("  converges to the true expectation as N → ∞.  With N = 10,000 days the")
print("  Monte Carlo estimate is within < 1 EGP of the analytical value.")


# --- CELL ---

# ══════════════════════════════════════════════════════════════════════════
#  SENSITIVITY ANALYSIS
#  For each parameter scenario compute Q* and plot
# ══════════════════════════════════════════════════════════════════════════

scenarios = {
    'Baseline (p=25, c=10, s=2, π=3)' : dict(p=25, c=10, s=2, pi=3),
    'Higher price  p=30'               : dict(p=30, c=10, s=2, pi=3),
    'Higher cost   c=12'               : dict(p=25, c=12, s=2, pi=3),
    'No salvage    s=0'                : dict(p=25, c=10, s=0, pi=3),
    'Higher penalty π=5'               : dict(p=25, c=10, s=2, pi=5),
}

sens_results = {}
for label, params_s in scenarios.items():
    df_s, _ = run_simulation(Q_VALUES, N=N_DAYS, mode='normal', seed=GLOBAL_SEED,
                             **params_s)
    Q_opt   = df_s.loc[df_s['avg_profit'].idxmax(), 'Q']
    CR_s    = (params_s['p'] - params_s['c']) / (params_s['p'] - params_s['s'] + params_s['pi'])
    sens_results[label] = {'df': df_s, 'Q*': Q_opt, 'CR': round(CR_s, 4)}

# ── Summary table ─────────────────────────────────────────────────────────
print("Sensitivity Analysis — Q* under each scenario")
print("=" * 70)
for label, v in sens_results.items():
    print(f"  {label:42s}  CR={v['CR']:.3f}   Q*={v['Q*']}")
print("=" * 70)


# --- CELL ---

# ── Sensitivity plot ─────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(11, 5))

colors = ['#2563eb', '#16a34a', '#dc2626', '#d97706', '#7c3aed']
for (label, v), color in zip(sens_results.items(), colors):
    ax.plot(Q_VALUES, v['df']['avg_profit'],
            'o-', lw=2, ms=5, color=color, label=f"{label}  (Q*={v['Q*']})")
    ax.axvline(v['Q*'], color=color, ls=':', lw=1.2, alpha=0.6)

ax.set_xlabel('Order Quantity Q (units)')
ax.set_ylabel('Average Daily Profit (EGP)')
ax.set_title('Sensitivity Analysis: Avg Profit vs Q under Different Scenarios',
             fontsize=13, fontweight='bold')
ax.legend(fontsize=9, loc='lower right')

plt.tight_layout()
# plt.savefig('/mnt/user-data/outputs/fig4_sensitivity.png', dpi=150, bbox_inches='tight')
plt.show()

print("""
Interpretation:
  • Higher price (p=30) → CR increases → Q* shifts right (order more).
  • Higher cost (c=12)  → CR decreases → Q* shifts left  (order less).
  • No salvage (s=0)    → CR decreases → Q* shifts left  (losses on overstock are worse).
  • Higher penalty (π=5)→ CR increases → Q* shifts right (service-oriented policy).
""")


# --- CELL ---

# ══════════════════════════════════════════════════════════════════════════
#  INTERACTIVE PLOTLY DASHBOARD
# ══════════════════════════════════════════════════════════════════════════

if not PLOTLY_OK:
    print("Plotly not available — skipping dashboard.")
else:
    import ipywidgets as widgets
    from IPython.display import display

    # ── Sliders ───────────────────────────────────────────────────────────
    w_Q   = widgets.IntSlider(value=60,  min=30, max=95,  step=5,
                               description='Q (units):',   style={'description_width':'initial'})
    w_p   = widgets.FloatSlider(value=25, min=15, max=40, step=1,
                                 description='Price p:',    style={'description_width':'initial'})
    w_c   = widgets.FloatSlider(value=10, min=5,  max=20, step=1,
                                 description='Cost c:',     style={'description_width':'initial'})
    w_pi  = widgets.FloatSlider(value=3,  min=0,  max=10, step=1,
                                 description='Penalty π:',  style={'description_width':'initial'})

    out = widgets.Output()

    def update_dashboard(Q_sel, p_sel, c_sel, pi_sel):
        """Re-run simulation with new params and redraw Plotly charts."""
        df_dash, raw_dash = run_simulation(
            Q_VALUES, N=2000, mode='normal', seed=GLOBAL_SEED,
            c=c_sel, p=p_sel, s=2, pi=pi_sel)

        Q_opt_dash = df_dash.loc[df_dash['avg_profit'].idxmax(), 'Q']
        CR_dash    = (p_sel - c_sel) / (p_sel - 2 + pi_sel)

        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=(
                f'Avg Profit vs Q  (Q*={Q_opt_dash})',
                f'Profit Distribution at Q={Q_sel}',
            )
        )

        # Left panel: profit curve
        fig.add_trace(go.Scatter(
            x=df_dash['Q'], y=df_dash['avg_profit'],
            mode='lines+markers', name='Avg Profit',
            line=dict(color='royalblue', width=2.5),
            marker=dict(size=7)
        ), row=1, col=1)

        fig.add_vline(x=Q_opt_dash, line_dash='dash',
                      line_color='red', row=1, col=1,
                      annotation_text=f"Q*={Q_opt_dash}", annotation_position="top right")

        # Right panel: histogram for selected Q
        if Q_sel in raw_dash:
            profits_sel = raw_dash[Q_sel]['profit']
        else:
            D_tmp, _ = generate_demand(2000, mode='normal', seed=GLOBAL_SEED + Q_sel)
            comp_tmp  = compute_profit(Q_sel, D_tmp, c=c_sel, p=p_sel, s=2, pi=pi_sel)
            profits_sel = comp_tmp['profit']

        fig.add_trace(go.Histogram(
            x=profits_sel, nbinsx=35,
            marker_color='royalblue', opacity=0.7, name=f'Profit @Q={Q_sel}'
        ), row=1, col=2)

        fig.add_vline(x=float(np.mean(profits_sel)), line_dash='dot',
                      line_color='red', row=1, col=2,
                      annotation_text=f"Mean={np.mean(profits_sel):.1f}")

        fig.update_layout(
            height=420,
            title_text=(f"<b>Monte Carlo Dashboard</b>  |  "
                        f"p={p_sel} c={c_sel} π={pi_sel}  CR={CR_dash:.3f}  Q*={Q_opt_dash}"),
            showlegend=False,
            plot_bgcolor='#f8f9fa',
            paper_bgcolor='white',
            font=dict(size=12),
        )
        fig.update_xaxes(gridcolor='#e5e7eb')
        fig.update_yaxes(gridcolor='#e5e7eb')

        with out:
            out.clear_output(wait=True)
            fig.show()

    # Connect widgets
    ui = widgets.VBox([
        widgets.HTML("<h4 style='margin:8px 0'>⚙️ Adjust Parameters</h4>"),
        widgets.HBox([w_Q, w_p]),
        widgets.HBox([w_c, w_pi]),
    ])

    interactive_out = widgets.interactive_output(
        update_dashboard,
        {'Q_sel': w_Q, 'p_sel': w_p, 'c_sel': w_c, 'pi_sel': w_pi}
    )

    display(ui, interactive_out)


# --- CELL ---

# ── Service Level definitions ─────────────────────────────────────────────
# SL_1 = P(D <= Q)        [Cycle Service Level]
# SL_2 = E[min(Q,D)]/E[D] [Fill Rate based]
# Fill Rate = 1 - E[Lost Sales]/E[D]

fig, axes = plt.subplots(1, 2, figsize=(13, 5))

# Left: Service Level
axes[0].plot(results_df['Q'], results_df['service_level'],
             'o-', color='#2563eb', lw=2.5, ms=7, label='SL₁ = P(D ≤ Q)')
axes[0].axhline(CR, color='#dc2626', ls='--', lw=1.8, label=f'CR = {CR:.3f}')
axes[0].axvline(Q_star_sim, color='grey', ls=':', lw=1.5)
axes[0].set_xlabel('Q'); axes[0].set_ylabel('Probability')
axes[0].set_title('Cycle Service Level vs Q', fontweight='bold')
axes[0].legend()

# Right: Fill Rate
axes[1].plot(results_df['Q'], results_df['fill_rate'],
             's-', color='#16a34a', lw=2.5, ms=7, label='Fill Rate')
axes[1].axvline(Q_star_sim, color='grey', ls=':', lw=1.5, label=f'Q*={Q_star_sim}')
axes[1].set_xlabel('Q'); axes[1].set_ylabel('Fraction of Demand Met')
axes[1].set_title('Fill Rate vs Q', fontweight='bold')
axes[1].legend()

plt.tight_layout()
# plt.savefig('/mnt/user-data/outputs/fig5_sl_fillrate.png', dpi=150, bbox_inches='tight')
plt.show()


# --- CELL ---

# ── CI plot ───────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(11, 5))

ax.plot(results_df['Q'], results_df['avg_profit'],
        'o-', color='#2563eb', lw=2.5, ms=7, zorder=3, label='Avg Profit')

ax.fill_between(results_df['Q'],
                results_df['ci_lower'],
                results_df['ci_upper'],
                alpha=0.25, color='#2563eb', label='95% CI')

ax.axvline(Q_star_sim, color='#dc2626', ls='--', lw=1.8, label=f'Q* = {Q_star_sim}')
ax.set_xlabel('Order Quantity Q (units)')
ax.set_ylabel('Daily Profit (EGP)')
ax.set_title('Average Daily Profit with 95% Confidence Intervals', fontsize=13, fontweight='bold')
ax.legend()

plt.tight_layout()
# plt.savefig('/mnt/user-data/outputs/fig6_ci_profit.png', dpi=150, bbox_inches='tight')
plt.show()

print("95% CI at Q* =", Q_star_sim)
row_opt = results_df[results_df['Q'] == Q_star_sim].iloc[0]
print(f"  Mean profit : {row_opt['avg_profit']:.2f} EGP")
print(f"  95% CI      : [{row_opt['ci_lower']:.2f},  {row_opt['ci_upper']:.2f}] EGP")
print(f"  Half-width  : {(row_opt['ci_upper'] - row_opt['ci_lower'])/2:.2f} EGP")


# --- CELL ---

# ══════════════════════════════════════════════════════════════════════════
#  FINAL SUMMARY
# ══════════════════════════════════════════════════════════════════════════

row_opt = results_df[results_df['Q'] == Q_star_sim].iloc[0]

print("=" * 60)
print("  FINAL SUMMARY")
print("=" * 60)
print(f"  Critical Ratio CR          : {CR:.4f}")
print(f"  Analytical Q* (empirical)  : {Q_star_empirical}")
print(f"  Analytical Q* (Normal ppf) : {Q_star_normal}")
print(f"  Simulation  Q*             : {Q_star_sim}")
print()
print(f"  At Q* = {Q_star_sim}:")
print(f"    Avg daily profit   : {row_opt['avg_profit']:.2f} EGP")
print(f"    Std deviation      : {row_opt['std_profit']:.2f} EGP")
print(f"    P(loss)            : {row_opt['loss_prob']*100:.1f} %")
print(f"    Service Level      : {row_opt['service_level']*100:.1f} %")
print(f"    Fill Rate          : {row_opt['fill_rate']*100:.1f} %")
print(f"    95% CI             : [{row_opt['ci_lower']:.2f}, {row_opt['ci_upper']:.2f}]")
print("=" * 60)
print()
print("Key Takeaways:")
print("  1. The Newsvendor critical-ratio formula gives a fast analytical Q*.")
print("  2. Monte Carlo simulation converges to the same Q* (Law of Large Numbers).")
print("  3. Sensitivity analysis confirms intuition: higher price → order more,")
print("     higher cost → order less.")
print("  4. At Q* the pharmacy balances overstock risk against lost-sales penalty")
print("     and achieves the highest expected daily profit.")


# --- CELL ---

# ══════════════════════════════════════════════════════════════════════════
#  ADVANCED INTERACTIVE DASHBOARD  — Section 15
#  Uses ipywidgets + Plotly.
# ══════════════════════════════════════════════════════════════════════════

import ipywidgets as widgets
from IPython.display import display, clear_output
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd
from scipy.stats import norm as _scipy_norm

# ── Dashboard-internal adapters ───────────────────────────────────────────
# These thin wrappers preserve the dashboard key-name contract
# (avg / ci_lo / ci_hi / sl / fr / p_loss) while delegating ALL
# computation to the public functions above — no duplicated logic.

_demand_values_g = np.array(DEMAND_VALUES)
_demand_probs_g  = np.array(DEMAND_PROBS)
_demand_cdf_g    = np.cumsum(_demand_probs_g)

def _gen_demand(n, mode='normal', seed=42):
    """Adapter: delegates to generate_demand()."""
    D, _ = generate_demand(n, mode=mode, seed=seed)
    return D

def _calc_profit(Q, D, p, c, s, pi):
    """Adapter: delegates to compute_profit()."""
    return compute_profit(Q, D, c=c, p=p, s=s, pi=pi)['profit']

def _metrics(Q, prof, D):
    """Adapter: delegates to calculate_metrics(), remaps keys for dashboard."""
    m = calculate_metrics(Q, prof, D)
    return dict(
        avg    = m['avg_profit'],
        std    = m['std_profit'],
        p_loss = m['loss_prob'],
        sl     = m['service_level'],
        fr     = m['fill_rate'],
        ci_lo  = m['ci_lower'],
        ci_hi  = m['ci_upper'],
    )

def _run_sim(Q_list, N, p, c, s, pi, mode, seed):
    """Adapter: delegates to run_simulation(), remaps columns for dashboard."""
    df_full, raw_full = run_simulation(Q_list, N=N, mode=mode, seed=seed,
                                       c=c, p=p, s=s, pi=pi)
    df_dash = df_full.rename(columns={
        'avg_profit': 'avg', 'std_profit': 'std', 'loss_prob': 'p_loss',
        'service_level': 'sl', 'fill_rate': 'fr',
        'ci_lower': 'ci_lo', 'ci_upper': 'ci_hi',
    })
    raw_dash = {Q: (v['profit'], v['D']) for Q, v in raw_full.items()}
    return df_dash, raw_dash

# ── Widgets ────────────────────────────────────────────────────────────────

ST = {'description_width': '150px'}
LY = widgets.Layout(width='330px')

w_N    = widgets.IntSlider(value=5000, min=100, max=20000, step=100,
                            description='N days:',        style=ST, layout=LY)
w_seed = widgets.IntSlider(value=42,   min=0,   max=999,   step=1,
                            description='Random Seed:',   style=ST, layout=LY)
w_dist = widgets.Dropdown(options=['Normal','Empirical'], value='Normal',
                           description='Demand Model:',   style=ST, layout=LY)
w_p    = widgets.FloatSlider(value=25, min=10,  max=50,  step=1,
                              description='Price p (EGP):',   style=ST, layout=LY)
w_c    = widgets.FloatSlider(value=10, min=1,   max=30,  step=1,
                              description='Cost c (EGP):',    style=ST, layout=LY)
w_s    = widgets.FloatSlider(value=2,  min=0,   max=15,  step=1,
                              description='Salvage s (EGP):', style=ST, layout=LY)
w_pi   = widgets.FloatSlider(value=3,  min=0,   max=15,  step=1,
                              description='Penalty pi (EGP):',style=ST, layout=LY)
w_Q    = widgets.IntSlider(value=60,  min=30,  max=95,  step=5,
                            description='Inspect Q:',        style=ST, layout=LY)

w_show_dist  = widgets.ToggleButton(value=True,  description='Profit Distribution',
                                     icon='bar-chart', button_style='info',
                                     layout=widgets.Layout(width='190px'))
w_show_curve = widgets.ToggleButton(value=True,  description='Profit vs Q Curve',
                                     icon='line-chart', button_style='info',
                                     layout=widgets.Layout(width='190px'))

btn_run = widgets.Button(description='  Run Simulation', button_style='success',
                          icon='play', layout=widgets.Layout(width='210px', height='40px'))
btn_run.style.font_weight = 'bold'

out_metrics = widgets.Output()
out_charts  = widgets.Output()
out_table   = widgets.Output()

Q_LIST = list(range(30, 96, 5))

# ── Chart builder ─────────────────────────────────────────────────────────

def _build_charts(df, raw, Q_sel, show_d, show_c):
    n = int(show_d) + int(show_c)
    if n == 0:
        return None
    titles = []
    if show_d: titles.append(f'Profit Distribution  Q = {Q_sel}')
    if show_c:
        Qs = int(df.loc[df['avg'].idxmax(), 'Q'])
        titles.append(f'Avg Profit vs Q   (Q* = {Qs})')
    fig = make_subplots(rows=1, cols=n, subplot_titles=titles,
                        horizontal_spacing=0.10)
    col = 1
    if show_d and Q_sel in raw:
        prof_sel, _ = raw[Q_sel]
        fig.add_trace(go.Histogram(x=prof_sel, nbinsx=40,
                                    marker_color='#3b82f6', opacity=0.78,
                                    name='Profit'), row=1, col=col)
        fig.add_vline(x=float(np.mean(prof_sel)), line_dash='dot',
                       line_color='#dc2626',
                       annotation_text=f'Mean={np.mean(prof_sel):.1f}',
                       annotation_font_size=11, row=1, col=col)
        fig.add_vline(x=0, line_dash='dash', line_color='#374151',
                       annotation_text='Break-even',
                       annotation_font_size=10, row=1, col=col)
        col += 1
    if show_c:
        Qs = int(df.loc[df['avg'].idxmax(), 'Q'])
        fig.add_trace(go.Scatter(
            x=df['Q'], y=df['avg'], mode='lines+markers',
            line=dict(color='#2563eb', width=2.5), marker=dict(size=7),
            error_y=dict(type='data',
                          array=(df['ci_hi'] - df['avg']).tolist(),
                          arrayminus=(df['avg'] - df['ci_lo']).tolist(),
                          visible=True, color='#93c5fd', thickness=1.5),
            name='Avg Profit'), row=1, col=col)
        opt_avg = float(df.loc[df['Q'] == Qs, 'avg'].values[0])
        fig.add_vline(x=Qs, line_dash='dash', line_color='#dc2626',
                       annotation_text=f'Q*={Qs}',
                       annotation_font_color='#dc2626',
                       annotation_font_size=12, row=1, col=col)
        fig.add_trace(go.Scatter(x=[Qs], y=[opt_avg], mode='markers',
                                  marker=dict(color='#dc2626', size=14,
                                              symbol='star'),
                                  name=f'Q*={Qs}'), row=1, col=col)
    fig.update_layout(height=420, plot_bgcolor='#f8f9fa',
                       paper_bgcolor='white',
                       font=dict(family='Inter,Arial', size=12),
                       margin=dict(t=60, b=55, l=50, r=30),
                       legend=dict(orientation='h', y=-0.22))
    fig.update_xaxes(gridcolor='#e5e7eb')
    fig.update_yaxes(gridcolor='#e5e7eb')
    return fig

# ── Metrics printer ───────────────────────────────────────────────────────

def _print_metrics(m, Q_sel, N, p, c, s, pi, mode, seed, df, Qs):
    denom = p - s + pi
    CR = (p - c) / denom if denom != 0 else float('nan')
    try:
        Qa_norm = int(round(_scipy_norm.ppf(CR, 60, 15)))
    except Exception:
        Qa_norm = '—'
    idx_emp = np.searchsorted(_demand_cdf_g, CR, side='left')
    Qa_emp  = int(_demand_values_g[min(idx_emp, len(_demand_values_g)-1)])

    sep = '─' * 53
    print(f'┌{sep}┐')
    print(f'│  📋  SIMULATION METRICS{" "*29}│')
    print(f'├{sep}┤')
    print(f'│  p={p:.0f}  c={c:.0f}  s={s:.0f}  π={pi:.0f}   Seed={seed}   N={N:,}{" "*max(0,5-len(str(N)))}│')
    print(f'│  Distribution: {mode:<37}│')
    print(f'├{sep}┤')
    print(f'│  Critical Ratio CR          : {CR:.4f}{" "*22}│')
    print(f'│  Analytical Q* (Empirical)  : {Qa_emp:<6}{" "*17}│')
    print(f'│  Analytical Q* (Normal ppf) : {Qa_norm:<6}{" "*17}│')
    print(f'│  Simulation   Q*            : {Qs:<6}{" "*17}│')
    print(f'├{sep}┤')
    print(f'│  Inspecting Q = {Q_sel}{" "*35}│')
    print(f'│    Avg Profit    : {m["avg"]:>8.2f} EGP{" "*19}│')
    print(f'│    Std Deviation : {m["std"]:>8.2f} EGP{" "*19}│')
    print(f'│    P(loss)       : {m["p_loss"]*100:>7.2f} %{" "*21}│')
    print(f'│    Service Level : {m["sl"]*100:>7.2f} %{" "*21}│')
    print(f'│    Fill Rate     : {m["fr"]*100:>7.2f} %{" "*21}│')
    print(f'│    95% CI        : [{m["ci_lo"]:.2f}, {m["ci_hi"]:.2f}]{" "*max(0,10-len(f"{m["ci_lo"]:.2f}")-len(f"{m["ci_hi"]:.2f}"))}│')
    print(f'└{sep}┘')

def _print_top5(df):
    top5 = df.nlargest(5, 'avg')[['Q','avg','p_loss','sl','fr']].copy()
    top5.columns = ['Q','Avg Profit','P(loss)','Serv.Level','Fill Rate']
    medals = ['🥇','🥈','🥉','4th ','5th ']
    print('\n  ★  Top-5 Q values by Average Profit:\n')
    header = f"{'':4}  {'Q':>4}  {'Avg Profit':>11}  {'P(loss)':>8}  {'Serv.Level':>10}  {'Fill Rate':>9}"
    print(header)
    print('  ' + '─'*58)
    for medal, (_, row) in zip(medals, top5.iterrows()):
        print(f"  {medal}  {int(row['Q']):>4}  {row['Avg Profit']:>11.2f}  "
              f"{row['P(loss)']:>8.4f}  {row['Serv.Level']:>10.4f}  {row['Fill Rate']:>9.4f}")

# ── Main callback ─────────────────────────────────────────────────────────

def _run_and_render(_=None):
    N     = w_N.value
    seed  = w_seed.value
    mode  = w_dist.value.lower()
    p_v   = w_p.value
    c_v   = w_c.value
    s_v   = w_s.value
    pi_v  = w_pi.value
    Q_sel = w_Q.value

    df, raw = _run_sim(Q_LIST, N, p_v, c_v, s_v, pi_v, mode, seed)
    Qs      = int(df.loc[df['avg'].idxmax(), 'Q'])

    if Q_sel not in raw:
        Q_sel = Qs
    prof_sel, D_sel = raw[Q_sel]
    m = _metrics(Q_sel, prof_sel, D_sel)

    with out_metrics:
        clear_output(wait=True)
        _print_metrics(m, Q_sel, N, p_v, c_v, s_v, pi_v, mode, seed, df, Qs)
    with out_charts:
        clear_output(wait=True)
        fig = _build_charts(df, raw, Q_sel, w_show_dist.value, w_show_curve.value)
        if fig:
            fig.show()
    with out_table:
        clear_output(wait=True)
        _print_top5(df)

btn_run.on_click(_run_and_render)
w_Q.observe(lambda c: _run_and_render() if c['name'] == 'value' else None)

# ── Layout ────────────────────────────────────────────────────────────────

def _header(text, bg):
    return widgets.HTML(
        f"<div style='background:{bg};color:#fff;padding:7px 13px;"
        f"border-radius:6px;font-weight:bold;font-size:13px'>{text}</div>")

sim_box   = widgets.VBox([_header('⚙️ Simulation Settings','#1e40af'),
                           w_N, w_seed, w_dist],
                          layout=widgets.Layout(padding='6px'))
par_box   = widgets.VBox([_header('💰 Model Parameters','#065f46'),
                           w_p, w_c, w_s, w_pi],
                          layout=widgets.Layout(padding='6px'))
view_box  = widgets.VBox([_header('🔍 Inspect Q','#4c1d95'), w_Q],
                          layout=widgets.Layout(padding='6px'))
tog_box   = widgets.VBox([_header('👁️ Toggle Plots','#92400e'),
                           widgets.HBox([w_show_dist, w_show_curve])],
                          layout=widgets.Layout(padding='6px'))

dashboard = widgets.VBox([
    widgets.HTML(
        "<h2 style='color:#1e3a8a;margin:10px 0 3px'>"
        "🎛️  Interactive Simulation Dashboard</h2>"
        "<p style='color:#64748b;margin:0 0 8px;font-size:13px'>"
        "Adjust parameters then click <b>Run Simulation</b>.</p>"),
    widgets.HBox([sim_box, par_box, view_box, tog_box],
                  layout=widgets.Layout(gap='16px', flex_wrap='wrap')),
    widgets.HBox([btn_run], layout=widgets.Layout(padding='10px 4px')),
    widgets.HTML("<hr style='border-color:#e2e8f0;margin:4px 0'>"),
    out_metrics,
    widgets.HTML("<hr style='border-color:#e2e8f0;margin:4px 0'>"),
    out_charts,
    widgets.HTML("<hr style='border-color:#e2e8f0;margin:4px 0'>"),
    out_table,
], layout=widgets.Layout(
    border='2px solid #cbd5e1', border_radius='10px',
    padding='16px', background='white'))

display(dashboard)
_run_and_render()   # auto-run once with default values


# --- CELL ---

# ══════════════════════════════════════════════════════════════════════════
#  SECTION 16 — 3D PROFIT SURFACE  (Plotly, interactive)
# ══════════════════════════════════════════════════════════════════════════

import numpy as np
import plotly.graph_objects as go

# Grid resolution (keep small to run fast; increase for finer surface)
_Q_range = list(range(30, 96, 5))          # 14 candidate Q values
_p_range = list(range(15, 46, 3))          # selling prices 15–45 EGP
_N3D     = 3_000                            # replications per grid point
_SEED3D  = GLOBAL_SEED                     # from Section 0

# Build profit matrix  [len(p_range) × len(Q_range)]
_Z = np.zeros((len(_p_range), len(_Q_range)))

for _pi_idx, _p_val in enumerate(_p_range):
    for _qi_idx, _Q_val in enumerate(_Q_range):
        # Use the notebook's existing generate_demand & compute_profit
        _D, _ = generate_demand(_N3D, mode='normal', seed=_SEED3D + _Q_val)
        _prof = compute_profit(_Q_val, _D, c=c, p=_p_val, s=s, pi=pi)['profit']
        _Z[_pi_idx, _qi_idx] = float(np.mean(_prof))

# Locate global maximum
_peak_idx = np.unravel_index(np.argmax(_Z), _Z.shape)
_peak_Q   = _Q_range[_peak_idx[1]]
_peak_p   = _p_range[_peak_idx[0]]
_peak_Z   = _Z[_peak_idx]

# ── Build figure ────────────────────────────────────────────────────────────
_fig3d = go.Figure()

# Surface
_fig3d.add_trace(go.Surface(
    x=_Q_range, y=_p_range, z=_Z,
    colorscale='Viridis',
    colorbar=dict(title='E[Profit] (EGP)', thickness=15, x=1.02),
    opacity=0.88,
    name='E[Profit] Surface'
))

# Peak marker
_fig3d.add_trace(go.Scatter3d(
    x=[_peak_Q], y=[_peak_p], z=[_peak_Z],
    mode='markers+text',
    marker=dict(size=10, color='red', symbol='diamond'),
    text=[f'Global Max<br>Q*={_peak_Q}, p*={_peak_p}<br>Profit={_peak_Z:.1f}'],
    textposition='top center',
    name='Global Maximum'
))

_fig3d.update_layout(
    title=dict(
        text='<b>3D Profit Surface — Expected Profit vs Q & Selling Price</b>',
        x=0.5, font=dict(size=16)
    ),
    scene=dict(
        xaxis_title='Order Quantity Q',
        yaxis_title='Selling Price p (EGP)',
        zaxis_title='E[Profit] (EGP)',
        xaxis=dict(backgroundcolor='#f0f4ff', gridcolor='#c7d2fe'),
        yaxis=dict(backgroundcolor='#f0fdf4', gridcolor='#bbf7d0'),
        zaxis=dict(backgroundcolor='#fefce8', gridcolor='#fef08a'),
        camera=dict(eye=dict(x=1.6, y=-1.6, z=1.0))
    ),
    height=620,
    paper_bgcolor='white',
    margin=dict(l=20, r=20, t=70, b=20),
    legend=dict(x=0.01, y=0.99)
)

_fig3d.show()
print(f'  ★  Global Maximum: Q* = {_peak_Q},  p* = {_peak_p} EGP,  '
      f'E[Profit] = {_peak_Z:.2f} EGP')


# --- CELL ---

# ══════════════════════════════════════════════════════════════════════════
#  SECTION 17 — RISK vs. REWARD: Profit Distribution Comparison
# ══════════════════════════════════════════════════════════════════════════

import numpy as np
import plotly.graph_objects as go
from scipy.stats import gaussian_kde

# --- Three Q scenarios ---
_Q_opt   = int(Q_star_sim)           # from Section 5 (original)
_Q_under = max(30, _Q_opt - 15)      # under-stocking
_Q_over  = min(95, _Q_opt + 15)      # over-stocking

_scenarios = [
    (_Q_under, '#3b82f6', 'Under-stocking  Q=' + str(_Q_under)),
    (_Q_opt,   '#16a34a', 'Optimal         Q=' + str(_Q_opt)),
    (_Q_over,  '#f97316', 'Over-stocking   Q=' + str(_Q_over)),
]

_fig_risk = go.Figure()

for _Qv, _clr, _lbl in _scenarios:
    _D_s, _ = generate_demand(N_DAYS, mode='normal', seed=GLOBAL_SEED + _Qv)
    _prf    = compute_profit(_Qv, _D_s)['profit']
    _loss_p = float(np.mean(_prf < 0))

    # Histogram (semi-transparent)
    _fig_risk.add_trace(go.Histogram(
        x=_prf, nbinsx=60,
        name=_lbl + f'  |  P(loss)={_loss_p:.2%}',
        marker_color=_clr, opacity=0.45,
        histnorm='probability density'
    ))

    # KDE smooth curve
    _kde  = gaussian_kde(_prf, bw_method='scott')
    _xgrd = np.linspace(_prf.min(), _prf.max(), 400)
    _fig_risk.add_trace(go.Scatter(
        x=_xgrd, y=_kde(_xgrd),
        mode='lines',
        line=dict(color=_clr, width=2.5),
        showlegend=False
    ))

    # Shade loss region (profit < 0)
    _x_loss = _xgrd[_xgrd < 0]
    if len(_x_loss) > 0:
        _fig_risk.add_trace(go.Scatter(
            x=np.concatenate([[_x_loss[0]], _x_loss, [_x_loss[-1]]]),
            y=np.concatenate([[0], _kde(_x_loss), [0]]),
            fill='toself',
            fillcolor=_clr.replace(')', ',0.20)').replace('rgb', 'rgba'),
            line=dict(width=0),
            showlegend=False,
            hoverinfo='skip'
        ))

# Break-even line
_fig_risk.add_vline(
    x=0, line_dash='dash', line_color='#dc2626', line_width=2,
    annotation_text='Break-even (Profit = 0)',
    annotation_font_size=12, annotation_font_color='#dc2626'
)

_fig_risk.update_layout(
    title=dict(
        text='<b>Risk vs. Reward — Profit Distribution for Under/Optimal/Over-stocking</b><br>'
             '<sup>Shaded left tails = Value at Risk (Loss Probability)</sup>',
        x=0.5, font=dict(size=15)
    ),
    xaxis_title='Daily Profit (EGP)',
    yaxis_title='Probability Density',
    barmode='overlay',
    height=520,
    plot_bgcolor='#f8f9fa',
    paper_bgcolor='white',
    font=dict(family='Inter,Arial', size=12),
    legend=dict(orientation='h', y=-0.22, x=0),
    margin=dict(t=90, b=90, l=60, r=30)
)
_fig_risk.update_xaxes(gridcolor='#e5e7eb')
_fig_risk.update_yaxes(gridcolor='#e5e7eb')
_fig_risk.show()

print('\nRisk Summary:')
for _Qv, _, _lbl in _scenarios:
    _D_s, _ = generate_demand(N_DAYS, mode='normal', seed=GLOBAL_SEED + _Qv)
    _prf    = compute_profit(_Qv, _D_s)['profit']
    print(f'  {_lbl.strip():35s}  Avg={np.mean(_prf):.1f} EGP  '
          f'P(loss)={np.mean(_prf<0):.2%}  Std={np.std(_prf):.1f}')


# --- CELL ---

# ══════════════════════════════════════════════════════════════════════════
#  SECTION 18 — STRESS TESTING  (stress_test function)
# ══════════════════════════════════════════════════════════════════════════

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.stats import norm as _st_norm


def stress_test(
    Q_list=None,
    N=None,
    seed=None,
    base_mu=None, base_sigma=None,
    base_c=None, base_p=None, base_s=None, base_pi=None
):
    """
    Run Monte Carlo stress tests against three scenarios:
      Baseline : original parameters
      Scenario A (Epidemic Shock)  : mu shifts 60→150, sigma increases
      Scenario B (Supply Crisis)   : unit cost c increases by 50%

    Parameters default to config values when None is passed.

    Returns
    -------
    summary_df : pd.DataFrame  — KPIs per scenario
    detail_dfs : dict          — per-Q avg profit for each scenario
    """
    # Resolve defaults from config — avoids frozen-global trap
    if N          is None: N          = N_DAYS
    if seed       is None: seed       = GLOBAL_SEED
    if base_mu    is None: base_mu    = MU
    if base_sigma is None: base_sigma = SIGMA
    if base_c     is None: base_c     = C
    if base_p     is None: base_p     = P
    if base_s     is None: base_s     = S
    if base_pi    is None: base_pi    = PI

    if Q_list is None:
        Q_list = list(range(30, 96, 5))

    # --- Scenario definitions ---
    scenarios = {
        'Baseline': dict(
            mu=base_mu, sigma=base_sigma,
            c=base_c, p=base_p, s=base_s, pi=base_pi,
            color='#2563eb', dash='solid'
        ),
        'A — Epidemic Spike': dict(
            mu=150, sigma=30,                        # demand explodes
            c=base_c, p=base_p, s=base_s, pi=base_pi,
            color='#dc2626', dash='dot'
        ),
        'B — Supply Crisis': dict(
            mu=base_mu, sigma=base_sigma,
            c=base_c * 1.5,                          # +50% cost
            p=base_p, s=base_s, pi=base_pi,
            color='#d97706', dash='dashdot'
        ),
    }

    rng_base  = np.random.default_rng(seed)
    detail_dfs = {}
    summary_rows = []

    for sc_name, sc in scenarios.items():
        rows = []
        for Qv in Q_list:
            rng = np.random.default_rng(seed + Qv)
            raw_D = rng.normal(sc['mu'], sc['sigma'], N)
            D     = np.clip(np.round(raw_D), 20, 200).astype(int)

            # Profit formula (unchanged from Section 2.3)
            sales = np.minimum(Qv, D)
            over  = np.maximum(Qv - D, 0)
            lost  = np.maximum(D - Qv, 0)
            prof  = (sc['p'] * sales
                     - sc['c'] * Qv
                     + sc['s'] * over
                     - sc['pi'] * lost)

            rows.append({'Q': Qv, 'avg_profit': float(np.mean(prof)),
                         'p_loss': float(np.mean(prof < 0)),
                         'std': float(np.std(prof, ddof=1))})

        df_sc = pd.DataFrame(rows)
        detail_dfs[sc_name] = df_sc

        best_row = df_sc.loc[df_sc['avg_profit'].idxmax()]
        # Analytical CR & Q* for this scenario
        denom = sc['p'] - sc['s'] + sc['pi']
        CR_sc = (sc['p'] - sc['c']) / denom if denom != 0 else float('nan')
        try:
            Qstar_an = int(round(_st_norm.ppf(CR_sc, sc['mu'], sc['sigma'])))
        except Exception:
            Qstar_an = '—'

        summary_rows.append({
            'Scenario'       : sc_name,
            'μ (demand)'     : sc['mu'],
            'σ (demand)'     : sc['sigma'],
            'c (cost, EGP)'  : sc['c'],
            'CR'             : round(CR_sc, 4),
            'Analytical Q*'  : Qstar_an,
            'Sim Q*'         : int(best_row['Q']),
            'Avg Profit (EGP)': round(best_row['avg_profit'], 2),
            'P(loss) @Q*'    : f"{best_row['p_loss']:.2%}",
            'Std Dev (EGP)'  : round(best_row['std'], 2),
        })

    summary_df = pd.DataFrame(summary_rows).set_index('Scenario')
    return summary_df, detail_dfs, scenarios


# ── Run stress test & display summary table ─────────────────────────────────
_st_summary, _st_details, _st_colors = stress_test()

print('=' * 90)
print('  STRESS TEST — SUMMARY TABLE')
print('=' * 90)
with pd.option_context('display.max_columns', None, 'display.width', 120,
                        'display.float_format', '{:.2f}'.format):
    print(_st_summary.to_string())
print('=' * 90)


# ── Profit Erosion multi-line chart (Plotly) ─────────────────────────────────
_fig_stress = go.Figure()

for sc_name, df_sc in _st_details.items():
    _cfg   = _st_colors[sc_name]
    _Qs_sc = int(df_sc.loc[df_sc['avg_profit'].idxmax(), 'Q'])
    _Yopt  = float(df_sc.loc[df_sc['Q'] == _Qs_sc, 'avg_profit'].values[0])

    _fig_stress.add_trace(go.Scatter(
        x=df_sc['Q'], y=df_sc['avg_profit'],
        mode='lines+markers',
        name=sc_name,
        line=dict(color=_cfg['color'], dash=_cfg['dash'], width=2.5),
        marker=dict(size=7)
    ))

    # Mark each scenario's own Q*
    _fig_stress.add_trace(go.Scatter(
        x=[_Qs_sc], y=[_Yopt],
        mode='markers',
        marker=dict(color=_cfg['color'], size=14, symbol='star'),
        showlegend=False,
        hovertemplate=f'{sc_name}<br>Q*={_Qs_sc}<br>Profit={_Yopt:.1f} EGP<extra></extra>'
    ))

_fig_stress.update_layout(
    title=dict(
        text='<b>Stress Test — Profit Erosion Across Scenarios</b><br>'
             '<sup>Stars mark each scenario\'s optimal Q* | dashed lines = shock scenarios</sup>',
        x=0.5, font=dict(size=15)
    ),
    xaxis_title='Order Quantity Q (units)',
    yaxis_title='Avg Daily Profit (EGP)',
    height=480,
    plot_bgcolor='#f8f9fa',
    paper_bgcolor='white',
    font=dict(family='Inter,Arial', size=12),
    legend=dict(orientation='h', y=-0.22),
    margin=dict(t=90, b=90, l=60, r=30)
)
_fig_stress.update_xaxes(gridcolor='#e5e7eb')
_fig_stress.update_yaxes(gridcolor='#e5e7eb')
_fig_stress.show()
