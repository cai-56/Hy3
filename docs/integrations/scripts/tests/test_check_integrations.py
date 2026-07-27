from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECKER = Path(__file__).resolve().parents[1] / "check_integrations.py"


def _run_checker_with_media(
    filename: str, media_bytes: bytes
) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temporary_directory:
        integrations_root = Path(temporary_directory) / "docs" / "integrations"
        manifest_path = integrations_root / "verification" / "manifest.json"
        media_path = integrations_root / "assets" / "client" / filename
        manifest_path.parent.mkdir(parents=True)
        media_path.parent.mkdir(parents=True)
        media_path.write_bytes(media_bytes)

        manifest = {
            "schema_version": "1.0",
            "task": {"id": "hy3-config-diagnosis-v1"},
            "products": [
                {
                    "name": "Example Client",
                    "category": "web-client",
                    "version": "1.0.0",
                    "verified_on": "2026-07-23",
                    "actual_model": "hy3-preview",
                    "protocol": "openai-compatible-chat-completions",
                    "mode": "online",
                    "first_turn_marker": "HY3_FIRST_TURN_V1",
                    "task_marker": "HY3_TASK_V1",
                    "guide_path": "guides/example.md",
                    "record_path": "verification/records/example.md",
                    "media": [
                        {
                            "path": f"assets/client/{filename}",
                            "sha256": hashlib.sha256(media_bytes).hexdigest(),
                        }
                    ],
                }
            ],
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )

        return subprocess.run(
            [sys.executable, str(CHECKER), "--manifest", str(manifest_path)],
            capture_output=True,
            check=False,
            text=True,
        )


