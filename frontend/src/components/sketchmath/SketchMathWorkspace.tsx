import React, { useEffect, useMemo, useRef, useState } from "react";
import { Box, Button, Heading, HStack, Input, Link, Spinner, Text, useColorMode, useToast, VStack } from "@chakra-ui/react";
import SketchCanvas2D from "./SketchCanvas2D";
import SketchMathToolbar from "./SketchMathToolbar";
import SelectionInspector from "./SelectionInspector";
import CommandPanel from "./CommandPanel";
import OperationHistoryPanel from "./OperationHistoryPanel";
import MeasurementPanel from "./MeasurementPanel";
import type {
  SketchMathCommand,
  SketchMathEntity,
  SketchMathHistoryEntry,
  SketchMathMode,
  SketchMathOperationResult,
  SketchMathSelectionContext,
  SketchMathSessionSnapshot,
  SketchMathTranslationOutcome,
} from "../../services/sketchmath";
import {
  commitSketchMathCommand,
  createSketchMathSession,
  getSketchMathSession,
  isSketchMathEnabled,
  previewSketchMathCommand,
  revertSketchMathSession,
  translateSketchMathUtterance,
  upsertSketchMathEntity,
} from "../../services/sketchmath";
import {
  buildDeleteEntityCommand,
  buildDefineLineCommand,
  buildDefinePointCommand,
  buildExtrudeProfileCommand,
  buildBatchCommand,
  buildEqualAngleCommand,
  buildEqualLengthCommand,
  buildMakeParallelCommand,
  buildMakePerpendicularCommand,
  buildMakeProfileCommand,
  buildSolveConstraintsCommand,
  buildSetAngleCommand,
  buildSetLengthCommand,
} from "./commandBuilders";

const CANVAS_WIDTH = 1200;
const CANVAS_HEIGHT = 800;
const SESSION_STORAGE_KEY = "friday_sketchmath_session_id";

type Point = { x: number; y: number };
type RectangleDraft = { anchor: Point; current: Point };
type RectanglePointId = "a" | "b" | "c" | "d";
type RectangleEdgeId = "ab" | "bc" | "cd" | "da";
type RectangleSelectionDetail =
  | { kind: "rectangle"; baseId: string }
  | { kind: "edge"; baseId: string; edgeId: RectangleEdgeId; dimension: "width" | "height" }
  | { kind: "corner"; baseId: string; cornerId: RectanglePointId }
  | { kind: "profile"; baseId: string };
type DimensionEditorState = { baseId: string; dimension: "width" | "height"; value: string } | null;
type DeletePromptState = { kind: "rectangle"; baseId: string; message: string } | null;
type SelectionRef = {
  kind: "none" | "rectangle_edge" | "rectangle_corner" | "rectangle_profile" | "rectangle" | "one_line" | "two_lines" | "one_point" | "two_points" | "mixed";
  summary: string;
  parentSummary?: string;
  detail?: string;
  canEditWidth: boolean;
  canEditHeight: boolean;
  canSetLength: boolean;
  canSetAngle: boolean;
  canMakeParallel: boolean;
  canMakePerpendicular: boolean;
  canEqualLength: boolean;
  canFixCorner: boolean;
};
type RectangleBundle = {
  baseId: string;
  pointIds: Record<RectanglePointId, string>;
  lineIds: Record<RectangleEdgeId, string>;
  profileId: string;
};

const RECTANGLE_DRAG_THRESHOLD = 3;

const sketchmathInitialContext = (): SketchMathSelectionContext => ({
  selection_set_id: "sketchmath_local",
  units: "mm",
  frame: "canvas_2d",
  items: [],
  constraints: [],
  named_references: {},
});

const asCommandText = (command: SketchMathCommand | null): string => (command ? JSON.stringify(command, null, 2) : "");

const isPointEntity = (entity: SketchMathEntity): entity is Extract<SketchMathEntity, { type: "point_2d" }> => entity.type === "point_2d";

const isLineEntity = (entity: SketchMathEntity): entity is Extract<SketchMathEntity, { type: "line_2d" | "construction_line_2d" }> =>
  entity.type === "line_2d" || entity.type === "construction_line_2d";

const isClosedProfileEntity = (entity: SketchMathEntity): entity is Extract<SketchMathEntity, { type: "profile_2d" }> =>
  entity.type === "profile_2d" && entity.closed !== false;

const pointsMatch = (point: SketchMathEntity | undefined, coords: [number, number]): point is Extract<SketchMathEntity, { type: "point_2d" }> =>
  !!point && isPointEntity(point) && point.coords[0] === coords[0] && point.coords[1] === coords[1];

const distanceBetween = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y);

const rectangleBaseIdFromPointId = (pointId: string): string | null => {
  const match = /^rect_(.+)_[abcd]$/.exec(pointId);
  return match ? `rect_${match[1]}` : null;
};

const rectangleBaseIdFromEntityId = (entityId: string): string | null => {
  const pointBaseId = rectangleBaseIdFromPointId(entityId);
  if (pointBaseId) {
    return pointBaseId;
  }
  const lineMatch = /^rect_(.+)_(ab|bc|cd|da)$/.exec(entityId);
  if (lineMatch) {
    return `rect_${lineMatch[1]}`;
  }
  const profileMatch = /^profile_(rect_.+)$/.exec(entityId);
  return profileMatch ? profileMatch[1] : null;
};

const rectangleEdgeIdFromEntityId = (entityId: string): RectangleEdgeId | null => {
  const match = /^rect_.+_(ab|bc|cd|da)$/.exec(entityId);
  return match ? (match[1] as RectangleEdgeId) : null;
};

const rectangleCornerIdFromPointId = (pointId: string): RectanglePointId | null => {
  const match = /^rect_.+_([abcd])$/.exec(pointId);
  return match ? (match[1] as RectanglePointId) : null;
};

const rectangleEdgeDimension = (edgeId: RectangleEdgeId): "width" | "height" =>
  edgeId === "ab" || edgeId === "cd" ? "width" : "height";

const rectangleEdgeLabel = (edgeId: RectangleEdgeId): string => edgeId.toUpperCase();

const rectangleIdsFromBaseId = (baseId: string): RectangleBundle => ({
  baseId,
  pointIds: {
    a: `${baseId}_a`,
    b: `${baseId}_b`,
    c: `${baseId}_c`,
    d: `${baseId}_d`,
  },
  lineIds: {
    ab: `${baseId}_ab`,
    bc: `${baseId}_bc`,
    cd: `${baseId}_cd`,
    da: `${baseId}_da`,
  },
  profileId: `profile_${baseId}`,
});

const rectangleSelectionIds = (baseId: string): string[] => {
  const ids = rectangleIdsFromBaseId(baseId);
  return [
    ids.pointIds.a,
    ids.pointIds.b,
    ids.pointIds.c,
    ids.pointIds.d,
    ids.lineIds.ab,
    ids.lineIds.bc,
    ids.lineIds.cd,
    ids.lineIds.da,
    ids.profileId,
  ];
};

const clampRectanglePoint = (anchor: Point, point: Point, forceSquare: boolean): Point => {
  if (!forceSquare) {
    return point;
  }
  const dx = point.x - anchor.x;
  const dy = point.y - anchor.y;
  const size = Math.max(Math.abs(dx), Math.abs(dy));
  const sx = dx === 0 ? 1 : Math.sign(dx);
  const sy = dy === 0 ? 1 : Math.sign(dy);
  return { x: anchor.x + sx * size, y: anchor.y + sy * size };
};

