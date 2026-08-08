import React from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SketchMathWorkspace from "./SketchMathWorkspace";

jest.mock("@chakra-ui/react", () => {
  const React = require("react");
  const makeElement = (tag: string) =>
    React.forwardRef(({ as, children, flexWrap, whiteSpace, alignItems, isDisabled, ...props }: any, ref: React.Ref<HTMLElement>) =>
      React.createElement(as || tag, { ...props, ref, disabled: isDisabled }, children),
    );
  const Textarea = React.forwardRef(({ children, ...props }: any, ref: React.Ref<HTMLTextAreaElement>) =>
    React.createElement("textarea", { ...props, ref }, children),
  );
  const Input = React.forwardRef(({ children, ...props }: any, ref: React.Ref<HTMLInputElement>) =>
    React.createElement("input", { ...props, ref }, children),
  );
  const ChakraProvider = ({ children }: any) => React.createElement(React.Fragment, null, children);
  const useColorMode = () => {
    const [colorMode, setColorMode] = React.useState("light");
    return {
      colorMode,
      toggleColorMode: () => setColorMode((mode: string) => (mode === "light" ? "dark" : "light")),
    };
  };
  const useToast = () => () => undefined;
  return {
    Box: makeElement("div"),
    Button: makeElement("button"),
    Divider: makeElement("hr"),
    Heading: makeElement("h2"),
    HStack: makeElement("div"),
    Input,
    Link: makeElement("a"),
    Spinner: makeElement("div"),
    Text: makeElement("span"),
    Textarea,
    VStack: makeElement("div"),
    ChakraProvider,
    useColorMode,
    useToast,
  };
});

type Entity =
  | { id: string; type: "point_2d"; coords: [number, number]; locked: boolean; label?: string | null }
  | { id: string; type: "line_2d"; start: [number, number]; end: [number, number]; start_point_id?: string | null; end_point_id?: string | null; locked: boolean; label?: string | null }
  | { id: string; type: "circle_2d"; center: [number, number]; radius: number; center_point_id?: string | null; locked: boolean; label?: string | null }
  | {
      id: string;
      type: "profile_2d";
      vertices: [number, number][];
      area: number;
      winding: "clockwise" | "counterclockwise" | "degenerate";
      warnings: string[];
      closed: boolean;
      locked: boolean;
      holes?: string[];
      source_line_ids?: string[];
      source_circle_id?: string | null;
      label?: string | null;
    };

type Snapshot = {
  session_id: string;
  selection_context: {
    selection_set_id: string;
    units: string;
    frame: "canvas_2d";
    items: Entity[];
    constraints: Array<Record<string, any>>;
    named_references: Record<string, string>;
  };
  session_metadata: Record<string, unknown>;
  history: Array<Record<string, any>>;
  history_length: number;
};

const baseSnapshot = (): Snapshot => ({
  session_id: "sm_test_session",
  selection_context: {
    selection_set_id: "sel_workspace",
    units: "mm",
    frame: "canvas_2d",
    items: [],
    constraints: [],
    named_references: {},
  },
  session_metadata: { persisted: true, storage_path: "/tmp/sketchmath/sm_test_session.json" },
  history: [],
  history_length: 0,
});

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));

const makePreviewMesh = (profileId: string, depth: number, holeCount: number) => ({
  version: "0.1",
  units: "mm",
  profile_id: profileId,
  depth,
  vertices: [
    [0, 0, 0],
    [40, 0, 0],
    [40, 25, 0],
    [0, 25, 0],
    [0, 0, depth],
    [40, 0, depth],
    [40, 25, depth],
    [0, 25, depth],
    [18, 10, 0],
    [22, 10, 0],
    [22, 15, 0],
    [18, 15, 0],
    [18, 10, depth],
    [22, 10, depth],
    [22, 15, depth],
    [18, 15, depth],
  ],
  triangles: [
    { indices: [4, 5, 6], surface: "top" },
    { indices: [4, 6, 7], surface: "top" },
    { indices: [0, 2, 1], surface: "bottom" },
    { indices: [0, 3, 2], surface: "bottom" },
    { indices: [0, 1, 5], surface: "outer_wall" },
    { indices: [0, 5, 4], surface: "outer_wall" },
    { indices: [8, 13, 9], surface: "hole_wall", ring_id: "hole" },
    { indices: [8, 12, 13], surface: "hole_wall", ring_id: "hole" },
  ],
  metadata: {
    profile_id: profileId,
    extrusion_depth: depth,
    extrusion_depth_unit: "mm",
    hole_count: holeCount,
    triangle_count: 8,
    vertex_count: 16,
    bbox: { xmin: 0, xmax: 40, ymin: 0, ymax: 25, zmin: 0, zmax: depth },
  },
});

const makeResponse = (payload: any) => ({
  ok: true,
  status: 200,
  json: async () => clone(payload),
  text: async () => JSON.stringify(payload),
  headers: { get: () => "application/json" },
});

