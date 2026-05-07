# Pharmacy Inventory Simulation & Optimization System
## Comprehensive Technical Documentation & User Manual

> **Version:** 2.0 | **Author:** Mayer Romany | **Stack:** FastAPI + React/Vite + NumPy/SciPy

---

# Section 1: System Architecture & Data Flow

## 1.1 Architectural Overview

The system follows a **strict decoupled (client-server) architecture** with two independent deployment units:

| Layer | Technology | Responsibility |
|---|---|---|
| **Backend** | Python 3.11 + FastAPI + Uvicorn | Monte Carlo engine, math, REST API |
| **Frontend** | React 18 + Vite + Recharts + Framer Motion | UI, parameter control, visualization |
| **Transport** | HTTPS/JSON (Axios) | Stateless request/response |
| **Deployment** | Vercel (both layers) | Serverless hosting |

This separation means the Python simulation engine can be updated, scaled, or replaced independently of the UI, and vice versa.

---

## 1.2 The Complete Simulation Lifecycle

Below is the precise, step-by-step lifecycle of a single simulation run triggered by the **"Run Simulation"** button in the UI.

### Step 1 — User Interaction (Frontend: `Dashboard.jsx`)
The user adjusts parameters in the sidebar (e.g., changes `Q_a = 250`) and clicks **"Run Simulation"**. This triggers the `handleSubmit()` function, which calls `fetchAll()`:

```javascript
// Dashboard.jsx — fetchAll()
const [simRes, stressRes, qRes, rqRes] = await Promise.all([
  runSimulation(params),      // POST /run-simulation
  runStressTest(params),      // POST /stress-test
  runProfitVsQ(params),       // POST /profit-vs-q
  runSensitivityRQ(params)    // POST /sensitivity-rq
]);
```

All **four API calls are fired in parallel** using `Promise.all()`, minimizing total wait time.

### Step 2 — HTTP Transmission (Frontend: `api.js`)
The `api.js` module wraps Axios and sends a serialized JSON payload to the Vercel-hosted backend:

```
POST https://simulation-api-seven.vercel.app/run-simulation
Content-Type: application/json
Body: { "mu_a": 60, "sigma_a": 15, "Q_a": 200, "R_a": 230, "lead_time": 3, ... }
```

### Step 3 — API Reception & Validation (Backend: `main.py`)
The FastAPI router receives the request. Pydantic's `SimulationParams` model automatically **validates and deserializes** the JSON into typed Python fields. Any missing field defaults to the value defined in `config.py`.

```python
@app.post("/run-simulation")
def api_run_simulation(req: SimulationParams):
    params = get_base_params(req)
    ss = np.random.SeedSequence(req.seed)
    rng_a, rng_b = (np.random.default_rng(c) for c in ss.spawn(2))
```

A `SeedSequence` is spawned from `req.seed` (default: 42), generating **two independent, reproducible RNG streams** — one per product — ensuring deterministic results.

### Step 4 — Demand Generation (Backend: `demand.py`)
`build_demand_series()` generates the full demand array for `n_days + warmup_days` days upfront (vectorized NumPy call, not day-by-day):

$$D_t \sim \mathcal{N}(\mu, \sigma^2), \quad D_t = \text{clip}(\text{round}(D_t),\, D_{\min},\, D_{\max})$$

If `weekend_mult > 1.0`, a seasonality multiplier is applied to Saturday/Sunday indices.

### Step 5 — Day-by-Day Monte Carlo Loop (Backend: `inventory.py` + `simulation.py`)
`run_multi_period_simulation()` iterates over `total_days = n_days + warmup_days`. For each day, `simulate_one_day()` executes the following **7-step protocol**:

1. **Receive** pipeline arrivals (orders placed `L` days ago)
2. **Age** all inventory buckets by +1 day
3. **Expire** all units whose age ≥ `expiry_k` (FIFO removal from left of deque)
4. **Sell** primary demand (FIFO: oldest units consumed first)
5. **Substitute** a fraction `sub_rate` of stockouts to the other product
6. **Order** decision: if Inventory Position ≤ R, place order of size Q
7. **Compute** daily profit per product

The first `warmup_days` (default: 90) rows are silently discarded to eliminate transient initialization effects.

### Step 6 — KPI Aggregation (Backend: `simulation.py` → `summarise()`)
The resulting `pd.DataFrame` (one row per measurement day) is passed to `summarise()`, which computes:
- Average and standard deviation of daily profit
- 95% CI for average profit (CLT z-interval)
- Service levels with Wilson confidence intervals
- Inventory turnover, waste percentage

