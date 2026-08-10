from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .selection_context import SelectionContext


class SketchRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sketch_id: str
    name: str
    plane: Literal["xy", "xz", "yz"] = "xy"
    state: SelectionContext
    visible: bool = True


class BodyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body_id: str
    name: str
    sketch_ids: list[str] = Field(default_factory=list)
    feature_ids: list[str] = Field(default_factory=list)
    visible: bool = True


class ExtrudeParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    depth_mm: float = Field(gt=0)
    extent: Literal["one_sided", "symmetric", "two_sided"] = "one_sided"
    second_depth_mm: float | None = Field(default=None, gt=0)
    direction: Literal["positive", "negative"] = "positive"
    operation: Literal["new_body", "add", "cut"] = "new_body"

    @model_validator(mode="after")
    def validate_extent(self) -> "ExtrudeParameters":
        if self.extent == "two_sided" and self.second_depth_mm is None:
            raise ValueError("two_sided extrusion requires second_depth_mm")
        if self.extent != "two_sided" and self.second_depth_mm is not None:
            raise ValueError("second_depth_mm is only valid for two_sided extrusion")
        return self


class HoleParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: Literal["simple", "counterbore", "countersink"] = "simple"
    termination: Literal["through", "blind"] = "through"
    position_mm: tuple[float, float]
    diameter_mm: float = Field(gt=0)
    depth_mm: float | None = Field(default=None, gt=0)
    counterbore_diameter_mm: float | None = Field(default=None, gt=0)
    counterbore_depth_mm: float | None = Field(default=None, gt=0)
    countersink_diameter_mm: float | None = Field(default=None, gt=0)
    countersink_angle_deg: float | None = Field(default=None, gt=0, lt=180)
    operation: Literal["cut"] = "cut"

    @model_validator(mode="after")
    def validate_hole_semantics(self) -> "HoleParameters":
        numeric_values = [
            *self.position_mm,
            self.diameter_mm,
            self.depth_mm,
            self.counterbore_diameter_mm,
            self.counterbore_depth_mm,
            self.countersink_diameter_mm,
            self.countersink_angle_deg,
        ]
        if not all(value is None or math.isfinite(value) for value in numeric_values):
            raise ValueError("hole parameters must be finite")
        if self.termination == "blind" and self.depth_mm is None:
            raise ValueError("blind hole requires depth_mm")
        if self.termination == "through" and self.depth_mm is not None:
            raise ValueError("through hole cannot declare depth_mm")
        if self.style == "counterbore":
            if self.counterbore_diameter_mm is None or self.counterbore_depth_mm is None:
                raise ValueError("counterbore requires counterbore diameter and depth")
            if self.counterbore_diameter_mm <= self.diameter_mm:
                raise ValueError("counterbore diameter must exceed hole diameter")
            if self.termination == "blind" and self.counterbore_depth_mm > float(self.depth_mm or 0):
                raise ValueError("counterbore depth cannot exceed blind hole depth")
        elif self.counterbore_diameter_mm is not None or self.counterbore_depth_mm is not None:
            raise ValueError("counterbore parameters require counterbore style")
        if self.style == "countersink":
            if self.countersink_diameter_mm is None or self.countersink_angle_deg is None:
                raise ValueError("countersink requires countersink diameter and angle")
            if self.countersink_diameter_mm <= self.diameter_mm:
                raise ValueError("countersink diameter must exceed hole diameter")
        elif self.countersink_diameter_mm is not None or self.countersink_angle_deg is not None:
            raise ValueError("countersink parameters require countersink style")
        return self


class RevolveParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    axis_entity_id: str
    angle_deg: float = Field(default=360.0, gt=0, le=360)
    operation: Literal["new_body", "add", "cut"] = "new_body"

    @model_validator(mode="after")
    def validate_revolve_parameters(self) -> "RevolveParameters":
        if not math.isfinite(self.angle_deg):
            raise ValueError("revolve angle must be finite")
        if not self.axis_entity_id.strip():
            raise ValueError("revolve axis_entity_id cannot be empty")
        return self


class FilletParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    radius_mm: float = Field(gt=0)
    operation: Literal["modify"] = "modify"

    @model_validator(mode="after")
    def validate_fillet_parameters(self) -> "FilletParameters":
        if not math.isfinite(self.radius_mm):
            raise ValueError("fillet radius must be finite")
        return self


class ChamferParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distance_mm: float = Field(gt=0)
    operation: Literal["modify"] = "modify"

    @model_validator(mode="after")
    def validate_chamfer_parameters(self) -> "ChamferParameters":
        if not math.isfinite(self.distance_mm):
            raise ValueError("chamfer distance must be finite")
        return self


class LinearPatternParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=2, le=128)
    spacing_mm: float = Field(gt=0)
    direction_xy: tuple[float, float] = (1.0, 0.0)
    operation: Literal["modify"] = "modify"

    @model_validator(mode="after")
    def validate_linear_pattern_parameters(self) -> "LinearPatternParameters":
        if not math.isfinite(self.spacing_mm) or not all(math.isfinite(value) for value in self.direction_xy):
            raise ValueError("linear pattern parameters must be finite")
        if math.hypot(*self.direction_xy) <= 1e-9:
            raise ValueError("linear pattern direction must be non-zero")
        return self


class CircularPatternParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=2, le=128)
    center_mm: tuple[float, float]
    angle_deg: Literal[360.0] = 360.0
    direction: Literal["counterclockwise", "clockwise"] = "counterclockwise"
    operation: Literal["modify"] = "modify"

    @model_validator(mode="after")
    def validate_circular_pattern_parameters(self) -> "CircularPatternParameters":
        if not all(math.isfinite(value) for value in self.center_mm):
            raise ValueError("circular pattern center must be finite")
        return self


class MirrorParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mirror_line_entity_id: str
    operation: Literal["modify"] = "modify"

    @model_validator(mode="after")
    def validate_mirror_parameters(self) -> "MirrorParameters":
        if not self.mirror_line_entity_id.strip():
            raise ValueError("mirror line entity id cannot be empty")
        return self


class ShellParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thickness_mm: float = Field(gt=0)
    opening: Literal["top"] = "top"
    operation: Literal["modify"] = "modify"

    @model_validator(mode="after")
    def validate_shell_parameters(self) -> "ShellParameters":
        if not math.isfinite(self.thickness_mm):
            raise ValueError("shell thickness must be finite")
        return self


class TopologyReferenceSelector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_id: str
    owner_feature_id: str
    topology_type: Literal["face", "edge"]
    role: str
    source_entity_id: str | None = None
    expected_signature: str


class SemanticTopologyReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_id: str
    owner_feature_id: str
    topology_type: Literal["face", "edge"]
    role: str
    source_entity_id: str | None = None
    ordinal: int = Field(ge=0)
    geometric_signature: str
    measurements: dict[str, float | int | str] = Field(default_factory=dict)


class ResolvedTopologyReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_reference_id: str
    resolved_reference_id: str
    owner_feature_id: str
    topology_type: Literal["face", "edge"]
    role: str
    source_entity_id: str | None = None
    recovery_state: Literal["exact", "recovered"]
    expected_signature: str
    current_signature: str


class FeatureRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_id: str
    feature_type: Literal["extrude", "hole", "revolve", "fillet", "chamfer", "linear_pattern", "circular_pattern", "mirror", "shell"] = "extrude"
    name: str
    body_id: str
    sketch_id: str
    profile_id: str | None = None
    source_region_id: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    topology_references: list[TopologyReferenceSelector] = Field(default_factory=list)
    parameters: ExtrudeParameters | HoleParameters | RevolveParameters | FilletParameters | ChamferParameters | LinearPatternParameters | CircularPatternParameters | MirrorParameters | ShellParameters
    suppressed: bool = False

    @model_validator(mode="after")
    def validate_feature_parameters(self) -> "FeatureRecord":
        if self.feature_type == "extrude":
            if not isinstance(self.parameters, ExtrudeParameters):
                raise ValueError("extrude feature requires extrusion parameters")
            if not self.profile_id:
                raise ValueError("extrude feature requires profile_id")
        elif self.feature_type == "hole":
            if not isinstance(self.parameters, HoleParameters):
                raise ValueError("hole feature requires hole parameters")
            if self.profile_id is not None:
                raise ValueError("hole feature does not use profile_id")
        elif self.feature_type == "revolve":
            if not isinstance(self.parameters, RevolveParameters):
                raise ValueError("revolve feature requires revolve parameters")
            if not self.profile_id:
                raise ValueError("revolve feature requires profile_id")
        elif self.feature_type == "fillet":
            if not isinstance(self.parameters, FilletParameters):
                raise ValueError("fillet feature requires fillet parameters")
            if self.profile_id is not None:
                raise ValueError("fillet feature does not use profile_id")
        elif self.feature_type == "chamfer":
            if not isinstance(self.parameters, ChamferParameters):
                raise ValueError("chamfer feature requires chamfer parameters")
            if self.profile_id is not None:
                raise ValueError("chamfer feature does not use profile_id")
        elif self.feature_type == "linear_pattern":
            if not isinstance(self.parameters, LinearPatternParameters):
                raise ValueError("linear pattern feature requires linear pattern parameters")
            if self.profile_id is not None:
                raise ValueError("linear pattern feature does not use profile_id")
        elif self.feature_type == "circular_pattern":
            if not isinstance(self.parameters, CircularPatternParameters):
                raise ValueError("circular pattern feature requires circular pattern parameters")
            if self.profile_id is not None:
                raise ValueError("circular pattern feature does not use profile_id")
        elif self.feature_type == "mirror":
            if not isinstance(self.parameters, MirrorParameters):
                raise ValueError("mirror feature requires mirror parameters")
            if self.profile_id is not None:
                raise ValueError("mirror feature does not use profile_id")
        else:
            if not isinstance(self.parameters, ShellParameters):
                raise ValueError("shell feature requires shell parameters")
            if self.profile_id is not None:
                raise ValueError("shell feature does not use profile_id")
        return self


class FeatureBuildError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    detail: dict[str, object] = Field(default_factory=dict)


class FeatureMeasurements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    net_profile_area_mm2: float
    volume_delta_mm3: float
    bounds_mm: tuple[float, float, float, float, float, float]
    hole_count: int


class FeatureBuildRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_id: str
    order: int
    status: Literal["succeeded", "suppressed", "failed", "blocked"]
    input_hash: str
    output_signature: str | None = None
    measurements: FeatureMeasurements | None = None
    generated_topology: list[SemanticTopologyReference] = Field(default_factory=list)
    resolved_references: list[ResolvedTopologyReference] = Field(default_factory=list)
    measurement_coverage: Literal["exact", "kernel_required"] = "exact"
    error: FeatureBuildError | None = None


class FeatureRebuildReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    document_id: str
    input_revision: int
    ok: bool
    rebuild_order: list[str] = Field(default_factory=list)
    records: list[FeatureBuildRecord] = Field(default_factory=list)
    content_hash: str


class ArtifactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    feature_id: str
    revision: int = Field(ge=0)
    format: Literal["step", "stl"]
    path: str
    content_hash: str
    metadata: dict[str, object] = Field(default_factory=dict)


class DesignParameterBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binding_type: Literal[
        "rectangle_profile_width",
        "circle_center_x",
        "hole_position_x",
        "hole_diameter",
    ]
    target_id: str
    scale: float = 1.0
    offset: float = 0.0

    @model_validator(mode="after")
    def validate_binding(self) -> "DesignParameterBinding":
        if not self.target_id.strip():
            raise ValueError("design parameter binding target_id cannot be empty")
        if not math.isfinite(self.scale) or not math.isfinite(self.offset):
            raise ValueError("design parameter binding scale and offset must be finite")
        return self


class DesignParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameter_id: str
    name: str
    value: float
    unit: Literal["mm"] = "mm"
    minimum: float | None = None
    maximum: float | None = None
    bindings: list[DesignParameterBinding] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_parameter(self) -> "DesignParameter":
        if not self.parameter_id.strip() or not self.name.strip():
            raise ValueError("design parameter id and name cannot be empty")
        bounds = [self.value, self.minimum, self.maximum]
        if not all(value is None or math.isfinite(value) for value in bounds):
            raise ValueError("design parameter values and bounds must be finite")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("design parameter minimum cannot exceed maximum")
        if self.minimum is not None and self.value < self.minimum:
            raise ValueError("design parameter value is below its minimum")
        if self.maximum is not None and self.value > self.maximum:
            raise ValueError("design parameter value is above its maximum")
        binding_keys = [(binding.binding_type, binding.target_id) for binding in self.bindings]
        if len(binding_keys) != len(set(binding_keys)):
            raise ValueError("duplicate bindings are not allowed within a design parameter")
        return self


class SketchMathDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "1.1"] = "1.1"
    document_id: str
    name: str = "SketchMath document"
    units: str = "mm"
    revision: int = Field(default=0, ge=0)
    bodies: list[BodyRecord] = Field(default_factory=list)
    sketches: list[SketchRecord] = Field(default_factory=list)
    features: list[FeatureRecord] = Field(default_factory=list)
    design_parameters: list[DesignParameter] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    provenance: dict[str, object] = Field(default_factory=dict)
    last_rebuild: FeatureRebuildReport | None = None

    @model_validator(mode="after")
    def validate_identity_graph(self) -> "SketchMathDocument":
        if self.design_parameters and self.schema_version != "1.1":
            raise ValueError("design parameters require document schema version 1.1")
        for label, values in (
            ("body", [item.body_id for item in self.bodies]),
            ("sketch", [item.sketch_id for item in self.sketches]),
            ("feature", [item.feature_id for item in self.features]),
            ("design parameter", [item.parameter_id for item in self.design_parameters]),
            ("artifact", [item.artifact_id for item in self.artifacts]),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label} ids are not allowed")

        body_ids = {body.body_id for body in self.bodies}
        sketch_ids = {sketch.sketch_id for sketch in self.sketches}
        feature_ids = {feature.feature_id for feature in self.features}
        entity_ids = {entity.id for sketch in self.sketches for entity in sketch.state.items}
        for body in self.bodies:
            if not set(body.sketch_ids).issubset(sketch_ids):
                raise ValueError(f"body {body.body_id} references an unknown sketch")
            if not set(body.feature_ids).issubset(feature_ids):
                raise ValueError(f"body {body.body_id} references an unknown feature")
        for feature in self.features:
            if feature.body_id not in body_ids:
                raise ValueError(f"feature {feature.feature_id} references an unknown body")
            if feature.sketch_id not in sketch_ids:
                raise ValueError(f"feature {feature.feature_id} references an unknown sketch")
        binding_keys: list[tuple[str, str]] = []
        for parameter in self.design_parameters:
            for binding in parameter.bindings:
                if binding.binding_type in {"rectangle_profile_width", "circle_center_x"}:
                    if binding.target_id not in entity_ids:
                        raise ValueError(f"design parameter {parameter.parameter_id} references an unknown entity")
                elif binding.target_id not in feature_ids:
                    raise ValueError(f"design parameter {parameter.parameter_id} references an unknown feature")
                binding_keys.append((binding.binding_type, binding.target_id))
        if len(binding_keys) != len(set(binding_keys)):
            raise ValueError("design parameter bindings must have one owner")
        return self


def wrap_legacy_selection_context(
    state: SelectionContext,
    *,
    document_id: str,
    name: str = "Imported SketchMath session",
) -> SketchMathDocument:
    return SketchMathDocument(
        document_id=document_id,
        name=name,
        units=state.units,
        bodies=[BodyRecord(body_id="body_main", name="Main body", sketch_ids=["sketch_main"])],
        sketches=[SketchRecord(sketch_id="sketch_main", name="Main sketch", state=state.model_copy(deep=True))],
        provenance={"migration": "legacy_selection_context_v1", "preserved_selection_set_id": state.selection_set_id},
    )