const createSketchmathMock = (options: { failDefineLine?: boolean; failAddProfileHoleDependency?: boolean; solverAnalysis?: Record<string, unknown> } = {}) => {
  let snapshot = baseSnapshot();

  const replaceNamedReference = (entityId: string, label: string | null | undefined) => {
    Object.entries(snapshot.selection_context.named_references).forEach(([name, mapped]) => {
      if (mapped === entityId) {
        delete snapshot.selection_context.named_references[name];
      }
    });
    if (label) {
      snapshot.selection_context.named_references[label] = entityId;
    }
  };

  const setSnapshot = (nextItems: Entity[], changedEntityIds: string[], command: any, mutate: boolean) => {
    const nextContext = { ...snapshot.selection_context, items: nextItems };
    if (mutate) {
      snapshot = {
        ...snapshot,
        selection_context: nextContext,
        history: [
          ...snapshot.history,
          {
            command: { ...command, mode: "commit" },
            committed: true,
            before: snapshot.selection_context,
            after: nextContext,
          },
        ],
        history_length: snapshot.history.length + 1,
      };
      changedEntityIds.forEach((entityId) => {
        const entity = snapshot.selection_context.items.find((item) => item.id === entityId);
        replaceNamedReference(entityId, entity?.label || null);
      });
    }
    return {
      session_id: snapshot.session_id,
      selection_context: mutate ? snapshot.selection_context : nextContext,
      result: {
        command: { ...command, mode: command.mode || "preview" },
        status: mutate ? "committed" : "preview",
        before: snapshot.selection_context,
        after: nextContext,
        changed_entity_ids: changedEntityIds,
        replay_index: snapshot.history.length,
        metadata: {},
      },
      history_length: snapshot.history.length,
      session_metadata: snapshot.session_metadata,
    };
  };

  const appendConstraint = (constraint: Record<string, any>, command: any, changedEntityIds: string[], mutate: boolean) => {
    const nextContext = { ...snapshot.selection_context, constraints: [...snapshot.selection_context.constraints, constraint] };
    if (mutate) {
      snapshot = {
        ...snapshot,
        selection_context: nextContext,
        history: [
          ...snapshot.history,
          {
            command: { ...command, mode: "commit" },
            committed: true,
            before: snapshot.selection_context,
            after: nextContext,
          },
        ],
        history_length: snapshot.history.length + 1,
      };
    }
    return {
      session_id: snapshot.session_id,
      selection_context: mutate ? snapshot.selection_context : nextContext,
      result: {
        command: { ...command, mode: command.mode || "preview" },
        status: mutate ? "committed" : "preview",
        before: snapshot.selection_context,
        after: nextContext,
        changed_entity_ids: changedEntityIds,
        replay_index: snapshot.history.length,
        metadata: {},
      },
      history_length: snapshot.history.length,
      session_metadata: snapshot.session_metadata,
    };
  };

  const definePoint = (command: any, mutate: boolean) => {
    const entity: Entity = {
      id: command.parameters.name,
      type: "point_2d",
      coords: command.parameters.coords,
      locked: !!command.parameters.locked,
      label: command.parameters.label || null,
    };
    const nextItems = [...snapshot.selection_context.items.filter((item) => item.id !== entity.id), entity];
    return setSnapshot(nextItems, [entity.id], command, mutate);
  };

  const defineLine = (command: any, mutate: boolean) => {
    const entity: Entity = {
      id: command.parameters.name,
      type: "line_2d",
      start: command.parameters.start,
      end: command.parameters.end,
      start_point_id: command.parameters.start_point_id || null,
      end_point_id: command.parameters.end_point_id || null,
      locked: !!command.parameters.locked,
      label: command.parameters.label || null,
    };
    const nextItems = [...snapshot.selection_context.items.filter((item) => item.id !== entity.id), entity];
    return setSnapshot(nextItems, [entity.id], command, mutate);
  };

  const deleteEntity = (command: any, mutate: boolean) => {
    const ids = command.selection as string[];
    const cascade = command.parameters?.cascade === true;
    const referenced = new Set<string>();
    snapshot.selection_context.constraints.forEach((constraint) => {
      (constraint.points || []).forEach((pointId: string) => referenced.add(pointId));
    });
    Object.values(snapshot.selection_context.named_references).forEach((entityId) => referenced.add(entityId));
    if (!cascade && ids.some((entityId) => referenced.has(entityId))) {
      return {
        __mockErrorResponse: true,
        ok: false,
        status: 422,
        json: async () => ({
          detail: {
            code: "selection_resolution_error",
            message: "Cannot delete an entity that is still referenced",
          },
        }),
        text: async () => "Cannot delete an entity that is still referenced",
        headers: { get: () => "application/json" },
      };
    }
    const nextItems = snapshot.selection_context.items.filter((item) => !ids.includes(item.id));
    const nextNamed = Object.fromEntries(
      Object.entries(snapshot.selection_context.named_references).filter(([, mapped]) => !ids.includes(mapped)),
    );
    const nextConstraints = cascade
      ? snapshot.selection_context.constraints.filter((constraint) => !(constraint.points || []).some((pointId: string) => ids.includes(pointId)))
      : snapshot.selection_context.constraints;
    const nextContext = { ...snapshot.selection_context, items: nextItems, constraints: nextConstraints, named_references: nextNamed };
    if (mutate) {
      snapshot = {
        ...snapshot,
        selection_context: nextContext,
        history: [
          ...snapshot.history,
          {
            command: { ...command, mode: "commit" },
            committed: true,
            before: snapshot.selection_context,
            after: nextContext,
          },
        ],
        history_length: snapshot.history.length + 1,
      };
    }
    return {
      session_id: snapshot.session_id,
      selection_context: mutate ? snapshot.selection_context : nextContext,
      result: {
        command: { ...command, mode: command.mode || "preview" },
        status: mutate ? "committed" : "preview",
        before: snapshot.selection_context,
        after: nextContext,
        changed_entity_ids: ids,
        replay_index: snapshot.history.length,
        metadata: {},
      },
      history_length: snapshot.history.length,
      session_metadata: snapshot.session_metadata,
    };
  };

  const constraintHandler = (command: any, mutate: boolean, type: string, changedEntityIds: string[]) => {
    const priorSnapshot = snapshot;
    if (["radius_constraint", "diameter_constraint"].includes(type)) {
      snapshot = {
        ...snapshot,
        selection_context: {
          ...snapshot.selection_context,
          constraints: snapshot.selection_context.constraints.filter((constraint) =>
            !["radius_constraint", "diameter_constraint"].includes(String(constraint.type)) || constraint.circle_id !== command.selection[0]),
        },
      };
    }
    const response = appendConstraint(
      {
        id: `${type}_${snapshot.history.length + 1}`,
        type,
        points: command.selection,
        distance: command.parameters.distance,
        unit: command.parameters.unit || "mm",
        angle: command.parameters.angle,
        anchor: command.parameters.anchor,
        direction: command.parameters.direction || 1,
        circle_id: command.selection[0],
        radius: command.parameters.radius,
        diameter: command.parameters.diameter,
      },
      command,
      changedEntityIds,
      mutate,
    );
    if (!mutate) snapshot = priorSnapshot;
    return response;
  };

  const circleDimensionHandler = (command: any, mutate: boolean) => {
    const beforeContext = snapshot.selection_context;
    const existing = beforeContext.items.find((item) => item.id === command.selection[0]) as Extract<Entity, { type: "circle_2d" }>;
    const radius = command.command_type === "set_radius" ? command.parameters.radius : command.parameters.diameter / 2;
    const constraintType = command.command_type === "set_radius" ? "radius_constraint" : "diameter_constraint";
    const constraint = {
      id: `${constraintType}_${snapshot.history.length + 1}`,
      type: constraintType,
      circle_id: existing.id,
      radius: command.parameters.radius,
      diameter: command.parameters.diameter,
      unit: command.parameters.unit || "mm",
    };
    const nextContext = {
      ...beforeContext,
      items: beforeContext.items.map((item) => item.id === existing.id ? { ...existing, radius } : item) as Entity[],
      constraints: [
        ...beforeContext.constraints.filter((item) =>
          !["radius_constraint", "diameter_constraint"].includes(String(item.type)) || item.circle_id !== existing.id),
        constraint,
      ],
    };
    if (mutate) {
      snapshot = {
        ...snapshot,
        selection_context: nextContext,
        history: [
          ...snapshot.history,
          { command: { ...command, mode: "commit" }, committed: true, before: beforeContext, after: nextContext },
        ],
        history_length: snapshot.history.length + 1,
      };
    }
    return {
      session_id: snapshot.session_id,
      selection_context: mutate ? snapshot.selection_context : nextContext,
      result: {
        command: { ...command, mode: command.mode || "preview" },
        status: mutate ? "committed" : "preview",
        before: beforeContext,
        after: nextContext,
        changed_entity_ids: [existing.id],
        replay_index: snapshot.history.length,
        metadata: { constraint_id: constraint.id, radius, diameter: radius * 2 },
      },
      history_length: snapshot.history.length,
      session_metadata: snapshot.session_metadata,
    };
  };

  const profile = (command: any, mutate: boolean) => {
    const selected = command.selection
      .map((entityId: string) => snapshot.selection_context.items.find((item) => item.id === entityId))
      .filter(Boolean) as Entity[];
    let vertices: [number, number][];
    if (selected.length > 0 && selected.every((item) => item.type === "point_2d")) {
      vertices = selected.map((point) => (point as Extract<Entity, { type: "point_2d" }>).coords) as [number, number][];
    } else if (selected.length > 0 && selected.every((item) => item.type === "line_2d")) {
      const lines = selected as Extract<Entity, { type: "line_2d" }>[];
      vertices = [lines[0].start];
      for (const line of lines) {
        const start = line.start;
        const end = line.end;
        if (vertices[vertices.length - 1][0] === start[0] && vertices[vertices.length - 1][1] === start[1]) {
          vertices.push(end);
        } else if (vertices[vertices.length - 1][0] === end[0] && vertices[vertices.length - 1][1] === end[1]) {
          vertices.push(start);
        } else {
          vertices.push(end);
        }
      }
    } else {
      vertices = [];
    }
    const entity: Entity = {
      id: command.parameters.name || `profile_${snapshot.history.length + 1}`,
      type: "profile_2d",
      vertices,
      area: vertices.length >= 3 ? vertices.length * 10 : 0,
      winding: "counterclockwise",
      warnings: [],
      closed: vertices.length >= 3,
      locked: false,
      label: command.parameters.name || null,
      source_line_ids: selected.filter((item): item is Extract<Entity, { type: "line_2d" }> => item.type === "line_2d").map((item) => item.id),
    };
    const nextItems = [...snapshot.selection_context.items.filter((item) => item.id !== entity.id), entity];
    return setSnapshot(nextItems, [entity.id], command, mutate);
  };

  const solveConstraints = (command: any, mutate: boolean) => {
    const nextItems = snapshot.selection_context.items.map((item) => {
      if (item.type !== "point_2d") {
        return item;
      }
      const match = /^rect_(.+)_([abcd])$/.exec(item.id);
      if (!match) {
        return item;
      }
      const baseId = `rect_${match[1]}`;
      const rectanglePoints = snapshot.selection_context.items.filter(
        (candidate): candidate is Extract<Entity, { type: "point_2d" }> =>
          candidate.type === "point_2d" && candidate.id.startsWith(baseId),
      );
      if (rectanglePoints.length !== 4) {
        return item;
      }
      const xs = rectanglePoints.map((point) => point.coords[0]);
      const ys = rectanglePoints.map((point) => point.coords[1]);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      const coordsBySuffix: Record<string, [number, number]> = {
        a: [minX, minY],
        b: [maxX, minY],
        c: [maxX, maxY],
        d: [minX, maxY],
      };
      const suffix = match[2];
      return { ...item, coords: coordsBySuffix[suffix] || item.coords };
    });
    return setSnapshot(nextItems as Entity[], [], command, mutate);
  };

  const analyzeConstraints = (command: any) => {
    const points = snapshot.selection_context.items.filter((item): item is Extract<Entity, { type: "point_2d" }> => item.type === "point_2d");
    const circles = snapshot.selection_context.items.filter((item): item is Extract<Entity, { type: "circle_2d" }> => item.type === "circle_2d");
    const supportedTypes = new Set([
      "fixed_point_constraint",
      "horizontal_constraint",
      "vertical_constraint",
      "coincident_constraint",
      "horizontal_distance_constraint",
      "vertical_distance_constraint",
      "radius_constraint",
      "diameter_constraint",
    ]);
    const unsupportedConstraintIds = snapshot.selection_context.constraints
      .filter((constraint) => !supportedTypes.has(String(constraint.type)))
      .map((constraint) => String(constraint.id));
    const unmodeledEntityIds = snapshot.selection_context.items
      .filter((item) => {
        if (item.type === "point_2d") return false;
        if (item.type === "line_2d") return !item.start_point_id || !item.end_point_id;
        if (item.type === "profile_2d") return !(item.source_line_ids?.length || item.source_circle_id);
        if (item.type === "circle_2d") return false;
        return true;
      })
      .map((item) => item.id);
    const fixedCount = points.filter((point) => point.locked).length;
    const supportedEquationCount = snapshot.selection_context.constraints.reduce((count, constraint) => {
      if (constraint.type === "fixed_point_constraint" || constraint.type === "coincident_constraint") return count + 2;
      if (["horizontal_constraint", "vertical_constraint", "horizontal_distance_constraint", "vertical_distance_constraint", "radius_constraint", "diameter_constraint"].includes(String(constraint.type))) return count + 1;
      return count;
    }, fixedCount * 2);
    const trackedVariableCount = points.length * 2 + circles.reduce((count, circle) => count + (circle.center_point_id ? 1 : 3), 0);
    const exact = unsupportedConstraintIds.length === 0 && unmodeledEntityIds.length === 0;
    const remainingDof = exact ? Math.max(0, trackedVariableCount - supportedEquationCount) : null;
    const analysis = {
      schema_version: "1.0",
      coverage: exact ? "exact" : points.length ? "partial" : "unknown",
      freedom_state: exact ? (remainingDof === 0 ? "fully_constrained" : "under_constrained") : "unknown",
      consistency_state: exact ? "consistent" : "unknown",
      redundancy_state: exact ? "none" : "unknown",
      tracked_variable_count: trackedVariableCount,
      independent_equation_count: supportedEquationCount,
      remaining_dof: remainingDof,
      remaining_tracked_dof_upper_bound: Math.max(0, trackedVariableCount - supportedEquationCount),
      fixed_entity_ids: points.filter((point) => point.locked).map((point) => point.id),
      supported_constraint_ids: snapshot.selection_context.constraints.filter((constraint) => supportedTypes.has(String(constraint.type))).map((constraint) => String(constraint.id)),
      unsupported_constraint_ids: unsupportedConstraintIds,
      invalid_constraint_ids: [],
      redundant_constraint_ids: [],
      conflicting_constraint_ids: [],
      unmodeled_entity_ids: unmodeledEntityIds,
      diagnostics: exact ? [] : ["Fixture contains geometry or constraints outside exact analysis coverage."],
      tolerance_policy: { version: "1.0", coordinate_abs_mm: 1e-9, scalar_rel: 1e-9, linear_rank_abs: 1e-10 },
      ...options.solverAnalysis,
    };
    const response = setSnapshot(snapshot.selection_context.items, [], command, false);
    response.result.metadata = { solver_analysis: analysis };
    return response;
  };

  const setRectangleDimension = (command: any, mutate: boolean) => {
    const baseId = (command.selection as string[])
      .map((entityId) => {
        if (entityId.startsWith("profile_rect_")) {
          return entityId.replace(/^profile_/, "");
        }
        const match = /^(rect_.+)_(a|b|c|d|ab|bc|cd|da)$/.exec(entityId);
        return match ? match[1] : null;
      })
      .find(Boolean);
    if (!baseId) {
      throw new Error("set_rectangle_dimension requires rectangle selection");
    }
    const pointById = new Map(
      snapshot.selection_context.items.filter((item): item is Extract<Entity, { type: "point_2d" }> => item.type === "point_2d").map((item) => [item.id, item] as const),
    );
    const lineById = new Map(
      snapshot.selection_context.items.filter((item): item is Extract<Entity, { type: "line_2d" }> => item.type === "line_2d").map((item) => [item.id, item] as const),
    );
    const a = pointById.get(`${baseId}_a`);
    const top = lineById.get(`${baseId}_ab`);
    const left = lineById.get(`${baseId}_da`);
    if (!a || !top || !left) {
      throw new Error("Rectangle geometry is incomplete");
    }
    const currentWidth = Math.abs(top.end[0] - top.start[0]);
    const currentHeight = Math.abs(left.start[1] - left.end[1]);
    const width = command.parameters.dimension === "width" ? Number(command.parameters.value) : currentWidth;
    const height = command.parameters.dimension === "height" ? Number(command.parameters.value) : currentHeight;
    const signX = top.end[0] >= top.start[0] ? 1 : -1;
    const signY = left.start[1] >= left.end[1] ? 1 : -1;
    const topLeft: [number, number] = [a.coords[0], a.coords[1]];
    const topRight: [number, number] = [Number((a.coords[0] + signX * width).toFixed(2)), a.coords[1]];
    const bottomLeft: [number, number] = [a.coords[0], Number((a.coords[1] + signY * height).toFixed(2))];
    const bottomRight: [number, number] = [topRight[0], bottomLeft[1]];
    const replacements: Record<string, Entity> = {
      [`${baseId}_a`]: { ...pointById.get(`${baseId}_a`)!, coords: topLeft },
      [`${baseId}_b`]: { ...pointById.get(`${baseId}_b`)!, coords: topRight },
      [`${baseId}_c`]: { ...pointById.get(`${baseId}_c`)!, coords: bottomRight },
      [`${baseId}_d`]: { ...pointById.get(`${baseId}_d`)!, coords: bottomLeft },
      [`${baseId}_ab`]: { ...lineById.get(`${baseId}_ab`)!, start: topLeft, end: topRight },
      [`${baseId}_bc`]: { ...lineById.get(`${baseId}_bc`)!, start: topRight, end: bottomRight },
      [`${baseId}_cd`]: { ...lineById.get(`${baseId}_cd`)!, start: bottomRight, end: bottomLeft },
      [`${baseId}_da`]: { ...lineById.get(`${baseId}_da`)!, start: bottomLeft, end: topLeft },
      [`profile_${baseId}`]: {
        id: `profile_${baseId}`,
        type: "profile_2d",
        vertices: [topLeft, topRight, bottomRight, bottomLeft, topLeft],
        area: Number((width * height).toFixed(2)),
        winding: "counterclockwise",
        warnings: [],
        closed: true,
        locked: false,
        label: `profile_${baseId}`,
      },
    };
    const changed = Object.keys(replacements);
    const nextItems = snapshot.selection_context.items.map((item) => replacements[item.id] || item);
    return setSnapshot(nextItems, changed, command, mutate);
  };

  const addProfileHole = (command: any, mutate: boolean) => {
    const profileId = command.selection[0];
    const profileEntity = snapshot.selection_context.items.find(
      (item): item is Extract<Entity, { type: "profile_2d" }> => item.type === "profile_2d" && item.id === profileId,
    );
    if (!profileEntity) {
      throw new Error("add_profile_hole requires profile selection");
    }
    const center = command.parameters.center as [number, number];
    const diameter = Number(command.parameters.diameter);
    const radius = diameter / 2;
    const holeId = `hole_${profileId}_${command.command_id}`;
    const vertices: [number, number][] = [
      [center[0] - radius, center[1] - radius],
      [center[0] - radius, center[1] + radius],
      [center[0] + radius, center[1] + radius],
      [center[0] + radius, center[1] - radius],
      [center[0] - radius, center[1] - radius],
    ];
    const hole: Entity = {
      id: holeId,
      type: "profile_2d",
      vertices,
      area: diameter * diameter,
      winding: "clockwise",
      warnings: [],
      closed: true,
      locked: false,
      label: "Hole",
    };
    const updatedProfile: Entity = { ...profileEntity, holes: [...(profileEntity.holes || []), holeId] };
    const nextItems = [
      ...snapshot.selection_context.items.filter((item) => item.id !== profileId && item.id !== holeId),
      updatedProfile,
      hole,
    ];
    return setSnapshot(nextItems, [profileId, holeId], command, mutate);
  };

  const updateProfileHole = (command: any, mutate: boolean) => {
    const [profileId, holeId] = command.selection as string[];
    const profileEntity = snapshot.selection_context.items.find(
      (item): item is Extract<Entity, { type: "profile_2d" }> => item.type === "profile_2d" && item.id === profileId,
    );
    const holeEntity = snapshot.selection_context.items.find(
      (item): item is Extract<Entity, { type: "profile_2d" }> => item.type === "profile_2d" && item.id === holeId,
    );
    if (!profileEntity || !holeEntity || !(profileEntity.holes || []).includes(holeId)) {
      throw new Error("update_profile_hole requires a parent profile and existing hole");
    }
    const center = command.parameters.center as [number, number];
    const diameter = Number(command.parameters.diameter);
    const radius = diameter / 2;
    const updatedHole: Entity = {
      ...holeEntity,
      vertices: [
        [center[0] - radius, center[1] - radius],
        [center[0] - radius, center[1] + radius],
        [center[0] + radius, center[1] + radius],
        [center[0] + radius, center[1] - radius],
        [center[0] - radius, center[1] - radius],
      ],
      area: diameter * diameter,
    };
    const nextItems = snapshot.selection_context.items.map((item) => (item.id === holeId ? updatedHole : item));
    return setSnapshot(nextItems, [profileId, holeId], command, mutate);
  };

  const extrudeProfile = (command: any, mutate: boolean) => {
    const profileId = command.selection[0];
    const profileEntity = snapshot.selection_context.items.find(
      (item): item is Extract<Entity, { type: "profile_2d" }> => item.type === "profile_2d" && item.id === profileId,
    );
    if (!profileEntity) {
      throw new Error("extrude_profile requires profile selection");
    }
    const holeIds = profileEntity.holes || [];
    const response = setSnapshot(snapshot.selection_context.items, [], command, mutate) as any;
    response.result.value = 1200;
    response.result.unit = "mm^3";
    response.result.metadata = {
      cad_export: {
        status: "export_ready",
        artifacts: {
          step_path: `/tmp/sketchmath/${command.command_id}/export.step`,
        },
        metadata: {
          adapter_strategy: holeIds.length ? "face_with_holes" : "plain_extrude",
          hole_count: holeIds.length,
          artifact_filename: "export.step",
          artifact_size_bytes: 2048,
          artifact_created_at: "2026-06-24T12:00:00+00:00",
          profile_id: profileId,
          extrusion_depth: Number(command.parameters.depth),
          extrusion_depth_unit: command.parameters.depth_unit || "mm",
        },
        measurements: {
          is_valid_solid: true,
          volume_mm3: 1200,
        },
      },
      profile_hole_validation: {
        ok: true,
        details: {
          hole_profile_ids: holeIds,
        },
      },
      preview_mesh: makePreviewMesh(profileId, Number(command.parameters.depth), holeIds.length),
    };
    return response;
  };

  async function fetchMockImpl(input: RequestInfo | URL, init?: RequestInit): Promise<any> {
    const url = String(input);
    const method = (init?.method || "GET").toUpperCase();

    if (url.endsWith("/api/sketchmath/sessions") && method === "POST") {
      snapshot = baseSnapshot();
      return makeResponse(snapshot);
    }
    if (url.endsWith(`/api/sketchmath/sessions/${snapshot.session_id}`) && method === "GET") {
      return makeResponse(snapshot);
    }
    if (url.endsWith(`/api/sketchmath/sessions/${snapshot.session_id}/history`) && method === "GET") {
      return makeResponse({ session_id: snapshot.session_id, history: snapshot.history, history_length: snapshot.history_length });
    }
    if (url.endsWith(`/api/sketchmath/sessions/${snapshot.session_id}/revert`) && method === "POST") {
      snapshot = baseSnapshot();
      return makeResponse(snapshot);
    }
    if (url.endsWith(`/api/sketchmath/sessions/${snapshot.session_id}/redo`) && method === "POST") {
      return makeResponse(snapshot);
    }
    if (url.endsWith(`/api/sketchmath/sessions/${snapshot.session_id}/entities`) && method === "POST") {
      const body = JSON.parse(String(init?.body || "{}"));
      const entity = body.entity;
      const nextItems = [...snapshot.selection_context.items.filter((item) => item.id !== entity.id), entity];
      return makeResponse(setSnapshot(nextItems, [entity.id], body, body.mode === "commit"));
    }
    if (init?.body && (url.includes("/commands/preview") || url.includes("/commands/commit"))) {
      const body = JSON.parse(String(init.body));
      const command = body.command;
      const mutate = url.includes("/commit");
      if (command.command_type === "batch") {
        const beforeBatch = clone(snapshot);
        let response: ReturnType<typeof makeResponse> | null = null;
        for (const subcommand of command.parameters.commands || []) {
          response = await fetchMockImpl(url, { ...(init || {}), body: JSON.stringify({ command: subcommand }) });
          if ((response as any).__mockErrorResponse) {
            snapshot = beforeBatch;
            return response;
          }
        }
        if (!mutate) {
          snapshot = beforeBatch;
        }
        return response || makeResponse(snapshot);
      }
      if (command.command_type === "define_point") {
        return makeResponse(definePoint(command, mutate));
      }
      if (command.command_type === "define_line") {
        if (options.failDefineLine) {
          return {
            __mockErrorResponse: true,
            ok: false,
            status: 500,
            json: async () => ({ detail: { message: "Failed to create line" } }),
            text: async () => "Failed to create line",
            headers: { get: () => "application/json" },
          };
        }
        return makeResponse(defineLine(command, mutate));
      }
      if (command.command_type === "define_circle") {
        const entity: Entity = { id: command.parameters.name, type: "circle_2d", center: command.parameters.center, radius: command.parameters.radius, center_point_id: command.parameters.center_point_id, locked: false, label: command.parameters.label };
        return makeResponse(setSnapshot([...snapshot.selection_context.items.filter((item) => item.id !== entity.id), entity], [entity.id], command, mutate));
      }
      if (command.command_type === "update_circle") {
        const existing = snapshot.selection_context.items.find((item) => item.id === command.selection[0]) as any;
        const entity = { ...existing, center: command.parameters.center || existing.center, radius: command.parameters.radius || existing.radius };
        return makeResponse(setSnapshot([...snapshot.selection_context.items.filter((item) => item.id !== entity.id), entity], [entity.id], command, mutate));
      }
      if (command.command_type === "make_circle_profile") {
        const circle = snapshot.selection_context.items.find((item) => item.id === command.selection[0]) as any;
        const vertices = Array.from({ length: 17 }, (_, index) => {
          const angle = (index % 16) * Math.PI * 2 / 16;
          return [circle.center[0] + circle.radius * Math.cos(angle), circle.center[1] + circle.radius * Math.sin(angle)] as [number, number];
        });
        const entity: Entity = { id: command.parameters.name || `profile_${circle.id}`, type: "profile_2d", vertices, area: Math.PI * circle.radius ** 2, winding: "counterclockwise", warnings: [], closed: true, locked: false, holes: [], source_circle_id: circle.id };
        return makeResponse(setSnapshot([...snapshot.selection_context.items.filter((item) => item.id !== entity.id), entity], [entity.id], command, mutate));
      }
      if (command.command_type === "delete_entity") {
        const deleted = deleteEntity(command, mutate);
        if ((deleted as any).__mockErrorResponse) {
          return deleted;
        }
        return makeResponse(deleted);
      }
      if (command.command_type === "set_distance") {
        return makeResponse(constraintHandler(command, mutate, "distance_constraint", command.selection.slice(0, 2)));
      }
      if (command.command_type === "set_horizontal_distance") {
        return makeResponse(constraintHandler(command, mutate, "horizontal_distance_constraint", command.selection.slice(0, 2)));
      }
      if (command.command_type === "set_vertical_distance") {
        return makeResponse(constraintHandler(command, mutate, "vertical_distance_constraint", command.selection.slice(0, 2)));
      }
      if (command.command_type === "set_radius" || command.command_type === "set_diameter") {
        return makeResponse(circleDimensionHandler(command, mutate));
      }
      if (command.command_type === "set_rectangle_dimension") {
        return makeResponse(setRectangleDimension(command, mutate));
      }
      if (command.command_type === "add_profile_hole") {
        if (options.failAddProfileHoleDependency) {
          const payload = {
            detail: {
              error: {
                code: "selection_resolution_error",
                message: "shapely is required for SketchMath hole validation",
                detail: { error_code: "dependency_missing", dependency: "shapely" },
                retryable: false,
              },
            },
          };
          return {
            __mockErrorResponse: true,
            ok: false,
            status: 422,
            json: async () => payload,
            text: async () => JSON.stringify(payload),
            headers: { get: () => "application/json" },
          };
        }
        return makeResponse(addProfileHole(command, mutate));
      }
      if (command.command_type === "update_profile_hole") {
        return makeResponse(updateProfileHole(command, mutate));
      }
      if (command.command_type === "extrude_profile") {
        return makeResponse(extrudeProfile(command, mutate));
      }
      if (command.command_type === "set_angle") {
        return makeResponse(constraintHandler(command, mutate, "angle_constraint", command.selection.slice(0, 3)));
      }
      if (command.command_type === "make_parallel") {
        return makeResponse(constraintHandler(command, mutate, "parallel_constraint", command.selection.slice(0, 4)));
      }
      if (command.command_type === "make_perpendicular") {
        return makeResponse(constraintHandler(command, mutate, "perpendicular_constraint", command.selection.slice(0, 4)));
      }
      if (command.command_type === "make_equal_length") {
        return makeResponse(constraintHandler(command, mutate, "equal_length_constraint", command.selection.slice(0, 4)));
      }
      if (command.command_type === "make_equal_angle") {
        return makeResponse(constraintHandler(command, mutate, "equal_angle_constraint", command.selection.slice(0, 6)));
      }
      if (command.command_type === "make_horizontal") {
        return makeResponse(constraintHandler(command, mutate, "horizontal_constraint", command.selection));
      }
      if (command.command_type === "make_vertical") {
        return makeResponse(constraintHandler(command, mutate, "vertical_constraint", command.selection));
      }
      if (command.command_type === "make_coincident") {
        return makeResponse(constraintHandler(command, mutate, "coincident_constraint", command.selection.slice(0, 2)));
      }
      if (command.command_type === "detect_profiles") {
        const response = setSnapshot(snapshot.selection_context.items, [], command, false);
        response.result.metadata = { profile_candidates: [] };
        return makeResponse(response);
      }
      if (command.command_type === "analyze_constraints") {
        return makeResponse(analyzeConstraints(command));
      }
      if (command.command_type === "solve_constraints") {
        return makeResponse(solveConstraints(command, mutate));
      }
      if (command.command_type === "make_profile") {
        return makeResponse(profile(command, mutate));
      }
    }

    throw new Error(`Unhandled fetch call: ${method} ${url}`);
  }

  const fetchMock = jest.fn(fetchMockImpl);

  return { fetchMock };
};

