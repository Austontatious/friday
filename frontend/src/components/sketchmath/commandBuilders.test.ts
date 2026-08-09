import {
  buildAddProfileHoleCommand,
  buildAnalyzeConstraintsCommand,
  buildDefineCenterArcCommand,
  buildDefineThreePointArcCommand,
  buildDeleteEntityCommand,
  buildExtrudeProfileCommand,
  buildFixedCommand,
  buildMidpointCommand,
  buildCollinearCommand,
  buildSymmetricCommand,
  buildConcentricCommand,
  buildTangentCommand,
  buildSetConstructionCommand,
  buildDefineRegularPolygonCommand,
  buildDefineSlotCommand,
  buildSplitLineCommand,
  buildTrimLineCommand,
  buildExtendLineCommand,
  buildOffsetCurveCommand,
  buildCopyLinearCommand,
  buildSetDiameterCommand,
  buildSetHorizontalDistanceCommand,
  buildSetLengthCommand,
  buildSetRadiusCommand,
  buildSetRectangleDimensionCommand,
  buildSetVerticalDistanceCommand,
  buildTranslateCommand,
  buildUpdateProfileHoleCommand,
} from "./commandBuilders";

describe("SketchMath command builders", () => {
  it("generates a valid set length GeometryCommand", () => {
    const command = buildSetLengthCommand(["point_A", "point_B"], 17.5, "mm");

    expect(command.version).toBe("0.2");
    expect(command.command_type).toBe("set_distance");
    expect(command.selection).toEqual(["point_A", "point_B"]);
    expect(command.parameters.distance).toBe(17.5);
    expect(command.parameters.unit).toBe("mm");
  });

  it("generates v0.4 driving axis distance commands", () => {
    const horizontal = buildSetHorizontalDistanceCommand(["point_A", "point_B"], 12, "mm");
    const vertical = buildSetVerticalDistanceCommand(["point_A", "point_B"], 7, "mm");

    expect(horizontal).toMatchObject({
      version: "0.4",
      command_type: "set_horizontal_distance",
      selection: ["point_A", "point_B"],
      parameters: { distance: 12, unit: "mm", anchor: "midpoint" },
    });
    expect(vertical).toMatchObject({
      version: "0.4",
      command_type: "set_vertical_distance",
      parameters: { distance: 7, unit: "mm", anchor: "midpoint" },
    });
  });

  it("generates v0.4 driving circle dimension commands", () => {
    expect(buildSetRadiusCommand("circle_A", 9)).toMatchObject({
      version: "0.4",
      command_type: "set_radius",
      selection: ["circle_A"],
      parameters: { radius: 9, unit: "mm" },
    });
    expect(buildSetDiameterCommand("circle_A", 18)).toMatchObject({
      version: "0.4",
      command_type: "set_diameter",
      selection: ["circle_A"],
      parameters: { diameter: 18, unit: "mm" },
    });
  });

  it("generates v0.5 canonical center and three-point arc commands", () => {
    const centerArc = buildDefineCenterArcCommand(
      { x: 0, y: 0 },
      { x: 10, y: 0 },
      { x: 0, y: 10 },
      "arc_center",
      { center: "center", start: "start", end: "end" },
    );
    const threePoint = buildDefineThreePointArcCommand(
      { x: 0, y: 0 },
      { x: 5, y: -5 },
      { x: 10, y: 0 },
      "arc_three",
      { start: "a", through: "b", end: "c" },
    );

    expect(centerArc).toMatchObject({
      version: "0.5",
      command_type: "define_arc",
      parameters: { construction: "center", direction: "clockwise", center_point_id: "center" },
    });
    expect(threePoint).toMatchObject({
      version: "0.5",
      command_type: "define_arc",
      parameters: { construction: "three_point", through_point_id: "b" },
    });
  });

  it("generates v0.6 Gate B constraint commands with explicit selection order", () => {
    expect(buildFixedCommand("anchor")).toMatchObject({ version: "0.6", command_type: "make_fixed", selection: ["anchor"] });
    expect(buildMidpointCommand(["mid", "a", "b"])).toMatchObject({ version: "0.6", command_type: "make_midpoint", selection: ["mid", "a", "b"] });
    expect(buildCollinearCommand(["a", "b", "moving"])).toMatchObject({ version: "0.6", command_type: "make_collinear", selection: ["a", "b", "moving"] });
    expect(buildSymmetricCommand(["reference", "target", "axis_a", "axis_b"])).toMatchObject({
      version: "0.6",
      command_type: "make_symmetric",
      selection: ["reference", "target", "axis_a", "axis_b"],
    });
    expect(buildConcentricCommand(["reference", "target"])).toMatchObject({ version: "0.6", command_type: "make_concentric" });
    expect(buildTangentCommand(["line", "circle"])).toMatchObject({
      version: "0.6",
      command_type: "make_tangent",
      selection: ["line", "circle"],
      parameters: { tangency: "external" },
    });
  });

  it("generates a v0.7 construction conversion command", () => {
    expect(buildSetConstructionCommand(["point", "line"], true)).toMatchObject({
      version: "0.7",
      command_type: "set_construction",
      selection: ["point", "line"],
      parameters: { enabled: true },
    });
  });

  it("generates v0.8 Gate B primitive and safe-edit commands", () => {
    expect(buildDefineRegularPolygonCommand({ x: 10, y: 20 }, 8, 6, "hex")).toMatchObject({
      version: "0.8",
      command_type: "define_regular_polygon",
      parameters: { center: [10, 20], radius: 8, sides: 6, name: "hex" },
    });
    expect(buildDefineSlotCommand({ x: 0, y: 0 }, { x: 20, y: 0 }, 8, "slot")).toMatchObject({
      version: "0.8",
      command_type: "define_slot",
      parameters: { start: [0, 0], end: [20, 0], width: 8 },
    });
    expect(buildSplitLineCommand("line")).toMatchObject({ version: "0.8", command_type: "split_line", selection: ["line"] });
    expect(buildTrimLineCommand("target", "cutter")).toMatchObject({ version: "0.8", command_type: "trim_line", selection: ["target", "cutter"] });
    expect(buildExtendLineCommand("target", "cutter")).toMatchObject({ version: "0.8", command_type: "extend_line" });
    expect(buildOffsetCurveCommand("arc", 4)).toMatchObject({ version: "0.8", command_type: "offset_curve", parameters: { distance: 4 } });
    expect(buildCopyLinearCommand(["profile"], { x: 25, y: 0 }, 3)).toMatchObject({ command_type: "copy_linear", parameters: { vector: [25, 0], count: 3 } });
  });

  it("generates a typed delete command for the full selected set", () => {
    const command = buildDeleteEntityCommand(["point_A", "point_B"]);

    expect(command.command_type).toBe("delete_entity");
    expect(command.selection).toEqual(["point_A", "point_B"]);
  });

  it("generates a typed rectangle dimension command for semantic rectangle edits", () => {
    const selection = [
      "rect_test_a",
      "rect_test_b",
      "rect_test_c",
      "rect_test_d",
      "rect_test_ab",
      "rect_test_bc",
      "rect_test_cd",
      "rect_test_da",
      "profile_rect_test",
    ];
    const command = buildSetRectangleDimensionCommand(selection, "width", 60, "mm");

    expect(command.command_type).toBe("set_rectangle_dimension");
    expect(command.selection).toEqual(selection);
    expect(command.parameters).toEqual({ dimension: "width", value: 60, unit: "mm" });
  });

  it("generates a typed add profile hole command", () => {
    const command = buildAddProfileHoleCommand("profile_rect_A", 12, { x: 280, y: 170 }, "mm");

    expect(command.command_type).toBe("add_profile_hole");
    expect(command.selection).toEqual(["profile_rect_A"]);
    expect(command.parameters).toEqual({ diameter: 12, unit: "mm", center: [280, 170] });
  });

  it("generates a typed update profile hole command", () => {
    const command = buildUpdateProfileHoleCommand("profile_rect_A", "hole_profile_rect_A_1", 8, { x: 280, y: 170 }, "mm");

    expect(command.command_type).toBe("update_profile_hole");
    expect(command.selection).toEqual(["profile_rect_A", "hole_profile_rect_A_1"]);
    expect(command.parameters).toEqual({ diameter: 8, unit: "mm", center: [280, 170] });
  });

  it("generates a typed extrude profile command for STEP preview", () => {
    const command = buildExtrudeProfileCommand("profile_rect_A", 10, "mm");

    expect(command.command_type).toBe("extrude_profile");
    expect(command.selection).toEqual(["profile_rect_A"]);
    expect(command.parameters).toEqual({
      depth: 10,
      depth_unit: "mm",
      direction: "positive_normal",
      output_format: "step",
    });
  });

  it("marks delete commands as cascade only when requested", () => {
    const command = buildDeleteEntityCommand(["rect_A_p1", "rect_A_l1"], true);

    expect(command.command_type).toBe("delete_entity");
    expect(command.selection).toEqual(["rect_A_p1", "rect_A_l1"]);
    expect(command.parameters).toEqual({ cascade: true });
  });

  it("generates a translation command with vector parameters", () => {
    const command = buildTranslateCommand(["line_A"], { x: 3, y: -1 });

    expect(command.command_type).toBe("translate");
    expect(command.parameters.vector).toEqual([3, -1]);
  });

  it("generates a preview-only v0.3 solver analysis command", () => {
    const command = buildAnalyzeConstraintsCommand();

    expect(command.version).toBe("0.3");
    expect(command.mode).toBe("preview");
    expect(command.command_type).toBe("analyze_constraints");
    expect(command.selection).toEqual([]);
    expect(command.parameters).toEqual({});
  });
});
