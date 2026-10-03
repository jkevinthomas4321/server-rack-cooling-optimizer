"""Run the full pump-speed x heat-load sweep on the Simscape model (needs MATLAB).

Usage:
    python scripts/run_sweep.py [--output results/sweep_results.csv]
"""

import argparse
from pathlib import Path

from cooling_optimizer.config import SWEEP_CSV
from cooling_optimizer.simulation import run_sweep


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=SWEEP_CSV, help="where to write the sweep CSV")
    args = parser.parse_args()

    df = run_sweep()
    print("\n--- Sweep results ---")
    print(df)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
