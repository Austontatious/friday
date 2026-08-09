from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _env_bool(*names: str, default: bool) -> bool:
    for name in names:
        raw = os.getenv(name)
        if raw is not None:
            return raw.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _env_int(*names: str, default: int) -> int:
    for name in names:
        raw = os.getenv(name)
        if raw is None or not raw.strip():
            continue
        try:
            return int(raw)
        except ValueError:
            continue
    return default


def _env_float(*names: str, default: float) -> float:
    for name in names:
        raw = os.getenv(name)
        if raw is None or not raw.strip():
            continue
        try:
            return float(raw)
        except ValueError:
            continue
    return default


def _env_str(*names: str, default: str) -> str:
    for name in names:
        raw = os.getenv(name)
        if raw is not None and raw.strip():
            return raw.strip()
    return default


@dataclass(frozen=True)
class CodexStandardsConfig:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout_seconds: float
    llm_max_retries: int
    llm_temperature: float
    llm_max_tokens: int
    tracing_enabled: bool
    tracing_backend: str
    tracing_jsonl_path: str
    eval_pass_threshold: float
    eval_dataset_glob: str
    prompt_root: str
    prompt_profile: str

    @classmethod
    def from_env(cls) -> "CodexStandardsConfig":
        return cls(
            llm_base_url=_env_str("LLM_BASE_URL", "CODEX_LLM_BASE_URL", default=""),
            llm_api_key=_env_str("LLM_API_KEY", "CODEX_LLM_API_KEY", default=""),
            llm_model=_env_str("FRIDAY_MODEL_NAME", "CODEX_LLM_MODEL", default="friday"),
            llm_timeout_seconds=_env_float("FRIDAY_LLM_TIMEOUT", "CODEX_LLM_TIMEOUT_SECONDS", default=30.0),
            llm_max_retries=_env_int("FRIDAY_LLM_MAX_RETRIES", "CODEX_LLM_MAX_RETRIES", default=2),
            llm_temperature=_env_float("FRIDAY_TEMPERATURE", "CODEX_LLM_TEMPERATURE", default=0.7),
            llm_max_tokens=_env_int("FRIDAY_MAX_TOKENS", "CODEX_LLM_MAX_TOKENS", default=512),
            tracing_enabled=_env_bool("FRIDAY_CODEX_TRACING_ENABLED", "CODEX_TRACING_ENABLED", default=False),
            tracing_backend=_env_str("FRIDAY_CODEX_TRACING_BACKEND", "CODEX_TRACING_BACKEND", default="noop"),
            tracing_jsonl_path=_env_str(
                "FRIDAY_CODEX_TRACING_JSONL_PATH",
                "CODEX_TRACING_JSONL_PATH",
                default=".mimir/trace/llm-trace.jsonl",
            ),
            eval_pass_threshold=_env_float("FRIDAY_CODEX_EVAL_PASS_THRESHOLD", "CODEX_EVAL_PASS_THRESHOLD", default=1.0),
            eval_dataset_glob=_env_str("FRIDAY_CODEX_EVAL_DATASET_GLOB", "CODEX_EVAL_DATASET_GLOB", default="evals/cases/**/*.json"),
            prompt_root=_env_str("FRIDAY_CODEX_PROMPT_ROOT", "CODEX_PROMPT_ROOT", default="prompts"),
            prompt_profile=_env_str("FRIDAY_PROMPT_PROFILE", default="friday_exec_v1"),
        )


@dataclass(frozen=True)
class RefinementConfig:
    enabled: bool
    mode: str
    max_extra_turns: int
    compare_enabled: bool
    trace_enabled: bool
    trace_path: str
    min_score_for_accept: float
    fail_open: bool

    @classmethod
    def from_env(cls) -> "RefinementConfig":
        return cls(
            enabled=_env_bool("FRIDAY_REFINEMENT_ENABLED", default=False),
            mode=_env_str("FRIDAY_REFINEMENT_MODE", default="patch_or_regen"),
            max_extra_turns=_env_int("FRIDAY_REFINEMENT_MAX_EXTRA_TURNS", default=2),
            compare_enabled=_env_bool("FRIDAY_REFINEMENT_COMPARE_ENABLED", default=False),
            trace_enabled=_env_bool("FRIDAY_REFINEMENT_TRACE_ENABLED", default=False),
            trace_path=_env_str("FRIDAY_REFINEMENT_TRACE_PATH", default="logs/refinement/friday_refinement_runs.jsonl"),
            min_score_for_accept=_env_float("FRIDAY_REFINEMENT_MIN_SCORE_FOR_ACCEPT", default=0.75),
            fail_open=_env_bool("FRIDAY_REFINEMENT_FAIL_OPEN", default=True),
        )


