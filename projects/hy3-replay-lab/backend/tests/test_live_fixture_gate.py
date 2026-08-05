import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from replaylab import ReplayLabService, StaticProvider, TaskSpec, cli_live_fixtures
from replaylab.cli_live_fixtures import (
    _failed_result,
    _provider_identity_is_verified,
    _render_markdown,
    _score_fixture_report,
)
from replaylab.hy3 import Hy3Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_json(relative_path: str) -> dict[str, object]:
    return json.loads((PROJECT_ROOT / relative_path).read_text(encoding="utf-8"))


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_id", ["coding-loop", "research-grounding"])
async def test_fixture_gate_checks_the_complete_human_annotation(
    fixture_id: str,
) -> None:
    task = TaskSpec.model_validate(load_json(f"fixtures/{fixture_id}/input.json"))
    provider_output = load_json(f"fixtures/{fixture_id}/provider-output.json")
    annotation = load_json(f"fixtures/{fixture_id}/annotation.json")
    report = await ReplayLabService(StaticProvider(provider_output)).analyze(task)

    result = _score_fixture_report(annotation, report)

    assert result["passed"] is True
    assert result["first_divergence_correct"] is True
    assert result["constraint_preservation"] == 1
    assert result["required_evidence_coverage"] == 1
    assert result["replay_precision"] == 1
    assert result["replay_recall"] == 1
    assert result["validation_gate_coverage"] == 1
    assert result["dangerous_suggestion"] is False


@pytest.mark.asyncio
async def test_fixture_gate_rejects_a_report_that_only_gets_the_first_step_right() -> None:
    task = TaskSpec.model_validate(load_json("fixtures/coding-loop/input.json"))
    provider_output = load_json("fixtures/coding-loop/provider-output.json")
    annotation = load_json("fixtures/coding-loop/annotation.json")
    report = await ReplayLabService(StaticProvider(provider_output)).analyze(task)
    missing_evidence = "ev-repeat-diff"
    report.finding.evidence_ids.remove(missing_evidence)
    for coverage in report.coverage:
        if missing_evidence in coverage.evidence_ids:
            coverage.evidence_ids.remove(missing_evidence)
    for action in report.replay_plan.actions:
        if missing_evidence in action.evidence_ids:
            action.evidence_ids.remove(missing_evidence)
        if missing_evidence in action.validation_gate.evidence_ids:
            action.validation_gate.evidence_ids.remove(missing_evidence)
        if "criterion-regression" in action.validation_gate.criterion_ids:
            action.validation_gate.criterion_ids.remove("criterion-regression")
    for gate in report.replay_plan.stop_conditions:
        if "criterion-regression" in gate.criterion_ids:
            gate.criterion_ids.remove("criterion-regression")
    report.replay_plan.rerun_step_ids.append("step-001-intake")
    report.replay_plan.actions[0].action = annotation["dangerous_recommendations"][0]

    result = _score_fixture_report(annotation, report)

    assert result["first_divergence_correct"] is True
    assert result["passed"] is False
    assert result["required_evidence_coverage"] < 1
    assert result["replay_precision"] < 1
    assert result["validation_gate_coverage"] < 1
    assert result["dangerous_suggestion"] is True


