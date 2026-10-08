# Spatial CPU reference: rigid circular vessel

Version 0.3.0 adds `rigid-pipe-navier-stokes-v1`. This is a spatially discretized, restricted Navier–Stokes solver, not a generic chamber or arterial-tree CFD engine. It models incompressible, Newtonian, fully developed axial flow in a straight, rigid circular tube. Axial convection vanishes under this assumption; radial velocity is zero and continuity is satisfied by axial invariance. It cannot model inlet development, branching, curvature, stenosis, wall motion or turbulence.

## Governing equation and numerical method

With G(t) = (P_in(t) - P_out(t))/L, the equation is

$$\rho\partial_t u = G(t) + \frac{\mu}{r}\partial_r(r\partial_r u).$$

The axis uses symmetry; the wall uses no slip. Annular finite volumes have exact shell areas, with velocities at radial cell centers. Viscous fluxes use center differences and a half-cell distance at the wall. Crank–Nicolson advances the tridiagonal system with linearly interpolated pressure forcing. Nonuniform timestamps are supported. N times produce N profiles and N-1 momentum residuals. No extra terminal step occurs.

Crank–Nicolson is stable but does not guarantee positivity or adequate resolution with large time steps. Abrupt forcing and large steps can produce numerical ringing. Users must refine both space and time for each new case; passing balance QC alone is not an accuracy certificate.

Pressure is linear along the tube between the reported inlet/outlet pressures. `axial_velocity_m_s` contains the computed radial profiles, flattened in time-major order; `provenance.field_shape` supplies [number of times, radial cells]. `radius_m` contains cell-center coordinates. This is not a 3D mesh artifact.

## Inputs and provenance

Install `.[cfd]` for NumPy/SciPy. The original 0D backend remains dependency-light. `doctor` reports availability of each backend independently.

`anatomy_ref.kind` must be `rigid_pipe_geometry`, referencing a local JSON object with exactly `subject_id`, positive `radius_m` and positive `length_m`. This explicit idealized geometry is not automatically inferred from patient anatomy. Subject identity is checked, an optional supplied SHA-256 is verified, and the actual consumed hash is always recorded. A mismatching anatomy hash also fails service lineage checks.

Exactly three boundaries are required: pressure at region `inlet`, pressure at region `outlet`, and stationary wall at region `wall`. Scalar pressures must be in Pa. Optional aligned `settings.inlet_pressure_pa` and `outlet_pressure_pa` arrays start at the corresponding boundary scalar. `settings.time_s` is mandatory. Density and dynamic viscosity use kg/m³ and Pa·s and are actually consumed. Unknown settings and unsupported couplings fail explicitly.

`radial_cells` defaults to 64 and must be an integer from 4 to 512. Time arrays require 2–20,000 samples, with at most 2,000,000 profile values. `initial_velocity_m_s` is an optional radial profile of matching length; it defaults to rest. The solver rejects peak bulk Reynolds number >= 2000 as a conservative scope guard. This cutoff does not prove laminarity of physiological flow.

Mechanics/circulation references, moving walls, arbitrary mesh references and non-Newtonian models are unsupported. The two native backends are separate: this release does not provide two-way pipe/Windkessel coupling or fluid–structure interaction.

## Outputs and quality control

- Integrated volumetric flow Q = sum(A_i u_i), in m³/s.
- Signed fluid-on-wall axial shear tau = 2 mu u_last / dr, in Pa; positive for positive axial flow.
- Mean flow, integrated flow volume, peak bulk Reynolds number and duration.
- Time-averaged absolute wall shear (TAWSS) and oscillatory shear index OSI = (1 - |integral(tau)| / integral(|tau|))/2.

Biomarkers describe the entire supplied observation window, including any startup transient. They are cycle metrics only if the caller supplies a suitable converged cycle. Absolute shear is integrated across zero crossings under piecewise-linear interpolation. OSI is undefined and omitted for identically zero shear; no infinite residence-time surrogate is emitted. Shear is a scalar in this axisymmetric model, not a multidirectional wall-shear vector.

QC checks finite output and discrete integrated axial momentum balance against pressure drive and wall friction. It does not report an invented mass residual: continuity follows from the fully developed ansatz. `converged` indicates successful linear solves/balance, not mesh refinement or periodic convergence. Results remain `software_checked`; empirical validation is absent.

## Independent numerical evidence

Poiseuille's analytic parabolic profile and flow provide the steady benchmark. Pulsatile verification evaluates the independent complex-Bessel Womersley solution from [Womersley (1955)](https://doi.org/10.1113/jphysiol.1955.sp005276), rather than using CardiFlow to generate a synthetic truth. The analytical velocity amplitude is

$$\hat u(r)=\frac{\hat G}{i\omega\rho}\left[1-\frac{J_0(zr/R)}{J_0(z)}\right],\quad z=R\sqrt{-i\omega\rho/\mu}.$$

Tests compare both velocity and analytic wall shear, include radial/time refinement, flow reversal, zero shear, corrupted geometry hashes, incompatible units and unsupported inputs. The benchmark's analytic initial velocity is stated explicitly; normal runs default to rest.

| Benchmark | Finest-case relative error |
| --- | ---: |
| Poiseuille flow, 64 cells | 0.0244% |
| Poiseuille velocity profile, 64 cells | 0.00610% |
| Womersley velocity profile, 64 cells / 400 intervals | 0.0465% |
| Womersley wall shear, same case, including initial wall derivative error | 1.441% |

Steady flow error decreases approximately fourfold per radial doubling. Harmonic velocity error decreases with coupled radial/time refinement. At 256 cells, 25/50/100 intervals give about 0.697/0.175/0.0442% velocity error. This is evidence for these manufactured cases, not all parameter combinations.

```bash
python -m pip install -e '.[dev,cfd]'
python -m cardiflow validate-spatial
python scripts/run_spatial_validation.py
python -m cardiflow simulate examples/rigid-pipe-request.json --output outputs/pipe-result.json
```

Run example commands from the repository root. [Committed benchmark results](../validation/cpu/spatial-results.json) include dependency versions and source SHA-256 hashes. CI reproduces the spatial report alongside the retained 0D CPU report. The SciPy [banded solver](https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.solve_banded.html) provides linear algebra, not the physical model or benchmark truth.

## Remaining broader HeartTwin work

General anatomical meshing and boundary labeling, 3D flow, moving-wall/FSI, branched circulation and 0D–spatial coupling, mesh-field artifacts, measured-flow validation and uncertainty propagation remain open. No percentage is claimed without a fixed acceptance checklist. The historical approximately 75% broader-role estimate was a qualitative assessment of the 0D-only release, not measured validation coverage.
