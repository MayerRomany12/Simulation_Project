# Pharmacy Inventory Simulation & Optimization System
## Technical Documentation — Part 2: Visuals, GUI Manual & Insights

---

# Section 3: Visual Analytics — How to Read the Charts

## 3.1 Inventory Timeline (Area Chart — Live Trace)

**Location:** Top-left panel of the Charts tab.
**Chart Type:** `AreaChart` (Recharts) with `stepAfter` interpolation.
**Data:** `inv_end_a` (cyan/blue) and `inv_end_b` (pink) — end-of-day on-hand inventory for Products A and B.

### How to Read It

The chart produces a characteristic **sawtooth (zigzag) pattern** that is the hallmark of an (R, Q) inventory system. Understanding each feature:

#### The Peaks — Order Arrivals
A **sudden vertical jump** (step up) in the chart marks the arrival of a replenishment order. Because the `stepAfter` interpolation is used, the chart displays inventory as a horizontal line until the step event occurs.

- The peak height = prior inventory level + $Q$ (order quantity)
- Peaks recur at irregular intervals (not fixed — because the (R, Q) policy triggers on the inventory position crossing $R$, not on a fixed schedule)
- **Two peaks close together** on a product's line indicate back-to-back orders — a potential sign that $Q$ is undersized relative to demand

#### The Downward Slopes — Daily Consumption
The gradual **decline** between peaks represents daily demand consumption. The steepness of the slope indicates the **average daily demand rate**:

- Steep slope → high $\mu$
- Gentle slope → low $\mu$
- A **curved** or irregular decline (vs. a straight line) indicates **demand variability** ($\sigma > 0$)

#### The Troughs — Stockouts & Low Inventory
When inventory reaches **zero or near-zero**, that day experienced a **stockout**. In the chart, the line touches or approaches the x-axis before a replenishment step.

- The **depth** of the trough reveals how close to a stockout the system reached
- If the line consistently rests near zero for multiple consecutive days, the **Reorder Point $R$ is too low** or the **Lead Time $L$ is too long**

#### The Lead Time Gap
Between placing an order (when IP drops below $R$) and receiving it (after $L$ days), inventory continues to be consumed. This **gap between the trigger and the jump** is the Lead Time visual signature. A longer Lead Time ($L$) means the inventory can fall much lower before the jump occurs — the trough will be deeper.

**Practical Guidance:**
- If troughs frequently touch zero → Increase $R$ or $Q$
- If peaks are very high and troughs are still far from zero → $Q$ is too large; decrease it to reduce expiry risk
- Use the **Live Trace** feature (described in Section 4.2) to watch this pattern unfold day by day

---

## 3.2 Profit vs. Order Quantity (Bar Chart)

**Location:** Top-right panel of the Charts tab.
**Chart Type:** `BarChart` (Recharts) with bars colored in indigo/purple.
**Data Source:** `/profit-vs-q` endpoint — runs the baseline Newsvendor simulation for each $Q$ in the range $[\mu_A - 30,\; \mu_A + 40]$ in steps of 5.

### How to Read It

#### Finding the "Sweet Spot" — The Optimal Q
The bar chart displays **average simulated profit** ($\bar{\Pi}$) on the Y-axis and order quantity $Q$ on the X-axis. The chart reveals the **concave profit curve** predicted by the Newsvendor model:

- **Left side (low Q):** Profits are low because frequent stockouts ($\pi \times \text{lost\_sales}$) dominate
- **Peak bar (optimal Q\*):** The bar with the **tallest height** is the empirical $Q^*$ — the quantity that maximizes expected profit
- **Right side (high Q):** Profits decline as ordering more than demand leads to excess expiry/salvage losses

#### Interpreting Individual Bars
Hovering over a bar shows the exact `sim_profit` value at that $Q$. Compare this to the `analytical_profit` returned in the API response to verify model convergence (the % difference should be < 2% at 10,000 replications).

#### The Flat Region (Profit Plateau)
Near the peak, several adjacent bars may be nearly equal in height. This **profit plateau** is important for operations:

