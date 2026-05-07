import os
import re

file_path = "frontend/src/components/Dashboard.jsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update getColor
old_getColor = """  const getColor = (val) => {
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

new_getColor = """  const getColor = (val) => {
    const ratio = (val - minP) / (maxP - minP || 1);
    if (ratio < 0.33) {
      const rRatio = ratio / 0.33;
      const r = Math.round(15 + rRatio * (13 - 15));
      const g = Math.round(23 + rRatio * (148 - 23));
      const b = Math.round(42 + rRatio * (136 - 42));
      return `rgb(${r}, ${g}, ${b})`;
    } else if (ratio < 0.66) {
      const rRatio = (ratio - 0.33) / 0.33;
      const r = Math.round(13 + rRatio * (6 - 13));
      const g = Math.round(148 + rRatio * (182 - 148));
      const b = Math.round(136 + rRatio * (212 - 136));
      return `rgb(${r}, ${g}, ${b})`;
    } else {
      const rRatio = (ratio - 0.66) / 0.34;
      const r = Math.round(6 + rRatio * (45 - 6));
      const g = Math.round(182 + rRatio * (212 - 182));
      const b = Math.round(212 + rRatio * (191 - 212));
      return `rgb(${r}, ${g}, ${b})`;
    }
  };"""
content = content.replace(old_getColor, new_getColor)

# 2. Border for cell:
content = content.replace("border border-white/5", "border-[1px] border-[rgba(255,255,255,0.03)]")

# 3. Crosshair Sync:
content = content.replace("text-[#fb7185] bg-[rgba(124,58,237,0.1)]", "text-[#2dd4bf] bg-[rgba(6,182,212,0.15)]")
content = content.replace("${isHovered ? 'bg-[rgba(124,58,237,0.1)] z-0 outline outline-1 outline-white/30' : ''}", "${isHovered ? 'bg-[rgba(6,182,212,0.15)] z-0 outline outline-1 outline-white/30' : ''}")

# 4. Glowing Optimal Point:
content = content.replace("${isOpt ? 'outline outline-2 outline-[#fb7185] z-10 shadow-[0_0_15px_rgba(251,113,133,0.6)] bg-[#fb7185]/20' : ''}", "${isOpt ? 'outline outline-2 outline-[#2dd4bf] z-10 shadow-[0_0_15px_rgba(6,182,212,0.4)] bg-[#2dd4bf]/20' : ''}")
content = content.replace('<span className="drop-shadow-[0_0_8px_rgba(251,113,133,0.8)]">⭐</span>', '<span className="drop-shadow-[0_0_8px_rgba(45,212,191,0.8)]">⭐</span>')

# 5. Apply Button & Badge:
content = content.replace('border-[#db2777]/30', 'border-[#06b6d4]/30')
content = content.replace('text-[#fb7185] font-bold', 'text-[#06b6d4] font-bold')
content = content.replace(
    'className="px-4 py-2 bg-gradient-to-r from-[#7c3aed] to-[#db2777] hover:from-[#6d28d9] hover:to-[#be185d] text-white font-bold rounded-lg shadow-[0_0_15px_rgba(219,39,119,0.4)] transition-all shrink-0"',
    'className="px-4 py-2 bg-gradient-to-r from-[#0d9488] to-[#06b6d4] hover:from-[#0f766e] hover:to-[#0891b2] text-white font-bold rounded-lg shadow-[0_0_15px_rgba(6,182,212,0.4)] transition-all shrink-0"'
)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Dashboard.jsx updated to Cyan/Teal Theme")
