# Cline 4.0.10 验证记录

| 项目 | 结果 |
| --- | --- |
| 产品 | Cline |
| 类别 | IDE 扩展 |
| 版本 | `4.0.10` |
| 宿主 | Visual Studio Code `1.130.0` official Windows x64 archive |
| 验证日期 | 2026-07-23 |
| 安装方式 | D 盘共享扩展目录；独立 `VSCODE_PORTABLE` 状态根 |
| 实际模型 | `hy3-preview` |
| Provider | OpenAI Compatible |
| 协议 | OpenAI-compatible Chat Completions |
| 模式 | 在线 |
| 鉴权 | VS Code secret storage；输入值来自用户环境变量 `HY3_API_KEY` |
| Base URL | 输入值来自用户环境变量 `HY3_BASE_URL` |

## 真实首轮

输入逐字取自 [`../task.md`](../task.md) 的首轮代码块。实际响应正文为：

```text
HY3_FIRST_TURN_V1
我可以协助您诊断客户端配置问题，包括检查配置文件、环境变量和相关设置。
```

Cline 的 Markdown 视图把单换行渲染为空格，任务完成卡片还会重复一次最终文本；记录按响应正文去重。界面底部模型选择器显示 `openai-compat:hy3-preview`。

## 统一任务

输入逐字取自 [`../task.md`](../task.md) 的统一任务代码块。实际响应正文为：

```text
HY3_TASK_V1

修正配置：
base_url: <HY3_BASE_URL>/v1
model: hy3-preview
api_key: <HY3_API_KEY>
protocol: openai-compatible-chat-completions

根因 1：Base URL 缺少 API 版本路径 /v1，导致请求无法路由到正确的 OpenAI 兼容接口端点。

根因 2：模型 ID 配置为 hy3-tokenhub，但实际可调用的模型 ID 应为 hy3-preview，导致模型不存在错误。

验证步骤：执行 curl -s <HY3_BASE_URL>/v1/models -H "Authorization: Bearer <HY3_API_KEY>" | head -c 200，仅打印前 200 字符的模型列表，不会暴露完整 API Key。
```

响应只保留公开占位符，没有输出真实 Key。验证过程中 Cline 没有读取工作区文件、调用工具、执行命令或写入文件。

## 干净状态复验

主验证使用 `cline-portable` 状态根。复验前重新创建独立的 `cline-clean-portable` 根和另一个公开临时工作区；打开 Cline 时没有 `RECENT` 会话。VS Code secret storage 重新关联了 provider 凭据，但首个 portable 根的聊天状态没有复制。相同首轮提示再次在线得到完整 `HY3_FIRST_TURN_V1` 响应。

## 启动隔离说明

验证期间系统安装版 VS Code 正被官方安装器更新，`vscode-updating` mutex 会阻止 archive 启动。没有终止用户的安装器或现有 VS Code。下载的官方 archive 副本仅在 `product.json` 中使用独立 `win32MutexName` 并关闭该副本的 versioned updater；Cline 扩展包、请求配置和响应均未修改。

## 媒体与脱敏检查

| 文件 | SHA-256 | 覆盖内容 |
| --- | --- | --- |
| `assets/cline/first-turn-online.png` | `b77db8b1850547cf32d95ac6c0b6550152cbde98880ccd1be87aaac47c5e5431` | Cline 身份、首轮输入、在线响应 |
| `assets/cline/task-output-online.png` | `31bc99b88118077fc643bcc7a9e65af0c83453c41a1708d9e51bd1c816dcad89` | Cline 身份、完整统一提示、任务标记、修正配置、根因和验证动作 |
| `assets/cline/version-4.0.10.png` | `63f0eed3b113de62a9b0d0807aa13e7be0f7fd01b8e3f7f6caced2dc0373c397` | VS Code Running Extensions 页中的 Cline `4.0.10` |
| `assets/cline/clean-reverification-online.png` | `f7ac656682b3f06ece89a8beb15bf0dd33e59543ba69d18aa172e3f83892bafb` | 第二个 portable 根、首次标记和在线响应 |
| `assets/cline/config-model-sanitized.png` | `1d03cd0232715af60f4a89b842e93bd835fb22c26ec1eb59d87c0c8a4ada1700` | Cline 原生 Provider 表单、`4.0.10`、OpenAI Compatible、占位端点、掩码 Key 与 `hy3-preview` |

五张图片均逐张检查。未发现 API Key、真实端点、账号、Cookie、个人路径、请求 ID、通知或私有代码。图片来自实际 VS Code/Cline 窗口像素，没有脚本绘制或手工填写响应。配置截图中的占位端点与模型只在未提交表单中用于脱敏取证，随后通过 **Back** 放弃。
