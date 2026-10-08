"""Post-processing of the pump-speed / heat-load sweep.

Pure pandas code: nothing here needs MATLAB, so it can be run and tested anywhere.
"""

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (
    CP_WATER_J_KGK,
    PIPE_FLOW_AREA_M2,
    PUMP_MIN_ELECTRICAL_W,
    PUMP_REF_ELECTRICAL_W,
    PUMP_REF_FLOW_LPM,
    PUMP_REF_SPEED_RPM,
    RHO_WATER_KG_M3,
    THERMAL_LIMIT_K,
)

SWEEP_COLUMNS = (
    "heat_load_W",
    "pump_speed_rad_s",
    "cpu_temp_K",
    "flow_rate_kg_s",
    "pump_pressure_in",
    "pump_pressure_out",
)

# Columns reported for each heat load's optimum (see find_optimal_points).
OPTIMUM_COLUMNS = (
    "pump_speed_rpm",
    "cpu_temp_K",
    "flow_L_min",
    "delta_p_Pa",
    "pump_hydraulic_power_W",
    "pump_electrical_power_W",
    "pump_power_share",
    "coolant_delta_T_K",
    "pipe_velocity_m_s",
)

STATUS_OK = "OK"
STATUS_INFEASIBLE = "NO FEASIBLE SPEED FOUND"


def load_sweep(path: Path) -> pd.DataFrame:
    """Read a sweep CSV and check that it has every column the analysis needs."""
    df = pd.read_csv(path)
    missing = [col for col in SWEEP_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")
    return df


def pump_electrical_power(flow_lpm, speed_rpm):
    """Electrical input power of the pump [W] from its datasheet curve.

    The datasheet gives power against flow at the reference speed. Other speeds are scaled
    with the affinity laws (flow ~ speed, power ~ speed^3), the same way the Simscape pump
    block scales its table. The result is never below the catalogue's minimum consumption.
    """
    ratio = np.asarray(speed_rpm, dtype=float) / PUMP_REF_SPEED_RPM
    flow_at_ref_speed = np.asarray(flow_lpm, dtype=float) / ratio
    power_at_ref_speed = np.interp(flow_at_ref_speed, PUMP_REF_FLOW_LPM, PUMP_REF_ELECTRICAL_W)
    return np.maximum(power_at_ref_speed * ratio**3, PUMP_MIN_ELECTRICAL_W)


def add_pump_power(df: pd.DataFrame, rho: float = RHO_WATER_KG_M3) -> pd.DataFrame:
    """Return a copy of ``df`` with the pump's hydraulic and electrical power added.

    Hydraulic power is pressure rise times volumetric flow, P = dp * (m_dot / rho).
    Electrical power comes from the pump datasheet (see :func:`pump_electrical_power`).
    Adds ``delta_p_Pa``, ``volumetric_flow_m3s``, ``flow_L_min``, ``pump_speed_rpm``,
    ``pump_hydraulic_power_W`` and ``pump_electrical_power_W``.
    """
    out = df.copy()
    out["delta_p_Pa"] = out["pump_pressure_out"] - out["pump_pressure_in"]
    out["volumetric_flow_m3s"] = out["flow_rate_kg_s"] / rho
    out["flow_L_min"] = out["volumetric_flow_m3s"] * 60_000
    out["pump_speed_rpm"] = (out["pump_speed_rad_s"] * 30 / math.pi).round(1)
    out["pump_hydraulic_power_W"] = out["delta_p_Pa"] * out["volumetric_flow_m3s"]
    out["pump_electrical_power_W"] = pump_electrical_power(out["flow_L_min"], out["pump_speed_rpm"])
    return out


def add_sanity_metrics(
    df: pd.DataFrame, cp: float = CP_WATER_J_KGK, pipe_area_m2: float = PIPE_FLOW_AREA_M2
) -> pd.DataFrame:
    """Return a copy of ``df`` with the quantities used to check the results against practice.

    ``df`` must already contain the columns from :func:`add_pump_power`. Adds
    ``coolant_delta_T_K`` (Q / (m_dot * cp)), ``pipe_velocity_m_s`` and
    ``pump_power_share`` (pump electrical power / CPU heat load).
    """
    out = df.copy()
    out["coolant_delta_T_K"] = out["heat_load_W"] / (out["flow_rate_kg_s"] * cp)
    out["pipe_velocity_m_s"] = out["volumetric_flow_m3s"] / pipe_area_m2
    out["pump_power_share"] = out["pump_electrical_power_W"] / out["heat_load_W"]
    return out


def find_optimal_points(df: pd.DataFrame, thermal_limit_k: float = THERMAL_LIMIT_K) -> pd.DataFrame:
    """For each heat load, pick the lowest-power pump speed that keeps the CPU under the limit.

    ``df`` must already contain the columns from :func:`add_pump_power` and
    :func:`add_sanity_metrics`. Power means the pump's electrical power. Returns one row
    per heat load with a ``status`` column: ``OK``, or ``NO FEASIBLE SPEED FOUND`` when even
    the fastest tested speed exceeds the limit (the pump-related columns are then NaN).
    Ties in power go to the lower speed.
    """
    df = df.sort_values(["heat_load_W", "pump_speed_rad_s"])
    feasible = df[df["cpu_temp_K"] <= thermal_limit_k]
    best = df.loc[feasible.groupby("heat_load_W")["pump_electrical_power_W"].idxmin()]

    all_loads = pd.DataFrame({"heat_load_W": df["heat_load_W"].unique()})
    result = all_loads.merge(best[["heat_load_W", *OPTIMUM_COLUMNS]], on="heat_load_W", how="left")
    result = result.rename(columns={"pump_speed_rpm": "optimal_speed_rpm"})
    result.insert(1, "status", result["optimal_speed_rpm"].notna().map({True: STATUS_OK, False: STATUS_INFEASIBLE}))
    return result


def pump_power_curve(df: pd.DataFrame, tolerance: float = 1e-3) -> pd.DataFrame:
    """Pump hydraulic and electrical power versus pump speed, as one curve each.

    The coolant reaches the pump, pipe and cold-plate resistance at supply temperature, so
    the flow should not depend on the CPU heat load and every heat load should give the same
    power at a given speed. This checks that assumption (relative spread within
    ``tolerance``) instead of silently using the first heat load's rows.
    """
    columns = ["pump_hydraulic_power_W", "pump_electrical_power_W"]
    grouped = df.groupby("pump_speed_rpm")[columns]
    spread = (grouped.max() - grouped.min()) / grouped.max()
    if (spread > tolerance).any().any():
        raise ValueError("Pump power differs between heat loads; the single-curve assumption does not hold.")
    return grouped.mean().reset_index()
