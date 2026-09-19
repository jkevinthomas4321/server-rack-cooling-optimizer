"""Post-processing of the pump-speed / heat-load sweep.

Pure pandas code: nothing here needs MATLAB, so it can be run and tested anywhere.
"""

from pathlib import Path

import pandas as pd

from .config import RHO_WATER_KG_M3, THERMAL_LIMIT_K

SWEEP_COLUMNS = (
    "heat_load_W",
    "pump_speed_rad_s",
    "cpu_temp_K",
    "flow_rate_kg_s",
    "pump_pressure_in",
    "pump_pressure_out",
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


def add_pump_power(df: pd.DataFrame, rho: float = RHO_WATER_KG_M3) -> pd.DataFrame:
    """Return a copy of ``df`` with the pump's hydraulic power added.

    Hydraulic power is pressure rise times volumetric flow, P = dp * (m_dot / rho).
    Adds ``delta_p_Pa``, ``volumetric_flow_m3s`` and ``pump_power_W``.
    """
    out = df.copy()
    out["delta_p_Pa"] = out["pump_pressure_out"] - out["pump_pressure_in"]
    out["volumetric_flow_m3s"] = out["flow_rate_kg_s"] / rho
    out["pump_power_W"] = out["delta_p_Pa"] * out["volumetric_flow_m3s"]
    return out


def find_optimal_points(df: pd.DataFrame, thermal_limit_k: float = THERMAL_LIMIT_K) -> pd.DataFrame:
    """For each heat load, pick the lowest-power pump speed that keeps the CPU under the limit.

    ``df`` must already contain ``pump_power_W`` (see :func:`add_pump_power`). Returns one row
    per heat load with a ``status`` column: ``OK``, or ``NO FEASIBLE SPEED FOUND`` when even
    the fastest tested speed exceeds the limit (the pump-related columns are then NaN).
    Ties in power go to the lower speed.
    """
    df = df.sort_values(["heat_load_W", "pump_speed_rad_s"])
    feasible = df[df["cpu_temp_K"] <= thermal_limit_k]
    best = df.loc[feasible.groupby("heat_load_W")["pump_power_W"].idxmin()]

    all_loads = pd.DataFrame({"heat_load_W": df["heat_load_W"].unique()})
    result = all_loads.merge(
        best[["heat_load_W", "pump_speed_rad_s", "cpu_temp_K", "delta_p_Pa", "flow_rate_kg_s", "pump_power_W"]],
        on="heat_load_W",
        how="left",
    )
    result = result.rename(columns={"pump_speed_rad_s": "optimal_speed_rad_s"})
    result.insert(1, "status", result["optimal_speed_rad_s"].notna().map({True: STATUS_OK, False: STATUS_INFEASIBLE}))
    return result


def pump_power_curve(df: pd.DataFrame, tolerance: float = 1e-6) -> pd.DataFrame:
    """Pump power versus pump speed, as one curve.

    In this model the fluid side does not depend on the CPU heat load, so every heat load
    should give the same power at a given speed. This checks that assumption (relative
    spread within ``tolerance``) instead of silently using the first heat load's rows.
    """
    by_speed = df.groupby("pump_speed_rad_s")["pump_power_W"].agg(["min", "max", "mean"])
    spread = (by_speed["max"] - by_speed["min"]) / by_speed["max"]
    if (spread > tolerance).any():
        raise ValueError("Pump power differs between heat loads; the single-curve assumption does not hold.")
    return by_speed[["mean"]].rename(columns={"mean": "pump_power_W"}).reset_index()
