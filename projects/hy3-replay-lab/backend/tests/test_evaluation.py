import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from replaylab import cli_evals
from replaylab.evaluation import (
    EvaluationOutcome,
    build_golden_draft,
    build_task,
    evaluate_suite,
    load_evaluation_suite,
    render_evaluation_markdown,
)
from replaylab.hy3 import Hy3Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_public_evaluation_suite_has_twelve_independent_stable_cases() -> None:
    suite = load_evaluation_suite(PROJECT_ROOT / "evals")
    tasks = [build_task(item) for item in suite.scenarios]
    digests = {
        hashlib.sha256(task.model_dump_json().encode("utf-8")).hexdigest()
        for task in tasks
    }

    assert len(tasks) == 12
    assert len(digests) == 12
    assert {item.category for item in suite.scenarios} >= {
        "no_divergence",
        "repeated_loop",
        "constraint_omission",
        "tool_misuse",
        "evidence_gap",
        "citation_error",
        "unsafe_action",
        "resource_limit",
    }


def test_golden_contract_scores_are_computed_from_separate_annotations() -> None:
    suite = load_evaluation_suite(PROJECT_ROOT / "evals")
    annotations = {item.case_id: item for item in suite.annotations}
    outcomes = [
        EvaluationOutcome(
            case_id=scenario.case_id,
            draft=build_golden_draft(scenario, annotations[scenario.case_id]),
            prompt_tokens=100,
            completion_tokens=25,
            total_tokens=125,
            latency_ms=index * 10,
        )
        for index, scenario in enumerate(suite.scenarios, start=1)
    ]

    metrics = evaluate_suite(suite, outcomes)

    assert metrics.case_count == 12
    assert metrics.first_divergence_accuracy == 1
    assert metrics.constraint_preservation_rate == 1
    assert metrics.citation_validity_rate == 1
    assert metrics.minimal_replay_precision == 1
    assert metrics.minimal_replay_recall == 1
    assert metrics.validation_gate_coverage_rate == 1
    assert metrics.dangerous_suggestion_rate == 0
    assert metrics.structured_success_rate == 1
    assert metrics.total_tokens == 1_500
    assert metrics.mean_tokens == 125
    assert metrics.p95_latency_ms == 120


def test_structured_failure_counts_against_every_quality_metric() -> None:
    suite = load_evaluation_suite(PROJECT_ROOT / "evals")
    annotations = {item.case_id: item for item in suite.annotations}
    outcomes = [
        EvaluationOutcome(
            case_id=scenario.case_id,
            draft=(
                None
                if index == 0
                else build_golden_draft(scenario, annotations[scenario.case_id])
            ),
            error_code="repair_failed" if index == 0 else None,
            total_tokens=0 if index == 0 else 120,
            latency_ms=0 if index == 0 else 12,
        )
        for index, scenario in enumerate(suite.scenarios)
    ]

    metrics = evaluate_suite(suite, outcomes)

    assert metrics.structured_success_rate == pytest.approx(11 / 12)
    assert metrics.accepted_case_count == 11
    assert metrics.first_divergence_accuracy == pytest.approx(11 / 12)
    assert metrics.dangerous_suggestion_rate == 0
    assert metrics.case_scores[0].dangerous_suggestion is None
    assert metrics.mean_tokens == 120
    assert metrics.mean_latency_ms == 12
    assert metrics.case_scores[0].error_code == "repair_failed"

    markdown = render_evaluation_markdown(
        metrics, mode="live-hy3", model="hy3-preview", run_date="2026-08-05"
    )
    assert "repair_failed" in markdown
    assert "Accepted structured reports: 11" in markdown
    assert "unknown" in markdown


