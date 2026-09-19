"""Project-wide constants and file locations.

Everything that used to be repeated (or hardcoded as an absolute path) across the
scripts lives here, so the sweep grid, the thermal limit and the output files are
defined exactly once.
"""

from pathlib import Path

# --- Locations (relative to the repository root, so the project runs from any checkout) ---
ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "models"
RESULTS_DIR = ROOT / "results"

SWEEP_CSV = RESULTS_DIR / "sweep_results.csv"
OPTIMIZATION_CSV = RESULTS_DIR / "optimization_results.csv"
TRADEOFF_PLOT = RESULTS_DIR / "tradeoff_plot.png"
PUMP_POWER_PLOT = RESULTS_DIR / "pump_power_plot.png"

# --- Simulink model ---
MODEL_NAME = "server_cooling_loop_v2_working"
PUMP_BLOCK = "mech_input"  # constant block that sets the pump shaft speed [rad/s]
HEAT_BLOCK = "heat_flow"  # step block that sets the CPU heat load [W]
SIM_STOP_TIME_S = 400  # long enough for the CPU temperature to reach steady state

# --- Physics / limits ---
RHO_WATER_KG_M3 = 1000.0
THERMAL_LIMIT_K = 368.15  # 95 degC CPU temperature limit

# --- Sweep grid ---
# The centrifugal pump produces zero or negative pressure rise below ~33 rad/s (outside
# its valid operating curve), so the sweep starts at 40 rad/s with a safety margin.
PUMP_SPEEDS_RAD_S = (40, 60, 80, 100, 125, 150, 175, 200)
HEAT_LOADS_W = (40, 65, 90, 115, 150, 200, 250, 300, 350, 400, 450, 500)
