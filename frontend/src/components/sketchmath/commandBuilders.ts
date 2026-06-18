import type { SketchMathCommand } from "../../services/sketchmath";

type Point = { x: number; y: number };

const nextCommandId = (prefix: string) => `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;

const baseCommand = (commandType: string, selection: string[], parameters: Record<string, unknown>): SketchMathCommand => ({
  version: "0.1",
  command_id: nextCommandId(commandType),
  mode: "preview",
  command_type: commandType,
  selection,
  parameters,
});

export const buildDefinePointCommand = (point: Point, name: string, label?: string | null): SketchMathCommand =>
  baseCommand("define_point", [], {
    name,
    coords: [Number(point.x.toFixed(2)), Number(point.y.toFixed(2))],
    locked: false,
    label: label || name,
  });

export const buildDefineLineCommand = (start: Point, end: Point, name: string, label?: string | null): SketchMathCommand =>
  baseCommand("define_line", [], {
    name,
    start: [Number(start.x.toFixed(2)), Number(start.y.toFixed(2))],
    end: [Number(end.x.toFixed(2)), Number(end.y.toFixed(2))],
    locked: false,
    label: label || name,
  });

export const buildSetLengthCommand = (selection: string[], length: number, unit: string, anchor: "point_a" | "point_b" | "midpoint" = "midpoint"): SketchMathCommand =>
  baseCommand("set_distance", selection.slice(0, 2), { distance: length, unit, anchor });

export const buildSetRectangleDimensionCommand = (
  selection: string[],
  dimension: "width" | "height",
  value: number,
  unit: string = "mm",
): SketchMathCommand =>
  baseCommand("set_rectangle_dimension", selection, {
    dimension,
    value,
    unit,
  });

export const buildSetAngleCommand = (selection: string[], angle: number, angleUnit: string = "deg"): SketchMathCommand =>
  baseCommand("set_angle", selection.slice(0, 3), { angle, angle_unit: angleUnit });

export const buildMakeParallelCommand = (selection: string[]): SketchMathCommand =>
  baseCommand("make_parallel", selection.slice(0, 4), {});

export const buildMakePerpendicularCommand = (selection: string[]): SketchMathCommand =>
  baseCommand("make_perpendicular", selection.slice(0, 4), {});

export const buildEqualLengthCommand = (selection: string[]): SketchMathCommand =>
  baseCommand("make_equal_length", selection.slice(0, 4), {});

export const buildEqualAngleCommand = (selection: string[]): SketchMathCommand =>
  baseCommand("make_equal_angle", selection.slice(0, 6), {});

export const buildMakeProfileCommand = (selection: string[], name?: string): SketchMathCommand =>
  baseCommand("make_profile", selection, { name: name || `profile_${nextCommandId("profile")}` });

export const buildExtrudeProfileCommand = (profileId: string, depth: number, unit: string = "mm"): SketchMathCommand =>
  baseCommand("extrude_profile", [profileId], {
    depth,
    depth_unit: unit,
    direction: "positive_normal",
    output_format: "step",
  });

export const buildAddProfileHoleCommand = (profileId: string, diameter: number, center: Point, unit: string = "mm"): SketchMathCommand =>
  baseCommand("add_profile_hole", [profileId], {
    diameter,
    unit,
    center: [Number(center.x.toFixed(2)), Number(center.y.toFixed(2))],
  });

export const buildTranslateCommand = (selection: string[], vector: Point): SketchMathCommand =>
  baseCommand("translate", selection, { vector: [Number(vector.x.toFixed(2)), Number(vector.y.toFixed(2))] });

export const buildRotateCommand = (selection: string[], angle: number, origin: Point = { x: 0, y: 0 }): SketchMathCommand =>
  baseCommand("rotate", selection, { angle, angle_unit: "deg", origin: [Number(origin.x.toFixed(2)), Number(origin.y.toFixed(2))] });

export const buildMirrorCommand = (selection: string[], axisX: number): SketchMathCommand =>
  baseCommand("mirror", selection, { axis_x: axisX });

export const buildDeleteEntityCommand = (selection: string[], cascade = false): SketchMathCommand =>
  baseCommand("delete_entity", selection, cascade ? { cascade: true } : {});

export const buildSolveConstraintsCommand = (constraintIds?: string[]): SketchMathCommand =>
  baseCommand("solve_constraints", [], constraintIds ? { constraint_ids: constraintIds } : {});

export const buildBatchCommand = (commands: SketchMathCommand[]): SketchMathCommand =>
  baseCommand("batch", [], {
    commands: commands.map((command) => command),
  });
