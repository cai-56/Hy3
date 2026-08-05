import json
from pathlib import Path

import pytest

from scripts.live_evaluation import (
    aggregate_metrics,
    assert_public_record,
    build_evaluation_record,
    load_dataset,
    run_live_evaluation,
    score_attempt,
    validate_dataset,
)


def test_live_dataset_is_frozen_public_and_large_enough() -> None:
    project_root = Path(__file__).resolve().parents[1]

    dataset, digest = load_dataset(project_root / "evals" / "live_cases.json")

    assert dataset["schema_version"] == "1.0"
    assert dataset["synthetic"] is True
    assert dataset["minimum_repeats"] >= 2
    assert len(dataset["tasks"]) >= 10
    assert len({case["task_id"] for case in dataset["tasks"]}) == len(dataset["tasks"])
    assert len(digest) == 64
    assert all(character in "0123456789abcdef" for character in digest)


@pytest.mark.asyncio
async def test_live_runner_caps_repeats_before_loading_provider_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset_path = Path(__file__).resolve().parents[1] / "evals" / "live_cases.json"
    monkeypatch.delenv("HY3_API_KEY", raising=False)
    monkeypatch.delenv("HY3_BASE_URL", raising=False)
    monkeypatch.delenv("HY3_MODEL", raising=False)

    with pytest.raises(ValueError, match="at most 5"):
        await run_live_evaluation(
            dataset_path,
            repeats=6,
            source_sha="a" * 40,
            confirm_live=True,
        )


@pytest.mark.asyncio
async def test_live_runner_requires_confirmation_at_the_function_boundary() -> None:
    dataset_path = Path(__file__).resolve().parents[1] / "evals" / "live_cases.json"

    with pytest.raises(ValueError, match="confirm_live"):
        await run_live_evaluation(
            dataset_path,
            repeats=2,
            source_sha="a" * 40,
            confirm_live=False,
        )


def test_live_dataset_rejects_additional_evidence_id_collisions() -> None:
    project_root = Path(__file__).resolve().parents[1]
    dataset, _ = load_dataset(project_root / "evals" / "live_cases.json")
    dataset["tasks"][0]["additional_evidence"][0]["evidence_id"] = dataset["tasks"][0][
        "create_input"
    ]["evidence"][0]["evidence_id"]

    with pytest.raises(ValueError, match="additional evidence IDs"):
        validate_dataset(dataset)


def test_attempt_scoring_covers_grounding_and_continuation_metrics() -> None:
    project_root = Path(__file__).resolve().parents[1]
    dataset, _ = load_dataset(project_root / "evals" / "live_cases.json")
    case = dataset["tasks"][1]
    artifacts = {
        "checkpoint": {
            "constraints": [
                {
                    "text": "Do not add a third-party serialization dependency.",
                    "evidence_ids": [],
                }
            ],
            "confirmed_facts": [
                {
                    "text": "The interrupted implementation is CSV-only.",
                    "evidence_ids": ["ev_export_old", "ev_export_test"],
                }
            ],
            "next_steps": [],
        },
        "audit": {
            "findings": [
                {
                    "category": "contradiction",
                    "evidence_ids": ["ev_export_old", "ev_export_new"],
                }
            ]
        },
        "resume": {
            "concise_context": [],
            "next_steps": [
                {
                    "action": "Add newline-delimited JSON coverage.",
                    "validation": "The JSON format test passes.",
                    "evidence_ids": ["ev_export_new"],
                }
            ],
            "blockers": [],
            "do_not": [],
        },
    }

    scores = score_attempt(case, artifacts)

    assert scores["constraint_retention"] == {"passed": 1, "eligible": 1}
    assert scores["fact_citation_accuracy"] == {"passed": 1, "eligible": 1}
    assert scores["contradiction_detection"] == {"passed": 1, "eligible": 1}
    assert scores["next_step_coverage"] == {"passed": 1, "eligible": 1}
    assert scores["unknown_references"]["unknown"] == 0
    assert scores["unknown_references"]["observed"] >= 3


def test_metric_aggregation_reports_rates_failures_and_repeat_variation() -> None:
    def scores(passed: int, observed: int) -> dict[str, dict[str, int]]:
        return {
            "constraint_retention": {"passed": passed, "eligible": 1},
            "fact_citation_accuracy": {"passed": passed, "eligible": 1},
            "contradiction_detection": {"passed": passed, "eligible": 1},
            "next_step_coverage": {"passed": passed, "eligible": 1},
            "unknown_references": {"unknown": 0, "observed": observed},
        }

    successful_tools = {
        tool: {"status": "success", "provider_calls": []}
        for tool in ("checkpoint", "audit", "resume")
    }
    attempts = [
        {
            "task_id": "stable",
            "repeat": 1,
            "tools": successful_tools,
            "scores": scores(1, 4),
            "cross_client_handoff": {"consistent": True},
        },
        {
            "task_id": "stable",
            "repeat": 2,
            "tools": successful_tools,
            "scores": scores(1, 4),
            "cross_client_handoff": {"consistent": True},
        },
        {
            "task_id": "varied",
            "repeat": 1,
            "tools": successful_tools,
            "scores": scores(1, 4),
            "cross_client_handoff": {"consistent": True},
        },
        {
            "task_id": "varied",
            "repeat": 2,
            "tools": {
                "checkpoint": {
                    "status": "failed",
                    "error_type": "Hy3OutputError",
                    "provider_calls": [],
                },
                "audit": {
                    "status": "skipped",
                    "error_type": "dependency_failed",
                    "provider_calls": [],
                },
                "resume": {
                    "status": "skipped",
                    "error_type": "dependency_failed",
                    "provider_calls": [],
                },
            },
            "scores": scores(0, 0),
            "cross_client_handoff": {"consistent": False},
        },
    ]

    summary = aggregate_metrics(attempts)

    assert summary["constraint_retention_rate"] == {
        "passed": 3,
        "eligible": 4,
        "rate": 0.75,
    }
    assert summary["fact_citation_accuracy"]["rate"] == 0.75
    assert summary["unknown_reference_rate"] == {
        "unknown": 0,
        "observed": 12,
        "rate": 0.0,
    }
    assert summary["cross_repeat_consistency"] == {
        "consistent_pairs": 1,
        "eligible_pairs": 2,
        "rate": 0.5,
    }
    assert summary["cross_client_consistency"] == {
        "consistent_handoffs": 3,
        "attempted_handoffs": 4,
        "rate": 0.75,
        "scope": "portable CodeBuddy checkpoint to Codex audit/resume artifact linkage",
    }
    assert [case["tool"] for case in summary["failure_cases"]] == [
        "checkpoint",
        "audit",
        "resume",
    ]
    assert summary["variation_cases"][0]["task_id"] == "varied"


