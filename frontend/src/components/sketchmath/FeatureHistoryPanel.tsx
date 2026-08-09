import React, { useEffect, useMemo, useState } from "react";
import { Box, Button, Heading, HStack, Input, Text, VStack } from "@chakra-ui/react";

import type {
  SketchMathDocument,
  SketchMathFeature,
  SketchMathFeatureBuildRecord,
  SketchMathProfileEntity,
} from "../../services/sketchmath";

type FeatureHistoryPanelProps = {
  document: SketchMathDocument;
  activeProfile: SketchMathProfileEntity | null;
  newDepthValue: string;
  busy: boolean;
  canUndo: boolean;
  canRedo: boolean;
  onNewDepthValueChange: (value: string) => void;
  onAddExtrusion: (profile: SketchMathProfileEntity, depth: number) => void;
  onUpdateDepth: (feature: SketchMathFeature, depth: number) => void;
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
  onNewDepthValueChange,
  onAddExtrusion,
  onUpdateDepth,
  onUndo,
  onRedo,
}: FeatureHistoryPanelProps) => {
  const [depthDrafts, setDepthDrafts] = useState<Record<string, string>>({});
  const buildRecords = useMemo(
    () => recordByFeature(document.last_rebuild?.records || []),
    [document.last_rebuild?.records],
  );

  useEffect(() => {
    setDepthDrafts(Object.fromEntries(
      document.features.map((feature) => [feature.feature_id, String(feature.parameters.depth_mm)]),
    ));
  }, [document.features]);

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
        ) : document.features.map((feature) => {
          const record = buildRecords[feature.feature_id];
          const depthDraft = depthDrafts[feature.feature_id] ?? String(feature.parameters.depth_mm);
          const nextDepth = validDepth(depthDraft);
          return (
            <Box key={feature.feature_id} className="sketchmath-history-row" data-testid={`sketchmath-feature-${feature.feature_id}`}>
              <Text fontWeight="600">{feature.name}</Text>
              <Text fontSize="sm" opacity={0.75}>
                {feature.parameters.operation} · {record?.status || "not rebuilt"} · profile {feature.profile_id}
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
