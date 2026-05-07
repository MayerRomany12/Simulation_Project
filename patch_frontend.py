import os
import re

file_path = "frontend/src/components/Dashboard.jsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update Heatmap Component
old_heatmap_pattern = r"const Heatmap = \(\{ data, optimalRq, currentR, currentQ \}\) => \{[\s\S]*?(?=\nconst TooltipLabel)"

new_heatmap = """const Heatmap = ({ data, optimalRq, currentR, currentQ, onApply }) => {
  const [cellSize, setCellSize] = useState(40);
  const [hoverR, setHoverR] = useState(null);
  const [hoverQ, setHoverQ] = useState(null);

  if (!data || data.length === 0) return <div className="text-white/50 text-center py-10">No data</div>;

  const rSet = new Set();
  const qSet = new Set();
  data.forEach(d => { rSet.add(d.R); qSet.add(d.Q); });

  const rVals = Array.from(rSet).sort((a, b) => a - b);
  const qVals = Array.from(qSet).sort((a, b) => a - b);

  const minP = Math.min(...data.map(d => d.profit));
  const maxP = Math.max(...data.map(d => d.profit));
  const midP = (minP + maxP) / 2;
  
  const baselineCell = data.find(d => d.R === currentR && d.Q === currentQ);
  const baselineProfit = baselineCell ? baselineCell.profit : minP;
  const optimalProfit = optimalRq?.profit || maxP;
  const boostPct = baselineProfit > 0 ? (((optimalProfit - baselineProfit) / baselineProfit) * 100).toFixed(1) : 0;

  const getColor = (val) => {
    // Tri-color scale: #1e1b4b (30,27,75) -> #0f172a (15,23,42) -> #10b981 (16,185,129)
    if (val <= midP) {
      const ratio = (val - minP) / (midP - minP || 1);
      const r = Math.round(30 + ratio * (15 - 30));
      const g = Math.round(27 + ratio * (23 - 27));
      const b = Math.round(75 + ratio * (42 - 75));
      return `rgb(${r}, ${g}, ${b})`;
    } else {
      const ratio = (val - midP) / (maxP - midP || 1);
      const r = Math.round(15 + ratio * (16 - 15));
      const g = Math.round(23 + ratio * (185 - 23));
      const b = Math.round(42 + ratio * (129 - 42));
      return `rgb(${r}, ${g}, ${b})`;
    }
  };

  return (
    <div className="flex flex-col space-y-4">
      <div className="flex items-center justify-between text-xs text-white/70 bg-black/20 p-2 rounded border border-white/5">
        <div className="flex items-center gap-2">
          <span>Zoom:</span>
          <input 
            type="range" min="30" max="80" step="5" 
            value={cellSize} 
            onChange={e => setCellSize(Number(e.target.value))} 
            className="w-24 accent-accent"
          />
        </div>
        <div>Hover over cells for coordinates & delta.</div>
      </div>
      
      <div className="overflow-auto custom-scrollbar border border-white/10 rounded max-h-[500px]">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: `auto repeat(${qVals.length}, ${cellSize}px)`,
            gap: '1px',
            backgroundColor: 'rgba(255,255,255,0.05)',
            padding: '1px'
          }}
        >
          <div className="text-xs text-white/50 flex items-center justify-center p-2 sticky left-0 top-0 bg-[#0f172a] z-20 backdrop-blur-md">R \\ Q</div>
          {qVals.map(q => (
            <div 
              key={`hq-${q}`} 
              className={`text-[10px] text-white/80 font-semibold flex items-center justify-center sticky top-0 bg-[#0f172a] z-10 transition-colors backdrop-blur-md ${hoverQ === q ? 'text-[#38bdf8] bg-white/5' : ''}`}
            >
              {q}
            </div>
          ))}

          {rVals.map(r => (
            <React.Fragment key={`row-${r}`}>
              <div 
                className={`text-[10px] text-white/80 font-semibold flex items-center justify-center sticky left-0 bg-[#0f172a] z-10 transition-colors backdrop-blur-md ${hoverR === r ? 'text-[#38bdf8] bg-white/5' : ''}`}
              >
                {r}
              </div>
              {qVals.map(q => {
                const cell = data.find(d => d.R === r && d.Q === q);
                const isOpt = optimalRq && optimalRq.r === r && optimalRq.q === q;
                const isHovered = hoverR === r || hoverQ === q;
                const profitDiff = cell ? (cell.profit - baselineProfit) : 0;
                const diffStr = profitDiff > 0 ? `+${profitDiff.toFixed(0)}` : profitDiff.toFixed(0);
                
                return (
                  <div
                    key={`cell-${r}-${q}`}
                    onMouseEnter={() => { setHoverR(r); setHoverQ(q); }}
                    onMouseLeave={() => { setHoverR(null); setHoverQ(null); }}
                    title={`R=${r}, Q=${q}\\nProfit=${cell?.profit?.toFixed(2)} (Avg over 5 runs)\\nDelta vs Current: ${diffStr} EGP`}
                    className={`cursor-pointer transition-all flex items-center justify-center text-[12px] relative
                      border border-white/5
                      ${isHovered ? 'bg-white/5 z-0 outline outline-1 outline-white/30' : ''}
                      ${isOpt ? 'outline outline-2 outline-yellow-400 z-10 shadow-[0_0_15px_rgba(250,204,21,0.7)] bg-yellow-400/20' : ''}
                    `}
                    style={{ 
                      height: `${cellSize}px`, 
                      backgroundColor: cell && !isOpt && !isHovered ? getColor(cell.profit) : (cell && (isOpt || isHovered) ? undefined : 'transparent'),
                    }}
                  >
                    {isOpt && <span className="drop-shadow-[0_0_8px_rgba(250,204,21,1)]">⭐</span>}
                  </div>
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>

      {optimalRq && (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-xs bg-black/20 p-4 rounded-xl border border-[#10b981]/30">
          <div className="text-white/80">
            <span className="text-[#10b981] font-bold">🎯 Strategic Sweet Spot:</span> Achieving the perfect balance at <strong>R={optimalRq.r}</strong> and <strong>Q={optimalRq.q}</strong> can boost your stability by <strong className="text-white">{boostPct}%</strong>.
          </div>
          <button 
            type="button"
            onClick={() => onApply && onApply(optimalRq.r, optimalRq.q)}
            className="px-4 py-2 bg-[#10b981] hover:bg-[#059669] text-white font-bold rounded-lg shadow-[0_0_15px_rgba(16,185,129,0.4)] transition-all shrink-0"
          >
            Apply Optimal Settings
          </button>
        </div>
      )}
    </div>
  );
};
"""
content = re.sub(old_heatmap_pattern, new_heatmap, content)

