import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Box, Button, Heading, HStack, Input, Link, Spinner, Text, useColorMode, useToast, VStack } from "@chakra-ui/react";
import SketchCanvas2D from "./SketchCanvas2D";
import SolidPreview3D, { DEFAULT_SOLID_CAMERA } from "./SolidPreview3D";
import type { SolidCameraState } from "./SolidPreview3D";
import SketchMathToolbar from "./SketchMathToolbar";
import SelectionInspector from "./SelectionInspector";
import CommandPanel from "./CommandPanel";
import OperationHistoryPanel from "./OperationHistoryPanel";
import FeatureHistoryPanel from "./FeatureHistoryPanel";
import MeasurementPanel from "./MeasurementPanel";
import TelemetryEventList from "../telemetry/TelemetryEventList";
import type { TelemetryEvent } from "../../telemetry/sessionTelemetry";
import { makeTelemetryEvent } from "../../telemetry/sessionTelemetry";
import type {
  SketchMathArtifactJobManifest,
  SketchMathCommand,
  SketchMathCommandResponse,
  SketchMathEntity,
  SketchMathDocument,
  SketchMathFeature,
  SketchMathFeatureCommand,
  SketchMathFeatureCommandResponse,
  SketchMathHistoryEntry,
  SketchMathHoleParameters,
  SketchMathMode,
  SketchMathOperationResult,
  SketchMathPlanarTopology,
  SketchMathPreviewMesh,
  SketchMathSelectionContext,
  SketchMathSessionSnapshot,
  SketchMathSemanticTopologyReference,
  SketchMathSolverAnalysis,
  SketchMathSolverRun,
  SketchMathTranslationOutcome,
} from "../../services/sketchmath";
import {
  SketchMathApiError,
  commitSketchMathCommand,
  commitSketchMathFeature,
  createSketchMathSession,
  getSketchMathArtifactJob,
  getSketchMathSession,
  isSketchMathChamferFeaturesEnabled,
  isSketchMathArtifactJobsEnabled,
  isSketchMathEnabled,
  isSketchMathFeatureHistoryEnabled,
  isSketchMathFilletFeaturesEnabled,
  isSketchMathHoleFeaturesEnabled,
  isSketchMathRevolveFeaturesEnabled,
  previewSketchMathCommand,
  redoSketchMathSession,
  redoSketchMathFeature,
  retrySketchMathArtifactJob,
  revertSketchMathSession,
  revertSketchMathFeature,
  sketchMathStepDownloadUrl,
  sketchMathStlDownloadUrl,
  startSketchMathArtifactJob,
  translateSketchMathUtterance,
  upsertSketchMathEntity,
} from "../../services/sketchmath";
import {
  buildAddProfileHoleCommand,
  buildAnalyzeConstraintsCommand,
  buildDeleteEntityCommand,
  buildDefineLineCommand,
  buildDefinePointCommand,
  buildDefineCircleCommand,
  buildDefineCenterArcCommand,
  buildDefineThreePointArcCommand,
  buildMakeCircleProfileCommand,
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
  buildMirrorCommand,
  buildDetectRegionsCommand,
  buildSelectRegionCommand,
  buildMakeRegionProfileCommand,
  buildMovePointCommand,
  buildSetLengthCommand,
  buildSetHorizontalDistanceCommand,
  buildSetVerticalDistanceCommand,
  buildSetRadiusCommand,
  buildSetDiameterCommand,
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
type ArcDraft = { points: Point[]; current: Point };
type PolylineDraft = { points: Point[]; current: Point };
type SlotDraft = { start: Point; current: Point };
type PolygonDraft = { center: Point; current: Point };
type SelectionBoxDraft = { start: Point; current: Point };
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
  kind: "none" | "rectangle_edge" | "rectangle_corner" | "rectangle_profile" | "profile" | "profile_hole" | "rectangle" | "circle" | "arc" | "one_line" | "two_lines" | "one_point" | "two_points" | "mixed";
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

const solverAnalysisFromMetadata = (value: unknown): SketchMathSolverAnalysis | null => {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Partial<SketchMathSolverAnalysis>;
  if (
    candidate.schema_version !== "1.0" ||
    !["exact", "partial", "unknown"].includes(String(candidate.coverage)) ||
    !["under_constrained", "fully_constrained", "unknown"].includes(String(candidate.freedom_state)) ||
    !["consistent", "inconsistent", "unknown"].includes(String(candidate.consistency_state)) ||
    !["none", "redundant", "unknown"].includes(String(candidate.redundancy_state))
  ) {
    return null;
  }
  return candidate as SketchMathSolverAnalysis;
};

const solverRunFromMetadata = (value: unknown): SketchMathSolverRun | null => {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Partial<SketchMathSolverRun>;
  if (
    !["1.0", "1.1"].includes(String(candidate.schema_version)) ||
    typeof candidate.backend !== "string" ||
    !["analyze", "solve"].includes(String(candidate.mode)) ||
    !["analyzed", "solved", "under_constrained", "inconsistent", "redundant", "failed"].includes(String(candidate.outcome)) ||
    !solverAnalysisFromMetadata(candidate.analysis_after)
  ) {
    return null;
  }
  return candidate as SketchMathSolverRun;
};

const topologyFromMetadata = (value: unknown): SketchMathPlanarTopology | null => {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Partial<SketchMathPlanarTopology>;
  if (
    candidate.schema_version !== "1.0" ||
    !Array.isArray(candidate.regions) ||
    !Array.isArray(candidate.diagnostics) ||
    !candidate.selection ||
    !["not_requested", "selected", "none", "boundary", "ambiguous"].includes(String(candidate.selection.status))
  ) {
    return null;
  }
  return candidate as SketchMathPlanarTopology;
};

const isPointEntity = (entity: SketchMathEntity): entity is Extract<SketchMathEntity, { type: "point_2d" }> => entity.type === "point_2d";

const isLineEntity = (entity: SketchMathEntity): entity is Extract<SketchMathEntity, { type: "line_2d" | "construction_line_2d" }> =>
  entity.type === "line_2d" || entity.type === "construction_line_2d";

const isClosedProfileEntity = (entity: SketchMathEntity): entity is Extract<SketchMathEntity, { type: "profile_2d" }> =>
  entity.type === "profile_2d" && entity.closed !== false;

const isCircleEntity = (entity: SketchMathEntity): entity is Extract<SketchMathEntity, { type: "circle_2d" }> => entity.type === "circle_2d";
const isArcEntity = (entity: SketchMathEntity): entity is Extract<SketchMathEntity, { type: "arc_2d" }> => entity.type === "arc_2d";

const pointsMatch = (point: SketchMathEntity | undefined, coords: [number, number]): point is Extract<SketchMathEntity, { type: "point_2d" }> =>
  !!point && isPointEntity(point) && point.coords[0] === coords[0] && point.coords[1] === coords[1];

const distanceBetween = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y);

const entityIntersectsBox = (entity: SketchMathEntity, start: Point, current: Point): boolean => {
  const minX = Math.min(start.x, current.x);
  const maxX = Math.max(start.x, current.x);
  const minY = Math.min(start.y, current.y);
  const maxY = Math.max(start.y, current.y);
  const inside = (point: Point) => point.x >= minX && point.x <= maxX && point.y >= minY && point.y <= maxY;
  if (isPointEntity(entity)) return inside({ x: entity.coords[0], y: entity.coords[1] });
  if (isLineEntity(entity)) return inside({ x: entity.start[0], y: entity.start[1] }) && inside({ x: entity.end[0], y: entity.end[1] });
  if (isCircleEntity(entity) || isArcEntity(entity)) {
    return entity.center[0] - entity.radius >= minX && entity.center[0] + entity.radius <= maxX && entity.center[1] - entity.radius >= minY && entity.center[1] + entity.radius <= maxY;
  }
  if (isClosedProfileEntity(entity)) return entity.vertices.every(([x, y]) => inside({ x, y }));
  return false;
};

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

const centerRectangleCorner = (center: Point, corner: Point, forceSquare: boolean): Point => {
  if (!forceSquare) return corner;
  const deltaX = corner.x - center.x;
  const deltaY = corner.y - center.y;
  const magnitude = Math.max(Math.abs(deltaX), Math.abs(deltaY));
  return {
    x: center.x + Math.sign(deltaX || 1) * magnitude,
    y: center.y + Math.sign(deltaY || 1) * magnitude,
  };
};

