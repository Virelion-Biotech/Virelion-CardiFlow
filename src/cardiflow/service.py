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
        if result.qc is not None and not result.qc.passed:
            raise ReadinessError("Flow result failed QC")
        return result
