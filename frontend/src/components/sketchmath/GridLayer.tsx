import React from "react";

type GridLayerProps = {
  width: number;
  height: number;
};

const majorStep = 120;
const minorStep = 24;

const GridLayer = ({ width, height }: GridLayerProps) => {
  const verticals = [] as number[];
  const horizontals = [] as number[];
  for (let x = 0; x <= width; x += minorStep) {
    verticals.push(x);
  }
  for (let y = 0; y <= height; y += minorStep) {
    horizontals.push(y);
  }

  return (
    <g data-testid="sketchmath-grid" className="sketchmath-grid">
      <defs>
        <pattern id="sketchmath-grid-pattern" width={minorStep} height={minorStep} patternUnits="userSpaceOnUse">
          <path d={`M ${minorStep} 0 L 0 0 0 ${minorStep}`} className="sketchmath-grid-minor" />
        </pattern>
        <linearGradient id="sketchmath-bg-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="rgba(15, 28, 61, 0.95)" />
          <stop offset="100%" stopColor="rgba(7, 12, 24, 0.98)" />
        </linearGradient>
      </defs>
      <rect x={0} y={0} width={width} height={height} fill="url(#sketchmath-bg-gradient)" />
      <rect x={0} y={0} width={width} height={height} fill="url(#sketchmath-grid-pattern)" opacity={0.85} />
      {verticals.map((x) => (
        <line
          key={`v-${x}`}
          x1={x}
          y1={0}
          x2={x}
          y2={height}
          className={x % majorStep === 0 ? "sketchmath-grid-major" : "sketchmath-grid-minor"}
        />
      ))}
      {horizontals.map((y) => (
        <line
          key={`h-${y}`}
          x1={0}
          y1={y}
          x2={width}
          y2={y}
          className={y % majorStep === 0 ? "sketchmath-grid-major" : "sketchmath-grid-minor"}
        />
      ))}
    </g>
  );
};

export default GridLayer;
