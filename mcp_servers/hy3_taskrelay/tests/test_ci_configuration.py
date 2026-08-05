"""Static contract for the public TaskRelay CI boundary."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised by the Python 3.10 CI job
    import tomli as tomllib


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parents[1]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "hy3-taskrelay.yml"


def test_python_and_type_checking_boundaries_are_locked() -> None:
    metadata = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lockfile = (PACKAGE_ROOT / "uv.lock").read_text(encoding="utf-8")

    assert metadata["project"]["requires-python"] == ">=3.10,<3.15"
    assert any(
        requirement.startswith("mypy>=")
        for requirement in metadata["project"]["optional-dependencies"]["dev"]
    )
    assert metadata["project"]["scripts"] == {
        "hy3-taskrelay": "hy3_taskrelay.server:main",
        "hy3-taskrelay-mcp": "hy3_taskrelay.server:main",
    }
    assert metadata["tool"]["mypy"]["files"] == ["src/hy3_taskrelay"]
    assert 'requires-python = ">=3.10, <3.15"' in lockfile
    assert 'name = "mypy"' in lockfile


def test_public_ci_covers_supported_boundaries_and_all_release_gates() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    for expected in (
        "ubuntu-latest",
        "windows-latest",
        '"3.10"',
        '"3.14"',
        "uv sync --frozen --extra dev",
        "uv run ruff format --check .",
        "uv run ruff check .",
        "uv run mypy",
        "uv run pytest",
        "uv run python evals/run.py",
        "uv run hy3-taskrelay --selfcheck",
        "uv run python -m build",
        "uv run twine check dist/*",
    ):
        assert expected in workflow

    assert "contents: read" in workflow
    assert "HY3_API_KEY" not in workflow
    assert "HY3_BASE_URL" not in workflow
    assert "secrets." not in workflow
    assert "http://" not in workflow
    assert "https://" not in workflow
