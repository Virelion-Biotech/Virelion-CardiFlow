# CardiFlow Colab numerical evidence — 2026-10-15

The notebook completed with return code zero in 1.817 seconds and status `NUMERICAL_ONLY`. All 21 unique archive members are retained in [`colab_numerical_2026_10_15/original`](colab_numerical_2026_10_15/original/); all 20 original artifact hashes match. Launcher hashes and the canonical protocol identity also match. Supplied launchers are archived as inert `.py.txt` files and were not executed during this review.

The 38-file snapshot matches pinned source `75c22fad2059293557bd6eb73c3c45bb16bfa6f8`; 14 current implementation/harness files match the uploaded run. The inputs are manufactured in code, consistent with empty download receipts. No independent patient dataset was used.

## Reproduction and interpretation

All Poiseuille, Womersley, momentum and manufactured RCR checks pass. Finest steady-flow relative error is 0.0244%; harmonic-profile error is 0.0465% and harmonic wall-shear error is 1.441%. RCR harmonic time orders are approximately one, as expected for its held-input update. Same-model noiseless inverse recovery passes.

The repository harness was rerun locally on CPU. Numerical result fields reproduce within relative tolerance 1e-7 and absolute tolerance 1e-10; environment-version fields differ and are retained explicitly in the fresh reports. Pass/fail flags and source hashes agree. Original and reproduced reports are separate. `REVIEW.json` identifies each pair, and `PAYLOAD_SHA256.json` covers all retained evidence.

102 local tests passed, with 97.13% statement coverage. These checks do not establish empirical or clinical validation.

## Decision and remaining scientific work

No demonstrated algorithmic defect was identified in this export. Algorithms, parameters, solver settings and acceptance thresholds remain unchanged. There is no notebook execution failure to repair.

- The spatial backend is a fully developed, axisymmetric, rigid straight-pipe reduction. These analytical controls are not general patient-specific 3D CFD or moving-wall/valve/FSI validation.
- The Womersley radial study refines both radial cells and time steps, so it does not isolate spatial order. The separate temporal study fixes 256 cells and reduces profile error, but wall-shear error nearly plateaus at 0.362%; finer time steps alone do not establish wall-shear convergence.
- Separate radial/time refinements and a boundary-flux error study could strengthen wall-shear verification. Changing only the shear output would risk inconsistency with the discrete momentum balance; this export does not demonstrate a defect warranting that change.
- RCR inverse recovery uses known initial/distal pressures and noiseless same-model observations. Independent pressure/flow data, physiological identifiability and 4D-flow/3D solver comparisons remain absent.

Reproduce from an installed checkout with the corresponding optional numerical dependencies:

```bash
python scripts/run_cpu_validation.py --output /tmp/cardiflow-cpu.json
python scripts/run_spatial_validation.py --output /tmp/cardiflow-spatial.json
```

The existing pinned notebook remains a valid record of its source revision. A passing numerical benchmark does not establish model adequacy or patient accuracy.
