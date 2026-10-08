"""Tests for the sweep post-processing (no MATLAB needed)."""

import math

import numpy as np
import pandas as pd
import pytest

from cooling_optimizer.analysis import (
    STATUS_INFEASIBLE,
    STATUS_OK,
    add_pump_power,
    add_sanity_metrics,
    find_optimal_points,
    load_sweep,
    pump_electrical_power,
    pump_power_curve,
)
from cooling_optimizer.config import (
    COOLANT_DELTA_T_RANGE_K,
    COOLANT_SUPPLY_K,
    MAX_COLD_PLATE_FLOW_LPM,
    MAX_PIPE_VELOCITY_M_S,
    MAX_PUMP_POWER_SHARE,
    SWEEP_CSV,
)


def make_sweep(rows):
    """Build a sweep DataFrame from (heat, speed_rpm, cpu_temp, flow_kg_s, dp) tuples."""
    return pd.DataFrame(
        [
            {
                "heat_load_W": heat,
                "pump_speed_rad_s": rpm * math.pi / 30,
                "cpu_temp_K": temp,
                "flow_rate_kg_s": flow,
                "pump_pressure_in": 150_000.0,
                "pump_pressure_out": 150_000.0 + dp,
            }
            for heat, rpm, temp, flow, dp in rows
        ]
    )


def prepare(rows):
    """A sweep with every derived column the optimisation needs."""
    return add_sanity_metrics(add_pump_power(make_sweep(rows)))


def test_hydraulic_power_is_pressure_rise_times_volumetric_flow():
    # dp = 1000 Pa, 2 kg/s at rho = 1000 kg/m^3 = 0.002 m^3/s  ->  P = 1000 * 0.002 = 2 W (hand calculation)
    df = add_pump_power(make_sweep([(100, 4800, 300.0, 2.0, 1000.0)]), rho=1000.0)
    assert df["pump_hydraulic_power_W"].iloc[0] == pytest.approx(2.0)
    assert df["delta_p_Pa"].iloc[0] == pytest.approx(1000.0)


def test_add_pump_power_does_not_modify_its_input():
    raw = make_sweep([(100, 4800, 300.0, 0.03, 1000.0)])
    add_pump_power(raw)
    assert "pump_hydraulic_power_W" not in raw.columns


def test_electrical_power_follows_the_datasheet_at_reference_speed():
    # Datasheet points at 4800 rpm: 17 W at zero flow, 19 W at 5 L/min.
    assert pump_electrical_power(0.0, 4800) == pytest.approx(17.0)
    assert pump_electrical_power(5.0, 4800) == pytest.approx(19.0)


def test_electrical_power_scales_with_speed_cubed():
    # 3600 rpm is 0.75 of the reference speed; 3.75 L/min maps to 5 L/min at reference speed.
    # P = 19 W * 0.75^3 = 8.016 W (hand calculation)
    assert pump_electrical_power(3.75, 3600) == pytest.approx(19.0 * 0.75**3)


def test_electrical_power_never_drops_below_the_catalogue_minimum():
    # Affinity scaling alone would give 19 W / 8 = 2.4 W at half speed; the catalogue minimum is 3 W.
    assert pump_electrical_power(2.5, 2400) == pytest.approx(3.0)


def test_sanity_metrics_match_hand_calculation():
    # 418 W into 0.01 kg/s of water (cp = 4180 J/kgK)  ->  dT = 418 / 41.8 = 10 K
    # 0.01 kg/s at 990.2 kg/m^3 through 5e-5 m^2       ->  v = 0.202 m/s
    row = prepare([(418, 4800, 330.0, 0.01, 30_000.0)]).iloc[0]
    assert row["coolant_delta_T_K"] == pytest.approx(10.0)
    assert row["pipe_velocity_m_s"] == pytest.approx(0.202, abs=1e-3)
    assert row["pump_power_share"] == pytest.approx(row["pump_electrical_power_W"] / 418)


def test_optimum_is_lowest_power_among_thermally_safe_speeds():
    # 2400 rpm is too hot, 3600 and 4800 rpm are safe, and 3600 rpm uses less power than 4800 rpm.
    sweep = prepare(
        [
            (600, 2400, 360.0, 0.018, 9_000.0),
            (600, 3600, 345.0, 0.027, 21_000.0),
            (600, 4800, 340.0, 0.036, 37_000.0),
        ]
    )
    row = find_optimal_points(sweep, thermal_limit_k=352.15).iloc[0]
    assert row["status"] == STATUS_OK
    assert row["optimal_speed_rpm"] == pytest.approx(3600)


