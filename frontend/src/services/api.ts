import type { ModelResponse } from "../types";

const API_URL = process.env.REACT_APP_API_URL || "/api";
const DEVICE_KEY = "friday_device_id";
const DEVICE_HEADER = "X-Friday-Device";

export interface PromptPayload {
  prompt: string;
  user_id?: string;
}

export interface MemoryConfirmPayload {
  pending_ids: string[];
  decision: "accept" | "reject";
  note?: string;
}

export interface MemoryConfirmResponse {
  memory?: {
    provider?: string;
    processed?: number;
    accepted_ids?: string[];
    rejected?: number;
    reasons?: string[];
  };
}

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

export const sendPrompt = async (payload: PromptPayload): Promise<ModelResponse> => {
  const response = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: requestHeaders(),
    body: JSON.stringify(payload),
  });

  const contentType = response.headers.get("Content-Type") || "";

  if (!response.ok) {
    const fallbackText = await response.text();
    throw new Error(`HTTP ${response.status}: ${fallbackText}`);
  }

  if (contentType.includes("application/json")) {
    return await response.json();
  }

  const text = await response.text();
  return { text } as ModelResponse;
};

export const confirmMemory = async (payload: MemoryConfirmPayload): Promise<MemoryConfirmResponse> => {
  const response = await fetch(`${API_URL}/memory/confirm`, {
    method: "POST",
    headers: requestHeaders(),
    body: JSON.stringify(payload),
  });

  const contentType = response.headers.get("Content-Type") || "";
  if (!response.ok) {
    const fallbackText = await response.text();
    throw new Error(`HTTP ${response.status}: ${fallbackText}`);
  }
  if (!contentType.includes("application/json")) {
    return {};
  }
  return await response.json();
};
