const API_URL = process.env.REACT_APP_API_URL || "/api";
const DEVICE_KEY = "friday_device_id";
const DEVICE_HEADER = "X-Friday-Device";

export type SketchMathMode =
  | "select"
  | "point"
  | "line"
  | "rectangle"
  | "center_rectangle"
  | "polyline"
  | "hole"
  | "pan"
  | "circle"
  | "arc"
  | "three_point_arc"
  | "dimension"
  | "horizontal"
  | "vertical"
  | "parallel"
  | "perpendicular"
  | "equal"
  | "delete"
  | "solve"
  | "convert";

export type SketchMathPointEntity = {
  id: string;
  type: "point_2d";
  coords: [number, number];
  locked?: boolean;
  label?: string | null;
  construction?: boolean;
};

export type SketchMathLineEntity = {
  id: string;
  type: "line_2d" | "construction_line_2d";
  start: [number, number];
  end: [number, number];
  locked?: boolean;
  label?: string | null;
  start_point_id?: string | null;
  end_point_id?: string | null;
};

export type SketchMathCircleEntity = {
  id: string;
  type: "circle_2d";
  center: [number, number];
  radius: number;
  center_point_id?: string | null;
  locked?: boolean;
  label?: string | null;
};

export type SketchMathArcEntity = {
  id: string;
  type: "arc_2d";
  center: [number, number];
  radius: number;
  start_angle_deg: number;
  sweep_angle_deg: number;
  construction: "center" | "three_point";
  center_point_id?: string | null;
  start_point_id?: string | null;
  through_point_id?: string | null;
  end_point_id?: string | null;
  locked?: boolean;
  label?: string | null;
};

export type SketchMathProfileEntity = {
  id: string;
  type: "profile_2d";
  vertices: [number, number][];
  area: number;
  winding: "clockwise" | "counterclockwise" | "degenerate";
  holes?: string[];
  warnings?: string[];
  closed?: boolean;
  locked?: boolean;
  label?: string | null;
  source_line_ids?: string[];
  source_circle_id?: string | null;
};

export type SketchMathEntity =
  | SketchMathPointEntity
  | SketchMathLineEntity
  | SketchMathCircleEntity
  | SketchMathArcEntity
  | SketchMathProfileEntity;

export type SketchMathSelectionContext = {
  selection_set_id: string;
  units: string;
  frame: "canvas_2d";
  items: SketchMathEntity[];
  constraints: Array<Record<string, unknown>>;
  named_references: Record<string, string>;
};

export type SketchMathSolverAnalysis = {
  schema_version: "1.0";
  coverage: "exact" | "partial" | "unknown";
  freedom_state: "under_constrained" | "fully_constrained" | "unknown";
  consistency_state: "consistent" | "inconsistent" | "unknown";
  redundancy_state: "none" | "redundant" | "unknown";
  tracked_variable_count: number;
  independent_equation_count: number;
  remaining_dof: number | null;
  remaining_tracked_dof_upper_bound: number;
  fixed_entity_ids: string[];
  supported_constraint_ids: string[];
  unsupported_constraint_ids: string[];
  invalid_constraint_ids: string[];
  redundant_constraint_ids: string[];
  conflicting_constraint_ids: string[];
  unmodeled_entity_ids: string[];
  diagnostics: string[];
  tolerance_policy: Record<string, number | string>;
};

export type SketchMathSolverRun = {
  schema_version: "1.0";
  backend: string;
  mode: "analyze" | "solve";
  outcome: "analyzed" | "solved" | "under_constrained" | "inconsistent" | "redundant" | "failed";
  termination_reason: string;
  requested_constraint_ids: string[];
  changed_entity_ids: string[];
  proposed_patch: Array<{
    entity_id: string;
    entity_type: string;
    before: Record<string, unknown>;
    after: Record<string, unknown>;
  }>;
  feasible: boolean | null;
  residual_norm: number | null;
  analysis_before: SketchMathSolverAnalysis;
  analysis_after: SketchMathSolverAnalysis;
  diagnostics: string[];
};

export const SKETCHMATH_COMMAND_TYPES = [
  "measure_distance",
  "measure_angle",
  "define_point",
  "define_line",
  "define_profile",
  "delete_entity",
  "set_distance",
  "set_horizontal_distance",
  "set_vertical_distance",
  "set_radius",
  "set_diameter",
  "set_rectangle_dimension",
  "set_line_polar",
  "set_angle",
  "make_parallel",
  "make_perpendicular",
  "make_equal_length",
  "make_equal_angle",
  "make_horizontal",
  "make_vertical",
  "make_coincident",
  "make_fixed",
  "make_midpoint",
  "make_collinear",
  "make_symmetric",
  "make_concentric",
  "make_tangent",
  "set_construction",
  "solve_constraints",
  "analyze_constraints",
  "move_point",
  "detect_profiles",
  "make_profile",
  "define_circle",
  "update_circle",
  "define_arc",
  "update_arc",
  "make_circle_profile",
  "add_profile_hole",
  "update_profile_hole",
  "extrude_profile",
  "translate",
  "rotate",
  "mirror",
  "copy_linear",
  "intersect_lines",
  "project_point_to_line",
  "batch",
] as const;

