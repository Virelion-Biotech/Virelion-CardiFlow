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
```

## Scientific boundary

Software-valid CFD artifacts do not establish physiological fidelity, clinically meaningful flow biomarkers, or patient-specific predictive validity.

## License

AGPL-3.0-or-later.
