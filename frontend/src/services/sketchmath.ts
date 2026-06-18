const API_URL = process.env.REACT_APP_API_URL || "/api";
const DEVICE_KEY = "friday_device_id";
const DEVICE_HEADER = "X-Friday-Device";

export type SketchMathMode =
  | "select"
  | "point"
  | "line"
  | "rectangle"
  | "circle"
  | "arc"
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
};

export type SketchMathLineEntity = {
  id: string;
  type: "line_2d" | "construction_line_2d";
  start: [number, number];
  end: [number, number];
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
};

export type SketchMathEntity =
  | SketchMathPointEntity
  | SketchMathLineEntity
  | SketchMathProfileEntity;

export type SketchMathSelectionContext = {
  selection_set_id: string;
  units: string;
  frame: "canvas_2d";
  items: SketchMathEntity[];
  constraints: Array<Record<string, unknown>>;
  named_references: Record<string, string>;
};

export type SketchMathCommand = {
  version: "0.1";
  command_id: string;
  mode?: "preview" | "commit";
  command_type: string;
  selection: string[];
  parameters: Record<string, unknown>;
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

const fetchJson = async <T,>(path: string, body?: Record<string, unknown>): Promise<T> => {
  const response = await fetch(`${API_URL}${path}`, {
    method: body ? "POST" : "GET",
    headers: requestHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`HTTP ${response.status}: ${detail}`);
  }
  return (await response.json()) as T;
};

export const isSketchMathEnabled = (): boolean => {
  const raw = process.env.REACT_APP_SKETCHMATH_ENABLED;
  if (raw == null || String(raw).trim() === "") {
    return true;
  }

  const normalized = String(raw).trim().toLowerCase();
  if (["0", "false", "disabled"].includes(normalized)) {
    return false;
  }

  return true;
};

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
): Promise<{ session_id: string; selection_context: SketchMathSelectionContext; result: SketchMathOperationResult; history_length: number }> =>
  fetchJson(`/sketchmath/sessions/${sessionId}/commands/preview`, { command });

export const commitSketchMathCommand = async (
  sessionId: string,
  command: SketchMathCommand,
): Promise<{ session_id: string; selection_context: SketchMathSelectionContext; result: SketchMathOperationResult; history_length: number }> =>
  fetchJson(`/sketchmath/sessions/${sessionId}/commands/commit`, { command });

export const revertSketchMathSession = async (sessionId: string): Promise<SketchMathSessionSnapshot> =>
  fetchJson<SketchMathSessionSnapshot>(`/sketchmath/sessions/${sessionId}/revert`, {});

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
