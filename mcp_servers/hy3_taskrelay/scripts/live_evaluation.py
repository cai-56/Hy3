"""Run the frozen public TaskRelay evaluation against the configured real Hy3 model."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import itertools
import json
import re
import subprocess
from dataclasses import asdict
from datetime import date
from importlib.metadata import version
from pathlib import Path
from typing import Any

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
    Evidence,
)
from hy3_taskrelay.service import TaskRelayService

_PRIVATE_KEY = re.compile(r"(?:api.?key|base.?url|endpoint|request.?id)", re.IGNORECASE)
_PERSONAL_PATH = re.compile(r"(?:[A-Za-z]:[\\/]Users[\\/]|/(?:home|Users)/)")
_WEB_URL = re.compile(r"https?://", re.IGNORECASE)
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_DATASET_SHA = re.compile(r"^[0-9a-f]{64}$")
_TASK_ID = re.compile(r"^[a-z0-9][a-z0-9_]{2,63}$")
MAX_EVALUATION_REPEATS = 5


def _nonempty_strings(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
    )


def validate_dataset(dataset: dict[str, Any]) -> None:
    """Fail fast when a frozen task or its explicit scoring contract is malformed."""

    if dataset.get("schema_version") != "1.0" or dataset.get("synthetic") is not True:
        raise ValueError("live evaluation dataset must be public synthetic schema 1.0")
    minimum_repeats = dataset.get("minimum_repeats")
    if (
        not isinstance(minimum_repeats, int)
        or isinstance(minimum_repeats, bool)
        or minimum_repeats < 2
    ):
        raise ValueError("live evaluation requires at least two repeats")
    tasks = dataset.get("tasks")
    if not isinstance(tasks, list) or len(tasks) < 10:
        raise ValueError("live evaluation dataset requires at least ten tasks")
    if any(not isinstance(task, dict) for task in tasks):
        raise ValueError("every live evaluation task must be an object")
    task_ids = [task.get("task_id") for task in tasks]
    if any(not isinstance(task_id, str) or not _TASK_ID.fullmatch(task_id) for task_id in task_ids):
        raise ValueError("every live evaluation task requires a task_id")
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("live evaluation task IDs must be unique")
    for task in tasks:
        create_input = CreateCheckpointInput.model_validate(task["create_input"])
        additional_data = task.get("additional_evidence")
        if not isinstance(additional_data, list):
            raise ValueError("additional_evidence must be a list")
        additional_evidence = [Evidence.model_validate(item) for item in additional_data]
        initial_ids = {item.evidence_id for item in create_input.evidence}
        additional_ids = [item.evidence_id for item in additional_evidence]
        if len(additional_ids) != len(set(additional_ids)) or initial_ids & set(additional_ids):
            raise ValueError("additional evidence IDs must be new and unique")
        continuation_context = task.get("continuation_context")
        if not isinstance(continuation_context, str) or len(continuation_context) > 4_000:
            raise ValueError("continuation_context must be at most 4000 characters")

        expectations = task.get("expectations")
        if not isinstance(expectations, dict):
            raise ValueError("every task requires scoring expectations")
        if set(expectations) != {
            "constraint_phrases",
            "facts",
            "contradiction",
            "next_steps",
        }:
            raise ValueError("scoring expectations must use the documented metric fields")
        constraint_phrases = expectations["constraint_phrases"]
        if not _nonempty_strings(constraint_phrases) or not set(constraint_phrases) <= set(
            create_input.constraints
        ):
            raise ValueError("constraint phrases must be explicit checkpoint input constraints")

        facts = expectations["facts"]
        if not isinstance(facts, list) or not facts:
            raise ValueError("every task requires at least one fact expectation")
        for fact in facts:
            if (
                not isinstance(fact, dict)
                or set(fact) != {"any_keywords", "evidence_ids"}
                or not _nonempty_strings(fact["any_keywords"])
                or not _nonempty_strings(fact["evidence_ids"])
                or not set(fact["evidence_ids"]) <= initial_ids
            ):
                raise ValueError("fact expectations require initial evidence and keyword cues")

        contradiction = expectations["contradiction"]
        known_ids = initial_ids | set(additional_ids)
        if (
            not isinstance(contradiction, dict)
            or set(contradiction) != {"expected", "evidence_ids"}
            or not isinstance(contradiction["expected"], bool)
            or not isinstance(contradiction["evidence_ids"], list)
            or not set(contradiction["evidence_ids"]) <= known_ids
            or (contradiction["expected"] and len(contradiction["evidence_ids"]) < 2)
            or (not contradiction["expected"] and contradiction["evidence_ids"])
        ):
            raise ValueError("contradiction expectations require a valid frozen evidence pair")

        next_steps = expectations["next_steps"]
        if not isinstance(next_steps, list) or not next_steps:
            raise ValueError("every task requires at least one next-step expectation")
        if any(
            not isinstance(step, dict)
            or set(step) != {"any_keywords"}
            or not _nonempty_strings(step["any_keywords"])
            for step in next_steps
        ):
            raise ValueError("next-step expectations require non-empty keyword cues")


def load_dataset(path: Path) -> tuple[dict[str, Any], str]:
    """Load and validate the frozen public dataset and return its byte-level SHA-256."""

    raw = path.read_bytes()
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("live evaluation dataset must be a JSON object")
    validate_dataset(parsed)
    return parsed, hashlib.sha256(raw).hexdigest()


def assert_public_record(record: object, sensitive_values: tuple[str, ...]) -> None:
    """Reject fields or values that would identify a provider request or local user."""

    serialized = json.dumps(record, ensure_ascii=False, sort_keys=True)
    if any(value and value in serialized for value in sensitive_values):
        raise ValueError("public evaluation record contains a sensitive value")

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if _PRIVATE_KEY.search(str(key)):
                    raise ValueError("public evaluation record contains a private field")
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, str):
            if _PERSONAL_PATH.search(value) or _WEB_URL.search(value):
                raise ValueError("public evaluation record contains a private location")
            if any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value):
                raise ValueError("public evaluation record contains terminal control bytes")

    visit(record)


def _references(value: object) -> list[str]:
    if isinstance(value, dict):
        own = value.get("evidence_ids", [])
        references = list(own) if isinstance(own, list) else []
        for item in value.values():
            references.extend(_references(item))
        return references
    if isinstance(value, list):
        references = []
        for item in value:
            references.extend(_references(item))
        return references
    return []


def _contains_any(text: str, keywords: list[str]) -> bool:
    folded = text.casefold()
    return any(keyword.casefold() in folded for keyword in keywords)


def score_attempt(
    case: dict[str, Any], artifacts: dict[str, dict[str, Any]]
) -> dict[str, dict[str, int]]:
    """Score one successful three-tool attempt against public task expectations."""

    expectations = case["expectations"]
    checkpoint = artifacts["checkpoint"]
    audit = artifacts["audit"]
    resume = artifacts["resume"]

    constraint_text = "\n".join(
        str(item.get("text", "")) for item in checkpoint.get("constraints", [])
    )
    constraint_phrases = expectations["constraint_phrases"]
    retained_constraints = sum(
        phrase.casefold() in constraint_text.casefold() for phrase in constraint_phrases
    )

    confirmed_facts = checkpoint.get("confirmed_facts", [])
    fact_expectations = expectations["facts"]
    accurate_facts = 0
    for expected_fact in fact_expectations:
        required_ids = set(expected_fact["evidence_ids"])
        if any(
            _contains_any(str(fact.get("text", "")), expected_fact["any_keywords"])
            and required_ids <= set(fact.get("evidence_ids", []))
            for fact in confirmed_facts
        ):
            accurate_facts += 1

    expected_contradiction = expectations["contradiction"]
    contradiction_findings = [
        finding
        for finding in audit.get("findings", [])
        if finding.get("category") == "contradiction"
    ]
    if expected_contradiction["expected"]:
        required_ids = set(expected_contradiction["evidence_ids"])
        contradiction_passed = any(
            required_ids <= set(finding.get("evidence_ids", []))
            for finding in contradiction_findings
        )
    else:
        contradiction_passed = not contradiction_findings

    next_step_text = "\n".join(
        str(item.get(field, ""))
        for artifact in (checkpoint, resume)
        for item in artifact.get("next_steps", [])
        for field in ("action", "verification", "validation")
    )
    next_step_expectations = expectations["next_steps"]
    covered_next_steps = sum(
        _contains_any(next_step_text, expected_step["any_keywords"])
        for expected_step in next_step_expectations
    )

    known_ids = {
        evidence["evidence_id"]
        for evidence in [
            *case["create_input"]["evidence"],
            *case["additional_evidence"],
        ]
    }
    references = _references(artifacts)
    return {
        "constraint_retention": {
            "passed": retained_constraints,
            "eligible": len(constraint_phrases),
        },
        "fact_citation_accuracy": {
            "passed": accurate_facts,
            "eligible": len(fact_expectations),
        },
        "contradiction_detection": {
            "passed": int(contradiction_passed),
            "eligible": 1,
        },
        "next_step_coverage": {
            "passed": covered_next_steps,
            "eligible": len(next_step_expectations),
        },
        "unknown_references": {
            "unknown": sum(reference not in known_ids for reference in references),
            "observed": len(references),
        },
    }


_SCORE_KEYS = (
    "constraint_retention",
    "fact_citation_accuracy",
    "contradiction_detection",
    "next_step_coverage",
)
_TOOL_KEYS = ("checkpoint", "audit", "resume")


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _signature(attempt: dict[str, Any]) -> dict[str, object]:
    signature: dict[str, object] = {
        f"tool:{tool}": attempt["tools"][tool]["status"] for tool in _TOOL_KEYS
    }
    for key in _SCORE_KEYS:
        score = attempt["scores"][key]
        signature[f"metric:{key}"] = (score["passed"], score["eligible"])
    return signature


def aggregate_metrics(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate transparent quality rates and repeat-level failure/variation cases."""

    summary: dict[str, Any] = {}
    for key in _SCORE_KEYS:
        passed = sum(attempt["scores"][key]["passed"] for attempt in attempts)
        eligible = sum(attempt["scores"][key]["eligible"] for attempt in attempts)
        summary[f"{key}_rate" if key != "fact_citation_accuracy" else key] = {
            "passed": passed,
            "eligible": eligible,
            "rate": _rate(passed, eligible),
        }

    unknown = sum(attempt["scores"]["unknown_references"]["unknown"] for attempt in attempts)
    observed = sum(attempt["scores"]["unknown_references"]["observed"] for attempt in attempts)
    summary["unknown_reference_rate"] = {
        "unknown": unknown,
        "observed": observed,
        "rate": _rate(unknown, observed),
    }

    failures = []
    for attempt in sorted(attempts, key=lambda item: (item["task_id"], item["repeat"])):
        for tool in _TOOL_KEYS:
            tool_record = attempt["tools"][tool]
            if tool_record["status"] != "success":
                failures.append(
                    {
                        "task_id": attempt["task_id"],
                        "repeat": attempt["repeat"],
                        "tool": tool,
                        "status": tool_record["status"],
                        "error_type": tool_record.get("error_type", "unknown"),
                    }
                )

    attempts_by_task: dict[str, list[dict[str, Any]]] = {}
    for attempt in attempts:
        attempts_by_task.setdefault(attempt["task_id"], []).append(attempt)
    consistent_pairs = 0
    eligible_pairs = 0
    variations = []
    for task_id, task_attempts in sorted(attempts_by_task.items()):
        ordered = sorted(task_attempts, key=lambda item: item["repeat"])
        signatures = [_signature(attempt) for attempt in ordered]
        for left, right in itertools.combinations(signatures, 2):
            eligible_pairs += 1
            consistent_pairs += left == right
        dimensions = sorted(
            key
            for key in signatures[0]
            if len({str(signature[key]) for signature in signatures}) > 1
        )
        if dimensions:
            variations.append(
                {
                    "task_id": task_id,
                    "repeats": [attempt["repeat"] for attempt in ordered],
                    "differing_dimensions": dimensions,
                }
            )

    summary["cross_repeat_consistency"] = {
        "consistent_pairs": consistent_pairs,
        "eligible_pairs": eligible_pairs,
        "rate": _rate(consistent_pairs, eligible_pairs),
    }
    summary["failure_cases"] = failures
    summary["variation_cases"] = variations
    return summary