- Choosing any $Q$ in the plateau is nearly optimal
- It gives the manager flexibility to select a $Q$ that also fits practical considerations (supplier MOQ, storage space)
- A **narrow peak** indicates the profit is highly sensitive to $Q$ — small deviations cause significant losses
- A **wide plateau** indicates robustness — you have more freedom in setting $Q$

**Practical Guidance:**
- Read off the peak bar's $Q$ value → set `Q_a` to this value in the sidebar
- If the current `Q_a` is to the left of the peak → increase it to capture lost revenue
- If to the right → decrease it to reduce waste costs

---

## 3.3 Sensitivity Heatmap — R vs. Q (2D Grid)

**Location:** Bottom-left panel of the Charts tab.
**Chart Type:** Custom CSS Grid heatmap (`Heatmap` component in `Dashboard.jsx`).
**Data Source:** `/sensitivity-rq` endpoint — runs the full multi-period simulation for every combination of $R$ and $Q$ in a ±20 unit window around the user's current values (step = 5).

### How to Read the Color Gradient

The heatmap uses a **linear color interpolation** from the minimum to the maximum profit in the grid:

$$\text{color}(v) = \text{RGB}\!\left(56 + r \cdot 188,\; 189 - r \cdot 75,\; 248 - r \cdot 66\right), \quad r = \frac{v - \Pi_{\min}}{\Pi_{\max} - \Pi_{\min}}$$

| Color | Meaning |
|---|---|
| **Deep Sky Blue** (low ratio) | Low profit — poor $(R, Q)$ combination |
| **Mid-Cyan** | Moderate profit |
| **Coral/Salmon** (high ratio) | High profit — near-optimal $(R, Q)$ combination |

The **Rows** represent values of $R$ (Reorder Point) and the **Columns** represent values of $Q$ (Order Quantity). The cell label "R \ Q" in the top-left corner confirms this axis convention.

### Reading the Optimal Region

#### Narrow vs. Wide Optimal Region
- **Narrow bright region** (few coral cells surrounded by blue): The profit function is highly peaked. The system is very sensitive to policy parameters — small deviations in $R$ or $Q$ cause significant profit drops. This calls for careful parameter tuning and tighter operational controls.
- **Wide bright region** (large coral area): The profit function is flat and robust. Many $(R, Q)$ combinations yield similar profits — the manager has significant flexibility without material financial consequence.

#### Diagonal Patterns
- A **diagonal band** of high-profit cells running from bottom-left to top-right indicates that $Q$ and $R$ are **substitutable** to some degree — you can compensate for a smaller $Q$ by raising $R$ (and vice versa).
- A **vertical stripe** of high-profit cells means profit is primarily sensitive to $Q$, and $R$ has little marginal effect in this range.
- A **horizontal stripe** means the opposite — $R$ dominates.

#### Hover Tooltip
Hovering over any cell displays: `R=230, Q=200 | Profit=842.50` — allowing precise identification of the optimal cell.

**Practical Guidance:**
- Identify the brightest (coral) cell and read its $R$ and $Q$ coordinates
- Update the sidebar with these values and click **Run Simulation** to confirm the improvement

---

## 3.4 Stress Test Comparison Panel

**Location:** Bottom-right panel of the Charts tab.
**Chart Type:** Styled card list (three cards: Normal, Weekend-Heavy, Epidemic).
**Data Source:** `/stress-test` endpoint.

### Three Scenarios Explained

| Scenario | Parameters Changed | Business Context |
|---|---|---|
| **Normal** | Base parameters, `weekend_mult=1.0` | Standard operating conditions |
| **Weekend-Heavy** | `weekend_mult=1.3` | 30% demand surge on Sat/Sun (e.g., flu season, holidays) |
| **Epidemic** | `mu_a = mu_b = 150`, `clip_high = 450` | Demand 2.5× baseline (outbreak, pandemic-like surge) |

### Reading the Stress Test Cards
Each card shows:
- **Scenario name** (left) and **Average Daily Profit** (right, in EGP)
- **Service Level A** — how well Product A meets demand under the scenario
- **Waste A%** — percentage of sales lost to expiry

