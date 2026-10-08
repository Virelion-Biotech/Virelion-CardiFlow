import hashlib
import json
from copy import deepcopy

import pytest
from test_windkessel import _request

from cardiflow import (
    ArtifactRef,
    CardiFlowService,
    FlowQC,
    FlowSimulationResult,
    ReadinessError,
    Windkessel3ElementBackend,
)
from cardiflow.api import FlowAPI
from cardiflow.backends import BackendUnavailable
from cardiflow.cli import main
from cardiflow.reduced_order import local_artifact_path
from cardiflow.validation import run_reference_validation


@pytest.mark.parametrize(
    "flow,time",
    [
        ([1], [0]),
        ([1, 2], [0]),
        ([1, 2], [1, 0]),
        ([1, 2], [0, float("nan")]),
        ([1, True], [0, 1]),
        ([1, 2], [-1e308, 1e308]),
    ],
)
def test_invalid_waveforms_fail(flow, time):
    request = _request()
    request.settings = {"inlet_flow": flow, "time_s": time}
    with pytest.raises((ValueError, TypeError)):
        Windkessel3ElementBackend().simulate(request)


@pytest.mark.parametrize(
    "change",
    [
        "circulation",
        "moving_wall",
        "rheology",
        "extra_parameter",
        "extra_boundary",
        "scalar_boundary",
        "missing_parameter",
        "duplicate_boundary",
    ],
)
def test_unsupported_inputs_are_not_silently_consumed(change):
    payload = _request().model_dump()
    ref = ArtifactRef(artifact_id="r", kind="ref", uri="memory://r").model_dump()
    if change == "circulation":
        payload["circulation_ref"] = ref
    elif change == "moving_wall":
        payload["domain"]["moving_wall_ref"] = ref
    elif change == "rheology":
        payload["fluid"]["model"] = "carreau_yasuda"
    elif change == "extra_parameter":
        payload["boundary_conditions"][0]["parameters"]["ignored"] = 1
    elif change == "missing_parameter":
        payload["boundary_conditions"][0]["parameters"].pop("compliance")
    elif change == "scalar_boundary":
        payload["boundary_conditions"][0]["value"] = 1
    elif change in {"extra_boundary", "duplicate_boundary"}:
        duplicate = deepcopy(payload["boundary_conditions"][0])
        if change == "extra_boundary":
            duplicate["boundary_id"] = "b2"
        payload["boundary_conditions"].append(duplicate)
    with pytest.raises((ValueError, BackendUnavailable)):
        FlowAPI().simulate(payload)


def mechanics_request(tmp_path, payload, *, digest=None):
    path = tmp_path / "aortic flow %.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    request = _request()
    request.settings = {}
    request.mechanics_ref = ArtifactRef(
        artifact_id="mech", kind="mechanics_timeseries", uri=path.as_uri(), sha256=digest
    )
    return request, path


