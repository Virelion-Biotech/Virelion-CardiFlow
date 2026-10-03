from __future__ import annotations

import math
from typing import Any

from .backends import BackendUnavailable
from .models import FlowQC, FlowSimulationRequest, FlowSimulationResult


class Windkessel3ElementBackend:
    """Deterministic three-element Windkessel afterload.

    This is a reduced-order 0D reference backend, not a CFD solver. The distal
    capacitor pressure is advanced with the exact solution for piecewise-constant
    inlet flow over each time step.
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

        raw_flow = request.settings.get("inlet_flow")
        if not isinstance(raw_flow, list) or len(raw_flow) < 2:
            raise ValueError("settings.inlet_flow must contain at least two samples")
        flow = [float(value) for value in raw_flow]
        if not all(math.isfinite(value) for value in flow):
            raise ValueError("settings.inlet_flow contains non-finite values")

        dt_s = self._finite_positive(request.settings.get("dt_s"), "settings.dt_s")
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
                "scientific_scope": (
                    "reduced-order afterload reference; not CFD and not "
                    "patient-specific physiological validation"
                ),
            },
        )
