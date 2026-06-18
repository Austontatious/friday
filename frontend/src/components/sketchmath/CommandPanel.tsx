import React, { useMemo, useState } from "react";
import {
  Box,
  Button,
  Divider,
  Heading,
  HStack,
  Input,
  Text,
  Textarea,
  VStack,
} from "@chakra-ui/react";
import type {
  SketchMathCommand,
  SketchMathEntity,
  SketchMathTranslationOutcome,
} from "../../services/sketchmath";
import {
  buildDeleteEntityCommand,
  buildEqualAngleCommand,
  buildEqualLengthCommand,
  buildMakeParallelCommand,
  buildMakePerpendicularCommand,
  buildMakeProfileCommand,
  buildMirrorCommand,
  buildRotateCommand,
  buildSetAngleCommand,
  buildSetLengthCommand,
  buildTranslateCommand,
} from "./commandBuilders";

type CommandPanelProps = {
  pendingCommandText: string;
  onPendingCommandTextChange: (text: string) => void;
  onPreview: () => void;
  onCommit: () => void;
  onClearPreview: () => void;
  onRejectProposal: () => void;
  onRevert: () => void;
  error: string | null;
  selectedEntityIds: string[];
  selectedEntities: SketchMathEntity[];
  translationOutcome: SketchMathTranslationOutcome | null;
  onTranslate: (utterance: string) => Promise<void>;
};

const summarizeCommand = (command: SketchMathCommand | null): string => {
  if (!command) {
    return "No proposed command yet.";
  }
  const pieces = [command.command_type];
  if (command.selection.length > 0) {
    pieces.push(`selection: ${command.selection.join(", ")}`);
  }
  const parameters = command.parameters;
  if (typeof parameters.length === "number") {
    pieces.push(`length: ${parameters.length}`);
  }
  if (typeof parameters.angle === "number") {
    pieces.push(`angle: ${parameters.angle}`);
  }
  if (Array.isArray(parameters.vector)) {
    pieces.push(`vector: [${parameters.vector.join(", ")}]`);
  }
  return pieces.join(" | ");
};

