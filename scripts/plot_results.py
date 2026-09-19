"""Make the trade-off and pump-power figures from the sweep and optimisation CSVs.

Usage:
    python scripts/plot_results.py [--show]
"""

import argparse

import matplotlib.pyplot as plt
import pandas as pd

from cooling_optimizer.analysis import add_pump_power, load_sweep, pump_power_curve
from cooling_optimizer.config import OPTIMIZATION_CSV, PUMP_POWER_PLOT, SWEEP_CSV, TRADEOFF_PLOT
from cooling_optimizer.plotting import plot_pump_power, plot_tradeoff


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--show", action="store_true", help="also open the figures in a window")
    args = parser.parse_args()

    sweep = add_pump_power(load_sweep(SWEEP_CSV))
    optimal = pd.read_csv(OPTIMIZATION_CSV)

    plot_tradeoff(sweep, optimal).savefig(TRADEOFF_PLOT, dpi=200, bbox_inches="tight")
    print(f"Saved {TRADEOFF_PLOT}")
    plot_pump_power(pump_power_curve(sweep)).savefig(PUMP_POWER_PLOT, dpi=200, bbox_inches="tight")
    print(f"Saved {PUMP_POWER_PLOT}")

    if args.show:
        plt.show()


if __name__ == "__main__":
    main()
