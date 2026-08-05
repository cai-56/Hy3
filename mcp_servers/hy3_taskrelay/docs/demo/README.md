# 客户端接力演示

## 2026-08-05 原生客户端录屏

[`taskrelay_native_clients_2026-08-05.gif`](taskrelay_native_clients_2026-08-05.gif) 长 44.5 秒。
录屏窗口实际运行 CodeBuddy Code 2.124.0、Codex CLI 0.144.6 和 TaskRelay stdio Server：

1. CodeBuddy 调用 `taskrelay_create_checkpoint`，得到 `cp_373f9873c7b47571`。
2. Codex 审计同一 checkpoint，结果为 `clean`，发现项为 0。
3. Codex 调用 `taskrelay_create_resume_brief`，得到 `resume_d8fbe6ea38b898ba`，优先级为
   `[1, 2]`。

三个服务适配器响应均为 HTTP 200，请求模型和返回模型均为本地合成身份
`hy3-native-demo`。完整源码 SHA、tool 顺序、关联结果和录制参数见
[`../native_clients_2026-08-05.json`](../native_clients_2026-08-05.json)。

录制使用本地确定性客户端模型适配器和本地确定性 TaskRelay 服务适配器。它验证原生客户端
可发现 MCP Server、三个 MCP 工具可执行、结构化产物可跨客户端传递。它不代表在线
Hy3 或 CodeBuddy/Codex 模型质量。录屏只捕获目标终端窗口；原始客户端流、凭据、服务地址、
请求 ID、账户信息和本机路径均未提交。

## 2026-07-20 历史结构摘要

13.2 秒的 [`taskrelay_cross_client.gif`](taskrelay_cross_client.gif) 是 Pillow 绘制的信息图，
不是原生桌面录屏。它根据当时的脱敏客户端记录和通过 schema 校验的产物展示以下流程：

- CodeBuddy Code 2.124.0 创建 `cp_b3067b1cc7f4a430`。
- Codex CLI 0.144.6 完成 `clean` audit，并创建 `resume_bff690737dece30f`。

四张 PNG 同样是确定性绘制的摘要卡：

- [`codebuddy_actual_call.png`](codebuddy_actual_call.png)
- [`codex_actual_calls.png`](codex_actual_calls.png)
- [`codebuddy_checkpoint.png`](codebuddy_checkpoint.png)
- [`codex_audit_resume.png`](codex_audit_resume.png)

安装开发依赖后可重新生成历史信息图：

```bash
python scripts/render_client_demo.py
```
