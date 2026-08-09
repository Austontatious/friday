import React, { useEffect, useMemo, useState } from "react";
import { Box, Button, Heading, HStack, Input, Link, Text, VStack } from "@chakra-ui/react";

import type {
  SketchMathArtifactJobManifest,
  SketchMathDocument,
  SketchMathFeature,
  SketchMathFeatureBuildRecord,
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
  artifactJobsEnabled: boolean;
  artifactJobs: Record<string, SketchMathArtifactJobManifest>;
  onNewDepthValueChange: (value: string) => void;
  onAddExtrusion: (profile: SketchMathProfileEntity, depth: number) => void;
  onUpdateDepth: (feature: Extract<SketchMathFeature, { feature_type: "extrude" }>, depth: number) => void;
  onAddSimpleHole: (
    feature: Extract<SketchMathFeature, { feature_type: "extrude" }>,
    topReference: SketchMathSemanticTopologyReference,
    position: [number, number],
    diameter: number,
    termination: "through" | "blind",
    depth: number | null,
  ) => void;
  onBuildArtifact: (feature: SketchMathFeature) => void;
  onRetryArtifact: (job: SketchMathArtifactJobManifest) => void;
  artifactDownloadUrl: (path: string) => string;
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
  artifactJobsEnabled,
  artifactJobs,
  onNewDepthValueChange,
  onAddExtrusion,
  onUpdateDepth,
  onAddSimpleHole,
  onBuildArtifact,
  onRetryArtifact,
  artifactDownloadUrl,
  onUndo,
  onRedo,
}: FeatureHistoryPanelProps) => {
  const [depthDrafts, setDepthDrafts] = useState<Record<string, string>>({});
  const [holeDrafts, setHoleDrafts] = useState<Record<string, HoleDraft>>({});
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

  const newDepth = validDepth(newDepthValue);

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

      <VStack align="stretch" spacing={3} mt={3}>
        {document.features.length === 0 ? (
          <Text fontSize="sm" opacity={0.72}>No committed features yet.</Text>
        ) : document.features.map((feature, featureIndex) => {
          const record = buildRecords[feature.feature_id];
          const depthDraft = feature.feature_type === "extrude"
            ? depthDrafts[feature.feature_id] ?? String(feature.parameters.depth_mm)
            : "";
          const nextDepth = feature.feature_type === "extrude" ? validDepth(depthDraft) : null;
          const artifactJob = artifactJobs[feature.feature_id];
          const registeredArtifact = artifactJob?.result?.artifact
            || document.artifacts.find((artifact) => (
              artifact.feature_id === feature.feature_id
              && artifact.revision === document.revision
              && artifact.format === "stl"
            ));
          const laterBodyFeatures = document.features.slice(featureIndex + 1).filter(
            (candidate) => candidate.body_id === feature.body_id && !candidate.suppressed,
          );
          const graphSupportsStl = document.features.slice(0, featureIndex + 1).every(
            (candidate) => candidate.body_id !== feature.body_id
              || candidate.suppressed
              || candidate.feature_type === "extrude"
              || candidate.parameters.style === "simple",
          );
          const canBuildArtifact = record?.status === "succeeded"
            && laterBodyFeatures.length === 0
            && graphSupportsStl;
          const artifactBusy = artifactJob?.state === "READY" || artifactJob?.state === "RUNNING";
          const topReference = record?.generated_topology.find((reference) => reference.topology_type === "face" && reference.role === "top");
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
                {feature.feature_type === "extrude" ? ` · profile ${feature.profile_id}` : ` · ${feature.parameters.style} ${feature.parameters.termination}`}
                {record ? ` · ${record.generated_topology.length} semantic refs` : ""}
              </Text>
              {record?.measurements ? (
                <Text fontSize="sm" opacity={0.75} data-testid={`sketchmath-feature-measurements-${feature.feature_id}`}>
                  Volume {record.measurements.volume_delta_mm3} mm³ · {record.measurements.hole_count} hole{record.measurements.hole_count === 1 ? "" : "s"}
                </Text>
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
                      onClick={() => onBuildArtifact(feature)}
                      isDisabled={!canBuildArtifact || artifactBusy || busy}
                    >
                      Build STL
                    </Button>
                    {artifactJob?.state === "FAILED" ? (
                      <Button size="sm" variant="outline" onClick={() => onRetryArtifact(artifactJob)} isDisabled={busy}>
                        Retry STL
                      </Button>
                    ) : null}
                    {registeredArtifact ? (
                      <Link
                        href={artifactDownloadUrl(registeredArtifact.path)}
                        download
                        data-testid={`sketchmath-artifact-download-${feature.feature_id}`}
                      >
                        Download STL
                      </Link>
                    ) : null}
                  </HStack>
                  {artifactJob ? (
                    <Text fontSize="xs" opacity={0.72} mt={1} data-testid={`sketchmath-artifact-status-${feature.feature_id}`}>
                      STL artifact · {artifactJob.state} · {artifactJob.step} · revision {artifactJob.input_revision}
                      {artifactJob.error ? ` · ${artifactJob.error.code}: ${artifactJob.error.message}` : ""}
                    </Text>
                  ) : !canBuildArtifact ? (
                    <Text fontSize="xs" opacity={0.65} mt={1}>STL build is available on the terminal supported body feature.</Text>
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
