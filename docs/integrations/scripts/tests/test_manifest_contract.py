from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from typing import Any


CHECKER = Path(__file__).resolve().parents[1] / "check_integrations.py"
SPEC = importlib.util.spec_from_file_location("check_integrations", CHECKER)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
validate_manifest = MODULE.validate_manifest


def _product(product_id: str, category: str) -> dict[str, Any]:
    return {
        "id": product_id,
        "name": product_id,
        "category": category,
        "version": "1.0.0",
        "verified_on": "2026-07-23",
        "actual_model": "hy3-preview",
        "protocol": "openai-compatible-chat-completions",
        "mode": "online",
        "first_turn_marker": "HY3_FIRST_TURN_V1",
        "task_marker": "HY3_TASK_V1",
        "guide_path": "guides/example.md",
        "record_path": "verification/records/example.md",
        "evidence_path": "verification/runtime/example.json",
        "evidence_sha256": "0" * 64,
        "installation": {"method": "test"},
        "configuration": {"model": "hy3-preview"},
        "clean_reverification": {"status": "passed", "method": "fresh"},
        "media": [
            {
                "path": "assets/example.png",
                "sha256": "0" * 64,
                "kind": "screenshot",
                "proves": [
                    "product",
                    "version",
                    "model",
                    "online-response",
                    "first-turn",
                    "task-marker",
                    "corrected-config",
                    "root-causes",
                    "validation-step",
                    "clean-configuration",
                ],
            }
        ],
    }


def _manifest() -> dict[str, Any]:
    categories = [
        "cli",
        "web-client",
        "ide-extension",
        "workflow-platform",
        "cli",
        "ide-extension",
        "cli",
    ]
    return {
        "schema_version": "1.0",
        "task": {
            "id": "hy3-config-diagnosis-v1",
            "prompt_path": "verification/task.md",
            "prompt_sha256": "0" * 64,
            "first_turn_marker": "HY3_FIRST_TURN_V1",
            "task_marker": "HY3_TASK_V1",
            "actual_model": "hy3-preview",
        },
        "products": [
            _product(f"client-{index}", category)
            for index, category in enumerate(categories)
        ],
    }


class ManifestContractTests(unittest.TestCase):
    def test_contract_accepts_seven_products_across_four_categories(self) -> None:
        self.assertEqual(validate_manifest(_manifest()), [])

    def test_contract_rejects_duplicate_ids_and_category_coverage(self) -> None:
        manifest = _manifest()
        for product in manifest["products"]:
            product["category"] = "cli"
        manifest["products"][1]["id"] = manifest["products"][0]["id"]

        errors = validate_manifest(manifest)

        self.assertTrue(any("product id must be unique" in error for error in errors))
        self.assertTrue(any("at least 4 categories" in error for error in errors))

    def test_contract_cross_checks_markers_model_protocol_and_mode(self) -> None:
        manifest = _manifest()
        product = manifest["products"][0]
        product["first_turn_marker"] = "wrong"
        product["task_marker"] = "wrong"
        product["actual_model"] = "other-model"
        product["protocol"] = "openai-responses"
        product["mode"] = "offline-fixture"

        errors = validate_manifest(manifest)

        self.assertTrue(
            any("first_turn_marker: does not match task" in error for error in errors)
        )
        self.assertTrue(
            any("task_marker: does not match task" in error for error in errors)
        )
        self.assertTrue(
            any("actual_model: does not match task" in error for error in errors)
        )
        self.assertTrue(any("protocol: unsupported" in error for error in errors))
        self.assertTrue(any("mode: must be online" in error for error in errors))

    def test_contract_cross_checks_machine_readable_runtime_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "integrations"
            task_path = root / "verification" / "task.md"
            guide = root / "guides" / "example.md"
            record = root / "verification" / "records" / "example.md"
            media = root / "assets" / "example.png"
            for path in (task_path, guide, record, media):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"evidence")

            manifest = _manifest()
            task_hash = hashlib.sha256(b"evidence").hexdigest()
            media_hash = hashlib.sha256(b"evidence").hexdigest()
            manifest["task"]["prompt_sha256"] = task_hash
            for index, product in enumerate(manifest["products"]):
                product["media"][0]["sha256"] = media_hash
                evidence_path = root / "verification" / "runtime" / f"{index}.json"
                product["evidence_path"] = f"verification/runtime/{index}.json"
                evidence = {
                    "schema_version": "1.0",
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "category": product["category"],
                    "version": product["version"],
                    "verified_on": product["verified_on"],
                    "actual_model": product["actual_model"],
                    "protocol": product["protocol"],
                    "mode": product["mode"],
                    "first_turn_marker": product["first_turn_marker"],
                    "task_marker": product["task_marker"],
                    "prompt_sha256": task_hash,
                    "record_path": product["record_path"],
                    "clean_reverification_status": "passed",
                    "response_origin": "actual-online-hy3",
                    "runtime_surface": "native-cli",
                    "observed_claims": {
                        claim: True for claim in MODULE.REQUIRED_RUNTIME_CLAIMS
                    },
                    "media_sha256": {
                        product["media"][0]["path"]: media_hash,
                    },
                }
                if index == 0:
                    evidence["actual_model"] = "wrong-model"
                evidence_path.parent.mkdir(parents=True, exist_ok=True)
                evidence_path.write_text(
                    MODULE.json.dumps(evidence),
                    encoding="utf-8",
                )
                product["evidence_sha256"] = hashlib.sha256(
                    evidence_path.read_bytes()
                ).hexdigest()

            errors = validate_manifest(manifest, root)

        self.assertTrue(
            any(
                "products[0].evidence.actual_model: does not match manifest" in error
                for error in errors
            )
        )

    def test_contract_checks_task_hash_and_rejects_escaping_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "integrations"
            task_path = root / "verification" / "task.md"
            guide = root / "guides" / "example.md"
            record = root / "verification" / "records" / "example.md"
            media = root / "assets" / "example.png"
            for path in (task_path, guide, record, media):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"evidence")

            manifest = _manifest()
            manifest["task"]["prompt_sha256"] = hashlib.sha256(b"wrong").hexdigest()
            manifest["products"][0]["guide_path"] = "../outside.md"
            actual_media_hash = hashlib.sha256(b"evidence").hexdigest()
            for product in manifest["products"]:
                product["media"][0]["sha256"] = actual_media_hash

            errors = validate_manifest(manifest, root)

        self.assertTrue(
            any("task.prompt_sha256: does not match" in error for error in errors)
        )
        self.assertTrue(
            any("guide_path: path escapes integrations root" in error for error in errors)
        )
