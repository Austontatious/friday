import React from "react";
import { Box, Heading, Text, VStack } from "@chakra-ui/react";
import type { SketchMathOperationResult } from "../../services/sketchmath";

type MeasurementPanelProps = {
  previewResult: SketchMathOperationResult | null;
};

const MeasurementPanel = ({ previewResult }: MeasurementPanelProps) => (
  <Box className="sketchmath-panel" data-testid="sketchmath-measurement-panel">
    <Heading size="sm" mb={3} className="sketchmath-panel-title">
      Measurement
    </Heading>
    <VStack align="start" spacing={2}>
      {previewResult ? (
        <>
          <Text>Status: {previewResult.status}</Text>
          <Text>Command: {previewResult.command.command_type}</Text>
          <Text>Changed: {previewResult.changed_entity_ids.join(", ") || "none"}</Text>
          <Text>
            Value: {previewResult.value ?? "n/a"} {previewResult.unit ?? ""}
          </Text>
        </>
      ) : (
        <Text opacity={0.7}>No preview yet.</Text>
      )}
    </VStack>
  </Box>
);

export default MeasurementPanel;
