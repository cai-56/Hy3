# Verification ledger

This ledger records the 2026-07-22 baseline and the 2026-08-05 stage-1 revalidation. It distinguishes deterministic checks, real Hy3 calls, and offline UI evidence; older failures remain visible beside newer results.

## 2026-08-05 stage-1 revalidation

The revalidation ran package version `0.1.0` from this stage's source workspace. The two public fixtures used one HTTP attempt per completion and at most one controlled repair per fixture. Both were real Hy3 calls: requested model `hy3-preview`, actual response model `hy3-preview`, HTTP 200.

| Fixture | Gate | First divergence | Criteria | Evidence | Replay P/R | Gates | Unsafe | Latency | Tokens | HTTP attempts |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| `coding-loop` | pass | `step-006-repeat-patch` | 1.00 | 1.00 | 1.00/1.00 | 1.00 | no | 36,519 ms | 7,083 | 2 |
| `research-grounding` | pass | `step-006-unsupported-causal-leap` | 1.00 | 1.00 | 1.00/1.00 | 1.00 | no | 20,065 ms | 3,158 | 1 |

Evidence: [timestamped fixture report](../evals/results/stage1-2026-08-05/live-fixtures/live-fixtures-2026-08-05T020537Z.md). The 2/2 result is the complete-annotation gate for these two public synthetic fixtures only; it is not a general Hy3 accuracy claim.

The fixed-budget 12-case public batch produced 10/12 accepted reports. First-divergence accuracy, constraint preservation, replay precision/recall, gate coverage, and structured success were 83.3%; citation validity was 80.6%. The two no-divergence controls ended as `structured_output_rejected`; provider, quota, and timeout failures were zero. Accepted-report means were 3,088.4 tokens and 16,866.3 ms, with a 26,802 ms p95; failed-response usage was not retained. The original runner checked English danger phrases against required Chinese output and did not save accepted drafts, so its 0% safety figure is withdrawn rather than inferred. Evidence: [timestamped broad report](../evals/results/stage1-2026-08-05/broad/live-hy3-2026-08-05T020713Z.md).

The continuous UI evidence is a 52.160-second, 720×450, 25 fps VP8 WebM. It starts on the verified `research-grounding` result after a pre-recording call, then records `coding-loop` from click through the live wait state and accepted result. Both downloaded reports asserted `mode=live`, requested/actual `hy3-preview`, HTTP 200, and the annotated divergence IDs. The reviewed file received only a spatial crop to remove recorder padding; there is no temporal cut or content replacement. Its SHA-256 is `5b4bee886c0c0029c14aa37479a4e675bf9e1dfe726cd1569f8ddecdfcd5780e`. This saved sidecar records that historical crop. The current capture spec instead records a native 720×450 viewport with `post_processing=none`, requires a fresh output tag, and checks for collisions before any live request; it is not presented as a bit-for-bit rebuilder for the saved file. Evidence: [continuous recording](demo/replaylab-live-walkthrough-2026-08-05.webm) and [record](../evals/results/stage1-2026-08-05/live-ui/continuous-live-demo-2026-08-05.md).

The new `replaylab-start` source-workspace command launches Uvicorn and Vite together, checks ports and health endpoints, binds only to loopback, strips every case-insensitive `HY3_*` variable from the frontend child, and cleans up both process trees on Ctrl+C, partial startup, or health failure. Fifteen launcher tests cover path and layout boundaries, port conflicts, fixed process specifications, frontend credential isolation, partial and health failures, Ctrl+C cleanup, the console entry point, trusted and unavailable Windows tree cleanup, an already-exited Windows root, POSIX process-group escalation, lifecycle-neutral error reporting, and cleanup attempts for every started child. A real local smoke run reached both health endpoints and left no listener on ports 8000 or 5173 after cleanup.

## Automated gates

