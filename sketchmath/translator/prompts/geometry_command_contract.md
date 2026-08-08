# Geometry Command Contract

The assistant must return a typed `GeometryCommand` envelope with:

- `version`
- `command_id`
- `mode`
- `command_type`
- `selection`
- `parameters`

The command is previewable first and commit-ready only after validation.

The translator currently emits compatible version `0.1` commands from its supported natural-language subset. The browser may emit version `0.2` commands for circle, topology, and endpoint-aware constraint workflows. Both versions and every supported `command_type` are declared by the canonical `GeometryCommand` model and generated JSON schema; never invent an undeclared command or version.