class CheckIntegrationsCliTests(unittest.TestCase):
    def test_rejects_a_product_without_a_category(self) -> None:
        manifest = {
            "schema_version": "1.0",
            "task": {"id": "hy3-config-diagnosis-v1"},
            "products": [{"name": "CodeBuddy Code"}],
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
            )

            result = subprocess.run(
                [sys.executable, str(CHECKER), "--manifest", str(manifest_path)],
                capture_output=True,
                check=False,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("products[0].category: required", result.stderr)

    def test_rejects_a_product_without_verification_metadata(self) -> None:
        manifest = {
            "schema_version": "1.0",
            "task": {"id": "hy3-config-diagnosis-v1"},
            "products": [{"category": "web-client"}],
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
            )

            result = subprocess.run(
                [sys.executable, str(CHECKER), "--manifest", str(manifest_path)],
                capture_output=True,
                check=False,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        for field in (
            "name",
            "version",
            "verified_on",
            "actual_model",
            "protocol",
            "mode",
            "first_turn_marker",
            "task_marker",
            "guide_path",
            "record_path",
            "media",
        ):
            self.assertIn(f"products[0].{field}: required", result.stderr)

    def test_rejects_media_when_sha256_does_not_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            integrations_root = Path(temporary_directory) / "docs" / "integrations"
            manifest_path = integrations_root / "verification" / "manifest.json"
            media_path = integrations_root / "assets" / "client" / "evidence.png"
            manifest_path.parent.mkdir(parents=True)
            media_path.parent.mkdir(parents=True)
            media_path.write_bytes(b"real client screenshot")

            manifest = {
                "schema_version": "1.0",
                "task": {"id": "hy3-config-diagnosis-v1"},
                "products": [
                    {
                        "name": "Example Client",
                        "category": "web-client",
                        "version": "1.0.0",
                        "verified_on": "2026-07-23",
                        "actual_model": "hy3-preview",
                        "protocol": "openai-compatible-chat-completions",
                        "mode": "online",
                        "first_turn_marker": "HY3_FIRST_TURN_V1",
                        "task_marker": "HY3_TASK_V1",
                        "guide_path": "guides/example.md",
                        "record_path": "verification/records/example.md",
                        "media": [
                            {
                                "path": "assets/client/evidence.png",
                                "sha256": "0" * 64,
                            }
                        ],
                    }
                ],
            }
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
            )

            result = subprocess.run(
                [sys.executable, str(CHECKER), "--manifest", str(manifest_path)],
                capture_output=True,
                check=False,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "products[0].media[0].sha256: does not match assets/client/evidence.png",
            result.stderr,
        )

    def test_rejects_jpeg_media_with_a_png_extension(self) -> None:
        result = _run_checker_with_media(
            "evidence.png", b"\xff\xd8\xff\xe0test-jpeg"
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "products[0].media[0].path: .png extension does not match JPEG content",
            result.stderr,
        )

    def test_rejects_png_media_with_a_jpeg_extension(self) -> None:
        result = _run_checker_with_media(
            "evidence.jpg", b"\x89PNG\r\n\x1a\ntest-png"
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "products[0].media[0].path: .jpg extension does not match PNG content",
            result.stderr,
        )

    def test_rejects_gif_media_with_a_png_extension(self) -> None:
        result = _run_checker_with_media("evidence.png", b"GIF89atest-gif")

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "products[0].media[0].path: .png extension does not match GIF content",
            result.stderr,
        )

    def test_rejects_mp4_media_with_a_png_extension(self) -> None:
        result = _run_checker_with_media(
            "evidence.png", b"\x00\x00\x00\x18ftypisomtest-mp4"
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "products[0].media[0].path: .png extension does not match MP4 content",
            result.stderr,
        )

    def test_rejects_media_without_a_recognized_signature(self) -> None:
        result = _run_checker_with_media("evidence.png", b"not-an-image")

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "products[0].media[0].path: content is not recognized as PNG, JPEG, GIF, or MP4",
            result.stderr,
        )

    def test_rejects_media_with_an_unsupported_extension(self) -> None:
        result = _run_checker_with_media(
            "evidence.webp", b"\x89PNG\r\n\x1a\ntest-png"
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "products[0].media[0].path: unsupported media extension .webp",
            result.stderr,
        )

    def test_accepts_matching_png_jpeg_gif_and_mp4_extensions(self) -> None:
        cases = (
            ("evidence.png", b"\x89PNG\r\n\x1a\ntest-png"),
            ("evidence.jpg", b"\xff\xd8\xff\xe0test-jpeg"),
            ("evidence.jpeg", b"\xff\xd8\xff\xe1test-jpeg"),
            ("evidence.gif", b"GIF87atest-gif"),
            ("evidence.mp4", b"\x00\x00\x00\x18ftypisomtest-mp4"),
        )

        for filename, media_bytes in cases:
            with self.subTest(filename=filename):
                result = _run_checker_with_media(filename, media_bytes)
                self.assertNotIn("extension does not match", result.stderr)
                self.assertNotIn("unsupported media extension", result.stderr)
                self.assertNotIn("content is not recognized", result.stderr)

    def test_rejects_references_to_missing_evidence_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            integrations_root = Path(temporary_directory) / "docs" / "integrations"
            manifest_path = integrations_root / "verification" / "manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest = {
                "schema_version": "1.0",
                "task": {"id": "hy3-config-diagnosis-v1"},
                "products": [
                    {
                        "name": "Example Client",
                        "category": "web-client",
                        "version": "1.0.0",
                        "verified_on": "2026-07-23",
                        "actual_model": "hy3-preview",
                        "protocol": "openai-compatible-chat-completions",
                        "mode": "online",
                        "first_turn_marker": "HY3_FIRST_TURN_V1",
                        "task_marker": "HY3_TASK_V1",
                        "guide_path": "guides/missing.md",
                        "record_path": "verification/records/missing.md",
                        "media": [
                            {
                                "path": "assets/client/missing.png",
                                "sha256": "0" * 64,
                            }
                        ],
                    }
                ],
            }
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
            )

            result = subprocess.run(
                [sys.executable, str(CHECKER), "--manifest", str(manifest_path)],
                capture_output=True,
                check=False,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "products[0].guide_path: not found: guides/missing.md", result.stderr
        )
        self.assertIn(
            "products[0].record_path: not found: verification/records/missing.md",
            result.stderr,
        )
        self.assertIn(
            "products[0].media[0].path: not found: assets/client/missing.png",
            result.stderr,
        )
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
