from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from .api import FlowAPI
from .backends import BackendUnavailable
from .service import ReadinessError


def main() -> int:
    parser = argparse.ArgumentParser(prog="cardiflow")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Report package and registered backends")
    sub.add_parser("validate-reference", help="Run CPU manufactured numerical checks")
    sub.add_parser("validate-spatial", help="Run analytical CPU pipe-flow benchmarks")
    simulate = sub.add_parser("simulate", help="Run a typed JSON simulation request")
    simulate.add_argument("request", type=Path)
    simulate.add_argument("--output", type=Path, help="Atomically write result JSON")
    args = parser.parse_args()
    api = FlowAPI()
    try:
        if args.command == "doctor":
            result = api.health()
        elif args.command == "validate-reference":
            result = api.validate_reference()
        elif args.command == "validate-spatial":
            result = api.validate_spatial()
        else:
            result = api.simulate(json.loads(args.request.read_text(encoding="utf-8")))
        serialized = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        output = getattr(args, "output", None)
        if output is None:
            print(serialized, end="")
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=".cardiflow-", dir=output.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(serialized)
                os.replace(temporary, output)
            finally:
                Path(temporary).unlink(missing_ok=True)
        return 0 if result.get("passed", True) else 1
    except (OSError, ValueError, TypeError, BackendUnavailable, ReadinessError) as exc:
        parser.error(str(exc))
    return 2