@pytest.mark.parametrize(
    "unsafe_record, sensitive_values",
    [
        ({"endpoint": "https://provider.invalid/v1"}, ()),
        ({"error": "C:\\Users\\Alice\\private.txt"}, ()),
        ({"request_id": "provider-request-123"}, ()),
        ({"note": "prefix-demo-secret-suffix"}, ("demo-secret",)),
    ],
)
def test_public_record_rejects_provider_and_personal_identifiers(
    unsafe_record: dict[str, str], sensitive_values: tuple[str, ...]
) -> None:
    with pytest.raises(ValueError, match="public evaluation record"):
        assert_public_record(unsafe_record, sensitive_values)


def test_public_record_allows_taskrelay_artifact_ids() -> None:
    assert_public_record(
        {
            "source_sha": "a" * 40,
            "checkpoint_id": "cp_0123456789abcdef",
            "resume_id": "resume_0123456789abcdef",
        },
        (),
    )


def test_blocked_stage2_record_does_not_invent_online_results() -> None:
    project_root = Path(__file__).resolve().parents[1]
    record = json.loads(
        (project_root / "docs" / "live_validation_2026-08-05.json").read_text(encoding="utf-8")
    )

    assert record["provider_identity"] == {
        "requested_model": "hy3",
        "actual_model": None,
        "http_status": 402,
        "identity_verified": False,
        "success_rule": "HTTP 200 and exact requested/actual model match",
    }
    assert record["three_tool_smoke"]["verified_provider_calls"] == 0
    assert record["live_evaluation"]["completed_tasks"] == 0
    assert all(value is None for value in record["live_evaluation"]["metrics"].values())
    assert_public_record(record, ())


def test_evaluation_record_pins_source_dataset_model_and_package_identity() -> None:
    dataset = {
        "schema_version": "1.0",
        "synthetic": True,
        "minimum_repeats": 2,
        "tasks": [{"task_id": "stable"}],
    }
    score = {
        "constraint_retention": {"passed": 1, "eligible": 1},
        "fact_citation_accuracy": {"passed": 1, "eligible": 1},
        "contradiction_detection": {"passed": 1, "eligible": 1},
        "next_step_coverage": {"passed": 1, "eligible": 1},
        "unknown_references": {"unknown": 0, "observed": 3},
    }
    provider_call = {
        "http_status": 200,
        "requested_model": "hy3",
        "actual_model": "hy3",
    }
    tools = {
        tool: {"status": "success", "provider_calls": [provider_call]}
        for tool in ("checkpoint", "audit", "resume")
    }
    attempts = [
        {
            "task_id": "stable",
            "repeat": repeat,
            "tools": tools,
            "scores": score,
            "cross_client_handoff": {"consistent": True},
        }
        for repeat in (1, 2)
    ]

    record = build_evaluation_record(
        dataset=dataset,
        dataset_sha256="b" * 64,
        attempts=attempts,
        source_sha="a" * 40,
        evaluation_date="2026-08-05",
        requested_model="hy3",
        package_versions={"hy3-taskrelay": "0.1.0", "mcp": "1.28.1"},
    )

    assert record["record_kind"] == "real_hy3_taskrelay_evaluation"
    assert record["source_sha"] == "a" * 40
    assert record["dataset"] == {
        "sha256": "b" * 64,
        "task_count": 1,
        "repeats": 2,
        "synthetic": True,
    }
    assert record["provider_identity"] == {
        "requested_model": "hy3",
        "actual_models": ["hy3"],
        "verified_response_rule": "HTTP 200 and exact model identity match",
    }
    assert record["package_versions"]["hy3-taskrelay"] == "0.1.0"
    assert len(record["attempts"]) == 2

    attempts[0]["tools"]["checkpoint"]["provider_calls"] = []
    with pytest.raises(ValueError, match="successful tool"):
        build_evaluation_record(
            dataset=dataset,
            dataset_sha256="b" * 64,
            attempts=attempts,
            source_sha="a" * 40,
            evaluation_date="2026-08-05",
            requested_model="hy3",
            package_versions={"hy3-taskrelay": "0.1.0", "mcp": "1.28.1"},
        )
