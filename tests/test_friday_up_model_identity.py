from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_manual_endpoint_rejects_reachable_wrong_model(tmp_path: Path) -> None:
    fake_curl = tmp_path / "curl"
    fake_curl.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' '{\"data\":[{\"id\":\"wrong-model\"}]}'\n",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{tmp_path}:{env['PATH']}",
            "LLM_BASE_URL": "http://127.0.0.1:9999/v1",
            "FRIDAY_MODEL_NAME": "exec",
            "AUTO_START_MUNINN": "0",
            "AUTO_START_MODELS": "0",
        }
    )

    result = subprocess.run(
        ["bash", "scripts/friday_up.sh"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "does not serve expected model 'exec'" in result.stderr
