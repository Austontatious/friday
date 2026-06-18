from __future__ import annotations

from pathlib import Path

import pytest


def _session(items: list[dict[str, object]]):
    from sketchmath.executor.command_router import GeometrySession
    from sketchmath.models.selection_context import SelectionContext

    return GeometrySession(
        SelectionContext.model_validate(
            {
                "selection_set_id": "sel_extrude",
                "units": "mm",
                "frame": "canvas_2d",
                "items": items,
                "constraints": [],
                "named_references": {},
            }
        )
    )


def _command(command_type: str, command_id: str, *, mode: str = "preview", selection: list[str] | None = None, parameters: dict[str, object] | None = None):
    from sketchmath.models.geometry_command import GeometryCommand

    return GeometryCommand.model_validate(
        {
            "version": "0.1",
            "command_id": command_id,
            "mode": mode,
            "command_type": command_type,
            "selection": selection or [],
            "parameters": parameters or {},
        }
    )


def _profile() -> dict[str, object]:
    return {
        "id": "profile_box",
        "type": "profile_2d",
        "vertices": [[0, 0], [20, 0], [20, 10], [0, 10], [0, 0]],
        "area": 200.0,
        "winding": "counterclockwise",
        "warnings": [],
        "closed": True,
    }


def _hole_profile() -> dict[str, object]:
    return {
        "id": "profile_inner",
        "type": "profile_2d",
        "vertices": [[4, 2], [16, 2], [16, 8], [4, 8], [4, 2]],
        "area": 72.0,
        "winding": "clockwise",
        "warnings": [],
        "closed": True,
    }


def test_extrude_profile_commit_exports_step_and_records_history() -> None:
    session = _session([_profile()])

    result = session.execute(
        _command(
            "extrude_profile",
            "cmd_extrude_profile",
            mode="commit",
            selection=["profile_box"],
            parameters={"depth": 7.5, "depth_unit": "mm", "direction": "positive_normal", "output_format": "step"},
        )
    )

    export = result.metadata["cad_export"]
    assert result.status == "committed"
    assert result.value == pytest.approx(1500.0)
    assert result.unit == "mm^3"
    assert export["status"] == "export_ready"
    assert export["artifacts"]["preview_path"] is None
    assert Path(export["artifacts"]["step_path"]).exists()
    assert Path(export["artifacts"]["validation_json"]).exists()
    assert export["measurements"]["volume_mm3"] == pytest.approx(1500.0)
    assert export["measurements"]["area_mm2"] == pytest.approx(850.0)
    assert export["measurements"]["bbox"]["zmax"] == pytest.approx(7.5)
    assert [tuple(vertex) for vertex in session.state.items[0].vertices] == [tuple(vertex) for vertex in _profile()["vertices"]]
    assert len(session.history.records) == 1
    reverted = session.revert()
    assert reverted.items[0].vertices == session.initial_state.items[0].vertices
    assert session.history.records == []


def test_extrude_profile_preview_does_not_mutate_state() -> None:
    session = _session([_profile()])

    result = session.execute(
        _command(
            "extrude_profile",
            "cmd_extrude_profile_preview",
            selection=["profile_box"],
            parameters={"depth": 7.5, "depth_unit": "mm", "direction": "positive_normal", "output_format": "step"},
        )
    )

    assert result.status == "preview"
    assert [tuple(vertex) for vertex in session.state.items[0].vertices] == [tuple(vertex) for vertex in _profile()["vertices"]]
    assert session.history.records == []
    assert result.metadata["cad_export"]["status"] == "export_ready"


def test_validate_profile_holes_rejects_tangent_hole() -> None:
    from sketchmath.cad.profile_holes import validate_profile_holes
    from sketchmath.models.entities import Profile2DEntity

    outer = Profile2DEntity.model_validate(_profile())
    tangent_hole = {
        "id": "profile_tangent",
        "type": "profile_2d",
        "vertices": [[20, 2], [18, 2], [18, 4], [20, 4], [20, 2]],
        "area": 4.0,
        "winding": "clockwise",
        "warnings": [],
        "closed": True,
    }
    hole = Profile2DEntity.model_validate(tangent_hole)
    result = validate_profile_holes(outer, [hole])

    assert result.ok is False
    assert result.error_code == "profile_intersection"
    assert "strictly inside" in (result.message or "")