def test_citation_metric_penalizes_missing_required_evidence() -> None:
    suite = load_evaluation_suite(PROJECT_ROOT / "evals")
    annotations = {item.case_id: item for item in suite.annotations}
    outcomes = []
    for index, scenario in enumerate(suite.scenarios):
        annotation = annotations[scenario.case_id]
        draft = build_golden_draft(scenario, annotation)
        if index == 0:
            missing = annotation.related_evidence_ids[1]
            draft.finding.evidence_ids.remove(missing)
            for action in draft.replay_plan.actions:
                if missing in action.evidence_ids:
                    action.evidence_ids.remove(missing)
        outcomes.append(EvaluationOutcome(case_id=scenario.case_id, draft=draft))

    metrics = evaluate_suite(suite, outcomes)

    assert metrics.case_scores[0].citation_validity == pytest.approx(2 / 3)
    assert metrics.citation_validity_rate == pytest.approx((11 + 2 / 3) / 12)


def test_dangerous_phrase_rules_cover_the_required_chinese_output_language() -> None:
    suite = load_evaluation_suite(PROJECT_ROOT / "evals")
    annotations = {item.case_id: item for item in suite.annotations}
    outcomes = []
    for scenario in suite.scenarios:
        draft = build_golden_draft(scenario, annotations[scenario.case_id])
        if scenario.case_id == "eval-destructive-action":
            draft.replay_plan.actions[0].action = "递归删除整个工作区"
        outcomes.append(EvaluationOutcome(case_id=scenario.case_id, draft=draft))

    metrics = evaluate_suite(suite, outcomes)
    destructive_score = next(
        item for item in metrics.case_scores if item.case_id == "eval-destructive-action"
    )

    assert all(
        any(
            "\u4e00" <= character <= "\u9fff"
            for term in annotation.dangerous_terms
            for character in term
        )
        for annotation in suite.annotations
    )
    assert destructive_score.dangerous_suggestion is True
    assert metrics.dangerous_suggestion_rate == pytest.approx(1 / 12)


def test_evaluation_markdown_labels_the_truth_source_and_runtime_mode() -> None:
    suite = load_evaluation_suite(PROJECT_ROOT / "evals")
    annotations = {item.case_id: item for item in suite.annotations}
    outcomes = [
        EvaluationOutcome(
            case_id=scenario.case_id,
            draft=build_golden_draft(scenario, annotations[scenario.case_id]),
        )
        for scenario in suite.scenarios
    ]
    metrics = evaluate_suite(suite, outcomes)

    markdown = render_evaluation_markdown(
        metrics,
        mode="offline-golden-contract",
        model="deterministic",
        run_date="2026-07-22",
    )

    assert "Human-authored annotations are the truth source" in markdown
    assert "offline-golden-contract" in markdown
    assert "First-divergence accuracy" in markdown
    assert "eval-malicious-trace" in markdown

    live_markdown = render_evaluation_markdown(
        metrics, mode="live-hy3", model="hy3", run_date="2026-07-22"
    )
    assert "bounded failures" in live_markdown
    assert "offline golden-contract mode" not in live_markdown


@pytest.mark.asyncio
async def test_broad_live_suite_limits_each_completion_to_one_http_attempt(
    monkeypatch,
) -> None:
    suite = load_evaluation_suite(PROJECT_ROOT / "evals")
    annotations = {item.case_id: item for item in suite.annotations}
    attempts: list[int | None] = []

    class FakeLiveProvider:
        name = "tencent-tokenhub"
        mode = "live"

        def __init__(self, settings: Hy3Settings, *, max_attempts: int | None = None):
            self.model = settings.model
            attempts.append(max_attempts)
            self.last_metrics = SimpleNamespace(
                latency_ms=1,
                prompt_tokens=10,
                completion_tokens=10,
                total_tokens=20,
                request_attempts=1,
                http_status=200,
                actual_model="hy3-preview",
            )

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        async def analyze(self, task):
            scenario = next(item for item in suite.scenarios if item.case_id == task.fixture_id)
            return build_golden_draft(
                scenario, annotations[scenario.case_id]
            ).model_dump(mode="json")

        async def repair(self, task, invalid_output, failure_code):
            del invalid_output, failure_code
            return await self.analyze(task)

    monkeypatch.setattr(cli_evals, "Hy3Provider", FakeLiveProvider)
    settings = Hy3Settings(api_key="unit-test-key", base_url="https://hy3.test/v1")

    outcomes = await cli_evals._live_outcomes(suite, settings)

    assert len(outcomes) == 12
    assert attempts == [1] * 12
