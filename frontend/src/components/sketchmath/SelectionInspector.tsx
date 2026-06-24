import React from "react";
import { Box, Button, Heading, HStack, Input, Text, VStack } from "@chakra-ui/react";
import type { SketchMathEntity } from "../../services/sketchmath";

type SelectionInspectorProps = {
  selectedEntities: SketchMathEntity[];
  sketchStatus: string;
  constraintSummaries: string[];
  dimensionSummary: string;
  rectangleDimensions: { baseId: string; width: number; height: number } | null;
  rectangleSelectionDetail:
    | { kind: "rectangle"; baseId: string }
    | { kind: "edge"; baseId: string; edgeId: "ab" | "bc" | "cd" | "da"; dimension: "width" | "height" }
    | { kind: "corner"; baseId: string; cornerId: "a" | "b" | "c" | "d" }
    | { kind: "profile"; baseId: string }
    | null;
  rectangleAnchorSummary: string | null;
  profileSummary: string;
  profileHoleCount: number | null;
  rectangleWidthDraft: string;
  rectangleHeightDraft: string;
  dimensionEditor: { baseId: string; dimension: "width" | "height"; value: string } | null;
  deletePrompt: { kind: "rectangle"; baseId: string; message: string } | null;
  showInternals: boolean;
  namedReferences: Record<string, string>;
  pendingCommandText: string;
  labelDraft: string;
  onLabelDraftChange: (label: string) => void;
  onRectangleWidthDraftChange: (value: string) => void;
  onRectangleHeightDraftChange: (value: string) => void;
  onApplyRectangleDimensions: () => void;
  onOpenDimensionEditor: (dimension: "width" | "height") => void;
  onDimensionEditorValueChange: (value: string) => void;
  onApplyDimensionEditor: () => void;
  onSelectWholeRectangle: () => void;
  onSelectProfile: () => void;
  onDeleteWholeRectangle: () => void;
  onCancelDeletePrompt: () => void;
  onFixRectangleCorner: () => void;
  onApplyLabel: () => void;
  onToggleLockSelected: () => void;
  onDeleteSelected: () => void;
};