const CommandPanel = ({
  pendingCommandText,
  onPendingCommandTextChange,
  onPreview,
  onCommit,
  onClearPreview,
  onRejectProposal,
  onRevert,
  error,
  selectedEntityIds,
  selectedEntities,
  translationOutcome,
  onTranslate,
}: CommandPanelProps) => {
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  const [utterance, setUtterance] = useState("");
  const [lengthValue, setLengthValue] = useState("17.5");
  const [angleValue, setAngleValue] = useState("45");
  const [vectorX, setVectorX] = useState("12");
  const [vectorY, setVectorY] = useState("0");
  const [originX, setOriginX] = useState("0");
  const [originY, setOriginY] = useState("0");
  const [axisX, setAxisX] = useState("0");
  const [profileName, setProfileName] = useState("profile_1");

  const selectedCount = selectedEntityIds.length;
  const proposedCommand = translationOutcome?.status === "command" ? translationOutcome.command : null;
  const proposedSummary = useMemo(() => summarizeCommand(proposedCommand), [proposedCommand]);

  const applyCommand = (command: SketchMathCommand) => {
    onPendingCommandTextChange(JSON.stringify(command, null, 2));
  };

  const handleTranslate = async () => {
    await onTranslate(utterance);
  };

  const helperSelection = selectedEntityIds.slice();

  const helperButtons = [
    {
      label: "Set Length",
      disabled: selectedCount < 2,
      build: () => buildSetLengthCommand(helperSelection, Number(lengthValue), "mm", "point_a"),
    },
    {
      label: "Set Angle",
      disabled: selectedCount < 3,
      build: () => buildSetAngleCommand(helperSelection, Number(angleValue), "deg"),
    },
    {
      label: "Make Parallel",
      disabled: selectedCount < 4,
      build: () => buildMakeParallelCommand(helperSelection),
    },
    {
      label: "Make Perpendicular",
      disabled: selectedCount < 4,
      build: () => buildMakePerpendicularCommand(helperSelection),
    },
    {
      label: "Equal Length",
      disabled: selectedCount < 4,
      build: () => buildEqualLengthCommand(helperSelection),
    },
    {
      label: "Equal Angle",
      disabled: selectedCount < 6,
      build: () => buildEqualAngleCommand(helperSelection),
    },
    {
      label: "Make Profile",
      disabled: selectedCount < 3,
      build: () => buildMakeProfileCommand(helperSelection, profileName),
    },
    {
      label: "Translate",
      disabled: selectedCount < 1,
      build: () => buildTranslateCommand(helperSelection, { x: Number(vectorX), y: Number(vectorY) }),
    },
    {
      label: "Rotate",
      disabled: selectedCount < 1,
      build: () => buildRotateCommand(helperSelection, Number(angleValue), { x: Number(originX), y: Number(originY) }),
    },
    {
      label: "Mirror",
      disabled: selectedCount < 1,
      build: () => buildMirrorCommand(helperSelection, Number(axisX)),
    },
    {
      label: "Delete Selected",
      disabled: selectedCount < 1,
      build: () => buildDeleteEntityCommand(helperSelection),
    },
  ];

  return (
    <Box className="sketchmath-panel" data-testid="sketchmath-command-panel">
      <Heading size="sm" mb={3} className="sketchmath-panel-title">
        Command Composer
      </Heading>
      <VStack align="stretch" spacing={3}>
        <Box>
          <Text fontWeight="600" mb={2}>
            Natural language
          </Text>
          <HStack align="stretch">
            <Input
              value={utterance}
              onChange={(event) => setUtterance(event.target.value)}
              aria-label="SketchMath utterance"
              placeholder='make A-B 17.5 mm at 45 degrees'
            />
            <Button onClick={handleTranslate} isDisabled={!utterance.trim()} data-testid="sketchmath-translate-button">
              Translate Utterance
            </Button>
          </HStack>
          {translationOutcome ? (
            <Box mt={2} className="sketchmath-translation-result" data-testid="sketchmath-translation-outcome">
              <Text fontWeight="600">{translationOutcome.status}</Text>
              {translationOutcome.reason ? <Text fontSize="sm">{translationOutcome.reason}</Text> : null}
              {translationOutcome.options.length ? (
                <Text fontSize="sm" whiteSpace="pre-wrap">
                  {translationOutcome.options.join("\n")}
                </Text>
              ) : null}
              {translationOutcome.status === "command" ? <Text fontSize="sm">{proposedSummary}</Text> : null}
              <HStack mt={2} spacing={2}>
                <Button size="sm" variant="outline" onClick={onRejectProposal} data-testid="sketchmath-reject-button">
                  Reject
                </Button>
              </HStack>
            </Box>
          ) : null}
        </Box>

        <Divider />

        <Box>
          <Text fontWeight="600" mb={2}>
            User-friendly commands
          </Text>
          <HStack spacing={2} flexWrap="wrap" alignItems="flex-start">
            <Input
              value={lengthValue}
              onChange={(event) => setLengthValue(event.target.value)}
              aria-label="SketchMath length"
              width="110px"
            />
            <Input
              value={angleValue}
              onChange={(event) => setAngleValue(event.target.value)}
              aria-label="SketchMath angle"
              width="110px"
            />
            <Input
              value={vectorX}
              onChange={(event) => setVectorX(event.target.value)}
              aria-label="SketchMath vector x"
              width="110px"
            />
            <Input
              value={vectorY}
              onChange={(event) => setVectorY(event.target.value)}
              aria-label="SketchMath vector y"
              width="110px"
            />
            <Input
              value={originX}
              onChange={(event) => setOriginX(event.target.value)}
              aria-label="SketchMath origin x"
              width="110px"
            />
            <Input
              value={originY}
              onChange={(event) => setOriginY(event.target.value)}
              aria-label="SketchMath origin y"
              width="110px"
            />
            <Input
              value={axisX}
              onChange={(event) => setAxisX(event.target.value)}
              aria-label="SketchMath mirror axis"
              width="110px"
            />
            <Input
              value={profileName}
              onChange={(event) => setProfileName(event.target.value)}
              aria-label="SketchMath profile name"
              width="150px"
            />
          </HStack>
          <HStack mt={3} spacing={2} flexWrap="wrap">
            {helperButtons.map((helper) => (
              <Button
                key={helper.label}
                size="sm"
                variant="outline"
                isDisabled={helper.disabled}
                onClick={() => applyCommand(helper.build())}
              >
                {helper.label}
              </Button>
            ))}
          </HStack>
        </Box>

        <Box>
          <Text fontWeight="600" mb={2}>
            Proposed command
          </Text>
          <Text fontSize="sm" whiteSpace="pre-wrap" className="sketchmath-command-preview">
            {translationOutcome?.status === "command" ? proposedSummary : pendingCommandText || "Use a helper or translate an utterance."}
          </Text>
          <HStack mt={2} spacing={2} flexWrap="wrap">
            <Button onClick={onPreview} data-testid="sketchmath-preview-button">
              Preview
            </Button>
            <Button onClick={onCommit} className="sketchmath-button sketchmath-button-strong" data-testid="sketchmath-commit-button">
              Commit
            </Button>
            <Button variant="outline" onClick={onClearPreview} data-testid="sketchmath-clear-preview-button">
              Clear Preview
            </Button>
            <Button variant="outline" onClick={onRevert} data-testid="sketchmath-revert-button">
              Revert Last
            </Button>
          </HStack>
        </Box>

        {error ? (
          <Text className="sketchmath-error" data-testid="sketchmath-error">
            {error}
          </Text>
        ) : null}

        <Box>
          <Button size="sm" variant="ghost" onClick={() => setIsAdvancedOpen((next) => !next)} data-testid="sketchmath-advanced-toggle">
            {isAdvancedOpen ? "Hide" : "Show"} Advanced / Debug DSL
          </Button>
          {isAdvancedOpen ? (
            <Box mt={3}>
              <Textarea
                value={pendingCommandText}
                onChange={(event) => onPendingCommandTextChange(event.target.value)}
                rows={10}
                className="sketchmath-command-box"
                aria-label="SketchMath command box"
                data-testid="sketchmath-command-box"
              />
            </Box>
          ) : null}
        </Box>
      </VStack>
    </Box>
  );
};

export default CommandPanel;
