import React, { useEffect, useMemo, useState } from "react";
import { Box, Button, Heading, HStack, Input, Link, Select, Text, VStack } from "@chakra-ui/react";

import type {
  SketchMathArtifactJobManifest,
  SketchMathDocument,
  SketchMathFeature,
  SketchMathFeatureBuildRecord,
  SketchMathExtrudeParameters,
  SketchMathHoleParameters,
  SketchMathLineEntity,
  SketchMathProfileEntity,
  SketchMathSemanticTopologyReference,
} from "../../services/sketchmath";

type HoleDraft = {
  x: string;
  y: string;
  diameter: string;
  depth: string;
  termination: "through" | "blind";
  style: "simple" | "counterbore" | "countersink";
  counterboreDiameter: string;
  counterboreDepth: string;
  countersinkDiameter: string;
  countersinkAngle: string;
};

type RevolveDraft = { axisId: string; angle: string };
type ExtrusionDraft = { depth: string; extent: SketchMathExtrudeParameters["extent"]; secondDepth: string; direction: SketchMathExtrudeParameters["direction"] };

type FeatureHistoryPanelProps = {
  document: SketchMathDocument;
  activeProfile: SketchMathProfileEntity | null;
  newDepthValue: string;
  busy: boolean;
  canUndo: boolean;
  canRedo: boolean;
  holeFeaturesEnabled: boolean;
  revolveFeaturesEnabled: boolean;
  filletFeaturesEnabled: boolean;
  chamferFeaturesEnabled: boolean;
  artifactJobsEnabled: boolean;
  revolveAxes: SketchMathLineEntity[];
  artifactJobs: Record<string, SketchMathArtifactJobManifest>;
  onNewDepthValueChange: (value: string) => void;
  onAddExtrusion: (profile: SketchMathProfileEntity, depth: number, operation: "new_body" | "add" | "cut") => void;
  onAddFullRevolve: (profile: SketchMathProfileEntity, axis: SketchMathLineEntity) => void;
  onAddOuterFillet: (
    feature: Extract<SketchMathFeature, { feature_type: "extrude" }>,
    edgeReferences: SketchMathSemanticTopologyReference[],
    radius: number,
  ) => void;
  onAddOuterChamfer: (
    feature: Extract<SketchMathFeature, { feature_type: "extrude" }>,
    edgeReferences: SketchMathSemanticTopologyReference[],
    distance: number,
  ) => void;
  onUpdateExtrusion: (feature: Extract<SketchMathFeature, { feature_type: "extrude" }>, parameters: SketchMathExtrudeParameters) => void;
  onUpdateFilletRadius: (feature: Extract<SketchMathFeature, { feature_type: "fillet" }>, radius: number) => void;
  onUpdateChamferDistance: (feature: Extract<SketchMathFeature, { feature_type: "chamfer" }>, distance: number) => void;
  onUpdateHole: (
    feature: Extract<SketchMathFeature, { feature_type: "hole" }>,
    parameters: SketchMathHoleParameters,
  ) => void;
  onUpdateFullRevolve: (
    feature: Extract<SketchMathFeature, { feature_type: "revolve" }>,
    axisId: string,
    angle: number,
  ) => void;
  onSetDesignParameter: (parameterId: string, value: number) => void;
  onRenameFeature: (feature: SketchMathFeature, name: string) => void;
  onAddSimpleHole: (
    feature: Extract<SketchMathFeature, { feature_type: "extrude" }>,
    topReference: SketchMathSemanticTopologyReference,
    position: [number, number],
    diameter: number,
    termination: "through" | "blind",
    depth: number | null,
  ) => void;
  onBuildArtifact: (feature: SketchMathFeature, format: "step" | "stl") => void;
  onRetryArtifact: (job: SketchMathArtifactJobManifest) => void;
  artifactDownloadUrl: (path: string, format: "step" | "stl") => string;
  onUndo: () => void;
  onRedo: () => void;
};

const recordByFeature = (records: SketchMathFeatureBuildRecord[]): Record<string, SketchMathFeatureBuildRecord> =>
  Object.fromEntries(records.map((record) => [record.feature_id, record]));

const validDepth = (value: string): number | null => {
  const depth = Number(value);
  return Number.isFinite(depth) && depth > 0 ? Number(depth.toFixed(2)) : null;
};

type ModelTreeSelection = {
  kind: "body" | "sketch" | "feature";
  id: string;
};

const selectionKey = (selection: ModelTreeSelection): string => `${selection.kind}:${selection.id}`;

const featureTypeLabel = (feature: SketchMathFeature): string => ({
  extrude: "Extrude",
  hole: "Hole",
  revolve: "Revolve",
  fillet: "Fillet",
  chamfer: "Chamfer",
})[feature.feature_type];

const featurePropertySummary = (feature: SketchMathFeature): string => {
  if (feature.feature_type === "extrude") return `Depth ${feature.parameters.depth_mm} mm · ${feature.parameters.extent.replace("_", " ")}`;
  if (feature.feature_type === "hole") {
    const depth = feature.parameters.termination === "blind" ? ` · depth ${feature.parameters.depth_mm} mm` : "";
    return `${feature.parameters.style} · ${feature.parameters.termination} · diameter ${feature.parameters.diameter_mm} mm${depth}`;
  }
  if (feature.feature_type === "revolve") return `Angle ${feature.parameters.angle_deg}° · construction axis`;
  if (feature.feature_type === "fillet") return `Radius ${feature.parameters.radius_mm} mm`;
  return `Distance ${feature.parameters.distance_mm} mm`;
};

