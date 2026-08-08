import type { SketchMathArcEntity } from "../../services/sketchmath";

export const arcEndpoints = (arc: SketchMathArcEntity) => {
  const startRadians = (arc.start_angle_deg * Math.PI) / 180;
  const endRadians = ((arc.start_angle_deg + arc.sweep_angle_deg) * Math.PI) / 180;
  return {
    start: {
      x: arc.center[0] + arc.radius * Math.cos(startRadians),
      y: arc.center[1] + arc.radius * Math.sin(startRadians),
    },
    end: {
      x: arc.center[0] + arc.radius * Math.cos(endRadians),
      y: arc.center[1] + arc.radius * Math.sin(endRadians),
    },
  };
};

export const arcSvgPath = (arc: SketchMathArcEntity): string => {
  const { start, end } = arcEndpoints(arc);
  const largeArc = Math.abs(arc.sweep_angle_deg) > 180 ? 1 : 0;
  const sweep = arc.sweep_angle_deg > 0 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${arc.radius} ${arc.radius} 0 ${largeArc} ${sweep} ${end.x} ${end.y}`;
};
