"""Drive the Simscape cooling-loop model from Python through the MATLAB Engine.

This is the only module that needs MATLAB. ``matlab.engine`` is imported inside
:func:`run_sweep` so the analysis code and its tests work on a machine without MATLAB.
"""

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (
    HEAT_BLOCK, HEAT_LOADS_W, MODEL_DIR, MODEL_NAME, PUMP_BLOCK, PUMP_SPEEDS_RAD_S, SIM_STOP_TIME_S,
)

# Model workspace signals read after each run: name in the model -> column in the results.
_OUTPUT_SIGNALS = {
    "cpu_temp_out": "cpu_temp_K",
    "flow_rate_out": "flow_rate_kg_s",
    "pump_pressure_in": "pump_pressure_in",
    "pump_pressure_out": "pump_pressure_out",
}


def run_sweep(
    heat_loads: Sequence[float] = HEAT_LOADS_W,
    pump_speeds: Sequence[float] = PUMP_SPEEDS_RAD_S,
    model_name: str = MODEL_NAME,
    model_dir: Path = MODEL_DIR,
    stop_time_s: float = SIM_STOP_TIME_S,
) -> pd.DataFrame:
    """Simulate every (heat load, pump speed) pair and return the final steady-state values.

    One simulation is run per pair. The CPU heat load is held constant for each run, so the
    last sample of each output signal is its steady-state value.
    """
    import matlab.engine  # imported here on purpose, see module docstring

    engine = matlab.engine.start_matlab()
    try:
        engine.cd(str(model_dir), nargout=0)
        engine.load_system(model_name, nargout=0)
        engine.set_param(model_name, "ReturnWorkspaceOutputs", "off", nargout=0)
        engine.set_param(model_name, "StopTime", str(stop_time_s), nargout=0)

        pump_path = f"{model_name}/{PUMP_BLOCK}"
        heat_path = f"{model_name}/{HEAT_BLOCK}"
        total = len(heat_loads) * len(pump_speeds)
        rows = []

        for heat in heat_loads:
            # A step from `heat` to `heat` at t=0: a constant load for the whole run.
            engine.set_param(heat_path, "Time", "0", nargout=0)
            engine.set_param(heat_path, "Before", str(heat), nargout=0)
            engine.set_param(heat_path, "After", str(heat), nargout=0)

            for speed in pump_speeds:
                print(f"Run {len(rows) + 1}/{total}: speed={speed} rad/s, heat={heat} W")
                engine.set_param(pump_path, "constant", str(speed), nargout=0)
                engine.sim(model_name, nargout=0)

                row = {"heat_load_W": heat, "pump_speed_rad_s": speed}
                for signal, column in _OUTPUT_SIGNALS.items():
                    data = np.array(engine.eval(f"{signal}.Data", nargout=1))
                    row[column] = data[-1][0]
                rows.append(row)
    finally:
        engine.close_system(model_name, 0, nargout=0)
        engine.quit()

    return pd.DataFrame(rows)