const renderWorkspace = () => render(<SketchMathWorkspace />);

const clickCanvasAt = (canvas: HTMLElement, x: number, y: number) => {
  const bounds = { left: 0, top: 0, width: 1200, height: 800, right: 1200, bottom: 800, x: 0, y: 0, toJSON: () => ({}) };
  if (!jest.isMockFunction(canvas.getBoundingClientRect)) {
    jest.spyOn(canvas, "getBoundingClientRect").mockReturnValue(bounds as DOMRect);
  }
  fireEvent.click(canvas, { clientX: x, clientY: y });
};

const pointerCanvasAt = (
  canvas: HTMLElement,
  type: "pointerdown" | "pointermove" | "pointerup",
  props: { clientX: number; clientY: number; pointerId: number; button?: number; buttons?: number; shiftKey?: boolean },
) => {
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.entries({ button: 0, buttons: 0, shiftKey: false, ...props }).forEach(([key, value]) => {
    Object.defineProperty(event, key, { configurable: true, value });
  });
  fireEvent(canvas, event);
};

describe("SketchMath workspace", () => {
  const stamp = { value: 1710000000000 };
  const firstStamp = 1710000000000;
  const secondStamp = 1710000001000;

  beforeEach(() => {
    window.localStorage.clear();
    process.env.REACT_APP_SKETCHMATH_ENABLED = "1";
    stamp.value = 1710000000000;
    jest.spyOn(Date, "now").mockImplementation(() => stamp.value);
    if (!HTMLCanvasElement.prototype.setPointerCapture) {
      HTMLCanvasElement.prototype.setPointerCapture = jest.fn();
    }
    if (!HTMLCanvasElement.prototype.releasePointerCapture) {
      HTMLCanvasElement.prototype.releasePointerCapture = jest.fn();
    }
    if (!HTMLCanvasElement.prototype.hasPointerCapture) {
      HTMLCanvasElement.prototype.hasPointerCapture = jest.fn(() => true);
    }
    jest.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      setTransform: jest.fn(),
      clearRect: jest.fn(),
      fillRect: jest.fn(),
      save: jest.fn(),
      restore: jest.fn(),
      translate: jest.fn(),
      scale: jest.fn(),
      beginPath: jest.fn(),
      moveTo: jest.fn(),
      lineTo: jest.fn(),
      closePath: jest.fn(),
      fill: jest.fn(),
      stroke: jest.fn(),
      fillStyle: "",
      strokeStyle: "",
      lineWidth: 1,
    } as unknown as CanvasRenderingContext2D);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("loads canvas-first and keeps advanced JSON hidden by default", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    expect(screen.getByTestId("sketchmath-workspace")).toBeInTheDocument();
    expect(screen.getByTestId("friday-telemetry-panel")).toBeInTheDocument();
    expect(screen.queryByText("Workspace initialized")).toBeNull();
    expect(screen.queryByText("Raw details")).toBeNull();
    expect(screen.getByTestId("sketchmath-canvas")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Select" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Draw rectangle" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Add hole" })).toBeVisible();
    expect(screen.getAllByRole("button", { name: "Pan / view" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Line" })).toBeVisible();
    expect(screen.getAllByRole("button", { name: "Dimension" }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Parallel" })).toBeNull();
    expect(screen.getByRole("button", { name: "Show Advanced Constraints" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Extrude" })).toBeDisabled();
    expect(screen.getByTestId("sketchmath-view-controls")).toBeInTheDocument();
    expect(screen.getByTestId("sketchmath-plane-widget")).toHaveTextContent("2D sketch plane");
    expect(screen.getByRole("button", { name: "2D sketch" })).toBeVisible();
    expect(screen.getByRole("button", { name: "3D solid" })).toBeVisible();
    expect(screen.queryByText("3D orbit coming soon")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "3D solid" }));
    expect(screen.getByTestId("sketchmath-solid-preview")).toBeInTheDocument();
    expect(screen.getByTestId("sketchmath-solid-preview-status")).toHaveTextContent("Extrude a valid profile to preview the 3D solid.");
    await userEvent.click(screen.getByRole("button", { name: "2D sketch" }));
    expect(screen.queryByTestId("friday-session-map")).toBeNull();
    expect(screen.queryByTestId("sketchmath-command-panel")).toBeNull();
    expect(screen.queryByTestId("sketchmath-command-box")).toBeNull();
  });

  it("draws geometry, selects it, and exposes dimensions and constraints in the normal workspace", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");
    const workbench = screen.getByTestId("sketchmath-workbench-panel");

    await userEvent.click(screen.getByRole("button", { name: "Line" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 380, 120);

    const lineId = `line_${stamp.value.toString(36)}`;
    const startPointId = `point_${stamp.value.toString(36)}_start`;
    const endPointId = `point_${stamp.value.toString(36)}_end`;

    await waitFor(() => expect(screen.getByTestId(`entity-${lineId}`)).toBeVisible());
    await waitFor(() => expect(screen.getByTestId("sketchmath-selection-summary")).toHaveTextContent("Selected: 1 line"));
    expect(within(workbench).getByRole("button", { name: "Horizontal" })).toBeEnabled();
    expect(within(workbench).getByRole("button", { name: "Vertical" })).toBeEnabled();

    await userEvent.click(within(workbench).getByRole("button", { name: "Apply length" }));
    await waitFor(() =>
      expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("distance 17.5 mm"),
    );
    await waitFor(() => expect(within(workbench).getByTestId("sketchmath-status")).toHaveTextContent("Partially analyzed"));

    stamp.value = 1710000001000;
    await userEvent.click(screen.getByRole("button", { name: "Line" }));
    clickCanvasAt(canvas, 160, 220);
    clickCanvasAt(canvas, 380, 220);

    const secondLineId = `line_${stamp.value.toString(36)}`;
    await waitFor(() => expect(screen.getByTestId(`entity-${secondLineId}`)).toBeVisible());
    await waitFor(() => expect(within(workbench).getByRole("button", { name: "Extrude" })).toBeDisabled());
    await userEvent.click(within(workbench).getByRole("button", { name: "Parallel" }));

    await waitFor(() =>
      expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Parallel"),
    );
    expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("distance 17.5 mm");
    expect(screen.getByTestId("sketchmath-workbench-panel")).not.toHaveTextContent("parallel_constraint");

    await userEvent.click(screen.getByRole("button", { name: "Select" }));
    clickCanvasAt(canvas, 620, 520);
    await waitFor(() => expect(screen.getByTestId("sketchmath-selection-summary")).toHaveTextContent("Nothing selected."));
  });

  it.each([
    ["Fully constrained", { coverage: "exact", freedom_state: "fully_constrained", consistency_state: "consistent", redundancy_state: "none", remaining_dof: 0 }],
    ["Over-constrained", { coverage: "exact", freedom_state: "fully_constrained", consistency_state: "consistent", redundancy_state: "redundant", remaining_dof: 0, redundant_constraint_ids: ["constraint_redundant"] }],
    ["Conflicting", { coverage: "exact", freedom_state: "unknown", consistency_state: "inconsistent", redundancy_state: "none", remaining_dof: null, conflicting_constraint_ids: ["constraint_conflict"] }],
  ])("shows the live %s solver state in Normal mode", async (expectedStatus, solverAnalysis) => {
    const { fetchMock } = createSketchmathMock({ solverAnalysis });
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");
    await userEvent.click(screen.getByRole("button", { name: "Line" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 380, 120);

    await waitFor(() => expect(screen.getByTestId("sketchmath-status")).toHaveTextContent(expectedStatus));
    expect(screen.queryByText(/Independent equations:/)).toBeNull();
  });

  it("keeps solver internals Advanced-only while explaining partial coverage normally", async () => {
    const { fetchMock } = createSketchmathMock({
      solverAnalysis: {
        coverage: "partial",
        freedom_state: "unknown",
        consistency_state: "unknown",
        redundancy_state: "unknown",
        remaining_dof: null,
        unsupported_constraint_ids: ["constraint_distance"],
        diagnostics: ["Nonlinear constraints prevent exact classification."],
      },
    });
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");
    await userEvent.click(screen.getByRole("button", { name: "Line" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 380, 120);

    await waitFor(() => expect(screen.getByTestId("sketchmath-status")).toHaveTextContent("Partially analyzed"));
    expect(screen.getByTestId("sketchmath-solver-status-detail")).toHaveTextContent("outside exact solver coverage");
    expect(screen.queryByText(/Independent equations:/)).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: /Show Advanced \/ Debug/ }));
    expect(await screen.findByTestId("sketchmath-solver-analysis-debug")).toHaveTextContent("Independent equations:");
    expect(screen.getByTestId("sketchmath-solver-analysis-debug")).toHaveTextContent("constraint_distance");
    expect(screen.getByTestId("sketchmath-solver-analysis-debug")).toHaveTextContent("Nonlinear constraints prevent exact classification.");
  });

  it("creates driving horizontal and vertical distance constraints from Normal mode", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");
    await userEvent.click(screen.getByRole("button", { name: "Line" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 380, 200);

    await waitFor(() => expect(screen.getByTestId("sketchmath-selection-summary")).toHaveTextContent("Selected: 1 line"));
    fireEvent.change(screen.getByLabelText("SketchMath length"), { target: { value: "30" } });
    await userEvent.click(screen.getByRole("button", { name: "Set horizontal distance" }));
    await waitFor(() => expect(screen.getByTestId("sketchmath-selected-constraints")).toHaveTextContent("Horizontal distance • distance 30 mm"));
    expect(screen.getByTestId("sketchmath-status")).toHaveTextContent("Under-constrained");

    await userEvent.click(screen.getByRole("button", { name: "Set vertical distance" }));
    await waitFor(() => expect(screen.getByTestId("sketchmath-selected-constraints")).toHaveTextContent("Vertical distance • distance 30 mm"));
  });

  it("creates a parametric rectangle from two clicks and keeps the workbench CAD-ready", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");
    const workbench = screen.getByTestId("sketchmath-workbench-panel");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    await waitFor(() => expect(screen.getByTestId("sketchmath-selection-summary")).toHaveTextContent("Selected: Profile"));
    expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Rectangle 240 mm x 100 mm");
    expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Closed profile: valid");
    expect(within(workbench).getByRole("button", { name: "Extrude" })).toBeEnabled();
  });

  it("exposes rectangle dimensions that drive grouped rectangle geometry", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");
    const workbench = screen.getByTestId("sketchmath-workbench-panel");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    const baseId = `rect_${firstStamp.toString(36)}`;
    const topEdge = await screen.findByTestId(`entity-${baseId}_ab`);
    await waitFor(() => expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Rectangle dimensions"));
    expect(screen.getByLabelText("Rectangle width")).toHaveValue(240);
    expect(screen.getByLabelText("Rectangle height")).toHaveValue(100);
    expect(screen.getByTestId(`dimension-${baseId}-width`)).toHaveTextContent("240 mm");
    expect(screen.getByTestId(`dimension-${baseId}-height`)).toHaveTextContent("100 mm");
    expect(screen.getByTestId(`dimension-guide-${baseId}-width`)).toBeVisible();
    expect(screen.getByTestId(`dimension-guide-${baseId}-height`)).toBeVisible();
    await waitFor(() => expect(within(workbench).getByTestId("sketchmath-status")).toHaveTextContent("Partially analyzed"));
    expect(screen.getByTestId(`rectangle-selection-outline-${baseId}`)).toBeVisible();

    fireEvent.change(screen.getByLabelText("Rectangle width"), { target: { value: "40" } });
    fireEvent.change(screen.getByLabelText("Rectangle height"), { target: { value: "25" } });
    await userEvent.click(within(screen.getByTestId("sketchmath-workbench-panel")).getByRole("button", { name: "Apply Rectangle Dimensions" }));

    await waitFor(() => expect(screen.getByTestId(`dimension-${baseId}-width`)).toHaveTextContent("40 mm"));
    await waitFor(() => expect(screen.getByTestId(`dimension-${baseId}-height`)).toHaveTextContent("25 mm"));
    expect(screen.queryByTestId("sketchmath-preview-controls")).toBeNull();
    await waitFor(() => expect(screen.getByLabelText("Rectangle width")).toHaveValue(40));
    await waitFor(() => expect(screen.getByLabelText("Rectangle height")).toHaveValue(25));
    expect(topEdge.querySelector("line")).toHaveAttribute("x1", "160");
    expect(topEdge.querySelector("line")).toHaveAttribute("x2", "200");

    await userEvent.click(screen.getAllByRole("button", { name: "Dimension" })[0]);
    await userEvent.click(topEdge);
    await waitFor(() => expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Selected: Rectangle width edge"));
    expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Parent: Rectangle");
    expect(screen.getByLabelText("Width dimension value")).toHaveValue(40);
    expect(topEdge.querySelector("line.sketchmath-line")).toHaveClass("sketchmath-line-focus");
  });

  it("shows CAD-style dimension guides only for the selected rectangle", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    stamp.value = 1710000001000;
    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 500, 180);
    clickCanvasAt(canvas, 620, 260);

    const firstBaseId = `rect_${firstStamp.toString(36)}`;
    const secondBaseId = `rect_${stamp.value.toString(36)}`;

    await waitFor(() => expect(screen.getByTestId(`dimension-${secondBaseId}-width`)).toHaveTextContent("120 mm"));
    expect(screen.getByTestId(`dimension-guide-${secondBaseId}-width`)).toBeVisible();
    expect(screen.getByTestId(`dimension-guide-${secondBaseId}-height`)).toBeVisible();
    expect(screen.queryByTestId(`dimension-${firstBaseId}-width`)).toBeNull();
    expect(screen.queryByTestId(`dimension-guide-${firstBaseId}-width`)).toBeNull();

    await userEvent.click(await screen.findByTestId(`entity-${firstBaseId}_ab`));

    await waitFor(() => expect(screen.getByTestId(`dimension-${firstBaseId}-width`)).toHaveTextContent("240 mm"));
    expect(screen.getByTestId(`dimension-guide-${firstBaseId}-width`)).toBeVisible();
    expect(screen.getByTestId(`dimension-guide-${firstBaseId}-height`)).toBeVisible();
    expect(screen.queryByTestId(`dimension-${secondBaseId}-width`)).toBeNull();
    expect(screen.queryByTestId(`dimension-guide-${secondBaseId}-width`)).toBeNull();
  });

  it("opens edge-specific rectangle dimension editors from direct label clicks", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    const baseId = `rect_${firstStamp.toString(36)}`;
    const rightEdge = await screen.findByTestId(`entity-${baseId}_bc`);
    const widthLabel = await screen.findByTestId(`dimension-${baseId}-width`);
    await userEvent.click(widthLabel);

    await screen.findByRole("heading", { name: "Edit width dimension" });
    fireEvent.change(screen.getByLabelText("Width dimension value"), { target: { value: "40" } });
    await userEvent.click(screen.getByRole("button", { name: "Apply dimension" }));
    const commitCall = await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url, init]) => String(url).includes("/commands/commit") && String(init?.body || "").includes("set_rectangle_dimension"));
      expect(call).toBeTruthy();
      return call;
    });
    const commitBody = JSON.parse(String(commitCall?.[1]?.body || "{}"));
    expect(commitBody.command).toMatchObject({
      mode: "commit",
      command_type: "set_rectangle_dimension",
      selection: [
        `${baseId}_a`,
        `${baseId}_b`,
        `${baseId}_c`,
        `${baseId}_d`,
        `${baseId}_ab`,
        `${baseId}_bc`,
        `${baseId}_cd`,
        `${baseId}_da`,
        `profile_${baseId}`,
      ],
      parameters: { dimension: "width", value: 40, unit: "mm" },
    });
    await waitFor(() => expect(screen.getByTestId(`dimension-${baseId}-width`)).toHaveTextContent("40 mm"));
    expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Selected: Rectangle width edge");
    expect(screen.queryByTestId("sketchmath-preview-controls")).toBeNull();
    await waitFor(() =>
      expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Partially analyzed"),
    );

    await userEvent.click(screen.getByTestId(`dimension-${baseId}-height`));
    await screen.findByRole("heading", { name: "Edit height dimension" });
    fireEvent.change(screen.getByLabelText("Height dimension value"), { target: { value: "25" } });
    await userEvent.click(screen.getByRole("button", { name: "Apply dimension" }));
    await waitFor(() => expect(screen.getByTestId(`dimension-${baseId}-height`)).toHaveTextContent("25 mm"));

    await userEvent.click(screen.getAllByRole("button", { name: "Dimension" })[0]);
    await userEvent.click(rightEdge);
    await waitFor(() => expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Selected: Rectangle height edge"));
    expect(screen.getByLabelText("Height dimension value")).toHaveValue(25);
  });

  it("exposes Add Hole on selected rectangles and commits a typed centered hole command", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    const baseId = `rect_${firstStamp.toString(36)}`;
    await waitFor(() => expect(screen.getByRole("button", { name: "Add Hole" })).toBeEnabled());
    expect(screen.getByLabelText("Hole diameter")).toHaveValue(8);
    fireEvent.change(screen.getByLabelText("Hole diameter"), { target: { value: "12" } });
    await userEvent.click(screen.getByRole("button", { name: "Add Hole" }));
    await screen.findByTestId("sketchmath-hole-placement");
    await userEvent.click(screen.getByRole("button", { name: "Add Centered Hole" }));

    const commitCall = await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url, init]) => String(url).includes("/commands/commit") && String(init?.body || "").includes("add_profile_hole"));
      expect(call).toBeTruthy();
      return call;
    });
    const commitBody = JSON.parse(String(commitCall?.[1]?.body || "{}"));
    expect(commitBody.command).toMatchObject({
      mode: "commit",
      command_type: "add_profile_hole",
      selection: [`profile_${baseId}`],
      parameters: { diameter: 12, unit: "mm", center: [280, 170] },
    });
    await waitFor(() => expect(screen.getByTestId(/^entity-hole_/)).toBeVisible());
    expect(screen.queryByTestId("sketchmath-preview-controls")).toBeNull();
  });

  it("commits Add Hole previews into visible profile holes", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    await waitFor(() => expect(screen.getByRole("button", { name: "Add Hole" })).toBeEnabled());
    fireEvent.change(screen.getByLabelText("Hole diameter"), { target: { value: "12" } });
    await userEvent.click(screen.getByRole("button", { name: "Add Hole" }));
    await screen.findByTestId("sketchmath-hole-placement");
    await userEvent.click(screen.getByRole("button", { name: "Add Centered Hole" }));

    await waitFor(() => expect(screen.getByTestId(/^entity-hole_/)).toBeVisible());
    expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Profile holes: 1");
  });

  it("selects an existing hole, labels its diameter, and edits it after placement", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    await waitFor(() => expect(screen.getByRole("button", { name: "Add Hole" })).toBeEnabled());
    fireEvent.change(screen.getByLabelText("Hole diameter"), { target: { value: "12" } });
    await userEvent.click(screen.getByRole("button", { name: "Add Hole" }));
    await screen.findByTestId("sketchmath-hole-placement");
    await userEvent.click(screen.getByRole("button", { name: "Add Centered Hole" }));

    const hole = await screen.findByTestId(/^entity-hole_/);
    await userEvent.click(hole);

    const holeId = hole.getAttribute("data-entity-id") || "";
    await waitFor(() => expect(screen.getByTestId("selected-hole-editor")).toHaveTextContent("Selected hole"));
    expect(screen.getByTestId(`dimension-${holeId}-diameter`)).toHaveTextContent("Dia 12 mm");
    expect(screen.getByLabelText("Selected hole diameter")).toHaveValue(12);

    fireEvent.change(screen.getByLabelText("Selected hole diameter"), { target: { value: "8" } });
    await userEvent.click(screen.getByRole("button", { name: "Apply hole update" }));

    const updateCall = await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url, init]) => String(url).includes("/commands/commit") && String(init?.body || "").includes("update_profile_hole"));
      expect(call).toBeTruthy();
      return call;
    });
    const updateBody = JSON.parse(String(updateCall?.[1]?.body || "{}"));
    expect(updateBody.command).toMatchObject({
      mode: "commit",
      command_type: "update_profile_hole",
      selection: expect.arrayContaining([holeId]),
      parameters: { diameter: 8, unit: "mm", center: [280, 170] },
    });
    await waitFor(() => expect(screen.getByTestId(`dimension-${holeId}-diameter`)).toHaveTextContent("Dia 8 mm"));
    expect(screen.getByTestId("selected-hole-editor-message")).toHaveTextContent("Hole updated.");
  });

  it("enters Add Hole placement mode and previews the clicked center", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    const baseId = `rect_${firstStamp.toString(36)}`;
    await waitFor(() => expect(screen.getByRole("button", { name: "Add Hole" })).toBeEnabled());
    fireEvent.change(screen.getByLabelText("Hole diameter"), { target: { value: "10" } });
    await userEvent.click(screen.getByRole("button", { name: "Add Hole" }));

    expect(await screen.findByTestId("sketchmath-hole-placement")).toHaveTextContent("Click inside selected profile");
    clickCanvasAt(canvas, 250, 160);

    const commitCall = await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url, init]) => String(url).includes("/commands/commit") && String(init?.body || "").includes("add_profile_hole"));
      expect(call).toBeTruthy();
      return call;
    });
    const commitBody = JSON.parse(String(commitCall?.[1]?.body || "{}"));
    expect(commitBody.command).toMatchObject({
      command_type: "add_profile_hole",
      selection: [`profile_${baseId}`],
      parameters: { diameter: 10, unit: "mm", center: [250, 160] },
    });
    await waitFor(() => expect(screen.getByTestId(/^entity-hole_/)).toBeVisible());
  });

  it("handles outside Add Hole placement clicks without previewing", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    await waitFor(() => expect(screen.getByRole("button", { name: "Add Hole" })).toBeEnabled());
    await userEvent.click(screen.getByRole("button", { name: "Add Hole" }));
    clickCanvasAt(canvas, 800, 500);

    await waitFor(() => expect(screen.getByTestId("sketchmath-hole-placement")).toHaveTextContent("inside the selected profile"));
    const commitCalls = fetchMock.mock.calls.filter(([url, init]) => String(url).includes("/commands/commit") && String(init?.body || "").includes("add_profile_hole"));
    expect(commitCalls).toHaveLength(0);
  });

  it("normalizes backend dependency errors and keeps raw details advanced-only", async () => {
    const { fetchMock } = createSketchmathMock({ failAddProfileHoleDependency: true });
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    await waitFor(() => expect(screen.getByRole("button", { name: "Add Hole" })).toBeEnabled());
    await userEvent.click(screen.getByRole("button", { name: "Add Hole" }));
    await screen.findByTestId("sketchmath-hole-placement");
    await userEvent.click(screen.getByRole("button", { name: "Add Centered Hole" }));

    await waitFor(() =>
      expect(screen.getByTestId("sketchmath-user-error")).toHaveTextContent("Geometry validation dependency is unavailable"),
    );
    expect(screen.getByTestId("sketchmath-user-error")).not.toHaveTextContent("HTTP 422");
    expect(screen.getByTestId("sketchmath-user-error")).not.toHaveTextContent("shapely is required");
    expect(screen.queryByTestId("sketchmath-error-details")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: /Show Advanced \/ Debug/ }));
    expect(screen.getByTestId("sketchmath-error-details")).toHaveTextContent("shapely is required for SketchMath hole validation");
  });

  it("selects rectangle corners as editable anchor targets", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    const baseId = `rect_${firstStamp.toString(36)}`;
    await userEvent.click(screen.getAllByRole("button", { name: "Dimension" })[0]);
    await userEvent.click(await screen.findByTestId(`entity-${baseId}_a`));

    await waitFor(() => expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Selected: Rectangle corner"));
    expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Angle: 90");
    expect(screen.getByRole("button", { name: "Fix corner" })).toBeEnabled();
  });

  it("anchors a rectangle corner without overstating partial solver coverage", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");
    const workbench = screen.getByTestId("sketchmath-workbench-panel");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    await waitFor(() => expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Position free"));
    await userEvent.click(screen.getByRole("button", { name: "Fix corner" }));

    await waitFor(() =>
      expect(within(workbench).getByTestId("sketchmath-status")).toHaveTextContent("Partially analyzed"),
    );
    expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Anchored at corner A");
  });

  it("previews extrusion for a selected profile with holes and exposes commit/export affordances", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");
    const workbench = screen.getByTestId("sketchmath-workbench-panel");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    const baseId = `rect_${firstStamp.toString(36)}`;
    await waitFor(() => expect(within(workbench).getByRole("button", { name: "Extrude" })).toBeEnabled());
    expect(screen.queryByTestId("sketchmath-command-panel")).toBeNull();
    expect(screen.getByLabelText("Extrusion depth")).toHaveValue(10);

    fireEvent.change(screen.getByLabelText("Hole diameter"), { target: { value: "12" } });
    await userEvent.click(screen.getByRole("button", { name: "Add Hole" }));
    await screen.findByTestId("sketchmath-hole-placement");
    await userEvent.click(screen.getByRole("button", { name: "Add Centered Hole" }));
    await waitFor(() => expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Profile holes: 1"));

    await userEvent.click(within(workbench).getByRole("button", { name: "Extrude" }));

    await waitFor(() => expect(screen.getByTestId("sketchmath-preview-controls")).toBeVisible());
    const previewCall = fetchMock.mock.calls.find(([url, init]) => String(url).includes("/commands/preview") && String(init?.body || "").includes("extrude_profile"));
    expect(previewCall).toBeTruthy();
    const previewBody = JSON.parse(String(previewCall?.[1]?.body || "{}"));
    expect(previewBody.command).toMatchObject({
      mode: "preview",
      command_type: "extrude_profile",
      selection: [`profile_${baseId}`],
      parameters: {
        depth: 10,
        depth_unit: "mm",
        direction: "positive_normal",
        output_format: "step",
      },
    });
    await waitFor(() => expect(workbench).toHaveTextContent("Extrude preview ready: profile accepted with 1 hole"));
    expect(screen.getByTestId("sketchmath-plane-widget")).toHaveTextContent("3D solid preview");
    expect(screen.getByTestId("sketchmath-solid-preview")).toBeVisible();
    expect(screen.getByTestId("sketchmath-solid-preview-status")).toHaveTextContent("10 mm extrusion with 1 through-hole");
    expect(screen.getByRole("button", { name: "Iso" })).toBeEnabled();
    expect(screen.queryByText("3D orbit coming soon")).toBeNull();

    const cameraHud = screen.getByTestId("sketchmath-solid-camera-hud");
    const azimuth = screen.getByTestId("sketchmath-camera-azimuth");
    const elevation = screen.getByTestId("sketchmath-camera-elevation");
    const zoom = screen.getByTestId("sketchmath-camera-zoom");
    const pan = screen.getByTestId("sketchmath-camera-pan");
    const target = screen.getByTestId("sketchmath-camera-target");
    const solidCanvas = screen.getByTestId("sketchmath-solid-preview-canvas");
    expect(cameraHud).toHaveTextContent("3D solid");
    expect(azimuth).toHaveTextContent("0 deg");
    expect(elevation).toHaveTextContent("-90 deg");
    expect(zoom).toHaveTextContent("1x");
    expect(pan).toHaveTextContent("0, 0");
    expect(target).toHaveTextContent("280, 170");

    await userEvent.click(screen.getByRole("button", { name: "Tilt to 3D" }));
    expect(elevation).toHaveTextContent("-35 deg");
    expect(target).toHaveTextContent("280, 170");

    const initialAzimuth = azimuth.textContent;
    const initialElevation = elevation.textContent;
    pointerCanvasAt(solidCanvas, "pointerdown", { clientX: 220, clientY: 180, pointerId: 1, button: 0, buttons: 1 });
    pointerCanvasAt(solidCanvas, "pointermove", { clientX: 270, clientY: 210, pointerId: 1, buttons: 1 });
    pointerCanvasAt(solidCanvas, "pointerup", { clientX: 270, clientY: 210, pointerId: 1, button: 0 });
    expect(azimuth.textContent).not.toEqual(initialAzimuth);
    expect(elevation.textContent).not.toEqual(initialElevation);

    const zoomBeforeWheel = zoom.textContent;
    fireEvent.wheel(solidCanvas, { deltaY: -100 });
    expect(zoom.textContent).not.toEqual(zoomBeforeWheel);

    const panBeforeDrag = pan.textContent;
    pointerCanvasAt(solidCanvas, "pointerdown", { clientX: 270, clientY: 210, pointerId: 2, button: 1, buttons: 4 });
    pointerCanvasAt(solidCanvas, "pointermove", { clientX: 300, clientY: 235, pointerId: 2, buttons: 4 });
    pointerCanvasAt(solidCanvas, "pointerup", { clientX: 300, clientY: 235, pointerId: 2, button: 1 });
    await waitFor(() => expect(pan.textContent).not.toEqual(panBeforeDrag));

    await userEvent.click(screen.getByRole("button", { name: "Fit" }));
    expect(zoom).toHaveTextContent("1x");
    expect(pan).toHaveTextContent("0, 0");
    expect(target).toHaveTextContent("280, 170");

    await userEvent.click(screen.getByRole("button", { name: "Top" }));
    expect(elevation).toHaveTextContent("-90 deg");
    await userEvent.click(screen.getByRole("button", { name: "Front" }));
    expect(azimuth).toHaveTextContent("0 deg");
    expect(elevation).toHaveTextContent("0 deg");
    await userEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(azimuth).toHaveTextContent("0 deg");
    expect(elevation).toHaveTextContent("-90 deg");
    expect(zoom).toHaveTextContent("1x");
    expect(pan).toHaveTextContent("0, 0");
    await userEvent.click(screen.getByRole("button", { name: "Iso" }));
    expect(azimuth).toHaveTextContent("-41 deg");
    expect(elevation).toHaveTextContent("-31 deg");
    expect(target).toHaveTextContent("280, 170");

    await userEvent.click(screen.getByRole("button", { name: "2D sketch" }));
    expect(screen.getByTestId("sketchmath-plane-widget")).toHaveTextContent("2D sketch plane");
    await userEvent.click(screen.getByRole("button", { name: "3D solid" }));
    expect(screen.getByTestId("sketchmath-plane-widget")).toHaveTextContent("3D solid preview");
    expect(screen.getByTestId("sketchmath-camera-azimuth")).toHaveTextContent("0 deg");
    expect(screen.getByTestId("sketchmath-camera-elevation")).toHaveTextContent("-90 deg");
    expect(screen.getByTestId("sketchmath-camera-target")).toHaveTextContent("280, 170");
    expect(screen.queryByTestId("sketchmath-command-panel")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Commit Preview" }));
    await waitFor(() => expect(workbench).toHaveTextContent("STEP export ready"));
    expect(screen.getByRole("link", { name: "Download STEP" })).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: /Show Advanced \/ Debug/ }));
    expect(screen.getByTestId("sketchmath-command-panel")).toBeVisible();
    expect(screen.getByTestId("sketchmath-command-panel")).toHaveTextContent("extrude_profile");
  });

  it("routes vertical rectangle edge edits through the parent rectangle without creating loose geometry", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    const baseId = `rect_${firstStamp.toString(36)}`;
    const rightEdge = await screen.findByTestId(`entity-${baseId}_bc`);

    fireEvent.change(screen.getByLabelText("Rectangle width"), { target: { value: "40" } });
    await userEvent.click(within(screen.getByTestId("sketchmath-workbench-panel")).getByRole("button", { name: "Apply Rectangle Dimensions" }));
    await waitFor(() => expect(screen.getByTestId(`dimension-${baseId}-width`)).toHaveTextContent("40 mm"));

    await userEvent.click(screen.getAllByRole("button", { name: "Dimension" })[0]);
    await userEvent.click(rightEdge);
    await waitFor(() => expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Selected: Rectangle height edge"));
    fireEvent.change(screen.getByLabelText("Height dimension value"), { target: { value: "25" } });
    await userEvent.click(screen.getByRole("button", { name: "Apply dimension" }));

    await waitFor(() => expect(screen.getByTestId(`dimension-${baseId}-height`)).toHaveTextContent("25 mm"));
    expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Closed profile: valid");
    expect(screen.getAllByTestId(/^entity-rect_.*_[abcd]$/).length).toBe(4);
    expect(screen.getAllByTestId(/^entity-rect_.*_(ab|bc|cd|da)$/).length).toBe(4);
  });

  it("does not expose raw backend reference errors when deleting a referenced rectangle edge", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    const baseId = `rect_${firstStamp.toString(36)}`;
    await userEvent.click(screen.getAllByRole("button", { name: "Dimension" })[0]);
    await userEvent.click(await screen.findByTestId(`entity-${baseId}_ab`));
    fireEvent.keyDown(window, { key: "Delete" });

    await waitFor(() => expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("This edge belongs to a rectangle"));
    expect(screen.getByRole("button", { name: "Delete whole rectangle" })).toBeEnabled();
    expect(screen.queryByText(/Cannot delete an entity that is still referenced/)).toBeNull();
  });

  it("summarizes rectangle edge roles and enables contextual width and height actions", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    const baseId = `rect_${firstStamp.toString(36)}`;
    await userEvent.click(screen.getAllByRole("button", { name: "Dimension" })[0]);
    await userEvent.click(await screen.findByTestId(`entity-${baseId}_ab`));

    await waitFor(() => expect(screen.getByTestId("sketchmath-selection-summary")).toHaveTextContent("Selected: Rectangle width edge"));
    expect(screen.getByTestId("sketchmath-selection-summary")).toHaveTextContent("Parent: Rectangle");
    expect(screen.getByRole("button", { name: "Apply Rectangle Dimensions" })).toBeEnabled();

    await userEvent.click(await screen.findByTestId(`entity-${baseId}_bc`));

    await waitFor(() => expect(screen.getByTestId("sketchmath-selection-summary")).toHaveTextContent("Selected: Rectangle height edge"));
    expect(screen.getByRole("button", { name: "Apply Rectangle Dimensions" })).toBeEnabled();
  });

  it("shift-click toggles rectangle edges into a contextual two-line selection", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    const baseId = `rect_${firstStamp.toString(36)}`;
    fireEvent.click(await screen.findByTestId(`entity-${baseId}_ab`), { shiftKey: true });
    fireEvent.click(await screen.findByTestId(`entity-${baseId}_cd`), { shiftKey: true });

    await waitFor(() => expect(screen.getByTestId("sketchmath-selection-summary")).toHaveTextContent("Selected: 2 lines"));
    expect(screen.getByRole("button", { name: "Parallel" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Perpendicular" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Equal Length" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Set Angle" })).toBeNull();

    fireEvent.click(await screen.findByTestId(`entity-${baseId}_cd`), { shiftKey: true });

    await waitFor(() => expect(screen.getByTestId("sketchmath-selection-summary")).toHaveTextContent("Selected: Rectangle width edge"));
  });

  it("rectangle corner selection exposes fix and angle context without raw IDs as the main summary", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    const baseId = `rect_${firstStamp.toString(36)}`;
    await userEvent.click(screen.getAllByRole("button", { name: "Dimension" })[0]);
    await userEvent.click(await screen.findByTestId(`entity-${baseId}_a`));

    await waitFor(() => expect(screen.getByTestId("sketchmath-selection-summary")).toHaveTextContent("Selected: Rectangle corner A"));
    expect(screen.getByTestId("sketchmath-selection-summary")).toHaveTextContent("Angle: 90");
    expect(screen.getByRole("button", { name: "Fix corner" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Set Angle" })).toBeNull();
  });

  it("deletes a selected rectangle as one dependency-safe object", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");
    const workbench = screen.getByTestId("sketchmath-workbench-panel");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    await waitFor(() => expect(within(workbench).getByRole("button", { name: "Extrude" })).toBeEnabled());
    await userEvent.click(within(screen.getByTestId("sketchmath-workbench-panel")).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(screen.queryByTestId(/^entity-rect_/)).toBeNull());
    expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Nothing selected.");
    expect(within(workbench).getByRole("button", { name: "Extrude" })).toBeDisabled();
    expect(within(workbench).getByTestId("sketchmath-status")).toHaveTextContent("No constraints");
  });

  it("clears the sketch and removes stale geometry from the normal UI", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");

    await userEvent.click(screen.getByRole("button", { name: "Line" }));
    clickCanvasAt(canvas, 160, 120);
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByTestId(/^entity-point_.*_start$/)).toBeNull();
    expect(screen.getByRole("button", { name: "Select" })).toHaveAttribute("aria-pressed", "true");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);
    await waitFor(() => expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Rectangle"));

    await userEvent.click(screen.getByRole("button", { name: "Clear sketch" }));

    await waitFor(() => expect(screen.queryByTestId(/^entity-rect_/)).toBeNull());
    expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Nothing selected.");
    expect(screen.getByRole("button", { name: "Extrude" })).toBeDisabled();
  });

  it("rolls back line endpoint points when line creation fails", async () => {
    const { fetchMock } = createSketchmathMock({ failDefineLine: true });
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");

    await userEvent.click(screen.getByRole("button", { name: "Line" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 380, 120);

    await waitFor(() => expect(screen.queryByTestId(/^entity-point_.*_start$/)).toBeNull());
    expect(screen.queryByTestId(/^entity-point_.*_end$/)).toBeNull();
    expect(screen.queryByTestId(/^entity-line_/)).toBeNull();
    expect(screen.getByTestId("sketchmath-workbench-panel")).toHaveTextContent("Nothing selected.");
    expect(screen.queryByText(/HTTP 500|selection_resolution_error/)).toBeNull();
  });

  it("does not show contradictory CAD helper text when a closed profile is valid", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");
    const workbench = screen.getByTestId("sketchmath-workbench-panel");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    await waitFor(() => expect(within(workbench).getByRole("button", { name: "Extrude" })).toBeEnabled());
    expect(workbench).toHaveTextContent("Closed profile: valid");
    expect(workbench).toHaveTextContent("Ready for CAD feature");
    expect(workbench).not.toHaveTextContent("Requires a closed sketch profile before extrusion.");
  });

  it("reveals advanced command JSON only when requested", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    expect(screen.queryByTestId("sketchmath-command-panel")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /Show Advanced \/ Debug/ }));
    expect(screen.getByTestId("sketchmath-command-panel")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: /Show Advanced \/ Debug DSL/ }));
    expect(screen.getByTestId("sketchmath-command-box")).toBeVisible();
  });

  it("enables CAD feature creation only once a closed profile exists", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const convertButton = within(screen.getByTestId("sketchmath-workbench-panel")).getByRole("button", { name: "Extrude" });

    expect(convertButton).toBeDisabled();

    const canvas = screen.getByTestId("sketchmath-canvas");
    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 120, 120);
    clickCanvasAt(canvas, 320, 240);

    await waitFor(() =>
      expect(within(screen.getByTestId("sketchmath-workbench-panel")).getByRole("button", { name: "Extrude" })).toBeEnabled(),
    );
  });

  it("enables circles while keeping arcs explicitly deferred", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");

    expect(screen.getByRole("button", { name: "Circle" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Arc" })).toBeNull();
    expect(screen.getByText("Arc: coming soon")).toBeVisible();
  });

  it("draws and edits a selectable circle backed by an extrusion profile", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");
    await userEvent.click(screen.getByRole("button", { name: "Circle" }));
    clickCanvasAt(canvas, 300, 220);
    expect(screen.getByTestId("sketchmath-circle-draft")).toBeVisible();
    clickCanvasAt(canvas, 340, 220);

    const circleId = `circle_${stamp.value.toString(36)}`;
    await waitFor(() => expect(screen.getByTestId(`entity-${circleId}`)).toBeVisible());
    expect(screen.getByTestId("sketchmath-circle-editor")).toBeVisible();
    expect(screen.getByRole("button", { name: "Extrude" })).toBeEnabled();
    fireEvent.change(screen.getByLabelText("Circle radius"), { target: { value: "25" } });
    await userEvent.click(screen.getByRole("button", { name: "Apply radius" }));
    await waitFor(() => expect(screen.getByLabelText("Circle radius")).toHaveValue(25));
    expect(screen.getByTestId("sketchmath-selected-constraints")).toHaveTextContent("Radius • radius 25 mm");

    await userEvent.clear(screen.getByLabelText("Circle diameter"));
    await userEvent.type(screen.getByLabelText("Circle diameter"), "30");
    expect(screen.getByLabelText("Circle diameter")).toHaveValue(30);
    await userEvent.click(screen.getByRole("button", { name: "Apply diameter" }));
    await waitFor(() => expect(screen.getByTestId("sketchmath-selected-constraints")).toHaveTextContent("Diameter • diameter 30 mm"));
    await waitFor(() => expect(screen.getByLabelText("Circle radius")).toHaveValue(15));
    expect(screen.getByLabelText("Circle diameter")).toHaveValue(30);
  });

  it("shows a productized STEP export card with browser download href after extrusion commit", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");
    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    await waitFor(() => expect(screen.getByRole("button", { name: "Extrude" })).toBeEnabled());
    await userEvent.click(screen.getByRole("button", { name: "Extrude" }));
    await waitFor(() => expect(screen.getByTestId("sketchmath-cad-feature-summary")).toHaveTextContent("Extrude preview ready"));
    await userEvent.click(screen.getByRole("button", { name: "Commit Preview" }));

    await waitFor(() => expect(screen.getByTestId("sketchmath-export-card")).toBeVisible());
    expect(screen.getByTestId("sketchmath-export-card")).toHaveTextContent("Export succeeded");
    expect(screen.getByTestId("sketchmath-export-card")).toHaveTextContent("export.step");
    expect(screen.getByTestId("sketchmath-export-card")).toHaveTextContent("Download is served through FRIDAY");
    expect(screen.getByTestId("sketchmath-export-metadata")).toHaveTextContent("2048 bytes");
    expect(screen.getByTestId("sketchmath-export-metadata")).toHaveTextContent("10 mm");
    expect(screen.getByTestId("sketchmath-export-card")).toHaveTextContent("The 3D solid preview uses the same profile, holes, and extrusion depth.");
    expect(screen.getByRole("link", { name: "Download STEP" })).toHaveAttribute(
      "href",
      expect.stringMatching(/^\/api\/sketchmath\/artifacts\/step\?path=%2Ftmp%2Fsketchmath%2Fextrude_profile_.+%2Fexport\.step$/),
    );
    await userEvent.click(screen.getByRole("button", { name: "Clear export result" }));
    expect(screen.queryByTestId("sketchmath-export-card")).toBeNull();
  });

  it("completes the core browser workflow from rectangle to holed STEP download without JSON", async () => {
    const { fetchMock } = createSketchmathMock();
    global.fetch = fetchMock as unknown as typeof fetch;
    renderWorkspace();

    await screen.findByText("SketchMath");
    const canvas = screen.getByTestId("sketchmath-canvas");
    const inspector = screen.getByTestId("sketchmath-workbench-panel");
    const workbench = screen.getByTestId("sketchmath-workbench-panel");

    await userEvent.click(screen.getByRole("button", { name: "Draw rectangle" }));
    clickCanvasAt(canvas, 160, 120);
    clickCanvasAt(canvas, 400, 220);

    const baseId = `rect_${firstStamp.toString(36)}`;
    await waitFor(() => expect(inspector).toHaveTextContent("Rectangle dimensions"));

    fireEvent.change(screen.getByLabelText("Rectangle width"), { target: { value: "40" } });
    fireEvent.change(screen.getByLabelText("Rectangle height"), { target: { value: "25" } });
    await userEvent.click(within(screen.getByTestId("sketchmath-workbench-panel")).getByRole("button", { name: "Apply Rectangle Dimensions" }));

    await waitFor(() => expect(screen.getByTestId(`dimension-${baseId}-width`)).toHaveTextContent("40 mm"));
    await waitFor(() => expect(screen.getByTestId(`dimension-${baseId}-height`)).toHaveTextContent("25 mm"));
    expect(screen.queryByTestId("sketchmath-command-panel")).toBeNull();

    fireEvent.change(screen.getByLabelText("Hole diameter"), { target: { value: "6" } });
    await userEvent.click(screen.getByRole("button", { name: "Add Hole" }));
    await waitFor(() => expect(screen.getByTestId("sketchmath-hole-placement")).toHaveTextContent("Click inside selected profile"));
    clickCanvasAt(canvas, 180, 132);

    const hole = await screen.findByTestId(/^entity-hole_/);
    await waitFor(() => expect(inspector).toHaveTextContent("Profile holes: 1"));
    await userEvent.click(hole);
    fireEvent.change(screen.getByLabelText("Selected hole diameter"), { target: { value: "8" } });
    await userEvent.click(screen.getByRole("button", { name: "Apply hole update" }));
    await waitFor(() => expect(screen.getByTestId("selected-hole-editor-message")).toHaveTextContent("Hole updated."));

    fireEvent.change(screen.getByLabelText("Extrusion depth"), { target: { value: "15" } });
    await userEvent.click(within(workbench).getByRole("button", { name: "Extrude" }));
    await waitFor(() => expect(screen.getByTestId("sketchmath-cad-feature-summary")).toHaveTextContent("Extrude preview ready: profile accepted with 1 hole"));
    expect(screen.getByTestId("sketchmath-solid-preview")).toBeVisible();
    expect(screen.getByTestId("sketchmath-solid-preview-status")).toHaveTextContent("15 mm extrusion with 1 through-hole");
    expect(screen.getByRole("button", { name: "Top" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Front" })).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: "Commit Preview" }));

    await waitFor(() => expect(screen.getByTestId("sketchmath-export-card")).toHaveTextContent("Export succeeded"));
    expect(screen.getByRole("link", { name: "Download STEP" })).toHaveAttribute(
      "href",
      expect.stringMatching(/^\/api\/sketchmath\/artifacts\/step\?path=%2Ftmp%2Fsketchmath%2Fextrude_profile_.+%2Fexport\.step$/),
    );
    expect(screen.queryByTestId("sketchmath-command-panel")).toBeNull();

    const commandTypes = fetchMock.mock.calls
      .filter(([url]) => String(url).includes("/commands/commit"))
      .map(([, init]) => JSON.parse(String(init?.body || "{}")).command?.command_type);
    expect(commandTypes).toEqual(expect.arrayContaining(["batch", "set_rectangle_dimension", "add_profile_hole", "update_profile_hole", "extrude_profile"]));
    const rectangleBatchCall = fetchMock.mock.calls.find(([url, init]) => String(url).includes("/commands/commit") && String(init?.body || "").includes("\"command_type\":\"batch\""));
    const rectangleBatchBody = JSON.parse(String(rectangleBatchCall?.[1]?.body || "{}"));
    expect(rectangleBatchBody.command.parameters.commands).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ mode: "commit", command_type: "define_point" }),
        expect.objectContaining({ mode: "commit", command_type: "define_line" }),
        expect.objectContaining({ mode: "commit", command_type: "make_profile" }),
      ]),
    );
  });
});
