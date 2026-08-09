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
          ["rectangle", "Draw rectangle"],
          ["center_rectangle", "Center rectangle"],
          ["slot", "Slot"],
          ["polygon", "Polygon"],
          ["region_select", "Region select"],
          ["box_select", "Box select"],
          ["hole", "Add hole"],
          ["pan", "Pan / view"],
          ["point", "Point"],
          ["line", "Line"],
          ["polyline", "Polyline"],
          ["circle", "Circle"],
          ["arc", "Arc"],
          ["three_point_arc", "3-point arc"],
          ["dimension", "Dimension"],
          ["delete", "Delete"],
        ].map(([value, label]) => (
          <Button
            key={value}
            size="sm"
            variant={mode === value ? "solid" : "outline"}
            onClick={() => onModeChange(value as SketchMathMode)}
            aria-pressed={mode === value}
            title={mode === value ? `${label} tool active` : `Switch to ${label}`}
          >
            {label}
          </Button>
        ))}
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
