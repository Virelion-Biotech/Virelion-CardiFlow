# CardiFlow 0.2.0 CPU audit

Audited 2026-10-07 from main `f1965c895bc4167590f25095102b94419c5a953c`. The baseline had nine passing tests. Nine new regression cases failed before fixes: endpoint advancement, tiny-step cancellation, ignored/incompatible settings, nonfinite typed outputs/fluid density, and underflow/overflow of the RC time constant.

## Numerical evidence

| Check | Result | Scope |
| --- | --- | --- |
| Constant-flow transient | Maximum error 8.88e-16 mmHg | Analytic solution with nonzero distal pressure |
| Zero-flow decay | Maximum error 1.78e-15 mmHg | Analytic exponential relaxation |
| Integrated global volume balance | Reported error 0 mL in manufactured case | Storage and independently integrated distal flow |
| Tiny interval | Correct 2e-20 mmHg increment at dt=1e-20 s | Floating-point cancellation regression |
| Harmonic refinement, 20/40/80/160 samples per period | RMSE 0.34882 / 0.17458 / 0.08738 / 0.04372 mmHg | Observed orders 0.9986 / 0.9986 / 0.9991 |
| Independent adaptive ODE | Sixteen randomized waveforms agree within 2e-9 absolute plus 2e-10 relative tolerance | Complete pressure trajectory, outflow integral and pressure mean |
| Noiseless synthetic inverse | Optimizer succeeds; maximum relative parameter error 1.73e-16 | Known initial/distal pressures; same forward model |

Results and environment versions are committed in [results.json](../validation/cpu/results.json). CI regenerates the report from code. No GPU is required.

Local verification: **71 tests passed**, **96.24% statement coverage**, source lint passed, and the built wheel passed reference validation outside the source checkout. The package dependency check passed. Core-only CI skips sixteen optional SciPy reference cases; a dedicated job installs reference dependencies.

## Product corrections

- Removed the extra advance beyond the last time sample. N samples now define N-1 intervals.
- Replaced cancellation-prone exponential subtraction and algebraic conservation identity with stable updates and integrated-volume checks.
- Added nonzero distal pressure, explicit output units, interval-volume outputs, time-weighted means and correct within-interval pressure extrema.
- Retained mechanics time origins and nonuniform sampling; verified identity/units/hashes and refused conflicting or ignored coupling inputs.
- Rejected unsupported settings/boundaries/parameters, nonfinite typed values, duplicate boundary IDs, malformed hashes and conflicting provenance.
- Added `simulate` and `validate-reference` CLI commands, atomic result-file writes, public validation API, accurate backend readiness reporting and portable file-URI decoding.
- Added independent SciPy references, manufactured validation, clean-wheel checks and Linux/Windows CI.

The exact [numerical contract and limits](SCIENTIFIC_VALIDATION.md) must accompany scientific use. There is no CFD, experimental or clinical validation claim.

Publication provenance: pending publication.