@dataclass(frozen=True)
class HandoffConfig:
    enabled: bool
    trace_enabled: bool
    trace_path: str
    max_revision_budget: int
    max_candidate_chars: int
    max_timeout_ms: int
    allow_command_execution: bool
    command_timeout_ms: int

    @classmethod
    def from_env(cls) -> "HandoffConfig":
        return cls(
            enabled=_env_bool("FRIDAY_HANDOFF_ENABLED", default=False),
            trace_enabled=_env_bool("FRIDAY_HANDOFF_TRACE_ENABLED", default=True),
            trace_path=_env_str("FRIDAY_HANDOFF_TRACE_PATH", default="logs/handoff/friday_handoff_runs.jsonl"),
            max_revision_budget=max(0, _env_int("FRIDAY_HANDOFF_MAX_REVISION_BUDGET", default=2)),
            max_candidate_chars=max(256, _env_int("FRIDAY_HANDOFF_MAX_CANDIDATE_CHARS", default=12000)),
            max_timeout_ms=max(1000, _env_int("FRIDAY_HANDOFF_MAX_TIMEOUT_MS", default=45000)),
            allow_command_execution=_env_bool("FRIDAY_HANDOFF_ALLOW_COMMAND_EXECUTION", default=True),
            command_timeout_ms=max(500, _env_int("FRIDAY_HANDOFF_COMMAND_TIMEOUT_MS", default=30000)),
        )


@dataclass(frozen=True)
class AlthingBridgeConfig:
    enabled: bool
    default_mode: str
    althing_base_url: str
    althing_route_path: str
    timeout_ms: int
    model_hint: str

    @classmethod
    def from_env(cls) -> "AlthingBridgeConfig":
        default_mode_raw = _env_str("FRIDAY_UI_DEFAULT_MODE", default="althing").strip().lower()
        default_mode = "direct_friday" if default_mode_raw in {"direct_friday", "direct", "friday"} else "althing"
        return cls(
            enabled=_env_bool("FRIDAY_ALTHING_BRIDGE_ENABLED", default=True),
            default_mode=default_mode,
            althing_base_url=_env_str("FRIDAY_ALTHING_BASE_URL", default="http://localhost:8010"),
            althing_route_path=_env_str("FRIDAY_ALTHING_ROUTE_PATH", default="/chat/completions"),
            timeout_ms=max(1000, _env_int("FRIDAY_ALTHING_TIMEOUT_MS", default=45000)),
            model_hint=_env_str("FRIDAY_ALTHING_MODEL_HINT", default="auto_no_reason"),
            )


@dataclass(frozen=True)
class CompanionConfig:
    enabled: bool
    default_mode: str
    session_ttl_seconds: int
    top_k: int
    min_score: float

    @classmethod
    def from_env(cls) -> "CompanionConfig":
        mode = _env_str("FRIDAY_COMPANION_DEFAULT_MODE", default="companion").strip().lower()
        if mode not in {"companion", "halo", "review"}:
            mode = "companion"
        return cls(
            enabled=_env_bool("FRIDAY_COMPANION_ENABLED", default=False),
            default_mode=mode,
            session_ttl_seconds=max(60, _env_int("FRIDAY_COMPANION_SESSION_TTL_SECONDS", default=3600)),
            top_k=max(1, _env_int("FRIDAY_COMPANION_TOP_K", default=3)),
            min_score=max(0.0, min(1.0, _env_float("FRIDAY_COMPANION_MIN_SCORE", default=0.55))),
        )


@dataclass(frozen=True)
class SketchMathConfig:
    enabled: bool
    document_v1_enabled: bool
    artifact_jobs_enabled: bool
    session_dir: str
    cad_export_dir: str
    artifact_job_dir: str
    freecad_cmd: str
    cad_timeout_seconds: float

    @classmethod
    def from_env(cls) -> "SketchMathConfig":
        session_dir = _env_str(
            "FRIDAY_SKETCHMATH_SESSION_DIR",
            default=str(Path("artifacts") / "sketchmath" / "sessions"),
        )
        cad_export_dir = _env_str(
            "FRIDAY_SKETCHMATH_CAD_EXPORT_DIR",
            default=str(Path("artifacts") / "sketchmath" / "cad"),
        )
        artifact_job_dir = _env_str(
            "FRIDAY_SKETCHMATH_ARTIFACT_JOB_DIR",
            default=str(Path("artifacts") / "sketchmath" / "jobs"),
        )
        return cls(
            enabled=_env_bool("FRIDAY_SKETCHMATH_ENABLED", default=False),
            document_v1_enabled=_env_bool("FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED", default=False),
            artifact_jobs_enabled=_env_bool("FRIDAY_SKETCHMATH_ARTIFACT_JOBS_ENABLED", default=False),
            session_dir=session_dir,
            cad_export_dir=cad_export_dir,
            artifact_job_dir=artifact_job_dir,
            freecad_cmd=_env_str("FRIDAY_SKETCHMATH_FREECAD_CMD", default=""),
            cad_timeout_seconds=_env_float("FRIDAY_SKETCHMATH_CAD_TIMEOUT_SECONDS", default=60.0),
        )
