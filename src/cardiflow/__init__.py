"""Public API for Virelion-CardiFlow."""

from .api import FlowAPI
from .models import (
    ArtifactRef,
    FlowBoundaryCondition,
    FlowDomain,
    FlowQC,
    FlowSimulationRequest,
    FlowSimulationResult,
    FluidProperties,
)
from .reduced_order import Windkessel3ElementBackend
from .service import CardiFlowService, ReadinessError
from .validation import run_reference_validation

__all__ = [
    "ArtifactRef",
    "CardiFlowService",
    "FlowAPI",
    "FlowBoundaryCondition",
    "FlowDomain",
    "FlowQC",
    "FlowSimulationRequest",
    "FlowSimulationResult",
    "FluidProperties",
    "ReadinessError",
    "Windkessel3ElementBackend",
    "run_reference_validation",
]

__version__ = "0.3.0"
