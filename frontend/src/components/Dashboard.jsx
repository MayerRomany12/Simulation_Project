import React, { useState, useEffect, useRef } from 'react';
import { runSimulation, runStressTest, runProfitVsQ, runSensitivityRQ, suggestR } from '../api';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  BarChart, Bar, Legend, Cell
} from 'recharts';
import { Activity, DollarSign, Package, AlertTriangle, TrendingUp, RefreshCw, Download, List, BarChart2, Play, Square, Settings, Info } from 'lucide-react';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';
import { motion, AnimatePresence, animate } from 'framer-motion';

/* ── Smooth animated number counter ── */
const AnimatedCounter = ({ value, suffix = '', decimals = 0 }) => {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current || value == null || isNaN(value)) return;
    const ctrl = animate(0, value, {
      duration: 1.4,
      ease: 'easeOut',
      onUpdate: v => { if (ref.current) ref.current.textContent = v.toFixed(decimals) + suffix; }
    });
    return () => ctrl.stop();
  }, [value, suffix, decimals]);
  if (value == null || isNaN(value)) return <span>—</span>;
  return <span ref={ref}>{(0).toFixed(decimals)}{suffix}</span>;
};

/* ── KPI card with neon hover glow ── */
const KPICard = ({ title, rawValue, suffix = '', decimals = 0, icon: Icon, colorClass }) => (
  <motion.div
    whileHover={{ scale: 1.03, boxShadow: '0 0 22px rgba(56,189,248,0.45)' }}
    transition={{ type: 'spring', stiffness: 300, damping: 20 }}
    className="glass-panel p-6 flex items-center space-x-4"
  >
    <div className={`p-3 rounded-full bg-black/20 ${colorClass}`}>
      <Icon size={24} />
    </div>
    <div>
      <h3 className="text-sm font-medium text-white/60">{title}</h3>
      <p className="text-2xl font-bold text-white">
        <AnimatedCounter value={rawValue} suffix={suffix} decimals={decimals} />
      </p>
    </div>
  </motion.div>
);

