"""Solver-specific biomarker boundaries; solver QC alone does not validate physiology."""

from __future__ import annotations
import re

# Explicit restriction to the numerically tested reference pipe implementation.
_PIPE = {"wall_shear_pa", "time_averaged_wall_shear_pa", "oscillatory_shear_index"}
_SPATIAL = re.compile(
    r"wss|shear|vortex|vorticity|washout|residence|flow_efficiency|kinetic_energy|energy_loss", re.I
)


def check_biomarker_eligibility(result):
    names = set(result.scalar_outputs) | set(result.series_outputs)
    names.update(item.kind for item in result.outputs)
    spatial = {name for name in names if _SPATIAL.search(name)}
    if not spatial:
        return
    if result.backend == "rigid-pipe-navier-stokes-v1" and spatial <= _PIPE:
        result.provenance["biomarker_context"] = (
            "rigid circular pipe reference only; not intracardiac validation"
        )
        return
    # A self-reported validation_status or CFD backend name cannot establish eligibility.
    raise ValueError(
        "Spatial flow biomarkers require independently qualified solver integration: "
        + ", ".join(sorted(spatial))
    )
