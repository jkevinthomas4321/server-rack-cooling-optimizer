# 🖥️ Cooling a Server CPU — Finding the Sweet Spot Between Power and Temperature

*A physics-based simulation, automated with Python, that answers a simple question: how hard does a cooling pump actually need to work?*

<p align="center">
  <img src="results/tradeoff_plot.png" width="700">
</p>

---

## Overview

**Problem:**
Liquid-cooled servers face a direct trade-off: a faster pump improves cooling but consumes power that grows close to cubically with speed, while a slower pump saves energy but risks the CPU exceeding its case temperature limit. Neither "run it slow to save power" nor "run it fast to be safe" is a defensible engineering answer without knowing where the trade-off actually sits.

**Approach:**
Built a coupled fluid-thermal model in MATLAB Simscape (pump → tubing → cold plate → CPU thermal mass) with parameters taken from datasheets and published guidelines, checked the governing relationships against hand calculations, then used Python (`matlab.engine`) to automate a parameter sweep across pump speeds and CPU heat loads. A Python analysis finds, for each heat load, the lowest-power pump speed that keeps the CPU under its case temperature limit, and checks the results against realistic ranges.

**Result:**
With 45 °C coolant supply and a 79 °C case limit, the pump's minimum speed (800 rpm, 0.37 L/min) is enough up to 350 W. From 400 W to 700 W the speed has to rise to 1000–1800 rpm (0.46–0.83 L/min). At these operating points the pump draws about 3 W, which is 0.4–2 % of the CPU heat load, and the coolant warms by 11–14 K. Running the same pump at full speed would draw about 18 W for no thermal benefit.