const Heatmap = ({ data }) => {
  if (!data || data.length === 0) return <div className="text-white/50 text-center py-10">No data</div>;

  const rSet = new Set();
  const qSet = new Set();
  data.forEach(d => { rSet.add(d.R); qSet.add(d.Q); });

  const rVals = Array.from(rSet).sort((a, b) => a - b);
  const qVals = Array.from(qSet).sort((a, b) => a - b);

  const minP = Math.min(...data.map(d => d.profit));
  const maxP = Math.max(...data.map(d => d.profit));

  const getColor = (val) => {
    const ratio = (val - minP) / (maxP - minP || 1);
    const r = Math.round(56 + ratio * (244 - 56));
    const g = Math.round(189 + ratio * (114 - 189));
    const b = Math.round(248 + ratio * (182 - 248));
    return `rgb(${r}, ${g}, ${b})`;
  };

  return (
    <div className="overflow-x-auto">
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `auto repeat(${qVals.length}, minmax(40px, 1fr))`,
          gap: '2px'
        }}
      >
        <div className="text-xs text-white/50 flex items-center justify-center p-2">R \ Q</div>
        {qVals.map(q => <div key={`hq-${q}`} className="text-xs text-white/80 font-semibold text-center p-2">{q}</div>)}

        {rVals.map(r => (
          <React.Fragment key={`row-${r}`}>
            <div className="text-xs text-white/80 font-semibold flex items-center justify-center p-2">{r}</div>
            {qVals.map(q => {
              const cell = data.find(d => d.R === r && d.Q === q);
              return (
                <div
                  key={`cell-${r}-${q}`}
                  title={`R=${r}, Q=${q}\nProfit=${cell?.profit?.toFixed(2)}`}
                  className="h-10 rounded-sm cursor-pointer hover:opacity-80 transition-opacity flex items-center justify-center text-[10px]"
                  style={{ backgroundColor: cell ? getColor(cell.profit) : 'transparent' }}
                >
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};


const TooltipLabel = ({ label, tooltip }) => (
  <div className="flex items-center gap-1 group relative mb-1">
    <label className="text-xs text-white/60 block">{label}</label>
    <Info size={12} className="text-white/40 cursor-help" />
    <div className="absolute left-0 bottom-full mb-2 w-48 p-2 bg-slate-800 text-xs text-white rounded shadow-xl opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 border border-white/10">
      {tooltip}
    </div>
  </div>
);

export default function Dashboard() {
  const [params, setParams] = useState({
    mu_a: 60, sigma_a: 15, mu_b: 55, sigma_b: 12,
    p: 10, c: 5, s: 2, pi: 3,
    Q_a: 200, Q_b: 180, R_a: 230, R_b: 200,
    lead_time: 3, expiry_k: 30, sub_rate: 0.15,
    n_days: 365, seed: 42
  });
  
  const [validationError, setValidationError] = useState('');

  const [serviceLevelTarget, setServiceLevelTarget] = useState(0.95);

  const [loading, setLoading] = useState(false);
  const [simData, setSimData] = useState(null);
  const [stressData, setStressData] = useState(null);
  const [qData, setQData] = useState(null);
  const [rqData, setRqData] = useState(null);

  const [activeTab, setActiveTab] = useState('charts');
  const [logPage, setLogPage] = useState(1);
  const rowsPerPage = 50;

  const [traceSpeed, setTraceSpeed] = useState(50);
  const [isTracing, setIsTracing] = useState(false);
  const [traceDay, setTraceDay] = useState(365);

  const dashboardRef = useRef(null);

  const validateParams = () => {
    const demandParams = ['mu_a', 'sigma_a', 'mu_b', 'sigma_b'];
    for (const p of demandParams) {
      if (params[p] < 5 || params[p] > 500) {
        return `Demand parameter ${p} must be between 5 and 500.`;
      }
    }
    if (params.sigma_a > params.mu_a) return "Product A: Std Dev (σ) cannot exceed Mean (μ).";
    if (params.sigma_b > params.mu_b) return "Product B: Std Dev (σ) cannot exceed Mean (μ).";
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
    setIsTracing(false);
    try {
      const [simRes, stressRes, qRes, rqRes] = await Promise.all([
        runSimulation(params),
        runStressTest(params),
        runProfitVsQ(params),
        runSensitivityRQ(params)
      ]);
      setSimData(simRes);
      setStressData(stressRes);
      setQData(qRes);
      setRqData(rqRes);
      setTraceDay(simRes.timeline.length);
    } catch (err) {
      console.error(err);
      alert("Error fetching data. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };



  useEffect(() => {
    let interval;
    if (isTracing && simData) {
      interval = setInterval(() => {
        setTraceDay(prev => {
          const maxDays = simData.timeline.length;
          const nextDay = prev + 1;
          // Auto-paginate log table
          setLogPage(Math.ceil(nextDay / rowsPerPage) || 1);

          if (nextDay >= maxDays) {
            setIsTracing(false);
            return maxDays;
          }
          return nextDay;
        });
      }, traceSpeed);
    }
    return () => clearInterval(interval);
  }, [isTracing, traceSpeed, simData]);

  const handleParamChange = (e) => {
    const { name, value, type, checked } = e.target;
    const val = type === 'checkbox' ? checked : parseFloat(value) || 0;
    setParams(prev => ({ ...prev, [name]: val }));
  };

  const handleSuggestR = async () => {
    try {
      const res = await suggestR({
        mu_daily: params.mu_a,
        sigma_daily: params.sigma_a,
        lead_time: params.lead_time,
        service_level: serviceLevelTarget
      });
      setParams(prev => ({ ...prev, R_a: res.reorder_point }));
    } catch (err) {
      console.error(err);
      alert("Error calculating R");
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    fetchAll();
  };

  const handleStartTrace = () => {
    setTraceDay(0);
    setLogPage(1);
    setIsTracing(true);
    setActiveTab('charts');
  };

  const handleStopTrace = () => {
    setIsTracing(false);
    // Switch to log tab to immediately see where it stopped
    setActiveTab('log');
  };

  const handleExportPDF = async () => {
    const element = dashboardRef.current;
    if (!element) return;

    // Briefly stop tracing for clean capture
    const wasTracing = isTracing;
    setIsTracing(false);

    try {
      const canvas = await html2canvas(element, { scale: 1.5, useCORS: true, backgroundColor: '#0f172a' });
      const imgData = canvas.toDataURL('image/png');
      const pdf = new jsPDF('p', 'mm', 'a4');
      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = (canvas.height * pdfWidth) / canvas.width;
      pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, pdfHeight);
      pdf.save('Pharmacy_Simulation_Report.pdf');
    } catch (err) {
      console.error("PDF Export failed", err);
    }

    if (wasTracing) setIsTracing(true);
  };

  const timelineToRender = simData ? simData.timeline.slice(0, traceDay) : [];

  // Pagination logic
  const totalPages = simData ? Math.ceil(simData.timeline.length / rowsPerPage) : 0;
  const paginatedLogs = simData ? simData.timeline.slice((logPage - 1) * rowsPerPage, logPage * rowsPerPage) : [];

  // Spotlight on glass panels
  const handleMouseMove = null; // disabled

  const page = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.05 } } };
  const item = { hidden: { opacity: 0, y: 18 }, show: { opacity: 1, y: 0 } };
  const tab  = { hidden: { opacity: 0, x: 20 }, show: { opacity: 1, x: 0 }, exit: { opacity: 0, x: -20 } };

  return (
    <div>
      {/* ── Animated Mesh Gradient Background ── */}
      <div className="mesh-bg">
        <div className="mesh-blob" style={{ width: 800, height: 800, top: -150, left: -250, background: 'radial-gradient(circle, rgba(56,189,248,0.35), transparent 70%)' }} />
        <div className="mesh-blob" style={{ width: 700, height: 700, bottom: -100, right: -150, background: 'radial-gradient(circle, rgba(129,140,248,0.35), transparent 70%)', animationDelay: '-6s', animationDirection: 'reverse' }} />
      </div>
      {/* ── Data Particles ── */}
      <div className="particles-container">
        {Array.from({ length: 60 }, (_, i) => (
          <div key={i} className="particle" style={{
            left: `${(i * 7.3) % 100}%`,
            width: `${2 + (i % 4)}px`,
            height: `${2 + (i % 4)}px`,
            animationDuration: `${3 + (i % 5)}s`,
            animationDelay: `${(i * 0.2) % 5}s`,
          }} />
        ))}
      </div>

      <motion.div variants={page} initial="hidden" animate="show" className="flex flex-col lg:flex-row gap-12 relative p-4 lg:p-6">
        {/* Sidebar */}
        <motion.div variants={item} className="w-full lg:w-80 flex-shrink-0">
          <form onSubmit={handleSubmit} className="glass-panel p-6 sticky top-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <Settings className="text-primary" />
              <h2 className="text-xl font-bold text-white">Parameters</h2>
            </div>
            <button type="button" onClick={handleExportPDF} title="Download Report" className="p-2 rounded hover:bg-white/10 text-white/70 transition">
              <Download size={18} />
            </button>
          </div>

          <div className="space-y-4 max-h-[75vh] overflow-y-auto pr-2 custom-scrollbar">
            <h3 className="text-sm text-primary font-semibold uppercase tracking-wider">Simulation Setting</h3>
            <div className="grid grid-cols-1 gap-4 mb-4">
              <div>
                <TooltipLabel label="Simulation Horizon (Days)" tooltip="Number of days to simulate." />
                <input type="number" name="n_days" min="100" max="30000" value={params.n_days} onChange={handleParamChange} className="glass-input w-full" />
              </div>
            </div>

            <h3 className="text-sm text-primary font-semibold uppercase tracking-wider">Demand (Product A)</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <TooltipLabel label="Mean Daily Demand (μ)" tooltip="Average number of units sold per day. (Min: 5, Max: 500)" />
                <input type="number" name="mu_a" value={params.mu_a} onChange={handleParamChange} className="glass-input w-full" />
              </div>
              <div>
                <TooltipLabel label="Standard Deviation (σ)" tooltip="Daily demand volatility. Cannot exceed Mean. (Min: 5, Max: 500)" />
                <input type="number" name="sigma_a" value={params.sigma_a} onChange={handleParamChange} className="glass-input w-full" />
              </div>
            </div>

            <h3 className="text-sm text-primary font-semibold uppercase tracking-wider mt-6">Inventory Policy (A)</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <TooltipLabel label="Order Quantity (Q)" tooltip="Number of units ordered when inventory drops." />
                <input type="number" name="Q_a" value={params.Q_a} onChange={handleParamChange} className="glass-input w-full" />
              </div>
              <div>
                <TooltipLabel label="Reorder Point (R)" tooltip="Inventory level that triggers a new order." />
                <input type="number" name="R_a" value={params.R_a} onChange={handleParamChange} className="glass-input w-full" />
              </div>
            </div>

            <div className="mt-4 p-3 bg-primary/10 rounded-lg border border-primary/20">
              <label className="text-xs text-white/80 mb-2 block font-medium">Auto-Suggest Reorder Point</label>
              <div className="flex gap-2">
                <div className="flex-1">
                  <div className="flex items-center">
                    <input type="number" step="0.01" value={serviceLevelTarget} onChange={(e) => setServiceLevelTarget(parseFloat(e.target.value))} className="glass-input w-full text-sm py-1 px-2" placeholder="e.g. 0.95" />
                    <span className="ml-2 text-xs text-white/50">Target SL</span>
                  </div>
                </div>
                <button type="button" onClick={handleSuggestR} className="bg-primary/80 hover:bg-primary text-white text-xs px-3 py-1 rounded transition-colors font-medium">
                  Suggest R
                </button>
              </div>
            </div>

            <h3 className="text-sm text-primary font-semibold uppercase tracking-wider mt-6">Supply & Constraints</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <TooltipLabel label="Lead Time (Days)" tooltip="Days between order placement and receipt." />
                <input type="number" name="lead_time" value={params.lead_time} onChange={handleParamChange} className="glass-input w-full" />
              </div>
              <div>
                <TooltipLabel label="Expiry Limit (Days)" tooltip="Shelf life of the product." />
                <input type="number" name="expiry_k" value={params.expiry_k} onChange={handleParamChange} className="glass-input w-full" />
              </div>
            </div>

            <h3 className="text-sm text-primary font-semibold uppercase tracking-wider mt-6">Economics (EGP)</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <TooltipLabel label="Selling Price" tooltip="Retail selling price per unit (EGP)." />
                <input type="number" name="p" value={params.p} onChange={handleParamChange} className="glass-input w-full" />
              </div>
              <div>
                <TooltipLabel label="Unit Cost" tooltip="Wholesale cost per unit (EGP)." />
                <input type="number" name="c" value={params.c} onChange={handleParamChange} className="glass-input w-full" />
              </div>
            </div>
          </div>

          {validationError && (
            <div className="mt-4 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-xs text-red-200">
              {validationError}
            </div>
          )}

          <button type="submit" disabled={loading} className="glass-button w-full mt-6 flex items-center justify-center gap-2 font-bold py-3">
            {loading ? <RefreshCw className="animate-spin" size={18} /> : <Activity size={18} />}
            {loading ? 'Running...' : 'Run Simulation'}
          </button>
          </form>
        </motion.div>

        {/* Main Content Area */}
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
        {/* Header Tab & Action Bar */}
        <div className="flex flex-col sm:flex-row justify-between items-center gap-4 bg-white/5 p-2 rounded-xl backdrop-blur-md border border-white/10">
          <div className="flex space-x-2">
            <button
              onClick={() => setActiveTab('charts')}
              className={`px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-medium transition-all ${activeTab === 'charts' ? 'bg-primary text-white shadow-lg shadow-primary/20' : 'text-white/60 hover:text-white hover:bg-white/10'}`}
            >
              <BarChart2 size={16} /> Charts
            </button>
            <button
              onClick={() => setActiveTab('log')}
              className={`px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-medium transition-all ${activeTab === 'log' ? 'bg-primary text-white shadow-lg shadow-primary/20' : 'text-white/60 hover:text-white hover:bg-white/10'}`}
            >
              <List size={16} /> Simulation Table
            </button>
          </div>

          {/* Live Trace Controls */}
          {activeTab === 'charts' && (
            <div className="flex items-center gap-3 bg-black/30 px-4 py-2 rounded-lg border border-white/5">
              {isTracing ? (
                <button
                  onClick={handleStopTrace}
                  className="flex items-center gap-2 text-xs font-semibold text-danger text-red-400 hover:text-red-300 transition-colors"
                >
                  <Square size={14} className="fill-current" />
                  Stop
                </button>
              ) : (
                <button
                  onClick={handleStartTrace}
                  disabled={loading || !simData}
                  className="flex items-center gap-2 text-xs font-semibold text-accent hover:text-white transition-colors disabled:opacity-50"
                >
                  <Play size={14} />
                  Live Trace
                </button>
              )}
              <div className="h-4 w-px bg-white/20"></div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-white/50 uppercase tracking-wider w-10 text-right">{traceSpeed}ms</span>
                <input
                  type="range"
                  min="10" max="200" step="10"
                  value={traceSpeed}
                  onChange={(e) => setTraceSpeed(Number(e.target.value))}
                  className="w-24 accent-accent"
                />
              </div>
            </div>
          )}
        </div>

        {/* KPI Row */}
        <motion.div variants={item} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
          <KPICard title="Avg Daily Profit"  rawValue={simData?.kpis?.avg_profit}          suffix=" EGP" decimals={0} icon={DollarSign}    colorClass="text-primary"   />
          <KPICard title="Service Level (A)" rawValue={simData ? simData.kpis.service_level_a * 100 : null} suffix="%" decimals={1} icon={Activity} colorClass="text-success" />
          <KPICard title="Waste Pct (A)"     rawValue={simData?.kpis?.waste_pct_a}          suffix="%"   decimals={1} icon={AlertTriangle} colorClass="text-warning"   />
          <KPICard title="Avg Inventory (A)" rawValue={simData?.kpis?.avg_inv_a}             suffix=""    decimals={0} icon={Package}       colorClass="text-secondary" />
        </motion.div>

        <AnimatePresence mode="wait">
        {activeTab === 'charts' ? (
          <motion.div key="charts" variants={tab} initial="hidden" animate="show" exit="exit" transition={{ duration: 0.25 }} className="space-y-10">
            {/* Charts Row 1 */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-10">
              <div className="glass-panel p-6">
                <h3 className="text-lg font-bold mb-4 text-white flex items-center gap-2">
                  <TrendingUp className="text-primary" size={20} />
                  Inventory Timeline (Live Trace)
                </h3>
                <div className="h-72">
                  {loading || !simData ? (
                    <div className="w-full h-full flex items-center justify-center text-white/30 animate-pulse">Loading Chart...</div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={timelineToRender}>
                        <defs>
                          <linearGradient id="colorInvA" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#38bdf8" stopOpacity={0} />
                          </linearGradient>
                          <linearGradient id="colorInvB" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#f472b6" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#f472b6" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                        <XAxis dataKey="day" stroke="rgba(255,255,255,0.5)" tick={{ fill: 'rgba(255,255,255,0.5)' }} />
                        <YAxis stroke="rgba(255,255,255,0.5)" tick={{ fill: 'rgba(255,255,255,0.5)' }} />
                        <RechartsTooltip
                          contentStyle={{ backgroundColor: 'rgba(15,23,42,0.9)', borderColor: 'rgba(255,255,255,0.1)', borderRadius: '8px' }}
                          itemStyle={{ color: '#fff' }}
                        />
                        <Legend />
                        <Area type="stepAfter" dataKey="inv_end_a" name="Inv A" stroke="#38bdf8" fillOpacity={1} fill="url(#colorInvA)" animationDuration={0} />
                        <Area type="stepAfter" dataKey="inv_end_b" name="Inv B" stroke="#f472b6" fillOpacity={1} fill="url(#colorInvB)" animationDuration={0} />
                      </AreaChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>

              <div className="glass-panel p-6">
                <h3 className="text-lg font-bold mb-4 text-white flex items-center gap-2">
                  <DollarSign className="text-success" size={20} />
                  Profit vs. Order Quantity (Q)
                </h3>
                <div className="h-72">
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
                </div>
              </div>
            </div>

            {/* Charts Row 2 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
              <div className="glass-panel p-6">
                <h3 className="text-lg font-bold mb-4 text-white flex items-center gap-2">
                  <Activity className="text-accent" size={20} />
                  R vs. Q Sensitivity Analysis (Profit)
                </h3>
                <div className="w-full">
                  {loading || !rqData ? (
                    <div className="h-64 flex items-center justify-center text-white/30 animate-pulse">Loading Heatmap...</div>
                  ) : (
                    <Heatmap data={rqData} />
                  )}
                </div>
              </div>

              <div className="glass-panel p-6">
                <h3 className="text-lg font-bold mb-4 text-white flex items-center gap-2">
                  <AlertTriangle className="text-warning" size={20} />
                  Stress Test Comparison
                </h3>
                <div className="space-y-4">
                  {loading || !stressData ? (
                    <div className="h-64 flex items-center justify-center text-white/30 animate-pulse">Loading Data...</div>
                  ) : Object.entries(stressData).map(([scenario, data]) => (
                    <div key={scenario} className="bg-black/20 p-4 rounded-lg border border-white/5 relative overflow-hidden group">
                      <div className="absolute inset-0 bg-gradient-to-r from-primary/0 via-primary/5 to-transparent -translate-x-[100%] group-hover:translate-x-[100%] transition-transform duration-1000"></div>
                      <div className="flex justify-between items-center mb-2">
                        <span className="font-semibold text-white/90">{scenario}</span>
                        <span className="text-primary font-bold">{data.avg_profit?.toFixed(0)} EGP</span>
                      </div>
                      <div className="flex justify-between text-sm text-white/60">
                        <span>Service A: {(data.service_level_a * 100).toFixed(1)}%</span>
                        <span>Waste A: {data.waste_pct_a?.toFixed(1)}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Mayer's Executive Insights */}
            <div className="glass-panel p-6 bg-gradient-to-br from-indigo-900/40 to-slate-900/80 border-t border-t-accent/50 relative overflow-hidden group">
              <div className="absolute inset-0 bg-gradient-to-r from-primary/0 via-primary/10 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000" />
              <h3 className="text-xl font-bold mb-6 text-white flex items-center gap-2">
                <span className="text-accent">&#11088;</span>
                Executive Insights
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-black/30 p-4 rounded-lg border border-white/10">
                  <h4 className="text-sm text-white/50 mb-2">Daily Costs Breakdown (EGP)</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-white/80">Lost Sales Cost:</span>
                      <span className="text-warning font-bold"><AnimatedCounter value={simData?.kpis?.lost_sales_cost ?? 0} suffix=" EGP" decimals={0} /></span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-white/80">Waste Cost:</span>
                      <span className="text-red-400 font-bold"><AnimatedCounter value={simData?.kpis?.waste_cost ?? 0} suffix=" EGP" decimals={0} /></span>
                    </div>
                  </div>
                </div>
                <div className="space-y-3">
                  {simData?.insights?.map((insight, idx) => (
                    <div key={idx} className="bg-primary/10 border-l-4 border-primary p-3 rounded-r-lg text-sm text-white/90 leading-relaxed">
                      {insight}
                    </div>
                  )) || <div className="text-white/40">Analysing...</div>}
                </div>
              </div>
            </div>
          </motion.div>
        ) : (
          <motion.div key="log" variants={tab} initial="hidden" animate="show" exit="exit" transition={{ duration: 0.25 }} className="glass-panel p-6">
            <h3 className="text-lg font-bold mb-4 text-white flex items-center justify-between">
              <div className="flex items-center gap-2"><List className="text-secondary" size={20} /> Simulation Table</div>
              <div className="flex items-center gap-2 text-sm">
                <button disabled={logPage === 1} onClick={() => setLogPage(p => p - 1)} className="px-3 py-1 bg-white/10 rounded disabled:opacity-30">Prev</button>
                <span className="text-white/60">Page {logPage} of {totalPages}</span>
                <button disabled={logPage >= totalPages} onClick={() => setLogPage(p => p + 1)} className="px-3 py-1 bg-white/10 rounded disabled:opacity-30">Next</button>
              </div>
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-white/50 uppercase bg-black/20">
                  <tr>
                    <th className="px-4 py-3">Day</th>
                    <th className="px-4 py-3">Demand A</th>
                    <th className="px-4 py-3">Sales A</th>
                    <th className="px-4 py-3">Lost A</th>
                    <th className="px-4 py-3">Inv End A</th>
                    <th className="px-4 py-3">Profit A (EGP)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {paginatedLogs.map((row) => (
                    <tr key={row.day} className="hover:bg-white/5 transition-colors">
                      <td className="px-4 py-2 font-medium text-white/80">{row.day}</td>
                      <td className="px-4 py-2 text-white/70">{row.demand_a}</td>
                      <td className="px-4 py-2 text-success/90">{row.sales_a}</td>
                      <td className="px-4 py-2 text-warning/90">{row.lost_a}</td>
                      <td className="px-4 py-2 text-white/70">{row.inv_end_a}</td>
                      <td className="px-4 py-2 font-semibold text-primary">{row.profit_a?.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {(!simData || simData.timeline.length === 0) && (
                <div className="text-center py-10 text-white/40">No simulation data available</div>
              )}
            </div>
          </motion.div>
        )}
        </AnimatePresence>
          </>
        )}
        </motion.div>
      </motion.div>
    </div>
  );
}