export type SketchMathCommandType = typeof SKETCHMATH_COMMAND_TYPES[number];

export type SketchMathCommand = {
  version: "0.1" | "0.2" | "0.3" | "0.4" | "0.5" | "0.6" | "0.7";
  command_id: string;
  mode?: "preview" | "commit";
  command_type: SketchMathCommandType;
  selection: string[];
  parameters: Record<string, unknown>;
};

export type SketchMathPreviewTriangle = {
  indices: [number, number, number];
  surface: "top" | "bottom" | "outer_wall" | "hole_wall" | string;
  ring_id?: string;
};

export type SketchMathPreviewMesh = {
  version: "0.1";
  units: string;
  profile_id: string;
  depth: number;
  vertices: [number, number, number][];
  triangles: SketchMathPreviewTriangle[];
  loops?: Record<string, unknown>;
  metadata?: {
    profile_id?: string;
    extrusion_depth?: number;
    extrusion_depth_unit?: string;
    hole_count?: number;
    triangle_count?: number;
    vertex_count?: number;
    bbox?: {
      xmin: number;
      xmax: number;
      ymin: number;
      ymax: number;
      zmin: number;
      zmax: number;
    };
  };
};

export type SketchMathOperationResult = {
  command: SketchMathCommand;
  status: "preview" | "committed";
  before: SketchMathSelectionContext;
  after: SketchMathSelectionContext;
  changed_entity_ids: string[];
  replay_index: number;
  value?: number | null;
  unit?: string | null;
  metadata: Record<string, unknown>;
};

export type SketchMathHistoryEntry = {
  command: SketchMathCommand;
  committed: boolean;
  before: SketchMathSelectionContext;
  after: SketchMathSelectionContext;
};

export type SketchMathSessionSnapshot = {
  session_id: string;
  selection_context: SketchMathSelectionContext;
  session_metadata: Record<string, unknown>;
  history_length: number;
  history: SketchMathHistoryEntry[];
  history_cursor?: number;
  can_undo?: boolean;
  can_redo?: boolean;
};

export type SketchMathProfileCandidate = {
  candidate_id: string;
  line_ids: string[];
  point_ids: string[];
  vertices: [number, number][];
  valid: boolean;
  area: number;
  winding: string;
  warnings: string[];
};

export type SketchMathCommandResponse = {
  session_id: string;
  selection_context: SketchMathSelectionContext;
  result: SketchMathOperationResult;
  history_length: number;
  session_metadata?: Record<string, unknown>;
};

export type SketchMathTranslationOutcome =
  | {
      session_id: string;
      utterance: string;
      selection_context: SketchMathSelectionContext;
      status: "command";
      command: SketchMathCommand;
      reason: string | null;
      options: string[];
      metadata: Record<string, unknown>;
    }
  | {
      session_id: string;
      utterance: string;
      selection_context: SketchMathSelectionContext;
      status: "clarification_required" | "unsupported";
      command?: undefined;
      reason: string | null;
      options: string[];
      metadata: Record<string, unknown>;
    };

