import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import warnings
warnings.filterwarnings('ignore')

# ── Plotly for the interactive dashboard ──────────────────────────────────
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False
    print("Plotly not installed — dashboard will use matplotlib fallback.")

# ── Reproducibility ───────────────────────────────────────────────────────
GLOBAL_SEED = 42
np.random.seed(GLOBAL_SEED)

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

# ══════════════════════════════════════════════════════════════════════════
## 11. Interactive Dashboard (Plotly)

# Use the sliders below to explore how the profit curve and distribution change
# when you modify the model parameters **without re-running the simulation**.

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

# ══════════════════════════════════════════════════════════════════════════
## 15. 🎛️ Advanced Interactive Dashboard

# This section layers a **fully interactive dashboard** on top of all previous results.

# **Features at a glance:**
# | Feature | Detail |
# |---------|--------|
# | N days slider | 100 – 20,000 replications |
# | Parameter sliders | p, c, s, π |
# | Distribution dropdown | Normal · Empirical |
# | Seed control | Any integer 0 – 999 |
# | Inspect Q slider | Single-Q profit distribution |
# | Run button | Re-runs Monte Carlo on demand |
# | Toggle buttons | Show / hide individual plots |
# | Live Plotly charts | Profit histogram + Profit-vs-Q with Q* star |
# | Metrics panel | CR, analytical Q*, simulation Q*, all KPIs |
# | Top-5 table | Best Q values ranked by average profit |

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

# ── Demand & profit helpers (extended signatures, local scope) ─────────────

_demand_values_g = np.array([30, 40, 50, 60, 70, 80, 90])
_demand_probs_g  = np.array([0.05, 0.10, 0.20, 0.30, 0.20, 0.10, 0.05])
_demand_cdf_g    = np.cumsum(_demand_probs_g)

def _gen_demand(n, mode='normal', seed=42):
    """Generate n demand values. mode: 'normal' or 'empirical'."""
    rng = np.random.default_rng(seed)
    if mode == 'normal':
        D = np.clip(np.round(rng.normal(60, 15, n)), 20, 100).astype(int)
    else:
        U   = rng.uniform(0, 1, n)
        idx = np.clip(np.searchsorted(_demand_cdf_g, U, side='right'),
                      0, len(_demand_values_g) - 1)
        D   = _demand_values_g[idx]
    return D

def _calc_profit(Q, D, p, c, s, pi):
    """Vectorised: Sales=min(Q,D), OS=max(Q-D,0), LS=max(D-Q,0)."""
    sales = np.minimum(Q, D)
    os    = np.maximum(Q - D, 0)
    ls    = np.maximum(D - Q, 0)
    return p * sales - c * Q + s * os - pi * ls

def _metrics(Q, prof, D):
    """All KPIs from profit and demand arrays."""
    N   = len(prof)
    avg = np.mean(prof)
    std = np.std(prof, ddof=1)
    return dict(
        avg    = avg,
        std    = std,
        p_loss = np.mean(prof < 0),
        sl     = np.mean(D <= Q),
        fr     = 1 - np.mean(np.maximum(D - Q, 0)) / np.mean(D),
        ci_lo  = avg - 1.96 * std / np.sqrt(N),
        ci_hi  = avg + 1.96 * std / np.sqrt(N),
    )

def _run_sim(Q_list, N, p, c, s, pi, mode, seed):
    """Full Monte Carlo for every Q in Q_list."""
    rows, raw = [], {}
    for Q in Q_list:
        D    = _gen_demand(N, mode, seed + Q)
        prof = _calc_profit(Q, D, p, c, s, pi)
        m    = _metrics(Q, prof, D)
        rows.append({'Q': Q, **m})
        raw[Q] = (prof, D)
    return pd.DataFrame(rows), raw

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

# ══════════════════════════════════════════════════════════════════════════
#  SECTION 18 — STRESS TESTING  (stress_test function)
# ══════════════════════════════════════════════════════════════════════════

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.stats import norm as _st_norm


def stress_test(
    Q_list=None,
    N=N_DAYS,
    seed=GLOBAL_SEED,
    base_mu=mu, base_sigma=sigma,
    base_c=c, base_p=p, base_s=s, base_pi=pi
):
    """
    Run Monte Carlo stress tests against three scenarios:
      Baseline : original parameters
      Scenario A (Epidemic Shock)  : mu shifts 60→150, sigma increases
      Scenario B (Supply Crisis)   : unit cost c increases by 50%

    Returns
    -------
    summary_df : pd.DataFrame  — KPIs per scenario
    detail_dfs : dict          — per-Q avg profit for each scenario
    """
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
