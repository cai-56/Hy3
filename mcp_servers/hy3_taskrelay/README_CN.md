# Hy3 TaskRelay MCP

[English](README.md) | 简体中文

Hy3 TaskRelay 是一个本地 stdio MCP Server，用于把中断的长任务交接给另一会话或另一
MCP 客户端。Hy3 负责语义抽取、冲突推理和续作规划；本地代码负责输入边界、凭据脱敏、
稳定 ID、evidence 完整性、超时、有限重试和输出 schema 校验。

TaskRelay 无状态且只读：不扫描仓库，不读取 agent 日志，不写文件，不执行命令，也不
建立数据库。调用方负责保存和传递返回的 checkpoint。

![CodeBuddy 到 Codex 的原生客户端接力](docs/demo/taskrelay_native_clients_2026-08-05.gif)

这段 44.5 秒录屏实际运行 CodeBuddy Code 2.124.0、Codex CLI 0.144.6 和本项目的 stdio
Server。CodeBuddy 创建 checkpoint，Codex 接收同一份 artifact，完成 audit 和 resume。
本次录制使用本地确定性客户端模型适配器和本地确定性 TaskRelay 服务适配器，验证范围是
原生客户端发现、三个 MCP 调用、产物关联、HTTP 200/模型精确匹配和优先级顺序。
它不评价在线 Hy3 或客户端模型质量。脱敏结果见
[`native_clients_2026-08-05.json`](docs/native_clients_2026-08-05.json)，录制说明见
[`docs/demo/README.md`](docs/demo/README.md)。

当前在线状态（2026-08-05）：生产环境冒烟验证的第一次调用在取得可验证响应前返回 HTTP
402，因此没有重试。`actual_model` 无法确认，冻结的 10 个任务 × 2 次重复评测也没有
运行。[门禁记录](docs/live_validation_2026-08-05.json)不包含响应体、服务地址、请求 ID、
账户信息、凭据或本机路径。下文的 14/14 是离线契约断言，不是在线模型得分。

## 范围

TaskRelay 只处理当前 MCP 调用显式传入的材料，并返回可携带、通过 schema 校验的
checkpoint、audit 和 resume artifact。它不采集项目状态，不持久化记忆，也不提供用户
界面。

## 1. 安装

需要 Python 3.10–3.14，以及 `uv` 或 `pip`。项目使用
[官方 MCP Python SDK 稳定 v1](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x)，
依赖固定为 `mcp>=1.28.1,<2`。

在 Hy3 仓库根目录运行：

```powershell
# Windows PowerShell
uv sync --directory mcp_servers/hy3_taskrelay --extra dev
uv run --directory mcp_servers/hy3_taskrelay hy3-taskrelay-mcp
```

```bash
# macOS / Linux
uv sync --directory mcp_servers/hy3_taskrelay --extra dev
uv run --directory mcp_servers/hy3_taskrelay hy3-taskrelay-mcp
```

也支持普通本地安装：

```bash
python -m pip install ./mcp_servers/hy3_taskrelay
hy3-taskrelay-mcp
# 等价入口：
python -m hy3_taskrelay
```

进程在 stdin 等待 MCP JSON-RPC；直接启动时不会显示交互提示。

以下单条命令固定到原生客户端录屏所用的完整源码 SHA，并运行打包后的自检：

```bash
uvx --from "git+https://github.com/cai-56/Hy3.git@1a7694ec9451f0300d683d7071e9a44ddc064c65#subdirectory=mcp_servers/hy3_taskrelay" hy3-taskrelay --selfcheck
```

自检会启动打包后的 stdio 入口，初始化 MCP，列出恰好三个工具，通过确定性回环服务
适配器依次调用三个工具，校验产物关联，然后退出。

## 2. 配置 Hy3 API

只设置三个进程环境变量。Key 应保存在操作系统密钥存储或本地 shell 环境中；不要提交
到 Git，不要粘贴到 issue，也不要发到聊天里。

```powershell
$env:HY3_API_KEY = "<仅在本机设置>"
$env:HY3_BASE_URL = "<以-/v1-结尾的服务地址>"
$env:HY3_MODEL = "hy3"
```

```bash
export HY3_API_KEY='<仅在本机设置>'
export HY3_BASE_URL='<以-/v1-结尾的服务地址>'
export HY3_MODEL='hy3'
```

