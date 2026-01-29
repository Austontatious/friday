# friday/memory_types.py – unified data model
from __future__ import annotations

"""Friday AI – unified memory data model.

A **MemoryShard** is the atomic unit written to the JSONL store.  It
encodes either a single conversational **interaction** (`prompt` →
`response`) or a consolidated discussion **thread**.  The two shapes are
chosen via the `type` field and share common metadata so they can live
side‑by‑side in the same file without migrations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
import time
import uuid


@dataclass
class MemoryShard:
    """Canonical memory record.

    Fields are deliberately **optional** so the loader can accept legacy
    shards that were missing some attributes.  New shards are always
    written with the full schema produced by :py:meth:`to_dict`.
    """

    # Core identifiers
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    shard_type: str = "interaction"  # "interaction" | "thread"
    session_id: str = "default"

    # Interaction‑specific
    prompt: Optional[str] = None
    response: Optional[str] = None

    # Thread‑specific
    thread_id: Optional[str] = None
    text: Optional[str] = None

    # Metadata / housekeeping
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_used: float = field(default_factory=time.time)

    # ------------------------------------------------------------------
    #  Convenience helpers
    # ------------------------------------------------------------------
    def touch(self) -> None:
        """Update :pyattr:`last_used` to *now*."""
        self.last_used = time.time()

    # ------------------------------------------------------------------
    #  (De)serialization
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Convert the shard to a fully‑expressed dict suitable for JSON."""
        return {
            "id": self.id,
            "type": self.shard_type,
            "session_id": self.session_id,
            "prompt": self.prompt,
            "response": self.response,
            "thread_id": self.thread_id,
            "text": self.text,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "last_used": self.last_used,
        }
    def to_json(self) -> str:
        """Serialize shard as compact JSON line."""
        import json
        return json.dumps(self.to_dict())

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "MemoryShard":
        """Robust loader that accepts both new and legacy shapes."""
        return MemoryShard(
            id=data.get("id", str(uuid.uuid4())),
            shard_type=data.get("type", "interaction"),
            session_id=data.get("session_id", "default"),
            prompt=data.get("prompt"),
            response=data.get("response"),
            thread_id=data.get("thread_id"),
            text=data.get("text"),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            last_used=data.get("last_used", time.time()),
        )
    def from_json(json_line: str) -> "MemoryShard":
        """Deserialize from a raw JSON line."""
        import json
        data = json.loads(json_line)
        return MemoryShard.from_dict(data)
