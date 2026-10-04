from __future__ import annotations

from .backends import BackendUnavailable, FlowBackend
from .models import FlowSimulationRequest, FlowSimulationResult


class ReadinessError(RuntimeError):
    pass


class CardiFlowService:
    def __init__(self) -> None:
        self._backends: dict[str, FlowBackend] = {}
        from .reduced_order import Windkessel3ElementBackend

        self.register_backend(Windkessel3ElementBackend())

    def register_backend(self, backend: FlowBackend) -> None:
        self._backends[backend.name] = backend

    def backends(self) -> list[str]:
        return sorted(self._backends)

    def _backend(self, name: str) -> FlowBackend:
        backend = self._backends.get(name)
        if backend is None or not backend.available():
            raise BackendUnavailable(f"CardiFlow backend unavailable: {name}")
        return backend

    def simulate(self, request: FlowSimulationRequest) -> FlowSimulationResult:
        result = self._backend(request.backend).simulate(request)
        if result.subject_id != request.subject_id:
            raise ReadinessError("Backend returned flow results for a different subject")
        if result.backend != request.backend:
            raise ReadinessError("Backend result identifier does not match request backend")
        if result.qc is not None and not result.qc.passed:
            raise ReadinessError("Flow result failed QC")

        result.provenance.setdefault(
            "anatomy_artifact_id", request.domain.anatomy_ref.artifact_id
        )
        if request.domain.anatomy_ref.sha256 is not None:
            result.provenance.setdefault(
                "anatomy_sha256", request.domain.anatomy_ref.sha256
            )
        bundle_fingerprint = request.domain.anatomy_ref.metadata.get(
            "bundle_fingerprint"
        )
        if bundle_fingerprint is not None:
            result.provenance.setdefault(
                "anatomy_bundle_fingerprint", str(bundle_fingerprint)
            )
        if request.mechanics_ref is not None:
            result.provenance.setdefault(
                "mechanics_artifact_id", request.mechanics_ref.artifact_id
            )
            if request.mechanics_ref.sha256 is not None:
                result.provenance.setdefault(
                    "mechanics_sha256", request.mechanics_ref.sha256
                )
        if request.circulation_ref is not None:
            result.provenance.setdefault(
                "circulation_artifact_id", request.circulation_ref.artifact_id
            )
        return result
