from __future__ import annotations

from typing import Protocol

from .models import FlowSimulationRequest, FlowSimulationResult


class FlowBackend(Protocol):
    name: str

    def available(self) -> bool: ...

    def simulate(self, request: FlowSimulationRequest) -> FlowSimulationResult: ...


class BackendUnavailable(RuntimeError):
    pass
