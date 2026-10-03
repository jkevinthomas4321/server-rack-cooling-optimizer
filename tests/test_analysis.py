"""Tests for the sweep post-processing (no MATLAB needed)."""

import math

import pandas as pd
import pytest

from cooling_optimizer.analysis import (
    STATUS_INFEASIBLE,
    STATUS_OK,
    add_pump_power,
    find_optimal_points,
    load_sweep,
    pump_power_curve,
)
from cooling_optimizer.config import SWEEP_CSV


def make_sweep(rows):
    """Build a sweep DataFrame from (heat, speed, cpu_temp, flow, dp) tuples."""
    return pd.DataFrame(
        [
            {
                "heat_load_W": heat,
                "pump_speed_rad_s": speed,
                "cpu_temp_K": temp,
                "flow_rate_kg_s": flow,
                "pump_pressure_in": 100_000.0,
                "pump_pressure_out": 100_000.0 + dp,
            }
            for heat, speed, temp, flow, dp in rows
        ]
    )


def test_pump_power_is_pressure_rise_times_volumetric_flow():
    # dp = 1000 Pa, 2 kg/s of water = 0.002 m^3/s  ->  P = 1000 * 0.002 = 2 W (hand calculation)
    df = add_pump_power(make_sweep([(100, 50, 300.0, 2.0, 1000.0)]))
    assert df["pump_power_W"].iloc[0] == pytest.approx(2.0)
    assert df["delta_p_Pa"].iloc[0] == pytest.approx(1000.0)


def test_add_pump_power_does_not_modify_its_input():
    raw = make_sweep([(100, 50, 300.0, 2.0, 1000.0)])
    add_pump_power(raw)
    assert "pump_power_W" not in raw.columns


def test_optimum_is_lowest_power_among_thermally_safe_speeds():
    # Speed 40 is too hot, 60 and 80 are safe, and 60 uses less power than 80.
    sweep = add_pump_power(
        make_sweep(
            [
                (200, 40, 400.0, 0.2, 5_000.0),
                (200, 60, 360.0, 0.3, 30_000.0),
                (200, 80, 340.0, 0.4, 60_000.0),
            ]
        )
    )
    result = find_optimal_points(sweep, thermal_limit_k=368.15)
    row = result.iloc[0]
    assert row["status"] == STATUS_OK
    assert row["optimal_speed_rad_s"] == 60


def test_heat_load_with_no_safe_speed_is_reported_not_dropped():
    sweep = add_pump_power(make_sweep([(500, 40, 400.0, 0.2, 5_000.0), (500, 60, 390.0, 0.3, 30_000.0)]))
    result = find_optimal_points(sweep, thermal_limit_k=368.15)
    assert list(result["status"]) == [STATUS_INFEASIBLE]
    assert math.isnan(result["optimal_speed_rad_s"].iloc[0])


def test_ties_in_power_go_to_the_lower_speed():
    sweep = add_pump_power(make_sweep([(100, 80, 300.0, 0.3, 30_000.0), (100, 60, 300.0, 0.3, 30_000.0)]))
    assert find_optimal_points(sweep)["optimal_speed_rad_s"].iloc[0] == 60


def test_temperature_exactly_at_the_limit_counts_as_safe():
    sweep = add_pump_power(make_sweep([(100, 60, 368.15, 0.3, 30_000.0)]))
    assert find_optimal_points(sweep, thermal_limit_k=368.15)["status"].iloc[0] == STATUS_OK


def test_load_sweep_rejects_a_file_with_missing_columns(tmp_path):
    bad = tmp_path / "bad.csv"
    pd.DataFrame({"heat_load_W": [1], "pump_speed_rad_s": [2]}).to_csv(bad, index=False)
    with pytest.raises(ValueError, match="missing required columns"):
        load_sweep(bad)


def test_pump_power_curve_rejects_heat_load_dependent_power():
    sweep = add_pump_power(make_sweep([(100, 60, 300.0, 0.3, 30_000.0), (200, 60, 300.0, 0.3, 90_000.0)]))
    with pytest.raises(ValueError, match="single-curve"):
        pump_power_curve(sweep)


# --- Regression checks against the committed sweep (values quoted in the README) ---


@pytest.fixture(scope="module")
def committed_optimum():
    sweep = add_pump_power(load_sweep(SWEEP_CSV))
    return find_optimal_points(sweep).set_index("heat_load_W")


@pytest.mark.parametrize(
    "heat, speed, power",
    [(40, 40, 1.62), (200, 60, 9.09), (350, 150, 155.4), (450, 200, 368.4)],
)
def test_committed_sweep_reproduces_readme_optima(committed_optimum, heat, speed, power):
    row = committed_optimum.loc[heat]
    assert row["optimal_speed_rad_s"] == speed
    assert row["pump_power_W"] == pytest.approx(power, rel=1e-3)


def test_committed_sweep_has_no_safe_speed_at_500_w(committed_optimum):
    assert committed_optimum.loc[500, "status"] == STATUS_INFEASIBLE