const FeatureHistoryPanel = ({
  document,
  activeProfile,
  newDepthValue,
  busy,
  canUndo,
  canRedo,
  holeFeaturesEnabled,
  revolveFeaturesEnabled,
  filletFeaturesEnabled,
  chamferFeaturesEnabled,
  artifactJobsEnabled,
  revolveAxes,
  artifactJobs,
  onNewDepthValueChange,
  onAddExtrusion,
  onAddFullRevolve,
  onAddOuterFillet,
  onAddOuterChamfer,
  onUpdateExtrusion,
  onUpdateFilletRadius,
  onUpdateChamferDistance,
  onUpdateHole,
  onUpdateFullRevolve,
  onSetDesignParameter,
  onRenameFeature,
  onAddSimpleHole,
  onBuildArtifact,
  onRetryArtifact,
  artifactDownloadUrl,
  onUndo,
  onRedo,
}: FeatureHistoryPanelProps) => {
  const [extrusionDrafts, setExtrusionDrafts] = useState<Record<string, ExtrusionDraft>>({});
  const [holeDrafts, setHoleDrafts] = useState<Record<string, HoleDraft>>({});
  const [filletDrafts, setFilletDrafts] = useState<Record<string, string>>({});
  const [chamferDrafts, setChamferDrafts] = useState<Record<string, string>>({});
  const [parameterDrafts, setParameterDrafts] = useState<Record<string, string>>({});
  const [revolveDrafts, setRevolveDrafts] = useState<Record<string, RevolveDraft>>({});
  const [revolveAxisId, setRevolveAxisId] = useState("");
  const [newExtrusionOperation, setNewExtrusionOperation] = useState<"new_body" | "add" | "cut">(
    document.features.length === 0 ? "new_body" : "add",
  );
  const defaultSelection = useMemo<ModelTreeSelection | null>(() => {
    const feature = document.features[document.features.length - 1];
    if (feature) return { kind: "feature", id: feature.feature_id };
    const sketch = document.sketches[0];
    if (sketch) return { kind: "sketch", id: sketch.sketch_id };
    const body = document.bodies[0];
    return body ? { kind: "body", id: body.body_id } : null;
  }, [document.bodies, document.features, document.sketches]);
  const [treeSelection, setTreeSelection] = useState<ModelTreeSelection | null>(defaultSelection);
  const [featureNameDraft, setFeatureNameDraft] = useState("");
  const designParameters = useMemo(() => document.design_parameters || [], [document.design_parameters]);
  const boundFeatureIds = useMemo(() => new Set(
    designParameters.flatMap((parameter) => parameter.bindings.map((binding) => binding.target_id)),
  ), [designParameters]);
  const buildRecords = useMemo(
    () => recordByFeature(document.last_rebuild?.records || []),
    [document.last_rebuild?.records],
  );

  useEffect(() => {
    setExtrusionDrafts(Object.fromEntries(
      document.features
        .filter((feature): feature is Extract<SketchMathFeature, { feature_type: "extrude" }> => feature.feature_type === "extrude")
        .map((feature) => [feature.feature_id, {
          depth: String(feature.parameters.depth_mm),
          extent: feature.parameters.extent,
          secondDepth: String(feature.parameters.second_depth_mm ?? ""),
          direction: feature.parameters.direction,
        }]),
    ));
  }, [document.features]);

  useEffect(() => {
    setChamferDrafts((current) => Object.fromEntries(
      document.features
        .filter((feature) => feature.feature_type === "extrude" || feature.feature_type === "chamfer")
        .map((feature) => [
          feature.feature_id,
          feature.feature_type === "chamfer" ? String(feature.parameters.distance_mm) : current[feature.feature_id] || "2",
        ]),
    ));
  }, [document.features]);

  useEffect(() => {
    setHoleDrafts((current) => Object.fromEntries(
      document.features
        .filter((feature) => feature.feature_type === "extrude" || feature.feature_type === "hole")
        .map((feature) => {
          if (feature.feature_type === "hole") {
            return [feature.feature_id, {
              x: String(feature.parameters.position_mm[0]),
              y: String(feature.parameters.position_mm[1]),
              diameter: String(feature.parameters.diameter_mm),
              depth: String(feature.parameters.depth_mm ?? ""),
              termination: feature.parameters.termination,
              style: feature.parameters.style,
              counterboreDiameter: String(feature.parameters.counterbore_diameter_mm ?? ""),
              counterboreDepth: String(feature.parameters.counterbore_depth_mm ?? ""),
              countersinkDiameter: String(feature.parameters.countersink_diameter_mm ?? ""),
              countersinkAngle: String(feature.parameters.countersink_angle_deg ?? ""),
            } satisfies HoleDraft];
          }
          const record = buildRecords[feature.feature_id];
          const bounds = record?.measurements?.bounds_mm;
          return [feature.feature_id, current[feature.feature_id] || {
            x: bounds ? String((bounds[0] + bounds[1]) / 2) : "0",
            y: bounds ? String((bounds[2] + bounds[3]) / 2) : "0",
            diameter: "4",
            depth: bounds ? String((bounds[5] - bounds[4]) / 2) : "5",
            termination: "through",
            style: "simple",
            counterboreDiameter: "",
            counterboreDepth: "",
            countersinkDiameter: "",
            countersinkAngle: "",
          }];
        }),
    ));
  }, [buildRecords, document.features]);

  useEffect(() => {
    setFilletDrafts((current) => Object.fromEntries(
      document.features
        .filter((feature) => feature.feature_type === "extrude" || feature.feature_type === "fillet")
        .map((feature) => [
          feature.feature_id,
          feature.feature_type === "fillet" ? String(feature.parameters.radius_mm) : current[feature.feature_id] || "2",
        ]),
    ));
  }, [document.features]);

  useEffect(() => {
    setParameterDrafts(Object.fromEntries(
      designParameters.map((parameter) => [parameter.parameter_id, String(parameter.value)]),
    ));
  }, [designParameters]);

  useEffect(() => {
    setRevolveDrafts(Object.fromEntries(
      document.features
        .filter((feature): feature is Extract<SketchMathFeature, { feature_type: "revolve" }> => feature.feature_type === "revolve")
        .map((feature) => [feature.feature_id, {
          axisId: feature.parameters.axis_entity_id,
          angle: String(feature.parameters.angle_deg),
        }]),
    ));
  }, [document.features]);

  const newDepth = validDepth(newDepthValue);
  const effectiveNewExtrusionOperation = document.features.length === 0
    ? "new_body"
    : newExtrusionOperation === "new_body" ? "add" : newExtrusionOperation;
  const revolveAxis = revolveAxes.find((axis) => axis.id === revolveAxisId) || revolveAxes[0] || null;
  const selectedBody = treeSelection?.kind === "body"
    ? document.bodies.find((body) => body.body_id === treeSelection.id) || null
    : null;
  const selectedSketch = treeSelection?.kind === "sketch"
    ? document.sketches.find((sketch) => sketch.sketch_id === treeSelection.id) || null
    : null;
  const selectedFeature = treeSelection?.kind === "feature"
    ? document.features.find((feature) => feature.feature_id === treeSelection.id) || null
    : null;
  const normalizedFeatureName = featureNameDraft.trim();

  useEffect(() => {
    const validSelections = new Set([
      ...document.bodies.map((body) => `body:${body.body_id}`),
      ...document.sketches.map((sketch) => `sketch:${sketch.sketch_id}`),
      ...document.features.map((feature) => `feature:${feature.feature_id}`),
    ]);
    if (!treeSelection || !validSelections.has(selectionKey(treeSelection))) {
      setTreeSelection(defaultSelection);
    }
  }, [defaultSelection, document.bodies, document.features, document.sketches, treeSelection]);

  useEffect(() => {
    setFeatureNameDraft(selectedFeature?.name || "");
  }, [selectedFeature?.feature_id, selectedFeature?.name]);

  useEffect(() => {
    if (!revolveAxes.some((axis) => axis.id === revolveAxisId)) {
      setRevolveAxisId(revolveAxes[0]?.id || "");
    }
  }, [revolveAxes, revolveAxisId]);

  return (
    <Box className="sketchmath-panel sketchmath-feature-history" data-testid="sketchmath-feature-history-panel">
      <HStack justify="space-between" align="center" mb={3}>
        <Heading size="sm" className="sketchmath-panel-title">Feature history</Heading>
        <Text fontSize="sm" data-testid="sketchmath-document-revision">Revision {document.revision}</Text>
      </HStack>
      <Text fontSize="sm" opacity={0.78} data-testid="sketchmath-rebuild-status">
        Rebuild {document.last_rebuild?.ok === false ? "failed" : "passed"} · {document.features.length} feature{document.features.length === 1 ? "" : "s"}
      </Text>

      {designParameters.length > 0 ? (
        <Box className="sketchmath-inline-editor" mt={3} data-testid="sketchmath-design-parameters">
          <Text fontSize="sm" fontWeight="600">Design parameters</Text>
          <VStack align="stretch" spacing={2} mt={2}>
            {designParameters.map((parameter) => {
              const draft = parameterDrafts[parameter.parameter_id] ?? String(parameter.value);
              const value = Number(draft);
              const valid = Number.isFinite(value)
                && (parameter.minimum == null || value >= parameter.minimum)
                && (parameter.maximum == null || value <= parameter.maximum);
              return (
                <HStack
                  key={parameter.parameter_id}
                  spacing={2}
                  flexWrap="wrap"
                  data-testid={`sketchmath-design-parameter-${parameter.parameter_id}`}
                >
                  <Text fontSize="sm" style={{ minWidth: "145px" }}>{parameter.name}</Text>
                  <Input
                    type="number"
                    min={parameter.minimum ?? undefined}
                    max={parameter.maximum ?? undefined}
                    step="0.01"
                    aria-label={parameter.name}
                    value={draft}
                    onChange={(event) => setParameterDrafts((current) => ({
                      ...current,
                      [parameter.parameter_id]: event.target.value,
                    }))}
                    width="110px"
                  />
                  <Text fontSize="sm">{parameter.unit}</Text>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => valid && onSetDesignParameter(parameter.parameter_id, value)}
                    isDisabled={!valid || value === parameter.value || busy}
                  >
                    Apply
                  </Button>
                </HStack>
              );
            })}
          </VStack>
        </Box>
      ) : null}

      <Box className="sketchmath-inline-editor" mt={3} data-testid="sketchmath-model-tree">
        <Text fontSize="sm" fontWeight="600">Model tree</Text>
        <Text fontSize="xs" opacity={0.7} mt={1}>{document.name}</Text>
        <VStack align="stretch" spacing={1} mt={2}>
          {document.bodies.map((body) => (
            <React.Fragment key={body.body_id}>
              <Button
                size="xs"
                variant={selectedBody?.body_id === body.body_id ? "solid" : "ghost"}
                style={{ justifyContent: "flex-start" }}
                onClick={() => setTreeSelection({ kind: "body", id: body.body_id })}
                aria-pressed={selectedBody?.body_id === body.body_id}
              >
                Body · {body.name}
              </Button>
              {document.sketches
                .filter((sketch) => body.sketch_ids.includes(sketch.sketch_id))
                .map((sketch) => (
                  <Button
                    key={sketch.sketch_id}
                    size="xs"
                    variant={selectedSketch?.sketch_id === sketch.sketch_id ? "solid" : "ghost"}
                    style={{ justifyContent: "flex-start", marginLeft: "1rem" }}
                    onClick={() => setTreeSelection({ kind: "sketch", id: sketch.sketch_id })}
                    aria-pressed={selectedSketch?.sketch_id === sketch.sketch_id}
                  >
                    Sketch · {sketch.name}
                  </Button>
                ))}
              {document.features
                .filter((feature) => feature.body_id === body.body_id)
                .map((feature) => (
                  <Button
                    key={feature.feature_id}
                    size="xs"
                    variant={selectedFeature?.feature_id === feature.feature_id ? "solid" : "ghost"}
                    style={{ justifyContent: "flex-start", marginLeft: "1rem" }}
                    onClick={() => setTreeSelection({ kind: "feature", id: feature.feature_id })}
                    aria-pressed={selectedFeature?.feature_id === feature.feature_id}
                  >
                    {featureTypeLabel(feature)} · {feature.name}{feature.suppressed ? " · Suppressed" : ""}
                  </Button>
                ))}
            </React.Fragment>
          ))}
        </VStack>
      </Box>

      {treeSelection ? (
        <Box className="sketchmath-inline-editor" mt={3} data-testid="sketchmath-model-properties">
          <Text fontSize="sm" fontWeight="600">Properties</Text>
          {selectedBody ? (
            <Text fontSize="sm" opacity={0.78} mt={1}>
              Body · {selectedBody.visible ? "Visible" : "Hidden"} · {selectedBody.feature_ids.length} feature{selectedBody.feature_ids.length === 1 ? "" : "s"}
            </Text>
          ) : null}
          {selectedSketch ? (
            <Text fontSize="sm" opacity={0.78} mt={1}>
              Sketch · {selectedSketch.plane.toUpperCase()} plane · {selectedSketch.visible ? "Visible" : "Hidden"}
            </Text>
          ) : null}
          {selectedFeature ? (
            <>
              <Text fontSize="sm" opacity={0.78} mt={1}>
                {featureTypeLabel(selectedFeature)} · {selectedFeature.parameters.operation} · {featurePropertySummary(selectedFeature)}
              </Text>
              <HStack spacing={2} flexWrap="wrap" mt={2}>
                <Input
                  aria-label="Selected feature name"
                  value={featureNameDraft}
                  maxLength={80}
                  onChange={(event) => setFeatureNameDraft(event.target.value)}
                  width="190px"
                />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onRenameFeature(selectedFeature, normalizedFeatureName)}
                  isDisabled={
                    busy
                    || normalizedFeatureName.length === 0
                    || normalizedFeatureName === selectedFeature.name
                  }
                >
                  Rename feature
                </Button>
              </HStack>
            </>
          ) : null}
        </Box>
      ) : null}

      <Box className="sketchmath-inline-editor" mt={3}>
        <Text fontSize="sm" fontWeight="600">New extrusion</Text>
        <Text fontSize="sm" opacity={0.75} mt={1}>
          {activeProfile ? `Source profile: ${activeProfile.label || "Selected closed profile"}` : "Select a closed profile to add a feature."}
        </Text>
        <HStack spacing={2} flexWrap="wrap" mt={2}>
          <Input
            type="number"
            min="0.01"
            step="0.01"
            aria-label="Feature extrusion depth"
            value={newDepthValue}
            onChange={(event) => onNewDepthValueChange(event.target.value)}
            width="110px"
          />
          <Button
            size="sm"
            onClick={() => activeProfile && newDepth != null && onAddExtrusion(activeProfile, newDepth, effectiveNewExtrusionOperation)}
            isDisabled={!activeProfile || newDepth == null || busy}
            data-testid="sketchmath-add-feature"
          >
            Add extrusion feature
          </Button>
          <Select
            aria-label="New extrusion operation"
            value={effectiveNewExtrusionOperation}
            onChange={(event) => setNewExtrusionOperation(event.target.value as "new_body" | "add" | "cut")}
            width="120px"
            isDisabled={document.features.length === 0}
          >
            {document.features.length === 0 ? <option value="new_body">New body</option> : null}
            {document.features.length > 0 ? <option value="add">Add</option> : null}
            {document.features.length > 0 ? <option value="cut">Cut</option> : null}
          </Select>
        </HStack>
      </Box>

      {revolveFeaturesEnabled ? (
        <Box className="sketchmath-inline-editor" mt={3} data-testid="sketchmath-revolve-editor">
          <Text fontSize="sm" fontWeight="600">New full revolve</Text>
          <Text fontSize="sm" opacity={0.75} mt={1}>
            {activeProfile
              ? "Choose a construction-line axis. The profile must remain on one side of the axis."
              : "Select a closed profile and create a construction line for the axis."}
          </Text>
          <HStack spacing={2} flexWrap="wrap" mt={2}>
            <Select
              aria-label="Revolve axis"
              value={revolveAxis?.id || ""}
              onChange={(event) => setRevolveAxisId(event.target.value)}
              width="190px"
              placeholder="No construction axis"
            >
              {revolveAxes.map((axis, index) => (
                <option key={axis.id} value={axis.id}>{axis.label || `Construction axis ${index + 1}`}</option>
              ))}
            </Select>
            <Button
              size="sm"
              onClick={() => activeProfile && revolveAxis && onAddFullRevolve(activeProfile, revolveAxis)}
              isDisabled={!activeProfile || !revolveAxis || document.features.length > 0 || busy}
              data-testid="sketchmath-add-revolve-feature"
            >
              Add full revolve
            </Button>
          </HStack>
          {document.features.length > 0 ? (
            <Text fontSize="xs" opacity={0.65} mt={1}>The guarded UI currently creates new-body revolves only.</Text>
          ) : null}
        </Box>
      ) : null}

      <VStack align="stretch" spacing={3} mt={3}>
        {document.features.length === 0 ? (
          <Text fontSize="sm" opacity={0.72}>No committed features yet.</Text>
        ) : document.features.map((feature, featureIndex) => {
          const record = buildRecords[feature.feature_id];
          const extrusionDraft = feature.feature_type === "extrude" ? extrusionDrafts[feature.feature_id] : undefined;
          const nextDepth = validDepth(extrusionDraft?.depth || "");
          const nextSecondDepth = validDepth(extrusionDraft?.secondDepth || "");
          const nextExtrusionParameters: SketchMathExtrudeParameters | null = feature.feature_type === "extrude"
            && extrusionDraft
            && nextDepth != null
            && (extrusionDraft.extent !== "two_sided" || nextSecondDepth != null)
            ? {
              ...feature.parameters,
              depth_mm: nextDepth,
              extent: extrusionDraft.extent,
              second_depth_mm: extrusionDraft.extent === "two_sided" ? nextSecondDepth : null,
              direction: extrusionDraft.direction,
            }
            : null;
          const filletDraft = filletDrafts[feature.feature_id]
            ?? (feature.feature_type === "fillet" ? String(feature.parameters.radius_mm) : "2");
          const nextFilletRadius = validDepth(filletDraft);
          const chamferDraft = chamferDrafts[feature.feature_id]
            ?? (feature.feature_type === "chamfer" ? String(feature.parameters.distance_mm) : "2");
          const nextChamferDistance = validDepth(chamferDraft);
          const artifactJob = artifactJobs[feature.feature_id];
          const artifactFormat: "step" | "stl" = ["fillet", "chamfer"].includes(feature.feature_type) ? "step" : "stl";
          const registeredArtifact = artifactJob?.result?.artifact
            || document.artifacts.find((artifact) => (
              artifact.feature_id === feature.feature_id
              && artifact.revision === document.revision
              && artifact.format === artifactFormat
            ));
          const laterBodyFeatures = document.features.slice(featureIndex + 1).filter(
            (candidate) => candidate.body_id === feature.body_id && !candidate.suppressed,
          );
          const graphSupportsStl = document.features.slice(0, featureIndex + 1).every(
            (candidate) => candidate.body_id !== feature.body_id
              || candidate.suppressed
              || candidate.feature_type === "extrude"
              || (candidate.feature_type === "hole" && candidate.parameters.style === "simple"),
          );
          const bodyGraph = document.features.slice(0, featureIndex + 1).filter(
            (candidate) => candidate.body_id === feature.body_id && !candidate.suppressed,
          );
          const preFinishGraph = bodyGraph.slice(0, -1);
          const graphSupportsEdgeFinishStep = (feature.feature_type === "fillet" || feature.feature_type === "chamfer")
            && preFinishGraph.length > 0
            && preFinishGraph.every((candidate, index) => (
              candidate.feature_type === "extrude"
                ? candidate.parameters.operation === (index === 0 ? "new_body" : "add")
                : candidate.feature_type === "hole" && candidate.parameters.style === "simple"
            ));
          const canBuildArtifact = record?.status === "succeeded"
            && laterBodyFeatures.length === 0
            && (artifactFormat === "stl" ? graphSupportsStl : graphSupportsEdgeFinishStep);
          const artifactBusy = artifactJob?.state === "READY" || artifactJob?.state === "RUNNING";
          const topReference = record?.generated_topology.find((reference) => reference.topology_type === "face" && reference.role === "top");
          const verticalOuterEdges = record?.generated_topology.filter(
            (reference) => reference.topology_type === "edge"
              && reference.role === "vertical_outer_edge"
              && reference.measurements.corner_class === "convex",
          ) || [];
          const holeDraft = holeDrafts[feature.feature_id];
          const holeX = Number(holeDraft?.x);
          const holeY = Number(holeDraft?.y);
          const holeDiameter = Number(holeDraft?.diameter);
          const holeDepth = Number(holeDraft?.depth);
          const counterboreDiameter = Number(holeDraft?.counterboreDiameter);
          const counterboreDepth = Number(holeDraft?.counterboreDepth);
          const countersinkDiameter = Number(holeDraft?.countersinkDiameter);
          const countersinkAngle = Number(holeDraft?.countersinkAngle);
          const validHoleDraft = Boolean(
            holeDraft
            && Number.isFinite(holeX)
            && Number.isFinite(holeY)
            && Number.isFinite(holeDiameter)
            && holeDiameter > 0
            && (holeDraft.termination === "through" || (Number.isFinite(holeDepth) && holeDepth > 0)),
          );
          const validHoleStyle = Boolean(
            validHoleDraft
            && (
              holeDraft?.style === "simple"
              || (
                holeDraft?.style === "counterbore"
                && Number.isFinite(counterboreDiameter)
                && counterboreDiameter > holeDiameter
                && Number.isFinite(counterboreDepth)
                && counterboreDepth > 0
                && (holeDraft.termination === "through" || counterboreDepth <= holeDepth)
              )
              || (
                holeDraft?.style === "countersink"
                && Number.isFinite(countersinkDiameter)
                && countersinkDiameter > holeDiameter
                && Number.isFinite(countersinkAngle)
                && countersinkAngle > 0
                && countersinkAngle < 180
              )
            )
          );
          const nextHoleParameters: SketchMathHoleParameters | null = holeDraft && validHoleStyle ? {
            ...(feature.feature_type === "hole" ? feature.parameters : {
              operation: "cut" as const,
              position_mm: [holeX, holeY] as [number, number],
            }),
            style: holeDraft.style,
            termination: holeDraft.termination,
            diameter_mm: holeDiameter,
            depth_mm: holeDraft.termination === "blind" ? holeDepth : null,
            counterbore_diameter_mm: holeDraft.style === "counterbore" ? counterboreDiameter : null,
            counterbore_depth_mm: holeDraft.style === "counterbore" ? counterboreDepth : null,
            countersink_diameter_mm: holeDraft.style === "countersink" ? countersinkDiameter : null,
            countersink_angle_deg: holeDraft.style === "countersink" ? countersinkAngle : null,
          } : null;
          const featureParameterBound = boundFeatureIds.has(feature.feature_id);
          const revolveDraft = revolveDrafts[feature.feature_id];
          const revolveAngle = Number(revolveDraft?.angle);
          return (
            <Box
              key={feature.feature_id}
              className="sketchmath-history-row"
              data-testid={`sketchmath-feature-${feature.feature_id}`}
              style={selectedFeature?.feature_id === feature.feature_id ? { borderColor: "#33f6ff" } : undefined}
            >
              <Text fontWeight="600">{feature.name}</Text>
              <Text fontSize="sm" opacity={0.75}>
                {feature.feature_type} · {feature.parameters.operation} · {record?.status || "not rebuilt"}
                {feature.feature_type === "extrude" ? " · source profile" : ""}
                {feature.feature_type === "hole" ? ` · ${feature.parameters.style} ${feature.parameters.termination}` : ""}
                {feature.feature_type === "revolve" ? ` · ${feature.parameters.angle_deg}° about construction axis` : ""}
                {feature.feature_type === "fillet" ? ` · radius ${feature.parameters.radius_mm} mm` : ""}
                {feature.feature_type === "chamfer" ? ` · distance ${feature.parameters.distance_mm} mm` : ""}
                {record ? ` · ${record.generated_topology.length} semantic refs` : ""}
              </Text>
              {record?.measurements ? (
                <Text fontSize="sm" opacity={0.75} data-testid={`sketchmath-feature-measurements-${feature.feature_id}`}>
                  Volume {record.measurements.volume_delta_mm3} mm³ · {record.measurements.hole_count} hole{record.measurements.hole_count === 1 ? "" : "s"}
                </Text>
              ) : record?.measurement_coverage === "kernel_required" ? (
                <Text fontSize="sm" opacity={0.75}>Measurements require a validated kernel artifact.</Text>
              ) : null}
              {record?.output_signature ? (
                <Text fontSize="xs" opacity={0.62} data-testid={`sketchmath-feature-signature-${feature.feature_id}`}>
                  Signature {record.output_signature.slice(0, 12)}
                </Text>
              ) : null}
              {feature.feature_type === "extrude" ? (
                <HStack spacing={2} flexWrap="wrap" mt={2}>
                  <Input
                    type="number"
                    min="0.01"
                    step="0.01"
                    aria-label={`Feature depth ${feature.feature_id}`}
                    value={extrusionDraft?.depth || ""}
                    onChange={(event) => setExtrusionDrafts((current) => ({ ...current, [feature.feature_id]: { ...current[feature.feature_id], depth: event.target.value } }))}
                    width="110px"
                  />
                  <Select
                    aria-label={`Feature extent ${feature.feature_id}`}
                    value={extrusionDraft?.extent || "one_sided"}
                    onChange={(event) => setExtrusionDrafts((current) => ({ ...current, [feature.feature_id]: { ...current[feature.feature_id], extent: event.target.value as SketchMathExtrudeParameters["extent"], secondDepth: current[feature.feature_id]?.secondDepth || String(feature.parameters.depth_mm) } }))}
                    width="130px"
                  >
                    <option value="one_sided">One-sided</option>
                    <option value="symmetric">Symmetric</option>
                    <option value="two_sided">Two-sided</option>
                  </Select>
                  <Select
                    aria-label={`Feature direction ${feature.feature_id}`}
                    value={extrusionDraft?.direction || "positive"}
                    onChange={(event) => setExtrusionDrafts((current) => ({ ...current, [feature.feature_id]: { ...current[feature.feature_id], direction: event.target.value as SketchMathExtrudeParameters["direction"] } }))}
                    width="120px"
                  >
                    <option value="positive">Positive</option>
                    <option value="negative">Negative</option>
                  </Select>
                  {extrusionDraft?.extent === "two_sided" ? (
                    <Input
                      type="number"
                      min="0.01"
                      step="0.01"
                      aria-label={`Feature second depth ${feature.feature_id}`}
                      value={extrusionDraft.secondDepth}
                      onChange={(event) => setExtrusionDrafts((current) => ({ ...current, [feature.feature_id]: { ...current[feature.feature_id], secondDepth: event.target.value } }))}
                      width="110px"
                    />
                  ) : null}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => nextExtrusionParameters && onUpdateExtrusion(feature, nextExtrusionParameters)}
                    isDisabled={!nextExtrusionParameters || JSON.stringify(nextExtrusionParameters) === JSON.stringify(feature.parameters) || busy}
                  >
                    Apply extrusion
                  </Button>
                </HStack>
              ) : null}
              {filletFeaturesEnabled && feature.feature_type === "extrude" ? (
                <HStack spacing={2} flexWrap="wrap" mt={2} data-testid={`sketchmath-fillet-editor-${feature.feature_id}`}>
                  <Input
                    type="number"
                    min="0.01"
                    step="0.01"
                    aria-label={`Fillet radius ${feature.feature_id}`}
                    value={filletDraft}
                    onChange={(event) => setFilletDrafts((current) => ({ ...current, [feature.feature_id]: event.target.value }))}
                    width="110px"
                  />
                  <Button
                    size="sm"
                    onClick={() => nextFilletRadius != null && onAddOuterFillet(feature, verticalOuterEdges, nextFilletRadius)}
                    isDisabled={
                      nextFilletRadius == null
                      || verticalOuterEdges.length === 0
                      || document.features.length !== 1
                      || busy
                    }
                  >
                    Fillet outer edges
                  </Button>
                </HStack>
              ) : null}
              {chamferFeaturesEnabled && feature.feature_type === "extrude" ? (
                <HStack spacing={2} flexWrap="wrap" mt={2} data-testid={`sketchmath-chamfer-editor-${feature.feature_id}`}>
                  <Input
                    type="number"
                    min="0.01"
                    step="0.01"
                    aria-label={`Chamfer distance ${feature.feature_id}`}
                    value={chamferDraft}
                    onChange={(event) => setChamferDrafts((current) => ({ ...current, [feature.feature_id]: event.target.value }))}
                    width="110px"
                  />
                  <Button
                    size="sm"
                    onClick={() => nextChamferDistance != null && onAddOuterChamfer(feature, verticalOuterEdges, nextChamferDistance)}
                    isDisabled={
                      nextChamferDistance == null
                      || verticalOuterEdges.length === 0
                      || document.features.length !== 1
                      || busy
                    }
                  >
                    Chamfer outer edges
                  </Button>
                </HStack>
              ) : null}
              {feature.feature_type === "fillet" ? (
                <HStack spacing={2} flexWrap="wrap" mt={2}>
                  <Input
                    type="number"
                    min="0.01"
                    step="0.01"
                    aria-label={`Fillet radius ${feature.feature_id}`}
                    value={filletDraft}
                    onChange={(event) => setFilletDrafts((current) => ({ ...current, [feature.feature_id]: event.target.value }))}
                    width="110px"
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => nextFilletRadius != null && onUpdateFilletRadius(feature, nextFilletRadius)}
                    isDisabled={nextFilletRadius == null || nextFilletRadius === feature.parameters.radius_mm || busy}
                  >
                    Apply radius
                  </Button>
                </HStack>
              ) : null}
              {feature.feature_type === "chamfer" ? (
                <HStack spacing={2} flexWrap="wrap" mt={2}>
                  <Input
                    type="number"
                    min="0.01"
                    step="0.01"
                    aria-label={`Chamfer distance ${feature.feature_id}`}
                    value={chamferDraft}
                    onChange={(event) => setChamferDrafts((current) => ({ ...current, [feature.feature_id]: event.target.value }))}
                    width="110px"
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => nextChamferDistance != null && onUpdateChamferDistance(feature, nextChamferDistance)}
                    isDisabled={nextChamferDistance == null || nextChamferDistance === feature.parameters.distance_mm || busy}
                  >
                    Apply distance
                  </Button>
                </HStack>
              ) : null}
              {holeFeaturesEnabled && feature.feature_type === "hole" ? (
                <HStack spacing={2} flexWrap="wrap" mt={2} data-testid={`sketchmath-existing-hole-editor-${feature.feature_id}`}>
                  <Select
                    aria-label={`Existing hole style ${feature.name}`}
                    value={holeDraft?.style || "simple"}
                    onChange={(event) => setHoleDrafts((current) => ({
                      ...current,
                      [feature.feature_id]: {
                        ...current[feature.feature_id],
                        style: event.target.value as HoleDraft["style"],
                        counterboreDiameter: current[feature.feature_id]?.counterboreDiameter || String(holeDiameter * 2),
                        counterboreDepth: current[feature.feature_id]?.counterboreDepth || "2",
                        countersinkDiameter: current[feature.feature_id]?.countersinkDiameter || String(holeDiameter * 2),
                        countersinkAngle: current[feature.feature_id]?.countersinkAngle || "90",
                      },
                    }))}
                    width="145px"
                    isDisabled={featureParameterBound}
                  >
                    <option value="simple">Simple</option>
                    <option value="counterbore">Counterbore</option>
                    <option value="countersink">Countersink</option>
                  </Select>
                  <Input
                    type="number"
                    min="0.01"
                    step="0.01"
                    aria-label={`Existing hole diameter ${feature.name}`}
                    value={holeDraft?.diameter || ""}
                    onChange={(event) => setHoleDrafts((current) => ({
                      ...current,
                      [feature.feature_id]: { ...current[feature.feature_id], diameter: event.target.value },
                    }))}
                    width="100px"
                    isDisabled={featureParameterBound}
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setHoleDrafts((current) => ({
                      ...current,
                      [feature.feature_id]: {
                        ...current[feature.feature_id],
                        termination: current[feature.feature_id]?.termination === "blind" ? "through" : "blind",
                      },
                    }))}
                    isDisabled={featureParameterBound}
                  >
                    {holeDraft?.termination === "blind" ? "Blind" : "Through"}
                  </Button>
                  {holeDraft?.termination === "blind" ? (
                    <Input
                      type="number"
                      min="0.01"
                      step="0.01"
                      aria-label={`Existing hole depth ${feature.name}`}
                      value={holeDraft.depth}
                      onChange={(event) => setHoleDrafts((current) => ({
                        ...current,
                        [feature.feature_id]: { ...current[feature.feature_id], depth: event.target.value },
                      }))}
                      width="100px"
                      isDisabled={featureParameterBound}
                    />
                  ) : null}
                  {holeDraft?.style === "counterbore" ? (
                    <>
                      <Input
                        type="number"
                        min="0.01"
                        step="0.01"
                        aria-label={`Counterbore diameter ${feature.name}`}
                        value={holeDraft.counterboreDiameter}
                        onChange={(event) => setHoleDrafts((current) => ({ ...current, [feature.feature_id]: { ...current[feature.feature_id], counterboreDiameter: event.target.value } }))}
                        width="110px"
                        isDisabled={featureParameterBound}
                      />
                      <Input
                        type="number"
                        min="0.01"
                        step="0.01"
                        aria-label={`Counterbore depth ${feature.name}`}
                        value={holeDraft.counterboreDepth}
                        onChange={(event) => setHoleDrafts((current) => ({ ...current, [feature.feature_id]: { ...current[feature.feature_id], counterboreDepth: event.target.value } }))}
                        width="110px"
                        isDisabled={featureParameterBound}
                      />
                    </>
                  ) : null}
                  {holeDraft?.style === "countersink" ? (
                    <>
                      <Input
                        type="number"
                        min="0.01"
                        step="0.01"
                        aria-label={`Countersink diameter ${feature.name}`}
                        value={holeDraft.countersinkDiameter}
                        onChange={(event) => setHoleDrafts((current) => ({ ...current, [feature.feature_id]: { ...current[feature.feature_id], countersinkDiameter: event.target.value } }))}
                        width="110px"
                        isDisabled={featureParameterBound}
                      />
                      <Input
                        type="number"
                        min="0.01"
                        max="179.99"
                        step="0.01"
                        aria-label={`Countersink angle ${feature.name}`}
                        value={holeDraft.countersinkAngle}
                        onChange={(event) => setHoleDrafts((current) => ({ ...current, [feature.feature_id]: { ...current[feature.feature_id], countersinkAngle: event.target.value } }))}
                        width="110px"
                        isDisabled={featureParameterBound}
                      />
                    </>
                  ) : null}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => nextHoleParameters && onUpdateHole(feature, nextHoleParameters)}
                    isDisabled={
                      featureParameterBound
                      || !nextHoleParameters
                      || JSON.stringify(nextHoleParameters) === JSON.stringify(feature.parameters)
                      || busy
                    }
                  >
                    Apply hole
                  </Button>
                  {featureParameterBound ? <Text fontSize="xs">Controlled by a design parameter.</Text> : null}
                </HStack>
              ) : null}
              {revolveFeaturesEnabled && feature.feature_type === "revolve" ? (
                <HStack spacing={2} flexWrap="wrap" mt={2} data-testid={`sketchmath-existing-revolve-editor-${feature.feature_id}`}>
                  <Select
                    aria-label={`Revolve axis ${feature.name}`}
                    value={revolveDraft?.axisId || ""}
                    onChange={(event) => setRevolveDrafts((current) => ({
                      ...current,
                      [feature.feature_id]: { ...current[feature.feature_id], axisId: event.target.value },
                    }))}
                    width="180px"
                  >
                    {revolveAxes.map((axis, index) => (
                      <option key={axis.id} value={axis.id}>{axis.label || `Construction axis ${index + 1}`}</option>
                    ))}
                  </Select>
                  <Input
                    type="number"
                    min="360"
                    max="360"
                    aria-label={`Revolve angle ${feature.name}`}
                    value={revolveDraft?.angle || ""}
                    onChange={(event) => setRevolveDrafts((current) => ({
                      ...current,
                      [feature.feature_id]: { ...current[feature.feature_id], angle: event.target.value },
                    }))}
                    width="100px"
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => revolveDraft && onUpdateFullRevolve(feature, revolveDraft.axisId, revolveAngle)}
                    isDisabled={
                      !revolveDraft?.axisId
                      || revolveAngle !== 360
                      || (
                        revolveDraft.axisId === feature.parameters.axis_entity_id
                        && revolveAngle === feature.parameters.angle_deg
                      )
                      || busy
                    }
                  >
                    Apply revolve
                  </Button>
                  <Text fontSize="xs">Full 360° revolves are the supported envelope.</Text>
                </HStack>
              ) : null}
              {holeFeaturesEnabled && feature.feature_type === "extrude" ? (
                <Box mt={2} data-testid={`sketchmath-hole-editor-${feature.feature_id}`}>
                  <Text fontSize="sm" fontWeight="600">Simple hole</Text>
                  <HStack spacing={2} flexWrap="wrap" mt={1}>
                    <Input
                      type="number"
                      step="0.01"
                      aria-label={`Hole X ${feature.feature_id}`}
                      value={holeDraft?.x || ""}
                      onChange={(event) => setHoleDrafts((current) => ({
                        ...current,
                        [feature.feature_id]: { ...current[feature.feature_id], x: event.target.value },
                      }))}
                      width="90px"
                    />
                    <Input
                      type="number"
                      step="0.01"
                      aria-label={`Hole Y ${feature.feature_id}`}
                      value={holeDraft?.y || ""}
                      onChange={(event) => setHoleDrafts((current) => ({
                        ...current,
                        [feature.feature_id]: { ...current[feature.feature_id], y: event.target.value },
                      }))}
                      width="90px"
                    />
                    <Input
                      type="number"
                      min="0.01"
                      step="0.01"
                      aria-label={`Hole diameter ${feature.feature_id}`}
                      value={holeDraft?.diameter || ""}
                      onChange={(event) => setHoleDrafts((current) => ({
                        ...current,
                        [feature.feature_id]: { ...current[feature.feature_id], diameter: event.target.value },
                      }))}
                      width="90px"
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setHoleDrafts((current) => ({
                        ...current,
                        [feature.feature_id]: {
                          ...current[feature.feature_id],
                          termination: current[feature.feature_id]?.termination === "blind" ? "through" : "blind",
                        },
                      }))}
                    >
                      {holeDraft?.termination === "blind" ? "Blind" : "Through"}
                    </Button>
                    {holeDraft?.termination === "blind" ? (
                      <Input
                        type="number"
                        min="0.01"
                        step="0.01"
                        aria-label={`Hole depth ${feature.feature_id}`}
                        value={holeDraft.depth}
                        onChange={(event) => setHoleDrafts((current) => ({
                          ...current,
                          [feature.feature_id]: { ...current[feature.feature_id], depth: event.target.value },
                        }))}
                        width="90px"
                      />
                    ) : null}
                    <Button
                      size="sm"
                      onClick={() => topReference && holeDraft && onAddSimpleHole(
                        feature,
                        topReference,
                        [holeX, holeY],
                        holeDiameter,
                        holeDraft.termination,
                        holeDraft.termination === "blind" ? holeDepth : null,
                      )}
                      isDisabled={!topReference || !validHoleDraft || busy}
                    >
                      Add simple hole
                    </Button>
                  </HStack>
                </Box>
              ) : null}
              {artifactJobsEnabled ? (
                <Box mt={2} data-testid={`sketchmath-artifact-job-${feature.feature_id}`}>
                  <HStack spacing={2} flexWrap="wrap">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onBuildArtifact(feature, artifactFormat)}
                      isDisabled={!canBuildArtifact || artifactBusy || busy}
                    >
                      Build {artifactFormat.toUpperCase()}
                    </Button>
                    {artifactJob?.state === "FAILED" ? (
                      <Button size="sm" variant="outline" onClick={() => onRetryArtifact(artifactJob)} isDisabled={busy}>
                        Retry {artifactFormat.toUpperCase()}
                      </Button>
                    ) : null}
                    {registeredArtifact ? (
                      <Link
                        href={artifactDownloadUrl(registeredArtifact.path, registeredArtifact.format)}
                        download
                        data-testid={`sketchmath-artifact-download-${feature.feature_id}`}
                      >
                        Download {registeredArtifact.format.toUpperCase()}
                      </Link>
                    ) : null}
                  </HStack>
                  {artifactJob ? (
                    <Text fontSize="xs" opacity={0.72} mt={1} data-testid={`sketchmath-artifact-status-${feature.feature_id}`}>
                      {artifactJob.format.toUpperCase()} artifact · {artifactJob.state} · {artifactJob.step} · revision {artifactJob.input_revision}
                      {artifactJob.error ? ` · ${artifactJob.error.code}: ${artifactJob.error.message}` : ""}
                    </Text>
                  ) : !canBuildArtifact ? (
                    <Text fontSize="xs" opacity={0.65} mt={1}>Artifact build is available on the terminal supported body feature.</Text>
                  ) : null}
                </Box>
              ) : null}
            </Box>
          );
        })}
      </VStack>

      <HStack spacing={2} flexWrap="wrap" mt={3}>
        <Button size="sm" variant="outline" onClick={onUndo} isDisabled={!canUndo || busy}>Undo feature</Button>
        <Button size="sm" variant="outline" onClick={onRedo} isDisabled={!canRedo || busy}>Redo feature</Button>
      </HStack>
    </Box>
  );
};

export default FeatureHistoryPanel;
