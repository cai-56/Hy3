# Aider 0.86.2 验证记录

| 项目 | 结果 |
| --- | --- |
| 产品 | Aider |
| 类别 | 命令行客户端 |
| 版本 | `0.86.2` |
| 验证日期 | 2026-07-23 |
| 安装方式 | D 盘 uv 隔离工具；Python `3.12.13`；补装 `aider-chat[browser]==0.86.2` |
| 实际模型 | `hy3-preview` |
| Aider 模型名 | `openai/hy3-preview` |
| 协议 | OpenAI-compatible Chat Completions |
| 模式 | 在线 |
| 鉴权 | `OPENAI_API_KEY` 从用户环境变量 `HY3_API_KEY` 复制 |
| Base URL | `OPENAI_API_BASE` 从用户环境变量 `HY3_BASE_URL` 复制 |

## 真实首轮

输入逐字取自 [`../task.md`](../task.md) 的首轮代码块。实际输出：

```text
HY3_FIRST_TURN_V1
我可以协助你诊断客户端配置问题。
```

Aider 界面同时显示 `Aider v0.86.2`、`Model: openai/hy3-preview` 和 `ask edit format`。

## 统一任务

输入逐字取自 [`../task.md`](../task.md) 的统一任务代码块。实际输出内容为：

```text
HY3_TASK_V1
修正配置：
base_url: <HY3_BASE_URL>/v1
model: hy3-preview
api_key: <HY3_API_KEY>
protocol: openai-compatible-chat-completions
根因 1：Base URL 缺少 API 版本路径 /v1，导致请求无法路由到正确的接口。
根因 2：模型 ID 配置错误，使用了 hy3-tokenhub 而非实际可调用的 hy3-preview。
验证步骤：使用 curl 向 <HY3_BASE_URL>/v1/models 发送不带认证头的请求，确认返回模型列表。
```

本机最小探针已确认 `/v1/models` 可返回模型列表，因此该验证动作不需要输出 Key。

## 干净配置复验

首次验证在只含公开 README 的新 Git 仓库中完成，历史文件全部指向 Windows `NUL`。复验另建第二个 Git 仓库并使用独立端口，没有复制首个会话的 Streamlit 状态；相同首轮提示再次得到 `HY3_FIRST_TURN_V1`。

## 实测失败与处理

1. Aider 基础工具环境缺少 browser extra，`--gui` 首次停在交互安装提示；改为显式安装固定版本的 `aider-chat[browser]`。
2. `--gui --no-browser` 的后一个参数关闭了 GUI；最终只使用 `--gui`，并用 Streamlit headless 配置控制浏览器行为。
3. `--no-git` 与当前 GUI 不兼容；改用无私有内容的临时 Git 仓库。
4. README 未被 Git 跟踪时，Streamlit 的文件多选框报错；`git add README.md` 后界面正常，无需提交。
5. 默认编辑格式的一次终端试验试图创建以首轮标记命名的文件；该运行未计入结果。最终固定 `--edit-format ask`，真实首轮和统一任务均没有修改文件。

## 媒体与脱敏检查

| 文件 | SHA-256 | 覆盖内容 |
| --- | --- | --- |
| `assets/aider/first-turn-online.png` | `ce59b032558f643f0046eba33c42387879107786bbd74dd005f63a95b0ceed48` | Aider 身份、版本、在线模型、首轮输入与响应 |
| `assets/aider/task-output-online.png` | `da3c91b17a4edcc01580d2db64e817d16e213fb2d55ea6da4b9c09e176bab98d` | Aider 身份、统一任务约束、任务标记与完整诊断 |
| `assets/aider/clean-reverification-online.png` | `ea0e9c96a30cd8781bc634245d1be25802b2152a9b11aca5b090bd2bd2f0b447` | 第二个临时仓库中的版本、模型、首轮标记和在线响应 |

逐张检查未发现 API Key、账号、Cookie、个人路径、请求 ID、通知或私有代码。截图来自 Aider 自带的真实 Streamlit 界面，没有脚本绘制或手工填写响应。
