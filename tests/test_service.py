import pytest

from cardiflow import (
    ArtifactRef,
    CardiFlowService,
    FlowBoundaryCondition,
    FlowDomain,
    FlowSimulationRequest,
    FluidProperties,
)
from cardiflow.backends import BackendUnavailable


def test_service_fails_closed_without_backend() -> None:
    request = FlowSimulationRequest(
        subject_id="S1",
        domain=FlowDomain(
            domain_id="lv",
            anatomy_ref=ArtifactRef(
                artifact_id="anatomy",
                kind="surface_mesh",
                uri="file:///lv.vtp",
            ),
            region="left_ventricle",
        ),
        backend="missing",
        fluid=FluidProperties(density=1060.0, dynamic_viscosity=0.0035),
        boundary_conditions=[
            FlowBoundaryCondition(
                boundary_id="wall",
                kind="wall",
                region="endocardium",
            )
        ],
    )
    with pytest.raises(BackendUnavailable):
        CardiFlowService().simulate(request)