**Key Comparisons to Make:**
1. **Normal → Weekend-Heavy profit change**: If profit *increases*, the higher volume is profitable and the inventory can handle weekend surges. If it *decreases*, stockouts are eating the gains.
2. **Weekend-Heavy → Epidemic**: A severe service level drop (e.g., 96% → 55%) signals the current $(R, Q)$ policy cannot handle demand surges. The Executive Insights panel will flag this automatically.
3. **Consistent high Waste%**: Across all scenarios, a high waste percentage indicates $Q$ is consistently oversized relative to actual demand.

---

# Section 4: Graphical User Interface (GUI) User Manual

## 4.1 Sidebar — Controller Parameters

The left sidebar is the **control panel** for the simulation. All parameters are live-editable. Changes take effect only when you click **Run Simulation** — no auto-refresh occurs to avoid excessive API calls.

---

### 4.1.1 Simulation Settings

#### Simulation Horizon (Days) — `n_days`
- **Range:** 100 – 30,000 days
- **Default:** 365 days
- **Purpose:** Sets the measurement period length after the 90-day warm-up. Longer horizons produce more statistically stable KPIs (lower CI width) but take more computation time.
- **Practical Rule:** Use 365 for standard annual planning. Use 3,000–10,000 for high-precision sensitivity studies.

---

### 4.1.2 Demand Parameters (Products A & B)

#### Mean Daily Demand — `mu_a`, `mu_b`
- **What it means:** The average number of units customers request per day for each product.
- **How to estimate:** Compute the arithmetic mean of actual historical daily sales records (not orders — sales).
- **Effect:** Drives the entire scale of the system. A higher $\mu$ requires proportionally larger $Q$ and $R$ to maintain the same service level.

#### Standard Deviation — `sigma_a`, `sigma_b`
- **What it means:** The day-to-day variability in demand. A pharmacy in a tourist area may have $\sigma/\mu \approx 0.4$ (high CV), while a hospital pharmacy may have $\sigma/\mu \approx 0.1$ (very stable demand).
- **Effect:** Higher $\sigma$ directly increases required safety stock: $SS = z_\alpha \cdot \sigma\sqrt{L}$.
- **Practical tip:** Compute from at least 6 months of historical daily sales data.

---

### 4.1.3 Inventory Policy — Products A & B

#### Order Quantity — `Q_a`, `Q_b`
- **What it means:** The number of units ordered each time a replenishment is triggered.
- **How to set optimally:** Click **Run Simulation**, navigate to the "Profit vs. Q" chart, and read the peak bar's $Q$ value. Alternatively, use the Newsvendor formula: $Q^* \approx \mu + \sigma\Phi^{-1}(\text{critical ratio})$.
- **Warning:** Setting $Q$ much larger than $\mu \times K$ (mean demand × shelf life) will guarantee high expiry waste.

#### Reorder Point — `R_a`, `R_b`
- **What it means:** The inventory position level that triggers a new order. Think of it as the "alarm level" — when stock (including pipeline) drops to $R$, the system places an order.
- **How to set optimally:** Use the **Auto-Suggest Reorder Point** feature described below.

---

### 4.1.4 Auto-Suggest Reorder Point

This is the most powerful tool in the sidebar for practitioners. Located below the Policy inputs.

**Step-by-step usage:**
1. Enter your **Target Service Level** in the decimal input (e.g., `0.95` for 95%)
2. Click **"Suggest R"** button
3. The system calls `/suggest-r` with your current $\mu_A$, $\sigma_A$, and `lead_time`
4. The computed $R$ is automatically populated into the `R_a` field

**Behind the scenes — the formula used:**
$$R = \mu_A \cdot L + \Phi^{-1}(\alpha) \cdot \sigma_A \cdot \sqrt{L}$$

The API response also provides `mu_L`, `sigma_L`, `z`, and `safety_stock` for full transparency.

**Common service level targets:**
| Target $\alpha$ | z-score | Use Case |
|---|---|---|
| 90% | 1.282 | Low-cost, non-critical items |
| 95% | 1.645 | Standard pharmacy operations (default) |
| 99% | 2.326 | Critical life-saving medications |
| 99.9% | 3.090 | ICU/emergency medications |

