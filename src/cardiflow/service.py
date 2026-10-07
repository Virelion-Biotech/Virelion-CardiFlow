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

    def register_backend(self, backend: FlowBackend, *, replace: bool = False) -> None:
        if not isinstance(backend.name, str) or not backend.name.strip():
            raise ValueError("Backend name must be non-empty")
        if backend.name in self._backends and not replace:
            raise ValueError(f"Backend already registered: {backend.name}")
        self._backends[backend.name] = backend

    def backends(self) -> list[str]:
        return sorted(self._backends)

    def backend_status(self) -> list[dict]:
        status = []
        for name, backend in sorted(self._backends.items()):
            try:
                available, error = bool(backend.available()), None
            except (OSError, ImportError, RuntimeError, ValueError, TypeError) as exc:
                available, error = False, str(exc)
            status.append({"name": name, "available": available, "error": error})
        return status

    def _backend(self, name: str) -> FlowBackend:
        backend = self._backends.get(name)
        if backend is None or not backend.available():
            raise BackendUnavailable(f"CardiFlow backend unavailable: {name}")
        return backend

    def simulate(self, request: FlowSimulationRequest) -> FlowSimulationResult:
        result = self._backend(request.backend).simulate(request)
        if not isinstance(result, FlowSimulationResult):
            raise ReadinessError("Backend must return a FlowSimulationResult")
        result = FlowSimulationResult.model_validate(result.model_dump(mode="python"))
        if result.subject_id != request.subject_id:
            raise ReadinessError("Backend returned flow results for a different subject")
        if result.backend != request.backend:
            raise ReadinessError("Backend result identifier does not match request backend")
        if result.qc is None or not result.qc.passed:
            raise ReadinessError("Flow result is missing QC or failed QC")

        expected = {"domain_id": request.domain.domain_id}
        references = {
            "anatomy": request.domain.anatomy_ref,
            "mechanics": request.mechanics_ref,
            "circulation": request.circulation_ref,
        }
        for label, ref in references.items():
            if ref is None:
                continue
            expected[f"{label}_artifact_id"] = ref.artifact_id
            if ref.sha256 is not None:
                expected[f"{label}_sha256"] = ref.sha256.lower()
            if ref.coordinate_frame is not None:
                expected[f"{label}_coordinate_frame"] = ref.coordinate_frame
            fingerprint = ref.metadata.get("bundle_fingerprint")
            if fingerprint is not None:
                expected[f"{label}_bundle_fingerprint"] = str(fingerprint)
        for key, value in expected.items():
            reported = result.provenance.get(key)
            if reported is not None and reported != value:
                raise ReadinessError(f"Backend lineage conflict: {key}")
            result.provenance[key] = value
        return result
