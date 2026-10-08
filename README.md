# Virelion-CardiFlow

Hemodynamics and flow-simulation layer for the Virelion HeartTwin stack.

CardiFlow defines contracts for chamber/vascular flow domains, fluid properties, inlet/outlet/wall boundary conditions, reduced-order and CFD backends, coupling to CardiMech and circulation models, flow-derived biomarkers, solver QC, and HeartTwin integration.

## Scope

CardiFlow owns:
- patient-specific flow-domain references from CardiAnatomy;
- blood/fluid-property contracts;
- inlet, outlet, wall, pressure, flow, resistance and Windkessel conditions;
- optional moving-wall inputs from CardiMech;
- reduced-order or CFD execution through registered backends;
- velocity, pressure, wall-shear and derived-hemodynamic outputs;
- conservation and numerical-quality checks;
- calibration-ready outputs for CardiInfer.

CardiFlow includes two real CPU solvers: the tested `windkessel-3element-v1` 0D three-element afterload, and the optional `rigid-pipe-navier-stokes-v1` spatial reference for fully developed pulsatile flow in a rigid circular vessel. The 0D reference implementation is nearly complete within its stated scope, with independent numerical tests and committed CPU results. The spatial backend adds radial velocity profiles, wall shear, pressure/flow outputs and independent analytical verification. Neither establishes patient-specific physiological validity. Unsupported backends and inputs fail closed.

| Capability | Current implementation |
| --- | --- |
| 0D afterload and mechanics waveform handoff | Tested Windkessel solver |
| Spatial pulsatile vessel flow | Restricted rigid circular pipe, CPU finite volumes |
| Velocity, wall shear, TAWSS and OSI | Native pipe outputs with units and numerical QC |
| General patient-specific CFD, branching and moving-wall/FSI | Not implemented |

The earlier approximately 75% estimate concerned the broader HeartTwin hemodynamics role of the 0D-only implementation; it was qualitative, not a measured completeness score. See [spatial scope, validation and remaining work](docs/SPATIAL_REFERENCE.md).

## Quick start

```bash
python -m pip install -e '.[dev]'
pytest -q
cardiflow doctor
cardiflow validate-reference
cardiflow simulate examples/windkessel-request.json --output outputs/result.json
```

## Scientific boundary

Software-valid CFD artifacts do not establish physiological fidelity, clinically meaningful flow biomarkers, or patient-specific predictive validity.

## License

AGPL-3.0-or-later.

## CPU verification

Version 0.2.0 fixes endpoint timing, floating-point cancellation, integrated-volume QC, waveform means/extrema, coupling integrity, and strict unsupported-input handling. See the [CPU audit](docs/CPU_AUDIT.md) and [scientific contract](docs/SCIENTIFIC_VALIDATION.md).

```bash
python -m pip install -e '.[dev,reference]'
python -m pytest --cov=cardiflow --cov-report=term-missing
python scripts/run_cpu_validation.py
```

SciPy/NumPy are optional reference dependencies. All validation runs on CPU. Explicit input values use mL/s, mmHg, seconds, mmHg*s/mL resistance and mL/mmHg compliance.

Compatibility correction: waveform samples are time points, not interval counts. N samples now integrate N-1 intervals, and pressure/flow means are duration-weighted. Previously ignored settings and coupling inputs now fail explicitly.

## Spatial reference quick start

```bash
python -m pip install -e '.[dev,cfd]'
python -m cardiflow validate-spatial
python scripts/run_spatial_validation.py
python -m cardiflow simulate examples/rigid-pipe-request.json --output outputs/pipe-result.json
```

Version 0.3.0 preserves the 0D solver and adds the optional spatial backend, geometry consumption/checksums, SI field units, momentum QC and independent Poiseuille/Womersley refinement benchmarks. Run the example from the repository root. No GPU is needed.
