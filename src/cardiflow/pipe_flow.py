"""Fully developed, axisymmetric rigid-pipe Navier–Stokes reference solver.

rho du/dt = G(t) + mu/r d/dr(r du/dr). Annular finite volumes,
no-slip wall, symmetry at the axis, Crank–Nicolson in time. SI units.
This restricted spatial CFD model is not a general anatomy-mesh solver.
"""

from __future__ import annotations

import hashlib
import json
import math

from .backends import BackendUnavailable
from .models import FlowQC, FlowSimulationRequest, FlowSimulationResult
from .reduced_order import Windkessel3ElementBackend, local_artifact_path


class RigidPipeBackend:
    name = "rigid-pipe-navier-stokes-v1"

    def available(self) -> bool:
        try:
            import numpy  # noqa: F401
            import scipy.linalg  # noqa: F401
        except ImportError:
            return False
        return True

    def simulate(self, request: FlowSimulationRequest) -> FlowSimulationResult:
        if not self.available():
            raise BackendUnavailable("Rigid pipe requires pip install '.[cfd]'")
        import numpy as np
        from scipy.linalg import solve_banded

        finite = Windkessel3ElementBackend._finite
        s = request.settings
        allowed = {
            "time_s",
            "radial_cells",
            "inlet_pressure_pa",
            "outlet_pressure_pa",
            "initial_velocity_m_s",
        }
        if set(s) - allowed:
            raise ValueError(f"Unsupported rigid-pipe settings: {sorted(set(s) - allowed)}")
        if request.mechanics_ref or request.circulation_ref or request.domain.moving_wall_ref:
            raise ValueError("Rigid pipe does not support mechanics, circulation or moving walls")
        if request.domain.mesh_ref:
            raise ValueError("Rigid pipe generates an annular grid; mesh_ref is unsupported")
        fluid = request.fluid
        if (
            fluid.model != "newtonian"
            or fluid.parameters
            or fluid.density_unit != "kg/m^3"
            or fluid.viscosity_unit != "Pa*s"
        ):
            raise ValueError("Rigid pipe requires Newtonian fluid in kg/m^3 and Pa*s")
        ref = request.domain.anatomy_ref
        if ref.kind != "rigid_pipe_geometry":
            raise ValueError("anatomy_ref must reference rigid_pipe_geometry")
        raw = local_artifact_path(ref).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if ref.sha256 and ref.sha256.lower() != digest:
            raise ValueError("Geometry SHA-256 verification failed")
        g = json.loads(raw)
        if not isinstance(g, dict) or set(g) != {"subject_id", "radius_m", "length_m"}:
            raise ValueError("Geometry requires only subject_id, radius_m and length_m")
        if g["subject_id"] != request.subject_id or (
            ref.metadata.get("subject_id", request.subject_id) != request.subject_id
        ):
            raise ValueError("Geometry belongs to a different subject")
        radius = finite(g["radius_m"], "radius_m", positive=True)
        length = finite(g["length_m"], "length_m", positive=True)
        n = s.get("radial_cells", 64)
        if isinstance(n, bool) or not isinstance(n, int) or not 4 <= n <= 512:
            raise ValueError("radial_cells must be an integer from 4 to 512")
        boundaries = {(b.region, b.kind): b for b in request.boundary_conditions}
        if len(request.boundary_conditions) != 3 or set(boundaries) != {
            ("inlet", "pressure"),
            ("outlet", "pressure"),
            ("wall", "wall"),
        }:
            raise ValueError("Require inlet/outlet pressure and stationary wall boundaries")
        for b in boundaries.values():
            if b.waveform_ref or b.parameters:
                raise ValueError("Boundary waveform_ref and parameters are unsupported")
            if b.kind == "pressure" and (b.value is None or b.unit != "Pa"):
                raise ValueError("Pressure boundary requires scalar value in Pa")
            if b.kind == "wall" and (b.value is not None or b.unit is not None):
                raise ValueError("Wall boundary must be stationary no-slip without scalar/unit")
        time = s.get("time_s")
        if not isinstance(time, list) or not 2 <= len(time) <= 20000 or len(time) * n > 2000000:
            raise ValueError("time_s requires 2..20000 samples and <=2000000 field values")
        pressures = []
        for region in ["inlet", "outlet"]:
            p = s.get(f"{region}_pressure_pa", [boundaries[(region, "pressure")].value] * len(time))
            p, validated_time = Windkessel3ElementBackend._waveform(p, time)
            if p[0] != boundaries[(region, "pressure")].value:
                raise ValueError("Pressure waveform first sample must match boundary scalar")
            pressures.append(np.asarray(p))
        time = np.asarray(validated_time)
        gradient = (pressures[0] - pressures[1]) / length
        dr = radius / n
        faces = np.linspace(0, radius, n + 1)
        r = (faces[:-1] + faces[1:]) / 2
        area = math.pi * (faces[1:] ** 2 - faces[:-1] ** 2)
        rho, mu = fluid.density, fluid.dynamic_viscosity
        lo = 2 * math.pi * mu * faces[:-1] / (rho * area * dr)
        hi = 2 * math.pi * mu * faces[1:] / (rho * area * dr)
        hi[-1] *= 2  # half-cell wall distance, u(R)=0
        diagonal = -(lo + hi)
        initial = s.get("initial_velocity_m_s", [0.0] * n)
        if not isinstance(initial, list) or len(initial) != n:
            raise ValueError("initial_velocity_m_s must have radial_cells values")
        u = np.asarray([finite(v, "initial_velocity_m_s") for v in initial])
        profiles, flow, shear, residuals = [u.copy()], [float(area @ u)], [2 * mu * u[-1] / dr], []
        for k, dt in enumerate(np.diff(time)):
            operator = diagonal * u
            operator[1:] += lo[1:] * u[:-1]
            operator[:-1] += hi[:-1] * u[1:]
            band = np.zeros((3, n))
            band[0, 1:] = -dt / 2 * hi[:-1]
            band[1] = 1 - dt / 2 * diagonal
            band[2, :-1] = -dt / 2 * lo[1:]
            force = (gradient[k] + gradient[k + 1]) / 2
            new = solve_banded((1, 1), band, u + dt / 2 * operator + dt * force / rho)
            tau = 2 * mu * new[-1] / dr
            inertia = rho * float(area @ (new - u)) / dt
            drive = force * math.pi * radius**2
            friction = 2 * math.pi * radius * (shear[-1] + tau) / 2
            residuals.append(
                abs(inertia - drive + friction)
                / max(abs(inertia) + abs(drive) + abs(friction), 1e-30)
            )
            u = new
            profiles.append(u.copy())
            flow.append(float(area @ u))
            shear.append(float(tau))
        fields = np.asarray(profiles)
        if not np.isfinite(fields).all() or not np.isfinite(residuals).all():
            raise ValueError("Non-finite rigid-pipe numerical output")
        reynolds = max(abs(np.asarray(flow))) * 2 * rho / (math.pi * radius * mu)
        if reynolds >= 2000:
            raise ValueError("Reynolds >= 2000 exceeds conservative laminar reference scope")
        # Biomarkers apply to the supplied observation window, not an assumed cardiac cycle.
        dt = np.diff(time)
        duration = time[-1] - time[0]
        integral = lambda values: float(
            np.sum(dt * (np.asarray(values)[:-1] + np.asarray(values)[1:]) / 2)
        )
        # Integrate |tau| exactly under piecewise-linear interpolation, including reversals.
        abs_integral = 0.0
        for a, b, step in zip(shear[:-1], shear[1:], dt):
            abs_integral += step * (
                (a * a + b * b) / (2 * (abs(a) + abs(b))) if a * b < 0 else (abs(a) + abs(b)) / 2
            )
        tawss = abs_integral / duration
        scalars = {
            "mean_flow_m3_s": integral(flow) / duration,
            "time_averaged_wall_shear_pa": tawss,
            "peak_reynolds_number": float(reynolds),
            "duration_s": float(duration),
            "integrated_flow_volume_m3": integral(flow),
            "peak_momentum_residual_fraction": float(max(residuals)),
        }
        if abs_integral > 0:
            scalars["oscillatory_shear_index"] = max(
                0.0, min(0.5, 0.5 * (1 - abs(integral(shear)) / abs_integral))
            )
        series = {
            "time_s": time.tolist(),
            "radius_m": r.tolist(),
            "axial_velocity_m_s": fields.ravel().tolist(),
            "flow_m3_s": flow,
            "wall_shear_pa": [float(v) for v in shear],
            "inlet_pressure_pa": pressures[0].tolist(),
            "outlet_pressure_pa": pressures[1].tolist(),
            "momentum_residual_fraction": [float(v) for v in residuals],
        }
        units = {
            "time_s": "s",
            "radius_m": "m",
            "axial_velocity_m_s": "m/s",
            "flow_m3_s": "m^3/s",
            "wall_shear_pa": "Pa",
            "inlet_pressure_pa": "Pa",
            "outlet_pressure_pa": "Pa",
            "momentum_residual_fraction": "1",
            "mean_flow_m3_s": "m^3/s",
            "time_averaged_wall_shear_pa": "Pa",
            "peak_reynolds_number": "1",
            "duration_s": "s",
            "integrated_flow_volume_m3": "m^3",
            "peak_momentum_residual_fraction": "1",
            "oscillatory_shear_index": "1",
        }
        passed = max(residuals) < 1e-8
        return FlowSimulationResult(
            subject_id=request.subject_id,
            backend=self.name,
            scalar_outputs=scalars,
            series_outputs=series,
            units=units,
            validation_status="software_checked",
            qc=FlowQC(
                passed=passed,
                converged=passed,
                checks={"finite_outputs": True, "discrete_momentum_balance": passed},
                metrics={"radial_cells": n},
                warnings=[
                    "QC is discrete balance, not mesh/time convergence or empirical validation.",
                    "Biomarkers describe the supplied window; periodicity is not assumed.",
                    "OSI is undefined and omitted when wall shear is identically zero.",
                ],
            ),
            provenance={
                "anatomy_sha256": digest,
                "anatomy_consumed": True,
                "fluid_properties_consumed": True,
                "moving_wall_consumed": False,
                "integration": "annular finite volume / Crank-Nicolson; linear pressure forcing",
                "field_shape": [len(time), n],
                "field_layout": "time-major",
                "wall_shear_convention": "positive for positive axial flow; fluid-on-wall",
                "scientific_scope": "fully developed laminar rigid circular pipe; no general mesh",
                "radius_m": radius,
                "length_m": length,
            },
        )