def test_nonuniform_mechanics_preserves_clock_and_records_actual_hash(tmp_path):
    request, path = mechanics_request(
        tmp_path, {"time_s": [5, 5.01, 5.04], "aortic_flow_ml_s": [1, 2, 3], "subject_id": "S1"}
    )
    result = CardiFlowService().simulate(request)
    assert result.series_outputs["time_s"] == [5, 5.01, 5.04]
    assert result.scalar_outputs["duration_s"] == pytest.approx(0.04)
    assert result.provenance["mechanics_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result.units["inlet_flow"] == "mL/s"
    assert not result.provenance["anatomy_consumed"]
    request.settings = {"dt_s": 0.01}
    with pytest.raises(ValueError, match="disagrees"):
        CardiFlowService().simulate(request)


@pytest.mark.parametrize("defect", ["sha", "subject", "units", "kind", "object", "missing_time"])
def test_mechanics_handoff_fails_on_invalid_evidence(tmp_path, defect):
    payload = {"time_s": [0, 0.01], "aortic_flow_ml_s": [1, 2]}
    if defect == "subject":
        payload["subject_id"] = "other"
    elif defect == "units":
        payload["units"] = {"aortic_flow_ml_s": "m^3/s"}
    elif defect == "missing_time":
        payload.pop("time_s")
    elif defect == "object":
        payload = []
    request, path = mechanics_request(
        tmp_path, payload, digest="0" * 64 if defect == "sha" else None
    )
    if defect == "kind":
        request.mechanics_ref.kind = "moving_wall"
    with pytest.raises((ValueError, TypeError)):
        CardiFlowService().simulate(request)
    assert (
        local_artifact_path(ArtifactRef(artifact_id="x", kind="x", uri=str(path))) == path.resolve()
    )


def test_remote_file_authority_rejected():
    with pytest.raises(ValueError, match="Remote"):
        local_artifact_path(ArtifactRef(artifact_id="x", kind="x", uri="file://remote/path"))


@pytest.mark.parametrize(
    "defect", ["subject", "backend", "anatomy", "missing_qc", "nan", "wrong_type"]
)
def test_service_rejects_invalid_backend_results(defect):
    request = _request()

    class Backend:
        name = request.backend

        def available(self):
            return True

        def simulate(self, incoming):
            if defect == "wrong_type":
                return {}
            result = FlowSimulationResult(
                subject_id=incoming.subject_id, backend=self.name, qc=FlowQC(passed=True)
            )
            if defect == "subject":
                result.subject_id = "other"
            elif defect == "backend":
                result.backend = "other"
            elif defect == "anatomy":
                result.provenance["anatomy_artifact_id"] = "other"
            elif defect == "missing_qc":
                result.qc = None
            elif defect == "nan":
                result.scalar_outputs["pressure"] = float("nan")
            return result

    service = CardiFlowService()
    with pytest.raises(ValueError, match="already registered"):
        service.register_backend(Backend())
    service.register_backend(Backend(), replace=True)
    with pytest.raises((ReadinessError, ValueError)):
        service.simulate(request)


def test_checked_result_requires_qc():
    with pytest.raises(ValueError, match="QC"):
        FlowSimulationResult(subject_id="s", backend="b", validation_status="numerically_checked")


def test_manufactured_validation_passes():
    report = run_reference_validation()
    assert report["passed"]
    assert len(report["harmonic_refinement"]) == 4
    assert max(report["metrics"].values()) < 1e-11


@pytest.mark.parametrize("command", ["doctor", "validate-reference"])
def test_cli_cpu_commands(monkeypatch, capsys, command):
    monkeypatch.setattr("sys.argv", ["cardiflow", command])
    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload.get("passed", payload.get("status") == "ok")


def test_cli_simulation_output_is_reviewable_and_preserved_on_invalid_request(
    tmp_path, monkeypatch
):
    source = tmp_path / "request.json"
    output = tmp_path / "result.json"
    source.write_text(_request().model_dump_json())
    monkeypatch.setattr("sys.argv", ["cardiflow", "simulate", str(source), "--output", str(output)])
    assert main() == 0
    payload = json.loads(output.read_text())
    assert payload["qc"]["passed"]
    assert payload["series_outputs"]["time_s"][-1] == pytest.approx(0.19)
    old = output.read_bytes()
    source.write_text("{}")
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert output.read_bytes() == old


def test_tiny_mechanics_sampling_mismatch_is_not_hidden_by_absolute_tolerance(tmp_path):
    request, _ = mechanics_request(tmp_path, {"time_s": [0, 1e-12], "aortic_flow_ml_s": [1, 1]})
    request.settings["dt_s"] = 1e-10
    with pytest.raises(ValueError, match="disagrees"):
        CardiFlowService().simulate(request)


@pytest.mark.parametrize("raises", [False, True])
def test_health_reports_unavailable_backends(raises):
    class Unavailable:
        name = "windkessel-3element-v1"

        def available(self):
            if raises:
                raise RuntimeError("unavailable")
            return False

    service = CardiFlowService()
    for name in service.backends():
        backend = Unavailable()
        backend.name = name
        service.register_backend(backend, replace=True)
    health = FlowAPI(service).health()
    assert health["status"] == "degraded"
    assert not health["backend_status"][0]["available"]
