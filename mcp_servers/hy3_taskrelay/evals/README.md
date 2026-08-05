# TaskRelay evaluation assets

This directory contains two deliberately separate verification layers.

## Offline contract assertions

`cases.json` and `run.py` execute 14 deterministic assertions over public,
fixture-authored responses. They prove schema, identity, grounding, audit, and priority
contracts without network access. They are not a model-quality benchmark and must not be
reported as real Hy3 results.

```console
uv run python -m evals.run
```

## Repeated real-Hy3 evaluation

`live_cases.json` is a frozen public synthetic dataset. Its raw bytes are SHA-256 hashed in
every result. It contains ten tasks and requires at least two repeats per task. The live runner
uses the production `Hy3Client` and `TaskRelayService` paths for checkpoint creation, audit,
and resume-brief creation. The completion-token ceiling and sampling parameters come directly
from the production client and are written into the result. To prevent accidental spend, the
runner rejects more than five repeats.

The runner is guarded by `--confirm-live`; tests and normal verification never issue paid
requests. Run it only with intentionally configured `HY3_API_KEY`, `HY3_BASE_URL`, and
`HY3_MODEL` values:

```console
uv run python scripts/live_evaluation.py --confirm-live --source-sha <40-character-source-sha>
```

Each de-identified JSON result records the date, full source SHA, dataset SHA-256, package
versions, requested and provider-returned model identities, exact HTTP 200 verification,
and success/failure for every task, repeat, and tool. It omits prompts, raw model responses,
provider request identifiers, credentials, endpoints, and local paths.

The reported metrics have intentionally narrow definitions:

- **Constraint retention rate:** expected explicit constraint phrases present in the checkpoint.
- **Fact citation accuracy:** expected fact cues found with all required evidence IDs attached.
- **Unknown reference rate:** unknown evidence IDs divided by all references in validated output.
- **Contradiction detection rate:** expected presence or absence of a contradiction finding; positive
  cases must cite the frozen evidence pair.
- **Next-step coverage rate:** expected action cues present in checkpoint or resume steps.
- **Cross-repeat consistency:** agreement of tool outcomes and metric pass counts across repeat pairs.
- **Failure and variation cases:** stable task/repeat/tool coordinates and differing dimensions;
  exception messages and raw content are never published.

These metrics evaluate the frozen synthetic scenarios only. They do not claim general model quality.
