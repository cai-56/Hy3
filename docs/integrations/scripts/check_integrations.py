from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any


REQUIRED_TASK_FIELDS = (
    "id",
    "prompt_path",
    "prompt_sha256",
    "first_turn_marker",
    "task_marker",
    "actual_model",
)
REQUIRED_PRODUCT_FIELDS = (
    "id",
    "name",
    "category",
    "version",
    "verified_on",
    "actual_model",
    "protocol",
    "mode",
    "first_turn_marker",
    "task_marker",
    "guide_path",
    "record_path",
    "evidence_path",
    "evidence_sha256",
    "installation",
    "configuration",
    "clean_reverification",
    "media",
)
REQUIRED_PROOFS = {
    "product",
    "version",
    "model",
    "first-turn",
    "task-marker",
    "corrected-config",
    "root-causes",
    "validation-step",
    "online-response",
}
SUPPORTED_PROTOCOLS = {"openai-compatible-chat-completions"}
SUPPORTED_MEDIA_KINDS = {"screenshot", "gif", "video"}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_RUNTIME_CLAIMS = {
    "product",
    "version",
    "model",
    "first-turn",
    "task-marker",
    "corrected-config",
    "root-causes",
    "validation-step",
    "online-response",
    "clean-state",
}


def _safe_path(root: Path, relative_path: Any) -> Path | None:
    if not isinstance(relative_path, str) or not relative_path:
        return None
    candidate = Path(relative_path)
    if candidate.is_absolute() or candidate.drive:
        return None
    resolved_root = root.resolve()
    resolved_candidate = (resolved_root / candidate).resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError:
        return None
    return resolved_candidate


def _check_evidence_path(
    errors: list[str],
    *,
    label: str,
    relative_path: Any,
    integrations_root: Path,
) -> Path | None:
    path = _safe_path(integrations_root, relative_path)
    if path is None:
        errors.append(f"{label}: path escapes integrations root")
        return None
    if not path.is_file():
        errors.append(f"{label}: not found: {relative_path}")
        return None
    return path


def _validate_runtime_evidence(
    errors: list[str],
    *,
    product: dict[str, Any],
    product_index: int,
    task: dict[str, Any],
    integrations_root: Path,
) -> None:
    label = f"products[{product_index}].evidence"
    evidence_path = _check_evidence_path(
        errors,
        label=f"products[{product_index}].evidence_path",
        relative_path=product.get("evidence_path"),
        integrations_root=integrations_root,
    )
    if evidence_path is None:
        return

    actual_sha256 = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    if product.get("evidence_sha256") != actual_sha256:
        errors.append(
            f"products[{product_index}].evidence_sha256: "
            f"does not match {product.get('evidence_path')}"
        )
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        errors.append(f"{label}: must be valid UTF-8 JSON")
        return
    if not isinstance(evidence, dict):
        errors.append(f"{label}: top level must be an object")
        return
    if evidence.get("schema_version") != "1.0":
        errors.append(f"{label}.schema_version: must be 1.0")

    expected_fields = {
        "product_id": product.get("id"),
        "product_name": product.get("name"),
        "category": product.get("category"),
        "version": product.get("version"),
        "verified_on": product.get("verified_on"),
        "actual_model": product.get("actual_model"),
        "protocol": product.get("protocol"),
        "mode": product.get("mode"),
        "first_turn_marker": product.get("first_turn_marker"),
        "task_marker": product.get("task_marker"),
        "prompt_sha256": task.get("prompt_sha256"),
        "record_path": product.get("record_path"),
        "clean_reverification_status": (
            product.get("clean_reverification", {}).get("status")
            if isinstance(product.get("clean_reverification"), dict)
            else None
        ),
    }
    for field, expected in expected_fields.items():
        if evidence.get(field) != expected:
            errors.append(f"{label}.{field}: does not match manifest")
    if evidence.get("response_origin") != "actual-online-hy3":
        errors.append(f"{label}.response_origin: must be actual-online-hy3")
    if evidence.get("runtime_surface") not in {
        "native-cli",
        "native-web-ui",
        "native-ide-extension",
        "native-workflow-ui",
    }:
        errors.append(f"{label}.runtime_surface: unsupported")

    claims = evidence.get("observed_claims")
    if not isinstance(claims, dict):
        errors.append(f"{label}.observed_claims: required object")
    else:
        for claim in sorted(REQUIRED_RUNTIME_CLAIMS):
            if claims.get(claim) is not True:
                errors.append(f"{label}.observed_claims.{claim}: must be true")

    expected_media = {
        media.get("path"): media.get("sha256")
        for media in product.get("media", [])
        if isinstance(media, dict)
        and isinstance(media.get("path"), str)
        and isinstance(media.get("sha256"), str)
    }
    evidence_media_value = evidence.get("media_sha256")
    evidence_media = evidence_media_value if isinstance(evidence_media_value, dict) else {}
    if evidence_media != expected_media:
        errors.append(f"{label}.media_sha256: does not match manifest media")


