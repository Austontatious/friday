import type { ModelResponse } from "../types";
const API_URL = typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL
  ? import.meta.env.VITE_API_URL
  : "http://localhost:8000";

export interface PromptPayload {
  prompt: string;
  task_type?: string;
}

export const sendPrompt = async (payload: { prompt: string; task_type?: string }): Promise<ModelResponse> => {
  const response = await fetch(`${API_URL}/process`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const contentType = response.headers.get("Content-Type") || "";

  if (!response.ok) {
    const fallbackText = await response.text();
    throw new Error(`HTTP ${response.status}: ${fallbackText}`);
  }

  if (contentType.includes("application/json")) {
    return await response.json(); // <-- this will be typed as ModelResponse
  } else {
    const text = await response.text();
    return { cleaned: text } as ModelResponse;
  }
};