---

### 4.1.5 Supply & Constraints

#### Lead Time (Days) — `lead_time`
- **What it means:** The number of calendar days between placing an order with the supplier and receiving it at the pharmacy.
- **How to measure:** Track your supplier's average delivery time over the past 6 months, including weekends.
- **Critical effect:** Lead Time is the **single most impactful parameter on safety stock**. Doubling $L$ from 3 to 6 days increases $\sigma_L$ by $\sqrt{2} \approx 41\%$, requiring substantially more buffer stock.
- **What "Lead Time = 0" means:** Immediate replenishment (no transit delay). Useful only for academic comparison; unrealistic in practice.

#### Expiry Limit (Days) — `expiry_k`
- **What it means:** The shelf life of the medication in days. Units remaining in stock for ≥ `expiry_k` days are automatically removed at the start of the next day and charged the `disposal_cost`.
- **Implementation detail:** The engine uses **FIFO (First-In, First-Out)** — oldest units are sold first and expire first, exactly reflecting real pharmacy dispensing practice.
- **Practical guidance:** Refrigerated products (e.g., insulin) may have $K = 7–14$ days once opened; OTC tablets may have $K = 730+$ days. For simulation purposes, $K = 30$ represents a typical opened multipack or short-dated product.

---

### 4.1.6 Economics (EGP)

#### Selling Price — `p`
- **What it means:** The retail price charged per unit to the customer (EGP/unit).
- **Effect:** Higher $p$ increases per-unit revenue and raises the critical ratio, pushing $Q^*$ upward.

#### Unit Cost — `c`
- **What it means:** The wholesale purchase price per unit paid to the supplier (EGP/unit).
- **Effect:** Higher $c$ reduces the profit margin and lowers the critical ratio, pushing $Q^*$ downward.
- **Gross Margin = `p - c`** — this is the fundamental profitability lever.

---

### 4.1.7 Running the Simulation
Click the **"Run Simulation"** button (with the activity icon). During execution:
- The button shows a spinning `RefreshCw` icon and the text "Running..."
- All four API calls execute in parallel
- Upon completion, all charts, KPI cards, and insights update simultaneously with animated transitions

---

## 4.2 Live Simulation Trace

The **Live Trace** feature replays the simulation timeline as an animation, allowing you to observe the inventory dynamics day by day in real time.

### Controls (Top action bar, Charts tab only)

#### Starting a Trace
1. Ensure a simulation has been run (charts are populated)
2. Click **"▶ Live Trace"** button
3. The `traceDay` counter resets to 0 and `isTracing` is set to `true`
4. The Inventory Timeline chart rebuilds itself by displaying an incrementally growing data slice: `simData.timeline.slice(0, traceDay)`

#### The Animation Mechanism
A `setInterval` timer fires every `traceSpeed` milliseconds (default: 50ms). On each tick:
- `traceDay` increments by 1
- The chart re-renders showing one additional day's data point
- The Transaction Log automatically paginates to follow the current day

At `traceSpeed = 50ms`, a 365-day simulation completes the full animation in ~18 seconds.

#### Adjusting Speed
The **speed slider** (range: 10ms – 200ms per tick) is displayed next to the trace controls:
- **10ms**: Very fast trace — full year in ~3.6 seconds (good for spotting overall patterns)
- **50ms**: Default — comfortable viewing speed for detailed analysis
- **200ms**: Slow trace — 365 days takes ~73 seconds (use for step-by-step examination of individual days)

#### Stopping a Trace
Click **"■ Stop"** (displayed in red when tracing is active). This:
- Clears the `setInterval` timer (prevents memory leaks)
- Automatically switches the active tab to **"Transaction Log"** so you can immediately examine the data at the stopped day

#### Why Use Live Trace?
- **Identify the exact day** a stockout occurs (the chart line touches zero)
- **Watch reorder cycles** in real time — observe the sawtooth pattern being drawn
- **Present simulation results** to non-technical stakeholders in a visually engaging way
- **Validate model behavior** against intuition — ensure orders arrive after the correct lead time

---

