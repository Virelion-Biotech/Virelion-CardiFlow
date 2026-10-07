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

CardiFlow does **not** run a placeholder CFD model. It includes a deterministic `windkessel-3element-v1` reduced-order 0D afterload backend for software integration and calibration plumbing; this is not CFD and is not patient-specific physiological validation. Unsupported numerical backends fail closed.

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
