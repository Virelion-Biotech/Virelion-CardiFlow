from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ArtifactRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    kind: str
    uri: str
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    coordinate_frame: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FlowDomain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain_id: str
    anatomy_ref: ArtifactRef
    region: str
    mesh_ref: ArtifactRef | None = None
    moving_wall_ref: ArtifactRef | None = None


class FluidProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    density: float = Field(gt=0)
    dynamic_viscosity: float = Field(gt=0)
    density_unit: str = "kg/m^3"
    viscosity_unit: str = "Pa*s"
    model: Literal["newtonian", "carreau_yasuda", "custom"] = "newtonian"
    parameters: dict[str, float] = Field(default_factory=dict)


class FlowBoundaryCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    boundary_id: str
    kind: Literal[
        "velocity",
        "flow_rate",
        "pressure",
        "resistance",
        "windkessel",
        "wall",
        "moving_wall",
        "custom",
    ]
    region: str
    value: float | None = None
    unit: str | None = None
    waveform_ref: ArtifactRef | None = None
    parameters: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_definition(self) -> FlowBoundaryCondition:
        if (
            self.kind not in {"wall", "moving_wall", "custom"}
            and self.value is None
            and self.waveform_ref is None
            and not self.parameters
        ):
            raise ValueError("Flow boundary condition has no scalar, waveform, or parameters")
        return self


class FlowQC(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    converged: bool | None = None
    mass_balance_error_fraction: float | None = Field(default=None, ge=0)
    checks: dict[str, bool] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_status(self) -> FlowQC:
        if self.passed and (
            self.errors
            or self.converged is False
            or any(not value for value in self.checks.values())
        ):
            raise ValueError("passed=True is inconsistent with failed flow QC")
        return self


class FlowSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str
    domain: FlowDomain
    backend: str
    fluid: FluidProperties
    boundary_conditions: list[FlowBoundaryCondition]
    mechanics_ref: ArtifactRef | None = None
    circulation_ref: ArtifactRef | None = None
    settings: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_boundaries(self) -> FlowSimulationRequest:
        if not self.boundary_conditions:
            raise ValueError("At least one flow boundary condition is required")
        return self


class FlowSimulationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = "1.0"
    subject_id: str
    backend: str
    outputs: list[ArtifactRef] = Field(default_factory=list)
    scalar_outputs: dict[str, float] = Field(default_factory=dict)
    series_outputs: dict[str, list[float]] = Field(default_factory=dict)
    qc: FlowQC | None = None
    validation_status: Literal[
        "unvalidated",
        "software_checked",
        "numerically_checked",
        "empirically_checked",
    ] = "unvalidated"
    provenance: dict[str, Any] = Field(default_factory=dict)
