# OpenCode 1.18.3 验证记录

| 项目 | 结果 |
| --- | --- |
| 产品 | OpenCode |
| 类别 | 命令行客户端 |
| npm 包 / 服务器版本 | `1.18.3` |
| Web UI bundle | `OpenCode Desktop v1.18.2` |
| 验证日期 | 2026-07-23 |
| 安装方式 | D 盘独立 npm prefix，`opencode-ai@1.18.3` |
| 实际模型 | `hy3-preview` |
| Provider model | `hy3/hy3-preview` |
| 协议 | OpenAI-compatible Chat Completions |
| 模式 | 在线 |
| 鉴权 | 配置引用 `HY3_API_KEY` |
| Base URL | 配置引用 `HY3_BASE_URL` |

## 真实首轮

Web UI 中输入逐字取自 [`../task.md`](../task.md) 的首轮代码块。实际输出：

```text
HY3_FIRST_TURN_V1
我可以协助您诊断客户端配置问题，包括检查配置文件、环境变量和连接设置等。
```

界面同时显示 `Hy3 Preview` 和在线耗时。

## 统一任务

同一 Web UI 会话使用冻结统一提示，命中 `HY3_TASK_V1`。响应内容为：

```text
HY3_TASK_V1
修正配置：
base_url: <HY3_BASE_URL>/v1
model: hy3-preview
api_key: <HY3_API_KEY>
protocol: openai-compatible-chat-completions
根因 1：Base URL 缺少 API 版本路径 /v1，导致请求无法路由到正确的 OpenAI 兼容端点。
根因 2：模型 ID 使用了 hy3-tokenhub 而非实际可调用的 hy3-preview，导致模型不存在错误。
验证步骤：使用 curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer <HY3_API_KEY>" <HY3_BASE_URL>/v1/models 检查返回状态码是否为 200。
```

Web UI 的 Markdown 渲染器把尖括号包围的占位符当作 HTML 标签，因此屏幕上 `base_url` 和 `api_key` 的值为空；输入区仍显示字面占位符。OpenCode CLI 对同一冻结任务的独立在线运行显示了完整占位符：

```text
HY3_TASK_V1
修正配置：
base_url: <HY3_BASE_URL>/v1
model: hy3-preview
api_key: <HY3_API_KEY>
protocol: openai-compatible-chat-completions
```

CLI 与 Web UI 属于同一产品，只计为一个 OpenCode。

## 干净配置复验

复验使用第二个临时 Git 仓库、全新的 `XDG_CONFIG_HOME`、`XDG_DATA_HOME`、`XDG_CACHE_HOME`、`XDG_STATE_HOME` 和独立端口。新 Web UI 首次打开时没有项目或会话；添加公开临时项目后发送相同首轮提示，再次得到 `HY3_FIRST_TURN_V1` 和在线中文响应。

## 实测失败与处理

1. 非 Git 临时目录只形成 `global` 项目，Web UI 首页不显示项目；初始化临时 Git 仓库后，通过“添加项目”选择目录即可。
2. 初次启动遗漏 `XDG_STATE_HOME`，调试路径显示状态仍落在系统盘；停止该实例并同时设置四个 XDG 目录后重启。
3. Web UI 的尖括号占位符被 Markdown/HTML 渲染隐藏；保留 UI 截图说明真实显示，同时用同产品 CLI 的原始文本交叉核验。
4. 设置页显示 Web UI bundle `v1.18.2`，而健康端点、npm 包和可执行文件均为 `1.18.3`；两者分开记录。

## 媒体与脱敏检查

| 文件 | SHA-256 | 覆盖内容 |
| --- | --- | --- |
| `assets/opencode/first-turn-online.png` | `8289819cce33795f99d9c78618831cc36c010ee37c0a2eb1c71af88c00030435` | 真实会话、首轮标记、模型和在线响应 |
| `assets/opencode/task-output-online.png` | `5c992eb3feb1529b7c4e3ba9da231697d5b52ba05f6a72bb5616c1634e8a0252` | 统一任务输入、任务标记、两个根因与验证步骤 |
| `assets/opencode/version-server-1.18.3.png` | `465082987652e76400d47e5e42dad225b6f3e769166f270d2d9c83d9e73fe6f8` | OpenCode 产品身份、Web UI bundle 与服务器版本 |
| `assets/opencode/clean-reverification-online.png` | `0492d41b88778199ed6a28c1047ff9b6bccfdf4ca65d38258e5d2da8202eb6c3` | 全新状态根中的模型、首轮标记和在线响应 |

逐张检查未发现 API Key、账号、Cookie、个人路径、请求 ID、通知或私有代码。截图来自 OpenCode 官方 Web UI，没有脚本绘制或手工填充响应。