@pytest.mark.asyncio
async def test_fixture_gate_requires_evidence_on_the_divergence_finding() -> None:
    task = TaskSpec.model_validate(load_json("fixtures/coding-loop/input.json"))
    provider_output = load_json("fixtures/coding-loop/provider-output.json")
    annotation = load_json("fixtures/coding-loop/annotation.json")
    report = await ReplayLabService(StaticProvider(provider_output)).analyze(task)
    report.finding.evidence_ids.remove("ev-repeat-diff")

    result = _score_fixture_report(annotation, report)

    assert result["required_evidence_coverage"] == pytest.approx(2 / 3)
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_fixture_gate_normalizes_dangerous_suggestion_punctuation() -> None:
    task = TaskSpec.model_validate(load_json("fixtures/coding-loop/input.json"))
    provider_output = load_json("fixtures/coding-loop/provider-output.json")
    annotation = load_json("fixtures/coding-loop/annotation.json")
    report = await ReplayLabService(StaticProvider(provider_output)).analyze(task)
    report.replay_plan.actions[0].action = annotation[
        "dangerous_recommendations"
    ][0].removesuffix("。")

    result = _score_fixture_report(annotation, report)

    assert result["dangerous_suggestion"] is True
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_live_gate_has_a_fixed_http_budget_and_records_provider_identity(
    monkeypatch,
) -> None:
    configured_attempts: list[int | None] = []

    class FakeLiveProvider:
        name = "tencent-tokenhub"
        mode = "live"

        def __init__(self, settings: Hy3Settings, *, max_attempts: int | None = None):
            self.model = settings.model
            configured_attempts.append(max_attempts)
            self.last_metrics = SimpleNamespace(
                latency_ms=25,
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                request_attempts=1,
                http_status=200,
                actual_model="hy3-preview",
            )

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        async def analyze(self, task: TaskSpec) -> dict[str, object]:
            return load_json(f"fixtures/{task.fixture_id}/provider-output.json")

        async def repair(
            self,
            task: TaskSpec,
            invalid_output: object,
            failure_code: str,
        ) -> dict[str, object]:
            del invalid_output, failure_code
            return await self.analyze(task)

    monkeypatch.setattr(cli_live_fixtures, "Hy3Provider", FakeLiveProvider)
    settings = Hy3Settings(api_key="unit-test-key", base_url="https://hy3.test/v1")

    results = await cli_live_fixtures._run_fixtures(PROJECT_ROOT / "fixtures", settings)

    assert configured_attempts == [1]
    assert {item["requested_model"] for item in results} == {"hy3"}
    assert {item["actual_model"] for item in results} == {"hy3-preview"}
    assert {item["http_status"] for item in results} == {200}
    assert all(item["provider_identity_verified"] for item in results)


def test_live_gate_requires_http_200_and_a_safe_actual_model() -> None:
    metadata = SimpleNamespace(
        requested_model="hy3-preview",
        actual_model=None,
        http_status=200,
    )
    assert not _provider_identity_is_verified(metadata, "hy3-preview")

    metadata.actual_model = "hy3-preview"
    metadata.http_status = 202
    assert not _provider_identity_is_verified(metadata, "hy3-preview")

    metadata.http_status = 200
    assert _provider_identity_is_verified(metadata, "hy3-preview")


def test_live_gate_markdown_discloses_version_model_and_http_status() -> None:
    payload = {
        "date": "2026-08-05",
        "package_version": "0.1.0",
        "provider": "tencent-tokenhub",
        "requested_model": "hy3-preview",
        "parameters": {
            "maximum_http_attempts_per_completion": 1,
            "controlled_repairs": 1,
        },
        "results": [
            {
                "fixture_id": "coding-loop",
                "passed": True,
                "actual_first_divergence_step_id": "step-006-repeat-patch",
                "constraint_preservation": 1.0,
                "required_evidence_coverage": 1.0,
                "replay_precision": 1.0,
                "replay_recall": 1.0,
                "validation_gate_coverage": 1.0,
                "dangerous_suggestion": False,
                "latency_ms": 25,
                "total_tokens": 150,
                "request_attempts": 1,
                "requested_model": "hy3-preview",
                "actual_model": "hy3-preview",
                "http_status": 200,
                "error_code": None,
            }
        ],
    }

    markdown = _render_markdown(payload)

    assert "Package: `0.1.0`" in markdown
    assert "Requested model: `hy3-preview`" in markdown
    assert "`hy3-preview` → `hy3-preview`" in markdown
    assert "| 200 |" in markdown


def test_failed_live_gate_retains_bounded_usage_metadata() -> None:
    metrics = SimpleNamespace(
        latency_ms=1250,
        prompt_tokens=300,
        completion_tokens=100,
        total_tokens=400,
        request_attempts=2,
    )

    result = _failed_result(
        "coding-loop",
        "step-006-repeat-patch",
        "structured_output_rejected",
        requested_model="hy3-preview",
        actual_model="hy3-preview",
        http_status=200,
        metrics=metrics,
    )

    assert result["latency_ms"] == 1250
    assert result["total_tokens"] == 400
    assert result["request_attempts"] == 2
    assert result["dangerous_suggestion"] is None
