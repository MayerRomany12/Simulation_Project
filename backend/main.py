import sys
import os
import math
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import numpy as np
import pandas as pd

from config import BASE_PARAMS, GLOBAL_SEED, Q_A, Q_B, R_A, R_B, SIM_DAYS, WARMUP_DAYS, Q_VALUES, N_DAYS
from simulation import (
    run_multi_period_simulation,
    summarise,
    run_stress_test,
    run_baseline_newsvendor_sim,
    compute_reorder_point
)

app = FastAPI(title="Pharmacy Simulation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimulationParams(BaseModel):
    # Demands
    mu_a: float = Field(default=BASE_PARAMS['mu_a'])
    sigma_a: float = Field(default=BASE_PARAMS['sigma_a'])
    mu_b: float = Field(default=BASE_PARAMS['mu_b'])
    sigma_b: float = Field(default=BASE_PARAMS['sigma_b'])
    clip_low: int = Field(default=BASE_PARAMS['clip_low'])
    clip_high: int = Field(default=BASE_PARAMS['clip_high'])
    weekend_mult: float = Field(default=BASE_PARAMS['weekend_mult'])
    # Economics
    p: float = Field(default=BASE_PARAMS['p'])
    c: float = Field(default=BASE_PARAMS['c'])
    s: float = Field(default=BASE_PARAMS['s'])
    pi: float = Field(default=BASE_PARAMS['pi'])
    disposal_cost: float = Field(default=BASE_PARAMS['disposal_cost'])
    holding_cost: float = Field(default=BASE_PARAMS['holding_cost'])
    # Inventory Policies
    lead_time: int = Field(default=BASE_PARAMS['lead_time'])
    expiry_k: int = Field(default=BASE_PARAMS['expiry_k'])
    sub_rate: float = Field(default=BASE_PARAMS['sub_rate'])
    
    Q_a: int = Field(default=Q_A)
    Q_b: int = Field(default=Q_B)
    R_a: int = Field(default=R_A)
    R_b: int = Field(default=R_B)
    
    n_days: int = Field(default=SIM_DAYS)
    warmup_days: int = Field(default=WARMUP_DAYS)
    seed: int = Field(default=GLOBAL_SEED)

def get_base_params(req: SimulationParams):
    return {
        'mu_a': req.mu_a, 'sigma_a': req.sigma_a,
        'mu_b': req.mu_b, 'sigma_b': req.sigma_b,
        'clip_low': req.clip_low, 'clip_high': req.clip_high,
        'weekend_mult': req.weekend_mult,
        'p': req.p, 'c': req.c, 's': req.s, 'pi': req.pi,
        'disposal_cost': req.disposal_cost, 'holding_cost': req.holding_cost,
        'lead_time': req.lead_time, 'expiry_k': req.expiry_k, 'sub_rate': req.sub_rate
    }

def clean_dict(d):
    """Convert numpy types to native Python types for JSON serialization."""
    clean = {}
    for k, v in d.items():
        if isinstance(v, (np.integer, np.int64, np.int32)):
            clean[k] = int(v)
        elif isinstance(v, (np.floating, np.float64, np.float32)):
            if math.isnan(v) or math.isinf(v):
                clean[k] = None
            else:
                clean[k] = float(v)
        elif isinstance(v, np.ndarray):
            clean[k] = v.tolist()
        else:
            clean[k] = v
    return clean

def generate_insights(kpis, params, stress_results=None):
    insights = []
    
    p = params.get('p', 0)
    c = params.get('c', 0)
    margin = p - c
    lead_time = params.get('lead_time', 0)
    
    avg_inv_total = kpis.get('avg_inv_a', 0) + kpis.get('avg_inv_b', 0)
    avg_lost_total = kpis.get('avg_lost_a', 0) + kpis.get('avg_lost_b', 0)
    
    # 1. Lead Time Insight
    # Capital tied up in transit approximation: Lead Time * Daily Demand * Cost
    daily_demand_a = params.get('mu_a', 0)
    daily_demand_b = params.get('mu_b', 0)
    capital_in_transit = lead_time * (daily_demand_a + daily_demand_b) * c
    if capital_in_transit > 0:
        insights.append(f"Supply Chain Insight: A Lead Time of {lead_time} days ties up approx. {capital_in_transit:.0f} EGP in transit inventory, potentially reducing ROI.")

    # 2. Safety Stock Alert
    sl_a = kpis.get('service_level_a', 0)
    sl_b = kpis.get('service_level_b', 0)
    if sl_a < 0.90 or sl_b < 0.90:
        insights.append(f"Safety Stock Alert: Current buffer is weak. The pharmacy loses an average of {avg_lost_total:.1f} customers daily due to stockouts. Consider raising the Reorder Point.")

    # 3. CV (Coefficient of Variation) check
    cv = (kpis.get('std_profit', 0) / max(kpis.get('avg_profit', 1), 1)) * 100
    if cv > 50:
        insights.append(f"High Profit Volatility: CV is {cv:.1f}%. It is recommended to increase cash reserves to handle demand fluctuations.")
    else:
        insights.append(f"Financial Stability: Good stability (CV={cv:.1f}%). Daily profits are reasonably steady under the current inventory policy.")
        
    # 4. Cost Analysis (Lost Sales vs Waste)
    lost_sales_cost = avg_lost_total * margin
    avg_expired_total = kpis.get('avg_expired_a', 0) + kpis.get('avg_expired_b', 0)
    waste_cost = avg_expired_total * c
    
    if lost_sales_cost > waste_cost * 2:
         insights.append(f"Opportunity Cost Warning: Lost sales cost ({lost_sales_cost:.0f} EGP) is significantly higher than waste cost ({waste_cost:.0f} EGP). Increasing Order Quantity (Q) is highly recommended.")
    elif waste_cost > lost_sales_cost * 2:
         insights.append(f"Waste Management Alert: Expiry waste cost ({waste_cost:.0f} EGP) is disproportionately high. Please review and decrease Order Quantity (Q) to minimize waste.")
         
    # 5. Stress Test check
    if stress_results and 'Epidemic' in stress_results:
        epi_sl = stress_results['Epidemic'].get('service_level_a', 0)
        if epi_sl < 0.80:
            insights.append(f"Critical Vulnerability: In an Epidemic scenario, service level drops to {epi_sl*100:.0f}%. An immediate upward adjustment of Reorder Point (R) is required for crisis readiness.")
            
    return insights

@app.post("/run-simulation")
def api_run_simulation(req: SimulationParams):
    params = get_base_params(req)
    ss = np.random.SeedSequence(req.seed)
    rng_a, rng_b = (np.random.default_rng(c) for c in ss.spawn(2))
    
    df = run_multi_period_simulation(
        params, req.Q_a, req.Q_b, req.R_a, req.R_b,
        n_days=req.n_days, warmup_days=req.warmup_days, rng_a=rng_a, rng_b=rng_b
    )
    
    kpis = summarise(df)
    
    # Add Financial KPIs in EGP
    margin = params['p'] - params['c']
    kpis['lost_sales_cost'] = (kpis.get('avg_lost_a', 0) + kpis.get('avg_lost_b', 0)) * margin
    kpis['waste_cost'] = (kpis.get('avg_expired_a', 0) + kpis.get('avg_expired_b', 0)) * params['c']
    
    insights = generate_insights(kpis, params)
    
    # Replace NaN/Infinity
    df = df.replace([np.inf, -np.inf, np.nan], None)
    
    return {
        "kpis": clean_dict(kpis),
        "timeline": df.to_dict(orient='records'),
        "insights": insights
    }

class SuggestRRequest(BaseModel):
    mu_daily: float
    sigma_daily: float
    lead_time: int
    service_level: float

@app.post("/suggest-r")
def api_suggest_r(req: SuggestRRequest):
    res = compute_reorder_point(req.mu_daily, req.sigma_daily, req.lead_time, req.service_level)
    return clean_dict(res)

@app.post("/stress-test")
def api_stress_test(req: SimulationParams):
    params = get_base_params(req)
    stress = run_stress_test(
        params, req.Q_a, req.Q_b, req.R_a, req.R_b,
        n_days=req.n_days, warmup_days=req.warmup_days,
        global_seed=req.seed + 99
    )
    
    results = {}
    for name, s in stress.items():
        s.pop('_profit_series', None)  # Remove raw series, not needed in JSON response typically
        results[name] = clean_dict(s)
        
    return results

class InsightsRequest(BaseModel):
    kpis: dict
    params: dict
    stress_results: dict = None

@app.post("/generate-insights")
def api_generate_insights(req: InsightsRequest):
    insights = generate_insights(req.kpis, req.params, req.stress_results)
    return {"insights": insights}

@app.post("/profit-vs-q")
def api_profit_vs_q(req: SimulationParams):
    params = get_base_params(req)
    
    # Use fixed expanded range to show full diminishing returns curve
    q_vals = list(range(20, 305, 5))
    
    results = []
    
    # Pre-spawn seeds for all iterations to ensure independent streams
    ss = np.random.SeedSequence(req.seed + 1)
    child_seeds = ss.spawn(len(q_vals) * 2)
    
    idx = 0
    for q_val in q_vals:
        rng_a = np.random.default_rng(child_seeds[idx])
        rng_b = np.random.default_rng(child_seeds[idx+1])
        idx += 2
        
        df = run_multi_period_simulation(
            params, q_val, req.Q_b, req.R_a, req.R_b,
            n_days=req.n_days, warmup_days=req.warmup_days, rng_a=rng_a, rng_b=rng_b
        )
        kpis = summarise(df)
        
        results.append({
            "Q": q_val,
            "sim_profit": clean_dict(kpis)["avg_profit"]
        })
        
    # Find optimal Q
    max_profit = -float('inf')
    optimal_q = None
    for res in results:
        if res["sim_profit"] > max_profit:
            max_profit = res["sim_profit"]
            optimal_q = res["Q"]
            
    for res in results:
        res["is_optimal"] = (res["Q"] == optimal_q)
        
    return {
        "optimal_q": optimal_q,
        "data": results
    }

@app.post("/sensitivity-rq")
def api_sensitivity_rq(req: SimulationParams):
    params = get_base_params(req)
    
    # Range: Q-20 to Q+20, step 5
    # For a 2D heatmap, we will vary R_a and Q_a around their given values.
    # We will keep B constant for the sake of standard 2D heatmap
    
    r_range = list(range(max(0, req.R_a - 20), req.R_a + 25, 5))
    q_range = list(range(max(0, req.Q_a - 20), req.Q_a + 25, 5))
    
    results = []
    
    ss = np.random.SeedSequence(req.seed + 77)
    child_seeds = ss.spawn(len(r_range) * len(q_range) * 2)
    
    idx = 0
    for r in r_range:
        for q in q_range:
            rng_a = np.random.default_rng(child_seeds[idx])
            rng_b = np.random.default_rng(child_seeds[idx+1])
            idx += 2
            
            df = run_multi_period_simulation(
                params, q, req.Q_b, r, req.R_b,
                n_days=req.n_days, warmup_days=req.warmup_days, rng_a=rng_a, rng_b=rng_b
            )
            kpis = summarise(df)
            
            results.append({
                "R": r,
                "Q": q,
                "profit": clean_dict(kpis)["avg_profit"]
            })
            
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
