import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import warnings
warnings.filterwarnings('ignore')

# ── Plotly for the interactive dashboard ──────────────────────────────────
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False
    print("Plotly not installed — dashboard will use matplotlib fallback.")

# ── Reproducibility ───────────────────────────────────────────────────────
GLOBAL_SEED = 42
np.random.seed(GLOBAL_SEED)

# ── Matplotlib style ──────────────────────────────────────────────────────
plt.rcParams.update({
    'figure.facecolor': 'white',
    'axes.facecolor' : '#f8f9fa',
    'axes.grid'      : True,
    'grid.alpha'     : 0.4,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'font.size'      : 11,
})

print("✅ All imports successful.")
print(f"   NumPy  : {np.__version__}")
print(f"   Pandas : {pd.__version__}")
