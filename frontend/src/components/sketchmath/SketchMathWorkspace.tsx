import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Box, Button, Heading, HStack, Input, Link, Spinner, Text, useColorMode, useToast, VStack } from "@chakra-ui/react";
import SketchCanvas2D from "./SketchCanvas2D";
import SolidPreview3D, { DEFAULT_SOLID_CAMERA } from "./SolidPreview3D";
import type { SolidCameraState } from "./SolidPreview3D";
import SketchMathToolbar from "./SketchMathToolbar";
import SelectionInspector from "./SelectionInspector";
import CommandPanel from "./CommandPanel";
import OperationHistoryPanel from "./OperationHistoryPanel";
import MeasurementPanel from "./MeasurementPanel";
import TelemetryEventList from "../telemetry/TelemetryEventList";
import type { TelemetryEvent } from "../../telemetry/sessionTelemetry";
import { makeTelemetryEvent } from "../../telemetry/sessionTelemetry";
import type {
  SketchMathCommand,
  SketchMathCommandResponse,
  SketchMathEntity,
  SketchMathHistoryEntry,
  SketchMathMode,
  SketchMathOperationResult,
  SketchMathPreviewMesh,
  SketchMathProfileCandidate,
  SketchMathSelectionContext,
  SketchMathSessionSnapshot,
  SketchMathTranslationOutcome,
} from "../../services/sketchmath";
import {
  SketchMathApiError,
  commitSketchMathCommand,
  createSketchMathSession,
  getSketchMathSession,
  isSketchMathEnabled,
  previewSketchMathCommand,
  redoSketchMathSession,
  revertSketchMathSession,
  sketchMathStepDownloadUrl,
  translateSketchMathUtterance,
  upsertSketchMathEntity,
} from "../../services/sketchmath";
import {
  buildAddProfileHoleCommand,
  buildDeleteEntityCommand,
  buildDefineLineCommand,
  buildDefinePointCommand,
  buildDefineCircleCommand,
  buildMakeCircleProfileCommand,
  buildUpdateCircleCommand,
  buildExtrudeProfileCommand,
  buildBatchCommand,
  buildEqualAngleCommand,
  buildEqualLengthCommand,
  buildMakeParallelCommand,
  buildMakePerpendicularCommand,
  buildMakeProfileCommand,
  buildSolveConstraintsCommand,
  buildHorizontalCommand,
  buildVerticalCommand,
  buildCoincidentCommand,
  buildDetectProfilesCommand,
  buildMovePointCommand,
  buildSetLengthCommand,
  buildSetRectangleDimensionCommand,
  buildUpdateProfileHoleCommand,
} from "./commandBuilders";

const CANVAS_WIDTH = 1200;
const CANVAS_HEIGHT = 800;
const SESSION_STORAGE_KEY = "friday_sketchmath_session_id";
const ISO_CAMERA_ANGLES = { yaw: -0.72, pitch: -0.54 };
const TILT_CAMERA_ANGLES = { yaw: 0, pitch: -0.61 };

type Point = { x: number; y: number };
type ViewBoxState = { x: number; y: number; width: number; height: number };
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
type HolePlacementState = { profileId: string; baseId: string | null; center: Point; message: string } | null;
type HoleSelectionSummary = { holeId: string; profileId: string; diameter: number; center: Point };
type WorkspaceViewMode = "sketch" | "solid";
type CircleDraft = { center: Point; current: Point };
type CadExportArtifact = {
  stepPath: string;
  filename: string;
  sizeBytes: number | null;
  createdAt: string | null;
  profileId: string | null;
  extrusionDepth: number | null;
  extrusionDepthUnit: string | null;
};
type SelectionRef = {
  kind: "none" | "rectangle_edge" | "rectangle_corner" | "rectangle_profile" | "profile_hole" | "rectangle" | "circle" | "one_line" | "two_lines" | "one_point" | "two_points" | "mixed";
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
  canMakeHorizontal: boolean;
  canMakeVertical: boolean;
  canMakeCoincident: boolean;
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

const isCircleEntity = (entity: SketchMathEntity): entity is Extract<SketchMathEntity, { type: "circle_2d" }> => entity.type === "circle_2d";

const pointsMatch = (point: SketchMathEntity | undefined, coords: [number, number]): point is Extract<SketchMathEntity, { type: "point_2d" }> =>
  !!point && isPointEntity(point) && point.coords[0] === coords[0] && point.coords[1] === coords[1];

const distanceBetween = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y);

const profileCenter = (profile: Extract<SketchMathEntity, { type: "profile_2d" }>): Point | null => {
  const vertices = profile.vertices.filter((vertex, index) => index === 0 || vertex[0] !== profile.vertices[0][0] || vertex[1] !== profile.vertices[0][1]);
  if (vertices.length === 0) {
    return null;
  }
  const xs = vertices.map((vertex) => vertex[0]);
  const ys = vertices.map((vertex) => vertex[1]);
  return {
    x: Number(((Math.min(...xs) + Math.max(...xs)) / 2).toFixed(2)),
    y: Number(((Math.min(...ys) + Math.max(...ys)) / 2).toFixed(2)),
  };
};

const profileBounds = (profile: Extract<SketchMathEntity, { type: "profile_2d" }>): ViewBoxState | null => {
  const vertices = profile.vertices.filter((vertex, index) => index === 0 || vertex[0] !== profile.vertices[0][0] || vertex[1] !== profile.vertices[0][1]);
  if (vertices.length === 0) {
    return null;
  }
  const xs = vertices.map((vertex) => vertex[0]);
  const ys = vertices.map((vertex) => vertex[1]);
  return {
    x: Math.min(...xs),
    y: Math.min(...ys),
    width: Math.max(...xs) - Math.min(...xs),
    height: Math.max(...ys) - Math.min(...ys),
  };
};

const fittedViewBoxFromBounds = (bounds: ViewBoxState | null): ViewBoxState => {
  if (!bounds) {
    return { x: 0, y: 0, width: CANVAS_WIDTH, height: CANVAS_HEIGHT };
  }
  const padding = 80;
  const minX = bounds.x - padding;
  const maxX = bounds.x + bounds.width + padding;
  const minY = bounds.y - padding;
  const maxY = bounds.y + bounds.height + padding;
  const width = Math.max(180, maxX - minX);
  const height = Math.max(140, maxY - minY);
  const aspect = CANVAS_WIDTH / CANVAS_HEIGHT;
  const fittedWidth = width / height > aspect ? width : height * aspect;
  const fittedHeight = fittedWidth / aspect;
  return {
    x: minX - (fittedWidth - width) / 2,
    y: minY - (fittedHeight - height) / 2,
    width: fittedWidth,
    height: fittedHeight,
  };
};

const profileDiameterAndCenter = (profile: Extract<SketchMathEntity, { type: "profile_2d" }>): { diameter: number; center: Point } | null => {
  const vertices = profile.vertices.filter((vertex, index) => index === 0 || vertex[0] !== profile.vertices[0][0] || vertex[1] !== profile.vertices[0][1]);
  if (vertices.length === 0) {
    return null;
  }
  const xs = vertices.map((vertex) => vertex[0]);
  const ys = vertices.map((vertex) => vertex[1]);
  const width = Math.max(...xs) - Math.min(...xs);
  const height = Math.max(...ys) - Math.min(...ys);
  return {
    diameter: Number(Math.max(width, height).toFixed(2)),
    center: {
      x: Number(((Math.min(...xs) + Math.max(...xs)) / 2).toFixed(2)),
      y: Number(((Math.min(...ys) + Math.max(...ys)) / 2).toFixed(2)),
    },
  };
};

const fileNameFromPath = (path: string): string => path.split(/[\\/]/).filter(Boolean).pop() || "export.step";

const isPreviewMesh = (value: unknown): value is SketchMathPreviewMesh => {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<SketchMathPreviewMesh>;
  return candidate.version === "0.1" && Array.isArray(candidate.vertices) && Array.isArray(candidate.triangles);
};

const previewMeshFromResult = (result: SketchMathOperationResult | null): SketchMathPreviewMesh | null => {
  const mesh = result?.metadata?.preview_mesh;
  return isPreviewMesh(mesh) ? mesh : null;
};