const SelectionInspector = ({
  selectedEntities,
  sketchStatus,
  constraintSummaries,
  dimensionSummary,
  rectangleDimensions,
  rectangleSelectionDetail,
  rectangleAnchorSummary,
  profileSummary,
  profileHoleCount,
  rectangleWidthDraft,
  rectangleHeightDraft,
  dimensionEditor,
  deletePrompt,
  showInternals,
  namedReferences,
  pendingCommandText,
  labelDraft,
  onLabelDraftChange,
  onRectangleWidthDraftChange,
  onRectangleHeightDraftChange,
  onApplyRectangleDimensions,
  onOpenDimensionEditor,
  onDimensionEditorValueChange,
  onApplyDimensionEditor,
  onSelectWholeRectangle,
  onSelectProfile,
  onDeleteWholeRectangle,
  onCancelDeletePrompt,
  onFixRectangleCorner,
  onApplyLabel,
  onToggleLockSelected,
  onDeleteSelected,
}: SelectionInspectorProps) => (
  <Box className="sketchmath-panel" data-testid="sketchmath-selection-inspector">
    <Heading size="sm" mb={3} className="sketchmath-panel-title">
      Selection
    </Heading>
    <VStack align="start" spacing={2}>
      <Box width="100%">
        <Text fontWeight="600" mb={1}>
          Sketch status
        </Text>
        <Text data-testid="sketchmath-status">{sketchStatus}</Text>
        <Text fontSize="sm" opacity={0.8}>
          {dimensionSummary}
        </Text>
      </Box>
      {selectedEntities.length === 0 ? <Text opacity={0.7}>Nothing selected.</Text> : null}
      {deletePrompt ? (
        <Box width="100%" data-testid="sketchmath-delete-prompt">
          <Text fontWeight="600" mb={1}>
            Dependency-aware delete
          </Text>
          <Text fontSize="sm" opacity={0.85}>
            {deletePrompt.message}
          </Text>
          <HStack mt={2}>
            <Button size="sm" onClick={onDeleteWholeRectangle}>
              Delete whole rectangle
            </Button>
            <Button size="sm" variant="outline" onClick={onCancelDeletePrompt}>
              Cancel
            </Button>
          </HStack>
        </Box>
      ) : null}
      {rectangleDimensions ? (
        <Box width="100%" data-testid="rectangle-semantic-summary">
          <Text fontWeight="600" mb={1}>
            {rectangleSelectionDetail?.kind === "edge"
              ? `Selected edge: ${rectangleSelectionDetail.dimension === "width" ? "Width edge" : "Height edge"}`
              : rectangleSelectionDetail?.kind === "corner"
                ? "Selected: Rectangle corner"
                : rectangleSelectionDetail?.kind === "profile"
                  ? "Selected profile"
                  : "Selected object"}
          </Text>
          {rectangleSelectionDetail?.kind === "edge" ? (
            <>
              <Text>Parent: Rectangle</Text>
              <Text fontSize="sm" opacity={0.8}>
                {rectangleSelectionDetail.dimension === "width"
                  ? `Width: ${rectangleDimensions.width} mm`
                  : `Height: ${rectangleDimensions.height} mm`}
              </Text>
              <HStack mt={2} flexWrap="wrap">
                <Button size="sm" onClick={() => onOpenDimensionEditor(rectangleSelectionDetail.dimension)}>
                  Edit dimension
                </Button>
                <Button size="sm" variant="outline" onClick={() => onOpenDimensionEditor(rectangleSelectionDetail.dimension)}>
                  Dimension this edge
                </Button>
                <Button size="sm" variant="outline" onClick={onSelectWholeRectangle}>
                  Select whole rectangle
                </Button>
                <Button size="sm" variant="outline" onClick={onSelectProfile}>
                  Select profile
                </Button>
              </HStack>
            </>
          ) : rectangleSelectionDetail?.kind === "corner" ? (
            <>
              <Text>Rectangle</Text>
              <Text fontSize="sm" opacity={0.8}>
                Corner: {rectangleSelectionDetail.cornerId.toUpperCase()}
              </Text>
              <Button size="sm" mt={2} onClick={onFixRectangleCorner}>
                Fix / Anchor corner
              </Button>
            </>
          ) : (
            <>
              <Text>Rectangle</Text>
              <HStack mt={2} flexWrap="wrap">
                <Button size="sm" variant="outline" onClick={onSelectWholeRectangle}>
                  Select whole rectangle
                </Button>
                <Button size="sm" variant="outline" onClick={onSelectProfile}>
                  Select profile
                </Button>
              </HStack>
            </>
          )}
          <Text fontSize="sm" opacity={0.8}>
            {rectangleAnchorSummary || "Position free"}
          </Text>
          <Text fontSize="sm" opacity={0.8}>
            {profileSummary}
          </Text>
          {profileHoleCount !== null ? (
            <Text fontSize="sm" opacity={0.8}>
              Profile holes: {profileHoleCount}
            </Text>
          ) : null}
          {rectangleSelectionDetail?.kind !== "corner" ? (
            <Button size="sm" mt={2} onClick={onFixRectangleCorner}>
              Fix corner
            </Button>
          ) : null}
        </Box>
      ) : null}
      {selectedEntities.map((entity) => (
        <Box key={entity.id} width="100%">
          <Text fontWeight="600">{entity.label || entity.id}</Text>
          <Text fontSize="sm" opacity={0.8}>
            {entity.id} • {entity.type} {entity.locked ? "• locked" : ""}
          </Text>
        </Box>
      ))}
      <Box width="100%">
        <Text fontWeight="600" mb={1}>
          Dimensions
        </Text>
        <Text fontSize="sm" opacity={0.8} whiteSpace="pre-wrap">
          {dimensionSummary}
        </Text>
        {rectangleDimensions ? (
          <Box mt={2}>
            <Text fontWeight="600" mb={1}>
              Rectangle dimensions
            </Text>
            <HStack>
              <Input
                type="number"
                value={rectangleWidthDraft}
                onChange={(event) => onRectangleWidthDraftChange(event.target.value)}
                aria-label="Rectangle width"
                data-testid="rectangle-width-input"
              />
              <Input
                type="number"
                value={rectangleHeightDraft}
                onChange={(event) => onRectangleHeightDraftChange(event.target.value)}
                aria-label="Rectangle height"
                data-testid="rectangle-height-input"
              />
              <Button onClick={onApplyRectangleDimensions}>
                Apply Rectangle Dimensions
              </Button>
            </HStack>
            <Text fontSize="sm" opacity={0.8}>
              {rectangleDimensions.width} mm x {rectangleDimensions.height} mm
            </Text>
            {dimensionEditor ? (
              <Box mt={3} data-testid="rectangle-dimension-editor">
                <Heading size="sm" mb={2}>
                  Edit {dimensionEditor.dimension} dimension
                </Heading>
                <HStack>
                  <Input
                    type="number"
                    value={dimensionEditor.value}
                    onChange={(event) => onDimensionEditorValueChange(event.target.value)}
                    aria-label={`${dimensionEditor.dimension === "width" ? "Width" : "Height"} dimension value`}
                  />
                  <Button onClick={onApplyDimensionEditor}>Apply dimension</Button>
                </HStack>
              </Box>
            ) : null}
          </Box>
        ) : null}
      </Box>
      <Box width="100%">
        <Text fontWeight="600" mb={1}>
          Constraints
        </Text>
        <Text fontSize="sm" opacity={0.8} whiteSpace="pre-wrap">
          {constraintSummaries.length ? constraintSummaries.join("\n") : "No constraints yet."}
        </Text>
      </Box>
      <Box width="100%">
        <Text fontWeight="600" mb={1}>
          Name selected
        </Text>
        <HStack>
          <Input
            value={labelDraft}
            onChange={(event) => onLabelDraftChange(event.target.value)}
            aria-label="SketchMath entity name"
            data-testid="sketchmath-entity-name-input"
            placeholder="A, B, C, centerline"
          />
          <Button onClick={onApplyLabel} isDisabled={selectedEntities.length === 0} data-testid="sketchmath-apply-label-button">
            Apply
          </Button>
        </HStack>
      </Box>
      <HStack width="100%" wrap="wrap">
        <Button size="sm" variant="outline" onClick={onToggleLockSelected} isDisabled={selectedEntities.length === 0}>
          Lock / Unlock
        </Button>
        <Button size="sm" variant="outline" onClick={onDeleteSelected} isDisabled={selectedEntities.length === 0}>
          Delete
        </Button>
      </HStack>
      {showInternals ? (
        <>
          <Box width="100%">
            <Text fontWeight="600" mb={1}>
              Named references
            </Text>
            <Text fontSize="sm" opacity={0.8} whiteSpace="pre-wrap">
              {Object.entries(namedReferences).length ? Object.entries(namedReferences).map(([name, id]) => `${name} -> ${id}`).join("\n") : "No named references yet."}
            </Text>
          </Box>
          <Box width="100%">
            <Text fontWeight="600" mb={1}>
              Pending command
            </Text>
            <Text fontSize="sm" whiteSpace="pre-wrap" className="sketchmath-command-preview">
              {pendingCommandText || "Select geometry to inspect a generated command."}
            </Text>
          </Box>
        </>
      ) : null}
    </VStack>
  </Box>
);

export default SelectionInspector;
