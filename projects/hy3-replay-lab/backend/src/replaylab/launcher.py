from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

HOST = "127.0.0.1"
BACKEND_PORT = 8000
FRONTEND_PORT = 5173
STARTUP_TIMEOUT_SECONDS = 45.0
POSIX_SIGTERM = getattr(signal, "SIGTERM", 15)
POSIX_SIGKILL = getattr(signal, "SIGKILL", 9)


class LauncherError(RuntimeError):
    """A bounded startup error that is safe to show in the terminal."""


@dataclass(frozen=True, slots=True)
class ProjectLayout:
    root: Path
    backend: Path
    frontend: Path


@dataclass(frozen=True, slots=True)
class ProcessSpec:
    label: str
    command: tuple[str, ...]
    cwd: Path


class ChildProcess(Protocol):
    pid: int

    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


def ensure_within_project(project_root: Path, candidate: Path, *, label: str) -> Path:
    resolved_root = project_root.resolve()
    resolved_candidate = candidate.resolve()
    if not resolved_candidate.is_relative_to(resolved_root):
        raise LauncherError(f"{label} path is outside the project directory")
    return resolved_candidate


def discover_layout() -> ProjectLayout:
    root = Path(__file__).resolve().parents[3]
    backend = ensure_within_project(root, root / "backend", label="backend")
    frontend = ensure_within_project(root, root / "frontend", label="frontend")
    if not backend.joinpath("pyproject.toml").is_file():
        raise LauncherError("backend project file is missing")
    if not frontend.joinpath("package.json").is_file():
        raise LauncherError("frontend package file is missing")
    return ProjectLayout(root=root, backend=backend, frontend=frontend)


def port_is_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def require_ports_available() -> None:
    for port in (BACKEND_PORT, FRONTEND_PORT):
        if not port_is_available(HOST, port):
            raise LauncherError(f"port {port} is already in use")


def process_specs(layout: ProjectLayout) -> tuple[ProcessSpec, ProcessSpec]:
    npm = "npm.cmd" if os.name == "nt" else "npm"
    return (
        ProcessSpec(
            label="backend",
            command=(
                sys.executable,
                "-m",
                "uvicorn",
                "replaylab.main:app",
                "--host",
                HOST,
                "--port",
                str(BACKEND_PORT),
            ),
            cwd=layout.backend,
        ),
        ProcessSpec(
            label="frontend",
            command=(
                npm,
                "run",
                "dev",
                "--",
                "--host",
                HOST,
                "--port",
                str(FRONTEND_PORT),
                "--strictPort",
            ),
            cwd=layout.frontend,
        ),
    )


def child_environment(label: str, source: Mapping[str, str]) -> dict[str, str]:
    if label == "backend":
        return dict(source)
    return {
        key: value
        for key, value in source.items()
        if key.casefold() != "hy3" and not key.casefold().startswith("hy3_")
    }


def spawn_process(spec: ProcessSpec) -> ChildProcess:
    options: dict[str, object] = {
        "cwd": spec.cwd,
        "env": child_environment(spec.label, os.environ),
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return subprocess.Popen(spec.command, **options)  # noqa: S603


def _service_is_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=0.75) as response:  # noqa: S310
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def wait_for_services(children: Sequence[ChildProcess]) -> None:
    services = {
        "backend": f"http://{HOST}:{BACKEND_PORT}/api/health",
        "frontend": f"http://{HOST}:{FRONTEND_PORT}/",
    }
    pending = dict(services)
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while pending:
        for child, label in zip(children, services, strict=True):
            return_code = child.poll()
            if return_code is not None:
                raise LauncherError(
                    f"{label} stopped before health checks passed (exit {return_code})"
                )
        for label, url in tuple(pending.items()):
            if _service_is_ready(url):
                del pending[label]
        if not pending:
            return
        if time.monotonic() >= deadline:
            labels = ", ".join(pending)
            raise LauncherError(f"startup health check timed out: {labels}")
        time.sleep(0.2)


def wait_for_shutdown(children: Sequence[ChildProcess]) -> None:
    labels = ("backend", "frontend")
    while True:
        for child, label in zip(children, labels, strict=True):
            return_code = child.poll()
            if return_code is not None:
                raise LauncherError(f"{label} stopped unexpectedly (exit {return_code})")
        time.sleep(0.25)


def _windows_taskkill_path() -> str | None:
    system_root_value = os.environ.get("SystemRoot")
    if system_root_value:
        system_root = Path(system_root_value).resolve()
        candidate = system_root / "System32" / "taskkill.exe"
        if candidate.is_file():
            return str(candidate)
    return shutil.which("taskkill")


def _wait_after_stop(child: ChildProcess) -> None:
    try:
        child.wait(timeout=5)
        return
    except (OSError, subprocess.TimeoutExpired):
        if child.poll() is not None:
            return
    child.kill()
    try:
        child.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return


def _posix_group_exists(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _stop_posix_process_tree(child: ChildProcess) -> None:
    try:
        os.killpg(child.pid, POSIX_SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 5
    child.poll()
    while _posix_group_exists(child.pid) and time.monotonic() < deadline:
        time.sleep(0.05)
        child.poll()
    if _posix_group_exists(child.pid):
        try:
            os.killpg(child.pid, POSIX_SIGKILL)
        except ProcessLookupError:
            pass
    try:
        child.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return


def stop_process_tree(child: ChildProcess) -> None:
    root_already_exited = child.poll() is not None
    if root_already_exited and os.name == "nt":
        raise LauncherError(
            "Windows process-tree cleanup cannot be verified after the root exited"
        )
    if os.name == "nt":
        taskkill = _windows_taskkill_path()
        if taskkill is None:
            child.terminate()
            _wait_after_stop(child)
            raise LauncherError("Windows process-tree cleanup is unavailable")
        completed = subprocess.run(  # noqa: S603
            (taskkill, "/PID", str(child.pid), "/T", "/F"),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if completed.returncode != 0:
            if child.poll() is None:
                child.terminate()
            _wait_after_stop(child)
            raise LauncherError("Windows process-tree cleanup failed")
        _wait_after_stop(child)
        return
    _stop_posix_process_tree(child)


def run_launcher(
    *,
    layout: ProjectLayout | None = None,
    require_ports: Callable[[], None] = require_ports_available,
    spawn: Callable[[ProcessSpec], ChildProcess] = spawn_process,
    wait_for_services: Callable[[Sequence[ChildProcess]], None] = wait_for_services,
    wait_for_shutdown: Callable[[Sequence[ChildProcess]], None] = wait_for_shutdown,
    stop: Callable[[ChildProcess], None] = stop_process_tree,
) -> None:
    resolved_layout = layout or discover_layout()
    require_ports()
    children: list[ChildProcess] = []
    try:
        for spec in process_specs(resolved_layout):
            try:
                children.append(spawn(spec))
            except OSError:
                raise LauncherError(f"{spec.label} could not be started") from None
        wait_for_services(children)
        print(f"ReplayLab is ready at http://{HOST}:{FRONTEND_PORT}/")
        print("Press Ctrl+C to stop both services.")
        wait_for_shutdown(children)
    except KeyboardInterrupt:
        print("\nStopping ReplayLab...")
    finally:
        cleanup_error: LauncherError | None = None
        for child in reversed(children):
            try:
                stop(child)
            except LauncherError as error:
                cleanup_error = cleanup_error or error
            except OSError:
                cleanup_error = cleanup_error or LauncherError("process cleanup failed")
        if cleanup_error is not None:
            raise cleanup_error from None


def main() -> None:
    try:
        run_launcher()
    except LauncherError as error:
        print(f"ReplayLab launcher failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