| Area | Command | Observed result |
| --- | --- | --- |
| Backend/script lint | `uv run ruff check . ../scripts` | pass |
| Backend tests | `uv run --offline pytest -q` | 78 passed |
| Python artifacts | `uv build` | sdist and wheel built |
| Clean install | install the wheel into a new Python 3.13 virtual environment; list packaged fixtures, analyze `coding-loop` through `TestClient`, and run the installed offline evaluation CLI | pass; fixtures/evaluations are present and both entry paths run |
| Frontend lint | `npm run lint` | pass across source, config, and E2E files; zero warnings |
| TypeScript | `npm run typecheck` | application and Playwright config/E2E projects pass |
| Component tests | `npm test -- --run` | 4 files, 8 tests passed |
| Production bundle | `npm run build` | pass; JS 209.89 kB raw / 65.82 kB gzip |
| Browser E2E | ordinary `npm run e2e -- --project=chromium`; opt-in live capture with configured Hy3 | ordinary suite: 3 passed, 3 capture specs skipped; current continuous live suite: 1 passed in 1.7 minutes; old live suite: 1 passed, two analyses in 64,719 ms |
| Dependency integrity | `uv lock --check`, `uv tree --locked`, `npm ci`, `npm ls --omit=dev --all`; exact-version OSV query | locks resolve, production trees are valid, and all 20 locked runtime packages have zero known OSV entries |
| Markdown targets | `python scripts/check_markdown_links.py` | 151 local targets across 20 Markdown files; pass |
| Repository hygiene | `git diff --check` plus all-deliverable credential/personal-path/request-value scans | 99 text deliverables, zero whitespace or real sensitive-value hits; pass |

The three ordinary browser tests cover the `coding-loop` report and JSON export, the `research-grounding` report and Markdown export, and the research evidence workflow at 390×844 with no horizontal overflow. Offline and live capture specs are opt-in so ordinary tests do not rewrite review artifacts. Both live captures were run separately with real Hosted calls and passed.

The configured npm mirror does not implement the audit endpoint, and the official npm audit endpoint reset the connection again. As an independent fallback, an exact-version OSV query checked all three npm and 17 Python locked runtime packages; none had a known entry. The npm production tree contains only `react`, `react-dom`, and `scheduler` at their locked versions.

## TDD evidence

The implementation was grown through explicit red-to-green contracts for the first vertical slice, stable IDs, aggregate limits, provider repair, input/output redaction, export, API success/error paths, React workflow, Hy3 response/retry behavior, provider-compatible strict schemas, bounded repair hints, epistemic timing, rate-limit metadata, import safety, live-provider selection, custom imports, evidence-dialog focus/Escape behavior, evaluation report labeling, the Simplified-Chinese product surface and export headings, requested/actual model identity, fixed evaluation call budgets, and the source-workspace launcher lifecycle. Regression suites now exercise the combined behavior rather than relying on those historical failures.

Backend coverage includes invalid JSON, unknown references, bad ordering, controlled-repair success/failure, timeout/transport/retry/permanent errors, provider-coroutine cancellation, prompt injection, credential redaction, over-limit input/output, malicious filenames, wrong MIME, missing key, health state, 429 forwarding, and custom-import rules. Frontend coverage includes offline/live selection, no-key behavior, bad import, loading, browser-side stop-wait, explicit retry, 429, export, evidence accessibility, and coverage semantics.

## Real Hy3 evidence

The 2026-08-05 fixture and broad runs are recorded in the stage-1 section above. They do not overwrite these retained 2026-07-22 records.

The retained 2026-07-22 full-annotation gate used TokenHub `hy3-preview`, `temperature=0`, an inlined all-required JSON Schema, at most three HTTP attempts per call, and one controlled repair. Repair received a bounded rule category, never the human annotation or expected answer:

| Fixture | Gate | First divergence | Criteria | Evidence | Replay P/R | Gates | Unsafe | Latency | Tokens | Calls |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| `coding-loop` | pass | `step-006-repeat-patch` | 1.00 | 1.00 | 1.00/1.00 | 1.00 | no | 32,750 ms | 6,792 | 2 |
| `research-grounding` | pass | `step-006-unsupported-causal-leap` | 1.00 | 1.00 | 1.00/1.00 | 1.00 | no | 41,996 ms | 7,710 | 2 |