const SketchMathWorkspace = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const toast = useToast();
  const [enabled] = useState<boolean>(isSketchMathEnabled());
  const [loading, setLoading] = useState(true);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [committedContext, setCommittedContext] = useState<SketchMathSelectionContext>(sketchmathInitialContext());
  const [sessionMetadata, setSessionMetadata] = useState<Record<string, unknown>>({});
  const [history, setHistory] = useState<SketchMathHistoryEntry[]>([]);
  const [selectedEntityIds, setSelectedEntityIds] = useState<string[]>([]);
  const [previewResult, setPreviewResult] = useState<SketchMathOperationResult | null>(null);
  const [draftPoint, setDraftPoint] = useState<Point | null>(null);
  const [rectangleDraft, setRectangleDraft] = useState<RectangleDraft | null>(null);
  const [dragPreviewPoint, setDragPreviewPoint] = useState<{ id: string; point: Point } | null>(null);
  const [tool, setTool] = useState<SketchMathMode>("select");
  const [pendingCommandText, setPendingCommandText] = useState("");
  const [translationOutcome, setTranslationOutcome] = useState<SketchMathTranslationOutcome | null>(null);
  const [labelDraft, setLabelDraft] = useState("");
  const [lengthValue, setLengthValue] = useState("17.5");
  const [angleValue, setAngleValue] = useState("45");
  const [rectangleWidthDraft, setRectangleWidthDraft] = useState("");
  const [rectangleHeightDraft, setRectangleHeightDraft] = useState("");
  const [rectangleSelectionDetail, setRectangleSelectionDetail] = useState<RectangleSelectionDetail | null>(null);
  const [dimensionEditor, setDimensionEditor] = useState<DimensionEditorState>(null);
  const [dimensionEditedRectangleIds, setDimensionEditedRectangleIds] = useState<string[]>([]);
  const [deletePrompt, setDeletePrompt] = useState<DeletePromptState>(null);
  const [extrudeDepthValue, setExtrudeDepthValue] = useState("10");
  const [cadFeatureSummary, setCadFeatureSummary] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canvasDragRef = useRef<{ start: Point; moved: boolean; forceSquare: boolean } | null>(null);
  const pointDragRef = useRef<{ entityId: string; start: Point; current: Point; moved: boolean } | null>(null);
  const ignoreNextCanvasClickRef = useRef(false);

  useEffect(() => {
    document.documentElement.dataset.fridayTheme = colorMode;
  }, [colorMode]);

  useEffect(() => {
    let cancelled = false;
    const initialize = async () => {
      if (!enabled) {
        setLoading(false);
        return;
      }
      const storedSessionId = window.localStorage.getItem(SESSION_STORAGE_KEY);
      try {
        const snapshot = storedSessionId ? await getSketchMathSession(storedSessionId) : await createSketchMathSession();
        if (cancelled) {
          return;
        }
        setSessionId(snapshot.session_id);
        window.localStorage.setItem(SESSION_STORAGE_KEY, snapshot.session_id);
        setCommittedContext(snapshot.selection_context);
        setSessionMetadata(snapshot.session_metadata || {});
        setHistory(snapshot.history);
        setPendingCommandText("");
      } catch (initialError) {
        try {
          const snapshot = await createSketchMathSession();
          if (cancelled) {
            return;
          }
          setSessionId(snapshot.session_id);
          window.localStorage.setItem(SESSION_STORAGE_KEY, snapshot.session_id);
          setCommittedContext(snapshot.selection_context);
          setSessionMetadata(snapshot.session_metadata || {});
          setHistory(snapshot.history);
          setPendingCommandText("");
        } catch (err) {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "Failed to initialize SketchMath");
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    initialize();
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  const committedEntities = committedContext.items;
  const selectedEntities = useMemo(
    () => committedEntities.filter((entity) => selectedEntityIds.includes(entity.id)),
    [committedEntities, selectedEntityIds],
  );
  const selectedPointEntities = useMemo(() => selectedEntities.filter(isPointEntity), [selectedEntities]);
  const closedProfileEntity = useMemo(
    () => committedEntities.find(isClosedProfileEntity) || null,
    [committedEntities],
  );
  const selectedRectangleBaseId = useMemo(
    () => selectedEntityIds.map(rectangleBaseIdFromEntityId).find((value): value is string => Boolean(value)) || null,
    [selectedEntityIds],
  );
  const selectedRectangleProfile = useMemo(() => {
    if (!selectedRectangleBaseId) {
      return null;
    }
    const profileId = rectangleIdsFromBaseId(selectedRectangleBaseId).profileId;
    const profile = committedEntities.find((entity) => entity.id === profileId);
    return profile && isClosedProfileEntity(profile) ? profile : null;
  }, [committedEntities, selectedRectangleBaseId]);
  const rectangleAnchorPoint = useMemo(() => {
    if (!selectedRectangleBaseId) {
      return null;
    }
    const anchorId = rectangleIdsFromBaseId(selectedRectangleBaseId).pointIds.a;
    const anchor = committedEntities.find((entity) => entity.id === anchorId);
    return anchor && isPointEntity(anchor) ? anchor : null;
  }, [committedEntities, selectedRectangleBaseId]);
  const rectangleDimensions = useMemo(() => {
    if (!selectedRectangleBaseId) {
      return null;
    }
    const ids = rectangleIdsFromBaseId(selectedRectangleBaseId);
    const lineById = new Map(
      committedEntities
        .filter(isLineEntity)
        .map((entity) => [entity.id, entity] as const),
    );
    const top = lineById.get(ids.lineIds.ab);
    const left = lineById.get(ids.lineIds.da);
    if (!top || !left) {
      return null;
    }
    return {
      baseId: selectedRectangleBaseId,
      width: Number(Math.abs(top.end[0] - top.start[0]).toFixed(2)),
      height: Number(Math.abs(left.start[1] - left.end[1]).toFixed(2)),
    };
  }, [committedEntities, selectedRectangleBaseId]);
  const rectangleAnchorSummary = rectangleDimensions
    ? rectangleAnchorPoint?.locked
      ? "Anchored at corner A"
      : "Position free"
    : null;
  const profileSummary = selectedRectangleProfile
    ? "Closed profile: valid"
    : closedProfileEntity
      ? "Closed profile: valid"
      : "No closed profile yet";

  useEffect(() => {
    if (selectedEntities.length === 1) {
      setLabelDraft(selectedEntities[0].label || selectedEntities[0].id);
    } else if (selectedEntities.length === 0) {
      setLabelDraft("");
    }
  }, [selectedEntities]);

  useEffect(() => {
    if (!rectangleDimensions) {
      setRectangleWidthDraft("");
      setRectangleHeightDraft("");
      return;
    }
    setRectangleWidthDraft(String(rectangleDimensions.width));
    setRectangleHeightDraft(String(rectangleDimensions.height));
  }, [rectangleDimensions]);

  const sketchStatus = useMemo(() => {
    if (error && (error.toLowerCase().includes("overconstrained") || error.toLowerCase().includes("conflict"))) {
      return "Overconstrained / conflict";
    }
    if (selectedRectangleProfile || closedProfileEntity) {
      if (rectangleDimensions && rectangleAnchorPoint?.locked) {
        return "Fully defined: width, height, and anchor are fixed";
      }
      if (rectangleDimensions && dimensionEditedRectangleIds.includes(rectangleDimensions.baseId)) {
        return "Underdefined: width and height set, position is free";
      }
      return "Underdefined: size/profile exists, position is free";
    }
    if (committedContext.constraints.length > 0 || closedProfileEntity) {
      return "Fully defined";
    }
    return "Underdefined";
  }, [committedContext.constraints.length, closedProfileEntity, dimensionEditedRectangleIds, error, rectangleAnchorPoint?.locked, rectangleDimensions, selectedRectangleProfile]);

  const dimensionSummary = useMemo(() => {
    const pointCount = committedEntities.filter((entity) => entity.type === "point_2d").length;
    const lineCount = committedEntities.filter((entity) => entity.type === "line_2d" || entity.type === "construction_line_2d").length;
    return `${pointCount} points • ${lineCount} lines • ${committedContext.constraints.length} constraints`;
  }, [committedContext.constraints.length, committedEntities]);

  const selectedIdsAreReferenced = (entityIds: string[]): boolean => {
    const selected = new Set(entityIds);
    const referencedByConstraint = committedContext.constraints.some((constraint) =>
      Array.isArray((constraint as Record<string, unknown>).points) &&
      ((constraint as Record<string, unknown>).points as unknown[]).some((pointId) => typeof pointId === "string" && selected.has(pointId)),
    );
    const referencedByName = Object.values(committedContext.named_references).some((entityId) => selected.has(entityId));
    const referencedByProfile = committedEntities.some(
      (entity) => isClosedProfileEntity(entity) && selected.has(entity.id),
    );
    return referencedByConstraint || referencedByName || referencedByProfile;
  };

  const constraintSummaries = useMemo(
    () =>
      committedContext.constraints.map((constraint, index) => {
        const type = typeof constraint.type === "string" ? constraint.type : "constraint";
        const label = typeof constraint.id === "string" ? constraint.id : `constraint_${index + 1}`;
        const detailParts: string[] = [];
        if (typeof (constraint as Record<string, unknown>).distance === "number") {
          const distance = (constraint as Record<string, unknown>).distance as number;
          const unit = typeof (constraint as Record<string, unknown>).unit === "string" ? (constraint as Record<string, unknown>).unit : "mm";
          detailParts.push(`distance ${distance} ${unit}`);
        }
        if (typeof (constraint as Record<string, unknown>).angle === "number") {
          const angle = (constraint as Record<string, unknown>).angle as number;
          const unit = typeof (constraint as Record<string, unknown>).unit === "string" ? (constraint as Record<string, unknown>).unit : "deg";
          detailParts.push(`angle ${angle} ${unit}`);
        }
        return `${index + 1}. ${type} • ${label}${detailParts.length ? ` • ${detailParts.join(" • ")}` : ""}`;
      }),
    [committedContext.constraints],
  );

  const lineSelectionGroup = (entity: Extract<SketchMathEntity, { type: "line_2d" | "construction_line_2d" }>): string[] => {
    const rectangleBaseId = rectangleBaseIdFromEntityId(entity.id);
    if (rectangleBaseId) {
      const ids = rectangleIdsFromBaseId(rectangleBaseId);
      return [
        ids.pointIds.a,
        ids.pointIds.b,
        ids.pointIds.c,
        ids.pointIds.d,
        ids.lineIds.ab,
        ids.lineIds.bc,
        ids.lineIds.cd,
        ids.lineIds.da,
        ids.profileId,
      ];
    }
    const startPoint = committedEntities.find((candidate) => pointsMatch(candidate, entity.start));
    const endPoint = committedEntities.find((candidate) => pointsMatch(candidate, entity.end));
    return [entity.id, startPoint?.id, endPoint?.id].filter((value): value is string => Boolean(value));
  };

  const lineEndpointPointIds = (entity: Extract<SketchMathEntity, { type: "line_2d" | "construction_line_2d" }>): string[] => {
    const startPoint = committedEntities.find((candidate) => pointsMatch(candidate, entity.start));
    const endPoint = committedEntities.find((candidate) => pointsMatch(candidate, entity.end));
    return [startPoint?.id, endPoint?.id].filter((value): value is string => Boolean(value));
  };

  const pointSelectionIds = useMemo(
    () => Array.from(new Set(selectedPointEntities.map((entity) => entity.id))),
    [selectedPointEntities],
  );

  const selectedLineEntities = useMemo(() => selectedEntities.filter(isLineEntity), [selectedEntities]);
  const selectedLinePointIds = useMemo(
    () => Array.from(new Set(selectedLineEntities.flatMap((entity) => lineEndpointPointIds(entity)))),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [committedEntities, selectedLineEntities],
  );
  const lengthSelectionPointIds = selectedLineEntities.length === 1 && selectedLinePointIds.length >= 2 ? selectedLinePointIds.slice(0, 2) : pointSelectionIds;
  const lineConstraintPointIds = selectedLineEntities.length === 2 && selectedLinePointIds.length >= 4 ? selectedLinePointIds.slice(0, 4) : pointSelectionIds;

  const selectionRef = useMemo<SelectionRef>(() => {
    const base: Omit<SelectionRef, "kind" | "summary"> = {
      canEditWidth: false,
      canEditHeight: false,
      canSetLength: false,
      canSetAngle: false,
      canMakeParallel: false,
      canMakePerpendicular: false,
      canEqualLength: false,
      canFixCorner: false,
    };
    if (selectedEntityIds.length === 0) {
      return { ...base, kind: "none", summary: "Selected: Nothing" };
    }
    if (rectangleSelectionDetail?.kind === "edge") {
      const edgeName = rectangleSelectionDetail.dimension === "width" ? "width" : "height";
      return {
        ...base,
        kind: "rectangle_edge",
        summary: `Selected: Rectangle ${edgeName} edge`,
        parentSummary: `Parent: Rectangle ${rectangleSelectionDetail.baseId}`,
        detail: `Edge ${rectangleEdgeLabel(rectangleSelectionDetail.edgeId)}`,
        canEditWidth: rectangleSelectionDetail.dimension === "width",
        canEditHeight: rectangleSelectionDetail.dimension === "height",
      };
    }
    if (rectangleSelectionDetail?.kind === "corner") {
      return {
        ...base,
        kind: "rectangle_corner",
        summary: `Selected: Rectangle corner ${rectangleSelectionDetail.cornerId.toUpperCase()}`,
        parentSummary: `Parent: Rectangle ${rectangleSelectionDetail.baseId}`,
        detail: "Angle: 90 deg",
        canFixCorner: true,
      };
    }
    if (rectangleSelectionDetail?.kind === "profile") {
      return { ...base, kind: "rectangle_profile", summary: "Selected: Rectangle profile", parentSummary: `Parent: Rectangle ${rectangleSelectionDetail.baseId}` };
    }
    if (selectedLineEntities.length === 2) {
      return {
        ...base,
        kind: "two_lines",
        summary: "Selected: 2 lines",
        detail: "Angle tools available. Arbitrary angle solving is not implemented yet.",
        canSetAngle: true,
        canMakeParallel: true,
        canMakePerpendicular: true,
        canEqualLength: true,
      };
    }
    if (selectedLineEntities.length === 1) {
      const line = selectedLineEntities[0];
      const edgeId = rectangleEdgeIdFromEntityId(line.id);
      const rectangleBaseId = rectangleBaseIdFromEntityId(line.id);
      if (edgeId && rectangleBaseId) {
        const dimension = rectangleEdgeDimension(edgeId);
        return {
          ...base,
          kind: "rectangle_edge",
          summary: `Selected: Rectangle ${dimension} edge`,
          parentSummary: `Parent: Rectangle ${rectangleBaseId}`,
          detail: `Edge ${rectangleEdgeLabel(edgeId)}`,
          canEditWidth: dimension === "width",
          canEditHeight: dimension === "height",
        };
      }
      return { ...base, kind: "one_line", summary: "Selected: 1 line", canSetLength: true };
    }
    if (selectedPointEntities.length === 2) {
      return { ...base, kind: "two_points", summary: "Selected: 2 points", canSetLength: true };
    }
    if (selectedPointEntities.length === 1) {
      const point = selectedPointEntities[0];
      const cornerId = rectangleCornerIdFromPointId(point.id);
      const rectangleBaseId = rectangleBaseIdFromEntityId(point.id);
      if (cornerId && rectangleBaseId) {
        return {
          ...base,
          kind: "rectangle_corner",
          summary: `Selected: Rectangle corner ${cornerId.toUpperCase()}`,
          parentSummary: `Parent: Rectangle ${rectangleBaseId}`,
          detail: "Angle: 90 deg",
          canFixCorner: true,
        };
      }
      return { ...base, kind: "one_point", summary: "Selected: 1 point", canFixCorner: true };
    }
    if (rectangleDimensions) {
      return { ...base, kind: "rectangle", summary: "Selected: Rectangle", parentSummary: `Parent: Rectangle ${rectangleDimensions.baseId}`, canFixCorner: true };
    }
    return { ...base, kind: "mixed", summary: `Selected: ${selectedEntityIds.length} entities` };
  }, [rectangleDimensions, rectangleSelectionDetail, selectedEntityIds.length, selectedLineEntities, selectedPointEntities]);

  const syncSnapshot = (snapshot: SketchMathSessionSnapshot) => {
    setCommittedContext(snapshot.selection_context);
    setSessionMetadata(snapshot.session_metadata || {});
    setHistory(snapshot.history);
    window.localStorage.setItem(SESSION_STORAGE_KEY, snapshot.session_id);
  };

  const refreshSession = async () => {
    if (!sessionId) {
      return;
    }
    const snapshot = await getSketchMathSession(sessionId);
    syncSnapshot(snapshot);
  };

  const commitCommand = async (command: SketchMathCommand): Promise<SketchMathOperationResult | null> => {
    if (!sessionId) {
      return null;
    }
    const nextCommand = { ...command, mode: "commit" as const };
    setPendingCommandText(asCommandText(nextCommand));
    try {
      const response = await commitSketchMathCommand(sessionId, nextCommand);
      const snapshot = await getSketchMathSession(sessionId);
      syncSnapshot(snapshot);
      setPreviewResult(response.result);
      setError(null);
      return response.result;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Command failed";
      setError(message);
      toast({
        title: "Sketch command failed",
        description: message,
        status: "error",
        duration: 2500,
        isClosable: true,
      });
      return null;
    }
  };

  const parseCurrentCommand = (): SketchMathCommand => {
    const parsed = JSON.parse(pendingCommandText) as SketchMathCommand;
    return parsed;
  };

  const executePreview = async () => {
    if (!sessionId) {
      return;
    }
    try {
      const command = parseCurrentCommand();
      const response = await previewSketchMathCommand(sessionId, command);
      setPreviewResult(response.result);
      setError(null);
      if (tool === "point") {
        setDraftPoint(null);
      }
      toast({
        title: "Preview ready",
        status: "success",
        duration: 1800,
        isClosable: true,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Preview failed";
      setError(message);
      toast({
        title: "Preview failed",
        description: message,
        status: "error",
        duration: 2500,
        isClosable: true,
      });
    }
  };

  const executeCommit = async () => {
    if (!sessionId) {
      return;
    }
    try {
      const command = {
        ...parseCurrentCommand(),
        mode: "commit" as const,
      };
      const response = await commitSketchMathCommand(sessionId, command);
      const snapshot = await getSketchMathSession(sessionId);
      syncSnapshot(snapshot);
      setPreviewResult(response.result);
      setDraftPoint(null);
      clearRectangleInteraction();
      setSelectedEntityIds([]);
      setTranslationOutcome(null);
      setError(null);
      toast({
        title: "Committed",
        status: "success",
        duration: 1800,
        isClosable: true,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Commit failed";
      setError(message);
      toast({
        title: "Commit failed",
        description: message,
        status: "error",
        duration: 2500,
        isClosable: true,
      });
    }
  };

  const clearPreview = () => {
    setPreviewResult(null);
    setError(null);
  };

  const rejectProposal = () => {
    setTranslationOutcome(null);
    setPendingCommandText("");
    setPreviewResult(null);
    setError(null);
  };

  const revertLast = async () => {
    if (!sessionId) {
      return;
    }
    try {
      const snapshot = await revertSketchMathSession(sessionId);
      syncSnapshot(snapshot);
      setSelectedEntityIds([]);
      setPreviewResult(null);
      setDraftPoint(null);
      clearRectangleInteraction();
      setTranslationOutcome(null);
      setPendingCommandText("");
      setError(null);
      toast({
        title: "Reverted",
        status: "info",
        duration: 1800,
        isClosable: true,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Revert failed";
      setError(message);
    }
  };

  const clearRectangleInteraction = () => {
    setRectangleDraft(null);
    setDragPreviewPoint(null);
    canvasDragRef.current = null;
    pointDragRef.current = null;
  };

  const resetLocalInteractionState = () => {
    setSelectedEntityIds([]);
    setRectangleSelectionDetail(null);
    setDimensionEditor(null);
    setDeletePrompt(null);
    setPreviewResult(null);
    setDraftPoint(null);
    clearRectangleInteraction();
    setTranslationOutcome(null);
    setPendingCommandText("");
    setCadFeatureSummary(null);
    setError(null);
  };

  const commitRectangle = async (anchor: Point, rawCurrent: Point, forceSquare: boolean) => {
    const resolvedCurrent = clampRectanglePoint(anchor, rawCurrent, forceSquare);
    const stamp = Date.now().toString(36);
    const baseId = `rect_${stamp}`;
    const ids = rectangleIdsFromBaseId(baseId);
    const topLeft = { x: anchor.x, y: anchor.y };
    const topRight = { x: resolvedCurrent.x, y: anchor.y };
    const bottomRight = { x: resolvedCurrent.x, y: resolvedCurrent.y };
    const bottomLeft = { x: anchor.x, y: resolvedCurrent.y };
    const command = buildBatchCommand([
      buildDefinePointCommand(topLeft, ids.pointIds.a, "A"),
      buildDefinePointCommand(topRight, ids.pointIds.b, "B"),
      buildDefinePointCommand(bottomRight, ids.pointIds.c, "C"),
      buildDefinePointCommand(bottomLeft, ids.pointIds.d, "D"),
      buildDefineLineCommand(topLeft, topRight, ids.lineIds.ab, "AB"),
      buildDefineLineCommand(topRight, bottomRight, ids.lineIds.bc, "BC"),
      buildDefineLineCommand(bottomRight, bottomLeft, ids.lineIds.cd, "CD"),
      buildDefineLineCommand(bottomLeft, topLeft, ids.lineIds.da, "DA"),
      buildMakeParallelCommand([ids.pointIds.a, ids.pointIds.b, ids.pointIds.c, ids.pointIds.d]),
      buildMakeParallelCommand([ids.pointIds.b, ids.pointIds.c, ids.pointIds.d, ids.pointIds.a]),
      buildMakePerpendicularCommand([ids.pointIds.a, ids.pointIds.b, ids.pointIds.b, ids.pointIds.c]),
      buildSolveConstraintsCommand(),
      buildMakeProfileCommand([ids.lineIds.ab, ids.lineIds.bc, ids.lineIds.cd, ids.lineIds.da], ids.profileId),
    ]);
    const result = await commitCommand(command);
    if (!result) {
      return;
    }
    setSelectedEntityIds(rectangleSelectionIds(baseId));
    setRectangleSelectionDetail({ kind: "rectangle", baseId });
    setTranslationOutcome(null);
  };

  const handleCanvasClick = (point: Point) => {
    if (ignoreNextCanvasClickRef.current) {
      ignoreNextCanvasClickRef.current = false;
      return;
    }
    if (tool === "point") {
      const pointId = `point_${Date.now().toString(36)}`;
      const nextCommand = buildDefinePointCommand(point, pointId);
      setDraftPoint(point);
      void commitCommand(nextCommand);
      setDraftPoint(null);
      setSelectedEntityIds([pointId]);
      setTranslationOutcome(null);
      return;
    }
    if (tool === "line") {
      if (!draftPoint) {
        setDraftPoint(point);
        setError(null);
        return;
      }
      const stamp = Date.now().toString(36);
      const startPointId = `point_${stamp}_start`;
      const endPointId = `point_${stamp}_end`;
      const lineId = `line_${stamp}`;
      const commands = [
        buildDefinePointCommand(draftPoint, startPointId),
        buildDefinePointCommand(point, endPointId),
        buildDefineLineCommand(draftPoint, point, lineId),
      ];
      setDraftPoint(null);
      void (async () => {
        const result = await commitCommand(buildBatchCommand(commands));
        if (result) {
          setSelectedEntityIds((current) => Array.from(new Set([...current, lineId, startPointId, endPointId])));
          setTranslationOutcome(null);
        } else {
          setSelectedEntityIds([]);
        }
      })();
      return;
    }
    if (tool === "rectangle") {
      if (!rectangleDraft) {
        setRectangleDraft({ anchor: point, current: point });
        setError(null);
        canvasDragRef.current = null;
        return;
      }
      const resolvedCurrent = clampRectanglePoint(rectangleDraft.anchor, point, false);
      void commitRectangle(rectangleDraft.anchor, resolvedCurrent, false);
      clearRectangleInteraction();
      return;
    }
    if (tool === "select") {
      return;
    }
  };

  const handleCanvasMouseDown = (point: Point, event: React.MouseEvent<SVGSVGElement>) => {
    if (tool !== "rectangle" || event.button !== 0) {
      return;
    }
    canvasDragRef.current = { start: point, moved: false, forceSquare: event.shiftKey };
  };

  const handleCanvasMouseMove = (point: Point, event: React.MouseEvent<SVGSVGElement>) => {
    if (pointDragRef.current) {
      const drag = pointDragRef.current;
      const resolvedPoint = { x: Number(point.x.toFixed(2)), y: Number(point.y.toFixed(2)) };
      if (!drag.moved && distanceBetween(drag.start, resolvedPoint) < RECTANGLE_DRAG_THRESHOLD) {
        return;
      }
      drag.moved = true;
      drag.current = resolvedPoint;
      setDragPreviewPoint({ id: drag.entityId, point: resolvedPoint });
    }
    if (tool !== "rectangle") {
      return;
    }
    if (canvasDragRef.current) {
      const drag = canvasDragRef.current;
      const resolvedPoint = clampRectanglePoint(drag.start, point, event.shiftKey || drag.forceSquare);
      if (!drag.moved && distanceBetween(drag.start, point) < RECTANGLE_DRAG_THRESHOLD) {
        return;
      }
      drag.moved = true;
      setRectangleDraft({ anchor: drag.start, current: resolvedPoint });
      return;
    }
    if (rectangleDraft) {
      setRectangleDraft({ anchor: rectangleDraft.anchor, current: clampRectanglePoint(rectangleDraft.anchor, point, event.shiftKey) });
    }
  };

  const handleCanvasMouseUp = (point: Point, event: React.MouseEvent<SVGSVGElement>) => {
    if (pointDragRef.current) {
      const drag = pointDragRef.current;
      const entity = committedEntities.find((candidate) => candidate.id === drag.entityId);
      if (!entity || !isPointEntity(entity)) {
        pointDragRef.current = null;
        setDragPreviewPoint(null);
        return;
      }
      const updatedPoint = drag.moved ? drag.current : { x: entity.coords[0], y: entity.coords[1] };
      if (!drag.moved) {
        pointDragRef.current = null;
        setDragPreviewPoint(null);
        return;
      }
      void (async () => {
        if (!sessionId) {
          return;
        }
        await upsertSketchMathEntity(sessionId, { ...entity, coords: [Number(updatedPoint.x.toFixed(2)), Number(updatedPoint.y.toFixed(2))] }, "commit");
        const afterPoint = await getSketchMathSession(sessionId);
        syncSnapshot(afterPoint);

        const baseId = rectangleBaseIdFromPointId(entity.id);
        if (baseId) {
          const bundle = rectangleIdsFromBaseId(baseId);
          const pointById = new Map(
            afterPoint.selection_context.items
              .filter(isPointEntity)
              .map((item) => [item.id, { x: item.coords[0], y: item.coords[1] }] as const),
          );
          const a = pointById.get(bundle.pointIds.a);
          const b = pointById.get(bundle.pointIds.b);
          const c = pointById.get(bundle.pointIds.c);
          const d = pointById.get(bundle.pointIds.d);
          if (a && b && c && d) {
            const lineUpdates = [
              { id: bundle.lineIds.ab, start: [a.x, a.y] as [number, number], end: [b.x, b.y] as [number, number] },
              { id: bundle.lineIds.bc, start: [b.x, b.y] as [number, number], end: [c.x, c.y] as [number, number] },
              { id: bundle.lineIds.cd, start: [c.x, c.y] as [number, number], end: [d.x, d.y] as [number, number] },
              { id: bundle.lineIds.da, start: [d.x, d.y] as [number, number], end: [a.x, a.y] as [number, number] },
            ];
            for (const line of lineUpdates) {
              await upsertSketchMathEntity(
                sessionId,
                {
                  id: line.id,
                  type: "line_2d",
                  start: line.start,
                  end: line.end,
                  locked: false,
                  label: line.id,
                },
                "commit",
              );
            }
            await commitCommand(buildMakeProfileCommand([bundle.lineIds.ab, bundle.lineIds.bc, bundle.lineIds.cd, bundle.lineIds.da], bundle.profileId));
            const refreshed = await getSketchMathSession(sessionId);
            syncSnapshot(refreshed);
          }
        }
      })();
      pointDragRef.current = null;
      setDragPreviewPoint(null);
      setError(null);
      return;
    }
    if (tool !== "rectangle") {
      return;
    }
    const drag = canvasDragRef.current;
    if (!drag) {
      return;
    }
    if (drag.moved || distanceBetween(drag.start, point) >= RECTANGLE_DRAG_THRESHOLD) {
      ignoreNextCanvasClickRef.current = true;
      void commitRectangle(drag.start, point, event.shiftKey || drag.forceSquare);
      clearRectangleInteraction();
      return;
    }
    canvasDragRef.current = null;
  };

  const handleCanvasContextMenu = () => {
    if (tool === "rectangle") {
      clearRectangleInteraction();
      setError(null);
    }
  };

  const openDimensionEditor = (baseId: string, dimension: "width" | "height") => {
    const value =
      rectangleDimensions && rectangleDimensions.baseId === baseId
        ? dimension === "width"
          ? rectangleDimensions.width
          : rectangleDimensions.height
        : "";
    setDimensionEditor({ baseId, dimension, value: String(value) });
  };

  const handleDimensionLabelEdit = (baseId: string, dimension: "width" | "height") => {
    setSelectedEntityIds(rectangleSelectionIds(baseId));
    setRectangleSelectionDetail({ kind: "edge", baseId, edgeId: dimension === "width" ? "ab" : "bc", dimension });
    openDimensionEditor(baseId, dimension);
  };

  const handleEntityClick = (entityId: string, event: React.MouseEvent<SVGGElement | SVGCircleElement>) => {
    const entity = committedEntities.find((candidate) => candidate.id === entityId);
    const toggleSelection = (ids: string[]) => {
      const isAlreadySelected = ids.every((id) => selectedEntityIds.includes(id));
      const next = isAlreadySelected
        ? selectedEntityIds.filter((id) => !ids.includes(id))
        : [...selectedEntityIds, ...ids.filter((id) => !selectedEntityIds.includes(id))].slice(-12);
      setSelectedEntityIds(next);
      if (next.length === 1) {
        const nextBaseId = rectangleBaseIdFromEntityId(next[0]);
        const nextEdgeId = rectangleEdgeIdFromEntityId(next[0]);
        const nextCornerId = rectangleCornerIdFromPointId(next[0]);
        if (nextBaseId && nextEdgeId) {
          setRectangleSelectionDetail({ kind: "edge", baseId: nextBaseId, edgeId: nextEdgeId, dimension: rectangleEdgeDimension(nextEdgeId) });
          return;
        }
        if (nextBaseId && nextCornerId) {
          setRectangleSelectionDetail({ kind: "corner", baseId: nextBaseId, cornerId: nextCornerId });
          return;
        }
        if (nextBaseId && next[0] === rectangleIdsFromBaseId(nextBaseId).profileId) {
          setRectangleSelectionDetail({ kind: "profile", baseId: nextBaseId });
          return;
        }
      }
      setRectangleSelectionDetail(null);
    };
    const rectangleBaseId = rectangleBaseIdFromEntityId(entityId);
    if (rectangleBaseId) {
      const edgeId = rectangleEdgeIdFromEntityId(entityId);
      const cornerId = rectangleCornerIdFromPointId(entityId);
      if (event.shiftKey) {
        if (selectionRef.kind === "rectangle" && selectedRectangleBaseId === rectangleBaseId) {
          setSelectedEntityIds([entityId]);
          if (edgeId) {
            setRectangleSelectionDetail({ kind: "edge", baseId: rectangleBaseId, edgeId, dimension: rectangleEdgeDimension(edgeId) });
          } else if (cornerId) {
            setRectangleSelectionDetail({ kind: "corner", baseId: rectangleBaseId, cornerId });
          } else {
            setRectangleSelectionDetail({ kind: "profile", baseId: rectangleBaseId });
          }
          setDimensionEditor(null);
          setDeletePrompt(null);
          setError(null);
          return;
        }
        toggleSelection([entityId]);
        setDimensionEditor(null);
        setDeletePrompt(null);
        setError(null);
        return;
      }
      setSelectedEntityIds(rectangleSelectionIds(rectangleBaseId));
      if (edgeId) {
        const dimension = rectangleEdgeDimension(edgeId);
        setRectangleSelectionDetail({ kind: "edge", baseId: rectangleBaseId, edgeId, dimension });
        if (tool === "dimension") {
          openDimensionEditor(rectangleBaseId, dimension);
        }
      } else if (cornerId) {
        setRectangleSelectionDetail({ kind: "corner", baseId: rectangleBaseId, cornerId });
      } else {
        setRectangleSelectionDetail({ kind: "profile", baseId: rectangleBaseId });
      }
      setDeletePrompt(null);
      setError(null);
      return;
    }
    const nextGroup = entity && isLineEntity(entity) ? lineSelectionGroup(entity) : [entityId];
    if (event.shiftKey) {
      toggleSelection(entity && isLineEntity(entity) ? [entity.id] : nextGroup);
    } else {
      setSelectedEntityIds(nextGroup);
      setRectangleSelectionDetail(null);
    }
    setDimensionEditor(null);
    setDeletePrompt(null);
    setError(null);
  };

  const handleEntityMouseDown = (entityId: string, entityType: SketchMathEntity["type"], event: React.MouseEvent<SVGGElement>) => {
    if (entityType !== "point_2d" || event.button !== 0) {
      return;
    }
    const entity = committedEntities.find((candidate) => candidate.id === entityId);
    if (!entity || !isPointEntity(entity)) {
      return;
    }
    pointDragRef.current = {
      entityId,
      start: { x: entity.coords[0], y: entity.coords[1] },
      current: { x: entity.coords[0], y: entity.coords[1] },
      moved: false,
    };
    setDragPreviewPoint({ id: entityId, point: { x: entity.coords[0], y: entity.coords[1] } });
    setError(null);
  };

  const handleApplyLabel = async () => {
    if (!sessionId || selectedEntities.length === 0) {
      return;
    }
    const entity = selectedEntities[0];
    const label = labelDraft.trim();
    if (!label) {
      return;
    }
    const payload =
      entity.type === "point_2d"
        ? { ...entity, label, locked: entity.locked }
        : entity.type === "line_2d" || entity.type === "construction_line_2d"
          ? { ...entity, label, locked: entity.locked }
          : null;
    if (!payload) {
      return;
    }
    await upsertSketchMathEntity(sessionId, payload as SketchMathEntity, "commit");
    const snapshot = await getSketchMathSession(sessionId);
    syncSnapshot(snapshot);
    setError(null);
  };

  const handleToggleLockSelected = async () => {
    if (!sessionId || selectedEntities.length === 0) {
      return;
    }
    const entity = selectedEntities[0];
    const payload =
      entity.type === "point_2d"
        ? { ...entity, locked: !entity.locked }
        : entity.type === "line_2d" || entity.type === "construction_line_2d"
          ? { ...entity, locked: !entity.locked }
          : null;
    if (!payload) {
      return;
    }
    await upsertSketchMathEntity(sessionId, payload as SketchMathEntity, "commit");
    const snapshot = await getSketchMathSession(sessionId);
    syncSnapshot(snapshot);
    setError(null);
  };

  const applyRectangleDimensions = async (width: number, height: number) => {
    if (!sessionId || !rectangleDimensions) {
      return;
    }
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
      setError("Rectangle width and height must be positive numbers");
      return;
    }

    const ids = rectangleIdsFromBaseId(rectangleDimensions.baseId);
    const pointById = new Map(
      committedEntities
        .filter(isPointEntity)
        .map((entity) => [entity.id, entity] as const),
    );
    const lineById = new Map(
      committedEntities
        .filter(isLineEntity)
        .map((entity) => [entity.id, entity] as const),
    );
    const a = pointById.get(ids.pointIds.a);
    const b = pointById.get(ids.pointIds.b);
    const c = pointById.get(ids.pointIds.c);
    const d = pointById.get(ids.pointIds.d);
    const top = lineById.get(ids.lineIds.ab);
    const left = lineById.get(ids.lineIds.da);
    if (!a || !b || !c || !d || !top || !left) {
      setError("Rectangle geometry is incomplete");
      return;
    }

    const signX = top.end[0] >= top.start[0] ? 1 : -1;
    const signY = left.start[1] >= left.end[1] ? 1 : -1;
    const topLeft = { x: top.start[0], y: top.start[1] };
    const topRight = { x: Number((top.start[0] + signX * width).toFixed(2)), y: top.start[1] };
    const bottomLeft = { x: top.start[0], y: Number((top.start[1] + signY * height).toFixed(2)) };
    const bottomRight = { x: topRight.x, y: bottomLeft.y };
    const updates: SketchMathEntity[] = [
      { ...a, coords: [topLeft.x, topLeft.y] },
      { ...b, coords: [topRight.x, topRight.y] },
      { ...c, coords: [bottomRight.x, bottomRight.y] },
      { ...d, coords: [bottomLeft.x, bottomLeft.y] },
      { id: ids.lineIds.ab, type: "line_2d", start: [topLeft.x, topLeft.y], end: [topRight.x, topRight.y], locked: false, label: "AB" },
      { id: ids.lineIds.bc, type: "line_2d", start: [topRight.x, topRight.y], end: [bottomRight.x, bottomRight.y], locked: false, label: "BC" },
      { id: ids.lineIds.cd, type: "line_2d", start: [bottomRight.x, bottomRight.y], end: [bottomLeft.x, bottomLeft.y], locked: false, label: "CD" },
      { id: ids.lineIds.da, type: "line_2d", start: [bottomLeft.x, bottomLeft.y], end: [topLeft.x, topLeft.y], locked: false, label: "DA" },
      {
        id: ids.profileId,
        type: "profile_2d",
        vertices: [
          [topLeft.x, topLeft.y],
          [topRight.x, topRight.y],
          [bottomRight.x, bottomRight.y],
          [bottomLeft.x, bottomLeft.y],
        ],
        area: Number((width * height).toFixed(2)),
        winding: "counterclockwise",
        warnings: [],
        closed: true,
        locked: false,
        label: ids.profileId,
      },
    ];

    const activeRectangleDetail = rectangleSelectionDetail?.baseId === rectangleDimensions.baseId ? rectangleSelectionDetail : null;

    try {
      for (const entity of updates) {
        await upsertSketchMathEntity(sessionId, entity, "commit");
      }
      await refreshSession();
      if (activeRectangleDetail?.kind === "edge") {
        setSelectedEntityIds([ids.lineIds[activeRectangleDetail.edgeId]]);
        setRectangleSelectionDetail(activeRectangleDetail);
      } else if (activeRectangleDetail?.kind === "corner") {
        setSelectedEntityIds([ids.pointIds[activeRectangleDetail.cornerId]]);
        setRectangleSelectionDetail(activeRectangleDetail);
      } else if (activeRectangleDetail?.kind === "profile") {
        setSelectedEntityIds([ids.profileId]);
        setRectangleSelectionDetail(activeRectangleDetail);
      } else {
        setSelectedEntityIds(rectangleSelectionIds(rectangleDimensions.baseId));
        setRectangleSelectionDetail(null);
      }
      setDimensionEditedRectangleIds((current) => Array.from(new Set([...current, rectangleDimensions.baseId])));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update rectangle dimensions");
    }
  };

  const handleApplyRectangleDimensions = async () => {
    await applyRectangleDimensions(Number(rectangleWidthDraft), Number(rectangleHeightDraft));
  };

  const handleApplyDimensionEditor = async () => {
    if (!dimensionEditor || !rectangleDimensions || rectangleDimensions.baseId !== dimensionEditor.baseId) {
      return;
    }
    const value = Number(dimensionEditor.value);
    const nextWidth = dimensionEditor.dimension === "width" ? value : rectangleDimensions.width;
    const nextHeight = dimensionEditor.dimension === "height" ? value : rectangleDimensions.height;
    await applyRectangleDimensions(nextWidth, nextHeight);
    setDimensionEditor(null);
  };

  const handleFixRectangleCorner = async () => {
    if (!sessionId || !rectangleDimensions) {
      return;
    }
    const ids = rectangleIdsFromBaseId(rectangleDimensions.baseId);
    const selectedCornerId = selectedEntities.find(
      (entity): entity is Extract<SketchMathEntity, { type: "point_2d" }> =>
        isPointEntity(entity) && rectangleBaseIdFromPointId(entity.id) === rectangleDimensions.baseId,
    )?.id;

    try {
      const latestSnapshot = await getSketchMathSession(sessionId);
      syncSnapshot(latestSnapshot);
      const latestAnchor = latestSnapshot.selection_context.items.find(
        (entity): entity is Extract<SketchMathEntity, { type: "point_2d" }> =>
          isPointEntity(entity) && entity.id === (selectedCornerId || ids.pointIds.a),
      );
      if (!latestAnchor) {
        setError("Rectangle anchor point is missing");
        return;
      }
      const pointIds = new Set(Object.values(ids.pointIds));
      const lockTarget = pointIds.has(latestAnchor.id) ? latestAnchor : latestSnapshot.selection_context.items.find(
        (entity): entity is Extract<SketchMathEntity, { type: "point_2d" }> => isPointEntity(entity) && entity.id === ids.pointIds.a,
      );
      if (!lockTarget) {
        setError("Rectangle anchor point is missing");
        return;
      }
      await upsertSketchMathEntity(sessionId, { ...lockTarget, locked: true }, "commit");
      await refreshSession();
      setSelectedEntityIds(rectangleSelectionIds(rectangleDimensions.baseId));
      setRectangleSelectionDetail({
        kind: "corner",
        baseId: rectangleDimensions.baseId,
        cornerId: rectangleCornerIdFromPointId(lockTarget.id) || "a",
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fix rectangle corner");
    }
  };

  const handleCreateCadFeature = () => {
    const profile = selectedRectangleProfile || closedProfileEntity;
    if (!profile) {
      return;
    }
    const depth = Number(extrudeDepthValue);
    if (!Number.isFinite(depth) || depth <= 0) {
      setError("Extrusion depth must be a positive number");
      return;
    }
    const normalizedDepth = Number(depth.toFixed(2));
    const command = buildExtrudeProfileCommand(profile.id, normalizedDepth, "mm");
    setPendingCommandText(asCommandText(command));
    setCadFeatureSummary(`Extrude Profile 1 by ${Number(normalizedDepth.toFixed(2)).toString()} mm`);
    setSelectedEntityIds([profile.id]);
    const baseId = rectangleBaseIdFromEntityId(profile.id);
    setRectangleSelectionDetail(baseId ? { kind: "profile", baseId } : null);
    setError(null);
  };

  const deleteRectangleCascade = async (baseId: string) => {
    const result = await commitCommand(buildDeleteEntityCommand(rectangleSelectionIds(baseId), true));
    if (!result) {
      setError("Could not delete the rectangle safely. Open Advanced / Debug for details.");
      return;
    }
    setSelectedEntityIds([]);
    setRectangleSelectionDetail(null);
    setDimensionEditor(null);
    setDeletePrompt(null);
    setCadFeatureSummary(null);
    setTranslationOutcome(null);
    setPendingCommandText("");
    setPreviewResult(null);
    setError(null);
  };

  const handleDeleteSelected = async () => {
    if (!sessionId || selectedEntities.length === 0) {
      return;
    }
    if (selectedRectangleBaseId) {
      if (rectangleSelectionDetail?.kind === "edge") {
        setDeletePrompt({
          kind: "rectangle",
          baseId: selectedRectangleBaseId,
          message: "This edge belongs to a rectangle. Delete the whole rectangle to remove its dependent points, edges, constraints, and profile.",
        });
        return;
      }
      if (rectangleSelectionDetail?.kind === "corner") {
        setDeletePrompt({
          kind: "rectangle",
          baseId: selectedRectangleBaseId,
          message: "This corner belongs to a rectangle. Delete the whole rectangle to remove its dependent points, edges, constraints, and profile.",
        });
        return;
      }
      await deleteRectangleCascade(selectedRectangleBaseId);
      return;
    }
    if (selectedIdsAreReferenced(selectedEntityIds)) {
      setError("Selection is referenced by sketch constraints or profiles. Delete the parent sketch object instead.");
      return;
    }
    const result = await commitCommand(buildDeleteEntityCommand(selectedEntityIds));
    if (!result) {
      setError("Could not delete the selection safely. Open Advanced / Debug for details.");
      return;
    }
    setSelectedEntityIds([]);
    setPendingCommandText("");
    setTranslationOutcome(null);
    setPreviewResult(null);
    setDraftPoint(null);
    setDeletePrompt(null);
    clearRectangleInteraction();
  };

  const handleClearSketch = async () => {
    try {
      const snapshot = await createSketchMathSession();
      setSessionId(snapshot.session_id);
      syncSnapshot(snapshot);
      resetLocalInteractionState();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clear sketch");
    }
  };

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const isTypingField =
        !!target &&
        "getAttribute" in target &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable || target.getAttribute("role") === "textbox");
      if (event.key === "Escape") {
        clearRectangleInteraction();
        setDraftPoint(null);
        setError(null);
        return;
      }
      if (isTypingField) {
        return;
      }
      if ((event.key === "Backspace" || event.key === "Delete") && selectedEntityIds.length > 0) {
        event.preventDefault();
        void handleDeleteSelected();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  // Rebind when selection identity or semantic rectangle detail changes so Delete uses the current routing state.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rectangleSelectionDetail, selectedEntityIds, selectedRectangleBaseId]);

  const handleTranslate = async (utterance: string) => {
    if (!sessionId) {
      return;
    }
    try {
      const response = await translateSketchMathUtterance(sessionId, utterance, committedContext);
      setTranslationOutcome(response);
      if (response.status === "command" && response.command) {
        setPendingCommandText(JSON.stringify(response.command, null, 2));
        setError(null);
      } else {
        setPendingCommandText("");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Translation failed");
    }
  };

  const runQuickLength = async () => {
    if (selectionRef.canEditWidth && rectangleSelectionDetail?.kind === "edge") {
      openDimensionEditor(rectangleSelectionDetail.baseId, "width");
      return;
    }
    if (selectionRef.canEditHeight && rectangleSelectionDetail?.kind === "edge") {
      openDimensionEditor(rectangleSelectionDetail.baseId, "height");
      return;
    }
    if (lengthSelectionPointIds.length < 2) {
      return;
    }
    await commitCommand(buildSetLengthCommand(lengthSelectionPointIds, Number(lengthValue), "mm", "midpoint"));
  };

  const runQuickAngle = async () => {
    if (selectionRef.kind === "two_lines") {
      setError("Arbitrary angle solving is not implemented yet. Perpendicular and parallel constraints are available.");
      return;
    }
    if (pointSelectionIds.length < 3) {
      return;
    }
    await commitCommand(buildSetAngleCommand(pointSelectionIds, Number(angleValue), "deg"));
  };

  const runQuickParallel = async () => {
    if (lineConstraintPointIds.length < 4) {
      return;
    }
    await commitCommand(buildMakeParallelCommand(lineConstraintPointIds));
  };

  const runQuickPerpendicular = async () => {
    if (lineConstraintPointIds.length < 4) {
      return;
    }
    await commitCommand(buildMakePerpendicularCommand(lineConstraintPointIds));
  };

  const runQuickEqualLength = async () => {
    if (lineConstraintPointIds.length < 4) {
      return;
    }
    await commitCommand(buildEqualLengthCommand(lineConstraintPointIds));
  };

  const runQuickEqualAngle = async () => {
    if (pointSelectionIds.length < 6) {
      return;
    }
    await commitCommand(buildEqualAngleCommand(pointSelectionIds));
  };

  const runQuickProfile = async () => {
    const selectedLineIds = selectedEntities.filter(isLineEntity).map((entity) => entity.id);
    if (selectedLineIds.length >= 3) {
      await commitCommand(buildMakeProfileCommand(selectedLineIds, closedProfileEntity?.id || undefined));
      return;
    }
    if (closedProfileEntity) {
      setSelectedEntityIds([closedProfileEntity.id]);
    }
  };

  const handleToolChange = (nextTool: SketchMathMode) => {
    if (nextTool !== tool) {
      clearRectangleInteraction();
      setDraftPoint(null);
    }
    if (nextTool === "solve") {
      setTool(nextTool);
      void refreshSession();
      return;
    }
    if (nextTool === "convert") {
      setTool(nextTool);
      void runQuickProfile();
      return;
    }
    if (nextTool === "delete") {
      setTool(nextTool);
      void handleDeleteSelected();
      return;
    }
    setTool(nextTool);
  };

  if (!enabled) {
    return (
      <Box className="sketchmath-shell" data-testid="sketchmath-workspace">
        <VStack align="start" spacing={4} className="sketchmath-disabled">
          <Heading>SketchMath is disabled</Heading>
          <Text>Set <code>FRIDAY_SKETCHMATH_ENABLED=1</code> to open the drawing pad.</Text>
          <Button as="a" href="/" variant="outline">
            Return to FRIDAY
          </Button>
        </VStack>
      </Box>
    );
  }

  if (loading) {
    return (
      <Box className="sketchmath-shell" data-testid="sketchmath-workspace">
        <HStack spacing={3}>
          <Spinner />
          <Text>Booting SketchMath session...</Text>
        </HStack>
      </Box>
    );
  }

  const hasUsableGeometry = Boolean(closedProfileEntity);

  return (
    <Box className="sketchmath-shell" data-testid="sketchmath-workspace">
      <Box className="sketchmath-shell-header">
        <VStack align="start" spacing={1}>
          <Heading size="lg" className="sketchmath-title">
            SketchMath
          </Heading>
          <Text opacity={0.8}>Deterministic 2D drawing pad mounted inside FRIDAY.</Text>
          <Text fontSize="sm" opacity={0.6}>
            Session: {sessionId || "loading"} {sessionMetadata.storage_path ? `• ${String(sessionMetadata.storage_path)}` : ""}
          </Text>
        </VStack>
        <HStack spacing={3}>
          <Link href="/" className="sketchmath-link">
            Back to FRIDAY chat
          </Link>
          <Button size="sm" variant="outline" onClick={toggleColorMode}>
            {colorMode === "light" ? "Dark grid" : "Light grid"}
          </Button>
        </HStack>
      </Box>

      <SketchMathToolbar mode={tool} onModeChange={handleToolChange} theme={colorMode} onToggleTheme={toggleColorMode} />

      <Box className="sketchmath-layout">
        <Box className="sketchmath-canvas-panel">
          <SketchCanvas2D
            width={CANVAS_WIDTH}
            height={CANVAS_HEIGHT}
            entities={committedEntities}
            previewResult={previewResult}
            selectedEntityIds={selectedEntityIds}
            focusedEntityId={
              rectangleSelectionDetail?.kind === "edge"
                ? rectangleIdsFromBaseId(rectangleSelectionDetail.baseId).lineIds[rectangleSelectionDetail.edgeId]
                : rectangleSelectionDetail?.kind === "corner"
                  ? rectangleIdsFromBaseId(rectangleSelectionDetail.baseId).pointIds[rectangleSelectionDetail.cornerId]
                  : null
            }
            draftPoint={draftPoint}
            rectangleDraft={rectangleDraft}
            dragPreviewPoint={dragPreviewPoint}
            onCanvasClick={handleCanvasClick}
            onCanvasMouseDown={handleCanvasMouseDown}
            onCanvasMouseMove={handleCanvasMouseMove}
            onCanvasMouseUp={handleCanvasMouseUp}
            onCanvasContextMenu={handleCanvasContextMenu}
            onEntityClick={handleEntityClick}
            onEntityMouseDown={handleEntityMouseDown}
            onDimensionLabelEdit={handleDimensionLabelEdit}
          />
        </Box>

        <VStack align="stretch" spacing={4} className="sketchmath-sidebar">
          <Box className="sketchmath-panel" data-testid="sketchmath-workbench-panel">
            <Heading size="sm" mb={3} className="sketchmath-panel-title">
              Sketch Workbench
            </Heading>
            <VStack align="stretch" spacing={3}>
              <Box>
                <Text fontWeight="600">Sketch status</Text>
                <Text data-testid="sketchmath-status">{sketchStatus}</Text>
                <Text fontSize="sm" opacity={0.8}>
                  {dimensionSummary}
                </Text>
              </Box>
              <Box data-testid="sketchmath-selection-summary">
                <Text fontWeight="600">{selectionRef.summary}</Text>
                {selectionRef.parentSummary ? (
                  <Text fontSize="sm" opacity={0.85}>
                    {selectionRef.parentSummary}
                  </Text>
                ) : null}
                {selectionRef.detail ? (
                  <Text fontSize="sm" opacity={0.78}>
                    {selectionRef.detail}
                  </Text>
                ) : null}
              </Box>
              <Box>
                <Text fontWeight="600" mb={2}>
                  Context actions
                </Text>
                <HStack spacing={2} flexWrap="wrap">
                  <Input aria-label="SketchMath length" value={lengthValue} onChange={(event) => setLengthValue(event.target.value)} width="100px" />
                  <Input aria-label="SketchMath angle" value={angleValue} onChange={(event) => setAngleValue(event.target.value)} width="100px" />
                </HStack>
                <HStack spacing={2} flexWrap="wrap" mt={2}>
                  {selectionRef.canEditWidth ? (
                    <Button size="sm" onClick={() => rectangleSelectionDetail?.kind === "edge" && openDimensionEditor(rectangleSelectionDetail.baseId, "width")}>
                      Edit Width
                    </Button>
                  ) : null}
                  {selectionRef.canEditHeight ? (
                    <Button size="sm" onClick={() => rectangleSelectionDetail?.kind === "edge" && openDimensionEditor(rectangleSelectionDetail.baseId, "height")}>
                      Edit Height
                    </Button>
                  ) : null}
                  {selectionRef.canFixCorner ? (
                    <Button size="sm" onClick={() => void handleFixRectangleCorner()}>
                      Fix Corner
                    </Button>
                  ) : null}
                  <Button size="sm" onClick={() => void runQuickLength()} isDisabled={!selectionRef.canSetLength}>
                    Set Length
                  </Button>
                  <Button size="sm" onClick={() => void runQuickAngle()} isDisabled={!selectionRef.canSetAngle}>
                    Set Angle
                  </Button>
                  <Button size="sm" onClick={() => void runQuickParallel()} isDisabled={!selectionRef.canMakeParallel}>
                    Make Parallel
                  </Button>
                  <Button size="sm" onClick={() => void runQuickPerpendicular()} isDisabled={!selectionRef.canMakePerpendicular}>
                    Make Perpendicular
                  </Button>
                  <Button size="sm" onClick={() => void runQuickEqualLength()} isDisabled={!selectionRef.canEqualLength}>
                    Equal Length
                  </Button>
                  <Button size="sm" onClick={() => void runQuickEqualAngle()} isDisabled={pointSelectionIds.length < 6}>
                    Equal Angle
                  </Button>
                  <Button size="sm" onClick={() => void handleDeleteSelected()} isDisabled={selectedEntityIds.length === 0}>
                    Delete
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => void refreshSession()}>
                    Solve
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => void handleClearSketch()}>
                    Clear sketch
                  </Button>
                </HStack>
                <Text fontSize="sm" opacity={0.75} mt={2}>
                  Select geometry on the canvas, then apply constraints here.
                </Text>
              </Box>
              <Box>
                <Text fontWeight="600" mb={2}>
                  CAD feature
                </Text>
                <Text fontSize="sm" opacity={0.85} data-testid="sketchmath-profile-status">
                  {profileSummary}
                </Text>
                {hasUsableGeometry ? (
                  <Text fontSize="sm" opacity={0.85}>
                    Ready for CAD feature
                  </Text>
                ) : null}
                <HStack spacing={2} flexWrap="wrap" mt={2}>
                  <Input
                    type="number"
                    aria-label="Extrusion depth"
                    value={extrudeDepthValue}
                    onChange={(event) => setExtrudeDepthValue(event.target.value)}
                    width="110px"
                  />
                  <Button size="sm" onClick={handleCreateCadFeature} isDisabled={!hasUsableGeometry}>
                    Create CAD Feature
                  </Button>
                </HStack>
                {cadFeatureSummary ? (
                  <Text fontSize="sm" mt={2} data-testid="sketchmath-cad-feature-summary">
                    {cadFeatureSummary}
                  </Text>
                ) : null}
                <Text fontSize="sm" opacity={0.75} mt={2}>
                  {hasUsableGeometry ? "Closed profile is ready for extrusion." : "Draw or select a closed profile before extrusion."}
                </Text>
              </Box>
              <Button size="sm" variant="ghost" onClick={() => setAdvancedOpen((value) => !value)}>
                {advancedOpen ? "Hide Advanced / Debug" : "Show Advanced / Debug"}
              </Button>
            </VStack>
          </Box>

          <SelectionInspector
            selectedEntities={selectedEntities}
            sketchStatus={sketchStatus}
            constraintSummaries={constraintSummaries}
            dimensionSummary={dimensionSummary}
            rectangleDimensions={rectangleDimensions}
            rectangleSelectionDetail={rectangleSelectionDetail}
            rectangleAnchorSummary={rectangleAnchorSummary}
            profileSummary={profileSummary}
            rectangleWidthDraft={rectangleWidthDraft}
            rectangleHeightDraft={rectangleHeightDraft}
            dimensionEditor={dimensionEditor}
            deletePrompt={deletePrompt}
            showInternals={advancedOpen}
            namedReferences={committedContext.named_references}
            pendingCommandText={pendingCommandText}
            labelDraft={labelDraft}
            onLabelDraftChange={setLabelDraft}
            onRectangleWidthDraftChange={setRectangleWidthDraft}
            onRectangleHeightDraftChange={setRectangleHeightDraft}
            onApplyRectangleDimensions={handleApplyRectangleDimensions}
            onOpenDimensionEditor={(dimension) => {
              if (rectangleDimensions) {
                openDimensionEditor(rectangleDimensions.baseId, dimension);
              }
            }}
            onDimensionEditorValueChange={(value) => setDimensionEditor((current) => (current ? { ...current, value } : current))}
            onApplyDimensionEditor={handleApplyDimensionEditor}
            onSelectWholeRectangle={() => {
              if (rectangleDimensions) {
                setSelectedEntityIds(rectangleSelectionIds(rectangleDimensions.baseId));
                setRectangleSelectionDetail({ kind: "rectangle", baseId: rectangleDimensions.baseId });
              }
            }}
            onSelectProfile={() => {
              if (rectangleDimensions) {
                const ids = rectangleIdsFromBaseId(rectangleDimensions.baseId);
                setSelectedEntityIds([ids.profileId]);
                setRectangleSelectionDetail({ kind: "profile", baseId: rectangleDimensions.baseId });
              }
            }}
            onDeleteWholeRectangle={() => {
              if (deletePrompt?.kind === "rectangle") {
                void deleteRectangleCascade(deletePrompt.baseId);
              }
            }}
            onCancelDeletePrompt={() => setDeletePrompt(null)}
            onFixRectangleCorner={handleFixRectangleCorner}
            onApplyLabel={handleApplyLabel}
            onToggleLockSelected={handleToggleLockSelected}
            onDeleteSelected={handleDeleteSelected}
          />

          {advancedOpen ? (
            <>
              <MeasurementPanel previewResult={previewResult} />
              <CommandPanel
                pendingCommandText={pendingCommandText}
                onPendingCommandTextChange={setPendingCommandText}
                onPreview={executePreview}
                onCommit={executeCommit}
                onClearPreview={clearPreview}
                onRejectProposal={rejectProposal}
                onRevert={revertLast}
                error={error}
                selectedEntityIds={selectedEntityIds}
                selectedEntities={selectedEntities}
                translationOutcome={translationOutcome}
                onTranslate={handleTranslate}
              />
              <OperationHistoryPanel history={history} />
            </>
          ) : null}
        </VStack>
      </Box>
      <Button size="sm" variant="ghost" onClick={() => void refreshSession()} className="sketchmath-refresh">
        Refresh session
      </Button>
    </Box>
  );
};

export default SketchMathWorkspace;
