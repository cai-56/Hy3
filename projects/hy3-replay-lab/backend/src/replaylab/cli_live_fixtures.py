from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from replaylab.builtins import FixtureStore
from replaylab.hy3 import (
    SAFE_MODEL_PATTERN,
    Hy3Provider,
    Hy3ProviderError,
    Hy3Settings,
)
from replaylab.resources import default_result_root, fixture_root
from replaylab.schemas import ReplayReport
from replaylab.service import ProviderOutputError, ReplayLabService
from replaylab.validation import OutputValidationError

FIXTURE_IDS = ("coding-loop", "research-grounding")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run both built-in ReplayLab fixtures against the configured Hy3 endpoint."
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    arguments = parser.parse_args()

    fixtures = fixture_root()
    settings = Hy3Settings.from_env()
    run_time = datetime.now(UTC)
    results = asyncio.run(_run_fixtures(fixtures, settings))
    destination = arguments.output_dir or default_result_root()
    destination.mkdir(parents=True, exist_ok=True)
    stem = f"live-fixtures-{run_time.strftime('%Y-%m-%dT%H%M%SZ')}"
    actual_models = sorted(
        {
            str(item["actual_model"])
            for item in results
            if item["actual_model"] is not None
        }
    )
    payload = {
        "date": run_time.date().isoformat(),
        "run_at_utc": run_time.isoformat(),
        "package_version": version("hy3-replay-lab"),
        "provider": "tencent-tokenhub",
        "model": settings.model,
        "requested_model": settings.model,
        "actual_models": actual_models,
        "parameters": {
            "structured_output": "json_schema_strict",
            "temperature": 0,
            "maximum_http_attempts_per_completion": 1,
            "maximum_http_attempts_per_fixture": 2,
            "controlled_repairs": 1,
        },
        "results": results,
    }
    (destination / f"{stem}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (destination / f"{stem}.md").write_text(
        _render_markdown(payload), encoding="utf-8"
    )
    passed = sum(bool(item["passed"]) for item in results)
    print(f"live fixture gate: {passed}/{len(results)} passed")
    print(f"report: {destination / f'{stem}.md'}")
    if passed != len(results):
        raise SystemExit(1)


async def _run_fixtures(
    fixtures: Path, settings: Hy3Settings
) -> list[dict[str, Any]]:
    store = FixtureStore(fixtures)
    results: list[dict[str, Any]] = []
    async with Hy3Provider(settings, max_attempts=1) as provider:
        for fixture_id in FIXTURE_IDS:
            annotation = json.loads(
                (fixtures / fixture_id / "annotation.json").read_text(encoding="utf-8")
            )
            try:
                report = await ReplayLabService(provider).analyze(store.load_task(fixture_id))
                result = _score_fixture_report(annotation, report)
                identity_verified = _provider_identity_is_verified(
                    report.metadata, settings.model
                )
                result.update(
                    {
                        "latency_ms": report.metadata.latency_ms or 0,
                        "prompt_tokens": report.metadata.prompt_tokens or 0,
                        "completion_tokens": report.metadata.completion_tokens or 0,
                        "total_tokens": report.metadata.total_tokens or 0,
                        "request_attempts": report.metadata.request_attempts or 0,
                        "requested_model": report.metadata.requested_model,
                        "actual_model": report.metadata.actual_model,
                        "http_status": report.metadata.http_status,
                        "provider_identity_verified": identity_verified,
                        "error_code": (
                            None if identity_verified else "provider_identity_unverified"
                        ),
                    }
                )
                result["passed"] = bool(result["passed"] and identity_verified)
                results.append(result)
            except Hy3ProviderError as error:
                metrics = provider.last_metrics
                results.append(
                    _failed_result(
                        fixture_id,
                        annotation["first_divergence_step_id"],
                        "provider_request_failed",
                        requested_model=settings.model,
                        actual_model=metrics.actual_model,
                        http_status=error.status_code or metrics.http_status,
                        metrics=metrics,
                    )
                )
            except (ProviderOutputError, OutputValidationError):
                metrics = provider.last_metrics
                results.append(
                    _failed_result(
                        fixture_id,
                        annotation["first_divergence_step_id"],
                        "structured_output_rejected",
                        requested_model=settings.model,
                        actual_model=metrics.actual_model,
                        http_status=metrics.http_status,
                        metrics=metrics,
                    )
                )
    return results


def _provider_identity_is_verified(metadata: Any, configured_model: str) -> bool:
    actual_model = getattr(metadata, "actual_model", None)
    return bool(
        getattr(metadata, "requested_model", None) == configured_model
        and isinstance(actual_model, str)
        and SAFE_MODEL_PATTERN.fullmatch(actual_model)
        and getattr(metadata, "http_status", None) == 200
    )


