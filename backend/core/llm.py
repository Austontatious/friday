from __future__ import annotations

import os
import asyncio
from typing import Any, Dict, List, Optional, Tuple

import httpx


class LLMDisabledError(Exception):
    pass


class LLMConfigError(Exception):
    pass


class LLMRequestError(Exception):
    pass


def _env_bool(key: str, default: str = "0") -> bool:
    return os.getenv(key, default).lower() in {"1", "true", "yes", "on"}


def _default_system_prompt() -> str:
    return os.getenv("FRIDAY_SYSTEM_PROMPT", "You are FRIDAY, a helpful assistant.")


def _chat_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if "/v1/" in base:
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _health_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/models"
    if "/v1/" in base:
        prefix = base.split("/v1", 1)[0] + "/v1"
        return f"{prefix}/models"
    return f"{base}/health"


class LLMClient:
    def __init__(self) -> None:
        self.enabled = _env_bool("FRIDAY_LLM_ENABLED", "1")
        self.model_path = os.getenv("FRIDAY_MODEL_PATH", "").strip()
        self.model_name = os.getenv("FRIDAY_MODEL_NAME", "friday")
        self.base_url = os.getenv("LLM_BASE_URL", "").strip()
        self.api_key = os.getenv("LLM_API_KEY", "").strip()
        self._llama = None

    def ready(self) -> bool:
        status = self.status()
        return status["status"] == "healthy"

    def status(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "status": "disabled"}
        if self.model_path:
            if os.path.exists(self.model_path):
                return {"enabled": True, "status": "healthy", "detail": "local_model"}
            return {"enabled": True, "status": "not_configured", "detail": "model_path_missing"}
        if self.base_url:
            ok, detail = self._probe_remote()
            return {"enabled": True, "status": "healthy" if ok else "unhealthy", "detail": detail}
        return {"enabled": True, "status": "not_configured", "detail": "no_model_or_url"}

    async def generate(self, prompt: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        messages = [{"role": "system", "content": _default_system_prompt()}]
        for msg in history or []:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": prompt})
        return await self.generate_messages(messages)

    async def generate_messages(self, messages: List[Dict[str, str]]) -> str:
        if not self.enabled:
            raise LLMDisabledError("LLM is disabled")
        if self.model_path:
            return await asyncio.to_thread(self._generate_local_messages, messages)
        if self.base_url:
            return await self._generate_remote_messages(messages)
        raise LLMConfigError("No LLM configured")

    def _load_llama(self):
        if self._llama is not None:
            return
        if not self.model_path:
            raise LLMConfigError("FRIDAY_MODEL_PATH is not set")
        if not os.path.exists(self.model_path):
            raise LLMConfigError(f"Model file not found: {self.model_path}")

        from llama_cpp import Llama

        context_length = int(os.getenv("FRIDAY_CONTEXT_LENGTH", "4096"))
        n_gpu_layers = int(os.getenv("FRIDAY_N_GPU_LAYERS", "0"))
        self._llama = Llama(
            model_path=self.model_path,
            n_ctx=context_length,
            n_gpu_layers=n_gpu_layers,
            verbose=False,
        )

    def _build_prompt_from_messages(self, messages: List[Dict[str, str]]) -> str:
        lines = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                lines.append(f"System: {content}")
            elif role == "assistant":
                lines.append(f"Assistant: {content}")
            else:
                lines.append(f"User: {content}")
        lines.append("Assistant:")
        return "\n".join(lines)

    def _generate_local_messages(self, messages: List[Dict[str, str]]) -> str:
        self._load_llama()
        max_tokens = int(os.getenv("FRIDAY_MAX_TOKENS", "512"))
        temperature = float(os.getenv("FRIDAY_TEMPERATURE", "0.7"))
        top_p = float(os.getenv("FRIDAY_TOP_P", "0.9"))
        repeat_penalty = float(os.getenv("FRIDAY_REPEAT_PENALTY", "1.1"))
        stop = ["<|EOT|>", "<|im_end|>"]

        prompt_text = self._build_prompt_from_messages(messages)
        output = self._llama(
            prompt=prompt_text,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            repeat_penalty=repeat_penalty,
            stop=stop,
        )
        text = output["choices"][0]["text"]
        return text.strip()

    async def _generate_remote_messages(self, messages: List[Dict[str, str]]) -> str:
        url = _chat_url(self.base_url)

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": float(os.getenv("FRIDAY_TEMPERATURE", "0.7")),
            "max_tokens": int(os.getenv("FRIDAY_MAX_TOKENS", "512")),
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        timeout = float(os.getenv("FRIDAY_LLM_TIMEOUT", "30"))
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                raise LLMRequestError(f"LLM error {resp.status_code}: {resp.text}")
            data = resp.json()

        try:
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            raise LLMRequestError(f"Invalid LLM response: {exc}")

    def _probe_remote(self) -> Tuple[bool, str]:
        url = _health_url(self.base_url)
        timeout = float(os.getenv("FRIDAY_LLM_HEALTH_TIMEOUT", "2"))
        try:
            resp = httpx.get(url, timeout=timeout)
            if resp.status_code < 400:
                return True, "reachable"
            return False, f"bad_status_{resp.status_code}"
        except Exception as exc:
            return False, f"unreachable:{exc}"


llm_client = LLMClient()
