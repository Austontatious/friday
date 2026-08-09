from __future__ import annotations

from sketchmath.executor.errors import CommandValidationError, FeatureRebuildError, MissingParameterError, RevisionConflictError, SelectionResolutionError
from sketchmath.features.rebuild import rebuild_document
from sketchmath.models.document import FeatureRecord, SketchMathDocument
from sketchmath.models.feature_command import FeatureCommand, FeatureOperationResult


def _feature_from_parameters(command: FeatureCommand) -> FeatureRecord:
    payload = command.parameters.get("feature")
    if not isinstance(payload, dict):
        raise MissingParameterError(
            "Feature operation requires parameters.feature",
            detail={"operation_type": command.operation_type, "parameter": "feature"},
        )
    return FeatureRecord.model_validate(payload)


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