const pointInsideProfile = (point: Point, profile: Extract<SketchMathEntity, { type: "profile_2d" }>): boolean => {
  const vertices = profile.vertices;
  if (vertices.length < 4) {
    return false;
  }
  let inside = false;
  for (let index = 0, previous = vertices.length - 1; index < vertices.length; previous = index++) {
    const currentVertex = vertices[index];
    const previousVertex = vertices[previous];
    const intersects =
      (currentVertex[1] > point.y) !== (previousVertex[1] > point.y) &&
      point.x < ((previousVertex[0] - currentVertex[0]) * (point.y - currentVertex[1])) / (previousVertex[1] - currentVertex[1]) + currentVertex[0];
    if (intersects) {
      inside = !inside;
    }
  }
  return inside;
};

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
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [selectedEntityIds, setSelectedEntityIds] = useState<string[]>([]);
  const [previewResult, setPreviewResult] = useState<SketchMathOperationResult | null>(null);
  const [draftPoint, setDraftPoint] = useState<Point | null>(null);
  const [rectangleDraft, setRectangleDraft] = useState<RectangleDraft | null>(null);
  const [circleDraft, setCircleDraft] = useState<CircleDraft | null>(null);
  const [profileCandidates, setProfileCandidates] = useState<SketchMathProfileCandidate[]>([]);
  const [solverOutcome, setSolverOutcome] = useState<"Solved" | "Conflict" | "Solve failed" | null>(null);
  const [dragPreviewPoint, setDragPreviewPoint] = useState<{ id: string; point: Point } | null>(null);
  const [tool, setTool] = useState<SketchMathMode>("select");
  const [workspaceViewMode, setWorkspaceViewMode] = useState<WorkspaceViewMode>("sketch");
  const [viewBoxState, setViewBoxState] = useState<ViewBoxState>({ x: 0, y: 0, width: CANVAS_WIDTH, height: CANVAS_HEIGHT });
  const [solidCamera, setSolidCamera] = useState<SolidCameraState>({
    ...DEFAULT_SOLID_CAMERA,
    targetX: CANVAS_WIDTH / 2,
    targetY: CANVAS_HEIGHT / 2,
  });
  const [showDebugLabels, setShowDebugLabels] = useState(false);
  const [pendingCommandText, setPendingCommandText] = useState("");
  const [translationOutcome, setTranslationOutcome] = useState<SketchMathTranslationOutcome | null>(null);
  const [labelDraft, setLabelDraft] = useState("");
  const [lengthValue, setLengthValue] = useState("17.5");
  const [rectangleWidthDraft, setRectangleWidthDraft] = useState("");
  const [rectangleHeightDraft, setRectangleHeightDraft] = useState("");
  const [rectangleSelectionDetail, setRectangleSelectionDetail] = useState<RectangleSelectionDetail | null>(null);
  const [dimensionEditor, setDimensionEditor] = useState<DimensionEditorState>(null);
  const [deletePrompt, setDeletePrompt] = useState<DeletePromptState>(null);
  const [extrudeDepthValue, setExtrudeDepthValue] = useState("10");
  const [holeDiameterValue, setHoleDiameterValue] = useState("8");
  const [circleRadiusValue, setCircleRadiusValue] = useState("10");
  const [selectedHoleDiameterDraft, setSelectedHoleDiameterDraft] = useState("");
  const [selectedHoleCenterXDraft, setSelectedHoleCenterXDraft] = useState("");
  const [selectedHoleCenterYDraft, setSelectedHoleCenterYDraft] = useState("");
  const [holeEditorMessage, setHoleEditorMessage] = useState<string | null>(null);
  const [holePlacement, setHolePlacement] = useState<HolePlacementState>(null);
  const [cadFeatureSummary, setCadFeatureSummary] = useState<string | null>(null);
  const [solidPreviewMesh, setSolidPreviewMesh] = useState<SketchMathPreviewMesh | null>(null);
  const [cadExportPath, setCadExportPath] = useState<string | null>(null);
  const [cadExportArtifact, setCadExportArtifact] = useState<CadExportArtifact | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [constraintsOpen, setConstraintsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorDebugText, setErrorDebugText] = useState<string | null>(null);
  const [systemEvents, setSystemEvents] = useState<TelemetryEvent[]>([]);
  const canvasDragRef = useRef<{ start: Point; moved: boolean; forceSquare: boolean } | null>(null);
  const viewPanRef = useRef<{ last: Point } | null>(null);
  const pointDragRef = useRef<{ entityId: string; start: Point; current: Point; moved: boolean } | null>(null);
  const dragPreviewTimerRef = useRef<number | null>(null);
  const ignoreNextCanvasClickRef = useRef(false);
  const notifiedArtifactPathsRef = useRef<Set<string>>(new Set());
  const lastSelectedHoleIdRef = useRef<string | null>(null);

  useEffect(() => {
    document.documentElement.dataset.fridayTheme = colorMode;
  }, [colorMode]);

  const appendEvents = useCallback((events: TelemetryEvent[]) => {
    setSystemEvents((previous) => [...[...events].reverse(), ...previous].slice(0, 16));
  }, []);

  const clearErrorState = () => {
    setError(null);
    setErrorDebugText(null);
  };

  const setUserError = (message: string, debugText?: string | null) => {
    setError(message);
    setErrorDebugText(debugText || null);
  };

  const normalizeCaughtError = (err: unknown, fallback: string): { message: string; debugText: string | null } => {
    if (err instanceof SketchMathApiError) {
      return { message: err.message, debugText: err.debugText };
    }
    if (err instanceof Error) {
      return { message: err.message || fallback, debugText: err.stack || err.message };
    }
    return { message: fallback, debugText: null };
  };

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
        appendEvents([
          makeTelemetryEvent("workspace_initialized", {
            detail: `SketchMath session ${snapshot.session_id} ready.`,
            raw: {
              session_id: snapshot.session_id,
              storage_path: snapshot.session_metadata?.storage_path,
              entities: snapshot.selection_context.items.length,
              constraints: snapshot.selection_context.constraints.length,
              history_length: snapshot.history_length,
            },
          }),
        ]);
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
          appendEvents([
            makeTelemetryEvent("fallback_attempted", {
              detail: "Stored SketchMath session could not be restored; a new session was created.",
              raw: initialError instanceof Error ? { message: initialError.message, stack: initialError.stack } : initialError,
            }),
            makeTelemetryEvent("workspace_initialized", {
              detail: `SketchMath session ${snapshot.session_id} ready.`,
              raw: {
                session_id: snapshot.session_id,
                storage_path: snapshot.session_metadata?.storage_path,
                entities: snapshot.selection_context.items.length,
                constraints: snapshot.selection_context.constraints.length,
                history_length: snapshot.history_length,
              },
            }),
          ]);
        } catch (err) {
          if (!cancelled) {
            const { message: detail, debugText } = normalizeCaughtError(err, "Failed to initialize SketchMath");
            setUserError(detail, debugText);
            appendEvents([
              makeTelemetryEvent("request_failed", {
                detail,
                raw: err instanceof Error ? { message: err.message, stack: err.stack } : err,
              }),
            ]);
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
  }, [appendEvents, enabled]);

  useEffect(() => {
    if (!cadExportPath || notifiedArtifactPathsRef.current.has(cadExportPath)) {
      return;
    }
    notifiedArtifactPathsRef.current.add(cadExportPath);
    appendEvents([
      makeTelemetryEvent("artifact_created", {
        detail: `STEP export available: ${cadExportPath}`,
        raw: { path: cadExportPath, workspace: "sketchmath" },
      }),
    ]);
  }, [appendEvents, cadExportPath]);

  const committedEntities = committedContext.items;
  const selectedEntities = useMemo(
    () => committedEntities.filter((entity) => selectedEntityIds.includes(entity.id)),
    [committedEntities, selectedEntityIds],
  );
  const selectedPointEntities = useMemo(() => selectedEntities.filter(isPointEntity), [selectedEntities]);
  const profileHoleParentById = useMemo(() => {
    const map = new Map<string, string>();
    committedEntities.filter(isClosedProfileEntity).forEach((profile) => {
      (profile.holes || []).forEach((holeId) => map.set(holeId, profile.id));
    });
    return map;
  }, [committedEntities]);
  const profileHoleIds = useMemo(() => new Set(profileHoleParentById.keys()), [profileHoleParentById]);
  const closedProfileEntity = useMemo(
    () =>
      committedEntities.find(
        (entity): entity is Extract<SketchMathEntity, { type: "profile_2d" }> => isClosedProfileEntity(entity) && !profileHoleIds.has(entity.id),
      ) || null,
    [committedEntities, profileHoleIds],
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
  const selectedClosedProfile = useMemo(
    () =>
      selectedEntities.find(
        (entity): entity is Extract<SketchMathEntity, { type: "profile_2d" }> => isClosedProfileEntity(entity) && !profileHoleIds.has(entity.id),
      ) || null,
    [profileHoleIds, selectedEntities],
  );
  const selectedCircle = useMemo(() => selectedEntities.find(isCircleEntity) || null, [selectedEntities]);
  const selectedCircleProfile = useMemo(() => {
    if (!selectedCircle) return null;
    const profile = committedEntities.find((entity) => entity.id === `profile_${selectedCircle.id}`);
    return profile && isClosedProfileEntity(profile) ? profile : null;
  }, [committedEntities, selectedCircle]);
  const circleHoleTarget = useMemo(
    () => selectedEntities.find((entity): entity is Extract<SketchMathEntity, { type: "profile_2d" }> => isClosedProfileEntity(entity) && entity.id !== selectedCircleProfile?.id) || null,
    [selectedCircleProfile, selectedEntities],
  );
  const selectedHoleEntity = useMemo(
    () =>
      selectedEntities.length === 1 && isClosedProfileEntity(selectedEntities[0]) && profileHoleIds.has(selectedEntities[0].id)
        ? selectedEntities[0]
        : null,
    [profileHoleIds, selectedEntities],
  );
  const selectedHoleSummary = useMemo<HoleSelectionSummary | null>(() => {
    if (!selectedHoleEntity) {
      return null;
    }
    const profileId = profileHoleParentById.get(selectedHoleEntity.id);
    const geometry = profileDiameterAndCenter(selectedHoleEntity);
    if (!profileId || !geometry) {
      return null;
    }
    return { holeId: selectedHoleEntity.id, profileId, diameter: geometry.diameter, center: geometry.center };
  }, [profileHoleParentById, selectedHoleEntity]);
  const selectedHoleParentProfile = useMemo(() => {
    if (!selectedHoleSummary) {
      return null;
    }
    const profile = committedEntities.find((entity) => entity.id === selectedHoleSummary.profileId);
    return profile && isClosedProfileEntity(profile) ? profile : null;
  }, [committedEntities, selectedHoleSummary]);
  const activeProfileForHole = selectedRectangleProfile || selectedClosedProfile || selectedHoleParentProfile;
  const activeProfileHoleCount = activeProfileForHole ? activeProfileForHole.holes?.length || 0 : null;
  const activeProfileForCad = selectedRectangleProfile || selectedClosedProfile || selectedCircleProfile || selectedHoleParentProfile;
  const allGeometryBounds = useMemo<ViewBoxState | null>(() => {
    const points = committedEntities.flatMap((entity) => {
      if (isPointEntity(entity)) {
        return [{ x: entity.coords[0], y: entity.coords[1] }];
      }
      if (isLineEntity(entity)) {
        return [
          { x: entity.start[0], y: entity.start[1] },
          { x: entity.end[0], y: entity.end[1] },
        ];
      }
      if (isClosedProfileEntity(entity)) {
        return entity.vertices.map((vertex) => ({ x: vertex[0], y: vertex[1] }));
      }
      return [];
    });
    if (points.length === 0) {
      return null;
    }
    const xs = points.map((point) => point.x);
    const ys = points.map((point) => point.y);
    return {
      x: Math.min(...xs),
      y: Math.min(...ys),
      width: Math.max(...xs) - Math.min(...xs),
      height: Math.max(...ys) - Math.min(...ys),
    };
  }, [committedEntities]);
  const cameraProfile = activeProfileForCad || activeProfileForHole || closedProfileEntity;
  const cameraTarget = cameraProfile ? profileCenter(cameraProfile) : null;
  const cameraFitViewBox = fittedViewBoxFromBounds((cameraProfile && profileBounds(cameraProfile)) || allGeometryBounds);
  const solidTargetZ = (mesh: SketchMathPreviewMesh | null): number => {
    const bbox = mesh?.metadata?.bbox;
    return bbox ? Number(((bbox.zmin + bbox.zmax) / 2).toFixed(2)) : 0;
  };
  const cameraFromSketchView = useCallback(
    (angles: { yaw: number; pitch: number } = { yaw: 0, pitch: -Math.PI / 2 }): SolidCameraState => {
      const target = cameraTarget || {
        x: Number((viewBoxState.x + viewBoxState.width / 2).toFixed(2)),
        y: Number((viewBoxState.y + viewBoxState.height / 2).toFixed(2)),
      };
      const carriedZoom = Math.max(1, Math.min(4, cameraFitViewBox.width / viewBoxState.width));
      return {
        ...DEFAULT_SOLID_CAMERA,
        ...angles,
        zoom: Number(carriedZoom.toFixed(2)),
        targetX: target.x,
        targetY: target.y,
        targetZ: solidTargetZ(solidPreviewMesh),
      };
    },
    [cameraFitViewBox.width, cameraTarget, solidPreviewMesh, viewBoxState],
  );
  const viewBoxFromCamera = useCallback(
    (camera: SolidCameraState): ViewBoxState => {
      const zoom = Math.max(0.35, camera.zoom);
      const width = Math.max(120, Math.min(CANVAS_WIDTH * 2, cameraFitViewBox.width / zoom));
      const height = width / (CANVAS_WIDTH / CANVAS_HEIGHT);
      return {
        x: camera.targetX - width / 2,
        y: camera.targetY - height / 2,
        width,
        height,
      };
    },
    [cameraFitViewBox.width],
  );
  const switchWorkspaceView = useCallback(
    (mode: WorkspaceViewMode) => {
      if (mode === "solid") {
        setSolidCamera(cameraFromSketchView());
      } else {
        setViewBoxState(viewBoxFromCamera(solidCamera));
      }
      setWorkspaceViewMode(mode);
    },
    [cameraFromSketchView, solidCamera, viewBoxFromCamera],
  );
  const applySolidCameraPreset = useCallback(
    (preset: "fit" | "reset" | "top" | "iso" | "front" | "tilt") => {
      const fromSketch = cameraFromSketchView();
      setSolidCamera((current) => {
        const targetState = {
          targetX: fromSketch.targetX,
          targetY: fromSketch.targetY,
          targetZ: fromSketch.targetZ,
        };
        if (preset === "fit") {
          return { ...current, ...targetState, zoom: 1, panX: 0, panY: 0 };
        }
        if (preset === "reset") {
          return { ...fromSketch, zoom: 1, panX: 0, panY: 0 };
        }
        if (preset === "top") {
          return { ...current, ...targetState, yaw: 0, pitch: -Math.PI / 2, panX: 0, panY: 0 };
        }
        if (preset === "front") {
          return { ...current, ...targetState, yaw: 0, pitch: 0, panX: 0, panY: 0 };
        }
        if (preset === "tilt") {
          return { ...current, ...targetState, ...TILT_CAMERA_ANGLES, panX: 0, panY: 0 };
        }
        return { ...current, ...targetState, ...ISO_CAMERA_ANGLES, panX: 0, panY: 0 };
      });
    },
    [cameraFromSketchView],
  );
  const cadExportFileName = cadExportArtifact?.filename || (cadExportPath ? fileNameFromPath(cadExportPath) : null);
  const cadExportDownloadUrl = cadExportPath ? sketchMathStepDownloadUrl(cadExportPath) : null;
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

  useEffect(() => {
    if (selectedCircle) setCircleRadiusValue(String(selectedCircle.radius));
  }, [selectedCircle]);

  useEffect(() => {
    if (!selectedHoleSummary) {
      lastSelectedHoleIdRef.current = null;
      setSelectedHoleDiameterDraft("");
      setSelectedHoleCenterXDraft("");
      setSelectedHoleCenterYDraft("");
      setHoleEditorMessage(null);
      return;
    }
    const selectedHoleChanged = lastSelectedHoleIdRef.current !== selectedHoleSummary.holeId;
    lastSelectedHoleIdRef.current = selectedHoleSummary.holeId;
    setSelectedHoleDiameterDraft(String(selectedHoleSummary.diameter));
    setSelectedHoleCenterXDraft(String(selectedHoleSummary.center.x));
    setSelectedHoleCenterYDraft(String(selectedHoleSummary.center.y));
    if (selectedHoleChanged) {
      setHoleEditorMessage(null);
    }
  }, [selectedHoleSummary]);

  const sketchStatus = useMemo(() => {
    if (solverOutcome) return solverOutcome;
    return committedContext.constraints.length > 0 ? "Constraints present" : "No constraints";
  }, [committedContext.constraints.length, solverOutcome]);

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
      committedContext.constraints.filter((constraint) => {
        if (selectedEntityIds.length === 0) return true;
        const record = constraint as Record<string, unknown>;
        const references = Array.isArray(record.points) ? record.points : typeof record.point_id === "string" ? [record.point_id] : [];
        return references.some((entityId) => typeof entityId === "string" && selectedEntityIds.includes(entityId));
      }).map((constraint, index) => {
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
    [committedContext.constraints, selectedEntityIds],
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
      canMakeHorizontal: false,
      canMakeVertical: false,
      canMakeCoincident: false,
    };
    if (selectedEntityIds.length === 0) {
      return { ...base, kind: "none", summary: "Selected: Nothing" };
    }
    if (selectedHoleSummary) {
      return {
        ...base,
        kind: "profile_hole",
        summary: "Selected: Hole",
        parentSummary: "Parent: Profile",
        detail: `Diameter: ${selectedHoleSummary.diameter} mm`,
      };
    }
    if (rectangleSelectionDetail?.kind === "edge") {
      const edgeName = rectangleSelectionDetail.dimension === "width" ? "width" : "height";
      return {
        ...base,
        kind: "rectangle_edge",
        summary: `Selected: Rectangle ${edgeName} edge`,
        parentSummary: "Parent: Rectangle",
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
        parentSummary: "Parent: Rectangle",
        detail: "Angle: 90 deg",
        canFixCorner: true,
      };
    }
    if (rectangleSelectionDetail?.kind === "profile") {
      return { ...base, kind: "rectangle_profile", summary: "Selected: Profile", parentSummary: "Parent: Rectangle" };
    }
    if (selectedLineEntities.length === 2) {
      return {
        ...base,
        kind: "two_lines",
        summary: "Selected: 2 lines",
        detail: "Relationship constraints available for the selected lines.",
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
          parentSummary: "Parent: Rectangle",
          detail: `Edge ${rectangleEdgeLabel(edgeId)}`,
          canEditWidth: dimension === "width",
          canEditHeight: dimension === "height",
        };
      }
      return { ...base, kind: "one_line", summary: "Selected: 1 line", canSetLength: true, canMakeHorizontal: true, canMakeVertical: true };
    }
    if (selectedPointEntities.length === 2) {
      return { ...base, kind: "two_points", summary: "Selected: 2 points", canSetLength: true, canMakeCoincident: true };
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
      return { ...base, kind: "rectangle", summary: "Selected: Rectangle", parentSummary: "Parent: Rectangle", canFixCorner: true };
    }
    if (selectedEntities.length === 1 && isCircleEntity(selectedEntities[0])) {
      return { ...base, kind: "circle", summary: "Selected: Circle", detail: `Radius: ${selectedEntities[0].radius} mm` };
    }
    return { ...base, kind: "mixed", summary: `Selected: ${selectedEntityIds.length} entities` };
  }, [rectangleDimensions, rectangleSelectionDetail, selectedEntities, selectedEntityIds.length, selectedHoleSummary, selectedLineEntities, selectedPointEntities]);

  const syncSnapshot = (snapshot: SketchMathSessionSnapshot) => {
    setCommittedContext(snapshot.selection_context);
    setSessionMetadata(snapshot.session_metadata || {});
    setHistory(snapshot.history);
    setCanUndo(Boolean(snapshot.can_undo ?? snapshot.history_length > 0));
    setCanRedo(Boolean(snapshot.can_redo));
    window.localStorage.setItem(SESSION_STORAGE_KEY, snapshot.session_id);
  };

  const syncCommandResponse = (response: SketchMathCommandResponse) => {
    setCommittedContext(response.selection_context || response.result.after);
    setSessionMetadata(response.session_metadata || {});
    setHistory((current) => [
      ...current,
      {
        command: response.result.command,
        committed: response.result.status === "committed",
        before: response.result.before,
        after: response.result.after,
      },
    ]);
    setCanUndo(true);
    setCanRedo(false);
    window.localStorage.setItem(SESSION_STORAGE_KEY, response.session_id);
  };

  const refreshProfileCandidates = async () => {
    if (!sessionId) return;
    try {
      const response = await previewSketchMathCommand(sessionId, buildDetectProfilesCommand());
      const raw = response.result.metadata.profile_candidates;
      setProfileCandidates(Array.isArray(raw) ? raw as SketchMathProfileCandidate[] : []);
    } catch {
      setProfileCandidates([]);
    }
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
      syncCommandResponse(response);
      setPreviewResult(response.result);
      clearErrorState();
      const topologyCommands = new Set(["define_line", "batch", "move_point", "make_horizontal", "make_vertical", "make_coincident", "delete_entity"]);
      if (topologyCommands.has(nextCommand.command_type)) {
        void refreshProfileCandidates();
      } else if (["make_profile", "make_circle_profile"].includes(nextCommand.command_type)) {
        setProfileCandidates([]);
      }
      if (nextCommand.command_type === "solve_constraints") setSolverOutcome("Solved");
      return response.result;
    } catch (err) {
      const { message, debugText } = normalizeCaughtError(err, "Command failed");
      setUserError(message, debugText);
      if (nextCommand.command_type === "solve_constraints") {
        setSolverOutcome(message.toLowerCase().includes("conflict") ? "Conflict" : "Solve failed");
      }
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
      clearErrorState();
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
      const { message, debugText } = normalizeCaughtError(err, "Preview failed");
      setUserError(message, debugText);
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
      syncCommandResponse(response);
      setPreviewResult(response.result);
      setDraftPoint(null);
      clearRectangleInteraction();
      setSelectedEntityIds([]);
      setTranslationOutcome(null);
      clearErrorState();
      toast({
        title: "Committed",
        status: "success",
        duration: 1800,
        isClosable: true,
      });
    } catch (err) {
      const { message, debugText } = normalizeCaughtError(err, "Commit failed");
      setUserError(message, debugText);
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
    setHolePlacement(null);
    clearErrorState();
  };

  const clearSolidPreview = () => {
    setSolidPreviewMesh(null);
    setWorkspaceViewMode("sketch");
  };

  const previewCommand = async (command: SketchMathCommand): Promise<SketchMathOperationResult | null> => {
    if (!sessionId) {
      return null;
    }
    setPendingCommandText(asCommandText(command));
    try {
      const response = await previewSketchMathCommand(sessionId, command);
      setPreviewResult(response.result);
      clearErrorState();
      return response.result;
    } catch (err) {
      const { message, debugText } = normalizeCaughtError(err, "Preview failed");
      setUserError(message, debugText);
      toast({
        title: "Preview failed",
        description: message,
        status: "error",
        duration: 2500,
        isClosable: true,
      });
      return null;
    }
  };

  const rejectProposal = () => {
    setTranslationOutcome(null);
    setPendingCommandText("");
    setPreviewResult(null);
    clearErrorState();
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
      clearSolidPreview();
      setDraftPoint(null);
      clearRectangleInteraction();
      setTranslationOutcome(null);
      setPendingCommandText("");
      clearErrorState();
      toast({
        title: "Reverted",
        status: "info",
        duration: 1800,
        isClosable: true,
      });
    } catch (err) {
      const { message, debugText } = normalizeCaughtError(err, "Revert failed");
      setUserError(message, debugText);
    }
  };

  const redoNext = async () => {
    if (!sessionId) return;
    try {
      const snapshot = await redoSketchMathSession(sessionId);
      syncSnapshot(snapshot);
      setSelectedEntityIds([]);
      setPreviewResult(null);
      clearSolidPreview();
      clearErrorState();
    } catch (err) {
      const { message, debugText } = normalizeCaughtError(err, "Redo failed");
      setUserError(message, debugText);
    }
  };

  const clearDimensionPreview = () => {
    setPreviewResult(null);
    setPendingCommandText("");
    setHolePlacement(null);
    clearSolidPreview();
    clearErrorState();
  };

  const clearRectangleInteraction = () => {
    setRectangleDraft(null);
    setDragPreviewPoint(null);
    canvasDragRef.current = null;
    viewPanRef.current = null;
    pointDragRef.current = null;
  };

  const resetLocalInteractionState = () => {
    setSelectedEntityIds([]);
    setRectangleSelectionDetail(null);
    setDimensionEditor(null);
    setDeletePrompt(null);
    setHolePlacement(null);
    setPreviewResult(null);
    setDraftPoint(null);
    setCircleDraft(null);
    clearRectangleInteraction();
    setTranslationOutcome(null);
    setPendingCommandText("");
    setCadFeatureSummary(null);
    setSolidPreviewMesh(null);
    setCadExportPath(null);
    setCadExportArtifact(null);
    setHoleEditorMessage(null);
    clearErrorState();
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
    const commands = [
      buildDefinePointCommand(topLeft, ids.pointIds.a, "A"),
      buildDefinePointCommand(topRight, ids.pointIds.b, "B"),
      buildDefinePointCommand(bottomRight, ids.pointIds.c, "C"),
      buildDefinePointCommand(bottomLeft, ids.pointIds.d, "D"),
      buildDefineLineCommand(topLeft, topRight, ids.lineIds.ab, "AB", ids.pointIds.a, ids.pointIds.b),
      buildDefineLineCommand(topRight, bottomRight, ids.lineIds.bc, "BC", ids.pointIds.b, ids.pointIds.c),
      buildDefineLineCommand(bottomRight, bottomLeft, ids.lineIds.cd, "CD", ids.pointIds.c, ids.pointIds.d),
      buildDefineLineCommand(bottomLeft, topLeft, ids.lineIds.da, "DA", ids.pointIds.d, ids.pointIds.a),
      buildMakeParallelCommand([ids.pointIds.a, ids.pointIds.b, ids.pointIds.c, ids.pointIds.d]),
      buildMakeParallelCommand([ids.pointIds.b, ids.pointIds.c, ids.pointIds.d, ids.pointIds.a]),
      buildMakePerpendicularCommand([ids.pointIds.a, ids.pointIds.b, ids.pointIds.b, ids.pointIds.c]),
      buildSolveConstraintsCommand(),
      buildMakeProfileCommand([ids.lineIds.ab, ids.lineIds.bc, ids.lineIds.cd, ids.lineIds.da], ids.profileId),
    ];
    const command = buildBatchCommand(commands.map((subcommand) => ({ ...subcommand, mode: "commit" as const })));
    const result = await commitCommand(command);
    if (!result) {
      return;
    }
    clearSolidPreview();
    setCadExportPath(null);
    setCadExportArtifact(null);
    setCadFeatureSummary(null);
    setSelectedEntityIds([ids.profileId]);
    setRectangleSelectionDetail({ kind: "profile", baseId });
    setTranslationOutcome(null);
  };

  const handleCanvasClick = (point: Point) => {
    if (ignoreNextCanvasClickRef.current) {
      ignoreNextCanvasClickRef.current = false;
      return;
    }
    if (holePlacement) {
      const profile = committedEntities.find((entity): entity is Extract<SketchMathEntity, { type: "profile_2d" }> => entity.id === holePlacement.profileId && isClosedProfileEntity(entity));
      const center = { x: Number(point.x.toFixed(2)), y: Number(point.y.toFixed(2)) };
      if (!profile || !pointInsideProfile(center, profile)) {
        setHolePlacement((current) =>
          current
            ? {
                ...current,
                message: "That point is outside the selected profile. Click inside the selected profile.",
              }
            : current,
        );
        setUserError("Hole center must be inside the selected profile");
        return;
      }
      setHolePlacement((current) => (current ? { ...current, center } : current));
      void commitProfileHole(center);
      return;
    }
    if (tool === "point") {
      const pointId = `point_${Date.now().toString(36)}`;
      const nextCommand = buildDefinePointCommand(point, pointId);
      setDraftPoint(point);
      void commitCommand(nextCommand);
      setDraftPoint(null);
      setCircleDraft(null);
      setSelectedEntityIds([pointId]);
      setTranslationOutcome(null);
      return;
    }
    if (tool === "line") {
      if (!draftPoint) {
        setDraftPoint(point);
        clearErrorState();
        return;
      }
      const stamp = Date.now().toString(36);
      const startPointId = `point_${stamp}_start`;
      const endPointId = `point_${stamp}_end`;
      const lineId = `line_${stamp}`;
      const commands = [
        buildDefinePointCommand(draftPoint, startPointId),
        buildDefinePointCommand(point, endPointId),
        buildDefineLineCommand(draftPoint, point, lineId, lineId, startPointId, endPointId),
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
    if (tool === "circle") {
      if (!circleDraft) {
        setCircleDraft({ center: point, current: point });
        return;
      }
      const radius = Number(distanceBetween(circleDraft.center, point).toFixed(2));
      if (radius <= 0) return;
      const stamp = Date.now().toString(36);
      const circleId = `circle_${stamp}`;
      const centerId = `${circleId}_center`;
      const commands = [
        buildDefinePointCommand(circleDraft.center, centerId, "Center"),
        buildDefineCircleCommand(circleDraft.center, radius, circleId, centerId),
        buildMakeCircleProfileCommand(circleId, `profile_${circleId}`),
      ];
      setCircleDraft(null);
      void (async () => {
        const result = await commitCommand(buildBatchCommand(commands));
        if (result) setSelectedEntityIds([circleId]);
      })();
      return;
    }
    if (tool === "rectangle") {
      if (!rectangleDraft) {
        setRectangleDraft({ anchor: point, current: point });
        clearErrorState();
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
    if (tool === "pan" && event.button === 0) {
      viewPanRef.current = { last: point };
      return;
    }
    if (tool !== "rectangle" || event.button !== 0) {
      return;
    }
    canvasDragRef.current = { start: point, moved: false, forceSquare: event.shiftKey };
  };

  const handleCanvasMouseMove = (point: Point, event: React.MouseEvent<SVGSVGElement>) => {
    if (viewPanRef.current) {
      const deltaX = viewPanRef.current.last.x - point.x;
      const deltaY = viewPanRef.current.last.y - point.y;
      viewPanRef.current = { last: point };
      setViewBoxState((current) => {
        const nextViewBox = { ...current, x: current.x + deltaX, y: current.y + deltaY };
        setSolidCamera((currentCamera) => ({
          ...currentCamera,
          targetX: cameraTarget?.x ?? Number((nextViewBox.x + nextViewBox.width / 2).toFixed(2)),
          targetY: cameraTarget?.y ?? Number((nextViewBox.y + nextViewBox.height / 2).toFixed(2)),
          targetZ: solidTargetZ(solidPreviewMesh),
        }));
        return nextViewBox;
      });
      return;
    }
    if (pointDragRef.current) {
      const drag = pointDragRef.current;
      const resolvedPoint = { x: Number(point.x.toFixed(2)), y: Number(point.y.toFixed(2)) };
      if (!drag.moved && distanceBetween(drag.start, resolvedPoint) < RECTANGLE_DRAG_THRESHOLD) {
        return;
      }
      drag.moved = true;
      drag.current = resolvedPoint;
      setDragPreviewPoint({ id: drag.entityId, point: resolvedPoint });
      if (dragPreviewTimerRef.current !== null) window.clearTimeout(dragPreviewTimerRef.current);
      dragPreviewTimerRef.current = window.setTimeout(() => {
        void previewCommand(buildMovePointCommand(drag.entityId, resolvedPoint));
      }, 80);
    }
    if (tool === "circle" && circleDraft) {
      setCircleDraft({ ...circleDraft, current: point });
      return;
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
    if (viewPanRef.current) {
      viewPanRef.current = null;
      return;
    }
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
        await commitCommand(buildMovePointCommand(entity.id, updatedPoint));
      })();
      pointDragRef.current = null;
      if (dragPreviewTimerRef.current !== null) window.clearTimeout(dragPreviewTimerRef.current);
      dragPreviewTimerRef.current = null;
      setDragPreviewPoint(null);
      clearErrorState();
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
      clearErrorState();
    }
    if (tool === "pan") {
      viewPanRef.current = null;
    }
  };

  const resetView = () => {
    const nextViewBox = cameraProfile ? cameraFitViewBox : { x: 0, y: 0, width: CANVAS_WIDTH, height: CANVAS_HEIGHT };
    setViewBoxState(nextViewBox);
    setSolidCamera({ ...cameraFromSketchView(), zoom: 1, panX: 0, panY: 0 });
  };

  const zoomView = (factor: number) => {
    setViewBoxState((current) => {
      const nextWidth = Math.max(120, Math.min(CANVAS_WIDTH * 2, current.width * factor));
      const nextHeight = Math.max(80, Math.min(CANVAS_HEIGHT * 2, current.height * factor));
      const nextViewBox = {
        x: current.x + (current.width - nextWidth) / 2,
        y: current.y + (current.height - nextHeight) / 2,
        width: nextWidth,
        height: nextHeight,
      };
      const target = cameraTarget || {
        x: Number((nextViewBox.x + nextViewBox.width / 2).toFixed(2)),
        y: Number((nextViewBox.y + nextViewBox.height / 2).toFixed(2)),
      };
      setSolidCamera((currentCamera) => ({
        ...currentCamera,
        zoom: Number(Math.max(1, Math.min(4, cameraFitViewBox.width / nextViewBox.width)).toFixed(2)),
        targetX: target.x,
        targetY: target.y,
        targetZ: solidTargetZ(solidPreviewMesh),
      }));
      return nextViewBox;
    });
  };

  const fitSketchToView = () => {
    const nextViewBox = cameraFitViewBox;
    setViewBoxState(nextViewBox);
    setSolidCamera((current) => ({
      ...current,
      zoom: 1,
      panX: 0,
      panY: 0,
      targetX: cameraTarget?.x ?? nextViewBox.x + nextViewBox.width / 2,
      targetY: cameraTarget?.y ?? nextViewBox.y + nextViewBox.height / 2,
      targetZ: solidTargetZ(solidPreviewMesh),
    }));
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
      const isModifierSelection = event.shiftKey || event.ctrlKey || event.metaKey;
      const isAdvancedEdgeMode = tool === "dimension" || constraintsOpen;
      if (isModifierSelection) {
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
          clearErrorState();
          return;
        }
        toggleSelection([entityId]);
        setDimensionEditor(null);
        setDeletePrompt(null);
        clearErrorState();
        return;
      }
      if (!isAdvancedEdgeMode) {
        const ids = rectangleIdsFromBaseId(rectangleBaseId);
        setSelectedEntityIds([ids.profileId]);
        setRectangleSelectionDetail({ kind: "profile", baseId: rectangleBaseId });
        setDimensionEditor(null);
        setDeletePrompt(null);
        clearErrorState();
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
      clearErrorState();
      return;
    }
    const nextGroup = entity && isLineEntity(entity) ? lineSelectionGroup(entity) : [entityId];
    if (event.shiftKey || event.ctrlKey || event.metaKey) {
      toggleSelection(entity && isLineEntity(entity) ? [entity.id] : nextGroup);
    } else {
      setSelectedEntityIds(nextGroup);
      setRectangleSelectionDetail(null);
    }
    setDimensionEditor(null);
    setDeletePrompt(null);
    clearErrorState();
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
    clearErrorState();
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
    clearErrorState();
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
    clearErrorState();
  };

  const commitRectangleDimension = async (
    dimension: "width" | "height",
    value: number,
    baseId = rectangleDimensions?.baseId,
    activeRectangleDetail: RectangleSelectionDetail | null = rectangleSelectionDetail,
  ): Promise<boolean> => {
    if (!sessionId || !baseId) {
      setUserError("Select a rectangle before applying dimensions");
      return false;
    }
    if (!Number.isFinite(value) || value <= 0) {
      setUserError("Rectangle dimension must be a positive number");
      return false;
    }
    const command = buildSetRectangleDimensionCommand(rectangleSelectionIds(baseId), dimension, value, "mm");
    const result = await commitCommand(command);
    if (!result) {
      return false;
    }
    setDimensionEditor(null);
    setPreviewResult(null);
    clearSolidPreview();
    setPendingCommandText(asCommandText({ ...command, mode: "commit" }));
    restoreRectangleSelection(baseId, activeRectangleDetail);
    return true;
  };

  const restoreRectangleSelection = (baseId: string, activeRectangleDetail: RectangleSelectionDetail | null) => {
    const ids = rectangleIdsFromBaseId(baseId);
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
      setSelectedEntityIds(rectangleSelectionIds(baseId));
      setRectangleSelectionDetail(activeRectangleDetail?.kind === "rectangle" ? activeRectangleDetail : null);
    }
  };

  const applyRectangleDimensions = async (width: number, height: number) => {
    if (!rectangleDimensions) {
      return;
    }
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
      setUserError("Rectangle width and height must be positive numbers");
      return;
    }
    const baseId = rectangleDimensions.baseId;
    const activeRectangleDetail = rectangleSelectionDetail?.baseId === baseId ? rectangleSelectionDetail : { kind: "rectangle" as const, baseId };
    let currentWidth = rectangleDimensions.width;
    let currentHeight = rectangleDimensions.height;
    if (width !== currentWidth) {
      const applied = await commitRectangleDimension("width", width, baseId, activeRectangleDetail);
      if (!applied) {
        return;
      }
      currentWidth = width;
    }
    if (height !== currentHeight) {
      await commitRectangleDimension("height", height, baseId, activeRectangleDetail);
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
    await commitRectangleDimension(dimensionEditor.dimension, value, dimensionEditor.baseId, rectangleSelectionDetail);
  };

  const commitPreview = async () => {
    if (!previewResult) {
      return;
    }
    const previewCommandPayload = previewResult.command;
    const activeRectangleDetail = rectangleDimensions?.baseId && rectangleSelectionDetail?.baseId === rectangleDimensions.baseId ? rectangleSelectionDetail : null;
    const baseId = previewCommandPayload.selection.map(rectangleBaseIdFromEntityId).find((value): value is string => Boolean(value)) || rectangleDimensions?.baseId || null;
    const result = await commitCommand(previewCommandPayload);
    if (!result) {
      return;
    }
    if (previewCommandPayload.command_type === "set_rectangle_dimension" && baseId) {
      setDimensionEditor(null);
      restoreRectangleSelection(baseId, activeRectangleDetail);
      return;
    }
    if (previewCommandPayload.command_type === "add_profile_hole") {
      const profileId = previewCommandPayload.selection[0];
      setSelectedEntityIds(profileId ? [profileId] : []);
      const profileBaseId = profileId ? rectangleBaseIdFromEntityId(profileId) : null;
      setRectangleSelectionDetail(profileBaseId ? { kind: "profile", baseId: profileBaseId } : null);
      setHolePlacement(null);
      clearSolidPreview();
      return;
    }
    if (previewCommandPayload.command_type === "extrude_profile") {
      const profileId = previewCommandPayload.selection[0];
      setSelectedEntityIds(profileId ? [profileId] : []);
      const profileBaseId = profileId ? rectangleBaseIdFromEntityId(profileId) : null;
      setRectangleSelectionDetail(profileBaseId ? { kind: "profile", baseId: profileBaseId } : null);
      setCadFeatureSummary(summarizeExtrudeResult(result, true));
      const { artifact } = cadExportMetadata(result);
      setCadExportArtifact(artifact);
      setCadExportPath(artifact?.stepPath || null);
      setSolidPreviewMesh(previewMeshFromResult(result));
      setWorkspaceViewMode("solid");
    }
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
        setUserError("Rectangle anchor point is missing");
        return;
      }
      const pointIds = new Set(Object.values(ids.pointIds));
      const lockTarget = pointIds.has(latestAnchor.id) ? latestAnchor : latestSnapshot.selection_context.items.find(
        (entity): entity is Extract<SketchMathEntity, { type: "point_2d" }> => isPointEntity(entity) && entity.id === ids.pointIds.a,
      );
      if (!lockTarget) {
        setUserError("Rectangle anchor point is missing");
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
      clearErrorState();
    } catch (err) {
      const { message, debugText } = normalizeCaughtError(err, "Failed to fix rectangle corner");
      setUserError(message, debugText);
    }
  };

  const cadExportMetadata = (result: SketchMathOperationResult | null): { holeCount: number; artifact: CadExportArtifact | null } => {
    const cadExport = result?.metadata?.cad_export as Record<string, unknown> | undefined;
    const exportMetadata = cadExport?.metadata as Record<string, unknown> | undefined;
    const artifacts = cadExport?.artifacts as Record<string, unknown> | undefined;
    const holeCount = typeof exportMetadata?.hole_count === "number" ? exportMetadata.hole_count : activeProfileForCad?.holes?.length || 0;
    const stepPath = typeof artifacts?.step_path === "string" ? artifacts.step_path : null;
    return {
      holeCount,
      artifact: stepPath
        ? {
            stepPath,
            filename: typeof exportMetadata?.artifact_filename === "string" ? exportMetadata.artifact_filename : fileNameFromPath(stepPath),
            sizeBytes: typeof exportMetadata?.artifact_size_bytes === "number" ? exportMetadata.artifact_size_bytes : null,
            createdAt: typeof exportMetadata?.artifact_created_at === "string" ? exportMetadata.artifact_created_at : null,
            profileId: typeof exportMetadata?.profile_id === "string" ? exportMetadata.profile_id : activeProfileForCad?.id || null,
            extrusionDepth: typeof exportMetadata?.extrusion_depth === "number" ? exportMetadata.extrusion_depth : Number(extrudeDepthValue) || null,
            extrusionDepthUnit: typeof exportMetadata?.extrusion_depth_unit === "string" ? exportMetadata.extrusion_depth_unit : "mm",
          }
        : null,
    };
  };

  const summarizeExtrudeResult = (result: SketchMathOperationResult, committed = false): string => {
    const { holeCount, artifact } = cadExportMetadata(result);
    const holeText = holeCount === 1 ? "1 hole" : `${holeCount} holes`;
    if (committed && artifact) {
      return `STEP export ready: profile accepted with ${holeText}`;
    }
    return `Extrude preview ready: profile accepted with ${holeText}`;
  };

  const handleCreateCadFeature = async () => {
    const profile = activeProfileForCad;
    if (!profile) {
      setUserError("Select a closed profile before extrusion");
      return;
    }
    const depth = Number(extrudeDepthValue);
    if (!Number.isFinite(depth) || depth <= 0) {
      setUserError("Extrusion depth must be a positive number");
      return;
    }
    const normalizedDepth = Number(depth.toFixed(2));
    const command = buildExtrudeProfileCommand(profile.id, normalizedDepth, "mm");
    setSelectedEntityIds([profile.id]);
    const baseId = rectangleBaseIdFromEntityId(profile.id);
    setRectangleSelectionDetail(baseId ? { kind: "profile", baseId } : null);
    setCadExportPath(null);
    setCadExportArtifact(null);
    const result = await previewCommand(command);
    if (result) {
      setCadFeatureSummary(summarizeExtrudeResult(result));
      const nextMesh = previewMeshFromResult(result);
      setSolidPreviewMesh(nextMesh);
      setSolidCamera({
        ...cameraFromSketchView(),
        targetZ: solidTargetZ(nextMesh),
      });
      setWorkspaceViewMode("solid");
    }
  };

  const handleAddProfileHole = async () => {
    if (!activeProfileForHole) {
      setUserError("Select a rectangle or closed profile before adding a hole");
      return;
    }
    const diameter = Number(holeDiameterValue);
    if (!Number.isFinite(diameter) || diameter <= 0) {
      setUserError("Hole diameter must be a positive number");
      return;
    }
    const center = profileCenter(activeProfileForHole);
    if (!center) {
      setUserError("Selected profile does not have usable bounds");
      return;
    }
    setSelectedEntityIds([activeProfileForHole.id]);
    const baseId = rectangleBaseIdFromEntityId(activeProfileForHole.id);
    setRectangleSelectionDetail(baseId ? { kind: "profile", baseId } : null);
    setTool("hole");
    setHolePlacement({
      profileId: activeProfileForHole.id,
      baseId,
      center,
      message: "Click inside selected profile to place the hole center.",
    });
    clearErrorState();
  };

  const handleAddCenteredProfileHole = async () => {
    if (!activeProfileForHole) {
      setUserError("Select a rectangle or closed profile before adding a hole");
      return;
    }
    const diameter = Number(holeDiameterValue);
    if (!Number.isFinite(diameter) || diameter <= 0) {
      setUserError("Hole diameter must be a positive number");
      return;
    }
    const center = profileCenter(activeProfileForHole);
    if (!center) {
      setUserError("Selected profile does not have usable bounds");
      return;
    }
    setSelectedEntityIds([activeProfileForHole.id]);
    const baseId = rectangleBaseIdFromEntityId(activeProfileForHole.id);
    setRectangleSelectionDetail(baseId ? { kind: "profile", baseId } : null);
    setTool("select");
    await commitProfileHole(center);
  };

  const commitProfileHole = async (center: Point) => {
    const profile = holePlacement
      ? committedEntities.find((entity): entity is Extract<SketchMathEntity, { type: "profile_2d" }> => entity.id === holePlacement.profileId && isClosedProfileEntity(entity))
      : activeProfileForHole;
    if (!profile) {
      setUserError("Select a rectangle or closed profile before adding a hole");
      return;
    }
    const diameter = Number(holeDiameterValue);
    if (!Number.isFinite(diameter) || diameter <= 0) {
      setUserError("Hole diameter must be a positive number");
      return;
    }
    if (!pointInsideProfile(center, profile)) {
      setHolePlacement((current) =>
        current
          ? {
              ...current,
              message: "That point is outside the selected profile. Click inside the selected profile.",
            }
          : current,
      );
      setUserError("Hole center must be inside the selected profile");
      return;
    }
    const command = buildAddProfileHoleCommand(profile.id, Number(diameter.toFixed(2)), center, "mm");
    const result = await commitCommand(command);
    if (!result) {
      return;
    }
    const afterProfile = result.after.items.find((entity): entity is Extract<SketchMathEntity, { type: "profile_2d" }> => entity.id === profile.id && isClosedProfileEntity(entity));
    const nextHoleId = afterProfile?.holes?.find((holeId) => !(profile.holes || []).includes(holeId));
    setSelectedEntityIds(nextHoleId ? [nextHoleId] : [profile.id]);
    const profileBaseId = rectangleBaseIdFromEntityId(profile.id);
    setRectangleSelectionDetail(nextHoleId ? null : profileBaseId ? { kind: "profile", baseId: profileBaseId } : null);
    setHolePlacement(null);
    setPreviewResult(null);
    clearSolidPreview();
    setPendingCommandText(asCommandText({ ...command, mode: "commit" }));
  };

  const handleApplySelectedHoleUpdate = async () => {
    if (!selectedHoleSummary) {
      setHoleEditorMessage("Select a profile hole before editing it.");
      return;
    }
    const parentProfile = committedEntities.find(
      (entity): entity is Extract<SketchMathEntity, { type: "profile_2d" }> => entity.id === selectedHoleSummary.profileId && isClosedProfileEntity(entity),
    );
    if (!parentProfile) {
      setHoleEditorMessage("The parent profile for this hole is missing.");
      return;
    }
    const diameter = Number(selectedHoleDiameterDraft);
    const center = { x: Number(selectedHoleCenterXDraft), y: Number(selectedHoleCenterYDraft) };
    if (!Number.isFinite(diameter) || diameter <= 0) {
      setHoleEditorMessage("Hole diameter must be a positive number.");
      setUserError("Hole diameter must be a positive number");
      return;
    }
    if (!Number.isFinite(center.x) || !Number.isFinite(center.y)) {
      setHoleEditorMessage("Hole center must use numeric X and Y values.");
      setUserError("Hole center must use numeric X and Y values");
      return;
    }
    if (!pointInsideProfile(center, parentProfile)) {
      setHoleEditorMessage("Hole center must stay inside the selected profile.");
      setUserError("Hole center must be inside the selected profile");
      return;
    }
    const command = buildUpdateProfileHoleCommand(
      selectedHoleSummary.profileId,
      selectedHoleSummary.holeId,
      Number(diameter.toFixed(2)),
      { x: Number(center.x.toFixed(2)), y: Number(center.y.toFixed(2)) },
      "mm",
    );
    const result = await commitCommand(command);
    if (!result) {
      setHoleEditorMessage("Hole update failed. Check the command error above.");
      return;
    }
    setSelectedEntityIds([selectedHoleSummary.holeId]);
    setRectangleSelectionDetail(null);
    setHoleEditorMessage("Hole updated.");
    setPreviewResult(null);
    clearSolidPreview();
    setPendingCommandText(asCommandText({ ...command, mode: "commit" }));
  };

  const deleteRectangleCascade = async (baseId: string) => {
    const result = await commitCommand(buildDeleteEntityCommand(rectangleSelectionIds(baseId), true));
    if (!result) {
      setUserError("Could not delete the rectangle safely. Open Advanced / Debug for details.");
      return;
    }
    setSelectedEntityIds([]);
    setRectangleSelectionDetail(null);
    setDimensionEditor(null);
    setDeletePrompt(null);
    setHolePlacement(null);
    setCadFeatureSummary(null);
    setSolidPreviewMesh(null);
    setTranslationOutcome(null);
    setPendingCommandText("");
    setPreviewResult(null);
    clearSolidPreview();
    clearErrorState();
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
    if (selectedCircle) {
      const ids = [selectedCircle.id, `profile_${selectedCircle.id}`].filter((entityId) => committedEntities.some((entity) => entity.id === entityId));
      const result = await commitCommand(buildDeleteEntityCommand(ids, true));
      if (result) {
        setSelectedEntityIds([]);
        setPreviewResult(null);
        clearSolidPreview();
      }
      return;
    }
    if (selectedIdsAreReferenced(selectedEntityIds)) {
      setUserError("Selection is referenced by sketch constraints or profiles. Delete the parent sketch object instead.");
      return;
    }
    const result = await commitCommand(buildDeleteEntityCommand(selectedEntityIds));
    if (!result) {
      setUserError("Could not delete the selection safely. Open Advanced / Debug for details.");
      return;
    }
    setSelectedEntityIds([]);
    setPendingCommandText("");
    setTranslationOutcome(null);
    setPreviewResult(null);
    clearSolidPreview();
    setCadExportPath(null);
    setCadExportArtifact(null);
    setCadFeatureSummary(null);
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
      const { message, debugText } = normalizeCaughtError(err, "Failed to clear sketch");
      setUserError(message, debugText);
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
        setHolePlacement(null);
        setDraftPoint(null);
        setCircleDraft(null);
        clearErrorState();
        return;
      }
      if (isTypingField) {
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (event.shiftKey) void redoNext();
        else void revertLast();
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") {
        event.preventDefault();
        void redoNext();
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
        clearErrorState();
      } else {
        setPendingCommandText("");
      }
    } catch (err) {
      const { message, debugText } = normalizeCaughtError(err, "Translation failed");
      setUserError(message, debugText);
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

  const runQuickHorizontal = async () => {
    if (selectedLineEntities.length === 1) await commitCommand(buildHorizontalCommand([selectedLineEntities[0].id]));
  };

  const runQuickVertical = async () => {
    if (selectedLineEntities.length === 1) await commitCommand(buildVerticalCommand([selectedLineEntities[0].id]));
  };

  const runQuickCoincident = async () => {
    if (pointSelectionIds.length === 2) await commitCommand(buildCoincidentCommand(pointSelectionIds));
  };

  const runUpdateCircle = async () => {
    if (!selectedCircle) return;
    const radius = Number(circleRadiusValue);
    if (!Number.isFinite(radius) || radius <= 0) {
      setUserError("Circle radius must be a positive number.");
      return;
    }
    await commitCommand(buildBatchCommand([
      buildUpdateCircleCommand(selectedCircle.id, { x: selectedCircle.center[0], y: selectedCircle.center[1] }, radius),
      buildMakeCircleProfileCommand(selectedCircle.id, `profile_${selectedCircle.id}`),
    ]));
  };

  const runCircleAsHole = async () => {
    if (!selectedCircle || !circleHoleTarget) return;
    const result = await commitCommand(buildAddProfileHoleCommand(
      circleHoleTarget.id,
      selectedCircle.radius * 2,
      { x: selectedCircle.center[0], y: selectedCircle.center[1] },
    ));
    if (result) setSelectedEntityIds([circleHoleTarget.id]);
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
      setHolePlacement(null);
      setDraftPoint(null);
    }
    if (nextTool === "solve") {
      setTool(nextTool);
      void commitCommand(buildSolveConstraintsCommand());
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
    if (nextTool === "hole") {
      setTool(nextTool);
      if (activeProfileForHole) {
        void handleAddProfileHole();
      }
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
  const canExtrudeSelection = Boolean(activeProfileForCad);
  const holePlacementDiameter = Number(holeDiameterValue);
  const holePlacementPreview =
    holePlacement && Number.isFinite(holePlacementDiameter) && holePlacementDiameter > 0
      ? { center: holePlacement.center, diameter: holePlacementDiameter }
      : null;
  const canvasHelperText = holePlacement
    ? "Click inside the selected profile to place the hole, or add it at the profile center from the workflow panel."
    : tool === "rectangle"
      ? "Drag on the canvas to draw a rectangle profile. Hold Shift while dragging for a square."
      : tool === "hole"
        ? "Select a profile, then click inside it to place a circular hole."
        : tool === "pan"
          ? "Drag the canvas to pan. Use Fit, Reset, and zoom controls to navigate the 2D sketch plane."
      : tool === "dimension"
        ? "Select a rectangle edge or click a dimension label to edit width or height."
        : tool === "line"
          ? draftPoint
            ? "Click the line end point."
            : "Click the line start point."
          : tool === "point"
            ? "Click the canvas to plot a point."
            : selectedHoleSummary
              ? "Selected hole: edit diameter and center in the workflow panel."
              : selectionRef.summary === "Nothing selected."
                ? "Select a rectangle or choose Draw rectangle to start the STEP workflow."
                : `${selectionRef.summary}. Use the workflow panel for the next step.`;

  return (
    <Box className="friday-command-shell sketchmath-command-shell" data-testid="sketchmath-workspace">
      <aside className="friday-mode-rail" aria-label="Friday workspaces">
        <Link href="/" className="friday-brand-mark">F</Link>
        <Link href="/" className="friday-rail-item" aria-label="Direct Friday">
          <span>FRIDAY</span>
          <strong>Chat</strong>
        </Link>
        <span className="friday-rail-item friday-rail-item-active" aria-label="SketchMath">
          <span>Sketch Math</span>
          <strong>CAD</strong>
        </span>
      </aside>

      <section className="friday-shell-frame">
        <header className="friday-status-bar">
          <div>
            <p className="friday-kicker">FRIDAY</p>
            <Heading size="lg" className="sketchmath-title">
              SketchMath
            </Heading>
          </div>
          <div className="friday-status-grid" aria-label="SketchMath runtime status">
            <span><b>Mode</b> CAD workspace</span>
            <span><b>Route / Model</b> Deterministic CAD executor</span>
            <span><b>Context</b> {committedEntities.length} entities / {committedContext.constraints.length} constraints</span>
            <span><b>Health</b> {error ? "Degraded" : "Ready"}</span>
          </div>
          <Button size="sm" variant="ghost" onClick={toggleColorMode} className="friday-icon-button">
            {colorMode === "light" ? "Dark grid" : "Light grid"}
          </Button>
        </header>

        <Box className="friday-workbench sketchmath-workbench-layout">
          <Box className="friday-workspace-pane sketchmath-main-pane">
            <Box className="sketchmath-shell-header sketchmath-workspace-summary">
              <VStack align="start" spacing={1}>
                <Text opacity={0.8}>Canvas-first deterministic sketching inside FRIDAY.</Text>
                <Text fontSize="sm" opacity={0.6}>
                  Session: {sessionId || "loading"} {sessionMetadata.storage_path ? `• ${String(sessionMetadata.storage_path)}` : ""}
                </Text>
              </VStack>
              <Link href="/" className="sketchmath-link">
                Back to FRIDAY chat
              </Link>
            </Box>

            <SketchMathToolbar mode={tool} onModeChange={handleToolChange} theme={colorMode} onToggleTheme={toggleColorMode} />

            <Box className="sketchmath-canvas-panel">
              <Text className="sketchmath-canvas-helper" data-testid="sketchmath-canvas-helper">
                {canvasHelperText}
              </Text>
              <HStack className="sketchmath-view-controls" spacing={2} flexWrap="wrap" mb={3} data-testid="sketchmath-view-controls">
                <Button size="sm" variant={workspaceViewMode === "sketch" ? "solid" : "outline"} onClick={() => switchWorkspaceView("sketch")}>
                  2D sketch
                </Button>
                <Button size="sm" variant={workspaceViewMode === "solid" ? "solid" : "outline"} onClick={() => switchWorkspaceView("solid")}>
                  3D solid
                </Button>
                <Button size="sm" variant={tool === "pan" ? "solid" : "outline"} onClick={() => handleToolChange("pan")}>
                  Pan / view
                </Button>
                <Button size="sm" variant="outline" onClick={() => zoomView(0.8)} isDisabled={workspaceViewMode !== "sketch"}>
                  Zoom in
                </Button>
                <Button size="sm" variant="outline" onClick={() => zoomView(1.25)} isDisabled={workspaceViewMode !== "sketch"}>
                  Zoom out
                </Button>
                <Button size="sm" variant="outline" onClick={fitSketchToView} isDisabled={workspaceViewMode !== "sketch"}>
                  Fit sketch
                </Button>
                <Button size="sm" variant="outline" onClick={resetView} isDisabled={workspaceViewMode !== "sketch"}>
                  Reset view
                </Button>
                <Text className="sketchmath-plane-chip" data-testid="sketchmath-plane-widget">
                  {workspaceViewMode === "solid" ? "3D solid preview" : "2D sketch plane"}
                </Text>
              </HStack>
              {workspaceViewMode === "solid" ? (
                <SolidPreview3D mesh={solidPreviewMesh} camera={solidCamera} onCameraChange={setSolidCamera} onPreset={applySolidCameraPreset} />
              ) : (
                <SketchCanvas2D
                  width={CANVAS_WIDTH}
                  height={CANVAS_HEIGHT}
                  viewBox={viewBoxState}
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
                  circleDraft={circleDraft}
                  dragPreviewPoint={dragPreviewPoint}
                  holePlacementPreview={holePlacementPreview}
                  holePlacementActive={Boolean(holePlacement)}
                  showDebugLabels={showDebugLabels}
                  profileCandidates={profileCandidates}
                  onCanvasClick={handleCanvasClick}
                  onCanvasMouseDown={handleCanvasMouseDown}
                  onCanvasMouseMove={handleCanvasMouseMove}
                  onCanvasMouseUp={handleCanvasMouseUp}
                  onCanvasContextMenu={handleCanvasContextMenu}
                  onEntityClick={handleEntityClick}
                  onEntityMouseDown={handleEntityMouseDown}
                  onDimensionLabelEdit={handleDimensionLabelEdit}
                />
              )}
            </Box>
          </Box>

          <VStack align="stretch" spacing={4} className="friday-telemetry-sidecar sketchmath-sidebar" data-testid="friday-telemetry-panel">
          <Box className="sketchmath-panel sketchmath-workflow-panel" data-testid="sketchmath-workbench-panel">
            <Heading size="sm" mb={3} className="sketchmath-panel-title">
              SketchMath workflow
            </Heading>
            <VStack align="stretch" spacing={3}>
              {error ? (
                <Box className="sketchmath-error" data-testid="sketchmath-user-error">
                  <Text fontWeight="600">Action needed</Text>
                  <Text>{error}</Text>
                </Box>
              ) : null}
              <Box className="sketchmath-workflow-step" data-testid="sketchmath-tool-mode">
                <Text className="sketchmath-step-label">Current mode</Text>
                <Text fontWeight="600">{tool === "select" ? "Select" : tool === "rectangle" ? "Draw rectangle" : tool === "hole" ? "Add hole" : tool === "pan" ? "Pan / view" : tool}</Text>
                <Text fontSize="sm" opacity={0.8}>
                  {canvasHelperText}
                </Text>
              </Box>

              <Box data-testid="sketchmath-selection-summary">
                <HStack spacing={2} mb={2}>
                  <Button size="sm" variant="outline" onClick={() => void revertLast()} isDisabled={!canUndo}>Undo</Button>
                  <Button size="sm" variant="outline" onClick={() => void redoNext()} isDisabled={!canRedo}>Redo</Button>
                </HStack>
                <Text fontWeight="600">{selectionRef.summary}</Text>
                {selectionRef.kind === "none" ? (
                  <Text fontSize="sm" opacity={0.75}>
                    Nothing selected.
                  </Text>
                ) : null}
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
                <Text data-testid="sketchmath-status" fontSize="sm" opacity={0.8}>
                  {sketchStatus}
                </Text>
                {constraintSummaries.length ? (
                  <Text fontSize="sm" opacity={0.75} whiteSpace="pre-wrap" data-testid="sketchmath-selected-constraints">
                    {constraintSummaries.join("\n")}
                  </Text>
                ) : null}
                {rectangleDimensions ? (
                  <Text fontSize="sm" opacity={0.75}>
                    {rectangleAnchorSummary || "Position free"}
                  </Text>
                ) : null}
                <HStack spacing={2} flexWrap="wrap" mt={2}>
                  {rectangleDimensions ? (
                    <Button size="sm" variant="outline" onClick={() => void handleFixRectangleCorner()}>
                      Fix corner
                    </Button>
                  ) : null}
                  <Button size="sm" variant="outline" onClick={() => void handleDeleteSelected()} isDisabled={selectedEntityIds.length === 0}>
                    Delete
                  </Button>
                </HStack>
                {deletePrompt ? (
                  <Box className="sketchmath-inline-editor" mt={3} data-testid="sketchmath-delete-prompt">
                    <Text fontWeight="600" mb={1}>
                      Dependency-aware delete
                    </Text>
                    <Text fontSize="sm" opacity={0.85}>
                      {deletePrompt.message}
                    </Text>
                    <HStack mt={2}>
                      <Button size="sm" onClick={() => void deleteRectangleCascade(deletePrompt.baseId)}>
                        Delete whole rectangle
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setDeletePrompt(null)}>
                        Cancel
                      </Button>
                    </HStack>
                  </Box>
                ) : null}
              </Box>

              <Box className="sketchmath-workflow-step" data-testid="sketchmath-workflow-draw">
                <Text className="sketchmath-step-label">1. Draw</Text>
                <Text fontSize="sm" opacity={0.85}>
                  {rectangleDimensions ? `Rectangle ${rectangleDimensions.width} mm x ${rectangleDimensions.height} mm` : "Draw a rectangle profile on the canvas."}
                </Text>
                <HStack spacing={2} flexWrap="wrap" mt={2}>
                  <Button size="sm" onClick={() => handleToolChange("rectangle")} variant={tool === "rectangle" ? "solid" : "outline"}>
                    Start rectangle
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => void handleClearSketch()}>
                    Clear sketch
                  </Button>
                </HStack>
              </Box>

              <Box className="sketchmath-workflow-step" data-testid="sketchmath-workflow-dimensions">
                <Text className="sketchmath-step-label">2. Dimension</Text>
                <Text fontSize="sm" opacity={0.85}>
                  {dimensionSummary}
                </Text>

                {/* Rectangle dimension editor — visible when a rectangle is selected */}
                {rectangleDimensions ? (
                  <>
                    <Text fontWeight="600" fontSize="sm" mt={2}>Rectangle dimensions</Text>
                    <HStack spacing={2} flexWrap="wrap" mt={2}>
                      <Input
                        type="number"
                        aria-label="Rectangle width"
                        value={rectangleWidthDraft}
                        onChange={(event) => setRectangleWidthDraft(event.target.value)}
                        width="104px"
                      />
                      <Input
                        type="number"
                        aria-label="Rectangle height"
                        value={rectangleHeightDraft}
                        onChange={(event) => setRectangleHeightDraft(event.target.value)}
                        width="104px"
                      />
                      <Button size="sm" onClick={() => void handleApplyRectangleDimensions()}>
                        Apply Rectangle Dimensions
                      </Button>
                    </HStack>
                  </>
                ) : null}

                {/* Inline dimension editor for rectangle edges */}
                {dimensionEditor ? (
                  <Box className="sketchmath-inline-editor" mt={3} data-testid="rectangle-dimension-editor">
                    <Heading size="sm" mb={2}>
                      Edit {dimensionEditor.dimension} dimension
                    </Heading>
                    <HStack spacing={2} flexWrap="wrap">
                      <Input
                        type="number"
                        value={dimensionEditor.value}
                        onChange={(event) => setDimensionEditor((current) => (current ? { ...current, value: event.target.value } : current))}
                        aria-label={`${dimensionEditor.dimension === "width" ? "Width" : "Height"} dimension value`}
                        width="110px"
                      />
                      <Button size="sm" onClick={() => void handleApplyDimensionEditor()}>
                        Apply dimension
                      </Button>
                    </HStack>
                  </Box>
                ) : null}

                {/* General line length editor — visible when 1 line or 2 points are selected */}
                {(selectionRef.kind === "one_line" || selectionRef.kind === "two_points") ? (
                  <Box className="sketchmath-inline-editor" mt={3} data-testid="sketchmath-line-length-editor">
                    <Text fontWeight="600" fontSize="sm" mb={2}>
                      {selectionRef.kind === "one_line" ? "Set line length" : "Set distance between points"}
                    </Text>
                    <HStack spacing={2} flexWrap="wrap">
                      <Input
                        type="number"
                        aria-label="SketchMath length"
                        value={lengthValue}
                        onChange={(event) => setLengthValue(event.target.value)}
                        width="100px"
                      />
                      <Text fontSize="sm" opacity={0.7}>mm</Text>
                      <Button size="sm" onClick={() => void runQuickLength()} isDisabled={!selectionRef.canSetLength}>
                        Apply length
                      </Button>
                    </HStack>
                    {selectionRef.kind === "one_line" ? (
                      <HStack spacing={2} mt={2}>
                        <Button size="sm" onClick={() => void runQuickHorizontal()}>Horizontal</Button>
                        <Button size="sm" onClick={() => void runQuickVertical()}>Vertical</Button>
                      </HStack>
                    ) : (
                      <Button size="sm" mt={2} onClick={() => void runQuickCoincident()}>Coincident</Button>
                    )}
                  </Box>
                ) : null}
                {selectedCircle ? (
                  <Box className="sketchmath-inline-editor" mt={3} data-testid="sketchmath-circle-editor">
                    <Text fontWeight="600" fontSize="sm" mb={2}>Circle radius</Text>
                    <HStack spacing={2}>
                      <Input type="number" aria-label="Circle radius" value={circleRadiusValue} onChange={(event) => setCircleRadiusValue(event.target.value)} width="100px" />
                      <Text fontSize="sm">mm</Text>
                      <Button size="sm" onClick={() => void runUpdateCircle()}>Apply radius</Button>
                      {circleHoleTarget ? <Button size="sm" onClick={() => void runCircleAsHole()}>Use as hole</Button> : null}
                    </HStack>
                  </Box>
                ) : null}

                {/* Constraint tools — visible when 2 lines are selected */}
                {selectionRef.kind === "two_lines" ? (
                  <Box className="sketchmath-inline-editor" mt={3} data-testid="sketchmath-constraint-tools">
                    <Text fontWeight="600" fontSize="sm" mb={1}>Geometric constraints</Text>
                    <Text fontSize="sm" opacity={0.75} mb={2}>
                      Apply a constraint between the 2 selected lines.
                    </Text>
                    <HStack spacing={2} flexWrap="wrap">
                      <Button size="sm" onClick={() => void runQuickParallel()} isDisabled={!selectionRef.canMakeParallel}>
                        Parallel
                      </Button>
                      <Button size="sm" onClick={() => void runQuickPerpendicular()} isDisabled={!selectionRef.canMakePerpendicular}>
                        Perpendicular
                      </Button>
                      <Button size="sm" onClick={() => void runQuickEqualLength()} isDisabled={!selectionRef.canEqualLength}>
                        Equal Length
                      </Button>
                    </HStack>
                    <HStack spacing={2} flexWrap="wrap" mt={2}>
                      <Input
                        type="number"
                        aria-label="SketchMath length"
                        value={lengthValue}
                        onChange={(event) => setLengthValue(event.target.value)}
                        width="100px"
                      />
                      <Text fontSize="sm" opacity={0.7}>mm</Text>
                      <Button size="sm" onClick={() => void runQuickLength()} isDisabled={!selectionRef.canSetLength}>
                        Set Length
                      </Button>
                    </HStack>
                  </Box>
                ) : null}

                {/* Hint when nothing is selected and no rectangle */}
                {!rectangleDimensions && selectionRef.kind === "none" ? (
                  <Text fontSize="sm" opacity={0.7} mt={2}>
                    Select a line, two lines, or two points to set dimensions and constraints.
                  </Text>
                ) : null}
              </Box>

              {profileCandidates.length > 0 ? (
                <Box className="sketchmath-workflow-step" data-testid="sketchmath-profile-candidates">
                  <Text className="sketchmath-step-label">Detected profiles</Text>
                  {profileCandidates.map((candidate) => (
                    <Box key={candidate.candidate_id} mt={2}>
                      <Text fontSize="sm">{candidate.valid ? "Valid closed loop" : "Invalid loop"} • {candidate.area.toFixed(2)} mm²</Text>
                      <Button
                        size="sm"
                        mt={1}
                        isDisabled={!candidate.valid}
                        onClick={() => void commitCommand(buildMakeProfileCommand(candidate.line_ids))}
                      >
                        Create profile
                      </Button>
                    </Box>
                  ))}
                </Box>
              ) : null}

              <Box className="sketchmath-workflow-step" data-testid="sketchmath-workflow-hole">
                <Text className="sketchmath-step-label">3. Hole</Text>
                <Text fontSize="sm" opacity={0.85}>
                  {activeProfileForHole ? `Profile holes: ${activeProfileHoleCount}` : "Select the rectangle/profile before adding a hole."}
                </Text>
                <HStack spacing={2} flexWrap="wrap" mt={2}>
                  <Input
                    type="number"
                    aria-label="Hole diameter"
                    value={holeDiameterValue}
                    onChange={(event) => setHoleDiameterValue(event.target.value)}
                    width="110px"
                    disabled={!activeProfileForHole && !selectedHoleSummary}
                  />
                  <Button size="sm" onClick={() => void handleAddCenteredProfileHole()} isDisabled={!activeProfileForHole}>
                    Add center hole
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => void handleAddProfileHole()} isDisabled={!activeProfileForHole}>
                    Add Hole
                  </Button>
                </HStack>
                {holePlacement ? (
                  <Box mt={2} data-testid="sketchmath-hole-placement">
                    <Text fontSize="sm" opacity={0.85}>
                      {holePlacement.message}
                    </Text>
                    <HStack spacing={2} flexWrap="wrap" mt={2}>
                      <Button size="sm" onClick={() => void commitProfileHole(holePlacement.center)}>
                        Add Centered Hole
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setHolePlacement(null)}>
                        Cancel Hole Placement
                      </Button>
                    </HStack>
                  </Box>
                ) : null}
                {selectedHoleSummary ? (
                  <Box className="sketchmath-inline-editor" mt={3} data-testid="selected-hole-editor">
                    <Text fontSize="sm" fontWeight="600">Selected hole</Text>
                    <HStack spacing={2} flexWrap="wrap" mt={2}>
                      <Input
                        type="number"
                        aria-label="Selected hole diameter"
                        value={selectedHoleDiameterDraft}
                        onChange={(event) => setSelectedHoleDiameterDraft(event.target.value)}
                        width="104px"
                      />
                      <Input
                        type="number"
                        aria-label="Selected hole center X"
                        value={selectedHoleCenterXDraft}
                        onChange={(event) => setSelectedHoleCenterXDraft(event.target.value)}
                        width="104px"
                      />
                      <Input
                        type="number"
                        aria-label="Selected hole center Y"
                        value={selectedHoleCenterYDraft}
                        onChange={(event) => setSelectedHoleCenterYDraft(event.target.value)}
                        width="104px"
                      />
                      <Button size="sm" onClick={() => void handleApplySelectedHoleUpdate()}>
                        Apply hole update
                      </Button>
                    </HStack>
                    {holeEditorMessage ? (
                      <Text fontSize="sm" opacity={0.8} mt={2}>
                        <span data-testid="selected-hole-editor-message">
                          {holeEditorMessage}
                        </span>
                      </Text>
                    ) : null}
                  </Box>
                ) : null}
              </Box>

              <Box className="sketchmath-workflow-step" data-testid="sketchmath-workflow-extrude">
                <Text className="sketchmath-step-label">4. Extrude</Text>
                <Text fontSize="sm" opacity={0.85} data-testid="sketchmath-profile-status">
                  {profileSummary}
                </Text>
                <HStack spacing={2} flexWrap="wrap" mt={2}>
                  <Input
                    type="number"
                    aria-label="Extrusion depth"
                    value={extrudeDepthValue}
                    onChange={(event) => setExtrudeDepthValue(event.target.value)}
                    width="110px"
                  />
                  <Button size="sm" onClick={() => void handleCreateCadFeature()} isDisabled={!canExtrudeSelection}>
                    Extrude
                  </Button>
                </HStack>
                <Text fontSize="sm" opacity={0.75} mt={2}>
                  {canExtrudeSelection
                    ? "Ready for CAD feature. Selected profile is ready for extrusion."
                    : hasUsableGeometry
                      ? "Select a closed profile before extrusion."
                      : "No extrusion available until a closed rectangle profile exists."}
                </Text>
                {cadFeatureSummary ? (
                  <Text fontSize="sm" mt={2} data-testid="sketchmath-cad-feature-summary">
                    {cadFeatureSummary}
                  </Text>
                ) : null}
                {previewResult?.status === "preview" ? (
                  <HStack spacing={2} flexWrap="wrap" mt={3} data-testid="sketchmath-preview-controls">
                    <Button size="sm" onClick={() => void commitPreview()}>
                      Commit Preview
                    </Button>
                    <Button size="sm" variant="outline" onClick={clearDimensionPreview}>
                      Revert Preview
                    </Button>
                  </HStack>
                ) : null}
              </Box>

              <Box className="sketchmath-workflow-step" data-testid="sketchmath-workflow-export">
                <Text className="sketchmath-step-label">5. Export</Text>
                {cadExportPath && cadExportDownloadUrl ? (
                  <Box className="sketchmath-export-card" data-testid="sketchmath-export-card" mt={2}>
                    <Text fontWeight="600">Export succeeded</Text>
                    <Text fontSize="sm" opacity={0.85}>
                      {cadExportFileName || "export.step"} is ready for download.
                    </Text>
                    <dl className="sketchmath-export-metadata" data-testid="sketchmath-export-metadata">
                      <div><dt>Filename</dt><dd>{cadExportFileName || "export.step"}</dd></div>
                      <div><dt>Size</dt><dd>{cadExportArtifact?.sizeBytes != null ? `${cadExportArtifact.sizeBytes} bytes` : "Not reported"}</dd></div>
                      <div><dt>Created</dt><dd>{cadExportArtifact?.createdAt || "Not reported"}</dd></div>
                      <div><dt>Profile</dt><dd>Selected profile</dd></div>
                      <div><dt>Depth</dt><dd>{cadExportArtifact?.extrusionDepth != null ? `${cadExportArtifact.extrusionDepth} ${cadExportArtifact.extrusionDepthUnit || "mm"}` : `${extrudeDepthValue} mm`}</dd></div>
                    </dl>
                    <Text fontSize="sm" opacity={0.75}>
                      Download is served through FRIDAY. The 3D solid preview uses the same profile, holes, and extrusion depth.
                    </Text>
                    <HStack spacing={2} flexWrap="wrap" mt={2}>
                      <Button as="a" href={cadExportDownloadUrl} size="sm" variant="outline" download={cadExportFileName || "export.step"}>
                        Download STEP
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => void handleCreateCadFeature()} isDisabled={!canExtrudeSelection}>
                        Export again
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setCadExportPath(null);
                          setCadExportArtifact(null);
                          setCadFeatureSummary(null);
                        }}
                      >
                        Clear export result
                      </Button>
                    </HStack>
                  </Box>
                ) : (
                  <Text fontSize="sm" opacity={0.75} mt={2}>
                    Preview an extrusion, then export STEP.
                  </Text>
                )}
              </Box>

              <Box>
                <Button size="sm" variant="ghost" onClick={() => setConstraintsOpen((value) => !value)}>
                  {constraintsOpen ? "Hide Advanced Constraints" : "Show Advanced Constraints"}
                </Button>
                {constraintsOpen ? (
                  <Box className="sketchmath-inline-editor" mt={3} data-testid="sketchmath-advanced-constraints">
                    <Text fontSize="sm" opacity={0.75} mb={2}>
                      Committed constraints for the current selection.
                    </Text>
                    <Text fontSize="sm" opacity={0.8} whiteSpace="pre-wrap" mb={2}>
                      {constraintSummaries.length ? constraintSummaries.join("\n") : "No constraints yet."}
                    </Text>
                    <HStack spacing={2} flexWrap="wrap" mt={2}>
                      <Button size="sm" onClick={() => void runQuickEqualAngle()} isDisabled={pointSelectionIds.length < 6}>
                        Equal Angle
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => void commitCommand(buildSolveConstraintsCommand())}>
                        Solve constraints
                      </Button>
                    </HStack>
                  </Box>
                ) : null}
              </Box>

              <Button size="sm" variant="ghost" onClick={() => setAdvancedOpen((value) => !value)}>
                {advancedOpen ? "Hide Advanced / Debug" : "Show Advanced / Debug"}
              </Button>
            </VStack>
          </Box>

          {advancedOpen ? (
            <>
              <section className="friday-session-map" data-testid="friday-session-map">
                <h2>Session Map</h2>
                <dl>
                  <div><dt>Objective</dt><dd>Build a constrained sketch and export CAD-ready geometry.</dd></div>
                  <div><dt>Workspace</dt><dd>SketchMath canvas</dd></div>
                  <div><dt>Recent decisions</dt><dd>{history.length ? history.slice(-3).map((entry) => entry.command.command_type).join(" / ") : "No geometry commands yet"}</dd></div>
                  <div><dt>Attached context</dt><dd>{selectionRef.summary}</dd></div>
                  <div><dt>Artifacts</dt><dd>{cadExportPath || "No STEP export yet"}</dd></div>
                </dl>
              </section>
              <section>
                <h2>System Events</h2>
                <TelemetryEventList events={systemEvents} emptyMessage="SketchMath lifecycle events will appear here." />
              </section>
              <Box className="sketchmath-panel">
                <HStack justify="space-between" align="center">
                  <Text fontWeight="600">Debug labels</Text>
                  <Button size="sm" variant="outline" onClick={() => setShowDebugLabels((value) => !value)} data-testid="sketchmath-debug-label-toggle">
                    {showDebugLabels ? "Hide debug labels" : "Show debug labels"}
                  </Button>
                </HStack>
                <Text fontSize="sm" opacity={0.75} mt={2}>
                  Shows raw point and line ids on the canvas for troubleshooting.
                </Text>
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
                profileHoleCount={activeProfileHoleCount}
                selectedHole={selectedHoleSummary}
                selectedHoleDiameterDraft={selectedHoleDiameterDraft}
                selectedHoleCenterXDraft={selectedHoleCenterXDraft}
                selectedHoleCenterYDraft={selectedHoleCenterYDraft}
                holeEditorMessage={holeEditorMessage}
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
                onSelectedHoleDiameterDraftChange={setSelectedHoleDiameterDraft}
                onSelectedHoleCenterXDraftChange={setSelectedHoleCenterXDraft}
                onSelectedHoleCenterYDraftChange={setSelectedHoleCenterYDraft}
                onApplySelectedHoleUpdate={handleApplySelectedHoleUpdate}
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
              {errorDebugText ? (
                <Box className="sketchmath-panel" data-testid="sketchmath-error-details">
                  <Heading size="sm" mb={3} className="sketchmath-panel-title">
                    Error details
                  </Heading>
                  <Text fontSize="sm" whiteSpace="pre-wrap" className="sketchmath-command-preview">
                    {errorDebugText}
                  </Text>
                </Box>
              ) : null}
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
      </section>
    </Box>
  );
};

export default SketchMathWorkspace;
