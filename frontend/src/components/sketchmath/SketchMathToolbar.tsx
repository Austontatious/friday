import React from "react";
import { Box, Button, HStack, Text } from "@chakra-ui/react";
import type { SketchMathMode } from "../../services/sketchmath";

type SketchMathToolbarProps = {
  mode: SketchMathMode;
  onModeChange: (mode: SketchMathMode) => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
};

const SketchMathToolbar = ({ mode, onModeChange, theme, onToggleTheme }: SketchMathToolbarProps) => (
  <Box className="sketchmath-toolbar">
    <HStack spacing={3} flexWrap="wrap" justify="space-between" alignItems="start">
      <HStack spacing={2} flexWrap="wrap" alignItems="start">
        {[
          ["select", "Select"],
          ["point", "Point"],
          ["line", "Line"],
          ["rectangle", "Rectangle"],
          ["dimension", "Dimension"],
          ["horizontal", "Horizontal"],
          ["vertical", "Vertical"],
          ["parallel", "Parallel"],
          ["perpendicular", "Perpendicular"],
          ["equal", "Equal"],
          ["delete", "Delete"],
          ["solve", "Solve"],
        ].map(([value, label]) => (
          <Button
            key={value}
            size="sm"
            variant={mode === value ? "solid" : "outline"}
            onClick={() => onModeChange(value as SketchMathMode)}
          >
            {label}
          </Button>
        ))}
        <Text className="sketchmath-tool-unavailable" fontSize="sm">
          Circle: coming soon
        </Text>
        <Text className="sketchmath-tool-unavailable" fontSize="sm">
          Arc: coming soon
        </Text>
      </HStack>
      <HStack spacing={3}>
        <Text fontSize="sm" opacity={0.8}>
          {theme === "light" ? "Light grid" : "Dark grid"}
        </Text>
        <Button size="sm" variant="outline" onClick={onToggleTheme}>
          Toggle Theme
        </Button>
      </HStack>
    </HStack>
  </Box>
);

export default SketchMathToolbar;
