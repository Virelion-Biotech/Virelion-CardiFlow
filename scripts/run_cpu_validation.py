"""Reproduce manufactured 0D checks and noiseless synthetic inverse recovery."""

import argparse
import json
import platform
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import least_squares

from cardiflow import CardiFlowService, __version__
from cardiflow.validation import run_reference_validation, validation_request


def synthetic_inverse():
    times = np.arange(251) * 0.02
    flow = np.maximum(0, 100 * np.sin(2 * np.pi * times)).tolist()
    truth = np.array([0.08, 1.1, 1.7])
    service = CardiFlowService()

    def pressure(parameters):
        request = validation_request(
            flow,
            dt_s=0.02,
            initial=4,
            distal=4,
            rp=parameters[0],
            rd=parameters[1],
            compliance=parameters[2],
        )
        return np.array(service.simulate(request).series_outputs["outlet_pressure"])

    observed = pressure(truth)
    fitted = least_squares(
        lambda parameters: pressure(parameters) - observed,
        [0.15, 0.8, 2.4],
        bounds=([0.02, 0.3, 0.3], [0.3, 2, 3]),
        xtol=1e-12,
        ftol=1e-12,
        gtol=1e-12,
    )
    relative = np.abs((fitted.x - truth) / truth)
    return {
        "truth": dict(
            zip(["proximal_resistance", "distal_resistance", "compliance"], truth.tolist())
        ),
        "recovered": dict(
            zip(["proximal_resistance", "distal_resistance", "compliance"], fitted.x.tolist())
        ),
        "max_relative_parameter_error": float(relative.max()),
        "pressure_rmse_mmHg": float(np.sqrt(np.mean(fitted.fun**2))),
        "optimizer_success": bool(fitted.success),
        "jacobian_condition_number": float(np.linalg.cond(fitted.jac)),
        "passed": bool(fitted.success and relative.max() < 1e-6),
        "scope": "Known initial and distal pressures; noiseless same-model observations. Not real-data identifiability or empirical validation.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("validation/cpu/results.json"))
    args = parser.parse_args()
    report = {
        "version": __version__,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "manufactured": run_reference_validation(),
        "synthetic_inverse": synthetic_inverse(),
        "cfd_validation": False,
        "empirical_validation": False,
        "clinical_validation": False,
    }
    report["passed"] = all(report[name]["passed"] for name in ["manufactured", "synthetic_inverse"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    raise SystemExit(0 if report["passed"] else 1)
