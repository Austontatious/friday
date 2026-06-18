from __future__ import annotations


class SketchMathError(RuntimeError):
    code = "sketchmath_error"
    retryable = False

    def __init__(self, message: str, *, detail: dict[str, object] | None = None) -> None:
        self.detail = detail or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": str(self),
            "detail": self.detail,
            "retryable": self.retryable,
        }


class UnsupportedCommandError(SketchMathError):
    code = "unsupported_command_type"


class SelectionResolutionError(SketchMathError):
    code = "selection_resolution_error"


class MissingEntityError(SelectionResolutionError):
    code = "missing_entity"


class WrongEntityTypeError(SelectionResolutionError):
    code = "wrong_entity_type"


class MissingParameterError(SketchMathError):
    code = "missing_parameter"


class LockedEntityMutationError(SketchMathError):
    code = "locked_entity_mutation"


class InvalidUnitsError(SketchMathError):
    code = "invalid_units"


class CadAdapterUnavailableError(SketchMathError):
    code = "cad_adapter_unavailable"
    retryable = True


class UnsupportedCadFormatError(SketchMathError):
    code = "unsupported_output_format"


class CadExportError(SketchMathError):
    code = "cad_export_error"
    retryable = True


class SolverError(SketchMathError):
    code = "solver_error"


class ClarificationRequiredError(SketchMathError):
    code = "clarification_required"
