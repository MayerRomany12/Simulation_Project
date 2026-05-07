import os

file_path = "backend/main.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

missing_code = """class SuggestRRequest(BaseModel):
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
        s.pop('_profit_series', None)
        results[name] = clean_dict(s)
        
    return results

class InsightsRequest(BaseModel):
    kpis: dict
    params: dict
    stress_results: dict = None

"""

content = content.replace('@app.post("/generate-insights")', missing_code + '@app.post("/generate-insights")')

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Restored missing code in backend/main.py")
