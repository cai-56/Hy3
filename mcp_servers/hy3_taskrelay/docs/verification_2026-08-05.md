# Verification record (2026-08-05)

The default checks ran offline from `mcp_servers/hy3_taskrelay`. No test, build, or self-check
command used a production credential or network service.

| Check | Result |
|---|---|
| `uv lock --offline --check` | Pass; lock file unchanged |
| `ruff format --check .` | Pass; 31 Python files |
| `ruff check .` | Pass |
| `mypy` | Pass; 11 source files |
| `pytest` | Pass; 133 tests |
| `python evals/run.py` | Pass; 14/14 offline contract assertions |
| `hy3-taskrelay --selfcheck` | Pass; protocol `2025-11-25`, exactly three tools, three HTTP 200 fixture responses, linked checkpoint/audit/resume artifacts |
| `python -m build` | Pass; wheel and sdist built from the source tree |
| `python -m twine check <artifacts>` | Pass; wheel and sdist |
| clean wheel install | Registry download timed out before an install result; the [2026-07-20 record](verification_2026-07-20.md) has passing clean wheel and sdist installs, and public CI installs the locked project on fresh runners |
| local Markdown links | Pass; root and package Markdown files |
| GIF bounds and privacy regression | Pass; 853×720, 85 frames, 44.5 seconds, no GIF comment or textual private marker |
| `git diff --check` | Pass |

The public workflow runs the same release gates on Ubuntu and Windows with Python 3.10 and 3.14.
The four jobs passed on the last published executable base, commit
`bb69970a154fe126f1ac43bc399d2e5711aba13b`, in
[GitHub Actions run 30978056792](https://github.com/cai-56/Hy3/actions/runs/30978056792).
The [branch workflow](https://github.com/cai-56/Hy3/actions/workflows/hy3-taskrelay.yml?query=branch%3Arhinobird%2Fissue-3-mcp-server)
shows the run for the current PR head.

## Fixed-source self-check

The native-client recording executed source commit
`1a7694ec9451f0300d683d7071e9a44ddc064c65`. This single command installs that exact package
revision and runs the deterministic stdio three-tool chain:

```bash
uvx --from "git+https://github.com/cai-56/Hy3.git@1a7694ec9451f0300d683d7071e9a44ddc064c65#subdirectory=mcp_servers/hy3_taskrelay" hy3-taskrelay --selfcheck
```

## Native-client checkpoint

The 44.5-second [recording](demo/taskrelay_native_clients_2026-08-05.gif) ran CodeBuddy Code 2.124.0
and Codex CLI 0.144.6. CodeBuddy called `taskrelay_create_checkpoint`; Codex called
`taskrelay_audit_checkpoint` and `taskrelay_create_resume_brief`. All three fixture-provider calls
returned HTTP 200 with an exact requested/actual fixture-model match. The audit was `clean` with no
findings, the checkpoint ID survived the client boundary, and resume priorities were `[1, 2]`.

The clients, MCP server, and artifact handoff were real. Local deterministic adapters supplied the
client-model responses and TaskRelay provider responses. This checkpoint does not measure live Hy3
or client-model quality. Raw client streams were not committed; the
[sanitized record](native_clients_2026-08-05.json) contains the publishable fields.

## Online Hy3 gate

The first production smoke call on source
`881c5262783a443abd8b7b07e281bf6afa4de0ab` returned HTTP 402 before a verified response. It was not
retried. No operation completed, `actual_model` is unknown, and the frozen 10-task × 2-repeat live
evaluation was not run. All live metrics remain unavailable. The
[gate record](live_validation_2026-08-05.json) omits the response body, network location, provider
request identifiers, account details, credentials, and local paths.

The package's `src/` runtime is byte-for-byte unchanged from that probe source. Later commits change
tests, evaluation/verification scripts, documentation, and demo evidence only.

The earlier [2026-07-20 verification](verification_2026-07-20.md), live smoke, client artifacts,
and rendered 13.2-second GIF remain historical records. They are not the current online gate or the
current native-client recording.
