import pytest

from cardiflow import (
    ArtifactRef,
    FlowBoundaryCondition,
    FlowDomain,
    FlowQC,
    FlowSimulationRequest,
    FluidProperties,
)


def domain() -> FlowDomain:
    return FlowDomain(
        domain_id="lv",
        anatomy_ref=ArtifactRef(
            artifact_id="anatomy",
            kind="surface_mesh",
            uri="file:///lv.vtp",
        ),
        region="left_ventricle",
    )


def test_nonwall_boundary_requires_definition() -> None:
    with pytest.raises(ValueError):
        FlowBoundaryCondition(
            boundary_id="aorta",
            kind="pressure",
            region="aortic_outlet",
        )


def test_flow_request_requires_boundaries() -> None:
    with pytest.raises(ValueError):
        FlowSimulationRequest(
            subject_id="S1",
            domain=domain(),
            backend="cfd",
            fluid=FluidProperties(density=1060.0, dynamic_viscosity=0.0035),
            boundary_conditions=[],
        )


def test_qc_cannot_pass_with_failed_check() -> None:
    with pytest.raises(ValueError):
        FlowQC(
            passed=True,
            converged=True,
            checks={"mass_conservation": False},
        )
