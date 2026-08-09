from __future__ import annotations

import math

from sketchmath.executor.errors import CommandValidationError, FeatureRebuildError, MissingParameterError, RevisionConflictError, SelectionResolutionError
from sketchmath.features.rebuild import rebuild_document
from sketchmath.models.document import FeatureRecord, HoleParameters, SketchMathDocument
from sketchmath.models.entities import Circle2DEntity, Profile2DEntity
from sketchmath.models.feature_command import FeatureCommand, FeatureOperationResult


def _feature_from_parameters(command: FeatureCommand) -> FeatureRecord:
    payload = command.parameters.get("feature")
    if not isinstance(payload, dict):
        raise MissingParameterError(
            "Feature operation requires parameters.feature",
            detail={"operation_type": command.operation_type, "parameter": "feature"},
        )
    return FeatureRecord.model_validate(payload)


def _binding_error(message: str, *, parameter_id: str, binding_type: str, target_id: str) -> CommandValidationError:
    return CommandValidationError(
        message,
        detail={
            "parameter_id": parameter_id,
            "binding_type": binding_type,
            "target_id": target_id,
            "error_code": "invalid_design_parameter_binding",
        },
    )


def _find_bound_entity(document: SketchMathDocument, target_id: str):  # noqa: ANN202
    matches = [
        (sketch, entity)
        for sketch in document.sketches
        for entity in sketch.state.items
        if entity.id == target_id
    ]
    if not matches:
        raise SelectionResolutionError(
            "Design parameter binding target does not exist",
            detail={"target_id": target_id, "error_code": "design_parameter_target_missing"},
        )
    if len(matches) > 1:
        raise SelectionResolutionError(
            "Design parameter binding target is ambiguous across sketches",
            detail={"target_id": target_id, "error_code": "design_parameter_target_ambiguous"},
        )
    return matches[0]


def _set_rectangle_width(
    document: SketchMathDocument,
    *,
    parameter_id: str,
    target_id: str,
    width: float,
) -> set[str]:
    sketch, entity = _find_bound_entity(document, target_id)
    if not isinstance(entity, Profile2DEntity) or not entity.closed or len(entity.vertices) != 5:
        raise _binding_error(
            "Rectangle-width binding requires a closed four-corner profile",
            parameter_id=parameter_id,
            binding_type="rectangle_profile_width",
            target_id=target_id,
        )
    if entity.locked:
        raise _binding_error(
            "Rectangle-width binding cannot mutate a locked profile",
            parameter_id=parameter_id,
            binding_type="rectangle_profile_width",
            target_id=target_id,
        )
    xs = [point[0] for point in entity.vertices[:-1]]
    ys = [point[1] for point in entity.vertices[:-1]]
    minimum_x, maximum_x = min(xs), max(xs)
    minimum_y, maximum_y = min(ys), max(ys)
    expected_corners = {
        (minimum_x, minimum_y),
        (maximum_x, minimum_y),
        (maximum_x, maximum_y),
        (minimum_x, maximum_y),
    }
    if set(entity.vertices[:-1]) != expected_corners or entity.vertices[0] != entity.vertices[-1]:
        raise _binding_error(
            "Rectangle-width binding requires an axis-aligned rectangle",
            parameter_id=parameter_id,
            binding_type="rectangle_profile_width",
            target_id=target_id,
        )
    height = maximum_y - minimum_y
    if width <= 0 or height <= 0:
        raise _binding_error(
            "Rectangle-width binding must produce positive dimensions",
            parameter_id=parameter_id,
            binding_type="rectangle_profile_width",
            target_id=target_id,
        )
    next_maximum_x = minimum_x + width
    next_vertices = [
        (minimum_x if math.isclose(x, minimum_x, abs_tol=1e-9) else next_maximum_x, y)
        for x, y in entity.vertices
    ]
    sketch.state.replace_entity(
        entity.model_copy(update={"vertices": next_vertices, "area": width * height})
    )
    return {feature.feature_id for feature in document.features if feature.profile_id == target_id}