const createDeviceId = (): string => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `friday-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
};

const resolveDeviceId = (): string => {
  if (typeof window === "undefined") {
    return "friday-local";
  }
  const existing = window.localStorage.getItem(DEVICE_KEY);
  if (existing) {
    return existing;
  }
  const generated = createDeviceId();
  window.localStorage.setItem(DEVICE_KEY, generated);
  return generated;
};

const requestHeaders = (): HeadersInit => ({
  "Content-Type": "application/json",
  [DEVICE_HEADER]: resolveDeviceId(),
});

type ApiErrorPayload = {
  code?: string;
  message?: string;
  detail?: unknown;
  retryable?: boolean;
};

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;

const userMessageForApiError = (status: number, payload: ApiErrorPayload | null, fallback: string): string => {
  const code = String(payload?.code || "");
  const message = String(payload?.message || fallback || "SketchMath request failed");
  const detail = asRecord(payload?.detail);
  const detailCode = String(detail?.error_code || "");
  if (code === "selection_resolution_error" && detailCode === "dependency_missing") {
    return "Geometry validation dependency is unavailable. Rebuild the backend or check SketchMath dependencies.";
  }
  if (code === "selection_resolution_error" && detailCode === "hole_outside_outer") {
    return "Hole must stay inside the selected profile.";
  }
  if (code === "selection_resolution_error" && detailCode === "invalid_hole_diameter") {
    return "Hole diameter must be a positive number.";
  }
  if (code === "selection_resolution_error" && detailCode === "profile_intersection") {
    return "Hole must fit fully inside the profile without touching an edge or another hole.";
  }
  if (code === "cad_adapter_unavailable") {
    return "STEP export is unavailable because the CAD adapter is not installed or configured.";
  }
  if (code === "cad_export_error") {
    return "STEP export failed. Check Advanced / Debug for the backend details.";
  }
  if (status >= 500) {
    return "SketchMath backend failed. Check Advanced / Debug for details.";
  }
  return message;
};

export class SketchMathApiError extends Error {
  status: number;
  code: string | null;
  detail: unknown;
  retryable: boolean;
  debugText: string;

  constructor(status: number, payload: ApiErrorPayload | null, rawText: string) {
    const fallback = rawText || `HTTP ${status}`;
    super(userMessageForApiError(status, payload, fallback));
    this.name = "SketchMathApiError";
    this.status = status;
    this.code = typeof payload?.code === "string" ? payload.code : null;
    this.detail = payload?.detail ?? null;
    this.retryable = Boolean(payload?.retryable);
    this.debugText = rawText;
  }
}

const parseErrorPayload = (rawText: string): ApiErrorPayload | null => {
  try {
    const parsed = JSON.parse(rawText);
    const root = asRecord(parsed);
    const detail = asRecord(root?.detail);
    const nested = asRecord(detail?.error);
    const direct = asRecord(root?.error);
    const source = nested || direct || detail || root;
    if (!source) {
      return null;
    }
    return {
      code: typeof source.code === "string" ? source.code : undefined,
      message: typeof source.message === "string" ? source.message : undefined,
      detail: source.detail,
      retryable: typeof source.retryable === "boolean" ? source.retryable : undefined,
    };
  } catch {
    return null;
  }
};

const fetchJson = async <T,>(path: string, body?: Record<string, unknown>): Promise<T> => {
  const response = await fetch(`${API_URL}${path}`, {
    method: body ? "POST" : "GET",
    headers: requestHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const rawText = await response.text();
    throw new SketchMathApiError(response.status, parseErrorPayload(rawText), rawText);
  }
  return (await response.json()) as T;
};

export const isSketchMathEnabled = (): boolean => {
  const raw = process.env.REACT_APP_SKETCHMATH_ENABLED;
  if (raw == null || String(raw).trim() === "") {
    return false;
  }

  const normalized = String(raw).trim().toLowerCase();
  return ["1", "true", "yes", "on"].includes(normalized);
};

export const sketchMathStepDownloadUrl = (stepPath: string): string =>
  `${API_URL}/sketchmath/artifacts/step?path=${encodeURIComponent(stepPath)}`;

export const createSketchMathSession = async (
  selectionContext?: Partial<SketchMathSelectionContext>,
): Promise<SketchMathSessionSnapshot> =>
  fetchJson<SketchMathSessionSnapshot>("/sketchmath/sessions", {
    selection_context: {
      selection_set_id: selectionContext?.selection_set_id || `client_${Date.now().toString(36)}`,
      units: selectionContext?.units || "mm",
      frame: "canvas_2d",
      items: selectionContext?.items || [],
      constraints: selectionContext?.constraints || [],
      named_references: selectionContext?.named_references || {},
    },
  });

export const getSketchMathSession = async (sessionId: string): Promise<SketchMathSessionSnapshot> =>
  fetchJson<SketchMathSessionSnapshot>(`/sketchmath/sessions/${sessionId}`);

export const previewSketchMathCommand = async (
  sessionId: string,
  command: SketchMathCommand,
): Promise<SketchMathCommandResponse> =>
  fetchJson(`/sketchmath/sessions/${sessionId}/commands/preview`, { command });

export const commitSketchMathCommand = async (
  sessionId: string,
  command: SketchMathCommand,
): Promise<SketchMathCommandResponse> =>
  fetchJson(`/sketchmath/sessions/${sessionId}/commands/commit`, { command });

export const revertSketchMathSession = async (sessionId: string): Promise<SketchMathSessionSnapshot> =>
  fetchJson<SketchMathSessionSnapshot>(`/sketchmath/sessions/${sessionId}/revert`, {});

export const redoSketchMathSession = async (sessionId: string): Promise<SketchMathSessionSnapshot> =>
  fetchJson<SketchMathSessionSnapshot>(`/sketchmath/sessions/${sessionId}/redo`, {});

export const upsertSketchMathEntity = async (
  sessionId: string,
  entity: SketchMathEntity,
  mode: "preview" | "commit" = "commit",
): Promise<{ session_id: string; selection_context: SketchMathSelectionContext; result: SketchMathOperationResult; history_length: number }> =>
  fetchJson(`/sketchmath/sessions/${sessionId}/entities`, { entity, mode });

export const translateSketchMathUtterance = async (
  sessionId: string,
  utterance: string,
  selectionContext: SketchMathSelectionContext,
): Promise<SketchMathTranslationOutcome> =>
  fetchJson(`/sketchmath/sessions/${sessionId}/translate`, { utterance, selection_context: selectionContext });
