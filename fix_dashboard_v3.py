import os

file_path = "frontend/src/components/Dashboard.jsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add Info to imports
content = content.replace("Settings } from 'lucide-react';", "Settings, Info } from 'lucide-react';")

# 2. Add TooltipLabel component
tooltip_comp = """
const TooltipLabel = ({ label, tooltip }) => (
  <div className="flex items-center gap-1 group relative mb-1">
    <label className="text-xs text-white/60 block">{label}</label>
    <Info size={12} className="text-white/40 cursor-help" />
    <div className="absolute left-0 bottom-full mb-2 w-48 p-2 bg-slate-800 text-xs text-white rounded shadow-xl opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 border border-white/10">
      {tooltip}
    </div>
  </div>
);
"""
content = content.replace("export default function Dashboard() {", tooltip_comp + "\nexport default function Dashboard() {")

# 3. Modify useState params
old_params = """  const [params, setParams] = useState({
    mu_a: 60, sigma_a: 15, mu_b: 55, sigma_b: 12,
    p: 25, c: 10, s: 2, pi: 3,
    Q_a: 200, Q_b: 180, R_a: 230, R_b: 200,
    lead_time: 3, expiry_k: 30, sub_rate: 0.15,
    n_days: 365, seed: 42
  });"""
new_params = """  const [params, setParams] = useState({
    mu_a: 60, sigma_a: 15, mu_b: 55, sigma_b: 12,
    p: 10, c: 5, s: 2, pi: 3,
    Q_a: 200, Q_b: 180, R_a: 230, R_b: 200,
    lead_time: 3, expiry_k: 30, sub_rate: 0.15,
    n_days: 365, seed: 42
  });
  
  const [validationError, setValidationError] = useState('');"""
content = content.replace(old_params, new_params)

# 4. Modify fetchAll and remove useEffect
old_fetch = """  const fetchAll = async () => {
    setLoading(true);
    setIsTracing(false);"""
new_fetch = """  const validateParams = () => {
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
  };

  const fetchAll = async () => {
    const error = validateParams();
    if (error) {
      setValidationError(error);
      return;
    }
    setValidationError('');
    setLoading(true);
    setIsTracing(false);"""
content = content.replace(old_fetch, new_fetch)

old_effect = """  useEffect(() => {
    fetchAll();
  }, []);"""
content = content.replace(old_effect, "")

# 5. Modify forms to use TooltipLabel
content = content.replace('<label className="text-xs text-white/60 mb-1 block">Simulation Horizon (Days)</label>',
                          '<TooltipLabel label="Simulation Horizon (Days)" tooltip="Number of days to simulate." />')
content = content.replace('<label className="text-xs text-white/60 mb-1 block">Mean (μ)</label>',
                          '<TooltipLabel label="Mean Daily Demand (μ)" tooltip="Average number of units sold per day. (Min: 5, Max: 500)" />')
content = content.replace('<label className="text-xs text-white/60 mb-1 block">Std Dev (σ)</label>',
                          '<TooltipLabel label="Standard Deviation (σ)" tooltip="Daily demand volatility. Cannot exceed Mean. (Min: 5, Max: 500)" />')
content = content.replace('<label className="text-xs text-white/60 mb-1 block">Order Qty (Q)</label>',
                          '<TooltipLabel label="Order Quantity (Q)" tooltip="Number of units ordered when inventory drops." />')
content = content.replace('<label className="text-xs text-white/60 mb-1 block">Reorder Pt (R)</label>',
                          '<TooltipLabel label="Reorder Point (R)" tooltip="Inventory level that triggers a new order." />')
content = content.replace('<label className="text-xs text-white/60 mb-1 block">Lead Time (Days)</label>',
                          '<TooltipLabel label="Lead Time (Days)" tooltip="Days between order placement and receipt." />')
content = content.replace('<label className="text-xs text-white/60 mb-1 block">Expiry Limit (Days)</label>',
                          '<TooltipLabel label="Expiry Limit (Days)" tooltip="Shelf life of the product." />')
content = content.replace('<label className="text-xs text-white/60 mb-1 block">Price</label>',
                          '<TooltipLabel label="Selling Price" tooltip="Retail selling price per unit (EGP)." />')
content = content.replace('<label className="text-xs text-white/60 mb-1 block">Cost</label>',
                          '<TooltipLabel label="Unit Cost" tooltip="Wholesale cost per unit (EGP)." />')

content = content.replace('Transaction Log', 'Simulation Table')

# Add validation error below sidebar
error_display = """          </div>

          {validationError && (
            <div className="mt-4 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-xs text-red-200">
              {validationError}
            </div>
          )}

          <button type="submit" disabled={loading} className="glass-button w-full mt-6 flex items-center justify-center gap-2 font-bold py-3">"""
content = content.replace("""          </div>

          <button type="submit" disabled={loading} className="glass-button w-full mt-6 flex items-center justify-center gap-2 font-bold py-3">""", error_display)

# 6. Idle state rendering
old_main_area = """        {/* Main Content Area */}
        <motion.div variants={item} className="flex-1 space-y-10" ref={dashboardRef}>

        {/* Header Tab & Action Bar */}"""

new_main_area = """        {/* Main Content Area */}
        <motion.div variants={item} className="flex-1 space-y-10" ref={dashboardRef}>
        
        {(!simData && !loading) ? (
          <div className="h-full min-h-[60vh] flex flex-col items-center justify-center text-center space-y-6">
            <div className="p-6 bg-primary/10 rounded-full animate-pulse">
              <Play size={48} className="text-primary/70 ml-2" />
            </div>
            <h2 className="text-3xl font-bold text-white">System Ready</h2>
            <p className="text-white/60 max-w-md">
              Adjust your pharmacy parameters in the sidebar and click "Run Simulation" to generate insights.
            </p>
          </div>
        ) : (
          <>
        {/* Header Tab & Action Bar */}"""

content = content.replace(old_main_area, new_main_area)

end_wrapper = """          </motion.div>
        )}
        </AnimatePresence>

        </motion.div>"""
new_end_wrapper = """          </motion.div>
        )}
        </AnimatePresence>
          </>
        )}
        </motion.div>"""
content = content.replace(end_wrapper, new_end_wrapper)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched Dashboard.jsx")
