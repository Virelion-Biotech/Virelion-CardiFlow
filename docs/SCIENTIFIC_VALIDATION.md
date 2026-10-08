# CardiFlow numerical contract and CPU validation

## Model and units

The 0D built-in solver is `windkessel-3element-v1`, a zero-dimensional three-element afterload. It solves

$$C\,\frac{dP_c}{dt}=Q-\frac{P_c-P_d}{R_d},\qquad P_{out}=P_c+R_pQ.$$

This is the standard RCR circuit decomposition; see the governing equation in [Arthurs et al., 2020](https://doi.org/10.1186/s40323-020-00186-x) and the circuit state formulation in the [Linfa RCR example](https://linfa-vi.readthedocs.io/en/latest/content/rcr.html). These sources establish the model equation, not validation of CardiFlow.

Canonical units are pressure mmHg, volume mL and time s. `proximal_resistance` and `distal_resistance` use mmHg*s/mL; `compliance` uses mL/mmHg. Optional `distal_pressure_mmHg` defaults to zero. Initial capacitor pressure defaults to the first-flow steady state; this does not imply periodic convergence.

Flow is held at sample `Q[i]` over `[time_s[i], time_s[i+1])`. N waveform samples define N-1 intervals. The last flow sample sets the endpoint pressure jump but supplies no extra interval. `terminal_capacitor_pressure` equals the last sampled capacitor pressure. Sample pressures are right-continuous at flow jumps.

The update uses `expm1` to retain small pressure increments. Distal outflow volumes are integrated analytically, with a small-argument series to avoid cancellation. QC compares integrated inlet volume, integrated distal volume and the actual capacitor storage change on every interval. Pressure means are exact time averages of the represented piecewise-constant-flow solution; pulse pressure includes interval endpoint left limits and the final right limit. It is not restricted to maxima/minima of sampled pressures.

`time_s`, pressure and flow series contain N entries. `interval_*` volumes/storage contain N-1 entries. Every numeric output has an entry in `result.units`. Reverse flow and negative gauge pressures are mathematically permitted; the model does not enforce physiological admissibility.

## Input and coupling scope

Explicit input uses `settings.inlet_flow` with either positive `dt_s` or aligned increasing `time_s`. Optional `inlet_flow_unit` and `pressure_unit` must declare mL/s and mmHg. Mechanics coupling consumes local `mechanics_timeseries` JSON with `time_s` and `aortic_flow_ml_s`, retains the time origin, supports nonuniform intervals, verifies declared hashes, and records the actual consumed hash even when none was supplied. Declared incompatible units or subject identity fail.

A supplied `dt_s` in a mechanics request must match every interval by relative tolerance. Explicit input cannot override mechanics input. Extra boundaries, unsupported settings/parameters, moving-wall input, circulation artifacts and rheology parameters fail explicitly. Geometry and fluid density/viscosity are not used in this 0D equation; provenance reports that they were not consumed. Anatomy lineage is preserved as declared identity, not geometric/hash validation of an unused mesh.

Checked results require passing QC. The service rejects conflicting subject/backend/anatomy/mechanics lineage and revalidates typed numeric outputs returned by plugins. A backend's own QC remains its responsibility; the service cannot independently certify arbitrary third-party CFD calculations.

## Reproduction

```bash
python -m pip install -e '.[dev,reference]'
python -m pytest --cov=cardiflow --cov-report=term-missing
python -m cardiflow validate-reference
python scripts/run_cpu_validation.py
```

The package itself needs no SciPy or NumPy. They are optional dependencies for independent reference tests and the synthetic inverse study. The full report is [validation/cpu/results.json](../validation/cpu/results.json).

Verification includes steady/transient analytic solutions, zero-flow decay, tiny-step stability, integrated volume balance, smooth harmonic refinement, sixteen independent SciPy adaptive ODE comparisons, and noiseless recovery of R_p, R_d and C from a prescribed dynamic waveform with known initial/distal pressure.

## Limits

These are manufactured and synthetic numerical checks. They do not validate blood velocity fields, wall shear stress, spatial geometry, Navier–Stokes discretization, turbulence, fluid-structure interaction, patient-specific accuracy, measured-data parameter identifiability, noise robustness or clinical outcomes. These 0D checks do not assess the separate spatial backend. Version 0.3.0 adds independent spatial numerical verification in [the spatial contract](SPATIAL_REFERENCE.md); no measured validation dataset is present. The synthetic inverse experiment uses the same model for truth and fitting; it cannot establish empirical accuracy. The observed first-order waveform error comes from zero-order-hold input approximation despite exact integration of each held interval.

## Spatial numerical verification

The optional rigid-pipe backend has its own [equations, units, boundary contract, benchmarks and limitations](SPATIAL_REFERENCE.md). Its spatial numerical report is [spatial-results.json](../validation/cpu/spatial-results.json). The 0D report above is retained as historical 0.2.0 evidence.
