import {
  buildAddProfileHoleCommand,
  buildDeleteEntityCommand,
  buildExtrudeProfileCommand,
  buildSetLengthCommand,
  buildSetRectangleDimensionCommand,
  buildTranslateCommand,
} from "./commandBuilders";

describe("SketchMath command builders", () => {
  it("generates a valid set length GeometryCommand", () => {
    const command = buildSetLengthCommand(["point_A", "point_B"], 17.5, "mm");

    expect(command.version).toBe("0.1");
    expect(command.command_type).toBe("set_distance");
    expect(command.selection).toEqual(["point_A", "point_B"]);
    expect(command.parameters.distance).toBe(17.5);
    expect(command.parameters.unit).toBe("mm");
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
});
