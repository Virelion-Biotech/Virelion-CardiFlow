import pytest
from cardiflow.eligibility import check_biomarker_eligibility
from cardiflow.models import FlowSimulationResult


def test_0d_and_unknown_solvers_cannot_claim_spatial_biomarkers():
    for name in ["windkessel-3element-v1", "claimed-validated-cfd"]:
        result = FlowSimulationResult(
            subject_id="s", backend=name, scalar_outputs={"wall_shear_pa": 1}
        )
        with pytest.raises(ValueError, match="qualified"):
            check_biomarker_eligibility(result)


def test_pipe_wall_shear_is_scoped_and_washout_blocked():
    result = FlowSimulationResult(
        subject_id="s", backend="rigid-pipe-navier-stokes-v1", scalar_outputs={"wall_shear_pa": 1}
    )
    check_biomarker_eligibility(result)
    assert "not intracardiac" in result.provenance["biomarker_context"]
    result.scalar_outputs["washout_fraction"] = 0.5
    with pytest.raises(ValueError):
        check_biomarker_eligibility(result)