### Step 7 — Insight Generation (Backend: `main.py` → `generate_insights()`)
The KPI dict is passed to the heuristic AI engine, which evaluates five business rules and generates plain-English advisory strings.

### Step 8 — JSON Response Serialization
`clean_dict()` sanitizes all NumPy types (`np.int64`, `np.float32`, `NaN`, `Inf`) into native Python/JSON-safe types. The final response payload has three keys:

```json
{
  "kpis": { "avg_profit": 842.5, "service_level_a": 0.963, ... },
  "timeline": [ { "day": 1, "demand_a": 58, "inv_end_a": 142, ... }, ... ],
  "insights": [ "Supply Chain Insight: ...", "Financial Stability: ..." ]
}
```

### Step 9 — UI State Update & Rendering (Frontend: `Dashboard.jsx`)
React calls `setSimData(simRes)` which triggers a re-render. The timeline data drives the `AreaChart`, KPI cards animate via Framer Motion's `AnimatedCounter`, and insights are rendered as styled cards.

---

## 1.3 Directory Tree & Module Purpose

```
simu_updated/
├── backend/
│   ├── config.py          ← [SINGLE SOURCE OF TRUTH] All constants live here
│   ├── demand.py          ← Demand generation: Normal dist + seasonality
│   ├── inventory.py       ← FIFO engine: AgeBucketInventory, PipelineQueue, simulate_one_day()
│   ├── simulation.py      ← Orchestration: multi-period loop, KPI summarise(), stress tests
│   ├── main.py            ← FastAPI router: 6 endpoints, Pydantic validation, insights engine
│   ├── visualization.py   ← (Legacy) Matplotlib/Plotly chart generators for notebook use
│   ├── requirements.txt   ← fastapi, uvicorn, numpy, scipy, pandas, pydantic
│   └── vercel.json        ← Vercel serverless deployment configuration
│
├── frontend/
│   ├── src/
│   │   ├── api.js                    ← Axios HTTP client: 6 named API functions
│   │   ├── App.jsx                   ← Root component: mounts <Dashboard />
│   │   ├── main.jsx                  ← Vite entry point: ReactDOM.render
│   │   ├── index.css / App.css       ← Global styles: glassmorphism, mesh gradients, particles
│   │   └── components/
│   │       └── Dashboard.jsx         ← [UI CONTROLLER] All state, charts, sidebar, log table
│   ├── package.json                  ← Dependencies: react, recharts, framer-motion, lucide-react
│   └── vite.config.js                ← Vite build configuration
│
├── main.py                ← (Root-level) Orchestration runner for notebook/CLI use
└── all_code.py            ← Monolithic legacy version (reference only)
```

### Core File Responsibilities

#### `config.py` — The Single Source of Truth
Every hardcoded parameter in the system **must originate here**. No other module is allowed to define numeric constants directly. This design prevents parameter drift — if `LEAD_TIME` changes from 3 to 5, you change it once in `config.py` and all modules pick it up automatically via `from config import LEAD_TIME`.

Key sections:
- **Section 1:** `GLOBAL_SEED = 42` — master seed for full reproducibility
- **Section 2:** Newsvendor parameters (`P`, `C`, `S`, `PI`, `MU`, `SIGMA`) for analytical validation
- **Section 3:** Multi-product simulation parameters (per-product `MU_A`, `SIGMA_A`, `MU_B`, `SIGMA_B`, `LEAD_TIME`, `EXPIRY_K`, `SUB_RATE`)
- **Section 4:** `BASE_PARAMS` dict — convenience wrapper passed to API and simulation functions

#### `simulation.py` — The Monte Carlo Orchestration Layer
This module does **not** implement per-day logic directly; it delegates to `inventory.py`. Its responsibilities:
- `run_multi_period_simulation()`: The main loop over `total_days`, warm-up gating, record collection
- `summarise()`: Aggregates per-day DataFrame into KPI dictionary with CI calculations
- `run_baseline_newsvendor_sim()`: Simplified simulation for analytical model validation (no lead time, no expiry)
- `run_stress_test()`: Three-scenario runner (Normal / Weekend-Heavy / Epidemic)
- `compare_stress_scenarios()`: Welch t-tests between scenario pairs
- `compute_reorder_point()`: Derives optimal R from the Normal CDF inverse

#### `inventory.py` — The FIFO + Expiry Engine
Two core classes and one function:

