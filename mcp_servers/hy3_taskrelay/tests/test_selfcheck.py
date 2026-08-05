import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hy3_taskrelay import selfcheck


def _run_selfcheck() -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("HY3_API_KEY", None)
    environment.pop("HY3_BASE_URL", None)
    environment.pop("HY3_MODEL", None)
    return subprocess.run(
        [sys.executable, "-m", "hy3_taskrelay", "--selfcheck"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        env=environment,
        timeout=30,
        check=False,
    )


def test_selfcheck_runs_a_stable_offline_stdio_three_tool_chain() -> None:
    first = _run_selfcheck()
    second = _run_selfcheck()

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first.stderr == ""
    assert second.stderr == ""
    assert first.stdout == second.stdout
    assert len(first.stdout.encode("utf-8")) < 4_096

    result = json.loads(first.stdout)
    assert result["status"] == "passed"
    assert result["transport"] == "stdio"
    assert result["protocol_version"] == "2025-11-25"
    assert result["tools"] == [
        "taskrelay_audit_checkpoint",
        "taskrelay_create_checkpoint",
        "taskrelay_create_resume_brief",
    ]
    assert result["provider_http_statuses"] == [200, 200, 200]
    assert [call["tool"] for call in result["calls"]] == [
        "taskrelay_create_checkpoint",
        "taskrelay_audit_checkpoint",
        "taskrelay_create_resume_brief",
    ]
    assert [call["status"] for call in result["calls"]] == ["passed", "passed", "passed"]
    assert result["calls"][0]["checkpoint_id"].startswith("cp_")
    assert result["calls"][1] == {
        "tool": "taskrelay_audit_checkpoint",
        "status": "passed",
        "overall_status": "clean",
        "finding_count": 0,
    }
    assert result["calls"][2]["resume_id"].startswith("resume_")
    assert result["calls"][2]["priority_order"] == [1]

    serialized = first.stdout.casefold()
    assert "127.0.0.1" not in serialized
    assert "localhost" not in serialized
    assert "hy3_api_key" not in serialized
    assert "request_id" not in serialized
    assert str(Path(__file__).resolve().parents[1]).casefold() not in serialized


def test_selfcheck_failure_is_bounded_and_does_not_echo_internal_details(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    marker = "SECRET_ENDPOINT_REQUEST_ID_PERSONAL_PATH"

    def fail() -> dict[str, object]:
        raise RuntimeError(marker)

    monkeypatch.setattr(selfcheck, "run_selfcheck", fail)

    assert selfcheck.selfcheck_main() == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == '{"error":"offline selfcheck failed","status":"failed"}\n'
    assert marker not in captured.out
