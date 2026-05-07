import os

file_path = "backend/main.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

old_rq = """@app.post("/sensitivity-rq")
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
            
    return results"""

new_rq = """@app.post("/sensitivity-rq")
def api_sensitivity_rq(req: SimulationParams):
    params = get_base_params(req)
    
    # 15x15 dynamic range grid
    step = 5
    
    # Calculate ranges avoiding negatives, keeping 15 values
    r_start = max(0, req.R_a - 7 * step)
    q_start = max(0, req.Q_a - 7 * step)
    r_range = list(range(r_start, r_start + 15 * step, step))
    q_range = list(range(q_start, q_start + 15 * step, step))
    
    results = []
    
    ss = np.random.SeedSequence(req.seed + 77)
    child_seeds = ss.spawn(len(r_range) * len(q_range) * 2)
    
    idx = 0
    max_profit = -float('inf')
    optimal_r = None
    optimal_q = None
    
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
            profit = clean_dict(kpis)["avg_profit"]
            
            if profit > max_profit:
                max_profit = profit
                optimal_r = r
                optimal_q = q
            
            results.append({
                "R": r,
                "Q": q,
                "profit": profit
            })
            
    # Add optimal flag
    for res in results:
        res["is_optimal"] = (res["R"] == optimal_r and res["Q"] == optimal_q)
        
    return {
        "optimal_rq": {"r": optimal_r, "q": optimal_q, "profit": max_profit},
        "data": results
    }"""

if old_rq in content:
    content = content.replace(old_rq, new_rq)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Backend api_sensitivity_rq patched successfully.")
else:
    print("Could not find old api_sensitivity_rq in backend/main.py")"""
