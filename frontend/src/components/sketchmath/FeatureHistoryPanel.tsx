import React, { useEffect, useMemo, useState } from "react";
import { Box, Button, Heading, HStack, Input, Link, Select, Text, VStack } from "@chakra-ui/react";

import type {
  SketchMathArtifactJobManifest,
  SketchMathDocument,
  SketchMathFeature,
  SketchMathFeatureBuildRecord,
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
};

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
  artifactJobsEnabled: boolean;
  revolveAxes: SketchMathLineEntity[];
  artifactJobs: Record<string, SketchMathArtifactJobManifest>;
  onNewDepthValueChange: (value: string) => void;
  onAddExtrusion: (profile: SketchMathProfileEntity, depth: number) => void;
  onAddFullRevolve: (profile: SketchMathProfileEntity, axis: SketchMathLineEntity) => void;
  onAddOuterFillet: (
    feature: Extract<SketchMathFeature, { feature_type: "extrude" }>,
    edgeReferences: SketchMathSemanticTopologyReference[],
    radius: number,
  ) => void;
  onUpdateDepth: (feature: Extract<SketchMathFeature, { feature_type: "extrude" }>, depth: number) => void;
  onUpdateFilletRadius: (feature: Extract<SketchMathFeature, { feature_type: "fillet" }>, radius: number) => void;
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
  artifactJobsEnabled,
  revolveAxes,
  artifactJobs,
  onNewDepthValueChange,
  onAddExtrusion,
  onAddFullRevolve,
  onAddOuterFillet,
  onUpdateDepth,
  onUpdateFilletRadius,
  onAddSimpleHole,
  onBuildArtifact,
  onRetryArtifact,
  artifactDownloadUrl,
  onUndo,
  onRedo,
}: FeatureHistoryPanelProps) => {
  const [depthDrafts, setDepthDrafts] = useState<Record<string, string>>({});
  const [holeDrafts, setHoleDrafts] = useState<Record<string, HoleDraft>>({});
  const [filletDrafts, setFilletDrafts] = useState<Record<string, string>>({});
  const [revolveAxisId, setRevolveAxisId] = useState("");
  const buildRecords = useMemo(
    () => recordByFeature(document.last_rebuild?.records || []),
    [document.last_rebuild?.records],
  );

  useEffect(() => {
    setDepthDrafts(Object.fromEntries(
      document.features
        .filter((feature): feature is Extract<SketchMathFeature, { feature_type: "extrude" }> => feature.feature_type === "extrude")
        .map((feature) => [feature.feature_id, String(feature.parameters.depth_mm)]),
    ));
  }, [document.features]);

  useEffect(() => {
    setHoleDrafts((current) => Object.fromEntries(
      document.features
        .filter((feature): feature is Extract<SketchMathFeature, { feature_type: "extrude" }> => feature.feature_type === "extrude")
        .map((feature) => {
          const record = buildRecords[feature.feature_id];
          const bounds = record?.measurements?.bounds_mm;
          return [feature.feature_id, current[feature.feature_id] || {
            x: bounds ? String((bounds[0] + bounds[1]) / 2) : "0",
            y: bounds ? String((bounds[2] + bounds[3]) / 2) : "0",
            diameter: "4",
            depth: bounds ? String((bounds[5] - bounds[4]) / 2) : "5",
            termination: "through",
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

  const newDepth = validDepth(newDepthValue);
  const revolveAxis = revolveAxes.find((axis) => axis.id === revolveAxisId) || revolveAxes[0] || null;

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

      <Box className="sketchmath-inline-editor" mt={3}>
        <Text fontSize="sm" fontWeight="600">New extrusion</Text>
        <Text fontSize="sm" opacity={0.75} mt={1}>
          {activeProfile ? `Source profile: ${activeProfile.label || activeProfile.id}` : "Select a closed profile to add a feature."}
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
            onClick={() => activeProfile && newDepth != null && onAddExtrusion(activeProfile, newDepth)}
            isDisabled={!activeProfile || newDepth == null || busy}
            data-testid="sketchmath-add-feature"
          >
            Add extrusion feature
          </Button>
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
              {revolveAxes.map((axis) => (
                <option key={axis.id} value={axis.id}>{axis.label || axis.id}</option>
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
          const depthDraft = feature.feature_type === "extrude"
            ? depthDrafts[feature.feature_id] ?? String(feature.parameters.depth_mm)
            : "";
          const nextDepth = feature.feature_type === "extrude" ? validDepth(depthDraft) : null;
          const filletDraft = filletDrafts[feature.feature_id]
            ?? (feature.feature_type === "fillet" ? String(feature.parameters.radius_mm) : "2");
          const nextFilletRadius = validDepth(filletDraft);
          const artifactJob = artifactJobs[feature.feature_id];
          const artifactFormat: "step" | "stl" = feature.feature_type === "fillet" ? "step" : "stl";
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
          const graphSupportsFilletStep = feature.feature_type === "fillet"
            && bodyGraph.length === 2
            && bodyGraph[0].feature_type === "extrude"
            && bodyGraph[0].parameters.operation === "new_body"
            && bodyGraph[1].feature_type === "fillet";
          const canBuildArtifact = record?.status === "succeeded"
            && laterBodyFeatures.length === 0
            && (artifactFormat === "stl" ? graphSupportsStl : graphSupportsFilletStep);
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
          const validHoleDraft = Boolean(
            holeDraft
            && Number.isFinite(holeX)
            && Number.isFinite(holeY)
            && Number.isFinite(holeDiameter)
            && holeDiameter > 0
            && (holeDraft.termination === "through" || (Number.isFinite(holeDepth) && holeDepth > 0)),
          );
          return (
            <Box key={feature.feature_id} className="sketchmath-history-row" data-testid={`sketchmath-feature-${feature.feature_id}`}>
              <Text fontWeight="600">{feature.name}</Text>
              <Text fontSize="sm" opacity={0.75}>
                {feature.feature_type} · {feature.parameters.operation} · {record?.status || "not rebuilt"}
                {feature.feature_type === "extrude" ? ` · profile ${feature.profile_id}` : ""}
                {feature.feature_type === "hole" ? ` · ${feature.parameters.style} ${feature.parameters.termination}` : ""}
                {feature.feature_type === "revolve" ? ` · ${feature.parameters.angle_deg}° about ${feature.parameters.axis_entity_id}` : ""}
                {feature.feature_type === "fillet" ? ` · radius ${feature.parameters.radius_mm} mm` : ""}
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
                    value={depthDraft}
                    onChange={(event) => setDepthDrafts((current) => ({ ...current, [feature.feature_id]: event.target.value }))}
                    width="110px"
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => nextDepth != null && onUpdateDepth(feature, nextDepth)}
                    isDisabled={nextDepth == null || nextDepth === feature.parameters.depth_mm || busy}
                  >
                    Apply depth
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
