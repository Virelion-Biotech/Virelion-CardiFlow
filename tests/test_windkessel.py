import hashlib
import json
import math

import pytest

from cardiflow import (
    ArtifactRef,
    CardiFlowService,
    FlowBoundaryCondition,
    FlowDomain,
    FlowSimulationRequest,
    FluidProperties,
)


def _request(flow=None):
    return FlowSimulationRequest(
        subject_id="S1",
        domain=FlowDomain(
            domain_id="systemic",
            anatomy_ref=ArtifactRef(
                artifact_id="anatomy",
                kind="reduced_order_domain",
                uri="memory://systemic",
            ),
            region="systemic_circulation",
        ),
        backend="windkessel-3element-v1",
        fluid=FluidProperties(density=1060.0, dynamic_viscosity=0.0035),
        boundary_conditions=[
            FlowBoundaryCondition(
                boundary_id="aortic_afterload",
                kind="windkessel",
                region="aorta",
                parameters={
                    "proximal_resistance": 1.0,
                    "distal_resistance": 4.0,
                    "compliance": 0.5,
                },
            )
        ],
        settings={
            "dt_s": 0.01,
            "inlet_flow": flow or [2.0] * 20,
        },
    )


def test_windkessel_backend_is_registered_and_passes_conservation_qc():
    service = CardiFlowService()
    assert "windkessel-3element-v1" in service.backends()
    result = service.simulate(_request())
    assert result.validation_status == "software_checked"
    assert result.qc is not None and result.qc.passed
    assert result.qc.mass_balance_error_fraction <= 1e-10
    assert result.scalar_outputs["mean_outlet_pressure"] == pytest.approx(10.0)
    assert result.scalar_outputs["pulse_pressure"] == pytest.approx(0.0)
    assert all(value == pytest.approx(8.0) for value in result.series_outputs["capacitor_pressure"])


def test_windkessel_transient_is_finite_and_relaxes_toward_new_steady_state():
    result = CardiFlowService().simulate(_request([1.0] * 5 + [2.0] * 100))
    pressure = result.series_outputs["capacitor_pressure"]
    assert all(math.isfinite(value) for value in pressure)
    assert pressure[-1] > pressure[5]
    assert pressure[-1] < 8.0
    assert result.qc is not None and result.qc.passed


def test_windkessel_rejects_invalid_parameterization():
    request = _request()
    request.boundary_conditions[0].parameters["compliance"] = 0.0
    with pytest.raises(ValueError, match="compliance"):
        CardiFlowService().simulate(request)


def test_windkessel_consumes_verified_cardimech_aortic_flow(tmp_path):
    mechanics = tmp_path / "mechanics.json"
    mechanics.write_text(
        json.dumps(
            {
                "time_s": [0.0, 0.01, 0.02, 0.03],
                "aortic_flow_ml_s": [1.0, 2.0, 3.0, 2.0],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(mechanics.read_bytes()).hexdigest()

    request = _request()
    request.settings = {}
    request.mechanics_ref = ArtifactRef(
        artifact_id="mechanics-timeseries",
        kind="mechanics_timeseries",
        uri=mechanics.resolve().as_uri(),
        sha256=digest,
    )
    result = CardiFlowService().simulate(request)
    assert result.series_outputs["inlet_flow"] == [1.0, 2.0, 3.0, 2.0]
    assert result.provenance["coupling_mode"] == "mechanics_aortic_flow"
    assert result.provenance["mechanics_artifact_id"] == "mechanics-timeseries"


def test_windkessel_refuses_to_bypass_declared_mechanics_coupling(tmp_path):
    mechanics = tmp_path / "mechanics.json"
    mechanics.write_text(
        json.dumps(
            {
                "time_s": [0.0, 0.01],
                "aortic_flow_ml_s": [1.0, 1.0],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    request = _request()
    request.mechanics_ref = ArtifactRef(
        artifact_id="mechanics-timeseries",
        kind="mechanics_timeseries",
        uri=mechanics.resolve().as_uri(),
    )
    with pytest.raises(ValueError, match="either settings.inlet_flow or mechanics_ref"):
        CardiFlowService().simulate(request)
