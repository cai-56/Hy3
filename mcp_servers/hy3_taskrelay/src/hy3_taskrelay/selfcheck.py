"""Bounded offline verification for the installed TaskRelay stdio server."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, TextIO, cast

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

from hy3_taskrelay.schemas import AuditResult, Checkpoint, ResumeBrief

_MODEL = "hy3-selfcheck"
_API_KEY = "selfcheck-only-key"
_EXPECTED_TOOLS = [
    "taskrelay_audit_checkpoint",
    "taskrelay_create_checkpoint",
    "taskrelay_create_resume_brief",
]
_PROVIDER_RESPONSES: tuple[dict[str, object], ...] = (
    {
        "goal": "Verify the offline TaskRelay handoff.",
        "confirmed_facts": [
            {
                "text": "The synthetic regression is reproduced.",
                "evidence_ids": ["ev_selfcheck"],
            }
        ],
        "constraints": [],
        "decisions": [],
        "open_questions": [],
        "next_steps": [
            {
                "action": "Apply the bounded synthetic fix.",
                "verification": "The synthetic regression test passes.",
                "evidence_ids": ["ev_selfcheck"],
            }
        ],
    },
    {"overall_status": "clean", "findings": []},
    {
        "concise_context": [
            {
                "text": "The synthetic regression is ready for a bounded fix.",
                "evidence_ids": ["ev_selfcheck"],
            }
        ],
        "next_steps": [
            {
                "priority": 1,
                "action": "Apply the bounded synthetic fix.",
                "validation": "The synthetic regression test passes.",
                "evidence_ids": ["ev_selfcheck"],
            }
        ],
        "blockers": [],
        "do_not": [],
    },
)


class _SelfcheckFailure(RuntimeError):
    """Internal failure whose details must not cross the CLI boundary."""


@dataclass
class _ProviderState:
    responses: tuple[dict[str, object], ...] = _PROVIDER_RESPONSES
    http_statuses: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def take_response(self) -> dict[str, object] | None:
        with self.lock:
            index = len(self.http_statuses)
            if index >= len(self.responses):
                self.errors.append("unexpected provider call")
                return None
            self.http_statuses.append(200)
            return self.responses[index]


class _ProviderServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, state: _ProviderState) -> None:
        self.state = state
        super().__init__(("127.0.0.1", 0), _ProviderHandler)

    def handle_error(self, request: object, client_address: object) -> None:
        del request, client_address
        self.state.errors.append("provider handler failed")


class _ProviderHandler(BaseHTTPRequestHandler):
    server: _ProviderServer

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def do_POST(self) -> None:
        try:
            length_text = self.headers.get("Content-Length", "")
            if not length_text.isdigit() or int(length_text) > 1_000_000:
                self._send_error()
                return
            payload = json.loads(self.rfile.read(int(length_text)).decode("utf-8"))
            if (
                self.path != "/v1/chat/completions"
                or self.headers.get("Authorization") != f"Bearer {_API_KEY}"
                or not isinstance(payload, dict)
                or payload.get("model") != _MODEL
                or not isinstance(payload.get("messages"), list)
            ):
                self.server.state.errors.append("invalid provider request")
                self._send_error()
                return
            response_payload = self.server.state.take_response()
            if response_payload is None:
                self._send_error()
                return
            self._send_json(
                200,
                {
                    "model": _MODEL,
                    "choices": [
                        {"message": {"content": json.dumps(response_payload, ensure_ascii=False)}}
                    ],
                },
            )
        except (UnicodeDecodeError, ValueError, TypeError):
            self.server.state.errors.append("invalid provider payload")
            self._send_error()

    def _send_error(self) -> None:
        self._send_json(400, {"error": {"message": "invalid selfcheck request"}})

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@contextmanager
def _loopback_provider() -> Iterator[tuple[_ProviderServer, str]]:
    state = _ProviderState()
    server = _ProviderServer(state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = cast(tuple[str, int], server.server_address)[1]
        yield server, f"http://127.0.0.1:{port}/v1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _structured(result: CallToolResult) -> dict[str, Any]:
    if result.isError or result.structuredContent is None:
        raise _SelfcheckFailure("tool call failed")
    return result.structuredContent


async def _run_stdio_chain(base_url: str) -> dict[str, object]:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "hy3_taskrelay"],
        env={
            "HY3_API_KEY": _API_KEY,
            "HY3_BASE_URL": base_url,
            "HY3_MODEL": _MODEL,
            "PYTHONUTF8": "1",
        },
        encoding="utf-8",
        encoding_error_handler="strict",
    )
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as child_stderr:
        async with (
            stdio_client(parameters, errlog=cast(TextIO, child_stderr)) as (
                read_stream,
                write_stream,
            ),
            ClientSession(read_stream, write_stream) as session,
        ):
            initialized = await session.initialize()
            listed = await session.list_tools()
            tool_names = sorted(tool.name for tool in listed.tools)
            if tool_names != _EXPECTED_TOOLS:
                raise _SelfcheckFailure("unexpected tool list")

            checkpoint_result = await session.call_tool(
                "taskrelay_create_checkpoint",
                {
                    "goal": "Verify the offline TaskRelay handoff.",
                    "session_material": "A synthetic regression was reproduced before handoff.",
                    "constraints": ["Keep the check offline and read-only."],
                    "decisions": ["Use one synthetic evidence item."],
                    "evidence": [
                        {
                            "evidence_id": "ev_selfcheck",
                            "content": "The synthetic regression test currently fails.",
                            "source": "selfcheck fixture",
                        }
                    ],
                },
                read_timeout_seconds=timedelta(seconds=15),
            )
            checkpoint = Checkpoint.model_validate(_structured(checkpoint_result))

            audit_result = await session.call_tool(
                "taskrelay_audit_checkpoint",
                {"checkpoint": checkpoint.model_dump(mode="json")},
                read_timeout_seconds=timedelta(seconds=15),
            )
            audit = AuditResult.model_validate(_structured(audit_result))

            resume_result = await session.call_tool(
                "taskrelay_create_resume_brief",
                {
                    "checkpoint": checkpoint.model_dump(mode="json"),
                    "audit": audit.model_dump(mode="json"),
                },
                read_timeout_seconds=timedelta(seconds=15),
            )
            resume = ResumeBrief.model_validate(_structured(resume_result))

        child_stderr.seek(0)
        if child_stderr.read():
            raise _SelfcheckFailure("stdio server wrote diagnostics")
    if audit.checkpoint_id != checkpoint.checkpoint_id:
        raise _SelfcheckFailure("audit linkage failed")
    if audit.overall_status != "clean" or audit.findings:
        raise _SelfcheckFailure("audit result failed")
    if resume.checkpoint_id != checkpoint.checkpoint_id:
        raise _SelfcheckFailure("resume linkage failed")
    priorities = [step.priority for step in resume.next_steps]
    if priorities != [1]:
        raise _SelfcheckFailure("resume priority failed")

    return {
        "status": "passed",
        "transport": "stdio",
        "protocol_version": initialized.protocolVersion,
        "tools": tool_names,
        "calls": [
            {
                "tool": "taskrelay_create_checkpoint",
                "status": "passed",
                "checkpoint_id": checkpoint.checkpoint_id,
            },
            {
                "tool": "taskrelay_audit_checkpoint",
                "status": "passed",
                "overall_status": audit.overall_status,
                "finding_count": len(audit.findings),
            },
            {
                "tool": "taskrelay_create_resume_brief",
                "status": "passed",
                "resume_id": resume.resume_id,
                "priority_order": priorities,
            },
        ],
    }


def run_selfcheck() -> dict[str, object]:
    """Run a real stdio workflow against a process-local HTTP provider."""

    with _loopback_provider() as (server, base_url):
        result = asyncio.run(_run_stdio_chain(base_url))
        if server.state.errors or server.state.http_statuses != [200, 200, 200]:
            raise _SelfcheckFailure("provider verification failed")
        result["provider_http_statuses"] = list(server.state.http_statuses)
        return result


def selfcheck_main() -> int:
    """Print one bounded result without exposing local configuration or paths."""

    try:
        result = run_selfcheck()
        output = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if len(output.encode("utf-8")) >= 4_096:
            raise _SelfcheckFailure("result exceeded output bound")
        status = 0
    except Exception:
        output = '{"error":"offline selfcheck failed","status":"failed"}'
        status = 1
    print(output)
    return status