const SketchMathWorkspace = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const toast = useToast();
  const [enabled] = useState<boolean>(isSketchMathEnabled());
  const [featureHistoryEnabled] = useState<boolean>(isSketchMathFeatureHistoryEnabled());
  const [holeFeaturesEnabled] = useState<boolean>(isSketchMathHoleFeaturesEnabled());
  const [revolveFeaturesEnabled] = useState<boolean>(isSketchMathRevolveFeaturesEnabled());
  const [filletFeaturesEnabled] = useState<boolean>(isSketchMathFilletFeaturesEnabled());
  const [chamferFeaturesEnabled] = useState<boolean>(isSketchMathChamferFeaturesEnabled());
  const [artifactJobsEnabled] = useState<boolean>(isSketchMathArtifactJobsEnabled());
  const [loading, setLoading] = useState(true);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sketchDocument, setSketchDocument] = useState<SketchMathDocument | null>(null);
  const [canFeatureUndo, setCanFeatureUndo] = useState(false);
  const [canFeatureRedo, setCanFeatureRedo] = useState(false);
  const [featureBusy, setFeatureBusy] = useState(false);
  const [artifactJobs, setArtifactJobs] = useState<Record<string, SketchMathArtifactJobManifest>>({});
  const [committedContext, setCommittedContext] = useState<SketchMathSelectionContext>(sketchmathInitialContext());
  const [history, setHistory] = useState<SketchMathHistoryEntry[]>([]);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [selectedEntityIds, setSelectedEntityIds] = useState<string[]>([]);
  const [previewResult, setPreviewResult] = useState<SketchMathOperationResult | null>(null);
  const [draftPoint, setDraftPoint] = useState<Point | null>(null);
  const [rectangleDraft, setRectangleDraft] = useState<RectangleDraft | null>(null);
  const [circleDraft, setCircleDraft] = useState<CircleDraft | null>(null);
  const [arcDraft, setArcDraft] = useState<ArcDraft | null>(null);
  const [polylineDraft, setPolylineDraft] = useState<PolylineDraft | null>(null);
  const [slotDraft, setSlotDraft] = useState<SlotDraft | null>(null);
  const [polygonDraft, setPolygonDraft] = useState<PolygonDraft | null>(null);
  const [selectionBox, setSelectionBox] = useState<SelectionBoxDraft | null>(null);
  const [topology, setTopology] = useState<SketchMathPlanarTopology | null>(null);
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);
  const [solverOutcome, setSolverOutcome] = useState<"Conflict" | "Solve failed" | null>(null);
  const [solverAnalysis, setSolverAnalysis] = useState<SketchMathSolverAnalysis | null>(null);
  const [solverRun, setSolverRun] = useState<SketchMathSolverRun | null>(null);
  const [solverAnalysisError, setSolverAnalysisError] = useState<string | null>(null);
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
  const [circleDiameterValue, setCircleDiameterValue] = useState("20");
  const [slotWidthValue, setSlotWidthValue] = useState("20");
  const [polygonSidesValue, setPolygonSidesValue] = useState("6");
  const [offsetValue, setOffsetValue] = useState("10");
  const [patternCountValue, setPatternCountValue] = useState("3");
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
  const topologyRequestRef = useRef(0);
  const solverAnalysisRequestRef = useRef(0);
  const notifiedArtifactPathsRef = useRef<Set<string>>(new Set());
  const lastSelectedHoleIdRef = useRef<string | null>(null);

  useEffect(() => {
    document.documentElement.dataset.fridayTheme = colorMode;
  }, [colorMode]);

  const appendEvents = useCallback((events: TelemetryEvent[]) => {
    setSystemEvents((previous) => [...[...events].reverse(), ...previous].slice(0, 16));
  }, []);

  const refreshSolverAnalysis = useCallback(async (activeSessionId: string) => {
    const requestId = solverAnalysisRequestRef.current + 1;
    solverAnalysisRequestRef.current = requestId;
    try {
      const response = await previewSketchMathCommand(activeSessionId, buildAnalyzeConstraintsCommand());
      if (requestId !== solverAnalysisRequestRef.current) return;
      const analysis = solverAnalysisFromMetadata(response.result.metadata.solver_analysis);
      const run = solverRunFromMetadata(response.result.metadata.solver_run);
      if (!analysis) {
        setSolverAnalysis(null);
        setSolverRun(null);
        setSolverAnalysisError("The backend returned an invalid solver analysis payload.");
        return;
      }
      setSolverAnalysis(analysis);
      setSolverRun(run);
      setSolverAnalysisError(null);
      setSolverOutcome(null);
    } catch (analysisError) {
      if (requestId !== solverAnalysisRequestRef.current) return;
      const detail = analysisError instanceof Error ? analysisError.message : "Solver analysis request failed.";
      setSolverAnalysis(null);
      setSolverRun(null);
      setSolverAnalysisError(detail);
    }
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
        setHistory(snapshot.history);
        setSketchDocument(snapshot.document || null);
        setCanFeatureUndo(Boolean(snapshot.can_feature_undo));
        setCanFeatureRedo(Boolean(snapshot.can_feature_redo));
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
          setHistory(snapshot.history);
          setSketchDocument(snapshot.document || null);
          setCanFeatureUndo(Boolean(snapshot.can_feature_undo));
          setCanFeatureRedo(Boolean(snapshot.can_feature_redo));
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
    if (!sessionId || loading) return;
    void refreshSolverAnalysis(sessionId);
  }, [committedContext, loading, refreshSolverAnalysis, sessionId]);

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
  const revolveAxes = useMemo(
    () => committedEntities.filter(
      (entity): entity is Extract<SketchMathEntity, { type: "line_2d" | "construction_line_2d" }> => entity.type === "construction_line_2d",
    ),
    [committedEntities],
  );
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
    if (selectedCircle) {
      setCircleRadiusValue(String(selectedCircle.radius));
      setCircleDiameterValue(String(selectedCircle.radius * 2));
    }
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
    if (committedEntities.length === 0) return "No constraints";
    if (!solverAnalysis) return solverAnalysisError ? "Analysis unavailable" : "Analyzing constraints…";
    if (solverAnalysis.consistency_state === "inconsistent") return "Conflicting";
    if (solverAnalysis.redundancy_state === "redundant") return "Over-constrained";
    if (solverAnalysis.coverage !== "exact" || solverAnalysis.freedom_state === "unknown") return "Partially analyzed";
    if (solverAnalysis.freedom_state === "fully_constrained") return "Fully constrained";
    return "Under-constrained";
  }, [committedEntities.length, solverAnalysis, solverAnalysisError, solverOutcome]);

  const solverStatusDetail = useMemo(() => {
    if (sketchStatus === "Fully constrained") return "All modeled movement is constrained.";
    if (sketchStatus === "Under-constrained") return "Some modeled geometry can still move.";
    if (sketchStatus === "Over-constrained") return "One or more constraints are redundant.";
    if (sketchStatus === "Conflicting" || sketchStatus === "Conflict") return "Constraints disagree; resolve the conflict before committing dependent edits.";
    if (sketchStatus === "Partially analyzed") return "Some geometry or constraints are outside exact solver coverage.";
    if (sketchStatus === "Analysis unavailable") return "Live constraint analysis is temporarily unavailable.";
    return null;
  }, [sketchStatus]);

  const solverAnalysisDebugLines = useMemo(() => {
    if (!solverAnalysis) return solverAnalysisError ? [`Analysis error: ${solverAnalysisError}`] : ["No solver analysis received yet."];
    return [
      `Backend: ${solverRun?.backend || "unknown"}`,
      `Run outcome: ${solverRun?.outcome || "unknown"}`,
      `Termination: ${solverRun?.termination_reason || "unknown"}`,
      `Feasible: ${solverRun?.feasible ?? "unknown"}`,
      `Residual norm: ${solverRun?.residual_norm ?? "unavailable"}`,
      `Max residual: ${solverRun?.max_abs_residual ?? "unavailable"}`,
      `Residual rows: ${solverRun?.residual_count ?? "unavailable"}`,
      `Jacobian: ${solverRun?.jacobian_strategy ?? "unavailable"}`,
      `Jacobian rank: ${solverRun?.jacobian_rank ?? "unavailable"}`,
      `Function evaluations: ${solverRun?.function_evaluations ?? "unavailable"}`,
      `Deterministic seeds: ${solverRun?.seed_count ?? "unavailable"}`,
      `Characteristic length (mm): ${solverRun?.characteristic_length_mm ?? "unavailable"}`,
      `Coverage: ${solverAnalysis.coverage}`,
      `Freedom: ${solverAnalysis.freedom_state}`,
      `Consistency: ${solverAnalysis.consistency_state}`,
      `Redundancy: ${solverAnalysis.redundancy_state}`,
      `Tracked variables: ${solverAnalysis.tracked_variable_count}`,
      `Independent equations: ${solverAnalysis.independent_equation_count}`,
      `Remaining DOF: ${solverAnalysis.remaining_dof ?? "unknown"}`,
      `Tracked DOF upper bound: ${solverAnalysis.remaining_tracked_dof_upper_bound}`,
      `Unsupported constraints: ${solverAnalysis.unsupported_constraint_ids.join(", ") || "none"}`,
      `Invalid constraints: ${solverAnalysis.invalid_constraint_ids.join(", ") || "none"}`,
      `Redundant constraints: ${solverAnalysis.redundant_constraint_ids.join(", ") || "none"}`,
      `Conflicting constraints: ${solverAnalysis.conflicting_constraint_ids.join(", ") || "none"}`,
      `Unmodeled entities: ${solverAnalysis.unmodeled_entity_ids.join(", ") || "none"}`,
      ...(solverAnalysis.diagnostics.length ? solverAnalysis.diagnostics.map((diagnostic) => `Diagnostic: ${diagnostic}`) : []),
    ];
  }, [solverAnalysis, solverAnalysisError, solverRun]);

  const dimensionSummary = useMemo(() => {
    const pointCount = committedEntities.filter((entity) => entity.type === "point_2d").length;
    const lineCount = committedEntities.filter((entity) => entity.type === "line_2d" || entity.type === "construction_line_2d").length;
    return `${pointCount} points • ${lineCount} lines • ${committedContext.constraints.length} constraints`;
  }, [committedContext.constraints.length, committedEntities]);

  const selectedIdsAreReferenced = (entityIds: string[]): boolean => {
    const selected = new Set(entityIds);
    const referencedByConstraint = committedContext.constraints.some((constraint) => {
      const record = constraint as Record<string, unknown>;
      const references = [record.points, record.line_points, record.entities]
        .flatMap((value) => Array.isArray(value) ? value : [])
        .concat([record.point_id, record.circle_id]);
      return references.some((reference) => typeof reference === "string" && selected.has(reference));
    });
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
        const references = Array.isArray(record.points)
          ? record.points
          : Array.isArray(record.line_points)
            ? [record.point_id, ...record.line_points]
            : Array.isArray(record.entities)
              ? record.entities
          : typeof record.point_id === "string"
            ? [record.point_id]
            : typeof record.circle_id === "string"
              ? [record.circle_id]
              : [];
        return references.some((entityId) => typeof entityId === "string" && selectedEntityIds.includes(entityId));
      }).map((constraint, index) => {
        const type = typeof constraint.type === "string" ? constraint.type : "constraint";
        const friendlyType = {
          distance_constraint: "Distance",
          horizontal_distance_constraint: "Horizontal distance",
          vertical_distance_constraint: "Vertical distance",
          radius_constraint: "Radius",
          diameter_constraint: "Diameter",
          angle_constraint: "Angle",
          horizontal_constraint: "Horizontal",
          vertical_constraint: "Vertical",
          coincident_constraint: "Coincident",
          parallel_constraint: "Parallel",
          perpendicular_constraint: "Perpendicular",
          equal_length_constraint: "Equal length",
          equal_angle_constraint: "Equal angle",
          fixed_point_constraint: "Fixed",
          midpoint_constraint: "Midpoint",
          collinear_constraint: "Collinear",
          symmetric_constraint: "Symmetric",
          concentric_constraint: "Concentric",
          tangent_constraint: "Tangent",
        }[type] || "Constraint";
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
        for (const dimension of ["radius", "diameter"] as const) {
          if (typeof (constraint as Record<string, unknown>)[dimension] === "number") {
            const value = (constraint as Record<string, unknown>)[dimension] as number;
            const unit = typeof (constraint as Record<string, unknown>).unit === "string" ? (constraint as Record<string, unknown>).unit : "mm";
            detailParts.push(`${dimension} ${value} ${unit}`);
          }
        }
        return `${index + 1}. ${friendlyType}${detailParts.length ? ` • ${detailParts.join(" • ")}` : ""}`;
      }),
    [committedContext.constraints, selectedEntityIds],
  );

  const constraintDebugSummaries = useMemo(
    () =>
      committedContext.constraints.filter((constraint) => {
        if (selectedEntityIds.length === 0) return true;
        const record = constraint as Record<string, unknown>;
        const references = Array.isArray(record.points)
          ? record.points
          : Array.isArray(record.line_points)
            ? [record.point_id, ...record.line_points]
            : Array.isArray(record.entities)
              ? record.entities
              : typeof record.point_id === "string"
                ? [record.point_id]
                : [];
        return references.some((entityId) => typeof entityId === "string" && selectedEntityIds.includes(entityId));
      }).map((constraint, index) => {
        const type = typeof constraint.type === "string" ? constraint.type : "constraint";
        const id = typeof constraint.id === "string" ? constraint.id : `constraint_${index + 1}`;
        return `${index + 1}. ${type} • ${id}`;
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

  const orderedPointSelectionIds = useMemo(
    () => selectedEntityIds.filter((entityId) => committedEntities.some((entity) => entity.id === entityId && isPointEntity(entity))),
    [committedEntities, selectedEntityIds],
  );

  const selectedLineEntities = useMemo(() => selectedEntities.filter(isLineEntity), [selectedEntities]);
  const constructionSelection = useMemo(
    () => selectedEntities.filter((entity) => isPointEntity(entity) || isLineEntity(entity)),
    [selectedEntities],
  );
  const canSetConstruction = constructionSelection.length > 0 && constructionSelection.length === selectedEntities.length;
  const selectionIsConstruction = canSetConstruction && constructionSelection.every((entity) =>
    isPointEntity(entity) ? Boolean(entity.construction) : entity.type === "construction_line_2d",
  );
  const selectedCenterEntities = useMemo(
    () => selectedEntityIds
      .map((entityId) => committedEntities.find((entity) => entity.id === entityId))
      .filter((entity): entity is Extract<SketchMathEntity, { type: "circle_2d" | "arc_2d" }> => Boolean(entity && (isCircleEntity(entity) || isArcEntity(entity)))),
    [committedEntities, selectedEntityIds],
  );
  const selectedCircleEntities = useMemo(
    () => selectedCenterEntities.filter(isCircleEntity),
    [selectedCenterEntities],
  );
  const tangentSelectionIds = useMemo(() => {
    if (selectedLineEntities.length === 1 && selectedCircleEntities.length === 1) {
      return [selectedLineEntities[0].id, selectedCircleEntities[0].id];
    }
    if (selectedCircleEntities.length === 2) {
      return selectedCircleEntities.map((entity) => entity.id);
    }
    return [];
  }, [selectedCircleEntities, selectedLineEntities]);
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
    if (selectedEntities.length === 1 && isClosedProfileEntity(selectedEntities[0])) {
      return { ...base, kind: "profile", summary: "Selected: Profile", detail: "Closed profile: valid" };
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
      return {
        ...base,
        kind: "one_line",
        summary: line.type === "construction_line_2d" ? "Selected: Construction line" : "Selected: 1 line",
        canSetLength: true,
        canMakeHorizontal: true,
        canMakeVertical: true,
      };
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
      return {
        ...base,
        kind: "one_point",
        summary: point.construction ? "Selected: Construction point" : "Selected: 1 point",
        canFixCorner: true,
      };
    }
    if (rectangleDimensions) {
      return { ...base, kind: "rectangle", summary: "Selected: Rectangle", parentSummary: "Parent: Rectangle", canFixCorner: true };
    }
    if (selectedEntities.length === 1 && isCircleEntity(selectedEntities[0])) {
      return { ...base, kind: "circle", summary: "Selected: Circle", detail: `Radius: ${selectedEntities[0].radius} mm` };
    }
    if (selectedEntities.length === 1 && isArcEntity(selectedEntities[0])) {
      return {
        ...base,
        kind: "arc",
        summary: `Selected: ${selectedEntities[0].construction === "three_point" ? "3-point arc" : "Arc"}`,
        detail: `Radius: ${Number(selectedEntities[0].radius.toFixed(2))} mm; sweep: ${Number(Math.abs(selectedEntities[0].sweep_angle_deg).toFixed(2))} deg`,
      };
    }
    return { ...base, kind: "mixed", summary: `Selected: ${selectedEntityIds.length} entities` };
  }, [rectangleDimensions, rectangleSelectionDetail, selectedEntities, selectedEntityIds.length, selectedHoleSummary, selectedLineEntities, selectedPointEntities]);

  const reconcileSelection = useCallback((items: SketchMathEntity[]) => {
    const validIds = new Set(items.map((entity) => entity.id));
    setSelectedEntityIds((current) => current.filter((entityId) => validIds.has(entityId)));
  }, []);

  const syncSnapshot = useCallback((snapshot: SketchMathSessionSnapshot) => {
    setCommittedContext(snapshot.selection_context);
    reconcileSelection(snapshot.selection_context.items);
    setHistory(snapshot.history);
    setCanUndo(Boolean(snapshot.can_undo ?? snapshot.history_length > 0));
    setCanRedo(Boolean(snapshot.can_redo));
    setSketchDocument(snapshot.document || null);
    setCanFeatureUndo(Boolean(snapshot.can_feature_undo));
    setCanFeatureRedo(Boolean(snapshot.can_feature_redo));
    window.localStorage.setItem(SESSION_STORAGE_KEY, snapshot.session_id);
  }, [reconcileSelection]);

  const syncCommandResponse = (response: SketchMathCommandResponse) => {
    setCommittedContext(response.selection_context || response.result.after);
    reconcileSelection((response.selection_context || response.result.after).items);
    if (response.history) {
      setHistory(response.history);
    } else {
      setHistory((current) => [
        ...current,
        {
          command: response.result.command,
          committed: response.result.status === "committed",
          before: response.result.before,
          after: response.result.after,
        },
      ]);
    }
    setCanUndo(Boolean(response.can_undo ?? true));
    setCanRedo(Boolean(response.can_redo));
    setSketchDocument(response.document || null);
    setCanFeatureUndo(Boolean(response.can_feature_undo));
    setCanFeatureRedo(Boolean(response.can_feature_redo));
    window.localStorage.setItem(SESSION_STORAGE_KEY, response.session_id);
  };

  const syncFeatureResponse = (response: SketchMathFeatureCommandResponse) => {
    setSketchDocument(response.document || response.result.after);
    setCanFeatureUndo(Boolean(response.can_feature_undo));
    setCanFeatureRedo(Boolean(response.can_feature_redo));
    window.localStorage.setItem(SESSION_STORAGE_KEY, response.session_id);
  };

  useEffect(() => {
    if (!artifactJobsEnabled || !sessionId) return;
    const activeJobs = Object.values(artifactJobs).filter((job) => job.state === "READY" || job.state === "RUNNING");
    if (activeJobs.length === 0) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const updates = await Promise.all(activeJobs.map((job) => getSketchMathArtifactJob(sessionId, job.job_id)));
        if (cancelled) return;
        setArtifactJobs((current) => ({
          ...current,
          ...Object.fromEntries(updates.map((job) => [job.feature_id, job])),
        }));
        const completed = updates.filter((job) => job.state === "DONE");
        if (completed.length > 0) {
          syncSnapshot(await getSketchMathSession(sessionId));
          appendEvents(completed.map((job) => makeTelemetryEvent("artifact_created", {
            detail: `${job.format.toUpperCase()} artifact available for ${job.feature_id} at revision ${job.input_revision}.`,
            raw: job,
          })));
        }
        const failed = updates.find((job) => job.state === "FAILED");
        if (failed?.error) {
          setUserError(failed.error.message, JSON.stringify(failed.error.detail, null, 2));
        }
      } catch (err) {
        if (!cancelled) {
          const { message, debugText } = normalizeCaughtError(err, "Artifact status polling failed");
          setUserError(message, debugText);
        }
      }
    }, 200);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [appendEvents, artifactJobs, artifactJobsEnabled, sessionId, syncSnapshot]);

  const refreshTopology = useCallback(async (activeSessionId: string) => {
    const requestId = topologyRequestRef.current + 1;
    topologyRequestRef.current = requestId;
    try {
      const response = await previewSketchMathCommand(activeSessionId, buildDetectRegionsCommand());
      const detected = topologyFromMetadata(response.result.metadata.topology);
      if (requestId === topologyRequestRef.current) {
        setTopology(detected);
        setSelectedRegionId((current) =>
          current && detected?.regions.some((region) => region.region_id === current) ? current : null,
        );
      }
    } catch {
      if (requestId === topologyRequestRef.current) {
        setTopology(null);
        setSelectedRegionId(null);
      }
    }
  }, []);

  useEffect(() => {
    if (!sessionId || loading) return;
    void refreshTopology(sessionId);
  }, [committedContext, loading, refreshTopology, sessionId]);

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
      if (nextCommand.command_type === "solve_constraints") setSolverOutcome(null);
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

  const commitFeatureOperation = async (command: SketchMathFeatureCommand): Promise<boolean> => {
    if (!sessionId || !sketchDocument || featureBusy) return false;
    setFeatureBusy(true);
    try {
      const response = await commitSketchMathFeature(sessionId, command);
      syncFeatureResponse(response);
      clearErrorState();
      toast({
        title: "Feature history updated",
        status: "success",
        duration: 1800,
        isClosable: true,
      });
      return true;
    } catch (err) {
      const { message, debugText } = normalizeCaughtError(err, "Feature operation failed");
      setUserError(message, debugText);
      if (err instanceof SketchMathApiError && err.code === "revision_conflict") {
        try {
          syncSnapshot(await getSketchMathSession(sessionId));
        } catch {
          // Preserve the original revision-conflict error when refresh also fails.
        }
      }
      toast({
        title: "Feature operation failed",
        description: message,
        status: "error",
        duration: 2500,
        isClosable: true,
      });
      return false;
    } finally {
      setFeatureBusy(false);
    }
  };

  const handleAddFeatureExtrusion = async (
    profile: Extract<SketchMathEntity, { type: "profile_2d" }>,
    depth: number,
  ) => {
    if (!sketchDocument) return;
    const body = sketchDocument.bodies[0];
    const sketch = sketchDocument.sketches[0];
    if (!body || !sketch) {
      setUserError("The active document does not contain a body and sketch for this feature.");
      return;
    }
    const stem = `feature_${profile.id.replace(/[^a-zA-Z0-9_-]+/g, "_")}`;
    const existingIds = new Set(sketchDocument.features.map((feature) => feature.feature_id));
    let featureId = stem;
    let suffix = 2;
    while (existingIds.has(featureId)) {
      featureId = `${stem}_${suffix}`;
      suffix += 1;
    }
    const dependency = [...sketchDocument.features].reverse().find(
      (candidate): candidate is Extract<SketchMathFeature, { feature_type: "extrude" }> => candidate.feature_type === "extrude",
    );
    const dependencyRecord = dependency
      ? sketchDocument.last_rebuild?.records.find((record) => record.feature_id === dependency.feature_id)
      : null;
    const dependencyTop = dependencyRecord?.generated_topology.find(
      (reference) => reference.topology_type === "face" && reference.role === "top",
    );
    if (dependency && !dependencyTop) {
      setUserError("The prior feature does not expose a semantic top face for attachment.");
      return;
    }
    const feature: SketchMathFeature = {
      feature_id: featureId,
      feature_type: "extrude",
      name: `Extrude ${sketchDocument.features.length + 1}`,
      body_id: body.body_id,
      sketch_id: sketch.sketch_id,
      profile_id: profile.id,
      source_region_id: profile.source_region_id || null,
      dependencies: dependency ? [dependency.feature_id] : [],
      topology_references: dependency && dependencyTop ? [
        {
          reference_id: dependencyTop.reference_id,
          owner_feature_id: dependency.feature_id,
          topology_type: "face",
          role: "top",
          source_entity_id: dependencyTop.source_entity_id || null,
          expected_signature: dependencyTop.geometric_signature,
        },
      ] : [],
      parameters: {
        depth_mm: depth,
        extent: "one_sided",
        direction: "positive",
        operation: dependency ? "add" : "new_body",
      },
      suppressed: false,
    };
    await commitFeatureOperation({
      version: "1.0",
      operation_id: `add_${featureId}_${Date.now().toString(36)}`,
      mode: "commit",
      base_revision: sketchDocument.revision,
      operation_type: "add_feature",
      parameters: { feature },
    });
  };

  const handleUpdateFeatureDepth = async (
    feature: Extract<SketchMathFeature, { feature_type: "extrude" }>,
    depth: number,
  ) => {
    if (!sketchDocument) return;
    await commitFeatureOperation({
      version: "1.0",
      operation_id: `replace_${feature.feature_id}_${Date.now().toString(36)}`,
      mode: "commit",
      base_revision: sketchDocument.revision,
      operation_type: "replace_feature",
      target_id: feature.feature_id,
      parameters: {
        feature: {
          ...feature,
          parameters: { ...feature.parameters, depth_mm: depth },
        },
      },
    });
  };

  const handleSetDesignParameter = async (parameterId: string, value: number) => {
    if (!sketchDocument) return;
    await commitFeatureOperation({
      version: "1.1",
      operation_id: `set_${parameterId}_${Date.now().toString(36)}`,
      mode: "commit",
      base_revision: sketchDocument.revision,
      operation_type: "set_design_parameter",
      target_id: parameterId,
      parameters: { value },
    });
  };

  const handleRenameFeature = async (feature: SketchMathFeature, name: string) => {
    if (!sketchDocument) return;
    const normalizedName = name.trim();
    if (!normalizedName || normalizedName === feature.name) return;
    await commitFeatureOperation({
      version: "1.0",
      operation_id: `rename_${feature.feature_id}_${Date.now().toString(36)}`,
      mode: "commit",
      base_revision: sketchDocument.revision,
      operation_type: "replace_feature",
      target_id: feature.feature_id,
      parameters: {
        feature: {
          ...feature,
          name: normalizedName,
        },
      },
    });
  };

  const handleAddFullRevolve = async (
    profile: Extract<SketchMathEntity, { type: "profile_2d" }>,
    axis: Extract<SketchMathEntity, { type: "line_2d" | "construction_line_2d" }>,
  ) => {
    if (!sketchDocument || !revolveFeaturesEnabled || sketchDocument.features.length > 0) return;
    const body = sketchDocument.bodies[0];
    const sketch = sketchDocument.sketches[0];
    if (!body || !sketch) {
      setUserError("The active document does not contain a body and sketch for this feature.");
      return;
    }
    const featureId = `revolve_${profile.id.replace(/[^a-zA-Z0-9_-]+/g, "_")}`;
    const feature: SketchMathFeature = {
      feature_id: featureId,
      feature_type: "revolve",
      name: "Revolve 1",
      body_id: body.body_id,
      sketch_id: sketch.sketch_id,
      profile_id: profile.id,
      source_region_id: profile.source_region_id || null,
      dependencies: [],
      topology_references: [],
      parameters: {
        axis_entity_id: axis.id,
        angle_deg: 360,
        operation: "new_body",
      },
      suppressed: false,
    };
    await commitFeatureOperation({
      version: "1.0",
      operation_id: `add_${featureId}_${Date.now().toString(36)}`,
      mode: "commit",
      base_revision: sketchDocument.revision,
      operation_type: "add_feature",
      parameters: { feature },
    });
  };

  const handleUpdateFullRevolve = async (
    feature: Extract<SketchMathFeature, { feature_type: "revolve" }>,
    axisId: string,
    angle: number,
  ) => {
    if (!sketchDocument || !revolveFeaturesEnabled || angle !== 360) return;
    await commitFeatureOperation({
      version: "1.0",
      operation_id: `replace_${feature.feature_id}_${Date.now().toString(36)}`,
      mode: "commit",
      base_revision: sketchDocument.revision,
      operation_type: "replace_feature",
      target_id: feature.feature_id,
      parameters: {
        feature: {
          ...feature,
          parameters: { ...feature.parameters, axis_entity_id: axisId, angle_deg: angle },
        },
      },
    });
  };

  const handleAddOuterFillet = async (
    target: Extract<SketchMathFeature, { feature_type: "extrude" }>,
    edgeReferences: SketchMathSemanticTopologyReference[],
    radius: number,
  ) => {
    if (
      !sketchDocument
      || !filletFeaturesEnabled
      || sketchDocument.features.length !== 1
      || edgeReferences.length === 0
    ) return;
    const featureId = `fillet_${target.feature_id.replace(/[^a-zA-Z0-9_-]+/g, "_")}`;
    const feature: SketchMathFeature = {
      feature_id: featureId,
      feature_type: "fillet",
      name: "Outer edge fillet",
      body_id: target.body_id,
      sketch_id: target.sketch_id,
      profile_id: null,
      source_region_id: null,
      dependencies: [target.feature_id],
      topology_references: edgeReferences.map((edge) => ({
        reference_id: edge.reference_id,
        owner_feature_id: target.feature_id,
        topology_type: "edge",
        role: edge.role,
        source_entity_id: edge.source_entity_id || null,
        expected_signature: edge.geometric_signature,
      })),
      parameters: { radius_mm: radius, operation: "modify" },
      suppressed: false,
    };
    await commitFeatureOperation({
      version: "1.0",
      operation_id: `add_${featureId}_${Date.now().toString(36)}`,
      mode: "commit",
      base_revision: sketchDocument.revision,
      operation_type: "add_feature",
      parameters: { feature },
    });
  };

  const handleUpdateFilletRadius = async (
    feature: Extract<SketchMathFeature, { feature_type: "fillet" }>,
    radius: number,
  ) => {
    if (!sketchDocument || !filletFeaturesEnabled) return;
    await commitFeatureOperation({
      version: "1.0",
      operation_id: `replace_${feature.feature_id}_${Date.now().toString(36)}`,
      mode: "commit",
      base_revision: sketchDocument.revision,
      operation_type: "replace_feature",
      target_id: feature.feature_id,
      parameters: {
        feature: {
          ...feature,
          parameters: { ...feature.parameters, radius_mm: radius },
        },
      },
    });
  };

  const handleAddOuterChamfer = async (
    target: Extract<SketchMathFeature, { feature_type: "extrude" }>,
    edgeReferences: SketchMathSemanticTopologyReference[],
    distance: number,
  ) => {
    if (
      !sketchDocument
      || !chamferFeaturesEnabled
      || sketchDocument.features.length !== 1
      || edgeReferences.length === 0
    ) return;
    const featureId = `chamfer_${target.feature_id.replace(/[^a-zA-Z0-9_-]+/g, "_")}`;
    const feature: SketchMathFeature = {
      feature_id: featureId,
      feature_type: "chamfer",
      name: "Outer edge chamfer",
      body_id: target.body_id,
      sketch_id: target.sketch_id,
      profile_id: null,
      source_region_id: null,
      dependencies: [target.feature_id],
      topology_references: edgeReferences.map((edge) => ({
        reference_id: edge.reference_id,
        owner_feature_id: target.feature_id,
        topology_type: "edge",
        role: edge.role,
        source_entity_id: edge.source_entity_id || null,
        expected_signature: edge.geometric_signature,
      })),
      parameters: { distance_mm: distance, operation: "modify" },
      suppressed: false,
    };
    await commitFeatureOperation({
      version: "1.0",
      operation_id: `add_${featureId}_${Date.now().toString(36)}`,
      mode: "commit",
      base_revision: sketchDocument.revision,
      operation_type: "add_feature",
      parameters: { feature },
    });
  };

  const handleUpdateChamferDistance = async (
    feature: Extract<SketchMathFeature, { feature_type: "chamfer" }>,
    distance: number,
  ) => {
    if (!sketchDocument || !chamferFeaturesEnabled) return;
    await commitFeatureOperation({
      version: "1.0",
      operation_id: `replace_${feature.feature_id}_${Date.now().toString(36)}`,
      mode: "commit",
      base_revision: sketchDocument.revision,
      operation_type: "replace_feature",
      target_id: feature.feature_id,
      parameters: {
        feature: {
          ...feature,
          parameters: { ...feature.parameters, distance_mm: distance },
        },
      },
    });
  };

  const handleAddSimpleHole = async (
    target: Extract<SketchMathFeature, { feature_type: "extrude" }>,
    topReference: SketchMathSemanticTopologyReference,
    position: [number, number],
    diameter: number,
    termination: "through" | "blind",
    depth: number | null,
  ) => {
    if (!sketchDocument || !holeFeaturesEnabled) return;
    const stem = `hole_${target.feature_id.replace(/[^a-zA-Z0-9_-]+/g, "_")}`;
    const existingIds = new Set(sketchDocument.features.map((feature) => feature.feature_id));
    let featureId = stem;
    let suffix = 2;
    while (existingIds.has(featureId)) {
      featureId = `${stem}_${suffix}`;
      suffix += 1;
    }
    const feature: SketchMathFeature = {
      feature_id: featureId,
      feature_type: "hole",
      name: `Hole ${sketchDocument.features.filter((item) => item.feature_type === "hole").length + 1}`,
      body_id: target.body_id,
      sketch_id: target.sketch_id,
      profile_id: null,
      source_region_id: null,
      dependencies: [target.feature_id],
      topology_references: [
        {
          reference_id: topReference.reference_id,
          owner_feature_id: target.feature_id,
          topology_type: "face",
          role: "top",
          source_entity_id: topReference.source_entity_id || null,
          expected_signature: topReference.geometric_signature,
        },
      ],
      parameters: {
        style: "simple",
        termination,
        position_mm: position,
        diameter_mm: diameter,
        depth_mm: termination === "blind" ? depth : null,
        operation: "cut",
      },
      suppressed: false,
    };
    await commitFeatureOperation({
      version: "1.0",
      operation_id: `add_${featureId}_${Date.now().toString(36)}`,
      mode: "commit",
      base_revision: sketchDocument.revision,
      operation_type: "add_feature",
      parameters: { feature },
    });
  };

  const handleUpdateHole = async (
    feature: Extract<SketchMathFeature, { feature_type: "hole" }>,
    parameters: SketchMathHoleParameters,
  ) => {
    if (!sketchDocument || !holeFeaturesEnabled) return;
    await commitFeatureOperation({
      version: "1.0",
      operation_id: `replace_${feature.feature_id}_${Date.now().toString(36)}`,
      mode: "commit",
      base_revision: sketchDocument.revision,
      operation_type: "replace_feature",
      target_id: feature.feature_id,
      parameters: {
        feature: {
          ...feature,
          parameters,
        },
      },
    });
  };

  const handleFeatureUndo = async () => {
    if (!sessionId || featureBusy) return;
    setFeatureBusy(true);
    try {
      syncSnapshot(await revertSketchMathFeature(sessionId));
      clearErrorState();
    } catch (err) {
      const { message, debugText } = normalizeCaughtError(err, "Feature undo failed");
      setUserError(message, debugText);
    } finally {
      setFeatureBusy(false);
    }
  };

  const handleFeatureRedo = async () => {
    if (!sessionId || featureBusy) return;
    setFeatureBusy(true);
    try {
      syncSnapshot(await redoSketchMathFeature(sessionId));
      clearErrorState();
    } catch (err) {
      const { message, debugText } = normalizeCaughtError(err, "Feature redo failed");
      setUserError(message, debugText);
    } finally {
      setFeatureBusy(false);
    }
  };

  const handleBuildFeatureArtifact = async (feature: SketchMathFeature, format: "step" | "stl") => {
    if (!sessionId || !sketchDocument || featureBusy || !artifactJobsEnabled) return;
    setFeatureBusy(true);
    try {
      const job = await startSketchMathArtifactJob(sessionId, feature.feature_id, sketchDocument.revision, format);
      setArtifactJobs((current) => ({ ...current, [feature.feature_id]: job }));
      if (job.state === "DONE") {
        syncSnapshot(await getSketchMathSession(sessionId));
      }
      clearErrorState();
    } catch (err) {
      const { message, debugText } = normalizeCaughtError(err, "Artifact build could not be started");
      setUserError(message, debugText);
    } finally {
      setFeatureBusy(false);
    }
  };

  const handleRetryFeatureArtifact = async (job: SketchMathArtifactJobManifest) => {
    if (!sessionId || featureBusy || !artifactJobsEnabled) return;
    setFeatureBusy(true);
    try {
      const retried = await retrySketchMathArtifactJob(sessionId, job.job_id);
      setArtifactJobs((current) => ({ ...current, [retried.feature_id]: retried }));
      clearErrorState();
    } catch (err) {
      const { message, debugText } = normalizeCaughtError(err, "Artifact retry could not be started");
      setUserError(message, debugText);
    } finally {
      setFeatureBusy(false);
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
    setArcDraft(null);
    setPolylineDraft(null);
    setSlotDraft(null);
    setPolygonDraft(null);
    setSelectionBox(null);
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
    const command = buildBatchCommand(
      commands.map((subcommand) => ({
        ...subcommand,
        // A fresh rectangle intentionally retains translational DOF. Keep the
        // intermediate solve diagnostic-only while committing the canonical
        // geometry, constraints, and profile as one atomic batch.
        mode: subcommand.command_type === "solve_constraints" ? "preview" as const : "commit" as const,
      })),
    );
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

  const commitCenterRectangle = async (center: Point, rawCorner: Point, forceSquare: boolean) => {
    const corner = centerRectangleCorner(center, rawCorner, forceSquare);
    const deltaX = corner.x - center.x;
    const deltaY = corner.y - center.y;
    const anchor = { x: center.x - deltaX, y: center.y - deltaY };
    await commitRectangle(anchor, corner, false);
  };

  const commitPolyline = async () => {
    if (!polylineDraft || polylineDraft.points.length < 2) return;
    const stamp = `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
    const pointIds = polylineDraft.points.map((_, index) => `polyline_${stamp}_p${index + 1}`);
    const lineIds = polylineDraft.points.slice(1).map((_, index) => `polyline_${stamp}_s${index + 1}`);
    const commands = [
      ...polylineDraft.points.map((point, index) => buildDefinePointCommand(point, pointIds[index], `Polyline point ${index + 1}`)),
      ...lineIds.map((lineId, index) => buildDefineLineCommand(
        polylineDraft.points[index],
        polylineDraft.points[index + 1],
        lineId,
        `Polyline segment ${index + 1}`,
        pointIds[index],
        pointIds[index + 1],
      )),
    ];
    const result = await commitCommand(buildBatchCommand(commands));
    if (result) {
      setSelectedEntityIds(lineIds);
      setPolylineDraft(null);
      setTool("select");
    }
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
    if (tool === "region_select") {
      if (!sessionId) return;
      void (async () => {
        try {
          const response = await previewSketchMathCommand(sessionId, buildSelectRegionCommand(point));
          const selectedTopology = topologyFromMetadata(response.result.metadata.topology);
          if (!selectedTopology) {
            setUserError("The backend returned an invalid topology selection payload.");
            return;
          }
          setTopology(selectedTopology);
          setPreviewResult(response.result);
          const selectedIds = selectedTopology.selection.region_ids;
          if (selectedTopology.selection.status === "selected" && selectedIds.length === 1) {
            setSelectedRegionId(selectedIds[0]);
            clearErrorState();
            return;
          }
          setSelectedRegionId(null);
          if (selectedTopology.selection.status === "boundary") {
            setUserError("The point is on a region boundary. Click clearly inside a region.");
          } else if (selectedTopology.selection.status === "ambiguous") {
            setUserError("The point matches multiple regions. Choose one from the region list.");
          } else {
            setUserError("No bounded region exists at that point.");
          }
        } catch (selectionError) {
          const { message, debugText } = normalizeCaughtError(selectionError, "Region selection failed");
          setSelectedRegionId(null);
          setUserError(message, debugText);
        }
      })();
      return;
    }
    if (tool === "point") {
      const pointId = `point_${Date.now().toString(36)}`;
      const nextCommand = buildDefinePointCommand(point, pointId);
      setDraftPoint(point);
      void commitCommand(nextCommand);
      setDraftPoint(null);
      setCircleDraft(null);
      setArcDraft(null);
      setSelectedEntityIds([pointId]);
      setTool("select");
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
        if (result) {
          setSelectedEntityIds([circleId]);
          setTool("select");
        }
      })();
      return;
    }
    if (tool === "arc" || tool === "three_point_arc") {
      if (!arcDraft) {
        setArcDraft({ points: [point], current: point });
        clearErrorState();
        return;
      }
      if (arcDraft.points.length === 1) {
        if (distanceBetween(arcDraft.points[0], point) <= 0.01) return;
        setArcDraft({ points: [...arcDraft.points, point], current: point });
        return;
      }
      const [first, second] = arcDraft.points;
      const stamp = `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
      const arcId = `arc_${stamp}`;
      const startId = `${arcId}_start`;
      const endId = `${arcId}_end`;
      const pointCommands = [buildDefinePointCommand(first, startId, "Arc start")];
      let arcCommand: SketchMathCommand;
      if (tool === "arc") {
        const centerId = `${arcId}_center`;
        pointCommands[0] = buildDefinePointCommand(first, centerId, "Arc center");
        pointCommands.push(buildDefinePointCommand(second, startId, "Arc start"));
        pointCommands.push(buildDefinePointCommand(point, endId, "Arc end"));
        arcCommand = buildDefineCenterArcCommand(first, second, point, arcId, { center: centerId, start: startId, end: endId });
      } else {
        const throughId = `${arcId}_through`;
        pointCommands.push(buildDefinePointCommand(second, throughId, "Arc through"));
        pointCommands.push(buildDefinePointCommand(point, endId, "Arc end"));
        arcCommand = buildDefineThreePointArcCommand(first, second, point, arcId, { start: startId, through: throughId, end: endId });
      }
      setArcDraft(null);
      void (async () => {
        const result = await commitCommand(buildBatchCommand([...pointCommands, arcCommand]));
        if (result) {
          setSelectedEntityIds([arcId]);
          setTool("select");
        }
      })();
      return;
    }
    if (tool === "slot") {
      if (!slotDraft) {
        setSlotDraft({ start: point, current: point });
        clearErrorState();
        return;
      }
      const width = Number(slotWidthValue);
      if (!Number.isFinite(width) || width <= 0 || distanceBetween(slotDraft.start, point) <= 0.01) {
        setUserError("Slot needs distinct centers and a positive width.");
        return;
      }
      const baseId = `slot_${Date.now().toString(36)}`;
      setSlotDraft(null);
      void (async () => {
        const result = await commitCommand(buildDefineSlotCommand(slotDraft.start, point, width, baseId));
        if (result) {
          setSelectedEntityIds([`profile_${baseId}`]);
          setTool("select");
        }
      })();
      return;
    }
    if (tool === "polygon") {
      if (!polygonDraft) {
        setPolygonDraft({ center: point, current: point });
        clearErrorState();
        return;
      }
      const sides = Number(polygonSidesValue);
      const radius = Number(distanceBetween(polygonDraft.center, point).toFixed(2));
      if (!Number.isInteger(sides) || sides < 3 || sides > 128 || radius <= 0) {
        setUserError("Polygon needs 3–128 sides and a positive radius.");
        return;
      }
      const baseId = `polygon_${Date.now().toString(36)}`;
      setPolygonDraft(null);
      void (async () => {
        const result = await commitCommand(buildDefineRegularPolygonCommand(polygonDraft.center, radius, sides, baseId));
        if (result) {
          setSelectedEntityIds([`profile_${baseId}`]);
          setTool("select");
        }
      })();
      return;
    }
    if (tool === "rectangle" || tool === "center_rectangle") {
      if (!rectangleDraft) {
        setRectangleDraft({ anchor: point, current: point });
        clearErrorState();
        canvasDragRef.current = null;
        return;
      }
      if (tool === "center_rectangle") {
        void commitCenterRectangle(rectangleDraft.anchor, point, false);
      } else {
        const resolvedCurrent = clampRectanglePoint(rectangleDraft.anchor, point, false);
        void commitRectangle(rectangleDraft.anchor, resolvedCurrent, false);
      }
      clearRectangleInteraction();
      setTool("select");
      return;
    }
    if (tool === "polyline") {
      if (!polylineDraft) {
        setPolylineDraft({ points: [point], current: point });
      } else if (distanceBetween(polylineDraft.points[polylineDraft.points.length - 1], point) > 0.01) {
        setPolylineDraft({ points: [...polylineDraft.points, point], current: point });
      }
      clearErrorState();
      return;
    }
    if (tool === "select") {
      setSelectedEntityIds([]);
      setRectangleSelectionDetail(null);
      setDimensionEditor(null);
      setDeletePrompt(null);
      clearErrorState();
      return;
    }
  };

  const handleCanvasMouseDown = (point: Point, event: React.MouseEvent<SVGSVGElement>) => {
    if (tool === "pan" && event.button === 0) {
      viewPanRef.current = { last: point };
      return;
    }
    if (tool === "box_select" && event.button === 0) {
      setSelectionBox({ start: point, current: point });
      return;
    }
    if ((tool !== "rectangle" && tool !== "center_rectangle") || event.button !== 0) {
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
    if (tool === "box_select" && selectionBox) {
      setSelectionBox({ ...selectionBox, current: point });
      return;
    }
    if (tool === "circle" && circleDraft) {
      setCircleDraft({ ...circleDraft, current: point });
      return;
    }
    if ((tool === "arc" || tool === "three_point_arc") && arcDraft) {
      setArcDraft({ ...arcDraft, current: point });
      return;
    }
    if (tool === "polyline" && polylineDraft) {
      setPolylineDraft({ ...polylineDraft, current: point });
      return;
    }
    if (tool === "slot" && slotDraft) {
      setSlotDraft({ ...slotDraft, current: point });
      return;
    }
    if (tool === "polygon" && polygonDraft) {
      setPolygonDraft({ ...polygonDraft, current: point });
      return;
    }
    if (tool !== "rectangle" && tool !== "center_rectangle") {
      return;
    }
    if (canvasDragRef.current) {
      const drag = canvasDragRef.current;
      const resolvedPoint = tool === "center_rectangle"
        ? centerRectangleCorner(drag.start, point, event.shiftKey || drag.forceSquare)
        : clampRectanglePoint(drag.start, point, event.shiftKey || drag.forceSquare);
      if (!drag.moved && distanceBetween(drag.start, point) < RECTANGLE_DRAG_THRESHOLD) {
        return;
      }
      drag.moved = true;
      setRectangleDraft({ anchor: drag.start, current: resolvedPoint });
      return;
    }
    if (rectangleDraft) {
      setRectangleDraft({
        anchor: rectangleDraft.anchor,
        current: tool === "center_rectangle"
          ? centerRectangleCorner(rectangleDraft.anchor, point, event.shiftKey)
          : clampRectanglePoint(rectangleDraft.anchor, point, event.shiftKey),
      });
    }
  };

  const handleCanvasMouseUp = (point: Point, event: React.MouseEvent<SVGSVGElement>) => {
    if (viewPanRef.current) {
      viewPanRef.current = null;
      return;
    }
    if (tool === "box_select" && selectionBox) {
      const nextSelection = committedEntities
        .filter((entity) => entityIntersectsBox(entity, selectionBox.start, point))
        .map((entity) => entity.id);
      setSelectedEntityIds(nextSelection);
      setRectangleSelectionDetail(null);
      setSelectionBox(null);
      setTool("select");
      clearErrorState();
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
    if (tool !== "rectangle" && tool !== "center_rectangle") {
      return;
    }
    const drag = canvasDragRef.current;
    if (!drag) {
      return;
    }
    if (drag.moved || distanceBetween(drag.start, point) >= RECTANGLE_DRAG_THRESHOLD) {
      ignoreNextCanvasClickRef.current = true;
      if (tool === "center_rectangle") {
        void commitCenterRectangle(drag.start, point, event.shiftKey || drag.forceSquare);
      } else {
        void commitRectangle(drag.start, point, event.shiftKey || drag.forceSquare);
      }
      clearRectangleInteraction();
      setTool("select");
      return;
    }
    canvasDragRef.current = null;
  };

  const handleCanvasContextMenu = () => {
    if (tool === "rectangle" || tool === "center_rectangle") {
      clearRectangleInteraction();
      clearErrorState();
    }
    if (tool === "polyline") {
      setPolylineDraft(null);
      clearErrorState();
    }
    if (tool === "slot") {
      setSlotDraft(null);
      clearErrorState();
    }
    if (tool === "polygon") {
      setPolygonDraft(null);
      clearErrorState();
    }
    if (tool === "box_select") {
      setSelectionBox(null);
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
        setArcDraft(null);
        setPolylineDraft(null);
        setSlotDraft(null);
        setPolygonDraft(null);
        setSelectionBox(null);
        setTool("select");
        clearErrorState();
        return;
      }
      if (isTypingField) {
        return;
      }
      if (event.key === "Enter" && tool === "polyline" && polylineDraft?.points.length && polylineDraft.points.length >= 2) {
        event.preventDefault();
        void commitPolyline();
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
  }, [polylineDraft, rectangleSelectionDetail, selectedEntityIds, selectedRectangleBaseId, tool]);

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

  const runQuickAxisDistance = async (axis: "horizontal" | "vertical") => {
    if (lengthSelectionPointIds.length < 2) return;
    const value = Number(lengthValue);
    if (!Number.isFinite(value) || value <= 0) {
      setUserError("Axis distance must be a positive number.");
      return;
    }
    await commitCommand(
      axis === "horizontal"
        ? buildSetHorizontalDistanceCommand(lengthSelectionPointIds, value)
        : buildSetVerticalDistanceCommand(lengthSelectionPointIds, value),
    );
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

  const runQuickFixed = async () => {
    if (orderedPointSelectionIds.length === 1) await commitCommand(buildFixedCommand(orderedPointSelectionIds[0]));
  };

  const runQuickMidpoint = async () => {
    if (orderedPointSelectionIds.length === 3) await commitCommand(buildMidpointCommand(orderedPointSelectionIds));
  };

  const runQuickCollinear = async () => {
    if (orderedPointSelectionIds.length === 3) await commitCommand(buildCollinearCommand(orderedPointSelectionIds));
  };

  const runQuickSymmetric = async () => {
    if (orderedPointSelectionIds.length === 4) await commitCommand(buildSymmetricCommand(orderedPointSelectionIds));
  };

  const runQuickConcentric = async () => {
    if (selectedCenterEntities.length === 2) await commitCommand(buildConcentricCommand(selectedCenterEntities.map((entity) => entity.id)));
  };

  const runQuickTangent = async () => {
    if (tangentSelectionIds.length === 2) await commitCommand(buildTangentCommand(tangentSelectionIds));
  };

  const runSetConstruction = async () => {
    if (canSetConstruction) {
      await commitCommand(buildSetConstructionCommand(constructionSelection.map((entity) => entity.id), !selectionIsConstruction));
    }
  };

  const runUpdateCircle = async () => {
    if (!selectedCircle) return;
    const radius = Number(circleRadiusValue);
    if (!Number.isFinite(radius) || radius <= 0) {
      setUserError("Circle radius must be a positive number.");
      return;
    }
    await commitCommand(buildSetRadiusCommand(selectedCircle.id, radius));
  };

  const runUpdateCircleDiameter = async () => {
    if (!selectedCircle) return;
    const diameter = Number(circleDiameterValue);
    if (!Number.isFinite(diameter) || diameter <= 0) {
      setUserError("Circle diameter must be a positive number.");
      return;
    }
    await commitCommand(buildSetDiameterCommand(selectedCircle.id, diameter));
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

  const orderedSelectedLineIds = () => selectedEntityIds.filter((entityId) => {
    const entity = committedEntities.find((candidate) => candidate.id === entityId);
    return Boolean(entity && isLineEntity(entity));
  });

  const runSplitLine = async () => {
    const [lineId] = orderedSelectedLineIds();
    if (!lineId || orderedSelectedLineIds().length !== 1) return;
    const result = await commitCommand(buildSplitLineCommand(lineId));
    if (result) setSelectedEntityIds(result.changed_entity_ids);
  };

  const runTrimLine = async () => {
    const lineIds = orderedSelectedLineIds();
    if (lineIds.length !== 2) return;
    const result = await commitCommand(buildTrimLineCommand(lineIds[0], lineIds[1]));
    if (result) setSelectedEntityIds([lineIds[0]]);
  };

  const runExtendLine = async () => {
    const lineIds = orderedSelectedLineIds();
    if (lineIds.length !== 2) return;
    const result = await commitCommand(buildExtendLineCommand(lineIds[0], lineIds[1]));
    if (result) setSelectedEntityIds([lineIds[0]]);
  };

  const runOffsetCurve = async () => {
    if (selectedEntities.length !== 1 || !["line_2d", "construction_line_2d", "circle_2d", "arc_2d"].includes(selectedEntities[0].type)) return;
    const distance = Number(offsetValue);
    if (!Number.isFinite(distance) || distance <= 0) {
      setUserError("Offset distance must be positive.");
      return;
    }
    const result = await commitCommand(buildOffsetCurveCommand(selectedEntities[0].id, distance));
    if (result) setSelectedEntityIds(result.changed_entity_ids.slice(-1));
  };

  const runDuplicate = async () => {
    if (selectedEntityIds.length === 0) return;
    const result = await commitCommand(buildCopyLinearCommand(selectedEntityIds, { x: 10, y: 10 }, 1));
    if (result) setSelectedEntityIds(result.changed_entity_ids);
  };

  const runLinearPattern = async () => {
    const count = Number(patternCountValue);
    if (selectedEntityIds.length === 0 || !Number.isInteger(count) || count < 1 || count > 32) {
      setUserError("Pattern count must be an integer from 1 to 32.");
      return;
    }
    const result = await commitCommand(buildCopyLinearCommand(selectedEntityIds, { x: 25, y: 0 }, count));
    if (result) setSelectedEntityIds(result.changed_entity_ids);
  };

  const runMirrorSelection = async () => {
    if (selectedEntityIds.length === 0) return;
    await commitCommand(buildMirrorCommand(selectedEntityIds, 0));
  };

  const promoteRegion = async (regionId: string) => {
    const result = await commitCommand(
      buildMakeRegionProfileCommand(regionId, `profile_region_${Date.now().toString(36)}`),
    );
    if (!result) return;
    const profileId = typeof result.metadata.profile_id === "string" ? result.metadata.profile_id : null;
    if (profileId) setSelectedEntityIds([profileId]);
    setSelectedRegionId(null);
    setTool("select");
  };

  const handleToolChange = (nextTool: SketchMathMode) => {
    if (nextTool !== tool) {
      clearRectangleInteraction();
      setHolePlacement(null);
      setDraftPoint(null);
      setCircleDraft(null);
      setArcDraft(null);
      setPolylineDraft(null);
      setSlotDraft(null);
      setPolygonDraft(null);
      setSelectionBox(null);
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
    if (nextTool === "region_select" && sessionId) {
      void refreshTopology(sessionId);
    }
    setTool(nextTool);
  };

  if (!enabled) {
    return (
      <Box className="sketchmath-shell" data-testid="sketchmath-workspace">
        <VStack align="start" spacing={4} className="sketchmath-disabled">
          <Heading>SketchMath is disabled</Heading>
          <Text>Set <code>FRIDAY_SKETCHMATH_ENABLED=1</code> and <code>REACT_APP_SKETCHMATH_ENABLED=1</code> to open the drawing pad.</Text>
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
      : tool === "center_rectangle"
        ? "Click or drag from the rectangle center to a corner. Hold Shift for a centered square."
      : tool === "polyline"
        ? "Click each polyline vertex, then press Enter or use Finish polyline. Escape cancels the draft."
      : tool === "slot"
        ? slotDraft ? "Click the second slot center." : "Click the first slot center, then the second center."
      : tool === "polygon"
        ? polygonDraft ? "Click a polygon vertex to set its radius." : "Click the polygon center, then a vertex."
      : tool === "region_select"
        ? "Click clearly inside a bounded region. Boundary clicks are refused so region choice stays deterministic."
      : tool === "box_select"
        ? "Drag a box around complete sketch entities to select them together."
      : tool === "hole"
        ? "Select a profile, then click inside it to place a circular hole."
        : tool === "pan"
          ? "Drag the canvas to pan. Use Fit, Reset, and zoom controls to navigate the 2D sketch plane."
        : tool === "dimension"
          ? "Select a rectangle edge or click a dimension label to edit width or height."
          : tool === "line"
          ? draftPoint
            ? "Click the line end point."
            : "Click the line start point. The Line tool stays active for repeated placement; press Escape to return to Select."
          : tool === "arc"
            ? !arcDraft
              ? "Click the arc center."
              : arcDraft.points.length === 1
                ? "Click the arc start point."
                : "Click the arc end point; the shorter sweep is used."
          : tool === "three_point_arc"
            ? !arcDraft
              ? "Click the arc start point."
              : arcDraft.points.length === 1
                ? "Click a point on the arc."
                : "Click the arc end point."
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
            <span><b>Sketch</b> Parametric 2D workspace</span>
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
                <Text fontSize="sm" opacity={0.6}>Your sketch is active in this browser session.</Text>
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
                  rectangleDraft={rectangleDraft && tool === "center_rectangle"
                    ? {
                        anchor: {
                          x: 2 * rectangleDraft.anchor.x - rectangleDraft.current.x,
                          y: 2 * rectangleDraft.anchor.y - rectangleDraft.current.y,
                        },
                        current: rectangleDraft.current,
                      }
                    : rectangleDraft}
                  circleDraft={circleDraft}
                  arcDraft={arcDraft}
                  polylineDraft={polylineDraft}
                  slotDraft={slotDraft ? { ...slotDraft, width: Number(slotWidthValue) || 20 } : null}
                  polygonDraft={polygonDraft ? { ...polygonDraft, sides: Number(polygonSidesValue) || 6 } : null}
                  selectionBox={selectionBox}
                  dragPreviewPoint={dragPreviewPoint}
                  holePlacementPreview={holePlacementPreview}
                  holePlacementActive={Boolean(holePlacement)}
                  regionSelectionActive={tool === "region_select"}
                  showDebugLabels={showDebugLabels}
                  topologyRegions={tool === "region_select" || selectedRegionId ? topology?.regions || [] : []}
                  selectedRegionId={selectedRegionId}
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
                <Text fontWeight="600">{tool === "select" ? "Select" : tool === "rectangle" ? "Draw rectangle" : tool === "center_rectangle" ? "Center rectangle" : tool === "polyline" ? "Polyline" : tool === "slot" ? "Slot" : tool === "polygon" ? "Polygon" : tool === "region_select" ? "Region select" : tool === "box_select" ? "Box select" : tool === "hole" ? "Add hole" : tool === "pan" ? "Pan / view" : tool}</Text>
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
                {solverStatusDetail ? (
                  <Text data-testid="sketchmath-solver-status-detail" fontSize="xs" opacity={0.72}>
                    {solverStatusDetail}
                  </Text>
                ) : null}
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
                  <Button size="sm" onClick={() => handleToolChange("center_rectangle")} variant={tool === "center_rectangle" ? "solid" : "outline"}>
                    Start center rectangle
                  </Button>
                  <Button size="sm" onClick={() => handleToolChange("polyline")} variant={tool === "polyline" ? "solid" : "outline"}>
                    Start polyline
                  </Button>
                  <Button size="sm" onClick={() => handleToolChange("slot")} variant={tool === "slot" ? "solid" : "outline"}>
                    Start slot
                  </Button>
                  <Button size="sm" onClick={() => handleToolChange("polygon")} variant={tool === "polygon" ? "solid" : "outline"}>
                    Start polygon
                  </Button>
                  <Button size="sm" onClick={() => handleToolChange("box_select")} variant={tool === "box_select" ? "solid" : "outline"}>
                    Box select
                  </Button>
                  <Button size="sm" onClick={() => void commitPolyline()} isDisabled={!polylineDraft || polylineDraft.points.length < 2}>
                    Finish polyline
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => void handleClearSketch()}>
                    Clear sketch
                  </Button>
                </HStack>
                <HStack spacing={2} flexWrap="wrap" mt={2}>
                  <Input type="number" aria-label="Slot width" value={slotWidthValue} onChange={(event) => setSlotWidthValue(event.target.value)} width="104px" />
                  <Text fontSize="xs" opacity={0.75}>slot width mm</Text>
                  <Input type="number" aria-label="Polygon sides" value={polygonSidesValue} onChange={(event) => setPolygonSidesValue(event.target.value)} width="90px" min={3} max={128} />
                  <Text fontSize="xs" opacity={0.75}>polygon sides</Text>
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
                    <HStack spacing={2} mt={2} flexWrap="wrap">
                      <Button size="sm" variant="outline" onClick={() => void runQuickAxisDistance("horizontal")}>Set horizontal distance</Button>
                      <Button size="sm" variant="outline" onClick={() => void runQuickAxisDistance("vertical")}>Set vertical distance</Button>
                    </HStack>
                  </Box>
                ) : null}
                {selectedCircle ? (
                  <Box className="sketchmath-inline-editor" mt={3} data-testid="sketchmath-circle-editor">
                    <Text fontWeight="600" fontSize="sm" mb={2}>Driving circle dimension</Text>
                    <HStack spacing={2} flexWrap="wrap">
                      <Input type="number" aria-label="Circle radius" value={circleRadiusValue} onChange={(event) => setCircleRadiusValue(event.target.value)} width="100px" />
                      <Text fontSize="sm">mm</Text>
                      <Button size="sm" onClick={() => void runUpdateCircle()}>Apply radius</Button>
                      <Input type="number" aria-label="Circle diameter" value={circleDiameterValue} onChange={(event) => setCircleDiameterValue(event.target.value)} width="100px" />
                      <Text fontSize="sm">mm</Text>
                      <Button size="sm" onClick={() => void runUpdateCircleDiameter()}>Apply diameter</Button>
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

              {topology ? (
                <Box className="sketchmath-workflow-step" data-testid="sketchmath-topology-panel">
                  <Text className="sketchmath-step-label">Planar regions</Text>
                  <Text fontSize="sm" opacity={0.85}>
                    {topology.regions.length === 0
                      ? "No bounded regions detected."
                      : `${topology.regions.length} deterministic region${topology.regions.length === 1 ? "" : "s"} detected.`}
                  </Text>
                  <HStack spacing={2} flexWrap="wrap" mt={2}>
                    <Button size="sm" variant={tool === "region_select" ? "solid" : "outline"} onClick={() => handleToolChange("region_select")}>
                      Select on canvas
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => sessionId && void refreshTopology(sessionId)}>
                      Rescan
                    </Button>
                  </HStack>
                  {topology.regions.map((region, index) => (
                    <Box key={region.region_id} mt={2} data-testid={`sketchmath-region-card-${region.region_id}`}>
                      <Text fontSize="sm">
                        Region {index + 1} • {region.area.toFixed(2)} mm² • {region.holes.length} hole{region.holes.length === 1 ? "" : "s"}
                      </Text>
                      <HStack spacing={2} flexWrap="wrap" mt={1}>
                        <Button
                          size="sm"
                          variant={selectedRegionId === region.region_id ? "solid" : "outline"}
                          onClick={() => setSelectedRegionId(region.region_id)}
                        >
                          {selectedRegionId === region.region_id ? "Region selected" : "Choose region"}
                        </Button>
                        <Button size="sm" onClick={() => void promoteRegion(region.region_id)}>
                          Create region profile {index + 1}
                        </Button>
                      </HStack>
                    </Box>
                  ))}
                  {topology.diagnostics.length > 0 ? (
                    <Box mt={2} data-testid="sketchmath-topology-diagnostics">
                      {topology.diagnostics.slice(0, 5).map((diagnostic, index) => (
                        <Text key={`${diagnostic.code}-${index}`} fontSize="xs" opacity={0.8}>
                          {diagnostic.severity.toUpperCase()} • {diagnostic.code}: {diagnostic.message}
                        </Text>
                      ))}
                    </Box>
                  ) : null}
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

              {featureHistoryEnabled && sketchDocument ? (
                <FeatureHistoryPanel
                  document={sketchDocument}
                  activeProfile={activeProfileForCad || null}
                  newDepthValue={extrudeDepthValue}
                  busy={featureBusy}
                  canUndo={canFeatureUndo}
                  canRedo={canFeatureRedo}
                  holeFeaturesEnabled={holeFeaturesEnabled}
                  revolveFeaturesEnabled={revolveFeaturesEnabled}
                  filletFeaturesEnabled={filletFeaturesEnabled}
                  chamferFeaturesEnabled={chamferFeaturesEnabled}
                  artifactJobsEnabled={artifactJobsEnabled}
                  revolveAxes={revolveAxes}
                  artifactJobs={artifactJobs}
                  onNewDepthValueChange={setExtrudeDepthValue}
                  onAddExtrusion={(profile, depth) => void handleAddFeatureExtrusion(profile, depth)}
                  onAddFullRevolve={(profile, axis) => void handleAddFullRevolve(profile, axis)}
                  onAddOuterFillet={(feature, edgeReferences, radius) => (
                    void handleAddOuterFillet(feature, edgeReferences, radius)
                  )}
                  onAddOuterChamfer={(feature, edgeReferences, distance) => (
                    void handleAddOuterChamfer(feature, edgeReferences, distance)
                  )}
                  onUpdateDepth={(feature, depth) => void handleUpdateFeatureDepth(feature, depth)}
                  onUpdateFilletRadius={(feature, radius) => void handleUpdateFilletRadius(feature, radius)}
                  onUpdateChamferDistance={(feature, distance) => void handleUpdateChamferDistance(feature, distance)}
                  onUpdateHole={(feature, parameters) => (
                    void handleUpdateHole(feature, parameters)
                  )}
                  onUpdateFullRevolve={(feature, axisId, angle) => (
                    void handleUpdateFullRevolve(feature, axisId, angle)
                  )}
                  onSetDesignParameter={(parameterId, value) => void handleSetDesignParameter(parameterId, value)}
                  onRenameFeature={(feature, name) => void handleRenameFeature(feature, name)}
                  onAddSimpleHole={(feature, topReference, position, diameter, termination, depth) => (
                    void handleAddSimpleHole(feature, topReference, position, diameter, termination, depth)
                  )}
                  onBuildArtifact={(feature, format) => void handleBuildFeatureArtifact(feature, format)}
                  onRetryArtifact={(job) => void handleRetryFeatureArtifact(job)}
                  artifactDownloadUrl={(path, format) => (
                    format === "step" ? sketchMathStepDownloadUrl(path) : sketchMathStlDownloadUrl(path)
                  )}
                  onUndo={() => void handleFeatureUndo()}
                  onRedo={() => void handleFeatureRedo()}
                />
              ) : null}

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
                      Committed constraints for the current selection. Point constraints use selection order: midpoint first; symmetry reference, target, then axis endpoints.
                    </Text>
                    <Text fontSize="sm" opacity={0.8} whiteSpace="pre-wrap" mb={2}>
                      {constraintDebugSummaries.length ? constraintDebugSummaries.join("\n") : "No constraints yet."}
                    </Text>
                    <HStack spacing={2} flexWrap="wrap" mt={2}>
                      <Button size="sm" onClick={() => void runQuickFixed()} isDisabled={orderedPointSelectionIds.length !== 1}>
                        Fixed
                      </Button>
                      <Button size="sm" onClick={() => void runQuickMidpoint()} isDisabled={orderedPointSelectionIds.length !== 3}>
                        Midpoint
                      </Button>
                      <Button size="sm" onClick={() => void runQuickCollinear()} isDisabled={orderedPointSelectionIds.length !== 3}>
                        Collinear
                      </Button>
                      <Button size="sm" onClick={() => void runQuickSymmetric()} isDisabled={orderedPointSelectionIds.length !== 4}>
                        Symmetric
                      </Button>
                      <Button size="sm" onClick={() => void runQuickConcentric()} isDisabled={selectedCenterEntities.length !== 2}>
                        Concentric
                      </Button>
                      <Button size="sm" onClick={() => void runQuickTangent()} isDisabled={tangentSelectionIds.length !== 2}>
                        Tangent
                      </Button>
                      <Button size="sm" onClick={() => void runSetConstruction()} isDisabled={!canSetConstruction}>
                        {selectionIsConstruction ? "Make regular" : "Make construction"}
                      </Button>
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

              <Box className="sketchmath-workflow-step" data-testid="sketchmath-editing-tools">
                <Text className="sketchmath-step-label">Safe editing</Text>
                <Text fontSize="sm" opacity={0.75}>Split uses one line; trim/extend use target then cutter selection order. Referenced profile curves fail without partial mutation.</Text>
                <HStack spacing={2} flexWrap="wrap" mt={2}>
                  <Button size="sm" onClick={() => void runSplitLine()} isDisabled={selectedLineEntities.length !== 1}>Split midpoint</Button>
                  <Button size="sm" onClick={() => void runTrimLine()} isDisabled={selectedLineEntities.length !== 2}>Trim target</Button>
                  <Button size="sm" onClick={() => void runExtendLine()} isDisabled={selectedLineEntities.length !== 2}>Extend target</Button>
                  <Input type="number" aria-label="Offset distance" value={offsetValue} onChange={(event) => setOffsetValue(event.target.value)} width="92px" />
                  <Button
                    size="sm"
                    onClick={() => void runOffsetCurve()}
                    isDisabled={
                      selectedEntities.length !== 1
                      || !["line_2d", "construction_line_2d", "circle_2d", "arc_2d"].includes(selectedEntities[0].type)
                    }
                  >
                    Offset
                  </Button>
                  <Button size="sm" onClick={() => void runDuplicate()} isDisabled={selectedEntityIds.length === 0}>Duplicate</Button>
                  <Input type="number" aria-label="Pattern count" value={patternCountValue} onChange={(event) => setPatternCountValue(event.target.value)} width="78px" min={1} max={32} />
                  <Button size="sm" onClick={() => void runLinearPattern()} isDisabled={selectedEntityIds.length === 0}>Linear pattern</Button>
                  <Button size="sm" onClick={() => void runMirrorSelection()} isDisabled={selectedEntityIds.length === 0}>Mirror about X=0</Button>
                </HStack>
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
              <Box className="sketchmath-panel" data-testid="sketchmath-solver-analysis-debug">
                <Text fontWeight="600">Solver analysis</Text>
                <Text fontSize="sm" opacity={0.78} mt={2} whiteSpace="pre-wrap">
                  {solverAnalysisDebugLines.join("\n")}
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
