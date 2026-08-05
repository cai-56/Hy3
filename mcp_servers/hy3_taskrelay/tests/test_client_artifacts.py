"""Regression checks for sanitized real-client evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from hy3_taskrelay.schemas import AuditResult, Checkpoint, ResumeBrief
from scripts.live_evaluation import assert_public_record

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = PROJECT_ROOT / "docs" / "client_artifacts"
CLIENTS = PROJECT_ROOT / "docs" / "clients"
DEMO = PROJECT_ROOT / "docs" / "demo"
NATIVE_RECORD = PROJECT_ROOT / "docs" / "native_clients_2026-08-05.json"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_real_client_artifacts_are_valid_and_linked() -> None:
    checkpoint = Checkpoint.model_validate(
        _load_json(ARTIFACTS / "codebuddy_checkpoint_2026-07-20.json")
    )
    audit = AuditResult.model_validate(_load_json(ARTIFACTS / "codex_audit_2026-07-20.json"))
    resume = ResumeBrief.model_validate(_load_json(ARTIFACTS / "codex_resume_2026-07-20.json"))

    assert checkpoint.checkpoint_id == audit.checkpoint_id == resume.checkpoint_id
    assert audit.overall_status == "clean"
    assert [step.priority for step in resume.next_steps] == [1, 2]


def test_client_records_match_the_validated_artifacts() -> None:
    codebuddy = _load_json(CLIENTS / "codebuddy_2026-07-20.json")
    codex = _load_json(CLIENTS / "codex_2026-07-20.json")

    assert codebuddy["exit_code"] == codex["exit_code"] == 0
    assert codebuddy["result"]["checkpoint_id"] == codex["input_checkpoint_id"]
    assert [call["status"] for call in codex["mcp_calls"]] == ["completed", "completed"]
    assert codebuddy["security"]["credentials_recorded"] is False
    assert codex["security"]["credentials_recorded"] is False


def test_actual_call_demo_is_bounded_and_rendered_from_current_records() -> None:
    for name in (
        "codebuddy_actual_call.png",
        "codex_actual_calls.png",
        "codebuddy_checkpoint.png",
        "codex_audit_resume.png",
    ):
        with Image.open(DEMO / name) as screenshot:
            assert screenshot.size == (1280, 720)

    with Image.open(DEMO / "taskrelay_cross_client.gif") as animation:
        durations = []
        for frame in range(animation.n_frames):
            animation.seek(frame)
            durations.append(animation.info["duration"])
        assert animation.size == (1280, 720)
        assert animation.n_frames == 6
        assert sum(durations) == 13_200


def test_native_client_demo_records_a_bounded_real_client_handoff() -> None:
    record = _load_json(NATIVE_RECORD)

    assert record["source_sha"] == "1a7694ec9451f0300d683d7071e9a44ddc064c65"
    assert record["clients"] == {
        "codebuddy": {"name": "CodeBuddy Code", "version": "2.124.0"},
        "codex": {"name": "Codex CLI", "version": "0.144.6"},
    }
    assert record["tool_sequence"] == [
        "taskrelay_create_checkpoint",
        "taskrelay_audit_checkpoint",
        "taskrelay_create_resume_brief",
    ]
    assert record["provider_verification"] == {
        "actual_model": "hy3-native-demo",
        "http_statuses": [200, 200, 200],
        "identity_verified": True,
        "requested_model": "hy3-native-demo",
    }
    assert record["artifact_linkage"] == {
        "audit_findings": 0,
        "audit_status": "clean",
        "checkpoint_id": "cp_373f9873c7b47571",
        "checkpoint_id_preserved": True,
        "resume_id": "resume_d8fbe6ea38b898ba",
        "resume_priorities": [1, 2],
    }
    assert record["validation_boundary"]["live_hy3_quality_measured"] is False
    assert record["validation_boundary"]["client_model_quality_measured"] is False
    assert record["privacy"]["raw_client_streams_committed"] is False
    assert record["privacy"]["network_locations_committed"] is False
    assert_public_record(record, ())

    demo_path = DEMO / record["recording"]["file"]
    assert hashlib.sha256(demo_path.read_bytes()).hexdigest() == record["recording"]["sha256"]
    with Image.open(demo_path) as animation:
        durations = []
        for frame in range(animation.n_frames):
            animation.seek(frame)
            durations.append(animation.info["duration"])
        assert animation.size == (853, 720)
        assert animation.n_frames == 85
        assert 30_000 <= sum(durations) <= 60_000
        assert animation.info.get("comment") is None

    raw_demo = demo_path.read_bytes().lower()
    for marker in (
        b"c:\\users",
        b"http://",
        b"https://",
        b"authorization",
        b"api_key",
        b"request_id",
        b"thread_id",
    ):
        assert marker not in raw_demo
