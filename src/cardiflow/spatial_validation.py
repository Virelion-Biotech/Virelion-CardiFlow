"""Analytical Poiseuille and Womersley benchmarks; CPU only, no clinical claim."""

import hashlib
import json
import tempfile
from itertools import pairwise
from pathlib import Path

from .models import FlowSimulationRequest
from .service import CardiFlowService


def pipe_request(tmp_path, n=32, time=None, pressure=None, initial=None):

    geometry = tmp_path / "pipe.json"
    geometry.write_text(json.dumps({"subject_id": "pipe", "radius_m": 0.003, "length_m": 0.1}))
    time = [0, 0.01, 0.1, 1, 3] if time is None else time
    pressure = [10.0] * len(time) if pressure is None else pressure
    s = {"time_s": list(time), "radial_cells": n, "inlet_pressure_pa": list(pressure)}
    if initial is not None:
        s["initial_velocity_m_s"] = list(initial)
    return FlowSimulationRequest.model_validate(
        {
            "subject_id": "pipe",
            "domain": {
                "domain_id": "pipe",
                "region": "vessel",
                "anatomy_ref": {
                    "artifact_id": "pipe-geometry",
                    "kind": "rigid_pipe_geometry",
                    "uri": geometry.as_uri(),
                    "sha256": hashlib.sha256(geometry.read_bytes()).hexdigest(),
                },
            },
            "backend": "rigid-pipe-navier-stokes-v1",
            "fluid": {"density": 1060, "dynamic_viscosity": 0.0035},
            "boundary_conditions": [
                {
                    "boundary_id": "in",
                    "kind": "pressure",
                    "region": "inlet",
                    "value": float(pressure[0]),
                    "unit": "Pa",
                },
                {
                    "boundary_id": "out",
                    "kind": "pressure",
                    "region": "outlet",
                    "value": 0,
                    "unit": "Pa",
                },
                {"boundary_id": "wall", "kind": "wall", "region": "wall"},
            ],
            "settings": s,
        }
    )


def poiseuille(tmp_path, n):
    import numpy as np

    radius, mu, gradient = 0.003, 0.0035, 100
    r = (np.arange(n) + 0.5) * radius / n
    exact = gradient / (4 * mu) * (radius**2 - r**2)
    # Long steps are acceptable here because we start close to the steady solution.
    result = CardiFlowService().simulate(
        pipe_request(tmp_path, n, np.linspace(0, 6, 3001), initial=exact)
    )
    field = np.asarray(result.series_outputs["axial_velocity_m_s"]).reshape(-1, n)[-1]
    exact_flow = np.pi * gradient * radius**4 / (8 * mu)
    exact_shear = gradient * radius / 2
    return {
        "cells": n,
        "profile_relative_error": float(np.max(abs(field - exact)) / max(exact)),
        "flow_relative_error": abs(result.series_outputs["flow_m3_s"][-1] / exact_flow - 1),
        "wall_shear_relative_error": abs(
            result.series_outputs["wall_shear_pa"][-1] / exact_shear - 1
        ),
        "momentum_residual": result.scalar_outputs["peak_momentum_residual_fraction"],
    }


def womersley(tmp_path, n=64, steps=400):
    import numpy as np
    from scipy.special import jv

    radius, rho, mu, omega, amplitude = 0.003, 1060, 0.0035, 2 * np.pi, 10
    r = (np.arange(n) + 0.5) * radius / n
    z = radius * np.sqrt(-1j * omega * rho / mu)
    profile = (amplitude / 0.1) / (1j * omega * rho) * (1 - jv(0, z * r / radius) / jv(0, z))
    time = np.linspace(0, 1, steps + 1)
    pressure = amplitude * np.cos(omega * time)
    result = CardiFlowService().simulate(
        pipe_request(tmp_path, n, time, pressure, initial=profile.real)
    )
    numeric = np.asarray(result.series_outputs["axial_velocity_m_s"]).reshape(-1, n)
    exact = np.real(np.exp(1j * omega * time[:, None]) * profile[None, :])
    wall_amplitude = (
        -mu * (amplitude / 0.1) / (1j * omega * rho) * (z / radius) * jv(1, z) / jv(0, z)
    )
    exact_wall = np.real(np.exp(1j * omega * time) * wall_amplitude)
    return {
        "cells": n,
        "steps": steps,
        "profile_relative_error": float(np.max(abs(numeric - exact)) / np.max(abs(exact))),
        "wall_shear_relative_error": float(
            np.max(abs(np.asarray(result.series_outputs["wall_shear_pa"]) - exact_wall))
            / np.max(abs(exact_wall))
        ),
        "momentum_residual": result.scalar_outputs["peak_momentum_residual_fraction"],
    }


def run_spatial_validation():
    from .pipe_flow import RigidPipeBackend

    if not RigidPipeBackend().available():
        from .backends import BackendUnavailable

        raise BackendUnavailable("Spatial validation requires pip install '.[cfd]'")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        steady = [poiseuille(path, n) for n in (16, 32, 64)]
        harmonic = [
            womersley(path, n=n, steps=steps) for n, steps in [(16, 100), (32, 200), (64, 400)]
        ]
        temporal = [womersley(path, n=256, steps=steps) for steps in (25, 50, 100)]
    checks = {
        "steady_second_order": all(
            b["flow_relative_error"] < a["flow_relative_error"] / 3.5 for a, b in pairwise(steady)
        ),
        "steady_flow_accuracy": steady[-1]["flow_relative_error"] < 0.0003,
        "steady_shear_accuracy": steady[-1]["wall_shear_relative_error"] < 1e-8,
        "harmonic_profile_accuracy": harmonic[-1]["profile_relative_error"] < 0.001,
        "harmonic_shear_accuracy": harmonic[-1]["wall_shear_relative_error"] < 0.015,
        "harmonic_refinement": all(
            b["profile_relative_error"] < a["profile_relative_error"] for a, b in pairwise(harmonic)
        ),
        "temporal_refinement": all(
            b["profile_relative_error"] < a["profile_relative_error"] for a, b in pairwise(temporal)
        ),
        "momentum_balance": max(row["momentum_residual"] for row in steady + harmonic + temporal)
        < 1e-8,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "poiseuille": steady,
        "womersley": harmonic,
        "temporal_refinement": temporal,
        "scientific_scope": "analytical numerical verification, not empirical validation",
    }
