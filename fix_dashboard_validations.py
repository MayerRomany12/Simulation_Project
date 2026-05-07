import os

file_path = "frontend/src/components/Dashboard.jsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update traceSpeed default
content = content.replace("const [traceSpeed, setTraceSpeed] = useState(50);", "const [traceSpeed, setTraceSpeed] = useState(80);")

# 2. Add errors state
old_validation_error = "const [validationError, setValidationError] = useState('');"
new_validation_error = """const [validationError, setValidationError] = useState('');
  const [errors, setErrors] = useState({});"""
content = content.replace(old_validation_error, new_validation_error)

# 3. Rewrite validateParams
old_validate_params = """  const validateParams = () => {
    const demandParams = ['mu_a', 'sigma_a', 'mu_b', 'sigma_b'];
    for (const p of demandParams) {
      if (params[p] < 5 || params[p] > 500) {
        return `Demand parameter ${p} must be between 5 and 500.`;
      }
    }
    if (params.sigma_a > params.mu_a) return "Product A: Std Dev (\u03c3) cannot exceed Mean (\u03bc).";
    if (params.sigma_b > params.mu_b) return "Product B: Std Dev (\u03c3) cannot exceed Mean (\u03bc).";
    for (const [key, value] of Object.entries(params)) {
      if (value === '' || value === null || isNaN(value)) return `Parameter ${key} is required.`;
    }
    return '';
  };"""

new_validate_params = """  const validateParams = () => {
    const newErrors = {};
    const checkDemand = (val, name) => {
      if (val < 5 || val > 500) newErrors[name] = "Must be between 5 and 500.";
    };
    checkDemand(params.mu_a, 'mu_a');
    checkDemand(params.sigma_a, 'sigma_a');
    
    if (params.sigma_a > params.mu_a) newErrors.sigma_a = "Cannot exceed Mean (\u03bc).";

    if (params.p < 5 || params.p > 10000) newErrors.p = "Must be between 5 and 10000.";
    if (params.c < 5 || params.c > 10000) newErrors.c = "Must be between 5 and 10000.";
    if (params.c >= params.p) newErrors.c = "Must be strictly less than Price.";

    if (params.lead_time < 1 || params.lead_time > 60) newErrors.lead_time = "Must be between 1 and 60.";
    if (params.expiry_k < 10 || params.expiry_k > 1200) newErrors.expiry_k = "Must be between 10 and 1200.";

    if (params.Q_a < 10 || params.Q_a > 10000) newErrors.Q_a = "Must be between 10 and 10000.";
    if (params.R_a < 10 || params.R_a > 10000) newErrors.R_a = "Must be between 10 and 10000.";

    if (serviceLevelTarget <= 0 || serviceLevelTarget >= 1) newErrors.serviceLevelTarget = "Must be strictly between 0 and 1.";

    for (const [key, value] of Object.entries(params)) {
      if (value === '' || value === null || isNaN(value)) {
        if (!newErrors[key]) newErrors[key] = "Required.";
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0 ? '' : 'Please fix the errors below.';
  };"""

content = content.replace(old_validate_params, new_validate_params)

# 4. Update sidebar css
content = content.replace('className="w-full lg:w-80 flex-shrink-0"', 'className="w-full lg:w-80 shrink-0"')
content = content.replace('className="space-y-4 max-h-[75vh] overflow-y-auto pr-2 custom-scrollbar"', 'className="space-y-4 max-h-[75vh] overflow-y-auto overflow-x-hidden pb-24 pr-2 custom-scrollbar"')

# 5. Inject inline errors
content = content.replace('className="glass-input w-full" />\n              </div>', 'className="glass-input w-full" />\n                {errors.n_days && <p className="text-red-400 text-xs mt-1">{errors.n_days}</p>}\n              </div>', 1)

content = content.replace('className="glass-input w-full" />\n              </div>', 'className="glass-input w-full" />\n                {errors.mu_a && <p className="text-red-400 text-xs mt-1">{errors.mu_a}</p>}\n              </div>', 1)
content = content.replace('className="glass-input w-full" />\n              </div>', 'className="glass-input w-full" />\n                {errors.sigma_a && <p className="text-red-400 text-xs mt-1">{errors.sigma_a}</p>}\n              </div>', 1)

content = content.replace('className="glass-input w-full" />\n              </div>', 'className="glass-input w-full" />\n                {errors.Q_a && <p className="text-red-400 text-xs mt-1">{errors.Q_a}</p>}\n              </div>', 1)
content = content.replace('className="glass-input w-full" />\n              </div>', 'className="glass-input w-full" />\n                {errors.R_a && <p className="text-red-400 text-xs mt-1">{errors.R_a}</p>}\n              </div>', 1)

content = content.replace('<span className="ml-2 text-xs text-white/50">Target SL</span>\n                  </div>\n                </div>', '<span className="ml-2 text-xs text-white/50">Target SL</span>\n                  </div>\n                  {errors.serviceLevelTarget && <p className="text-red-400 text-xs mt-1">{errors.serviceLevelTarget}</p>}\n                </div>')

content = content.replace('className="glass-input w-full" />\n              </div>', 'className="glass-input w-full" />\n                {errors.lead_time && <p className="text-red-400 text-xs mt-1">{errors.lead_time}</p>}\n              </div>', 1)
content = content.replace('className="glass-input w-full" />\n              </div>', 'className="glass-input w-full" />\n                {errors.expiry_k && <p className="text-red-400 text-xs mt-1">{errors.expiry_k}</p>}\n              </div>', 1)

content = content.replace('className="glass-input w-full" />\n              </div>', 'className="glass-input w-full" />\n                {errors.p && <p className="text-red-400 text-xs mt-1">{errors.p}</p>}\n              </div>', 1)
content = content.replace('className="glass-input w-full" />\n              </div>', 'className="glass-input w-full" />\n                {errors.c && <p className="text-red-400 text-xs mt-1">{errors.c}</p>}\n              </div>', 1)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched validations in Dashboard.jsx")
