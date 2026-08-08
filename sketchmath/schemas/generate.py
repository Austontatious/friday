from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TypeAlias

from pydantic import BaseModel

from sketchmath.models.geometry_command import GeometryCommand
from sketchmath.models.operation_result import OperationResult
from sketchmath.models.selection_context import SelectionContext
from sketchmath.models.solver_analysis import SolverAnalysis


SchemaModel: TypeAlias = type[BaseModel]
SCHEMA_MODELS: dict[str, SchemaModel] = {
    "geometry_command.schema.json": GeometryCommand,
    "selection_context.schema.json": SelectionContext,
    "operation_result.schema.json": OperationResult,
    "solver_analysis.schema.json": SolverAnalysis,
}
SCHEMA_ROOT = Path(__file__).resolve().parent


def render_schema(model: SchemaModel) -> str:
    payload = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **model.model_json_schema(mode="validation"),
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def schema_drift(root: Path = SCHEMA_ROOT) -> list[str]:
    drift: list[str] = []
    for filename, model in SCHEMA_MODELS.items():
        path = root / filename
        expected = render_schema(model)
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            drift.append(filename)
    return drift


def write_schemas(root: Path = SCHEMA_ROOT) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for filename, model in SCHEMA_MODELS.items():
        (root / filename).write_text(render_schema(model), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate canonical SketchMath JSON schemas from Pydantic models")
    parser.add_argument("--check", action="store_true", help="fail when checked-in schemas differ from the canonical models")
    args = parser.parse_args()

    if args.check:
        drift = schema_drift()
        if drift:
            print(f"SketchMath schema drift: {', '.join(drift)}")
            return 1
        print("SketchMath schemas match canonical models")
        return 0

    write_schemas()
    print(f"Wrote {len(SCHEMA_MODELS)} SketchMath schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
