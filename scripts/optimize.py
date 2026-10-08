"""Find the lowest-power thermally safe pump speed for each heat load.

Reads the sweep CSV, adds pump power and the sanity metrics, and writes one row per heat load to the optimisation CSV.

Usage:
    python scripts/optimize.py [--sweep results/sweep_results.csv] [--output results/optimization_results.csv]
"""

import argparse
from pathlib import Path

from cooling_optimizer.analysis import add_pump_power, add_sanity_metrics, find_optimal_points, load_sweep
from cooling_optimizer.config import OPTIMIZATION_CSV, SWEEP_CSV


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sweep", type=Path, default=SWEEP_CSV, help="sweep CSV written by run_sweep.py")
    parser.add_argument("--output", type=Path, default=OPTIMIZATION_CSV, help="where to write the optimum per heat load")
    args = parser.parse_args()

    sweep = add_sanity_metrics(add_pump_power(load_sweep(args.sweep)))
    optimal = find_optimal_points(sweep)
    print(optimal.to_string(index=False))

    rounded = optimal.round(
        {
            "optimal_speed_rpm": 0,
            "cpu_temp_K": 2,
            "flow_L_min": 3,
            "delta_p_Pa": 1,
            "pump_hydraulic_power_W": 4,
            "pump_electrical_power_W": 2,
            "pump_power_share": 4,
            "coolant_delta_T_K": 2,
            "pipe_velocity_m_s": 3,
        }
    )
    rounded.to_csv(args.output, index=False)
    print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
