from __future__ import annotations

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
    feature_type: Literal["extrude"] = "extrude"
    name: str
    body_id: str
    sketch_id: str
    profile_id: str
    source_region_id: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    topology_references: list[TopologyReferenceSelector] = Field(default_factory=list)
    parameters: ExtrudeParameters
    suppressed: bool = False


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


class SketchMathDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    document_id: str
    name: str = "SketchMath document"
    units: str = "mm"
    revision: int = Field(default=0, ge=0)
    bodies: list[BodyRecord] = Field(default_factory=list)
    sketches: list[SketchRecord] = Field(default_factory=list)
    features: list[FeatureRecord] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    provenance: dict[str, object] = Field(default_factory=dict)
    last_rebuild: FeatureRebuildReport | None = None

    @model_validator(mode="after")
    def validate_identity_graph(self) -> "SketchMathDocument":
        for label, values in (
            ("body", [item.body_id for item in self.bodies]),
            ("sketch", [item.sketch_id for item in self.sketches]),
            ("feature", [item.feature_id for item in self.features]),
            ("artifact", [item.artifact_id for item in self.artifacts]),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label} ids are not allowed")

        body_ids = {body.body_id for body in self.bodies}
        sketch_ids = {sketch.sketch_id for sketch in self.sketches}
        feature_ids = {feature.feature_id for feature in self.features}
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