def test_heat_load_with_no_safe_speed_is_reported_not_dropped():
    sweep = prepare([(900, 800, 400.0, 0.006, 1_000.0), (900, 1000, 390.0, 0.008, 1_600.0)])
    result = find_optimal_points(sweep, thermal_limit_k=352.15)
    assert list(result["status"]) == [STATUS_INFEASIBLE]
    assert math.isnan(result["optimal_speed_rpm"].iloc[0])


def test_ties_in_power_go_to_the_lower_speed():
    # Both speeds sit on the 3 W catalogue minimum, so the power is equal.
    sweep = prepare([(200, 1000, 340.0, 0.008, 1_600.0), (200, 800, 345.0, 0.006, 1_000.0)])
    assert find_optimal_points(sweep)["optimal_speed_rpm"].iloc[0] == pytest.approx(800)


def test_temperature_exactly_at_the_limit_counts_as_safe():
    sweep = prepare([(300, 800, 352.15, 0.006, 1_000.0)])
    assert find_optimal_points(sweep, thermal_limit_k=352.15)["status"].iloc[0] == STATUS_OK


def test_load_sweep_rejects_a_file_with_missing_columns(tmp_path):
    bad = tmp_path / "bad.csv"
    pd.DataFrame({"heat_load_W": [1], "pump_speed_rad_s": [2]}).to_csv(bad, index=False)
    with pytest.raises(ValueError, match="missing required columns"):
        load_sweep(bad)


def test_pump_power_curve_rejects_heat_load_dependent_power():
    sweep = prepare([(100, 4800, 330.0, 0.03, 30_000.0), (200, 4800, 330.0, 0.03, 90_000.0)])
    with pytest.raises(ValueError, match="single-curve"):
        pump_power_curve(sweep)


# --- Regression checks against the committed sweep (values quoted in the README) ---


@pytest.fixture(scope="module")
def committed_sweep():
    return add_sanity_metrics(add_pump_power(load_sweep(SWEEP_CSV)))


@pytest.fixture(scope="module")
def committed_optimum(committed_sweep):
    return find_optimal_points(committed_sweep).set_index("heat_load_W")


@pytest.mark.parametrize(
    "heat, speed_rpm, cpu_temp_k",
    [(150, 800, 332.62), (350, 800, 351.91), (400, 1000, 349.73), (550, 1500, 348.62), (700, 1800, 351.33)],
)
def test_committed_sweep_reproduces_readme_optima(committed_optimum, heat, speed_rpm, cpu_temp_k):
    row = committed_optimum.loc[heat]
    assert row["optimal_speed_rpm"] == pytest.approx(speed_rpm)
    assert row["cpu_temp_K"] == pytest.approx(cpu_temp_k, abs=0.01)


def test_committed_sweep_has_a_safe_speed_for_every_heat_load(committed_optimum):
    assert (committed_optimum["status"] == STATUS_OK).all()


# --- Sanity checks: the committed results must stay inside realistic ranges (sources in the README) ---


def test_pipe_velocity_stays_below_the_erosion_limit(committed_sweep):
    assert committed_sweep["pipe_velocity_m_s"].max() <= MAX_PIPE_VELOCITY_M_S


def test_flow_stays_inside_the_cold_plate_recommended_range(committed_sweep):
    assert committed_sweep["flow_L_min"].max() <= MAX_COLD_PLATE_FLOW_LPM


def test_pump_never_delivers_more_hydraulic_power_than_it_draws(committed_sweep):
    assert (committed_sweep["pump_hydraulic_power_W"] < committed_sweep["pump_electrical_power_W"]).all()


def test_coolant_temperature_rise_at_the_optimum_is_realistic(committed_optimum):
    low, high = COOLANT_DELTA_T_RANGE_K
    assert committed_optimum["coolant_delta_T_K"].between(low, high).all()


def test_pump_power_share_at_the_optimum_is_realistic(committed_optimum):
    assert committed_optimum["pump_power_share"].max() <= MAX_PUMP_POWER_SHARE


def test_cold_plate_resistance_matches_the_datasheet_calibration_point(committed_sweep):
    # Calibration target: case-to-inlet resistance 0.0267 K/W at 1.6 L/min.
    one_load = committed_sweep[committed_sweep["heat_load_W"] == 700].sort_values("flow_L_min")
    resistance = (one_load["cpu_temp_K"] - COOLANT_SUPPLY_K) / 700
    assert np.interp(1.6, one_load["flow_L_min"], resistance) == pytest.approx(0.0267, rel=0.05)
