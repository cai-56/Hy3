import tomllib
from pathlib import Path

import pytest

from replaylab import launcher
from replaylab.launcher import LauncherError, discover_layout, ensure_within_project


def test_launcher_rejects_a_path_outside_the_project() -> None:
    project_root = Path("C:/replaylab/project")
    escaped_path = Path("C:/replaylab/outside")

    with pytest.raises(LauncherError, match="outside the project directory"):
        ensure_within_project(project_root, escaped_path, label="frontend")


def test_launcher_discovers_the_bundled_backend_and_frontend() -> None:
    layout = discover_layout()

    assert layout.root.name == "hy3-replay-lab"
    assert layout.backend.joinpath("pyproject.toml").is_file()
    assert layout.frontend.joinpath("package.json").is_file()


def test_launcher_reports_an_occupied_port_before_startup(monkeypatch) -> None:
    monkeypatch.setattr(
        launcher,
        "port_is_available",
        lambda host, port: port != 8000,
    )

    with pytest.raises(LauncherError, match=r"port 8000 is already in use"):
        launcher.require_ports_available()


def test_launcher_cleans_the_backend_when_frontend_startup_fails() -> None:
    backend_child = object()
    stopped: list[object] = []

    def spawn(spec: launcher.ProcessSpec) -> object:
        if spec.label == "backend":
            return backend_child
        raise OSError("private operating-system detail")

    with pytest.raises(LauncherError, match="frontend could not be started") as caught:
        launcher.run_launcher(
            layout=discover_layout(),
            require_ports=lambda: None,
            spawn=spawn,
            wait_for_services=lambda children: None,
            wait_for_shutdown=lambda children: None,
            stop=lambda child: stopped.append(child),
        )

    assert stopped == [backend_child]
    assert "private operating-system detail" not in str(caught.value)


def test_backend_exposes_the_one_command_launcher() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    payload = tomllib.loads(backend_root.joinpath("pyproject.toml").read_text("utf-8"))

    assert payload["project"]["scripts"]["replaylab-start"] == "replaylab.launcher:main"


def test_console_error_does_not_mislabel_shutdown_cleanup_as_startup_failure(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        launcher,
        "run_launcher",
        lambda: (_ for _ in ()).throw(LauncherError("process cleanup failed")),
    )

    with pytest.raises(SystemExit, match="1"):
        launcher.main()

    assert capsys.readouterr().err == (
        "ReplayLab launcher failed: process cleanup failed\n"
    )


def test_frontend_child_never_receives_hy3_credentials() -> None:
    source = {
        "PATH": "C:/tools",
        "Hy3": "standalone-secret",
        "HY3_API_KEY": "unit-test-key",
        "hy3_base_url": "https://provider.invalid/v1",
        "HY3_MODEL": "hy3-preview",
    }

    backend = launcher.child_environment("backend", source)
    frontend = launcher.child_environment("frontend", source)

    assert backend == source
    assert frontend == {"PATH": "C:/tools"}


def test_process_specs_are_fixed_to_the_local_source_workspace() -> None:
    backend, frontend = launcher.process_specs(discover_layout())

    assert "replaylab.main:app" in backend.command
    assert backend.command[-4:] == ("--host", "127.0.0.1", "--port", "8000")
    assert frontend.command[-5:] == (
        "--host",
        "127.0.0.1",
        "--port",
        "5173",
        "--strictPort",
    )
    assert "install" not in backend.command + frontend.command


def test_launcher_stops_both_children_after_ctrl_c() -> None:
    children = [object(), object()]
    spawned = iter(children)
    ready_with: list[object] = []
    stopped: list[object] = []

    def interrupt(active_children: object) -> None:
        del active_children
        raise KeyboardInterrupt

    launcher.run_launcher(
        layout=discover_layout(),
        require_ports=lambda: None,
        spawn=lambda spec: next(spawned),
        wait_for_services=lambda active: ready_with.extend(active),
        wait_for_shutdown=interrupt,
        stop=lambda child: stopped.append(child),
    )

    assert ready_with == children
    assert stopped == list(reversed(children))


