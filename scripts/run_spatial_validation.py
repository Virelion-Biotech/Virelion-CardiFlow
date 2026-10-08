"""Reproduce the independent spatial CPU benchmark report and exact source hashes."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy
import scipy

import cardiflow
from cardiflow.spatial_validation import run_spatial_validation

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("validation/cpu/spatial-results.json"))
    args = parser.parse_args()
    report = run_spatial_validation()
    report.update(
        {
            "version": cardiflow.__version__,
            "python": platform.python_version(),
            "numpy": numpy.__version__,
            "scipy": scipy.__version__,
            "source_sha256": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in Path(cardiflow.__file__).parent.glob("*.py")
            },
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    raise SystemExit(0 if report["passed"] else 1)
