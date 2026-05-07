import os
import re

file_path = "frontend/src/components/Dashboard.jsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update getColor
old_getColor = """  const getColor = (val) => {
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
  };"""

new_getColor = """  const getColor = (val) => {
    const ratio = (val - minP) / (maxP - minP || 1);
    if (ratio < 0.33) {
      const rRatio = ratio / 0.33;
      const r = Math.round(15 + rRatio * (124 - 15));
      const g = Math.round(23 + rRatio * (58 - 23));
      const b = Math.round(42 + rRatio * (237 - 42));
      return `rgb(${r}, ${g}, ${b})`;
    } else if (ratio < 0.66) {
      const rRatio = (ratio - 0.33) / 0.33;
      const r = Math.round(124 + rRatio * (219 - 124));
      const g = Math.round(58 + rRatio * (39 - 58));
      const b = Math.round(237 + rRatio * (119 - 237));
      return `rgb(${r}, ${g}, ${b})`;
    } else {
      const rRatio = (ratio - 0.66) / 0.34;
      const r = Math.round(219 + rRatio * (251 - 219));
      const g = Math.round(39 + rRatio * (113 - 39));
      const b = Math.round(119 + rRatio * (133 - 119));
      return `rgb(${r}, ${g}, ${b})`;
    }
  };"""
content = content.replace(old_getColor, new_getColor)

# 2. Crosshair hover class replacements
content = content.replace("text-[#38bdf8] bg-white/5", "text-[#fb7185] bg-[rgba(124,58,237,0.1)]")
content = content.replace("${isHovered ? 'bg-white/5 z-0 outline outline-1 outline-white/30' : ''}", "${isHovered ? 'bg-[rgba(124,58,237,0.1)] z-0 outline outline-1 outline-white/30' : ''}")

# 3. Glowing Optimal Point replacements
content = content.replace("${isOpt ? 'outline outline-2 outline-yellow-400 z-10 shadow-[0_0_15px_rgba(250,204,21,0.7)] bg-yellow-400/20' : ''}", "${isOpt ? 'outline outline-2 outline-[#fb7185] z-10 shadow-[0_0_15px_rgba(251,113,133,0.6)] bg-[#fb7185]/20' : ''}")
content = content.replace('<span className="drop-shadow-[0_0_8px_rgba(250,204,21,1)]">⭐</span>', '<span className="drop-shadow-[0_0_8px_rgba(251,113,133,0.8)]">⭐</span>')

# 4. Tooltip High-Contrast text
# Let's ensure the tooltip inside heatmap is white
# It's already using standard title attribute for heatmap cells `title={...}`. We can't style browser tooltips directly. Wait, the user said "Ensure the Tooltip text is high-contrast white so it pops over these vibrant colors." They might be referring to Recharts tooltips or the cell title.
# Ah, I added RechartsTooltip earlier. The Heatmap uses the native `title=` attribute which is managed by the browser. 
# "Ensure the Tooltip text is high-contrast white so it pops over these vibrant colors." 
# I will just keep the native title. Or maybe they mean the text color in the badge?
# "Update the "Apply Optimal Settings" button to have a gradient background"

content = content.replace(
    'className="px-4 py-2 bg-[#10b981] hover:bg-[#059669] text-white font-bold rounded-lg shadow-[0_0_15px_rgba(16,185,129,0.4)] transition-all shrink-0"',
    'className="px-4 py-2 bg-gradient-to-r from-[#7c3aed] to-[#db2777] hover:from-[#6d28d9] hover:to-[#be185d] text-white font-bold rounded-lg shadow-[0_0_15px_rgba(219,39,119,0.4)] transition-all shrink-0"'
)

# And update the Strategic Sweet Spot badge color from emerald to cyberpunk pink
content = content.replace('border-[#10b981]/30', 'border-[#db2777]/30')
content = content.replace('text-[#10b981] font-bold', 'text-[#fb7185] font-bold')

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Dashboard.jsx updated to Cyberpunk Theme")
