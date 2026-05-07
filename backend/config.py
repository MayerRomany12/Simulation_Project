"""
config.py — Unified parameter registry for the pharmacy inventory simulation.

All global constants live here.  Every other module imports from this file.
Never hard-code a parameter elsewhere; always reference the name from config.

Usage
-----
    from config import GLOBAL_SEED, P, C, S, PI, MU, SIGMA, BASE_PARAMS

Sections
--------
1.  Random-number seeds
2.  Single-product Newsvendor parameters   (used in all_code.py / main.py)
3.  Multi-product simulation parameters    (used in simulation.py / main.py)
4.  Composite dict helpers                 (convenience for callers)
"""

# ──────────────────────────────────────────────────────────────────────────────
# 1.  Reproducibility
# ──────────────────────────────────────────────────────────────────────────────

GLOBAL_SEED: int = 42          # master seed; spawn children with SeedSequence

# ──────────────────────────────────────────────────────────────────────────────
# 2.  Single-product Newsvendor  (all_code.py analytical model)
# ──────────────────────────────────────────────────────────────────────────────

P:     float = 25.0    # retail selling price per unit (EGP)
C:     float = 10.0    # wholesale / ordering cost per unit (EGP)
S:     float =  2.0    # salvage value of each unsold unit (EGP)
PI:    float =  3.0    # goodwill / shortage penalty per unit of unmet demand (EGP)

MU:    float = 60.0    # mean daily demand (units)
SIGMA: float = 15.0    # std dev of daily demand (units)

N_DAYS:   int = 10_000                         # Monte Carlo replications per Q
Q_VALUES: list = list(range(30, 96, 5))        # candidate order quantities [30…95]

# Empirical discrete demand PMF
DEMAND_VALUES = [30, 40, 50, 60, 70, 80, 90]
DEMAND_PROBS  = [0.05, 0.10, 0.20, 0.30, 0.20, 0.10, 0.05]

# ──────────────────────────────────────────────────────────────────────────────
# 3.  Multi-product simulation  (simulation.py / inventory.py)
# ──────────────────────────────────────────────────────────────────────────────

# Product A  (Ibuprofen)
MU_A:    float = 60.0
SIGMA_A: float = 15.0

# Product B  (Paracetamol)
MU_B:    float = 55.0
SIGMA_B: float = 12.0

# Shared demand model bounds
CLIP_LOW:  int = 5
CLIP_HIGH: int = 500

# Seasonality
WEEKEND_MULT: float = 1.0    # 1.0 = no weekend effect; 1.2–1.3 = weekend boost

# Inventory policy  (R, Q) defaults
Q_A: int = 200    # order quantity — product A
Q_B: int = 180    # order quantity — product B
R_A: int = 230    # reorder point  — product A  (≈ μ_L + safety stock)
R_B: int = 200    # reorder point  — product B

# Supply chain
LEAD_TIME: int = 3     # days from order placement to receipt

# Perishability
EXPIRY_K: int = 30     # shelf life in days; units expire on day age >= EXPIRY_K

# Cross-substitution
SUB_RATE: float = 0.15    # fraction of stockouts that switch to the other product

# Cost extras
DISPOSAL_COST: float = 1.0    # cost per expired unit (EGP)
HOLDING_COST:  float = 0.0    # per-unit per-day holding cost (0 = no holding cost)

# Simulation horizon
SIM_DAYS:    int = 365    # measurement period (after warm-up)
WARMUP_DAYS: int = 90     # warm-up period discarded from statistics

# ──────────────────────────────────────────────────────────────────────────────
# 4.  Composite dict helpers
# ──────────────────────────────────────────────────────────────────────────────

BASE_PARAMS: dict = dict(
    # Demand
    mu_a        = MU_A,
    sigma_a     = SIGMA_A,
    mu_b        = MU_B,
    sigma_b     = SIGMA_B,
    clip_low    = CLIP_LOW,
    clip_high   = CLIP_HIGH,
    weekend_mult= WEEKEND_MULT,
    # Economics
    p           = P,
    c           = C,
    s           = S,
    pi          = PI,
    disposal_cost = DISPOSAL_COST,
    holding_cost  = HOLDING_COST,
    # Inventory
    lead_time   = LEAD_TIME,
    expiry_k    = EXPIRY_K,
    sub_rate    = SUB_RATE,
)
