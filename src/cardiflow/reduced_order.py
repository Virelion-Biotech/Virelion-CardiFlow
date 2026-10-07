from __future__ import annotations

import hashlib
import json
import math
from itertools import pairwise
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import url2pathname

from .backends import BackendUnavailable
from .models import ArtifactRef, FlowQC, FlowSimulationRequest, FlowSimulationResult


def local_artifact_path(ref: ArtifactRef) -> Path:
    parsed = urlparse(ref.uri)
    if parsed.scheme == "file":
        if parsed.netloc not in {"", "localhost"}:
            raise ValueError("Remote file URI authorities are not supported")
        path = Path(url2pathname(parsed.path))
    elif not parsed.scheme or Path(ref.uri).is_absolute():
        path = Path(ref.uri)
    else:
        raise ValueError("Windkessel requires local/file mechanics artifacts")
    return path.expanduser().resolve()


class Windkessel3ElementBackend:
    """Exact zero-order-hold 0D afterload, using N samples and N-1 intervals.

    Pressure uses mmHg, volume mL, time seconds. No spatial CFD is performed.
    """

    name = "windkessel-3element-v1"

    def available(self) -> bool:
        return True

    @staticmethod
    def _finite(value: Any, name: str, *, positive=False) -> float:
        if isinstance(value, bool):
            raise TypeError(f"{name} must be numeric, not boolean")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a finite number") from exc
        if not math.isfinite(number) or (positive and number <= 0):
            raise ValueError(f"{name} must be finite" + (" and > 0" if positive else ""))
        return number

    @classmethod
    def _waveform(cls, flow, time):
        if not isinstance(flow, list) or len(flow) < 2:
            raise ValueError("Inlet flow requires at least two samples")
        if not isinstance(time, list) or len(time) != len(flow):
            raise ValueError("time_s must be aligned with inlet flow")
        flow = [cls._finite(v, "inlet flow") for v in flow]
        time = [cls._finite(v, "time_s") for v in time]
        if any(b <= a or not math.isfinite(b - a) for a, b in pairwise(time)):
            raise ValueError("time_s must be strictly increasing with finite intervals")
        if not math.isfinite(time[-1] - time[0]):
            raise ValueError("Waveform duration must be finite")
        return flow, time

    @classmethod
    def _mechanics_inlet(cls, ref, subject_id):
        if ref.kind != "mechanics_timeseries":
            raise ValueError("mechanics_ref must have kind mechanics_timeseries")
        path = local_artifact_path(ref)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if ref.sha256 is not None and digest.lower() != ref.sha256.lower():
            raise ValueError("Mechanics artifact SHA-256 verification failed")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("Mechanics timeseries artifact must contain a JSON object")
        if "subject_id" in payload and payload["subject_id"] != subject_id:
            raise ValueError("Mechanics artifact belongs to a different subject")
        if ref.metadata.get("subject_id", subject_id) != subject_id:
            raise ValueError("Mechanics reference belongs to a different subject")
        units = payload.get("units", {})
        if not isinstance(units, dict):
            raise TypeError("Mechanics units must be a mapping")
        for key, expected in [("time_s", "s"), ("aortic_flow_ml_s", "ml/s")]:
            if key in units and str(units[key]).lower() != expected:
                raise ValueError(f"Mechanics {key} requires {expected} units")
        flow, time = cls._waveform(payload.get("aortic_flow_ml_s"), payload.get("time_s"))
        return flow, time, digest

    @staticmethod
    def _validate_scope(request):
        allowed = {
            "inlet_flow",
            "dt_s",
            "time_s",
            "initial_capacitor_pressure",
            "inlet_flow_unit",
            "pressure_unit",
        }
        if unknown := set(request.settings) - allowed:
            raise ValueError(f"Unsupported Windkessel settings: {sorted(unknown)}")
        for key, expected in [("inlet_flow_unit", "ml/s"), ("pressure_unit", "mmhg")]:
            if key in request.settings and str(request.settings[key]).lower() != expected:
                raise ValueError(f"{key} must be {expected}")
        if request.circulation_ref is not None:
            raise ValueError(
                "Windkessel does not consume circulation_ref; pass explicit parameters"
            )
        if request.domain.moving_wall_ref is not None:
            raise ValueError("Windkessel does not consume moving-wall inputs")
        if request.fluid.model != "newtonian" or request.fluid.parameters:
            raise ValueError("Windkessel does not consume rheology models or fluid parameters")
        if (
            len(request.boundary_conditions) != 1
            or request.boundary_conditions[0].kind != "windkessel"
        ):
            raise BackendUnavailable(
                "Windkessel requires exactly one windkessel boundary and no additional boundaries"
            )
        boundary = request.boundary_conditions[0]
        if (
            boundary.value is not None
            or boundary.waveform_ref is not None
            or boundary.unit is not None
        ):
            raise ValueError(
                "Windkessel boundary uses parameter values, not scalar/waveform/unit fields"
            )
        required = {"proximal_resistance", "distal_resistance", "compliance"}
        if not required <= boundary.parameters.keys():
            raise ValueError(f"Windkessel requires parameters {sorted(required)}")
        if unknown := set(boundary.parameters) - required - {"distal_pressure_mmHg"}:
            raise ValueError(f"Unsupported Windkessel parameters: {sorted(unknown)}")
        return boundary

    def simulate(self, request: FlowSimulationRequest) -> FlowSimulationResult:
        boundary = self._validate_scope(request)
        params = boundary.parameters
        rp = self._finite(params["proximal_resistance"], "proximal_resistance", positive=True)
        rd = self._finite(params["distal_resistance"], "distal_resistance", positive=True)
        compliance = self._finite(params["compliance"], "compliance", positive=True)
        pd = self._finite(params.get("distal_pressure_mmHg", 0), "distal_pressure_mmHg")
        tau = rd * compliance
        if not math.isfinite(tau) or tau <= 0:
            raise ValueError(
                "Windkessel time constant is not representable as positive finite float"
            )
        settings = request.settings
        digest = None
        if request.mechanics_ref is not None:
            if settings.get("inlet_flow") is not None or settings.get("time_s") is not None:
                raise ValueError("Provide either settings.inlet_flow or mechanics_ref, not both")
            flow, time, digest = self._mechanics_inlet(request.mechanics_ref, request.subject_id)
            if "dt_s" in settings:
                dt = self._finite(settings["dt_s"], "dt_s", positive=True)
                if any(
                    not math.isclose(b - a, dt, rel_tol=1e-6, abs_tol=0.0)
                    for a, b in pairwise(time)
                ):
                    raise ValueError("settings.dt_s disagrees with mechanics sampling intervals")
        else:
            flow = settings.get("inlet_flow")
            if not isinstance(flow, list) or len(flow) < 2:
                raise ValueError(
                    "Provide settings.inlet_flow with at least two samples or mechanics_ref"
                )
            if "time_s" in settings:
                if "dt_s" in settings:
                    raise ValueError("Provide time_s or dt_s, not both")
                time = settings["time_s"]
            else:
                dt = self._finite(settings.get("dt_s"), "dt_s", positive=True)
                time = [i * dt for i in range(len(flow))]
            flow, time = self._waveform(flow, time)
        pc = self._finite(
            settings.get("initial_capacitor_pressure", pd + flow[0] * rd),
            "initial_capacitor_pressure",
        )
        pressures = [pc]
        out_volumes, in_volumes, changes, pressure_integrals = [], [], [], []
        extrema = [pc + rp * flow[0]]
        for q, (a, b) in zip(flow[:-1], pairwise(time)):
            dt = b - a
            ratio = dt / tau
            if not math.isfinite(ratio) or ratio <= 0:
                raise ValueError("Time step divided by time constant must be positive and finite")
            alpha = -math.expm1(-ratio)
            # Average fraction of the approach to equilibrium, avoiding cancellation.
            beta = (
                ratio * (0.5 + ratio * (-1 / 6 + ratio * (1 / 24 - ratio / 120)))
                if ratio < 1e-4
                else 1 - alpha / ratio
            )
            equilibrium = pd + rd * q
            pc_next = pc + (equilibrium - pc) * alpha
            q_initial = (pc - pd) / rd
            out_volume = dt * (q_initial + (q - q_initial) * beta)
            storage = compliance * (pc_next - pc)
            in_volumes.append(q * dt)
            out_volumes.append(out_volume)
            changes.append(storage)
            pressure_integrals.append(pd * dt + rd * out_volume + rp * q * dt)
            extrema.extend((pc + rp * q, pc_next + rp * q))
            pc = pc_next
            pressures.append(pc)
        outlet = [p + rp * q for p, q in zip(pressures, flow)]
        extrema.append(outlet[-1])
        all_values = (
            pressures + outlet + out_volumes + in_volumes + changes + pressure_integrals + extrema
        )
        if not all(math.isfinite(v) for v in all_values):
            raise ValueError("Windkessel computation produced non-finite values")
        residuals = [abs(q - d - s) for q, d, s in zip(in_volumes, out_volumes, changes)]
        scales = [abs(q) + abs(d) + abs(s) for q, d, s in zip(in_volumes, out_volumes, changes)]
        mass_error = max((r / s if s else 0) for r, s in zip(residuals, scales))
        duration = time[-1] - time[0]
        scalars = {
            "mean_inlet_flow": math.fsum(in_volumes) / duration,
            "mean_outlet_pressure": math.fsum(pressure_integrals) / duration,
            "pulse_pressure": max(extrema) - min(extrema),
            "terminal_capacitor_pressure": pressures[-1],
            "duration_s": duration,
            "inlet_volume": math.fsum(in_volumes),
            "distal_outflow_volume": math.fsum(out_volumes),
            "capacitor_storage_change": compliance * (pressures[-1] - pressures[0]),
        }
        series = {
            "time_s": time,
            "inlet_flow": flow,
            "capacitor_pressure": pressures,
            "outlet_pressure": outlet,
            "distal_flow": [(p - pd) / rd for p in pressures],
            "interval_inlet_volume": in_volumes,
            "interval_distal_outflow_volume": out_volumes,
            "interval_storage_change": changes,
        }
        units = {
            k: (
                "s"
                if k in {"time_s", "duration_s"}
                else "mL/s"
                if "flow" in k and "volume" not in k
                else "mL"
                if "volume" in k or "storage" in k
                else "mmHg"
            )
            for k in scalars.keys() | series.keys()
        }
        qc = FlowQC(
            passed=mass_error <= 1e-10,
            converged=True,
            mass_balance_error_fraction=mass_error,
            checks={
                "finite_outputs": True,
                "mass_conservation": mass_error <= 1e-10,
                "positive_time_constant": True,
            },
            metrics={"time_constant_s": tau, "duration_s": duration, "n_intervals": len(flow) - 1},
            warnings=[
                "Converged denotes completed analytic propagation, not periodic-cycle convergence."
            ],
        )
        return FlowSimulationResult(
            subject_id=request.subject_id,
            backend=self.name,
            scalar_outputs=scalars,
            series_outputs=series,
            units=units,
            qc=qc,
            validation_status="software_checked",
            provenance={
                "model": "three-element Windkessel",
                "integration": "exact zero-order hold; N samples / N-1 intervals",
                "boundary_id": boundary.boundary_id,
                "distal_pressure_mmHg": pd,
                "coupling_mode": "mechanics_aortic_flow"
                if request.mechanics_ref
                else "explicit_inlet_flow",
                "mechanics_artifact_id": request.mechanics_ref.artifact_id
                if request.mechanics_ref
                else None,
                "mechanics_sha256": digest,
                "moving_wall_consumed": False,
                "anatomy_consumed": False,
                "fluid_properties_consumed": False,
                "scientific_scope": "0D afterload; not CFD or patient-specific physiological validation",
            },
        )
