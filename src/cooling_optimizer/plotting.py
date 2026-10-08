"""Figures for the sweep results."""

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from .analysis import STATUS_OK
from .config import THERMAL_LIMIT_K


def plot_tradeoff(df: pd.DataFrame, optimal: pd.DataFrame | None = None) -> Figure:
    """CPU temperature against pump speed, one line per heat load.

    ``df`` must contain ``pump_speed_rpm`` (see :func:`analysis.add_pump_power`).

    If ``optimal`` (from :func:`analysis.find_optimal_points`) is given, each heat load's
    minimum-power feasible operating point is circled.
    """
    fig, ax = plt.subplots(figsize=(11, 6))

    heat_loads = sorted(df["heat_load_W"].unique())
    colors = plt.cm.viridis_r([i / len(heat_loads) for i in range(len(heat_loads))])

    for heat, color in zip(heat_loads, colors):
        subset = df[df["heat_load_W"] == heat].sort_values("pump_speed_rpm")
        ax.plot(subset["pump_speed_rpm"], subset["cpu_temp_K"], marker="o", label=f"{heat} W", color=color)

        if optimal is not None:
            row = optimal[(optimal["heat_load_W"] == heat) & (optimal["status"] == STATUS_OK)]
            if not row.empty:
                ax.scatter(
                    row["optimal_speed_rpm"], row["cpu_temp_K"],
                    s=200, facecolors="none", edgecolors=color, linewidths=2.5, zorder=5,
                )

    ax.axhline(
        THERMAL_LIMIT_K, color="red", linestyle="--", linewidth=1.5,
        label=f"Thermal Limit ({THERMAL_LIMIT_K:.2f} K / {THERMAL_LIMIT_K - 273.15:.0f}°C)",
    )
    ax.set_xlabel("Pump Speed (rpm)")
    ax.set_ylabel("Steady-State CPU Case Temperature (K)")
    title = "CPU Cooling Trade-off: Temperature vs. Pump Speed"
    if optimal is not None:
        title += "\n(circled points = minimum-power feasible operating point)"
    ax.set_title(title)
    ax.legend(title="CPU Heat Load", loc="upper left", bbox_to_anchor=(1.01, 1.0))  # outside the axes so it hides no data
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def plot_pump_power(curve: pd.DataFrame) -> Figure:
    """Pump hydraulic and electrical power against pump speed (``curve`` from :func:`analysis.pump_power_curve`)."""
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(curve["pump_speed_rpm"], curve["pump_electrical_power_W"], marker="o", color="darkorange", label="Electrical (datasheet)")
    ax.plot(curve["pump_speed_rpm"], curve["pump_hydraulic_power_W"], marker="s", color="steelblue", label="Hydraulic (dp x flow)")
    ax.set_yscale("log")
    ax.set_xlabel("Pump Speed (rpm)")
    ax.set_ylabel("Pump Power (W)")
    ax.set_title("Pump Power vs. Pump Speed")
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    return fig
