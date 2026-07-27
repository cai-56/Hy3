# CodeBuddy Code 2.124.0 在线验证记录

| 项目 | 结果 |
| --- | --- |
| 产品 | CodeBuddy Code |
| 类别 | 命令行客户端 |
| 版本 | `2.124.0` |
| 验证日期 | 2026-07-23 |
| 安装状态 | 本机已有用户级 npm 包，本次未重复安装 |
| 实际模型 | `hy3-preview` |
| 协议 | OpenAI-compatible Chat Completions |
| 模式 | 在线 |
| 配置隔离 | 两个独立 `CODEBUDDY_CONFIG_DIR` |
| 鉴权 | `models.json` 引用 `${HY3_API_KEY}` |

`supportsToolCall` 与命令行工具列表均关闭。本记录只验证文本问答，不把工具调用能力写成已支持事实。

## 最小服务探针

探针没有输出原始响应体、请求标识或 Key。

| 请求 | HTTP | 结果 |
| --- | ---: | --- |
| `model=hy3`，要求只回复 `HY3_PROBE_V1` | 402 | `error_code=401008`，未通过 |
| `GET <HY3_BASE_URL>/models` | 200 | Hy3 系列列表包含 `hy3` 与 `hy3-preview` |
| `model=hy3-preview`，要求只回复 `HY3_PROBE_V1` | 200 | `response_model=hy3-preview`，标记命中，`finish_reason=stop` |

因此全部计数证据使用并标注 `hy3-preview`。

## 真实首轮

输入逐字取自 [`../task.md`](../task.md) 的首轮代码块。第二个干净配置目录中的实际输出：

```text
HY3_FIRST_TURN_V1
我可以帮你分析客户端配置文件、检查环境变量设置以及排查连接或启动相关的配置错误。
```

## 统一端到端任务

输入逐字取自 [`../task.md`](../task.md) 的统一任务代码块。第二个干净配置目录中的实际输出：

```text
HY3_TASK_V1

修正配置：
base_url: <HY3_BASE_URL>/v1
model: hy3-preview
api_key: <HY3_API_KEY>
protocol: openai-compatible-chat-completions

根因 1：Base URL 缺少 `/v1` API 版本路径。TokenHub 的 OpenAI 兼容接口要求请求路径为 `/v1/chat/completions`，仅配置服务根地址会导致所有请求 404。

根因 2：模型 ID 使用了 `hy3-tokenhub`，但探针确认可调用的模型 ID 是 `hy3-preview`，两者不匹配，会导致模型不存在错误。

验证步骤：用 curl 发送一个不携带真实 Key 的探测请求，只验证 URL 和模型参数格式是否正确：

curl -s -o /dev/null -w "%{http_code}" <HY3_BASE_URL>/v1/models -H "Authorization: Bearer <HY3_API_KEY>"

返回 401 说明路由和模型列表端点可达（鉴权失败是预期行为），配置路径正确。
```

输出包含任务标记、四行占位符配置、两个根因和一个不会打印实际 Key 的验证动作。

## 干净配置复验

首轮开发验证使用第一个临时配置目录。取证运行另建第二个只含 `models.json` 与最小 `user-state.json` 的目录，没有复制 `projects/`、`sessions/`、日志或缓存。冻结首轮与统一任务均在第二个目录重新在线执行，截图中的 `clean isolated configuration` 对应这次复验。

## 实测失败与处理

1. Windows PowerShell 把多行参数直接传给 `-p` 时，CodeBuddy 只接收到首行；改用标准输入。
2. 默认管道编码使一次中文 JSONL 输入乱码；最终以无 BOM UTF-8 字节写入子进程 stdin。
3. `-p --output-format json` 曾退出 0 但 stdout 为空；最终使用可观察的 `text` 输出。
4. 一次开启工具能力的试验产生工具标签文本，未计入证据；最终同时关闭模型工具能力和 CLI 工具列表。
5. PowerShell npm 包装器会调用 `exit`，不利于组合取证；最终直接调用已安装包的真实 Node 入口，没有修改客户端代码。

## 媒体与脱敏检查

| 文件 | SHA-256 | 覆盖内容 |
| --- | --- | --- |
| `assets/codebuddy-code/online-verification.png` | `83a4f672f7dcca3adc5a13b3dab2c84e03aaadff5aa7e8d7c1cc47972f3e33e9` | 产品名、版本、模型、在线/干净模式、首轮标记、任务标记、完整诊断 |
| `assets/codebuddy-code/native-cli-online.png` | `ed6e1bdf6d05a10e151cbe34db7c831eabb4ad8afd7b787a1a8e557d25b5f05d` | 原生 CLI 版本命令、`--model hy3-preview`、空工具列表和真实在线最小响应 |

两张图片逐项检查，未发现 API Key、真实端点、账号、Cookie、个人路径、请求 ID、通知或私有代码。图片是实际终端窗口的像素截图，响应来自 CodeBuddy Code 进程；没有脚本绘制界面或手工填充模型输出。补充标记 `HY3_NATIVE_EVIDENCE_V1` 不参与冻结任务计数，只用于证明原生 CLI 的命令与响应来源。
