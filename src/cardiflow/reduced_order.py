from __future__ import annotations

import hashlib
import json
import math
from itertools import pairwise
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .backends import BackendUnavailable
from .models import ArtifactRef, FlowQC, FlowSimulationRequest, FlowSimulationResult


class Windkessel3ElementBackend:
    """Deterministic three-element Windkessel afterload.

    This is a reduced-order 0D reference backend, not a CFD solver. The distal
    capacitor pressure is advanced with the exact solution for piecewise-constant
    inlet flow over each time step.

    The backend can consume the mechanics_timeseries artifact emitted by
    CardiMech and use aortic_flow_ml_s as its inlet waveform. That makes the
    built-in reference path a real Mechanics-to-Flow handoff.
    """

    name = "windkessel-3element-v1"

    def available(self) -> bool:
        return True

    @staticmethod
    def _finite_positive(value: Any, name: str) -> float:
        number = float(value)
        if not math.isfinite(number) or number <= 0:
            raise ValueError(f"{name} must be finite and > 0")
        return number

    @staticmethod
    def _local_path(ref: ArtifactRef) -> Path:
        parsed = urlparse(ref.uri)
        if parsed.scheme not in {"", "file"}:
            raise ValueError(
                "windkessel-3element-v1 requires local/file mechanics artifacts"
            )
        raw = unquote(parsed.path) if parsed.scheme == "file" else ref.uri
        return Path(raw).expanduser().resolve()

    @classmethod
    def _mechanics_inlet(cls, ref: ArtifactRef) -> tuple[list[float], float]:
        path = cls._local_path(ref)
        if not path.is_file():
            raise FileNotFoundError(f"Mechanics artifact does not exist: {path}")
        if ref.sha256 is not None:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest.lower() != ref.sha256.lower():
                raise ValueError("Mechanics artifact SHA-256 verification failed")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("Mechanics timeseries artifact must contain a JSON object")

        raw_flow = payload.get("aortic_flow_ml_s")
        raw_time = payload.get("time_s")
        if not isinstance(raw_flow, list) or len(raw_flow) < 2:
            raise ValueError(
                "Mechanics artifact requires at least two aortic_flow_ml_s samples"
            )
        if not isinstance(raw_time, list) or len(raw_time) != len(raw_flow):
            raise ValueError(
                "Mechanics artifact requires time_s aligned with aortic_flow_ml_s"
            )

        flow = [float(value) for value in raw_flow]
        time = [float(value) for value in raw_time]
        if not all(math.isfinite(value) for value in flow + time):
            raise ValueError("Mechanics coupling artifact contains non-finite values")

        deltas = [right - left for left, right in pairwise(time)]
        if not deltas or any(delta <= 0 or not math.isfinite(delta) for delta in deltas):
            raise ValueError("Mechanics time_s must be strictly increasing")
        dt_s = sum(deltas) / len(deltas)
        tolerance = max(1e-9, abs(dt_s) * 1e-6)
        if any(abs(delta - dt_s) > tolerance for delta in deltas):
            raise ValueError(
                "windkessel-3element-v1 requires a uniformly sampled mechanics waveform"
            )
        return flow, dt_s

    def simulate(self, request: FlowSimulationRequest) -> FlowSimulationResult:
        windkessels = [
            item for item in request.boundary_conditions if item.kind == "windkessel"
        ]
        if len(windkessels) != 1:
            raise BackendUnavailable(
                "windkessel-3element-v1 requires exactly one windkessel boundary"
            )
        boundary = windkessels[0]
        params = boundary.parameters
        rp = self._finite_positive(
            params.get("proximal_resistance"), "proximal_resistance"
        )
        rd = self._finite_positive(
            params.get("distal_resistance"), "distal_resistance"
        )
        compliance = self._finite_positive(params.get("compliance"), "compliance")

        explicit_flow = request.settings.get("inlet_flow")
        if explicit_flow is not None and request.mechanics_ref is not None:
            raise ValueError(
                "Provide either settings.inlet_flow or mechanics_ref, not both; "
                "the backend refuses to silently bypass a declared mechanics coupling"
            )

        coupling_mode = "explicit_inlet_flow"
        mechanics_artifact_id = None
        if request.mechanics_ref is not None:
            flow, mechanics_dt_s = self._mechanics_inlet(request.mechanics_ref)
            raw_dt = request.settings.get("dt_s")
            if raw_dt is None:
                dt_s = mechanics_dt_s
            else:
                dt_s = self._finite_positive(raw_dt, "settings.dt_s")
                tolerance = max(1e-9, abs(mechanics_dt_s) * 1e-6)
                if abs(dt_s - mechanics_dt_s) > tolerance:
                    raise ValueError(
                        "settings.dt_s disagrees with the mechanics artifact sampling interval"
                    )
            coupling_mode = "mechanics_aortic_flow"
            mechanics_artifact_id = request.mechanics_ref.artifact_id
        else:
            if not isinstance(explicit_flow, list) or len(explicit_flow) < 2:
                raise ValueError(
                    "Provide settings.inlet_flow with at least two samples or a mechanics_ref"
                )
            flow = [float(value) for value in explicit_flow]
            dt_s = self._finite_positive(request.settings.get("dt_s"), "settings.dt_s")

        if not all(math.isfinite(value) for value in flow):
            raise ValueError("Inlet flow contains non-finite values")

        tau_s = rd * compliance
        decay = math.exp(-dt_s / tau_s)

        initial = request.settings.get("initial_capacitor_pressure")
        pc = float(initial) if initial is not None else flow[0] * rd
        if not math.isfinite(pc):
            raise ValueError("initial_capacitor_pressure must be finite")

        capacitor_pressure: list[float] = []
        outlet_pressure: list[float] = []
        conservation_residuals: list[float] = []
        for q_in in flow:
            pc_inf = q_in * rd
            derivative = (pc_inf - pc) / tau_s
            q_distal = pc / rd
            residual = q_in - q_distal - compliance * derivative
            conservation_residuals.append(residual)
            pc_next = pc_inf + (pc - pc_inf) * decay
            capacitor_pressure.append(pc)
            outlet_pressure.append(pc + rp * q_in)
            pc = pc_next

        if not all(math.isfinite(value) for value in outlet_pressure + capacitor_pressure):
            raise RuntimeError("Windkessel solver produced non-finite output")

        scale = max(max(abs(value) for value in flow), 1e-12)
        mass_error = max(abs(value) for value in conservation_residuals) / scale
        mass_ok = mass_error <= 1e-10
        mean_flow = sum(flow) / len(flow)
        mean_pressure = sum(outlet_pressure) / len(outlet_pressure)
        pulse_pressure = max(outlet_pressure) - min(outlet_pressure)

        qc = FlowQC(
            passed=mass_ok,
            converged=True,
            mass_balance_error_fraction=mass_error,
            checks={
                "finite_outputs": True,
                "mass_conservation": mass_ok,
                "positive_time_constant": tau_s > 0,
            },
            metrics={
                "time_constant_s": tau_s,
                "dt_over_tau": dt_s / tau_s,
            },
        )
        return FlowSimulationResult(
            subject_id=request.subject_id,
            backend=self.name,
            scalar_outputs={
                "mean_inlet_flow": mean_flow,
                "mean_outlet_pressure": mean_pressure,
                "pulse_pressure": pulse_pressure,
                "terminal_capacitor_pressure": pc,
            },
            series_outputs={
                "inlet_flow": flow,
                "capacitor_pressure": capacitor_pressure,
                "outlet_pressure": outlet_pressure,
            },
            qc=qc,
            validation_status="software_checked",
            provenance={
                "model": "three-element Windkessel",
                "integration": "exact piecewise-constant RC update",
                "boundary_id": boundary.boundary_id,
                "coupling_mode": coupling_mode,
                "mechanics_artifact_id": mechanics_artifact_id,
                "moving_wall_consumed": False,
                "scientific_scope": (
                    "reduced-order afterload reference; not CFD and not "
                    "patient-specific physiological validation"
                ),
            },
        )
