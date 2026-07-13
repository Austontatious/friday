from sketchmath.evals.run_sketchmath_evals import _stable_result_value


def test_eval_report_removes_nested_runtime_timestamps() -> None:
    payload = {
        "artifact_created_at": "2026-07-13T00:00:00Z",
        "metadata": {
            "artifact_filename": "export.step",
            "nested": [{"artifact_created_at": "later", "volume": 42.0}],
        },
    }

    assert _stable_result_value(payload) == {
        "metadata": {
            "artifact_filename": "export.step",
            "nested": [{"volume": 42.0}],
        }
    }


def test_eval_report_normalizes_generated_command_identifiers() -> None:
    payload = {
        "command_id": "cmd_translate_random",
        "command_type": "make_profile",
        "parameters": {"name": "profile_random"},
    }

    assert _stable_result_value(payload) == {
        "command_id": "<generated>",
        "command_type": "make_profile",
        "parameters": {"name": "<generated_profile>"},
    }
