# Geometry Command Contract

The assistant must return a typed `GeometryCommand` envelope with:

- `version`
- `command_id`
- `mode`
- `command_type`
- `selection`
- `parameters`

The command is previewable first and commit-ready only after validation.
