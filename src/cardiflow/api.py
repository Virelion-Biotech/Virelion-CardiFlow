from __future__ import annotations

from typing import Any

from .models import FlowSimulationRequest
from .service import CardiFlowService


class FlowAPI:
    capabilities = ("flow.health", "flow.simulate")

    def __init__(self, service: CardiFlowService | None = None) -> None:
        self.service = service or CardiFlowService()

    def health(self) -> dict[str, Any]:
        return {
            "service": "CardiFlow",
            "status": "ok",
            "backends": self.service.backends(),
            "capabilities": list(self.capabilities),
        }

    def simulate(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = FlowSimulationRequest.model_validate(payload)
        return self.service.simulate(request).model_dump(mode="json")
