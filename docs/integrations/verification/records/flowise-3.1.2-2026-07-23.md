# Flowise 3.1.2 验证记录

| 项目 | 结果 |
| --- | --- |
| 产品 | Flowise |
| 类别 | 工作流平台 |
| 版本 | `3.1.2` |
| 验证日期 | 2026-07-23 |
| 安装方式 | D 盘 npm prefix；数据、密钥、上传目录和日志分别隔离 |
| 实际模型 | `hy3-preview` |
| 节点 | OpenAI Custom Model → LLM Chain；Prompt Template → LLM Chain |
| 协议 | OpenAI-compatible Chat Completions |
| 模式 | 在线 |
| 鉴权 | OpenAI API credential，由 Flowise 本地密钥加密 |
| Base Path | 从 `HY3_BASE_URL` 填入 OpenAI Custom Model |

## 真实首轮

输入逐字取自 [`../task.md`](../task.md) 的首轮代码块。主实例实际响应正文为：

```text
HY3_FIRST_TURN_V1
我可以协助您诊断客户端配置相关问题，例如网络连接、软件设置或参数错误等。
```

响应由 `Hy3 Integration Doctor` Chatflow 的真实在线调用产生。画布显示 `hy3-preview`、三节点连接、输入和响应；没有文件读取、工具调用或命令执行。

## 统一任务

输入逐字取自 [`../task.md`](../task.md) 的统一任务代码块。实际响应正文为：

```text
HY3_TASK_V1
base_url: <HY3_BASE_URL>/v1
model: hy3-preview
api_key: <HY3_API_KEY>
protocol: openai-compatible-chat-completions
根因 1：Base URL 缺少 API 版本路径 /v1，导致请求无法路由到正确的 OpenAI 兼容端点。
根因 2：模型 ID 使用了 hy3-tokenhub，与探针确认可调用的真实模型 ID hy3-preview 不一致，会导致模型不可用。
验证步骤：使用 curl 向 <HY3_BASE_URL>/v1/models 发起 GET 请求，仅检查返回状态码与模型列表是否包含 hy3-preview，不输出任何包含 API Key 的内容。
```

四行配置紧随任务标记输出；模型没有重复字面标题“修正配置”，但字段、顺序、两个根因和验证动作均完整。回答只包含公开占位符。`curl` 是模型给出的文字建议，Flowise 没有执行命令。

### 严格格式复验

将 Temperature 从 `0.2` 调整为 `0` 后逐字重跑统一任务，模型仍省略字面标题。记录保留这一
原始结果，不把它改写为完全符合格式。随后在同一无记忆 LLM Chain 中再次发送完整任务，只追加
一句“‘修正配置：’是必须原样输出的独立标题，不能省略”。真实在线响应为：

```text
HY3_TASK_V1
修正配置：
base_url: <HY3_BASE_URL>/v1
model: hy3-preview
api_key: <HY3_API_KEY>
protocol: openai-compatible-chat-completions
根因 1：Base URL 缺少 API 版本路径，openai-compatible-chat-completions 协议要求路径中包含 /v1 才能正确路由到聊天补全接口。
根因 2：model 字段使用了错误的模型 ID，当前可调用的正确模型 ID 为 hy3-preview，而非 hy3-tokenhub。
验证步骤：使用 curl 向 <HY3_BASE_URL>/v1/models 发送 GET 请求，并在请求头中携带 Authorization: Bearer <HY3_API_KEY>，检查返回列表中是否包含 hy3-preview，全程不打印或回显 API Key 内容。
```

严格复验截图同时显示追加说明、完整任务末段和完整响应，避免把格式补正误写成原始逐字任务的
首答。

## 干净配置复验

主验证使用 `flowise-main` 和 `18086`，复验使用新建的 `flowise-clean` 和 `18087`。第二个根包含独立的数据库、加密密钥、上传目录与日志；首次打开显示账户初始化页面，完成初始化后显示 `No Chatflows Yet`，没有复制主实例的账户、凭据、Chatflow 或会话。

重新创建凭据和三节点 Chatflow 后，相同首轮提示得到：

```text
HY3_FIRST_TURN_V1
我可以协助您诊断客户端配置相关问题，例如连接异常、参数错误或环境设置不当等情况。
```

## 版本与运行状态

- Flowise 的 `/api/v1/version` 返回 `{"version":"3.1.2"}`。
- 产品内 **Flowise Version** 对话框显示 **Current Version 3.1.2**。
- 两个实例均在 `127.0.0.1` 上监听；主实例 `/api/v1/ping` 返回 `pong`。

## 实测失败与处理

1. GitHub Release 原生二进制下载超时。安装树放在 D 盘，原生模块从经过官方资产大小或发布哈希交叉检查的缓存启用；没有修改产品代码。
2. `connect-sqlite3@^0.9.15` 在当前日期解析到 `0.9.17`，启动时报 `this.db.exec is not a function`。固定为 Flowise 声明范围内的 `0.9.15` 后，认证会话存储正常。
3. 部分 ReAct Agent 节点因当前 LangChain 传递依赖的导出路径变化而被节点扫描跳过。日志随后显示节点池和服务器初始化成功；本次三个节点不受影响。
4. 两次在线响应文本完整出现后，聊天输入框仍显示加载状态。没有伪造完成状态；截图保留加载指示器，记录按屏幕中的完整响应正文验收。
5. `tiktoken.pages.dev` 在格式复验期间连接超时。重启主实例时使用临时 preload，从已安装的
   `js-tiktoken` 包本地提供同一编码表；它只替代 token 计数的外网下载，不修改任务文本、
   Flowise 节点、Hy3 请求或模型响应。

## 媒体与脱敏检查

| 文件 | SHA-256 | 覆盖内容 |
| --- | --- | --- |
| `assets/flowise/first-turn-online.png` | `2d9f6fe14b7799b27c6d92b2f785f9b788d67b392b4fca1821698d739c341715` | Flowise Chatflow、模型、三节点连接、首轮输入和在线响应 |
| `assets/flowise/task-output-online.png` | `6476a5838e7d64d6fc4dce818340cf8c4ea5020e91699e44ea04bdff80453fed` | `HY3_TASK_V1`、四行修正配置、两个根因和验证动作 |
| `assets/flowise/task-output-strict-retry-sanitized.png` | `c7333a9b323b7c991cfe2245a80bda7a8d624314354e7fce28cfc658d74ccf05` | 透明的严格格式复验、独立“修正配置：”标题、四行配置、两个根因和验证动作 |
| `assets/flowise/version-3.1.2.png` | `ed3a849a83f00c4d1ec5b858865c1629b4e5e287308c47641298440bbdf96e31` | 产品身份、Current Version `3.1.2` 和运行中的干净 Chatflow |
| `assets/flowise/clean-reverification-online.png` | `7abc24dce093dcc56ea863d33e9bf79eb62deade9eff21b67c24cba92c203e31` | 全新数据根、重新创建的 Chatflow、模型、首轮输入和在线响应 |

五张图片均逐张检查。未发现 API Key、真实 Base URL、管理员邮箱、密码、Cookie、个人路径、
请求 ID 或私有代码。图片来自真实 Flowise/Chrome 页面像素，没有脚本绘制或手工填写响应。