只有调用 tool 时才要求 Key，因此缺 Key 时仍可完成 `initialize` 和 `tools/list` 排查。
`HY3_BASE_URL` 必须使用 HTTPS；只有离线测试的回环地址允许 HTTP。未展开的 `${...}`
占位符会被拒绝，不会作为凭据发往 API。

## 3. 添加到 MCP 客户端

### CodeBuddy 项目级配置

把 [`examples/clients/codebuddy.mcp.json`](examples/clients/codebuddy.mcp.json) 复制到 Hy3
项目根目录的 `.mcp.json`；本仓库已经包含该文件。CodeBuddy 的
[官方 MCP 文档](https://www.codebuddy.ai/docs/cli/mcp)说明了项目级位置、首次连接审批、
headless 审批配置和 tool 权限名称。

等价的持久注册命令：

```bash
codebuddy mcp add-json --scope project hy3-taskrelay '{"type":"stdio","command":"uv","args":["run","--directory","mcp_servers/hy3_taskrelay","hy3-taskrelay-mcp"],"env":{"HY3_API_KEY":"${HY3_API_KEY}","HY3_BASE_URL":"${HY3_BASE_URL}","HY3_MODEL":"${HY3_MODEL}"}}'
```

交互模式首次连接时先检查并批准项目 MCP Server。headless 模式无法弹出审批 UI，必须
显式允许项目 Server。实测命令还把可见和允许的工具收窄到唯一一个 TaskRelay tool：

```powershell
$prompt = '只调用一次 taskrelay_create_checkpoint，使用公开合成 fixture，并返回结构化结果。'
codebuddy --model hy3 --output-format text `
  --strict-mcp-config --mcp-config .mcp.json `
  --settings '{"enabledMcpjsonServers":["hy3-taskrelay"]}' `
  --tools 'NoDefer(mcp__hy3-taskrelay__taskrelay_create_checkpoint)' `
  --allowedTools 'mcp__hy3-taskrelay__taskrelay_create_checkpoint' `
  -y -p $prompt
```

`-y` 会跳过交互式权限询问，只应与上面的严格 Server 配置和精确 tool allowlist 一起使用。
官方安装命令是 `npm install -g @tencent-ai/codebuddy-code`；本次验证使用 CodeBuddy
Code 2.124.0。

### Codex 项目级配置

把 [`examples/clients/codex.config.toml`](examples/clients/codex.config.toml) 复制到 Hy3
项目根目录的 `.codex/config.toml`；本仓库已经包含该文件。Codex 只会为受信任的项目
加载项目级配置。[官方 MCP 文档](https://developers.openai.com/codex/mcp)说明了
`env_vars`、tool allowlist 和 timeout。`env_vars` 只转发客户端进程中的同名变量，
不会把变量值写入 TOML。

```bash
codex mcp list
codex
```

先确认列表中出现 `hy3-taskrelay` 和恰好三个 TaskRelay tool，再让 Codex 审计
checkpoint 并生成 resume brief。配置中的 240 秒客户端超时长于 Server 的 105 秒
结构化生成总预算。

### 可选 Cursor 配置

把 [`examples/clients/cursor.mcp.json`](examples/clients/cursor.mcp.json) 复制到项目根目录
的 `.cursor/mcp.json`。Cursor 是可选第三客户端，本次 CodeBuddy + Codex 验收不依赖它。

## 4. 第一次调用

让客户端调用 `taskrelay_create_checkpoint`，使用一份小型合成输入：

```json
{
  "goal": "修复空购物车总价回归。",
  "session_material": "上一会话已复现 test_empty_cart_total，但在修复前中断。",
  "constraints": ["不得改变公开 API。"],
  "decisions": ["先添加回归测试。"],
  "evidence": [
    {
      "evidence_id": "ev_test_log",
      "content": "test_empty_cart_total 期望 Decimal('0.00')，实际得到 None。",
      "source": "合成 pytest 日志"
    }
  ]
}
```

保存返回的完整 structured checkpoint。三步 artifact 传递规则是：

1. 把原 checkpoint 传给 `taskrelay_audit_checkpoint`。这里的 `additional_evidence` 是
   checkpoint 创建后新发现的证据。
2. audit 输出会自动携带完整 evidence 目录：未改动的 checkpoint evidence，加上 audit
   阶段的新证据。
3. 把原 checkpoint 和完整 audit 结果传给 `taskrelay_create_resume_brief`。resume 的
   `additional_evidence` 只用于 audit 完成后才发现的证据；不要重复传 audit 已携带的证据。

稳定 ID 根据规范化内容计算。修改 artifact 内容却保留旧 ID 会被拒绝。

## 5. 三个 tool

| Tool | 用途 | 主要输出 |
|---|---|---|
| `taskrelay_create_checkpoint` | 把显式任务材料整理成可携带交接件 | 目标、事实、约束、决策、未决问题、后续步骤、evidence 目录、稳定 checkpoint ID |
| `taskrelay_audit_checkpoint` | 检查矛盾、遗漏约束、过期假设和无证据结论 | 按严重度排列、带 evidence ID 与修正建议的发现项 |
| `taskrelay_create_resume_brief` | 根据 checkpoint 和 audit 规划续作 | 简短上下文、优先步骤、验证条件、阻塞项和禁止事项 |

三个 tool 均标注为只读、非破坏、幂等、open-world。open-world 为 true 是因为调用会访问
外部 Hy3 API。每个成功结果都包含 MCP `structuredContent`，并附带紧凑 JSON 文本块，
兼容不直接暴露 structured content 的客户端。

Evidence ID 必须以 `ev_` 开头且不可重复。模型生成的结论、动作、阻塞项和禁止事项必须
引用调用方提供的 ID。调用方显式约束和决策可以保留空 evidence 列表；audit 不会只因
它是显式上下文就报错。未知引用最多触发一次受控修复，修复后仍无效就拒绝结果。

## 6. 边界与错误行为

| 操作 | 序列化总输入上限 | 其他上限 |
|---|---:|---|
| 创建 checkpoint | 30,000 字符 | 1–50 条 evidence；约束和决策各最多 30 条 |
| audit | 200,000 字符 | 最多 20 条新增 evidence |
| resume | 500,000 字符 | 最多 20 条 audit 后新增 evidence；续作上下文最多 4,000 字符 |

- Checkpoint、audit、resume artifact 上限分别为 65,000、300,000、500,000 个字符；
  Hy3 draft 在附加本地 evidence 前另有上限。
- HTTP 响应包最多 512,000 bytes，assistant 内容最多 100,000 字符；随后还要通过 JSON、
  Pydantic、稳定 ID 和 evidence 引用校验。
- 一次结构化操作（原始生成加最多一次修复）总预算为 105 秒；单个 HTTP 尝试为 45 秒。
- HTTP 400、401、403 立即失败；429、502、503、504 和网络超时最多重试两次。
  数字或 HTTP-date 形式的 `Retry-After` 最多尊重 30 秒；TokenHub `429006` 走 429 路径。
- 请求参数为 `temperature=0.9`、`top_p=1.0`、Hy3 `reasoning_effort=high`。
- system instruction 会把调用方 payload 和失败模型输出标记为不可信数据。
- 错误不会回显响应体、请求 ID、账户信息、Key、Cookie、Authorization、连接串或不安全
  的调用方标识符。

## 7. 排错

出现 `HY3_API_KEY is required`：在启动 MCP 客户端的环境中设置变量，再重启或重新连接。
字面量 `${HY3_API_KEY}` 会被视为未配置。

出现鉴权失败：只在本机检查 Key 和 TokenHub/model 权限，不要把 Key 粘贴到报告中。

`HY3_BASE_URL` 报错：使用以 `/v1` 结尾的完整 HTTPS OpenAI 兼容地址；不能包含凭据、
query 或 fragment。

客户端发现不了 Server：从 Hy3 项目根目录运行 `codebuddy mcp list` 或 `codex mcp list`，
并确认客户端 PATH 中存在 `uv`。CodeBuddy headless 模式要包含上文的项目 Server 审批
设置；Codex 要信任项目或改用用户级配置。stdio 日志只能写 stderr；stdout 出现非 JSON
内容属于 Server 缺陷。

Schema 或 evidence 报错：错误只在安全时指出契约字段，不会回显调用方值或未知 ID。
检查上述字段/总量边界、evidence ID 格式、artifact 关联，以及 resume evidence 是否真的
是新证据。已有 artifact 若包含疑似凭据，应从已脱敏源材料重新创建。不要修改 artifact
后继续使用旧的内容 ID。

## 8. 验证记录

README 顶部的原生客户端录屏是当前传输层与产物链证据。完整源码 SHA、客户端版本、
工具顺序、HTTP 状态、合成模型精确匹配、产物 ID 和验证边界记录在
[`native_clients_2026-08-05.json`](docs/native_clients_2026-08-05.json)。

较早的 2026-07-20 流程使用同一份公开合成样例：

1. CodeBuddy Code 2.124.0 通过严格单 tool allowlist 调用
   `taskrelay_create_checkpoint`，生成 `cp_b3067b1cc7f4a430`，包含 3 条事实和 2 个后续步骤。
2. Codex CLI 0.144.6 在 ephemeral、read-only 模式接收该精确 structured checkpoint。
3. Codex 调用 `taskrelay_audit_checkpoint`（`clean`、0 条发现），再调用
   `taskrelay_create_resume_brief`，生成 `resume_bff690737dece30f`，优先级顺序 1 → 2。

通过 schema 校验的历史产物在 [`docs/client_artifacts`](docs/client_artifacts)，脱敏后的
历史客户端事件记录在 [`docs/clients`](docs/clients)。13.2 秒的
[`taskrelay_cross_client.gif`](docs/demo/taskrelay_cross_client.gif) 是根据这些记录用 Pillow
绘制的结构摘要，不是原生桌面录屏。仓库不提交凭据、prompt、原始 provider 响应、请求
元数据、账户数据或个人路径。

## 9. 离线验证与评测

默认套件不发起在线 API 调用：

```bash
uv run --directory mcp_servers/hy3_taskrelay pytest
uv run --directory mcp_servers/hy3_taskrelay ruff format --check .
uv run --directory mcp_servers/hy3_taskrelay ruff check .
uv run --directory mcp_servers/hy3_taskrelay python evals/run.py
```

[2026-08-05 验证记录](docs/verification_2026-08-05.md)列出离线、构建、原生客户端、公开 CI
和在线门禁的准确结果。

离线评测库包含 14 个相互独立的契约断言，使用两份公开合成样例：
[`interrupted_bug_fix.json`](examples/fixtures/interrupted_bug_fix.json) 和
[`requirements_change.json`](examples/fixtures/requirements_change.json)。

另一套冻结的在线数据包含 10 个公开合成任务，每个任务要求重复两次。指标包括约束保留、
事实引用准确率、未知引用率、矛盾检出、后续步骤覆盖、跨重复一致性、协议级跨客户端一致性、
变化案例和失败案例。2026-08-05 没有在线指标，因为前置三工具冒烟验证在 HTTP 402 时停止。
指标定义见 [`evals/README.md`](evals/README.md)。

安装后可用 MCP Inspector 检查 stdio：

```bash
npx -y @modelcontextprotocol/inspector uv run --directory mcp_servers/hy3_taskrelay hy3-taskrelay-mcp
```

## 官方验收映射

| 官方要求 | 仓库内证据 | 当前状态 |
|---|---|---|
| 官方 MCP SDK 与 stdio | `pyproject.toml`、SDK memory-session、原始 stdio 测试、[Inspector 记录](docs/inspector_2026-07-20.json) | 已实现 |
| 至少 3 个清晰 tool | `server.py`、Pydantic 契约、tool list/call 测试 | 已实现；selfcheck 会列出并调用恰好三个 |
| Hy3 完成核心推理 | prompts、结构化校验、真实 HTTP client、历史[三操作 smoke](docs/live_smoke_2026-07-20.json) | 本轮生产复查停在 HTTP 402，无当前在线得分 |
| Key 只来自环境变量 | `config.py`、脱敏/错误测试和脱敏记录 | 已实现 |
| 两个客户端且含 CodeBuddy/WorkBuddy | CodeBuddy + Codex 配置与当前[原生传输记录](docs/native_clients_2026-08-05.json) | 确定性合成样例下接力通过 |
| 一键安装 | console entry point、固定 SHA 的 `uvx` 命令、含许可证的 wheel/sdist、`--selfcheck` | Python 3.10–3.14 已覆盖 |
| GIF/短视频 | [44.5 秒原生客户端录屏](docs/demo/taskrelay_native_clients_2026-08-05.gif) | 通过；范围见上文 |
