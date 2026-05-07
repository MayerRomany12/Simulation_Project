import os
import re

file_path = "frontend/src/components/Dashboard.jsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Replace the Heatmap definition
old_heatmap_pattern = r"const Heatmap = \(\{ data \}\) => \{[\s\S]*?(?=\nconst TooltipLabel)"

new_heatmap = """const Heatmap = ({ data, optimalRq, currentR, currentQ }) => {
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
  
  const baselineCell = data.find(d => d.R === currentR && d.Q === currentQ);
  const baselineProfit = baselineCell ? baselineCell.profit : minP;
  const optimalProfit = optimalRq?.profit || maxP;
  const boostPct = baselineProfit > 0 ? (((optimalProfit - baselineProfit) / baselineProfit) * 100).toFixed(1) : 0;

  const getColor = (val) => {
    const ratio = (val - minP) / (maxP - minP || 1);
    const r = Math.round(15 + ratio * (16 - 15));
    const g = Math.round(23 + ratio * (185 - 23));
    const b = Math.round(42 + ratio * (129 - 42));
    return `rgb(${r}, ${g}, ${b})`;
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
          <div className="text-xs text-white/50 flex items-center justify-center p-2 sticky left-0 top-0 bg-[#0f172a] z-20">R \\ Q</div>
          {qVals.map(q => (
            <div 
              key={`hq-${q}`} 
              className={`text-[10px] text-white/80 font-semibold flex items-center justify-center sticky top-0 bg-[#0f172a] z-10 transition-colors ${hoverQ === q ? 'text-[#38bdf8]' : ''}`}
            >
              {q}
            </div>
          ))}

          {rVals.map(r => (
            <React.Fragment key={`row-${r}`}>
              <div 
                className={`text-[10px] text-white/80 font-semibold flex items-center justify-center sticky left-0 bg-[#0f172a] z-10 transition-colors ${hoverR === r ? 'text-[#38bdf8]' : ''}`}
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
                    title={`R=${r}, Q=${q}\\nProfit=${cell?.profit?.toFixed(2)}\\nDelta vs Current: ${diffStr} EGP`}
                    className={`cursor-pointer transition-all flex items-center justify-center text-[12px] relative
                      ${isHovered ? 'brightness-125 z-0 outline outline-1 outline-white/30' : ''}
                      ${isOpt ? 'outline outline-2 outline-yellow-400 z-10 shadow-[0_0_10px_rgba(250,204,21,0.5)]' : ''}
                    `}
                    style={{ 
                      height: `${cellSize}px`, 
                      backgroundColor: cell ? getColor(cell.profit) : 'transparent',
                    }}
                  >
                    {isOpt && <span>⭐</span>}
                  </div>
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>

      {optimalRq && (
        <div className="text-xs text-center bg-black/20 p-3 rounded-lg border border-[#10b981]/30">
          <span className="text-[#10b981] font-bold">🎯 Strategic Sweet Spot:</span> Achieving the perfect balance at <strong>R={optimalRq.r}</strong> and <strong>Q={optimalRq.q}</strong> can boost your stability by <strong className="text-white">{boostPct}%</strong>.
        </div>
      )}
    </div>
  );
};
"""

content = re.sub(old_heatmap_pattern, new_heatmap, content)

# 2. Update usage
old_usage = "<Heatmap data={rqData} />"
new_usage = "<Heatmap data={rqData.data} optimalRq={rqData.optimal_rq} currentR={params.R_a} currentQ={params.Q_a} />"
content = content.replace(old_usage, new_usage)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Dashboard.jsx updated.")