> **Note:** the model was corrected in October 2026. The earlier version used unrealistic parameters and its results should not be used. See [Model Correction](#model-correction-october-2026).

---

## Tools & Environment

| Tool | Version | Purpose |
|---|---|---|
| MATLAB | R2024a | Simulation environment |
| Simscape (Thermal Liquid + Thermal domains) | R2024a | Physics-based pump, coolant, and heat transfer modeling |
| Python | 3.11 | Automation, optimization, plotting |
| `matlab.engine` | 24.1 | Python ↔ MATLAB bridge (only needed to re-run the sweep) |
| pandas / numpy | latest | Data handling |
| matplotlib | latest | Result visualization |
| pytest | latest | Tests for the analysis code and sanity checks on the results |

---

## System Architecture

```
Reservoir (45 °C supply) → Centrifugal Pump → Pipe → Cold Plate Flow Resistance → Coolant Chamber → Reservoir (return)
                                                                                        ⇅
                                                                          Convective Heat Transfer
                                                                                        ⇅
                                                                  CPU Thermal Mass ← Heat Flow Source
```

The model couples two Simscape physical domains:
- **Thermal Liquid domain** — pump, tubing, cold-plate flow resistance and coolant chamber, governing flow rate and pressure
- **Thermal domain** — CPU heat generation and thermal mass

A `Convective Heat Transfer` block bridges the two domains, computing `Q = h·A·(T_cpu − T_coolant)`, with `h` calculated from coolant flow rate via a MATLAB Function block (`compute_h`).

Both reservoirs are at the same pressure (1.5 bar), so the flow is driven by the pump alone and the operating point is the intersection of the pump curve and the system curve.

---

## Model Parameters and Sources

| Parameter | Value | Source |
|---|---|---|
| Pump curve at 4800 rpm | 3.9 m shut-off head, 25 L/min maximum flow, 17–23 W electrical | Laing D5 catalogue (Xylem BR-19B), speed setting 5 [1]; headline values from [2] |
| Pump speed range | 800–4800 rpm | PWM range of the D5 pump [2] |
| Pump minimum power | 3 W | Lowest consumption stated in the catalogue [1] |
| Cold plate thermal resistance | 0.0267 K/W case-to-inlet at 1.6 L/min | Wakefield Thermal 133032 cold plate for Intel Xeon [3] |
| Cold plate pressure drop | 29.3 kPa at 2 L/min | OCP OAI liquid cooling guidelines, section 6.3.3 [4] |
| Coolant supply temperature | 45 °C | OCP "Group 1" supply range 40–45 °C [4]; test condition in [3] |
| CPU case temperature limit | 79 °C | Intel Xeon Platinum 8480+ (350 W TDP), TCASE [5] |
| Heat load range | 150–700 W | 350 W TDP of [5]; cold plate rated up to 700 W [3] |
| Tubing | 8 mm inner diameter, 1.3 m | Assumption (cold plate in [3] has 10 mm OD hose barbs) |
| CPU and cold plate thermal mass | 0.08 kg, cp = 900 J/kg·K | Assumption (affects only the transient, not the steady-state results) |
| Coolant | Water | Assumption ([3] recommends a 50/50 coolant, which performs somewhat worse) |

Values that needed interpretation:

- **Pump curve.** The catalogue shows the curve as a chart, so the six tabulated points are an approximate read-off anchored to the published shut-off head, maximum flow and maximum power. The loop only uses the first tenth of the curve (below 2.3 L/min), where the head is almost flat, so the results are not sensitive to the read-off.
- **Pump power.** The catalogue gives electrical input power. It is entered as the pump block's brake power because the D5 is a wet-rotor pump, so its motor losses also heat the coolant. Other speeds are scaled with the affinity laws and never fall below the 3 W catalogue minimum.
- **Cold plate pressure drop.** The OCP document reports 17 psi at 2 L/min per path, about half of it in two cold plates in series. That gives 29.3 kPa per cold plate. It is a different cold plate from [3], which publishes no pressure drop.
- **Cold plate heat transfer.** The CPU exchanges heat with the well-mixed chamber at coolant outlet temperature, so the case-to-inlet resistance of the model is `R = 1/(ṁ·cp) + 1/(h·A)`. At 1.6 L/min, `1/(ṁ·cp)` is 0.0091 K/W, so `h·A` must be 56.7 W/K to give 0.0267 K/W. With `h = C·ṁ^0.8` and the 0.002 m² footprint kept as reference area, `C = 5.19·10⁵`. `h` is therefore an effective coefficient that includes the gain from the fin area.
- **Datasheet [3] is not fully self-consistent:** its stated case temperature (55.4 °C at 45 °C inlet, 700 W) implies 0.0149 K/W, not the quoted 0.0267 K/W. The quoted, more conservative value is used.

---

## Methodology

### 1. Modeling assumptions

- CPU and cold plate modeled as a single lumped thermal mass; its temperature is compared with the CPU case temperature limit
- Convective coefficient modeled as flow-dependent, `h = C·ṁ^0.8` (flow-exponent form of the Dittus–Boelter correlation), calibrated to one datasheet point
- Cold plate pressure drop modeled as a quadratic flow resistance calibrated to one published point
- Coolant supply at constant temperature and pressure, representing a coolant distribution unit; the heat rejection side is not modeled
- CPU heat load held constant per simulation run

### 2. Validation

| Check | Hand calculation | Simulation |
|---|---|---|
| Pump head at 800 rpm (affinity law, `H ∝ N²`) | 3.81 m × (800/4800)² → 1028 Pa | 1030 Pa |
| System curve at 4800 rpm (cold plate + tubing at 2.22 L/min) | 35.6 kPa + about 1.4 kPa = 37.0 kPa | 37.0 kPa |
| Steady-state energy balance at 700 W, 1800 rpm | 45 °C + 12.3 K (coolant) + 20.9 K (cold plate) = 351.3 K | 351.3 K |
| Cold plate calibration point | 0.0267 K/W at 1.6 L/min | 0.0271 K/W (interpolated between sweep points) |
| Pump hydraulic power scaling | Cubic affinity law | Exponent 2.98–3.02 between neighbouring speeds |

The transient response check (`τ = m·cp / hA`) was done on the original model and has not been repeated after the correction.

### 3. Test scenarios

- **Full factorial sweep:** 12 CPU heat loads (150–700 W) × 8 pump speeds (800–4800 rpm) = 96 simulations, run automatically via Python
- **Optimization:** for each heat load, minimum pump electrical power subject to CPU case temperature remaining under 352.15 K (79 °C)

### 4. Post-processing

- Pump hydraulic power is `P = Δp · V̇`. Pump electrical power comes from the datasheet curve, scaled with the affinity laws.
- For every operating point the analysis also reports coolant temperature rise `Q/(ṁ·cp)`, tubing velocity and pump power as a share of the heat load.
- `pytest` checks these against realistic bounds, so an unrealistic model fails the tests:

| Quantity | Bound | Source |
|---|---|---|
| Tubing velocity | ≤ 2.1 m/s | ASHRAE erosion limit for liquid-cooling piping, as cited in [6] |
| Flow through the cold plate | ≤ 3.5 L/min | Recommended range of the cold plate [3] |
| Coolant temperature rise at the optimum | 2–15 K | OCP design range is 7.5–12 K [4]; widened for part load |
| Pump electrical power / heat load at the optimum | ≤ 5 % | Own bound; no published limit found |
| Hydraulic power | < electrical power | Energy conservation |

---

## Results

**Key plot:**
Temperature vs. pump speed for every tested heat load, with the case temperature limit overlaid and each heat load's optimal (minimum-power, thermally safe) point circled (top of this page).

**Optimum per heat load:**

| Heat Load (W) | Optimal Speed (rpm) | Flow (L/min) | CPU Case Temp (K) | Coolant ΔT (K) | Pump Electrical Power (W) | Pump Share of Heat Load |
|---|---|---|---|---|---|---|
| 150 | 800 | 0.37 | 332.6 | 5.9 | 3.0 | 2.0 % |
| 350 | 800 | 0.37 | 351.9 | 13.8 | 3.0 | 0.9 % |
| 400 | 1000 | 0.46 | 349.7 | 12.5 | 3.0 | 0.8 % |
| 500 | 1200 | 0.56 | 351.7 | 13.0 | 3.0 | 0.6 % |
| 600 | 1500 | 0.69 | 351.4 | 12.6 | 3.0 | 0.5 % |
| 700 | 1800 | 0.83 | 351.3 | 12.3 | 3.0 | 0.4 % |

Full table: `results/optimization_results.csv`.

**Findings:**

- **Two regimes.** Up to 350 W the pump's minimum speed is already sufficient (speed-limited). From 400 W the thermal limit is active and the required speed rises with heat load (thermally limited).
- **The optimum is a coolant temperature rise of 11–14 K.** In the thermally limited regime the lowest safe flow gives a rise slightly above the 7.5–12 K design range in the OCP guidelines [4]. The optimum has almost no margin (0.2–3.8 K below the limit), so a real design would run somewhat faster.
- **Pump power is small.** All optimal points sit on the pump's 3 W minimum, 0.4–2 % of the heat load. Pump energy is therefore not what limits this loop; the flow rate and coolant temperature rise are.
- **Running flat out is wasteful.** At 4800 rpm the pump draws 17.9 W and delivers 2.2 L/min, with the 700 W case 20 K below the limit. That is about 15 W more than needed per pump.
- **Hydraulic power is cubic in speed** (0.006 W at 800 rpm to 1.37 W at 4800 rpm). Only about 8 % of the electrical power becomes hydraulic power at full speed, because the pump works at 2.2 L/min on a curve that reaches 25 L/min.

**Limitations:**

- The optimum is found on a grid of 8 speeds, so the true minimum safe speed lies between the reported speed and the next lower one
- Because of the 3 W minimum, electrical power does not distinguish between speeds up to 2400 rpm; the optimum there is simply the lowest thermally safe speed
- Cold plate heat transfer and pressure drop are each calibrated to a single published point, from two different cold plates; the `ṁ^0.8` exponent is not verified for microchannel flow, where the flow dependence is usually weaker
- The pump curve is an approximate read-off from a catalogue chart
- No thermal interface material or junction-to-case resistance; the limit is applied to the lumped CPU and cold plate mass
- One cold plate on one pump; real servers put several cold plates on a shared loop with manifolds and quick disconnects, which roughly doubles the pressure drop [4]
- Constant heat load per run; a real server workload varies over time
- The supply is a constant-temperature boundary, not a closed loop with a heat exchanger

---

## Model Correction (October 2026)

The first version of this model produced results that no real cooling loop would show: up to 48 L/min through one cold plate, 16 m/s in the tubing, and 368 W of pump hydraulic power to cool a 450 W CPU. A review against datasheets found the causes:

| Problem | Before | After |
|---|---|---|
| Cold plate thermal resistance | 0.16–0.41 K/W (`h` applied to the bare 20 cm² footprint) | 0.020–0.096 K/W over the flow range, calibrated to 0.0267 K/W at 1.6 L/min [3] |
| Pump | Block default values: 60 m shut-off head, 0.85 kW | D5-class pump: 3.9 m, at most 23 W [1][2] |
| Boundaries | 1.5 bar inlet, 1.03 bar outlet; 13.9 L/min flowed with the pump doing nothing | Equal pressures; flow is driven by the pump only |
| Cold plate pressure drop | Not modeled | 29.3 kPa at 2 L/min [4] |
| Supply temperature and limit | 20 °C supply, 95 °C limit | 45 °C supply [4], 79 °C case limit [5] |
| Flow | 15–48 L/min | 0.37–2.2 L/min (OCP: 1–2 L/min per cold plate [4]) |
| Tubing velocity | 5–16 m/s | 0.12–0.74 m/s |
| Coolant temperature rise at the optimum | 0.04–0.16 K | 5.9–13.8 K |
| Pump power / heat load at the optimum | Up to 82 % (hydraulic only) | 0.4–2 % (electrical) |
| Reported pump power | Hydraulic only | Hydraulic and electrical |
| Sanity checks | None | `pytest` bounds on velocity, flow, coolant ΔT and pump share |

The weak cold plate was the root cause: it forced a very large flow, which needed an industrial pump, which produced the absurd pump power. The earlier "invalid pump region below 33 rad/s" was a symptom of the pressure difference between the reservoirs pushing more flow through the pump than it could deliver at that speed.

What stayed valid: the model structure, the steady-state energy balance, the cubic pump power trend, the existence of a speed-limited and a thermally limited regime, and the Python sweep and optimisation logic. The earlier headline figure ("pump power rises over 200×") was an artefact and has been removed.

Every changed model parameter is recorded in `models/apply_model_correction.m`, so the change to the binary `.slx` file can be reviewed as text. The review, the corrected parameters, the code changes and the re-run of the sweep were done with Claude Code, Anthropic's coding assistant.

---

## Repository Structure

```
├── models/
│   ├── server_cooling_loop_v2_working.slx      # Simscape model
│   └── apply_model_correction.m                # record of the October 2026 parameter changes
├── src/cooling_optimizer/
│   ├── config.py        # paths, sweep grid, thermal limit, pump datasheet, sanity bounds
│   ├── simulation.py    # runs the sweep through the MATLAB Engine (only module that needs MATLAB)
│   ├── analysis.py      # pump power, sanity metrics, minimum-power feasible speed per heat load
│   └── plotting.py      # trade-off and pump-power figures
├── scripts/
│   ├── run_sweep.py               # 1. simulate the full grid  -> results/sweep_results.csv
│   ├── optimize.py                # 2. find optimal points      -> results/optimization_results.csv
│   ├── plot_results.py            # 3. make the figures         -> results/*.png
│   └── check_matlab_connection.py # smoke test for the MATLAB Engine setup
├── tests/test_analysis.py         # unit tests, regression and sanity checks on the committed sweep
├── results/
└── README.md
```

---

## How to Run

```bash
# 1. Create and activate a Python 3.11 virtual environment
#    (required for MATLAB R2024a's matlab.engine compatibility)

# 2. Install the package and its dependencies
pip install -e ".[test]"

# 3. Run the tests (no MATLAB needed)
pytest

# 4. Re-run the analysis on the committed sweep (no MATLAB needed)
python scripts/optimize.py
python scripts/plot_results.py

# 5. Only to regenerate the sweep itself: install the MATLAB Engine API for Python
#    (pip install matlabengine==24.1.*), then
python scripts/check_matlab_connection.py
python scripts/run_sweep.py
```

---

## Code Cleanup (September 2026)

The original Simscape model, the sweep design and the analysis logic are my own work. In September 2026 I restructured the Python code from standalone scripts into a small package (shared config and analysis module, command-line scripts, tests) using Claude Code, Anthropic's coding assistant. The original scripts remain in the `main` branch history. The model parameters and results were replaced in October 2026 (see Model Correction above).

---

## What I'd Do With More Time

- Use a cold plate datasheet that gives thermal resistance and pressure drop over a range of flows, and fit the flow exponent instead of assuming 0.8
- Refine the speed grid around the optimum, or solve for the minimum safe speed directly
- Add a safety margin to the case temperature limit and compare the cost in pump power
- Model a closed loop with a heat exchanger and several cold plates on one pump
- Replace constant heat load with a time-varying server workload profile (idle → burst → idle) and add pump speed control

---

## References

1. Xylem / Laing Thermotech, *D5 Series* catalogue BR-19B (2016) — https://hvacquick.com/catalog_files/Goulds_Laing_D5_Vario_Catalog.pdf
2. Laing D5 pump product data (3.9 m head, 1500 l/h, 23 W at 4800 rpm) — https://shop.alphacool.com/en/shop/pumpen/vpp-d5/pum-laing-d5-pump-12v-d5-vario-1/2-ig-pht-eol; PWM range 800–4800 rpm — https://www.watercoolinguk.co.uk/product/laing-flojetd5-pwm-pump-motor-12v-1200-lph/
3. Wakefield Thermal, *On-Chip Liquid Cooling* datasheet, part 133032 — https://wakefieldthermal.com/content/data_sheets/On-Chip_Liquid_Cooling-v7.pdf
4. Open Compute Project, *OAI System Liquid Cooling Guidelines* (2023) — https://www.opencompute.org/documents/oai-system-liquid-cooling-guidelines-in-ocp-template-mar-3-2023-update-pdf
5. Intel, *Xeon Platinum 8480+ Processor* specifications — https://www.intel.com/content/www/us/en/products/sku/231746/intel-xeon-platinum-8480-processor-105m-cache-2-00-ghz/specifications.html
6. Consulting-Specifying Engineer, *How to design piping systems for data centers that require liquid cooling* — https://www.csemag.com/how-to-design-piping-systems-for-data-centers-that-require-liquid-cooling/
7. Dittus, F.W. and Boelter, L.M.K. — turbulent forced convection correlation (basis for the flow-dependent `h` model)
8. MathWorks Simscape Fluids documentation — Thermal Liquid domain component library
