# Hy3 Hosted API Quickstart

This is the short English path for the Tencent Cloud hosted API. The
[Chinese guide](quickstart.md) contains the full parameter table, regional endpoint
choices, and troubleshooting notes.

## 1. Configure the client

Python 3.10 through 3.13 is verified on Windows. Install the two runtime
dependencies from the repository root:

```bash
python -m pip install -r examples/api/requirements.txt
```

Set these variables in your shell. Keep their values out of source files, logs,
screenshots, and chat messages.

```text
HY3_API_KEY       required
HY3_BASE_URL      required; use the endpoint shown in your Tencent Cloud console
HY3_MODEL         optional; defaults to hy3
```

PowerShell:

```powershell
$env:HY3_API_KEY = "your key"
$env:HY3_BASE_URL = "your hosted API base URL"
$env:HY3_MODEL = "hy3"
```

Bash:

```bash
export HY3_API_KEY='your key'
export HY3_BASE_URL='your hosted API base URL'
export HY3_MODEL='hy3'
```

## 2. Make the first request

Run the basic chat example:

```bash
python examples/api/01_basic_chat.py
```

The equivalent minimal SDK call is:

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["HY3_API_KEY"],
    base_url=os.environ["HY3_BASE_URL"],
)
response = client.chat.completions.create(
    model=os.getenv("HY3_MODEL", "hy3"),
    messages=[{"role": "user", "content": "Explain an API in one sentence."}],
    max_tokens=256,
    extra_body={"thinking": {"type": "disabled"}},
)
print(response.choices[0].message.content)
```

For cURL, send the same JSON body to
`$HY3_BASE_URL/chat/completions` and pass the key in the `Authorization: Bearer`
header. The [Chinese quickstart](quickstart.md#3-用-curl-完成第一次调用) includes
copyable PowerShell and Bash commands.

## 3. Run the six examples

| Topic | Command | Guide |
|---|---|---|
| Basic and multi-turn chat | `python examples/api/01_basic_chat.py` | [Guide](examples/api/01_basic_chat.md) |
| Streaming chunks and usage | `python examples/api/02_streaming.py` | [Guide](examples/api/02_streaming.md) |
| TTFT and total latency | `python examples/api/03_latency_compare.py --runs 5 --warmup 1` | [Guide](examples/api/03_latency_compare.md) |
| Bounded tool loop | `python examples/api/04_tool_calling.py` | [Guide](examples/api/04_tool_calling.md) |
| Thinking modes | `python examples/api/05_reasoning_mode.py` | [Guide](examples/api/05_reasoning_mode.md) |
| Retry and backoff | `python examples/api/06_error_handling_retry.py` | [Guide](examples/api/06_error_handling_retry.md) |

Hosted requests use top-level `thinking` and `reasoning_effort` fields. The
`chat_template_kwargs` examples in the main README belong to local vLLM/SGLang
deployment.

## 4. Check the evidence

The [validation record](examples/api/LIVE_VALIDATION.md) separates the six
successful runs from 2026-07-17 and the current 2026-08-05 quota failure. It also
records test coverage, Python versions, platform limits, and the redacted terminal
demo.

Run the offline gate at any time:

```bash
python -m pytest examples/api/tests -m "not live" -q
python -m compileall -q examples/api
ruff format --check examples/api
ruff check examples/api
```

Set `HY3_REQUIRE_LIVE=1` when a skipped live check must fail the command. The live
smoke requires HTTP 200 and an exact match between the requested and returned model.
