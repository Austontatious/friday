import type { ModelResponse } from "../types";

const API_URL = process.env.REACT_APP_API_URL || "http://localhost:9001/api";

export interface PromptPayload {
  prompt: string;
  user_id?: string;
}

export const sendPrompt = async (payload: PromptPayload): Promise<ModelResponse> => {
  const response = await fetch(`${API_URL}/chat`, {
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
    return await response.json();
  }

  const text = await response.text();
  return { text } as ModelResponse;
};
