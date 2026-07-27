# Continue 2.0.0 验证记录

| 项目 | 结果 |
| --- | --- |
| 产品 | Continue |
| 类别 | IDE 扩展 |
| 版本 | `2.0.0` |
| 宿主 | Visual Studio Code `1.130.0` official Windows x64 archive |
| 验证日期 | 2026-07-23 |
| 安装方式 | D 盘共享扩展目录；独立 `VSCODE_PORTABLE` 和 `CONTINUE_GLOBAL_DIR` |
| 实际模型 | `hy3-preview` |
| UI 模型名 | `Hy3 Preview` |
| Provider | `openai`，自定义 `apiBase` |
| 协议 | OpenAI-compatible Chat Completions |
| 模式 | 在线、Chat |
| 鉴权 | `${{ secrets.HY3_API_KEY }}` 从隔离进程环境解析 |
| Base URL | `${{ secrets.HY3_BASE_URL }}` 从隔离进程环境解析 |

## 真实首轮

输入逐字取自 [`../task.md`](../task.md) 的首轮代码块。实际响应正文为：

```text
HY3_FIRST_TURN_V1
我可以协助你诊断客户端配置相关问题，例如连接异常、参数设置错误等。
```

Continue 界面显示 Chat 和 `Hy3 Preview`。Markdown 视图把响应中的单换行显示为空格。

## 统一任务

输入逐字取自 [`../task.md`](../task.md) 的统一任务代码块。实际响应正文为：

```text
HY3_TASK_V1
修正配置：
base_url: <HY3_BASE_URL>/v1
model: hy3-preview
api_key: <HY3_API_KEY>
protocol: openai-compatible-chat-completions
根因 1：Base URL 缺少 API 版本路径 /v1，导致请求无法路由到正确的接口端点。
根因 2：配置的模型 ID 为 hy3-tokenhub，与真实可调用的模型 ID hy3-preview 不匹配，会导致模型调用失败。
验证步骤：使用 curl 向 <HY3_BASE_URL>/v1/models 发送不带认证头的请求，确认返回模型列表中包含 hy3-preview。
```

响应没有输出真实 Key，验证动作也不要求认证头。Chat 模式没有读取工作区文件、调用工具、执行命令或写入文件。

## 干净状态复验

主验证使用 `continue-main` 和 `continue-portable`。复验前重新创建 `continue-clean` 与 `continue-clean-portable`，配置文件只复制公开 YAML 和 secret 引用，没有复制数据库或会话文件。首次打开会话搜索显示 `No results`。相同首轮提示再次得到：

```text
HY3_FIRST_TURN_V1
我可以协助你诊断客户端配置问题，例如检查连接参数、验证证书或排查网络设置。
```

## 实测失败与处理

1. Continue `2.0.0` 首次启动仍显示通用 provider 推荐卡片，即使本地模型已成功加载；关闭卡片后 `Hy3 Preview` 可正常调用。
2. 默认模式按钮只显示图标；展开后显式选择 Chat，防止误入 Agent。
3. Running Extensions 页报告 `continue.focusContinueInput` 已被同一扩展注册。首轮和统一任务均已在线成功，因此记录该非阻断警告，不把它误报为调用失败。

## 媒体与脱敏检查

| 文件 | SHA-256 | 覆盖内容 |
| --- | --- | --- |
| `assets/continue/first-turn-online.png` | `5c2d18caf854de4880441ac97394a7aad2169be8488e6d650c3fef28d8fe8acf` | Continue 身份、首轮输入与在线响应 |
| `assets/continue/task-output-online.png` | `11869569c40734307441a018e579ae150c0da2c9c8e242006c79df4e46e9e894` | 完整统一提示、任务标记、修正配置、根因和验证动作 |
| `assets/continue/version-2.0.0.png` | `cb5e9ec8044fa701fed97e06a010b14669c676710e4d8be8199dba37f6f5eeea` | Running Extensions 页中的 Continue `2.0.0` 与非阻断警告 |
| `assets/continue/clean-reverification-online.png` | `4bd09c24a91b8a664e52ad6338c00562523361208be14647a3517fa2bd27bc82` | 第二套状态根、首次标记和在线响应 |
| `assets/continue/config-model-sanitized.png` | `0b2502e49b94402c51eada88971777c981402fb118769790b981512f1b39cda4` | Continue 原生 Models 页和实际脱敏配置：provider、模型、secret 引用、Chat role 与禁用的未验证能力 |

五张图片均逐张检查。未发现 API Key、真实端点、账号、Cookie、个人路径、请求 ID、通知或私有代码。图片来自实际 VS Code/Continue 窗口像素，没有脚本绘制或手工填写响应。
