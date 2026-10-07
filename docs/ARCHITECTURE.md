# CardiFlow architecture

CardiFlow defines HeartTwin flow-domain and backend contracts. CardiAnatomy supplies domain identity, CardiMech can supply an aortic-flow waveform, and registered backends return pressure/flow artifacts and explicit QC. CardiInfer owns statistical calibration and uncertainty estimation.

The sole built-in solver is the 0D `windkessel-3element-v1` afterload. It consumes prescribed flow and three circuit parameters, with optional distal pressure. It does not consume geometry, wall deformation, fluid density or viscosity. Moving-wall CFD and spatial velocity/wall-shear fields are backend roadmap items, not implemented features.

The service checks typed result integrity, passing QC and lineage consistency. Native QC checks integrated volume balance and finite output. Neither indicates empirical or clinical accuracy. See [the numerical contract](SCIENTIFIC_VALIDATION.md).
