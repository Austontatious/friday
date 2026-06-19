import type { ChatMode } from "../services/api";
import type { ModelResponse } from "../types";

export type TelemetryEventKind =
  | "session_started"
  | "workspace_initialized"
  | "prompt_queued"
  | "request_sent"
  | "route_selected"
  | "response_streaming"
  | "response_completed"
  | "request_failed"
  | "fallback_attempted"
  | "tool_call_started"
  | "tool_call_completed"
  | "tool_call_failed"
  | "artifact_created";

export type TelemetryEventLevel = "info" | "success" | "warning" | "danger";

export type TelemetryEvent = {
  id: string;
  kind: TelemetryEventKind;
  level: TelemetryEventLevel;
  title: string;
  detail: string;
  timestamp: string;
  raw?: unknown;
};

export type TelemetryRouteEntry = {
  label: string;
  detail: string;
  timestamp: string;
};

export type TelemetryArtifact = {
  label: string;
  detail: string;
  raw?: unknown;
};

export const nowLabel = () =>
  new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date());

export const makeTelemetryEvent = (
  kind: TelemetryEventKind,
  options: {
    level?: TelemetryEventLevel;
    title?: string;
    detail: string;
    raw?: unknown;
  },
): TelemetryEvent => ({
  id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  kind,
  level: options.level || levelForKind(kind),
  title: options.title || titleForKind(kind),
  detail: options.detail,
  timestamp: nowLabel(),
  raw: options.raw,
});

export const extractRouteLabel = (response: ModelResponse, mode: ChatMode): string => {
  const meta = response.meta || {};
  const route = meta.route || meta.router || meta.routing_path || meta.profile || meta.alias;
  const model = meta.model || meta.model_name || meta.route_model || meta.provider_model;
  return [route, model].filter(Boolean).join(" / ") || (mode === "direct_friday" ? "Direct Friday / default" : "Legacy route");
};

export const extractContextUsage = (response: ModelResponse): string => {
  const meta = response.meta || {};
  const usage = meta.context_usage || meta.token_usage || meta.usage || meta.tokens;
  if (!usage) return "Context unavailable";
  if (typeof usage === "string") return usage;
  if (typeof usage === "number") return `${usage} tokens`;
  const used = usage.used || usage.prompt_tokens || usage.input_tokens || usage.total_tokens;
  const limit = usage.limit || usage.max || usage.context_limit;
  return used && limit ? `${used}/${limit}` : used ? `${used} tokens` : "Context reported";
};

export const extractArtifacts = (response: ModelResponse): TelemetryArtifact[] => {
  const metaArtifacts = response.meta?.artifacts;
  if (!Array.isArray(metaArtifacts)) return [];
  return metaArtifacts.slice(0, 6).map((artifact, index) => {
    if (typeof artifact === "string") {
      return { label: `Artifact ${index + 1}`, detail: artifact, raw: artifact };
    }
    return {
      label: String(artifact.name || artifact.label || artifact.type || `Artifact ${index + 1}`),
      detail: String(artifact.path || artifact.url || artifact.detail || artifact.id || "Attached to response"),
      raw: artifact,
    };
  });
};

export const buildResponseTelemetryEvents = (
  response: ModelResponse,
  mode: ChatMode,
  routeLabel: string,
  artifacts: TelemetryArtifact[],
): TelemetryEvent[] => {
  const meta = response.meta || {};
  const events: TelemetryEvent[] = [
    makeTelemetryEvent("route_selected", {
      detail: routeLabel,
      raw: { mode, route: routeLabel, meta },
    }),
  ];

  const fallbacks = normalizeFallbacks(meta);
  fallbacks.forEach((fallback) => {
    events.push(makeTelemetryEvent("fallback_attempted", {
      level: "warning",
      detail: fallback,
      raw: meta.fallback_history || meta.fallbacks || meta.fallback,
    }));
  });

  if (meta.streaming || meta.streamed || meta.response_streaming || meta.stream) {
    events.push(makeTelemetryEvent("response_streaming", {
      detail: "Backend reported a streaming response path.",
      raw: {
        streaming: meta.streaming,
        streamed: meta.streamed,
        response_streaming: meta.response_streaming,
        stream: meta.stream,
      },
    }));
  }

  if (Array.isArray(response.tools)) {
    response.tools.slice(0, 8).forEach((tool, index) => {
      const name = String(tool?.name || tool?.tool || tool?.id || `Tool ${index + 1}`);
      const status = String(tool?.status || tool?.state || "completed").toLowerCase();
      if (status === "started" || status === "running" || status === "queued") {
        events.push(makeTelemetryEvent("tool_call_started", {
          detail: name,
          raw: tool,
        }));
      } else if (status === "failed" || status === "error") {
        events.push(makeTelemetryEvent("tool_call_failed", {
          level: "danger",
          detail: `${name}${tool?.error ? `: ${String(tool.error)}` : ""}`,
          raw: tool,
        }));
      } else {
        events.push(makeTelemetryEvent("tool_call_completed", {
          level: "success",
          detail: name,
          raw: tool,
        }));
      }
    });
  }

  artifacts.forEach((artifact) => {
    events.push(makeTelemetryEvent("artifact_created", {
      level: "success",
      detail: `${artifact.label}: ${artifact.detail}`,
      raw: artifact.raw || artifact,
    }));
  });

  events.push(makeTelemetryEvent("response_completed", {
    level: "success",
    detail: `${routeLabel}; ${countWords(response.assistant_text || response.text || "")} words received.`,
    raw: {
      memory: response.memory,
      meta,
      text_length: (response.assistant_text || response.text || "").length,
    },
  }));

  return events;
};

export const formatTelemetryRaw = (value: unknown): string => {
  if (value === undefined) return "No raw details reported.";
  if (value instanceof Error) return value.stack || value.message;
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const levelForKind = (kind: TelemetryEventKind): TelemetryEventLevel => {
  if (kind === "request_failed" || kind === "tool_call_failed") return "danger";
  if (kind === "fallback_attempted") return "warning";
  if (kind === "response_completed" || kind === "tool_call_completed" || kind === "artifact_created" || kind === "workspace_initialized" || kind === "session_started") return "success";
  return "info";
};

const titleForKind = (kind: TelemetryEventKind): string => {
  const titles: Record<TelemetryEventKind, string> = {
    artifact_created: "Artifact created",
    fallback_attempted: "Fallback attempted",
    prompt_queued: "Prompt queued",
    request_failed: "Request failed",
    request_sent: "Request sent",
    response_completed: "Response completed",
    response_streaming: "Response streaming",
    route_selected: "Route selected",
    session_started: "Shell ready",
    tool_call_completed: "Tool call completed",
    tool_call_failed: "Tool call failed",
    tool_call_started: "Tool call started",
    workspace_initialized: "Workspace initialized",
  };
  return titles[kind];
};

const normalizeFallbacks = (meta: Record<string, any>): string[] => {
  const fallbackSource = meta.fallback_history || meta.fallbacks || meta.fallback_attempted || meta.fallback;
  if (!fallbackSource || fallbackSource === "none") return [];
  if (Array.isArray(fallbackSource)) {
    return fallbackSource.map((fallback) => {
      if (typeof fallback === "string") return fallback;
      return String(fallback.route || fallback.model || fallback.reason || JSON.stringify(fallback));
    });
  }
  if (fallbackSource === true) return ["Fallback path was attempted."];
  return [String(fallbackSource)];
};

const countWords = (text: string): number => text.trim().split(/\s+/).filter(Boolean).length;