def test_health_failure_stops_every_started_child() -> None:
    children = [object(), object()]
    spawned = iter(children)
    stopped: list[object] = []

    def fail_health(active_children: object) -> None:
        del active_children
        raise LauncherError("startup health check timed out: frontend")

    with pytest.raises(LauncherError, match="health check timed out"):
        launcher.run_launcher(
            layout=discover_layout(),
            require_ports=lambda: None,
            spawn=lambda spec: next(spawned),
            wait_for_services=fail_health,
            wait_for_shutdown=lambda active: None,
            stop=lambda child: stopped.append(child),
        )

    assert stopped == list(reversed(children))


def test_windows_cleanup_reports_unavailable_tree_kill(monkeypatch) -> None:
    class Child:
        pid = 42

        def __init__(self) -> None:
            self.terminated = False
            self.killed = False

        def poll(self) -> int | None:
            return None

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.killed = True

        def wait(self, timeout: float | None = None) -> int:
            del timeout
            return 0

    child = Child()
    monkeypatch.setattr(launcher.os, "name", "nt")
    monkeypatch.setattr(launcher.shutil, "which", lambda executable: None)
    monkeypatch.setattr(launcher, "_windows_taskkill_path", lambda: None, raising=False)

    with pytest.raises(LauncherError, match="process-tree cleanup is unavailable"):
        launcher.stop_process_tree(child)

    assert child.terminated is True
    assert child.killed is False


def test_windows_taskkill_path_uses_the_system_directory(monkeypatch) -> None:
    system_root = Path("C:/WindowsRoot")
    taskkill = system_root / "System32" / "taskkill.exe"
    monkeypatch.setenv("SystemRoot", str(system_root))
    monkeypatch.setattr(launcher.shutil, "which", lambda executable: None)
    monkeypatch.setattr(
        launcher.Path,
        "is_file",
        lambda candidate: candidate.name.casefold() == "taskkill.exe",
    )

    assert launcher._windows_taskkill_path() == str(taskkill.resolve())


def test_launcher_attempts_every_cleanup_when_one_child_cleanup_fails() -> None:
    children = [object(), object()]
    spawned = iter(children)
    stopped: list[object] = []

    def interrupt(active_children: object) -> None:
        del active_children
        raise KeyboardInterrupt

    def stop(child: object) -> None:
        stopped.append(child)
        if child is children[1]:
            raise LauncherError("Windows process-tree cleanup failed")

    with pytest.raises(LauncherError, match="process-tree cleanup failed"):
        launcher.run_launcher(
            layout=discover_layout(),
            require_ports=lambda: None,
            spawn=lambda spec: next(spawned),
            wait_for_services=lambda active: None,
            wait_for_shutdown=interrupt,
            stop=stop,
        )

    assert stopped == list(reversed(children))


def test_windows_cleanup_never_claims_a_tree_after_the_root_already_exited(
    monkeypatch,
) -> None:
    class ExitedChild:
        pid = 42

        def poll(self) -> int | None:
            return 1

        def terminate(self) -> None:
            raise AssertionError("an exited root cannot be terminated")

        def kill(self) -> None:
            raise AssertionError("an exited root cannot be killed")

        def wait(self, timeout: float | None = None) -> int:
            del timeout
            return 1

    monkeypatch.setattr(launcher.os, "name", "nt")

    with pytest.raises(LauncherError, match="cannot be verified after the root exited"):
        launcher.stop_process_tree(ExitedChild())


def test_posix_cleanup_kills_remaining_group_members_after_the_grace_period(
    monkeypatch,
) -> None:
    class ExitedLeader:
        pid = 42

        def poll(self) -> int | None:
            return 0

        def terminate(self) -> None:
            raise AssertionError("POSIX cleanup signals the process group")

        def kill(self) -> None:
            raise AssertionError("POSIX cleanup signals the process group")

        def wait(self, timeout: float | None = None) -> int:
            del timeout
            return 0

    signals: list[int] = []
    clock = iter((0.0, 6.0))
    monkeypatch.setattr(launcher.os, "name", "posix")
    monkeypatch.setattr(
        launcher.os,
        "killpg",
        lambda process_group, sent: signals.append(sent),
        raising=False,
    )
    monkeypatch.setattr(
        launcher, "_posix_group_exists", lambda process_group: True, raising=False
    )
    monkeypatch.setattr(launcher.time, "monotonic", lambda: next(clock))

    launcher.stop_process_tree(ExitedLeader())

    assert signals == [launcher.POSIX_SIGTERM, launcher.POSIX_SIGKILL]