def _set_circle_center_x(
    document: SketchMathDocument,
    *,
    parameter_id: str,
    target_id: str,
    center_x: float,
) -> set[str]:
    sketch, entity = _find_bound_entity(document, target_id)
    if not isinstance(entity, Circle2DEntity):
        raise _binding_error(
            "Circle-center binding requires a circle entity",
            parameter_id=parameter_id,
            binding_type="circle_center_x",
            target_id=target_id,
        )
    if entity.locked:
        raise _binding_error(
            "Circle-center binding cannot mutate a locked circle",
            parameter_id=parameter_id,
            binding_type="circle_center_x",
            target_id=target_id,
        )
    delta_x = center_x - entity.center[0]
    sketch.state.replace_entity(entity.model_copy(update={"center": (center_x, entity.center[1])}))
    changed_profiles: set[str] = set()
    for candidate in list(sketch.state.items):
        if not isinstance(candidate, Profile2DEntity) or candidate.source_circle_id != target_id:
            continue
        if candidate.locked:
            raise _binding_error(
                "Circle-center binding cannot mutate a locked derived profile",
                parameter_id=parameter_id,
                binding_type="circle_center_x",
                target_id=target_id,
            )
        sketch.state.replace_entity(
            candidate.model_copy(
                update={"vertices": [(x + delta_x, y) for x, y in candidate.vertices]}
            )
        )
        changed_profiles.add(candidate.id)
    return {feature.feature_id for feature in document.features if feature.profile_id in changed_profiles}


def _set_hole_binding(
    document: SketchMathDocument,
    *,
    parameter_id: str,
    binding_type: str,
    target_id: str,
    bound_value: float,
) -> set[str]:
    feature = next((candidate for candidate in document.features if candidate.feature_id == target_id), None)
    if feature is None:
        raise SelectionResolutionError(
            "Design parameter binding feature does not exist",
            detail={"target_id": target_id, "error_code": "design_parameter_target_missing"},
        )
    if feature.feature_type != "hole" or not isinstance(feature.parameters, HoleParameters):
        raise _binding_error(
            "Hole binding requires a hole feature",
            parameter_id=parameter_id,
            binding_type=binding_type,
            target_id=target_id,
        )
    if binding_type == "hole_position_x":
        parameters = feature.parameters.model_copy(
            update={"position_mm": (bound_value, feature.parameters.position_mm[1])}
        )
    else:
        if bound_value <= 0:
            raise _binding_error(
                "Hole-diameter binding must produce a positive diameter",
                parameter_id=parameter_id,
                binding_type=binding_type,
                target_id=target_id,
            )
        parameters = feature.parameters.model_copy(update={"diameter_mm": bound_value})
    document.features[document.features.index(feature)] = feature.model_copy(update={"parameters": parameters})
    return {target_id}


def _apply_design_parameter(document: SketchMathDocument, command: FeatureCommand) -> list[str]:
    parameter_id = command.target_id or ""
    parameter = next(
        (candidate for candidate in document.design_parameters if candidate.parameter_id == parameter_id),
        None,
    )
    if parameter is None:
        raise SelectionResolutionError(
            "Design parameter does not exist",
            detail={"parameter_id": parameter_id, "error_code": "design_parameter_missing"},
        )
    raw_value = command.parameters.get("value")
    if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
        raise MissingParameterError(
            "Design parameter operation requires a numeric parameters.value",
            detail={"parameter": "value", "parameter_id": parameter_id},
        )
    value = float(raw_value)
    if not math.isfinite(value):
        raise CommandValidationError(
            "Design parameter value must be finite",
            detail={"parameter_id": parameter_id, "value": raw_value},
        )
    if parameter.minimum is not None and value < parameter.minimum:
        raise CommandValidationError(
            "Design parameter value is below its minimum",
            detail={"parameter_id": parameter_id, "value": value, "minimum": parameter.minimum},
        )
    if parameter.maximum is not None and value > parameter.maximum:
        raise CommandValidationError(
            "Design parameter value is above its maximum",
            detail={"parameter_id": parameter_id, "value": value, "maximum": parameter.maximum},
        )

    changed: set[str] = set()
    for binding in parameter.bindings:
        bound_value = binding.scale * value + binding.offset
        if not math.isfinite(bound_value):
            raise _binding_error(
                "Design parameter binding produced a non-finite value",
                parameter_id=parameter_id,
                binding_type=binding.binding_type,
                target_id=binding.target_id,
            )
        if binding.binding_type == "rectangle_profile_width":
            changed.update(
                _set_rectangle_width(
                    document,
                    parameter_id=parameter_id,
                    target_id=binding.target_id,
                    width=bound_value,
                )
            )
        elif binding.binding_type == "circle_center_x":
            changed.update(
                _set_circle_center_x(
                    document,
                    parameter_id=parameter_id,
                    target_id=binding.target_id,
                    center_x=bound_value,
                )
            )
        else:
            changed.update(
                _set_hole_binding(
                    document,
                    parameter_id=parameter_id,
                    binding_type=binding.binding_type,
                    target_id=binding.target_id,
                    bound_value=bound_value,
                )
            )
    replacement = parameter.model_copy(update={"value": value})
    document.design_parameters[document.design_parameters.index(parameter)] = replacement
    return [feature.feature_id for feature in document.features if feature.feature_id in changed]


