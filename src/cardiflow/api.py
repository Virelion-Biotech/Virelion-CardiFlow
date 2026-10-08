from __future__ import annotations

from typing import Any

from .models import FlowSimulationRequest
from .service import CardiFlowService


class FlowAPI:
    capabilities = (
        "flow.health",
        "flow.simulate",
        "flow.validate.reference",
        "flow.validate.spatial",
    )

    def __init__(self, service: CardiFlowService | None = None) -> None:
        self.service = service or CardiFlowService()

    def health(self) -> dict[str, Any]:
        from . import __version__

        status = self.service.backend_status()
        return {
            "service": "CardiFlow",
            "version": __version__,
            "contract_version": "1.0",
            "status": "ok" if any(item["available"] for item in status) else "degraded",
            "backend_status": status,
            "backends": self.service.backends(),
            "capabilities": list(self.capabilities),
        }

    def simulate(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = FlowSimulationRequest.model_validate(payload)
        return self.service.simulate(request).model_dump(mode="json")

    def validate_reference(self) -> dict[str, Any]:
        from .validation import run_reference_validation

        return run_reference_validation()

    def validate_spatial(self) -> dict[str, Any]:
        from .spatial_validation import run_spatial_validation

        return run_spatial_validation()
