# CardiFlow architecture

CardiFlow defines HeartTwin flow-domain and backend contracts. CardiAnatomy supplies domain identity, CardiMech can supply an aortic-flow waveform, and registered backends return pressure/flow artifacts and explicit QC. CardiInfer owns statistical calibration and uncertainty estimation.

The dependency-light built-in solver is the 0D `windkessel-3element-v1` afterload. It consumes prescribed flow and three circuit parameters, with optional distal pressure. It does not consume geometry, wall deformation, fluid density or viscosity. The optional `rigid-pipe-navier-stokes-v1` backend consumes explicit local circular-vessel geometry and fluid properties and returns radial velocity profiles and wall shear. It uses annular finite volumes and Crank–Nicolson integration. General mesh CFD, branching, two-way circulation coupling and moving walls remain roadmap items. See [the spatial reference contract](SPATIAL_REFERENCE.md).

The service checks typed result integrity, passing QC and lineage consistency. Native QC checks integrated volume balance and finite output. Neither indicates empirical or clinical accuracy. See [the numerical contract](SCIENTIFIC_VALIDATION.md).