# 2. Add handleApplyOptimal to Dashboard
apply_optimal_code = """  const handleApplyOptimal = (r, q) => {
    setParams(prev => ({ ...prev, R_a: r, Q_a: q }));
    setValidationError('');
    // Optionally trigger fetchAll() automatically here if desired
  };

  const dashboardRef = useRef(null);"""
content = content.replace("const dashboardRef = useRef(null);", apply_optimal_code)

# 3. Update Heatmap usage in render
old_usage = "<Heatmap data={rqData.data} optimalRq={rqData.optimal_rq} currentR={params.R_a} currentQ={params.Q_a} />"
new_usage = "<Heatmap data={rqData.data} optimalRq={rqData.optimal_rq} currentR={params.R_a} currentQ={params.Q_a} onApply={handleApplyOptimal} />"
content = content.replace(old_usage, new_usage)

# 4. Update RechartsTooltip for Profit vs Q
# Add a CustomTooltip to prepend the "Averaged over 5 scenarios" or we can just append it to the name.
# RechartsTooltip allows formatter={(value, name, props) => [value, name + " (Avg over 5 runs)"]}
old_tooltip = """                                  <RechartsTooltip
                                    contentStyle={{ backgroundColor: 'rgba(15,23,42,0.9)', borderColor: 'rgba(255,255,255,0.1)', borderRadius: '8px' }}
                                    itemStyle={{ color: '#fff' }}
                                    cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                                  />"""
new_tooltip = """                                  <RechartsTooltip
                                    contentStyle={{ backgroundColor: 'rgba(15,23,42,0.9)', borderColor: 'rgba(255,255,255,0.1)', borderRadius: '8px' }}
                                    itemStyle={{ color: '#fff' }}
                                    cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                                    formatter={(value) => [Number(value).toFixed(2), "Simulated Profit (Avg over 5 runs)"]}
                                  />"""
content = content.replace(old_tooltip, new_tooltip)

# 5. Update Loading Indicators
# Run Simulation button
old_run_btn = "{loading ? 'Running...' : 'Run Simulation'}"
new_run_btn = "{loading ? 'Running 5 Scenarios...' : 'Run Simulation'}"
content = content.replace(old_run_btn, new_run_btn)

# Heatmap loading
old_hm_loading = "Loading Heatmap..."
new_hm_loading = "Stabilizing Results... (Running 1125 Scenarios)"
content = content.replace(old_hm_loading, new_hm_loading)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated frontend Dashboard.jsx with UI polish and averaging text")
