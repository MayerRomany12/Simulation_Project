import os

file_path = "frontend/src/components/Dashboard.jsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add ReferenceLine to recharts imports
content = content.replace(
    "BarChart, Bar, Legend, Cell",
    "BarChart, Bar, Legend, Cell, ReferenceLine"
)

# 2. Update the BarChart structure
old_chart = """                        <div className="h-72">
                          {loading || !qData ? (
                            <div className="w-full h-full flex items-center justify-center text-white/30 animate-pulse">Loading Chart...</div>
                          ) : (
                            <ResponsiveContainer width="100%" height="100%">
                              <BarChart data={qData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                                <XAxis dataKey="Q" stroke="rgba(255,255,255,0.5)" tick={{ fill: 'rgba(255,255,255,0.5)' }} />
                                <YAxis stroke="rgba(255,255,255,0.5)" tick={{ fill: 'rgba(255,255,255,0.5)' }} domain={['auto', 'auto']} />
                                <RechartsTooltip
                                  contentStyle={{ backgroundColor: 'rgba(15,23,42,0.9)', borderColor: 'rgba(255,255,255,0.1)', borderRadius: '8px' }}
                                  cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                                />
                                <Bar dataKey="sim_profit" name="Simulated Profit" fill="#818cf8" radius={[4, 4, 0, 0]} />
                              </BarChart>
                            </ResponsiveContainer>
                          )}
                        </div>"""

new_chart = """                        <div className="flex flex-col h-full space-y-4">
                          <div className="h-64">
                            {loading || !qData ? (
                              <div className="w-full h-full flex items-center justify-center text-white/30 animate-pulse">Loading Chart...</div>
                            ) : (
                              <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={qData.data}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                                  <XAxis dataKey="Q" stroke="rgba(255,255,255,0.5)" tick={{ fill: 'rgba(255,255,255,0.5)' }} />
                                  <YAxis stroke="rgba(255,255,255,0.5)" tick={{ fill: 'rgba(255,255,255,0.5)' }} domain={['auto', 'auto']} />
                                  <RechartsTooltip
                                    contentStyle={{ backgroundColor: 'rgba(15,23,42,0.9)', borderColor: 'rgba(255,255,255,0.1)', borderRadius: '8px' }}
                                    cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                                  />
                                  <Bar dataKey="sim_profit" name="Simulated Profit" radius={[4, 4, 0, 0]}>
                                    {qData.data.map((entry, index) => (
                                      <Cell key={`cell-${index}`} fill={entry.is_optimal ? '#10b981' : '#818cf8'} />
                                    ))}
                                  </Bar>
                                  <ReferenceLine x={qData.optimal_q} stroke="#10b981" strokeDasharray="3 3" label={{ position: 'top', value: '★ Optimal', fill: '#10b981', fontSize: 12, fontWeight: 'bold' }} />
                                </BarChart>
                              </ResponsiveContainer>
                            )}
                          </div>
                          {!loading && qData && (
                            <div className="text-xs text-center bg-black/20 p-3 rounded-lg border border-[#10b981]/30">
                              <span className="text-[#10b981] font-bold">💡 Optimized Recommendation:</span> Setting Q to <strong className="text-white text-sm px-1">{qData.optimal_q}</strong> maximizes your daily profit based on current constraints.
                            </div>
                          )}
                        </div>"""

content = content.replace(old_chart, new_chart)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched Dashboard.jsx with optimal Q logic")
