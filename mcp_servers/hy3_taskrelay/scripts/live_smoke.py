"""Run all three TaskRelay operations against the configured real Hy3 API."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
from dataclasses import asdict
from datetime import date
from importlib.metadata import version
from pathlib import Path

import httpx

from hy3_taskrelay.config import Settings
from hy3_taskrelay.hy3_client import (
    MAX_COMPLETION_TOKENS,
    REASONING_EFFORT,
    TEMPERATURE,
    TOP_P,
    Hy3Client,
)
from hy3_taskrelay.schemas import (
    AuditCheckpointInput,
    CreateCheckpointInput,
    CreateResumeBriefInput,
)
from hy3_taskrelay.security import redact_data
from hy3_taskrelay.service import TaskRelayService

_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _current_source_sha(project_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(project_root.parents[1]), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    source_sha = completed.stdout.strip()
    if not _FULL_SHA.fullmatch(source_sha):
        raise RuntimeError("git did not return a full source commit SHA")
    return source_sha


def _metadata_since(client: Hy3Client, offset: int) -> list[dict[str, object]]:
    metadata = client.call_metadata[offset:]
    if not metadata:
        raise RuntimeError("the operation completed without verified provider metadata")
    return [asdict(item) for item in metadata]


async def run(
    fixture_path: Path,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    source_sha: str | None = None,
    settings: Settings | None = None,
) -> dict[str, object]:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    settings = settings or Settings.from_env()
    secret = settings.api_key.get_secret_value()
    client = Hy3Client(settings, transport=transport)
    service = TaskRelayService(client, secret_values=(secret,))
    checkpoint_offset = len(client.call_metadata)
    checkpoint = await service.create_checkpoint(
        CreateCheckpointInput.model_validate(fixture["create_input"])
    )
    checkpoint_calls = _metadata_since(client, checkpoint_offset)
    audit_offset = len(client.call_metadata)
    audit = await service.audit_checkpoint(
        AuditCheckpointInput(
            checkpoint=checkpoint,
            additional_evidence=fixture["additional_evidence"],
        )
    )
    audit_calls = _metadata_since(client, audit_offset)
    resume_offset = len(client.call_metadata)
    resume = await service.create_resume_brief(
        CreateResumeBriefInput(
            checkpoint=checkpoint,
            audit=audit,
            continuation_context=fixture["continuation_context"],
        )
    )
    resume_calls = _metadata_since(client, resume_offset)
    project_root = fixture_path.resolve().parents[2]
    verified_source_sha = source_sha or _current_source_sha(project_root)
    if not _FULL_SHA.fullmatch(verified_source_sha):
        raise ValueError("source_sha must be a full 40-character lowercase Git SHA")
    record = {
        "date": date.today().isoformat(),
        "source_sha": verified_source_sha,
        "fixture_id": fixture["fixture_id"],
        "package_versions": {
            "hy3-taskrelay": version("hy3-taskrelay"),
            "mcp": version("mcp"),
        },
        "parameters": {
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "reasoning_effort": REASONING_EFFORT,
        },
        "checkpoint": {
            "checkpoint_id": checkpoint.checkpoint_id,
            "confirmed_fact_count": len(checkpoint.confirmed_facts),
            "next_step_count": len(checkpoint.next_steps),
            "provider_calls": checkpoint_calls,
        },
        "audit": {
            "overall_status": audit.overall_status,
            "finding_categories": [finding.category for finding in audit.findings],
            "provider_calls": audit_calls,
        },
        "resume": {
            "resume_id": resume.resume_id,
            "priority_order": [step.priority for step in resume.next_steps],
            "provider_calls": resume_calls,
        },
        "redaction": (
            "Only bounded metadata is recorded; prompts, raw responses, and "
            "credentials are omitted."
        ),
    }
    return redact_data(record, (secret,))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "examples"
        / "fixtures"
        / "interrupted_bug_fix.json",
    )
    parser.add_argument(
        "--source-sha",
        help="Full source commit SHA represented by this run (defaults to local HEAD)",
    )
    arguments = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(run(arguments.fixture, source_sha=arguments.source_sha)),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