- **`AgeBucketInventory`**: A `deque` of `[quantity, age_days]` pairs. Left = oldest (sold first). Supports `add()`, `age_one_day()`, `expire(max_age)`, `sell(demand)`. The `>= max_age` boundary ensures expiry fires on the **exact** shelf-life day (off-by-one corrected from original `>`).
- **`PipelineQueue`**: A circular deque of length `L+1`. Slot `[-1]` = newly placed orders; slot `[0]` = arriving today. `advance()` rotates left and returns arrived units.
- **`simulate_one_day()`**: Executes the complete 7-step daily protocol for both products simultaneously.

#### `main.py` (Backend) — The FastAPI Router
Exposes 6 REST endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/run-simulation` | POST | Full multi-period simulation + KPIs + insights |
| `/stress-test` | POST | Three-scenario stress comparison |
| `/profit-vs-q` | POST | Newsvendor profit curve across Q values |
| `/sensitivity-rq` | POST | 2D profit heatmap over R×Q grid |
| `/suggest-r` | POST | Auto-calculate optimal R from service level target |
| `/generate-insights` | POST | Standalone insights from externally supplied KPIs |

#### `Dashboard.jsx` — The UI Controller
The single React component that manages **all application state**:
- `params`: Current simulation parameters (controlled inputs)
- `simData`, `stressData`, `qData`, `rqData`: API response data
- `isTracing`, `traceDay`, `traceSpeed`: Live animation state
- `activeTab`, `logPage`: UI navigation state

All child components (`KPICard`, `AnimatedCounter`, `Heatmap`) are defined within this file as pure presentational components.

---

# Section 2: Mathematical Engine & Parameter Breakdown

## 2.1 Demand Model

Daily demand for each product follows a **truncated Normal distribution**:

$$D_t \sim \mathcal{N}(\mu, \sigma^2)$$

where the realization is discretized and clipped to hard physical bounds:

$$D_t = \text{clip}\!\left(\text{round}(D_t),\; D_{\min},\; D_{\max}\right)$$

In code: `clip_low = 20`, `clip_high = 300` (units).

**Weekend Seasonality Multiplier:**

$$D_t^{\text{adj}} = D_t \times \left[1 + (\omega - 1) \cdot \mathbf{1}_{\{t \;\text{is weekend}\}}\right]$$

where $\omega$ = `weekend_mult`. When $\omega = 1.3$, weekend demand is 30% higher than weekday demand.

---

## 2.2 Inventory Position & (R, Q) Policy

The **Inventory Position (IP)** at any point is:

$$\text{IP} = I_{\text{on-hand}} + I_{\text{pipeline}}$$

where $I_{\text{pipeline}}$ is the total quantity of all outstanding orders not yet received.

The **(R, Q) reorder policy** decision rule is:

$$\text{Order}(Q) \;\text{if}\; \text{IP} \leq R, \quad \text{otherwise order nothing}$$

This triggers at most one order per review period (daily review in this model).

---

## 2.3 Safety Stock & Reorder Point Derivation

During lead time $L$, cumulative demand $D_L$ is normally distributed:

$$D_L \sim \mathcal{N}(\mu_L,\; \sigma_L^2)$$

where:

$$\mu_L = \mu \cdot L \qquad \sigma_L = \sigma \cdot \sqrt{L}$$

To achieve a **Cycle Service Level (CSL)** of $\alpha$, the reorder point is:

$$R = \mu_L + z_\alpha \cdot \sigma_L$$

The **Safety Stock** embedded in $R$ is:

$$SS = R - \mu_L = z_\alpha \cdot \sigma_L$$

The **z-score** $z_\alpha$ is computed via the inverse CDF (percent-point function) of the standard Normal:

$$z_\alpha = \Phi^{-1}(\alpha)$$

Example with defaults ($\mu=60$, $\sigma=15$, $L=3$, $\alpha=0.95$):

$$\mu_L = 60 \times 3 = 180, \quad \sigma_L = 15\sqrt{3} \approx 25.98, \quad z_{0.95} \approx 1.645$$

$$SS = 1.645 \times 25.98 \approx 42.7, \quad R = 180 + 43 = 223$$

---

## 2.4 The Newsvendor Model — Analytical Profit Function

For a **single-period, no-lead-time** model under Normal demand, the expected profit at order quantity $Q$ is:

$$\mathbb{E}[\Pi(Q)] = p \cdot \mathbb{E}[\min(Q, D)] - c \cdot Q + s \cdot \mathbb{E}[\max(Q-D, 0)] - \pi \cdot \mathbb{E}[\max(D-Q, 0)]$$

Using the **Normal Loss Function** $\Lambda(z) = \phi(z) - z(1 - \Phi(z))$, where $z = (Q-\mu)/\sigma$:

$$\mathbb{E}[\max(D-Q, 0)] = \sigma \cdot \Lambda(z) = \sigma\phi(z) - (Q-\mu)(1-\Phi(z))$$

$$\mathbb{E}[\min(Q,D)] = Q - \mathbb{E}[\max(D-Q,0)]$$

$$\mathbb{E}[\max(Q-D,0)] = Q - \mu + \mathbb{E}[\max(D-Q,0)]$$

**Optimal Order Quantity** (Critical Ratio / Newsvendor condition):

$$Q^* = \mu + \sigma \cdot \Phi^{-1}\!\left(\frac{p - c}{p - s + \pi}\right) = \mu + \sigma \cdot z^*$$

With defaults ($p=25, c=10, s=2, \pi=3$):

$$Q^* = \mu + \sigma \cdot \Phi^{-1}\!\left(\frac{25-10}{25-2+3}\right) = \mu + \sigma \cdot \Phi^{-1}(0.577) \approx \mu + 0.194\sigma$$

---

## 2.5 Multi-Period Daily Profit Formula

In the full simulation, daily profit for **each product** (e.g., Product A) is:

$$\Pi_t^A = p \cdot \text{sold}_t^A - c \cdot \text{order}_t^A - \pi \cdot \text{lost}_t^A - d_c \cdot \text{expired}_t^A - h \cdot I_t^A$$

where:
- $p$ = unit selling price
- $c$ = unit ordering cost (charged on order placement day — accrual basis)
- $\pi$ = goodwill penalty per unit of unmet demand (lost sales)
- $d_c$ = disposal cost per expired unit
- $h$ = holding cost per unit per day (default: 0)
- $I_t^A$ = end-of-day on-hand inventory (after sales)

**Total Daily Profit:**

$$\Pi_t = \Pi_t^A + \Pi_t^B$$

**Average Daily Profit (KPI):**

$$\bar{\Pi} = \frac{1}{N} \sum_{t=1}^{N} \Pi_t$$

---

## 2.6 Substitution Logic

When Product A stockouts occur, a fraction `sub_rate` ($\rho$) of the unmet demand shifts to Product B:

$$\text{sub\_to\_B} = \text{round}(\text{lost}_A \times \rho)$$

The effective lost sales after substitution:

$$\text{total\_lost}_A = \text{lost}_A - \text{extra\_sold}_A$$

where `extra_sold_A` is the portion of `sub_to_A` that Product A's inventory could actually fill. This correctly accounts for cases where the substitute product is also out of stock.

---

## 2.7 Statistical Inference — Confidence Intervals

**95% CI for Average Daily Profit** (Central Limit Theorem z-interval):

$$\bar{\Pi} \pm 1.96 \cdot \frac{\hat{\sigma}_\Pi}{\sqrt{N}}$$

**Wilson 95% CI for Service Level proportions** (more accurate than normal approximation near 0 or 1):

$$\tilde{p} = \frac{\hat{p} + \frac{z^2}{2n}}{1 + \frac{z^2}{n}}, \quad \tilde{\sigma} = \frac{z\sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$

$$\text{CI} = \left[\tilde{p} - \tilde{\sigma},\; \tilde{p} + \tilde{\sigma}\right] \;\cap\; [0, 1]$$

where $\hat{p}$ = sample service level proportion, $n$ = number of days, $z = 1.96$.

---

## 2.8 Inventory Performance Metrics

**Service Level (Cycle):**

$$\text{SL} = P(\text{no stockout on a given day}) = \frac{\text{days with lost}=0}{N}$$

**Fill Rate (Volume):**

$$\text{FR} = 1 - \frac{\sum_{t}\text{lost}_t}{\sum_{t} D_t}$$

**Inventory Turnover:**

$$\text{Turnover} = \frac{\text{Total Sales}}{\bar{I} \times N}$$

**Waste Percentage:**

$$\text{Waste\%} = \frac{\sum_{t} \text{expired}_t}{\sum_{t} \text{sales}_t} \times 100\%$$

---

## 2.9 Parameter Dictionary

| Symbol | Parameter Name | Default | Unit | Description |
|---|---|---|---|---|
| $\mu_A$ | `mu_a` | 60 | units/day | Mean daily demand for Product A (Ibuprofen) |
| $\sigma_A$ | `sigma_a` | 15 | units/day | Std deviation of daily demand for Product A |
| $\mu_B$ | `mu_b` | 55 | units/day | Mean daily demand for Product B (Paracetamol) |
| $\sigma_B$ | `sigma_b` | 12 | units/day | Std deviation of daily demand for Product B |
| $D_{\min}$ | `clip_low` | 20 | units | Hard lower bound on any single day's demand |
| $D_{\max}$ | `clip_high` | 300 | units | Hard upper bound on any single day's demand |
| $\omega$ | `weekend_mult` | 1.0 | ratio | Weekend demand multiplier (1.0 = no effect) |
| $p$ | `p` | 25.0 | EGP/unit | Retail selling price per unit |
| $c$ | `c` | 10.0 | EGP/unit | Wholesale ordering cost per unit |
| $s$ | `s` | 2.0 | EGP/unit | Salvage value of each unsold/expired unit |
| $\pi$ | `pi` | 3.0 | EGP/unit | Goodwill penalty per unit of unmet demand |
| $d_c$ | `disposal_cost` | 1.0 | EGP/unit | Extra disposal cost per expired unit |
| $h$ | `holding_cost` | 0.0 | EGP/unit/day | Per-unit per-day inventory carrying cost |
| $Q_A$ | `Q_a` | 200 | units | Order quantity for Product A |
| $Q_B$ | `Q_b` | 180 | units | Order quantity for Product B |
| $R_A$ | `R_a` | 230 | units | Reorder point for Product A |
| $R_B$ | `R_b` | 200 | units | Reorder point for Product B |
| $L$ | `lead_time` | 3 | days | Days between order placement and receipt |
| $K$ | `expiry_k` | 30 | days | Shelf life; units expire when age ≥ K |
| $\rho$ | `sub_rate` | 0.15 | ratio | Fraction of stockouts redirected to alternate product |
| $N$ | `n_days` | 365 | days | Simulation measurement horizon |
| $N_w$ | `warmup_days` | 90 | days | Warm-up period discarded from statistics |
| — | `seed` | 42 | — | Master RNG seed for reproducibility |

---

## 2.10 Sensitivity Analysis — Real-World Parameter Impact

### Effect of Increasing $Q$ (Order Quantity)
- **Lower stockout risk**: More inventory on-hand covers demand spikes → Service Level $\uparrow$
- **Higher carrying risk**: More units age → Expiry $\uparrow$, Waste% $\uparrow$
- **Higher ordering cost**: $c \times Q$ is larger per cycle → Profit $\downarrow$ unless sales gain offsets it
- **Mathematical effect**: The profit curve $\mathbb{E}[\Pi(Q)]$ is concave; over-ordering past $Q^*$ causes profit to decline due to mounting salvage/waste losses.

### Effect of Increasing $R$ (Reorder Point)
- Triggers orders **earlier**, maintaining a larger average inventory buffer
- Reduces the probability of stockouts during lead time: $P(D_L > R)$ decreases
- Increases average on-hand inventory → Higher holding costs if $h > 0$
- **Mathematical effect**: $R$ controls safety stock directly: $SS = R - \mu_L$

### Effect of Increasing $L$ (Lead Time)
- Lead time demand variance grows: $\sigma_L = \sigma\sqrt{L}$ — a 4× increase in $L$ doubles $\sigma_L$
- Requires a **larger safety stock** to maintain the same service level
- Ties up more capital in transit: Capital$_{\text{in transit}} = L \times \mu \times c$
- **Mathematical effect**: $R_{\text{required}} = \mu L + z_\alpha \sigma\sqrt{L}$ grows super-linearly with $L$

### Effect of Increasing $K$ (Expiry / Shelf Life)
- Units can remain on shelf longer before forced disposal
- **Reduces** Waste% by giving more time to sell slow-moving stock
- At very high $K$, expiry becomes a non-binding constraint; at very low $K$ (e.g., $K=7$ for fresh products), even small $Q$ values generate high waste

### Effect of Increasing $h$ (Holding Cost)
- Directly reduces $\Pi_t^A$ by $h \times I_t^A$ each day
- Forces the optimal $Q$ to **decrease** — it becomes less economic to hold large inventories
- **Mathematical effect**: The marginal cost of ordering increases, shifting $Q^*$ downward

### Effect of Increasing $\rho$ (Substitution Rate)
- Converts previously lost sales into revenue, increasing total profit
- Reduces the effective service level penalty $\pi$ since fewer sales are truly lost
- **Diminishing returns**: Effect plateaus when the substitute product also stockouts

### Effect of Increasing $\pi$ (Shortage Penalty)
- Makes stockouts more expensive, pushing the optimal policy toward **higher $Q$** and **higher $R$**
- **Mathematical effect**: In the Newsvendor critical ratio, the denominator increases → $Q^*$ rises: $Q^* = \mu + \sigma\Phi^{-1}\!\left(\frac{p-c}{p-s+\pi}\right)$ — as $\pi \uparrow$, the ratio $\to 1$, so $z^* \to \infty$