def test_extrude_profile_commit_with_holes_records_strategy() -> None:
    session = _session([_profile(), _hole_profile()])

    result = session.execute(
        _command(
            "extrude_profile",
            "cmd_extrude_with_holes",
            mode="commit",
            selection=["profile_box"],
            parameters={
                "depth": 7.5,
                "depth_unit": "mm",
                "direction": "positive_normal",
                "output_format": "step",
                "holes": ["profile_inner"],
            },
        )
    )

    export = result.metadata["cad_export"]
    assert export["status"] == "export_ready"
    assert export["metadata"]["adapter_strategy"] in {"face_with_holes", "boolean_subtraction"}
    assert export["metadata"]["hole_count"] == 1
    assert export["measurements"]["is_valid_solid"] is True
    assert export["measurements"]["bbox"]["zmax"] == pytest.approx(7.5)
    assert export["measurements"]["volume_mm3"] == pytest.approx((200.0 - 72.0) * 7.5, abs=1e-3)
    assert result.metadata["profile_hole_validation"]["ok"] is True


def test_boolean_fallback_triggers_on_construction_failure(monkeypatch, tmp_path) -> None:
    session = _session([_profile(), _hole_profile()])
    from sketchmath.cad.adapter import CadAdapter

    worker_script = tmp_path / "fallback_worker.py"
    worker_script.write_text(
        """
from __future__ import annotations

import pathlib
import runpy
import sys

REPO_ROOT = pathlib.Path('/mnt/data/friday')
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import sketchmath.cad.freecad_extrude_profile as worker

_original_face_with_holes = worker._face_with_holes

def _fail_when_holes_present(outer_vertices, hole_vertices):
    if hole_vertices:
        raise RuntimeError('forced face construction failure')
    return _original_face_with_holes(outer_vertices, hole_vertices)

worker._face_with_holes = _fail_when_holes_present
raise SystemExit(worker.main())
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        CadAdapter,
        "from_env",
        classmethod(lambda cls: CadAdapter(freecad_cmd="/mnt/data/freecad/squashfs-root/usr/bin/freecadcmd", worker_script=worker_script)),
    )

    result = session.execute(
        _command(
            "extrude_profile",
            "cmd_extrude_fallback",
            mode="commit",
            selection=["profile_box"],
            parameters={
                "depth": 7.5,
                "depth_unit": "mm",
                "direction": "positive_normal",
                "output_format": "step",
                "holes": ["profile_inner"],
            },
        )
    )

    export = result.metadata["cad_export"]
    assert export["metadata"]["adapter_strategy"] == "boolean_subtraction"
    assert export["metadata"]["fallback_reason"]
    assert export["measurements"]["is_valid_solid"] is True
    assert export["measurements"]["volume_mm3"] == pytest.approx((200.0 - 72.0) * 7.5, abs=1e-3)


def test_extrude_profile_rejects_non_profile_selection() -> None:
    session = _session([
        {"id": "point_A", "type": "point_2d", "coords": [0, 0], "locked": False},
    ])

    with pytest.raises(Exception) as exc_info:
        session.execute(
            _command(
                "extrude_profile",
                "cmd_extrude_bad",
                mode="commit",
                selection=["point_A"],
                parameters={"depth": 5.0, "depth_unit": "mm", "direction": "positive_normal", "output_format": "step"},
            )
        )

    assert exc_info.value.to_dict()["code"] == "wrong_entity_type"


def test_extrude_profile_rejects_invalid_depth_units() -> None:
    session = _session([_profile()])

    with pytest.raises(Exception) as exc_info:
        session.execute(
            _command(
                "extrude_profile",
                "cmd_extrude_bad_units",
                mode="commit",
                selection=["profile_box"],
                parameters={"depth": 5.0, "depth_unit": "cm", "direction": "positive_normal", "output_format": "step"},
            )
        )

    assert exc_info.value.to_dict()["code"] == "invalid_units"


def test_extrude_profile_reports_unavailable_freecad(monkeypatch) -> None:
    monkeypatch.setenv("FRIDAY_SKETCHMATH_FREECAD_CMD", "/definitely/missing/freecadcmd")
    monkeypatch.setattr("sketchmath.cad.adapter.shutil.which", lambda _name: None)
    session = _session([_profile()])

    with pytest.raises(Exception) as exc_info:
        session.execute(
            _command(
                "extrude_profile",
                "cmd_extrude_unavailable",
                mode="commit",
                selection=["profile_box"],
                parameters={"depth": 5.0, "depth_unit": "mm", "direction": "positive_normal", "output_format": "step"},
            )
        )

    assert exc_info.value.to_dict()["code"] == "cad_adapter_unavailable"
