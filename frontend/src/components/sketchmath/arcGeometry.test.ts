import { arcEndpoints, arcSvgPath } from "./arcGeometry";

const arc = {
  id: "arc",
  type: "arc_2d" as const,
  center: [10, 20] as [number, number],
  radius: 5,
  start_angle_deg: 0,
  sweep_angle_deg: 90,
  construction: "center" as const,
};

describe("arc SVG geometry", () => {
  it("renders the canonical signed sweep without recomputing the circle", () => {
    expect(arcEndpoints(arc).start).toEqual({ x: 15, y: 20 });
    expect(arcEndpoints(arc).end.x).toBeCloseTo(10);
    expect(arcEndpoints(arc).end.y).toBeCloseTo(25);
    expect(arcSvgPath(arc)).toContain("A 5 5 0 0 1");
  });

  it("uses the large-arc and reverse-sweep flags for a major counterclockwise arc", () => {
    expect(arcSvgPath({ ...arc, sweep_angle_deg: -270 })).toContain("A 5 5 0 1 0");
  });
});