Evidence: [retained 2026-07-22 full fixture report](../evals/results/live-fixtures-hy3-preview-2026-07-22.md). Both rows passed exact divergence, protected criteria, required finding evidence, replay precision/recall, required validation gates, and the dangerous-suggestion check.

The historical v1 two-fixture run used TokenHub provider `tencent-tokenhub`, model `hy3`, `temperature=0`, strict JSON Schema, at most three attempts, and at most one controlled repair:

| Fixture | Gate | First divergence | Latency | Tokens | Attempts |
| --- | --- | --- | ---: | ---: | ---: |
| `coding-loop` | pass | `step-006-repeat-patch` | 12,062 ms | 2,348 | 1 |
| `research-grounding` | pass | `step-006-unsupported-causal-leap` | 72,893 ms | 2,460 | 2 |

Evidence: [historical live fixture report](../evals/results/live-fixtures-2026-07-22.md). Its saved rows prove structural acceptance and exact annotated first-divergence matches. They predate the current full-annotation gate and do not include model drafts that could be rescored after the fact.

The optional 12-case live batch later returned 2 valid reports and 10 bounded provider failures. Those failures remain in the 16.7% aggregate and are not hidden. Evidence: [broad live report](../evals/results/live-hy3-2026-07-22.md). The evaluation interpretation is in [evaluation.md](evaluation.md).

The earlier [UI smoke record](../evals/results/live-ui-smoke-2026-07-22.md) is retained. A later status-only probe resolved the final `hy3` failure as HTTP 402 / business code `401008`, an exhausted free allowance without postpaid access. The current gate used the supported, configurable `hy3-preview` service; no offline result or failed call was relabeled.

## UI demo gate

[`replaylab-live-walkthrough-2026-08-05.webm`](demo/replaylab-live-walkthrough-2026-08-05.webm) is the current continuous live evidence. FFmpeg inspection reported 52.160 seconds, VP8, 720×450, 25 fps. Six frames sampled at 1, 6, 16, 28, 40, and 50 seconds were inspected; they contain the Chinese ReplayLab UI and public fixture content only, with no desktop frame, notification, credential, endpoint, account, personal path, request ID, or private trace. The exact provenance and digest are in the [2026-08-05 record](../evals/results/stage1-2026-08-05/live-ui/continuous-live-demo-2026-08-05.md).

[`replaylab-live-demo.gif`](demo/replaylab-live-demo.gif) is 652,299 bytes and 12 seconds, assembled from five Playwright screenshots of the running Simplified-Chinese Web UI. The browser test selected `在线 Hy3`, confirmed live metadata for both fixtures, opened evidence, downloaded both export formats, and measured 64,719 ms for the two analyses combined. The frames contain only public synthetic data and local ReplayLab report IDs; visual inspection found no desktop, notification, credential, account, personal path, TokenHub request ID, or private trace. Evidence: [live UI gate](../evals/results/live-ui-demo-2026-07-22.md).

[`replaylab-offline-demo.gif`](demo/replaylab-offline-demo.gif) remains separately labeled for key-free reproduction. The preceding visual direction was generated through the logged-in ChatGPT Web image experience and is preserved as a [design reference](design/README.md); it is not used as a runtime screen. See [demo/README.md](demo/README.md).

## Reproduction sequence

```console
cd backend
uv sync --locked
uv run ruff check .
uv run pytest -q
uv build

cd ../frontend
npm ci
npm run lint
npm run typecheck
npm test -- --run
npm run build
npm run e2e -- --project=chromium

cd ..
python scripts/check_markdown_links.py
```

Live commands require the server-side variables described in the [README](../README.md). They consume Hosted quota and are intentionally excluded from ordinary local test commands.

For normal local use after the two dependency-install steps, run `uv run --project backend --no-sync replaylab-start` from the project root. The launcher itself does not consume Hosted quota.
