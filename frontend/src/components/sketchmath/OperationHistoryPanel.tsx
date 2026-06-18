import React from "react";
import { Box, Heading, Text, VStack } from "@chakra-ui/react";
import type { SketchMathHistoryEntry } from "../../services/sketchmath";

type OperationHistoryPanelProps = {
  history: SketchMathHistoryEntry[];
};

const OperationHistoryPanel = ({ history }: OperationHistoryPanelProps) => (
  <Box className="sketchmath-panel" data-testid="sketchmath-history-panel">
    <Heading size="sm" mb={3} className="sketchmath-panel-title">
      History
    </Heading>
    <VStack align="start" spacing={2}>
      {history.length === 0 ? <Text opacity={0.7}>No commits yet.</Text> : null}
      {history.map((entry, index) => (
        <Box key={`${entry.command.command_id}-${index}`} width="100%" className="sketchmath-history-row">
          <Text fontWeight="600">
            {index + 1}. {entry.command.command_type}
          </Text>
          <Text fontSize="sm" opacity={0.8}>
            {entry.command.mode}
          </Text>
        </Box>
      ))}
    </VStack>
  </Box>
);

export default OperationHistoryPanel;