## 4.3 Transaction Log

**Access:** Click the **"Transaction Log"** tab button in the top action bar.

The Transaction Log is a **paginated audit table** showing every day's raw simulation data for Product A. It contains 50 rows per page across however many pages are needed for the total simulation horizon.

### Column Definitions

| Column | Variable | Units | Description |
|---|---|---|---|
| **Day** | `row.day` | Day # | Sequential day number in the measurement period (1 to N, warm-up excluded) |
| **Demand A** | `row.demand_a` | units | Total demand received for Product A on this day (realized from Normal distribution) |
| **Sales A** | `row.sales_a` | units | Actual units of Product A sold (≤ Demand; limited by available inventory) |
| **Lost A** | `row.lost_a` | units | Unmet demand for Product A after substitution (= Demand - Sales - sub\_recovered). A non-zero value = stockout |
| **Inv End A** | `row.inv_end_a` | units | On-hand inventory at **end of day** (after sales, before next day's ordering) |
| **Profit A (EGP)** | `row.profit_a` | EGP | Daily profit contribution from Product A: $p \cdot \text{sales} - c \cdot \text{order} - \pi \cdot \text{lost} - d_c \cdot \text{expired}$ |

### How to Use It for Auditing

**Finding stockout days:**
Sort mentally by `Lost A > 0`. A non-zero value in the "Lost A" column indicates a stockout event. Cross-reference the "Inv End A" column — it should be 0 or near 0 on that day.

**Diagnosing expiry events:**
The log does not show `expired_a` directly, but Profit A will show a **sudden dip** on days when expiry occurs (the $d_c$ disposal penalty fires). Cross-reference with the Inventory Timeline chart to see the inventory level drop.

**Validating order cycles:**
When `Inv End A` is significantly lower than on the previous day and then jumps on the next, an order arrived. Count the days between the sudden drop to near-$R$ and the jump to confirm the lead time.

**Pagination during Live Trace:**
When a trace is running, the log automatically advances to the page containing the current trace day, so the live data is always visible without manual navigation.

---

## 4.4 Mayer's Executive Insights Engine

**Location:** Bottom panel of the Charts tab (gold star ⭐ icon).

The Insights Engine is a **rule-based heuristic AI** implemented in `generate_insights()` in `backend/main.py`. It evaluates five independent business rules against the live KPI data and generates plain-English advisory messages.

### The Five Business Rules

#### Rule 1: Supply Chain / Lead Time Insight
**Trigger:** Always fires (informational, not conditional).
**Formula:**
$$\text{Capital}_{\text{in transit}} = L \times (\mu_A + \mu_B) \times c$$

**Interpretation:** This is the EGP value of inventory that is "in the air" — ordered and paid for but not yet available to sell. High lead times with high unit costs tie up significant working capital, reducing liquidity and ROI.

**Action:** Negotiate faster delivery with suppliers, or switch to local suppliers with shorter lead times to reduce this capital requirement.

---

#### Rule 2: Safety Stock Alert
**Trigger:** Service Level A OR B < 90%
**Message:** "Safety Stock Alert: Current buffer is weak. The pharmacy loses an average of X customers daily due to stockouts. Consider raising the Reorder Point."

**Interpretation:** The current $(R, Q)$ policy is not providing adequate inventory protection. Daily stockouts are occurring at a rate that affects more than 10% of operating days.

**Action:** Use the **Auto-Suggest Reorder Point** tool with $\alpha = 0.95$ to immediately calculate and apply a stronger $R$.

---

#### Rule 3: Profit Volatility (CV Check)
**Trigger:** Coefficient of Variation (CV) of daily profit > 50% → High Volatility warning; ≤ 50% → Financial Stability confirmation.
$$CV = \frac{\hat{\sigma}_\Pi}{\bar{\Pi}} \times 100\%$$

**Interpretation:** A CV > 50% means daily profit swings wildly — some days may be deeply unprofitable while others are highly profitable. This makes cash flow planning difficult.

**Action (if high CV):** Increase cash reserves. Consider adding a second supplier to reduce demand-side supply shocks. Evaluate demand smoothing strategies (promotions, pre-orders).

---

#### Rule 4: Lost Sales vs. Waste Cost Trade-off
**Trigger (Underage):** Lost sales cost > 2× waste cost
$$\text{Lost Sales Cost} = (\bar{\text{lost}}_A + \bar{\text{lost}}_B) \times (p - c)$$

**Message:** "Opportunity Cost Warning: Lost sales cost (X EGP) is significantly higher than waste cost (Y EGP). Increasing Order Quantity (Q) is highly recommended."

**Trigger (Overage):** Waste cost > 2× lost sales cost
$$\text{Waste Cost} = (\bar{\text{expired}}_A + \bar{\text{expired}}_B) \times c$$

**Message:** "Waste Management Alert: Expiry waste cost (Y EGP) is disproportionately high. Please review and decrease Order Quantity (Q)."

**Interpretation:** This is the core Newsvendor trade-off visualized as a business decision. The 2× threshold provides a margin of error before triggering a recommendation, avoiding noise from small imbalances.

---

#### Rule 5: Epidemic Vulnerability Alert
**Trigger:** Stress Test is included in the request AND Service Level A under the Epidemic scenario < 80%.

**Message:** "Critical Vulnerability: In an Epidemic scenario, service level drops to X%. An immediate upward adjustment of Reorder Point (R) is required for crisis readiness."

**Interpretation:** The current policy has insufficient buffer for a 2.5× demand surge. In a real outbreak scenario (flu epidemic, disease outbreak), the pharmacy would fail to serve 20%+ of customer days.

**Action:** Maintain a **crisis buffer** — a separately earmarked safety stock of 2–4 weeks of epidemic-level demand that is only activated during declared health emergencies. Document the trigger conditions and reorder levels in the pharmacy's Emergency Operations Procedure (EOP).

---

### Daily Costs Breakdown Panel (Left side of Insights section)

Two line items are displayed with animated counters:

| Metric | Formula | Interpretation |
|---|---|---|
| **Lost Sales Cost** | $(\bar{\text{lost}}_A + \bar{\text{lost}}_B) \times (p - c)$ | Daily gross margin lost to stockouts — revenue that should have been captured |
| **Waste Cost** | $(\bar{\text{expired}}_A + \bar{\text{expired}}_B) \times c$ | Daily cost of purchasing units that were never sold and were disposed of |

**The goal is to minimize both simultaneously.** If both are high, the policy is fundamentally misaligned with demand. If they are roughly equal, you are near the optimal trade-off point.

---

## 4.5 PDF Export

Click the **Download (↓) icon** in the top-right of the sidebar to export the current dashboard view as a PDF report.

**Technical process:**
1. `html2canvas` renders the dashboard `<div>` to a canvas at 1.5× scale for crisp resolution
2. `jsPDF` converts the canvas PNG to a PDF page sized to A4
3. The file is downloaded as `Pharmacy_Simulation_Report.pdf`

**Best practice:** Stop any running Live Trace before exporting, as the export function does this automatically, but manually stopping ensures the chart is in its final, desired state before capture.

---

## 4.6 KPI Summary Cards (Top of Dashboard)

Four animated KPI cards update immediately after each simulation run:

| Card | Metric | Color | Meaning |
|---|---|---|---|
| **Avg Daily Profit** | `avg_profit` (EGP) | Blue (Primary) | Mean daily combined profit across the full simulation horizon |
| **Service Level (A)** | `service_level_a × 100%` | Green (Success) | % of days with zero stockout for Product A |
| **Waste Pct (A)** | `waste_pct_a%` | Amber (Warning) | % of Product A sales units that expired before being sold |
| **Avg Inventory (A)** | `avg_inv_a` (units) | Purple (Secondary) | Mean end-of-day on-hand stock for Product A |

All values animate from 0 to their final value over 1.4 seconds using Framer Motion's `animate()` function with `easeOut` easing. This animation is triggered on every data update, making changes in KPIs immediately perceptible.

---

*End of Technical Documentation — Pharmacy Inventory Simulation & Optimization System*
*Generated: 2026-05-06 | For internal use by the development and operations teams.*