def _score_fixture_report(
    annotation: dict[str, Any], report: ReplayReport
) -> dict[str, Any]:
    gates = [item.validation_gate for item in report.replay_plan.actions]
    gates.extend(report.replay_plan.stop_conditions)
    gate_criteria = {item for gate in gates for item in gate.criterion_ids}
    required_criteria = set(annotation["related_criterion_ids"])
    cited_evidence = set(report.finding.evidence_ids)
    required_evidence = set(annotation["related_evidence_ids"])
    predicted_rerun = set(report.replay_plan.rerun_step_ids)
    expected_rerun = set(annotation["minimum_rerun_step_ids"])

    required_gates = annotation["required_validation_gates"]
    gate_hits = sum(
        any(
            set(required["criterion_ids"]).issubset(gate.criterion_ids)
            and set(required["evidence_ids"]).issubset(gate.evidence_ids)
            for gate in gates
        )
        for required in required_gates
    )
    dangerous_suggestion = any(
        _normalized_text(recommendation) in _normalized_text(action.action)
        for action in report.replay_plan.actions
        for recommendation in annotation["dangerous_recommendations"]
    )
    first_divergence_correct = (
        report.finding.first_divergence_step_id
        == annotation["first_divergence_step_id"]
    )
    constraint_preservation = _set_recall(gate_criteria, required_criteria)
    evidence_coverage = _set_recall(cited_evidence, required_evidence)
    replay_precision = _set_precision(predicted_rerun, expected_rerun)
    replay_recall = _set_recall(predicted_rerun, expected_rerun)
    gate_coverage = gate_hits / len(required_gates) if required_gates else 1.0
    passed = all(
        (
            first_divergence_correct,
            constraint_preservation == 1,
            evidence_coverage == 1,
            replay_precision == 1,
            replay_recall == 1,
            gate_coverage == 1,
            not dangerous_suggestion,
        )
    )
    return {
        "fixture_id": annotation["fixture_id"],
        "passed": passed,
        "structured_success": True,
        "first_divergence_correct": first_divergence_correct,
        "expected_first_divergence_step_id": annotation["first_divergence_step_id"],
        "actual_first_divergence_step_id": report.finding.first_divergence_step_id,
        "constraint_preservation": constraint_preservation,
        "required_evidence_coverage": evidence_coverage,
        "replay_precision": replay_precision,
        "replay_recall": replay_recall,
        "validation_gate_coverage": gate_coverage,
        "dangerous_suggestion": dangerous_suggestion,
    }


def _normalized_text(value: str) -> str:
    return "".join(character.casefold() for character in value if character.isalnum())


def _set_precision(predicted: set[str], expected: set[str]) -> float:
    if not predicted:
        return 1.0 if not expected else 0.0
    return len(predicted & expected) / len(predicted)


def _set_recall(predicted: set[str], expected: set[str]) -> float:
    if not expected:
        return 1.0
    return len(predicted & expected) / len(expected)


def _failed_result(
    fixture_id: str,
    expected_first_divergence_step_id: str,
    error_code: str,
    *,
    requested_model: str,
    actual_model: str | None,
    http_status: int | None,
    metrics: Any,
) -> dict[str, Any]:
    return {
        "fixture_id": fixture_id,
        "passed": False,
        "structured_success": False,
        "first_divergence_correct": False,
        "expected_first_divergence_step_id": expected_first_divergence_step_id,
        "actual_first_divergence_step_id": None,
        "constraint_preservation": 0,
        "required_evidence_coverage": 0,
        "replay_precision": 0,
        "replay_recall": 0,
        "validation_gate_coverage": 0,
        "dangerous_suggestion": None,
        "latency_ms": metrics.latency_ms,
        "prompt_tokens": metrics.prompt_tokens,
        "completion_tokens": metrics.completion_tokens,
        "total_tokens": metrics.total_tokens,
        "request_attempts": metrics.request_attempts,
        "requested_model": requested_model,
        "actual_model": actual_model,
        "http_status": http_status,
        "provider_identity_verified": False,
        "error_code": error_code,
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Live Hy3 fixture gate",
        "",
        f"- Date: {payload['date']}",
        f"- Package: `{payload['package_version']}`",
        f"- Provider: `{payload['provider']}`",
        f"- Requested model: `{payload['requested_model']}`",
        "- HTTP budget: one attempt per completion, with at most one controlled repair",
        "- Input: the two public synthetic built-in fixtures",
        "- Validation: strict schema, reference closure, deterministic replay rules, "
        "and human annotations",
        "",
        "| Fixture | Gate | First step | Requested → actual | HTTP | Criteria | Evidence | "
        "Replay P/R | Gates | Unsafe | Latency | Tokens | Attempts | Error |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | "
        "---: | ---: | --- |",
    ]
    for item in payload["results"]:
        first_step = item["actual_first_divergence_step_id"] or "-"
        actual_model = item["actual_model"] or "-"
        http_status = item["http_status"] or "-"
        error = item["error_code"] or "-"
        unsafe = (
            "unknown"
            if item["dangerous_suggestion"] is None
            else "yes"
            if item["dangerous_suggestion"]
            else "no"
        )
        lines.append(
            f"| `{item['fixture_id']}` | {'pass' if item['passed'] else 'fail'} | "
            f"`{first_step}` | `{item['requested_model']}` → `{actual_model}` | "
            f"{http_status} | {item['constraint_preservation']:.2f} | "
            f"{item['required_evidence_coverage']:.2f} | "
            f"{item['replay_precision']:.2f}/{item['replay_recall']:.2f} | "
            f"{item['validation_gate_coverage']:.2f} | "
            f"{unsafe} | "
            f"{item['latency_ms']} ms | {item['total_tokens']} | "
            f"{item['request_attempts']} | `{error}` |"
        )
    lines.extend(
        [
            "",
            "No key, request ID, account data, raw prompt, or hidden reasoning is stored.",
            "",
        ]
    )
    return "\n".join(lines)
