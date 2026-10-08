"""Project-wide constants and file locations.

Everything that used to be repeated (or hardcoded as an absolute path) across the
scripts lives here, so the sweep grid, the thermal limit and the output files are
defined exactly once.
"""

import math
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
COOLANT_SUPPLY_K = 318.15  # 45 degC coolant supply (set in the model's reservoirs)
RHO_WATER_KG_M3 = 990.2  # water at 45 degC
CP_WATER_J_KGK = 4180.0  # water at 45 degC
THERMAL_LIMIT_K = 352.15  # 79 degC, TCASE of the Intel Xeon Platinum 8480+ (350 W TDP)
PIPE_FLOW_AREA_M2 = 5e-5  # 8 mm tubing, same value as the Pipe (TL) block

# --- Pump datasheet (Laing D5 class, speed setting 5 = 4800 rpm; same table as the pump block) ---
# Electrical input power against flow at the reference speed. Other speeds follow the
# affinity laws (flow ~ speed, power ~ speed^3), with the catalogue minimum as a floor.
PUMP_REF_SPEED_RPM = 4800.0
PUMP_REF_FLOW_LPM = (0.0, 5.0, 10.0, 15.0, 20.0, 25.0)
PUMP_REF_ELECTRICAL_W = (17.0, 19.0, 20.5, 22.0, 23.0, 23.0)
PUMP_MIN_ELECTRICAL_W = 3.0  # lowest power consumption stated in the catalogue

# --- Sanity bounds for the results (sources in the README) ---
MAX_PIPE_VELOCITY_M_S = 2.1  # ASHRAE erosion limit for liquid-cooling piping
MAX_COLD_PLATE_FLOW_LPM = 3.5  # recommended flow range of the reference cold plate
COOLANT_DELTA_T_RANGE_K = (2.0, 15.0)  # OCP design range is 7.5-12 K; wider band for part load
MAX_PUMP_POWER_SHARE = 0.05  # pump electrical power / CPU heat load at the optimum

# --- Sweep grid ---
# Speed range of a PWM-controlled D5 pump (800-4800 rpm), finer at the low end where the
# thermal limit becomes active. The model's speed input is in rad/s.
PUMP_SPEEDS_RPM = (800, 1000, 1200, 1500, 1800, 2400, 3600, 4800)
PUMP_SPEEDS_RAD_S = tuple(round(rpm * math.pi / 30, 3) for rpm in PUMP_SPEEDS_RPM)
HEAT_LOADS_W = (150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700)
