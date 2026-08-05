import json
from pathlib import Path

import httpx
import pytest

from hy3_taskrelay.config import Settings
from scripts.live_smoke import run


@pytest.mark.asyncio
async def test_live_smoke_records_verified_http_model_package_and_source_identity() -> None:
    project_root = Path(__file__).resolve().parents[1]
    fixture_path = project_root / "examples" / "fixtures" / "interrupted_bug_fix.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    responses = iter(fixture["hy3_responses"][name] for name in ("checkpoint", "audit", "resume"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "hy3",
                "choices": [{"message": {"content": json.dumps(next(responses))}}],
            },
        )

    record = await run(
        fixture_path,
        transport=httpx.MockTransport(handler),
        source_sha="a" * 40,
        settings=Settings.from_env(
            {
                "HY3_API_KEY": "test-key",
                "HY3_BASE_URL": "https://example.test/v1",
                "HY3_MODEL": "hy3",
            }
        ),
    )

    assert record["source_sha"] == "a" * 40
    assert record["package_versions"]["hy3-taskrelay"] == "0.1.0"
    assert record["package_versions"]["mcp"]
    assert record["parameters"]["max_completion_tokens"] == 1_600
    for operation in ("checkpoint", "audit", "resume"):
        assert record[operation]["provider_calls"] == [
            {
                "http_status": 200,
                "requested_model": "hy3",
                "actual_model": "hy3",
            }
        ]
