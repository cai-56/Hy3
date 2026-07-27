# Roo Code 3.54.0 验证记录

| 项目 | 结果 |
| --- | --- |
| 产品 | Roo Code |
| 类别 | IDE 扩展 |
| 版本 | `3.54.0` |
| 宿主 | Visual Studio Code `1.130.0` official Windows x64 archive |
| 验证日期 | 2026-07-23 |
| 安装方式 | D 盘共享扩展目录；两套独立 VS Code 状态根 |
| 实际模型 | `hy3-preview` |
| Provider | OpenAI Compatible |
| 协议 | OpenAI-compatible Chat Completions |
| 模式 | 在线、Ask、Auto-approve Off |
| 鉴权 | `HY3_API_KEY` 写入 VS Code secret storage |
| Base URL | 从 `HY3_BASE_URL` 填入首次引导 |

## 真实首轮

输入逐字取自 [`../task.md`](../task.md) 的首轮代码块。实际响应正文为：

```text
HY3_FIRST_TURN_V1
我可以协助您诊断客户端配置问题，包括检查配置文件、分析日志以及排查连接故障。
```

Roo Code 界面同时显示产品身份、`v3.54.0`、API Request、Task Completed 和响应正文。主验证没有读取文件、调用工具、执行命令或修改工作区。

## 统一任务

输入逐字取自 [`../task.md`](../task.md) 的统一任务代码块。实际响应正文为：

```text
HY3_TASK_V1

修正配置：
base_url: <HY3_BASE_URL>/v1
model: hy3-preview
api_key: <HY3_API_KEY>
protocol: openai-compatible-chat-completions

根因 1：Base URL 缺少 API 版本路径 /v1，导致请求无法路由到正确的 OpenAI 兼容端点。

根因 2：模型 ID 使用了 hy3-tokenhub，与探针确认可调用的真实模型 ID hy3-preview 不匹配，导致模型不可用。

验证步骤：执行 curl -s <HY3_BASE_URL>/v1/models -H "Authorization: Bearer <HY3_API_KEY>" | findstr "hy3-preview"，仅验证模型是否在返回列表中，不会打印 Key 内容。
```

响应只包含公开占位符。上述命令是模型给出的文字建议，没有被 Roo Code 执行；Ask 模式和 Auto-approve Off 保持不变。

## 干净状态复验

主验证使用 `roo-portable`，复验前新建此前不存在的 `roo-clean-portable` 与空工作区 `C:\tmp\hy3-roo-clean`。新状态首次打开显示 onboarding，没有复制主状态根的 Roo Code 会话。重新通过 UI 配置 OpenAI Compatible 和 `hy3-preview` 后，相同首轮提示再次得到：

```text
HY3_FIRST_TURN_V1
我可以协助您诊断客户端配置问题，包括检查配置文件、分析日志以及排查连接故障。
```

复验中扩展在纯文本响应后自动重试一次，并显示 `Model Response Incomplete`，说明它期待工具调用。由于冻结提示明确禁止工具调用，未启用工具或 Auto-approve；最终状态仍为 `Task Completed`，响应标记保持正确。

## 实测失败与处理

1. 首次主验证停在 `API Request`。扩展宿主日志定位到 `Could not find ripgrep binary`，不是 Hy3 API 错误。
2. Roo Code `3.54.0` 查找 `@vscode/ripgrep/bin/rg.exe`，而 VS Code `1.130.0` official archive 使用 `@vscode/ripgrep-universal/bin/win32-x64/rg.exe`。把官方二进制复制到兼容路径后，两次在线验证均成功；源与副本 SHA-256 都是 `83439bf545d316fb761e84e3180d1dbd36a46bd65598f8dcee0e816c117a4ceb`。
3. 复验中的 `Model Response Incomplete` 是 Roo Code 对无工具纯文本响应的状态判断。用户约束优先，因此记录该警告，不通过启用工具绕过。
4. 扩展内置公告称 `3.54.0` 为最后一个 Roo Code 版本，并提示后续不会提供 bug fix、功能或模型更新。

## 媒体与脱敏检查

| 文件 | SHA-256 | 覆盖内容 |
| --- | --- | --- |
| `assets/roo-code/first-turn-online.png` | `01cec3ef4fa24911a2e14aca342cfc4e072200df6b675ac39188fe3ab1aacac4` | Roo Code 身份、版本、首轮输入、API Request、Task Completed 和在线响应 |
| `assets/roo-code/task-output-online.png` | `62516a052169d126ce0342a81ce590d191173cbcb8e900ea2d27c7a05e50264a` | 任务标记、修正配置、两个根因、验证动作和 Task Completed |
| `assets/roo-code/version-3.54.0.png` | `d13b39b0102e31d6b6017e291af51535155f470e4653edf5c6d316e9e969f10a` | VS Code 扩展详情中的 Roo Code 身份、扩展 ID 与 `3.54.0` |
| `assets/roo-code/clean-reverification-online.png` | `7d76323ac2bc02684ceb991e85fb72a626563c90fd51f5cc9ad1ca8184a98e35` | 第二套状态根、首轮标记、在线响应、无工具警告与 Task Completed |
| `assets/roo-code/config-model-sanitized.png` | `406c7a12677cd8cf9128c7e6a49a147cae8c58566b21ee8489ac835833ee260a` | Roo Code 原生 Settings、`3.54.0`、OpenAI Compatible、占位端点、掩码 Key 与 `hy3-preview` |

五张图片均逐张检查。未发现 API Key、真实 Base URL、账号、Cookie、个人路径、请求 ID、通知或私有代码。图片来自实际 Visual Studio Code/Roo Code 窗口像素，没有脚本绘制或手工填写响应。配置截图只在未保存表单中显示公开端点占位符，随后退出设置页。
