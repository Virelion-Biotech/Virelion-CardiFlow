"""Independent analytical benchmarks, convergence and fail-closed contracts."""

import json
from itertools import pairwise

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

from cardiflow import CardiFlowService
from cardiflow.spatial_validation import pipe_request, poiseuille, run_spatial_validation, womersley


def test_poiseuille_mesh_refinement(tmp_path):
    rows = [poiseuille(tmp_path, n) for n in (16, 32, 64)]
    for a, b in pairwise(rows):
        assert b["profile_relative_error"] < a["profile_relative_error"] / 3.5
        assert b["flow_relative_error"] < a["flow_relative_error"] / 3.5
    assert rows[-1]["flow_relative_error"] < 0.0003
    assert rows[-1]["wall_shear_relative_error"] < 1e-8


def test_womersley_complex_bessel_solution(tmp_path):
    row = womersley(tmp_path)
    assert row["profile_relative_error"] < 0.001
    assert row["wall_shear_relative_error"] < 0.015
    assert row["momentum_residual"] < 1e-8


def test_quiescence_has_no_osi_and_verified_geometry(tmp_path):
    request = pipe_request(tmp_path, pressure=[0] * 5)
    result = CardiFlowService().simulate(request)
    assert result.scalar_outputs["time_averaged_wall_shear_pa"] == 0
    assert "oscillatory_shear_index" not in result.scalar_outputs
    assert result.provenance["anatomy_sha256"] == request.domain.anatomy_ref.sha256
    assert result.provenance["field_shape"] == [5, 32]
    assert result.qc.passed


@pytest.mark.parametrize(
    "defect",
    [
        "hash",
        "subject",
        "unknown",
        "units",
        "moving",
        "mesh",
        "rheology",
        "bad_cells",
        "bad_clock",
        "pressure_mismatch",
        "boundary",
        "wall_scalar",
        "initial",
        "high_reynolds",
        "bad_geometry",
        "bad_radius",
        "waveform",
        "geometry_kind",
        "fluid_units",
        "metadata_subject",
        "missing_pressure",
        "coupling",
    ],
)
def test_fail_closed(tmp_path, defect):
    req = pipe_request(tmp_path)
    if defect == "hash":
        req.domain.anatomy_ref.sha256 = "0" * 64
    elif defect in {"subject", "bad_geometry", "bad_radius"}:
        path = tmp_path / "pipe.json"
        g = json.loads(path.read_text())
        if defect == "subject":
            g["subject_id"] = "other"
        elif defect == "bad_radius":
            g["radius_m"] = -1
        else:
            g["unconsumed"] = 1
        path.write_text(json.dumps(g))
        req.domain.anatomy_ref.sha256 = None
    elif defect == "unknown":
        req.settings["turbulence"] = True
    elif defect == "units":
        req.boundary_conditions[0].unit = "mmHg"
    elif defect == "moving":
        req.domain.moving_wall_ref = req.domain.anatomy_ref
    elif defect == "mesh":
        req.domain.mesh_ref = req.domain.anatomy_ref
    elif defect == "rheology":
        req.fluid.model = "carreau_yasuda"
    elif defect == "bad_cells":
        req.settings["radial_cells"] = True
    elif defect == "bad_clock":
        req.settings["time_s"] = [0, 0, 1, 2, 3]
    elif defect == "pressure_mismatch":
        req.settings["inlet_pressure_pa"][0] = 2
    elif defect == "boundary":
        req.boundary_conditions.pop()
    elif defect == "wall_scalar":
        req.boundary_conditions[-1].value = 1
    elif defect == "initial":
        req.settings["initial_velocity_m_s"] = [1]
    elif defect == "high_reynolds":
        req.settings["initial_velocity_m_s"] = [10] * 32
    elif defect == "waveform":
        req.boundary_conditions[0].waveform_ref = req.domain.anatomy_ref
    elif defect == "geometry_kind":
        req.domain.anatomy_ref.kind = "mesh"
    elif defect == "fluid_units":
        req.fluid.density_unit = "g/mL"
    elif defect == "metadata_subject":
        req.domain.anatomy_ref.metadata["subject_id"] = "other"
    elif defect == "missing_pressure":
        req.boundary_conditions[0].value = None
    elif defect == "coupling":
        req.circulation_ref = req.domain.anatomy_ref
    with pytest.raises((ValueError, TypeError)):
        CardiFlowService().simulate(req)


def test_spatial_validation_cli_report(monkeypatch, capsys):
    from cardiflow.cli import main

    monkeypatch.setattr("sys.argv", ["cardiflow", "validate-spatial"])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["passed"]


def test_spatial_reference_checks():
    assert run_spatial_validation()["passed"]


def test_pulsatile_shear_reversal(tmp_path):
    n = 64
    time = np.linspace(0, 6, 2401)
    req = pipe_request(tmp_path, n=n, time=time, pressure=10 * np.cos(2 * np.pi * time))
    result = CardiFlowService().simulate(req)
    assert min(result.series_outputs["flow_m3_s"]) < 0
    assert min(result.series_outputs["wall_shear_pa"]) < 0
    assert 0.4 < result.scalar_outputs["oscillatory_shear_index"] <= 0.5
    assert result.scalar_outputs["time_averaged_wall_shear_pa"] > 0


def test_backend_unavailable_fails_without_optional_dependencies(monkeypatch):
    import builtins

    from cardiflow.backends import BackendUnavailable
    from cardiflow.pipe_flow import RigidPipeBackend

    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name == "numpy":
            raise ImportError("missing optional dependency")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    backend = RigidPipeBackend()
    assert not backend.available()
    with pytest.raises(BackendUnavailable):
        backend.simulate(None)
    with pytest.raises(BackendUnavailable):
        run_spatial_validation()