def apply_feature_command(document: SketchMathDocument, command: FeatureCommand) -> FeatureOperationResult:
    if command.base_revision != document.revision:
        raise RevisionConflictError(
            "Feature operation targets a stale document revision",
            detail={
                "document_id": document.document_id,
                "operation_id": command.operation_id,
                "base_revision": command.base_revision,
                "current_revision": document.revision,
            },
        )
    if command.operation_type == "rebuild" and command.mode != "preview":
        raise CommandValidationError(
            "Explicit rebuild is preview-only",
            detail={"operation_type": command.operation_type, "mode": command.mode},
        )

    before = document.model_copy(deep=True)
    after = document.model_copy(deep=True)
    changed: list[str] = []
    if command.operation_type == "add_feature":
        feature = _feature_from_parameters(command)
        if any(existing.feature_id == feature.feature_id for existing in after.features):
            raise SelectionResolutionError(
                "Feature id already exists",
                detail={"feature_id": feature.feature_id, "error_code": "duplicate_feature_id"},
            )
        after.features.append(feature)
        changed.append(feature.feature_id)
    elif command.operation_type == "replace_feature":
        feature = _feature_from_parameters(command)
        target_id = command.target_id or feature.feature_id
        if feature.feature_id != target_id:
            raise CommandValidationError(
                "Feature replacement cannot change immutable feature id",
                detail={"target_id": target_id, "feature_id": feature.feature_id},
            )
        index = next((index for index, existing in enumerate(after.features) if existing.feature_id == target_id), None)
        if index is None:
            raise SelectionResolutionError("Feature does not exist", detail={"feature_id": target_id})
        after.features[index] = feature
        changed.append(feature.feature_id)
    elif command.operation_type == "delete_feature":
        target_id = command.target_id or ""
        parameter_owners = [
            parameter.parameter_id
            for parameter in after.design_parameters
            if any(binding.target_id == target_id for binding in parameter.bindings)
        ]
        if parameter_owners:
            raise SelectionResolutionError(
                "Feature is still referenced by a design parameter",
                detail={
                    "feature_id": target_id,
                    "design_parameter_ids": parameter_owners,
                    "error_code": "feature_still_parameter_bound",
                },
            )
        dependents = [feature.feature_id for feature in after.features if target_id in feature.dependencies]
        if dependents:
            raise SelectionResolutionError(
                "Feature is still referenced by downstream features",
                detail={"feature_id": target_id, "dependent_feature_ids": dependents, "error_code": "feature_still_referenced"},
            )
        previous_count = len(after.features)
        after.features = [feature for feature in after.features if feature.feature_id != target_id]
        if len(after.features) == previous_count:
            raise SelectionResolutionError("Feature does not exist", detail={"feature_id": target_id})
        changed.append(target_id)
    elif command.operation_type == "set_feature_suppressed":
        target_id = command.target_id or ""
        enabled = command.parameters.get("suppressed")
        if not isinstance(enabled, bool):
            raise MissingParameterError(
                "Suppression operation requires a boolean parameters.suppressed",
                detail={"parameter": "suppressed"},
            )
        feature = next((candidate for candidate in after.features if candidate.feature_id == target_id), None)
        if feature is None:
            raise SelectionResolutionError("Feature does not exist", detail={"feature_id": target_id})
        replacement = feature.model_copy(update={"suppressed": enabled})
        after.features[after.features.index(feature)] = replacement
        changed.append(target_id)
    elif command.operation_type == "set_design_parameter":
        changed.extend(_apply_design_parameter(after, command))
    elif command.operation_type != "rebuild":
        raise CommandValidationError("Unsupported feature operation", detail={"operation_type": command.operation_type})

    if command.operation_type != "rebuild":
        feature_ids_by_body: dict[str, list[str]] = {}
        for feature in after.features:
            feature_ids_by_body.setdefault(feature.body_id, []).append(feature.feature_id)
        after.bodies = [body.model_copy(update={"feature_ids": feature_ids_by_body.get(body.body_id, [])}) for body in after.bodies]
        after.revision += 1
    rebuild = rebuild_document(after)
    after.last_rebuild = rebuild
    if not rebuild.ok:
        raise FeatureRebuildError(
            "Feature rebuild failed",
            detail={
                "document_id": after.document_id,
                "operation_id": command.operation_id,
                "rebuild": rebuild.model_dump(mode="json"),
            },
        )
    return FeatureOperationResult(
        command=command,
        status="committed" if command.mode == "commit" else "preview",
        before=before,
        after=after,
        changed_feature_ids=changed,
        rebuild=rebuild,
    )
