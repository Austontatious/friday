import type { SketchMathCommand, SketchMathCommandType } from "../../services/sketchmath";

type Point = { x: number; y: number };

const nextCommandId = (prefix: string) => `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;

const baseCommand = (commandType: SketchMathCommandType, selection: string[], parameters: Record<string, unknown>): SketchMathCommand => ({
  version: "0.2",
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

export const buildDefineLineCommand = (start: Point, end: Point, name: string, label?: string | null, startPointId?: string, endPointId?: string): SketchMathCommand =>
  baseCommand("define_line", [], {
    name,
    start: [Number(start.x.toFixed(2)), Number(start.y.toFixed(2))],
    end: [Number(end.x.toFixed(2)), Number(end.y.toFixed(2))],
    locked: false,
    label: label || name,
    start_point_id: startPointId,
    end_point_id: endPointId,
  });

export const buildHorizontalCommand = (selection: string[]): SketchMathCommand =>
  baseCommand("make_horizontal", selection, {});

export const buildVerticalCommand = (selection: string[]): SketchMathCommand =>
  baseCommand("make_vertical", selection, {});

export const buildCoincidentCommand = (selection: string[]): SketchMathCommand =>
  baseCommand("make_coincident", selection.slice(0, 2), {});

const gateBConstraintCommand = (
  commandType: SketchMathCommandType,
  selection: string[],
  parameters: Record<string, unknown> = {},
): SketchMathCommand => ({
  ...baseCommand(commandType, selection, parameters),
  version: "0.6",
});

export const buildFixedCommand = (pointId: string): SketchMathCommand =>
  gateBConstraintCommand("make_fixed", [pointId]);

export const buildMidpointCommand = (selection: string[]): SketchMathCommand =>
  gateBConstraintCommand("make_midpoint", selection.slice(0, 3));

export const buildCollinearCommand = (selection: string[]): SketchMathCommand =>
  gateBConstraintCommand("make_collinear", selection.slice(0, 3));

export const buildSymmetricCommand = (selection: string[]): SketchMathCommand =>
  gateBConstraintCommand("make_symmetric", selection.slice(0, 4));

export const buildConcentricCommand = (selection: string[]): SketchMathCommand =>
  gateBConstraintCommand("make_concentric", selection.slice(0, 2));

export const buildTangentCommand = (selection: string[], tangency: "external" | "internal" = "external"): SketchMathCommand =>
  gateBConstraintCommand("make_tangent", selection.slice(0, 2), { tangency });

export const buildSetConstructionCommand = (selection: string[], enabled: boolean): SketchMathCommand => ({
  ...baseCommand("set_construction", selection, { enabled }),
  version: "0.7",
});

const gateBEditingCommand = (
  commandType: SketchMathCommandType,
  selection: string[],
  parameters: Record<string, unknown>,
): SketchMathCommand => ({
  ...baseCommand(commandType, selection, parameters),
  version: "0.8",
});

export const buildDefineRegularPolygonCommand = (center: Point, radius: number, sides: number, name: string): SketchMathCommand =>
  gateBEditingCommand("define_regular_polygon", [], { center: [center.x, center.y], radius, sides, name, unit: "mm" });

export const buildDefineSlotCommand = (start: Point, end: Point, width: number, name: string): SketchMathCommand =>
  gateBEditingCommand("define_slot", [], { start: [start.x, start.y], end: [end.x, end.y], width, name, unit: "mm" });

export const buildSplitLineCommand = (lineId: string, parameter: number = 0.5): SketchMathCommand =>
  gateBEditingCommand("split_line", [lineId], { parameter });

export const buildTrimLineCommand = (targetId: string, cutterId: string, keep: "start" | "end" = "start"): SketchMathCommand =>
  gateBEditingCommand("trim_line", [targetId, cutterId], { keep });

export const buildExtendLineCommand = (targetId: string, cutterId: string): SketchMathCommand =>
  gateBEditingCommand("extend_line", [targetId, cutterId], {});

export const buildOffsetCurveCommand = (entityId: string, distance: number, side: "left" | "right" = "left"): SketchMathCommand =>
  gateBEditingCommand("offset_curve", [entityId], { distance, side, unit: "mm" });

export const buildCopyLinearCommand = (selection: string[], vector: Point, count: number): SketchMathCommand =>
  baseCommand("copy_linear", selection, { vector: [Number(vector.x.toFixed(2)), Number(vector.y.toFixed(2))], count });

export const buildDetectProfilesCommand = (): SketchMathCommand =>
  baseCommand("detect_profiles", [], {});

export const buildMovePointCommand = (pointId: string, point: Point): SketchMathCommand =>
  baseCommand("move_point", [pointId], { coords: [Number(point.x.toFixed(2)), Number(point.y.toFixed(2))] });

export const buildDefineCircleCommand = (center: Point, radius: number, name: string, centerPointId?: string): SketchMathCommand =>
  baseCommand("define_circle", [], { name, center: [center.x, center.y], radius, center_point_id: centerPointId, label: name });

export const buildUpdateCircleCommand = (circleId: string, center: Point, radius: number): SketchMathCommand =>
  baseCommand("update_circle", [circleId], { center: [center.x, center.y], radius });

const arcCommand = (parameters: Record<string, unknown>): SketchMathCommand => ({
  ...baseCommand("define_arc", [], parameters),
  version: "0.5",
});

export const buildDefineCenterArcCommand = (
  center: Point,
  start: Point,
  end: Point,
  name: string,
  pointIds: { center: string; start: string; end: string },
): SketchMathCommand => {
  const startAngle = Math.atan2(start.y - center.y, start.x - center.x);
  const endAngle = Math.atan2(end.y - center.y, end.x - center.x);
  const clockwiseSweep = ((endAngle - startAngle) * 180) / Math.PI % 360;
  const normalizedClockwiseSweep = clockwiseSweep < 0 ? clockwiseSweep + 360 : clockwiseSweep;
  return arcCommand({
    name,
    construction: "center",
    center: [center.x, center.y],
    start: [start.x, start.y],
    end: [end.x, end.y],
    direction: normalizedClockwiseSweep <= 180 ? "clockwise" : "counterclockwise",
    center_point_id: pointIds.center,
    start_point_id: pointIds.start,
    end_point_id: pointIds.end,
    label: name,
  });
};

export const buildDefineThreePointArcCommand = (
  start: Point,
  through: Point,
  end: Point,
  name: string,
  pointIds: { start: string; through: string; end: string },
): SketchMathCommand =>
  arcCommand({
    name,
    construction: "three_point",
    start: [start.x, start.y],
    through: [through.x, through.y],
    end: [end.x, end.y],
    start_point_id: pointIds.start,
    through_point_id: pointIds.through,
    end_point_id: pointIds.end,
    label: name,
  });

export const buildMakeCircleProfileCommand = (circleId: string, profileId?: string): SketchMathCommand =>
  baseCommand("make_circle_profile", [circleId], profileId ? { name: profileId } : {});

export const buildSetLengthCommand = (selection: string[], length: number, unit: string, anchor: "point_a" | "point_b" | "midpoint" = "midpoint"): SketchMathCommand =>
  baseCommand("set_distance", selection.slice(0, 2), { distance: length, unit, anchor });

const versionedConstraintCommand = (
  commandType: SketchMathCommandType,
  selection: string[],
  parameters: Record<string, unknown>,
): SketchMathCommand => ({
  ...baseCommand(commandType, selection, parameters),
  version: "0.4",
});

export const buildSetHorizontalDistanceCommand = (selection: string[], distance: number, unit: string = "mm"): SketchMathCommand =>
  versionedConstraintCommand("set_horizontal_distance", selection.slice(0, 2), { distance, unit, anchor: "midpoint" });

export const buildSetVerticalDistanceCommand = (selection: string[], distance: number, unit: string = "mm"): SketchMathCommand =>
  versionedConstraintCommand("set_vertical_distance", selection.slice(0, 2), { distance, unit, anchor: "midpoint" });

export const buildSetRadiusCommand = (circleId: string, radius: number, unit: string = "mm"): SketchMathCommand =>
  versionedConstraintCommand("set_radius", [circleId], { radius, unit });

export const buildSetDiameterCommand = (circleId: string, diameter: number, unit: string = "mm"): SketchMathCommand =>
  versionedConstraintCommand("set_diameter", [circleId], { diameter, unit });

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

export const buildUpdateProfileHoleCommand = (profileId: string, holeId: string, diameter: number, center: Point, unit: string = "mm"): SketchMathCommand =>
  baseCommand("update_profile_hole", [profileId, holeId], {
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

export const buildAnalyzeConstraintsCommand = (): SketchMathCommand => ({
  ...baseCommand("analyze_constraints", [], {}),
  version: "0.3",
});

export const buildBatchCommand = (commands: SketchMathCommand[]): SketchMathCommand =>
  baseCommand("batch", [], {
    commands: commands.map((command) => command),
  });