def build_evaluation_record(
    *,
    dataset: dict[str, Any],
    dataset_sha256: str,
    attempts: list[dict[str, Any]],
    source_sha: str,
    evaluation_date: str,
    requested_model: str,
    package_versions: dict[str, str],
    sensitive_values: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build the stable, de-identified public record for a completed live run."""

    if not _FULL_SHA.fullmatch(source_sha):
        raise ValueError("source_sha must be a full lowercase Git SHA")
    if not _DATASET_SHA.fullmatch(dataset_sha256):
        raise ValueError("dataset_sha256 must be a lowercase SHA-256 digest")
    task_ids = [task["task_id"] for task in dataset["tasks"]]
    repeat_values = sorted({attempt["repeat"] for attempt in attempts})
    if not repeat_values or repeat_values != list(range(1, repeat_values[-1] + 1)):
        raise ValueError("attempt repeats must be contiguous and start at one")
    if len(repeat_values) < dataset["minimum_repeats"]:
        raise ValueError("attempts do not satisfy the dataset minimum repeat count")
    expected_pairs = {(task_id, repeat) for task_id in task_ids for repeat in repeat_values}
    actual_pairs = {(attempt["task_id"], attempt["repeat"]) for attempt in attempts}
    if len(attempts) != len(actual_pairs) or actual_pairs != expected_pairs:
        raise ValueError("attempts must cover every dataset task and repeat exactly once")

    actual_models = set()
    for attempt in attempts:
        for tool in _TOOL_KEYS:
            tool_record = attempt["tools"][tool]
            provider_calls = tool_record["provider_calls"]
            if tool_record["status"] == "success" and not provider_calls:
                raise ValueError("every successful tool requires verified provider metadata")
            for call in provider_calls:
                if (
                    call.get("http_status") != 200
                    or call.get("requested_model") != requested_model
                    or call.get("actual_model") != requested_model
                ):
                    raise ValueError("provider metadata does not prove exact Hy3 identity")
                actual_models.add(call["actual_model"])

    ordered_attempts = sorted(attempts, key=lambda item: (item["task_id"], item["repeat"]))
    record = {
        "record_kind": "real_hy3_taskrelay_evaluation",
        "date": evaluation_date,
        "source_sha": source_sha,
        "dataset": {
            "sha256": dataset_sha256,
            "task_count": len(task_ids),
            "repeats": len(repeat_values),
            "synthetic": dataset["synthetic"],
        },
        "package_versions": dict(sorted(package_versions.items())),
        "generation_parameters": {
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "reasoning_effort": REASONING_EFFORT,
        },
        "provider_identity": {
            "requested_model": requested_model,
            "actual_models": sorted(actual_models),
            "verified_response_rule": "HTTP 200 and exact model identity match",
        },
        "attempts": ordered_attempts,
        "metrics": aggregate_metrics(ordered_attempts),
        "record_policy": (
            "Prompts, raw responses, provider request identifiers, credentials, endpoints, "
            "and local paths are omitted."
        ),
    }
    assert_public_record(record, sensitive_values)
    return record


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


def _provider_calls_since(client: Hy3Client, offset: int) -> list[dict[str, object]]:
    return [asdict(item) for item in client.call_metadata[offset:]]


def _failed_scores(case: dict[str, Any]) -> dict[str, dict[str, int]]:
    expectations = case["expectations"]
    return {
        "constraint_retention": {
            "passed": 0,
            "eligible": len(expectations["constraint_phrases"]),
        },
        "fact_citation_accuracy": {
            "passed": 0,
            "eligible": len(expectations["facts"]),
        },
        "contradiction_detection": {"passed": 0, "eligible": 1},
        "next_step_coverage": {
            "passed": 0,
            "eligible": len(expectations["next_steps"]),
        },
        "unknown_references": {"unknown": 0, "observed": 0},
    }


def _failure_record(client: Hy3Client, offset: int, error: Exception) -> dict[str, Any]:
    return {
        "status": "failed",
        "error_type": type(error).__name__,
        "provider_calls": _provider_calls_since(client, offset),
    }


def _skipped_record() -> dict[str, object]:
    return {
        "status": "skipped",
        "error_type": "dependency_failed",
        "provider_calls": [],
    }


async def _run_attempt(
    case: dict[str, Any],
    repeat: int,
    client: Hy3Client,
    service: TaskRelayService,
) -> dict[str, Any]:
    tools: dict[str, dict[str, Any]] = {}
    artifacts: dict[str, dict[str, Any]] = {}

    offset = len(client.call_metadata)
    try:
        checkpoint = await service.create_checkpoint(
            CreateCheckpointInput.model_validate(case["create_input"])
        )
    except Exception as error:
        tools["checkpoint"] = _failure_record(client, offset, error)
        tools["audit"] = _skipped_record()
        tools["resume"] = _skipped_record()
        return {
            "task_id": case["task_id"],
            "repeat": repeat,
            "tools": tools,
            "scores": _failed_scores(case),
        }
    artifacts["checkpoint"] = checkpoint.model_dump(mode="json")
    tools["checkpoint"] = {
        "status": "success",
        "provider_calls": _provider_calls_since(client, offset),
        "artifact_id": checkpoint.checkpoint_id,
        "confirmed_fact_count": len(checkpoint.confirmed_facts),
        "next_step_count": len(checkpoint.next_steps),
    }

    offset = len(client.call_metadata)
    try:
        audit = await service.audit_checkpoint(
            AuditCheckpointInput(
                checkpoint=checkpoint,
                additional_evidence=case["additional_evidence"],
            )
        )
    except Exception as error:
        tools["audit"] = _failure_record(client, offset, error)
        tools["resume"] = _skipped_record()
        return {
            "task_id": case["task_id"],
            "repeat": repeat,
            "tools": tools,
            "scores": _failed_scores(case),
        }
    artifacts["audit"] = audit.model_dump(mode="json")
    tools["audit"] = {
        "status": "success",
        "provider_calls": _provider_calls_since(client, offset),
        "overall_status": audit.overall_status,
        "finding_count": len(audit.findings),
        "finding_categories": sorted(finding.category for finding in audit.findings),
    }

    offset = len(client.call_metadata)
    try:
        resume = await service.create_resume_brief(
            CreateResumeBriefInput(
                checkpoint=checkpoint,
                audit=audit,
                continuation_context=case["continuation_context"],
            )
        )
    except Exception as error:
        tools["resume"] = _failure_record(client, offset, error)
        return {
            "task_id": case["task_id"],
            "repeat": repeat,
            "tools": tools,
            "scores": _failed_scores(case),
        }
    artifacts["resume"] = resume.model_dump(mode="json")
    tools["resume"] = {
        "status": "success",
        "provider_calls": _provider_calls_since(client, offset),
        "artifact_id": resume.resume_id,
        "next_step_count": len(resume.next_steps),
        "priority_order": [step.priority for step in resume.next_steps],
    }
    return {
        "task_id": case["task_id"],
        "repeat": repeat,
        "tools": tools,
        "scores": score_attempt(case, artifacts),
    }


async def run_live_evaluation(
    dataset_path: Path,
    *,
    repeats: int | None = None,
    source_sha: str | None = None,
    confirm_live: bool = False,
) -> dict[str, Any]:
    """Run every frozen task and repeat through the production Hy3 client and service."""

    if not confirm_live:
        raise ValueError("confirm_live must be true before issuing real model requests")
    dataset, dataset_sha256 = load_dataset(dataset_path)
    repeat_count = dataset["minimum_repeats"] if repeats is None else repeats
    if repeat_count < dataset["minimum_repeats"]:
        raise ValueError(
            f"repeats must be at least the dataset minimum ({dataset['minimum_repeats']})"
        )
    if repeat_count > MAX_EVALUATION_REPEATS:
        raise ValueError(f"repeats must be at most {MAX_EVALUATION_REPEATS}")
    project_root = dataset_path.resolve().parents[1]
    verified_source_sha = source_sha or _current_source_sha(project_root)
    if not _FULL_SHA.fullmatch(verified_source_sha):
        raise ValueError("source_sha must be a full 40-character lowercase Git SHA")

    settings = Settings.from_env()
    secret = settings.api_key.get_secret_value()
    assert_public_record(
        {"requested_model": settings.model},
        (secret, settings.base_url),
    )
    client = Hy3Client(settings)
    service = TaskRelayService(client, secret_values=(secret,))
    attempts = []
    for case in dataset["tasks"]:
        for repeat in range(1, repeat_count + 1):
            attempts.append(await _run_attempt(case, repeat, client, service))

    package_versions = {
        name: version(name) for name in ("hy3-taskrelay", "mcp", "httpx", "pydantic")
    }
    return build_evaluation_record(
        dataset=dataset,
        dataset_sha256=dataset_sha256,
        attempts=attempts,
        source_sha=verified_source_sha,
        evaluation_date=date.today().isoformat(),
        requested_model=settings.model,
        package_versions=package_versions,
        sensitive_values=(secret, settings.base_url),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "evals" / "live_cases.json",
    )
    parser.add_argument("--repeats", type=int)
    parser.add_argument("--source-sha", help="Full source Git SHA represented by this run")
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Confirm that this command may issue billable requests to the configured Hy3 model",
    )
    arguments = parser.parse_args()
    if not arguments.confirm_live:
        parser.error("--confirm-live is required; this evaluation issues real model requests")
    record = asyncio.run(
        run_live_evaluation(
            arguments.dataset,
            repeats=arguments.repeats,
            source_sha=arguments.source_sha,
            confirm_live=True,
        )
    )
    print(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
