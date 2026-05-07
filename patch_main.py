import os
import re

file_path = "backend/main.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

helper_code = """
def get_averaged_simulation(params, q_a, q_b, r_a, r_b, n_days, warmup_days, base_seed, iterations=5):
    ss = np.random.SeedSequence(base_seed)
    child_seeds = ss.spawn(iterations * 2)
    
    all_kpis = []
    last_df = None
    idx = 0
    
    for i in range(iterations):
        rng_a = np.random.default_rng(child_seeds[idx])
        rng_b = np.random.default_rng(child_seeds[idx+1])
        idx += 2
        
        df = run_multi_period_simulation(
            params, q_a, q_b, r_a, r_b,
            n_days=n_days, warmup_days=warmup_days, rng_a=rng_a, rng_b=rng_b
        )
        all_kpis.append(summarise(df))
        last_df = df
        
    avg_kpis = {}
    if all_kpis:
        for k in all_kpis[0].keys():
            vals = [kpi[k] for kpi in all_kpis if isinstance(kpi[k], (int, float))]
            if vals:
                avg_kpis[k] = sum(vals) / len(vals)
                
    return avg_kpis, last_df

@app.post("/run-simulation")
"""

content = re.sub(r'@app\.post\("/run-simulation"\)\n', helper_code, content, 1)

run_sim_code = """@app.post("/run-simulation")
def api_run_simulation(req: SimulationParams):
    params = get_base_params(req)
    
    avg_kpis, last_df = get_averaged_simulation(
        params, req.Q_a, req.Q_b, req.R_a, req.R_b,
        n_days=req.n_days, warmup_days=req.warmup_days, base_seed=req.seed, iterations=5
    )
    
    # Add Financial KPIs in EGP
    margin = params['p'] - params['c']
    avg_kpis['lost_sales_cost'] = (avg_kpis.get('avg_lost_a', 0) + avg_kpis.get('avg_lost_b', 0)) * margin
    avg_kpis['waste_cost'] = (avg_kpis.get('avg_expired_a', 0) + avg_kpis.get('avg_expired_b', 0)) * params['c']
    
    insights = generate_insights(avg_kpis, params)
    
    # Replace NaN/Infinity
    last_df = last_df.replace([np.inf, -np.inf, np.nan], None)
    
    return {
        "kpis": clean_dict(avg_kpis),
        "timeline": last_df.to_dict(orient='records'),
        "insights": insights
    }"""

old_run_sim = r'@app\.post\("/run-simulation"\)\ndef api_run_simulation[\s\S]*?(?=@app\.post\("/generate-insights"\))'
content = re.sub(old_run_sim, run_sim_code + "\n\n", content)

old_profit_q = r'@app\.post\("/profit-vs-q"\)\ndef api_profit_vs_q[\s\S]*?(?=@app\.post\("/sensitivity-rq"\))'
new_profit_q = """@app.post("/profit-vs-q")
def api_profit_vs_q(req: SimulationParams):
    params = get_base_params(req)
    q_vals = list(range(20, 305, 5))
    results = []
    
    for q_val in q_vals:
        avg_kpis, _ = get_averaged_simulation(
            params, q_val, req.Q_b, req.R_a, req.R_b,
            n_days=req.n_days, warmup_days=req.warmup_days, base_seed=req.seed + q_val, iterations=5
        )
        results.append({
            "Q": q_val,
            "sim_profit": clean_dict(avg_kpis).get("avg_profit", 0)
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

"""
content = re.sub(old_profit_q, new_profit_q, content)

old_sens = r'@app\.post\("/sensitivity-rq"\)\ndef api_sensitivity_rq[\s\S]*?(?=if __name__ == "__main__":)'
new_sens = """@app.post("/sensitivity-rq")
def api_sensitivity_rq(req: SimulationParams):
    params = get_base_params(req)
    
    step = 5
    r_start = max(0, req.R_a - 7 * step)
    q_start = max(0, req.Q_a - 7 * step)
    r_range = list(range(r_start, r_start + 15 * step, step))
    q_range = list(range(q_start, q_start + 15 * step, step))
    
    results = []
    max_profit = -float('inf')
    optimal_r = None
    optimal_q = None
    
    for r in r_range:
        for q in q_range:
            avg_kpis, _ = get_averaged_simulation(
                params, q, req.Q_b, r, req.R_b,
                n_days=req.n_days, warmup_days=req.warmup_days, base_seed=req.seed + r * 1000 + q, iterations=5
            )
            profit = clean_dict(avg_kpis).get("avg_profit", 0)
            
            if profit > max_profit:
                max_profit = profit
                optimal_r = r
                optimal_q = q
            
            results.append({
                "R": r,
                "Q": q,
                "profit": profit
            })
            
    for res in results:
        res["is_optimal"] = (res["R"] == optimal_r and res["Q"] == optimal_q)
        
    return {
        "optimal_rq": {"r": optimal_r, "q": optimal_q, "profit": max_profit},
        "data": results
    }

"""
content = re.sub(old_sens, new_sens, content)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated backend/main.py")
