"""CPU manufactured numerical checks; no empirical or clinical validation claim."""

from __future__ import annotations

import math
from itertools import pairwise

from .models import (
    ArtifactRef,
    FlowBoundaryCondition,
    FlowDomain,
    FlowSimulationRequest,
    FluidProperties,
)
from .service import CardiFlowService


def validation_request(flow, *, dt_s=0.01, initial=0.0, rp=0.3, rd=1.2, compliance=1.5, distal=0.0):
    return FlowSimulationRequest(
        subject_id="manufactured",
        domain=FlowDomain(
            domain_id="0d",
            anatomy_ref=ArtifactRef(
                artifact_id="manufactured-domain", kind="reduced_order_domain", uri="memory://0d"
            ),
            region="afterload",
        ),
        backend="windkessel-3element-v1",
        fluid=FluidProperties(density=1060, dynamic_viscosity=0.0035),
        boundary_conditions=[
            FlowBoundaryCondition(
                boundary_id="afterload",
                kind="windkessel",
                region="aorta",
                parameters={
                    "proximal_resistance": rp,
                    "distal_resistance": rd,
                    "compliance": compliance,
                    "distal_pressure_mmHg": distal,
                },
            )
        ],
        settings={"inlet_flow": list(flow), "dt_s": dt_s, "initial_capacitor_pressure": initial},
    )


def run_reference_validation():
    service = CardiFlowService()
    request = validation_request([3.0] * 51, initial=7, distal=4)
    result = service.simulate(request)
    tau = 1.2 * 1.5
    equilibrium = 4 + 1.2 * 3
    expected = [
        equilibrium + (7 - equilibrium) * math.exp(-t / tau)
        for t in result.series_outputs["time_s"]
    ]
    constant_error = max(
        abs(a - b) for a, b in zip(result.series_outputs["capacitor_pressure"], expected)
    )
    volume_error = abs(
        result.scalar_outputs["inlet_volume"]
        - result.scalar_outputs["distal_outflow_volume"]
        - result.scalar_outputs["capacitor_storage_change"]
    )
    decay = service.simulate(validation_request([0] * 51, initial=7, distal=4))
    decay_error = max(
        abs(p - (4 + 3 * math.exp(-t / tau)))
        for t, p in zip(decay.series_outputs["time_s"], decay.series_outputs["capacitor_pressure"])
    )
    tiny = service.simulate(validation_request([1, 1], dt_s=1e-20, initial=0, rd=4, compliance=0.5))
    tiny_relative = abs(tiny.series_outputs["capacitor_pressure"][1] / 2e-20 - 1)
    refinements = []
    omega = 2 * math.pi
    for n in (20, 40, 80, 160):
        dt = 1 / n
        times = [i * dt for i in range(2 * n + 1)]
        flow = [60 + 30 * math.sin(omega * t) for t in times]

        def exact(t):
            return 1.2 * 60 + 1.2 * 30 / (1 + (omega * tau) ** 2) * (
                math.sin(omega * t) - omega * tau * math.cos(omega * t)
            )

        simulation = service.simulate(validation_request(flow, dt_s=dt, initial=exact(0)))
        errors = [
            p - exact(t) for t, p in zip(times, simulation.series_outputs["capacitor_pressure"])
        ]
        rmse = math.sqrt(math.fsum(e * e for e in errors) / len(errors))
        refinements.append({"samples_per_period": n, "dt_s": dt, "rmse_mmHg": rmse})
    orders = [math.log2(a["rmse_mmHg"] / b["rmse_mmHg"]) for a, b in pairwise(refinements)]
    repeat = service.simulate(request).model_dump(mode="json") == result.model_dump(mode="json")
    checks = {
        "constant_flow_exact": constant_error < 1e-11,
        "zero_flow_decay_exact": decay_error < 1e-11,
        "integrated_volume_balance": volume_error < 1e-11,
        "tiny_step_stability": tiny_relative < 1e-12,
        "first_order_smooth_waveform_refinement": all(0.9 < o < 1.1 for o in orders),
        "deterministic": repeat,
        "terminal_time_alignment": result.scalar_outputs["terminal_capacitor_pressure"]
        == result.series_outputs["capacitor_pressure"][-1],
    }
    return {
        "schema_version": "cardiflow-cpu-validation-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "metrics": {
            "constant_flow_max_error_mmHg": constant_error,
            "zero_flow_max_error_mmHg": decay_error,
            "global_volume_balance_error_mL": volume_error,
            "tiny_step_relative_error": tiny_relative,
        },
        "harmonic_refinement": refinements,
        "observed_orders": orders,
        "scientific_boundary": "Manufactured 0D numerical verification; no CFD, measured-data or clinical validation.",
    }
