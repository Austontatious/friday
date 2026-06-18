import { buildDeleteEntityCommand, buildSetLengthCommand, buildTranslateCommand } from "./commandBuilders";

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