def validate_manifest(
    manifest: dict[str, Any], integrations_root: Path | None = None
) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != "1.0":
        errors.append("schema_version: must be 1.0")

    task = manifest.get("task")
    if not isinstance(task, dict):
        errors.append("task: required object")
        task = {}
    for field in REQUIRED_TASK_FIELDS:
        if not task.get(field):
            errors.append(f"task.{field}: required")

    products = manifest.get("products")
    if not isinstance(products, list):
        errors.append("products: required array")
        products = []
    if len(products) < 7:
        errors.append("products: at least 7 verified products are required")

    product_ids: set[str] = set()
    categories: set[str] = set()
    for index, product_value in enumerate(products):
        if not isinstance(product_value, dict):
            errors.append(f"products[{index}]: must be an object")
            continue
        product = product_value
        for field in REQUIRED_PRODUCT_FIELDS:
            if not product.get(field):
                errors.append(f"products[{index}].{field}: required")

        product_id = product.get("id")
        if isinstance(product_id, str) and product_id:
            if product_id in product_ids:
                errors.append(f"products[{index}].id: product id must be unique")
            product_ids.add(product_id)
        category = product.get("category")
        if isinstance(category, str) and category:
            categories.add(category)

        verified_on = product.get("verified_on")
        if isinstance(verified_on, str):
            try:
                date.fromisoformat(verified_on)
            except ValueError:
                errors.append(f"products[{index}].verified_on: invalid ISO date")

        for marker_field in ("first_turn_marker", "task_marker", "actual_model"):
            task_value = task.get(marker_field)
            product_value = product.get(marker_field)
            if task_value and product_value and task_value != product_value:
                errors.append(
                    f"products[{index}].{marker_field}: does not match task"
                )
        if (
            product.get("protocol")
            and product.get("protocol") not in SUPPORTED_PROTOCOLS
        ):
            errors.append(f"products[{index}].protocol: unsupported")
        if product.get("mode") and product.get("mode") != "online":
            errors.append(f"products[{index}].mode: must be online")

        clean = product.get("clean_reverification")
        if isinstance(clean, dict) and clean.get("status") != "passed":
            errors.append(
                f"products[{index}].clean_reverification.status: must be passed"
            )
        evidence_sha256 = product.get("evidence_sha256")
        if isinstance(evidence_sha256, str) and not SHA256_PATTERN.fullmatch(
            evidence_sha256
        ):
            errors.append(f"products[{index}].evidence_sha256: invalid")

        if integrations_root is not None:
            for field in ("guide_path", "record_path"):
                relative_path = product.get(field)
                if relative_path:
                    _check_evidence_path(
                        errors,
                        label=f"products[{index}].{field}",
                        relative_path=relative_path,
                        integrations_root=integrations_root,
                    )
            if product.get("evidence_path"):
                _validate_runtime_evidence(
                    errors,
                    product=product,
                    product_index=index,
                    task=task,
                    integrations_root=integrations_root,
                )

        proof_union: set[str] = set()
        media_entries = product.get("media")
        if not isinstance(media_entries, list):
            media_entries = []
        for media_index, media_value in enumerate(media_entries):
            if not isinstance(media_value, dict):
                errors.append(
                    f"products[{index}].media[{media_index}]: must be an object"
                )
                continue
            media = media_value
            for field in ("path", "sha256", "kind", "proves"):
                if not media.get(field):
                    errors.append(
                        f"products[{index}].media[{media_index}].{field}: required"
                    )
            if media.get("kind") and media.get("kind") not in SUPPORTED_MEDIA_KINDS:
                errors.append(
                    f"products[{index}].media[{media_index}].kind: unsupported"
                )
            sha256 = media.get("sha256")
            if isinstance(sha256, str) and not SHA256_PATTERN.fullmatch(sha256):
                errors.append(
                    f"products[{index}].media[{media_index}].sha256: invalid"
                )
            proves = media.get("proves")
            if isinstance(proves, list):
                proof_union.update(
                    proof for proof in proves if isinstance(proof, str)
                )

            if integrations_root is None or not media.get("path"):
                continue
            media_path = _check_evidence_path(
                errors,
                label=f"products[{index}].media[{media_index}].path",
                relative_path=media.get("path"),
                integrations_root=integrations_root,
            )
            if media_path is None:
                continue
            actual_sha256 = hashlib.sha256(media_path.read_bytes()).hexdigest()
            if media.get("sha256") != actual_sha256:
                errors.append(
                    f"products[{index}].media[{media_index}].sha256: "
                    f"does not match {media['path']}"
                )

        missing_proofs = sorted(REQUIRED_PROOFS - proof_union)
        for proof in missing_proofs:
            errors.append(f"products[{index}].media.proves: missing {proof}")
        if not {"clean-configuration", "clean-state"} & proof_union:
            errors.append(
                f"products[{index}].media.proves: missing clean-state evidence"
            )

    if len(categories) < 4:
        errors.append("products: at least 4 categories are required")

    if integrations_root is not None and task.get("prompt_path"):
        prompt_path = _check_evidence_path(
            errors,
            label="task.prompt_path",
            relative_path=task.get("prompt_path"),
            integrations_root=integrations_root,
        )
        if prompt_path is not None:
            actual_prompt_sha256 = hashlib.sha256(prompt_path.read_bytes()).hexdigest()
            if task.get("prompt_sha256") != actual_prompt_sha256:
                errors.append("task.prompt_sha256: does not match task.prompt_path")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Hy3 integration evidence.")
    parser.add_argument("--manifest", required=True, type=Path)
    arguments = parser.parse_args()

    try:
        manifest_value = json.loads(arguments.manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"manifest: cannot read valid UTF-8 JSON ({type(exc).__name__})", file=sys.stderr)
        return 1
    if not isinstance(manifest_value, dict):
        print("manifest: top level must be an object", file=sys.stderr)
        return 1

    errors = validate_manifest(manifest_value, arguments.manifest.parent.parent)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
