# Open WebUI 0.10.1 验证记录

| 项目 | 结果 |
| --- | --- |
| 产品 | Open WebUI |
| 类别 | 桌面/网页客户端 |
| 版本 | `0.10.1` |
| 验证日期 | 2026-07-23 |
| 安装方式 | uv 隔离工具，Python `3.11.15`，程序与缓存位于 D 盘任务目录 |
| 实际模型 | `hy3-preview` |
| 协议 | OpenAI-compatible Chat Completions |
| 模式 | 在线 |
| Base URL | 用户环境变量 `HY3_BASE_URL`，完整 API 前缀以 `/v1` 结尾 |
| 鉴权 | 用户环境变量 `HY3_API_KEY` |

## 安装与版本

固定安装 `open-webui==0.10.1`。uv 工具清单和 Python 包元数据均返回 `0.10.1`；真实界面的“关于”页显示 `v0.10.1`。本次使用原生 Python 安装，没有启动 Docker，避免 Docker 数据继续占用系统盘。

## 真实首轮

输入：

```text
HY3_FIRST_TURN_V1
只回复两行：第一行原样回复上面的标记；第二行用一句简体中文说明你能协助诊断客户端配置问题。
```

实际输出：

```text
HY3_FIRST_TURN_V1
我可以协助您诊断客户端配置问题。
```

界面同时显示模型 `Hy3 preview`。

## 统一任务

输入使用 [`../task.md`](../task.md) 的冻结提示词，未经改写。实际输出为：

```text
HY3_TASK_V1
修正配置：
base_url: <HY3_BASE_URL>/v1
model: hy3-preview
api_key: <HY3_API_KEY>
protocol: openai-compatible-chat-completions
根因 1：Base URL 缺少 API 版本路径 /v1，导致请求无法路由到正确的 OpenAI 兼容接口端点。
根因 2：模型 ID 使用了 hy3-tokenhub，但当前可调用的正确模型 ID 应为 hy3-preview，导致模型不可用。
验证步骤：使用 curl 向 <HY3_BASE_URL>/v1/models 发送 GET 请求（不带 API Key 或仅使用 -H "Authorization: Bearer <HY3_API_KEY>" 占位符），确认返回模型列表中包含 hy3-preview。
```

响应满足任务标记、占位符配置、两个根因和一个验证步骤。输出中的 `<HY3_API_KEY>` 是公开占位符，不是实际凭据。

## 干净配置

服务器首次使用新的隔离 `DATA_DIR`、禁用持久配置和本地账号认证启动。完成首轮和统一任务后，又在第二个全新 `DATA_DIR` 与独立端口启动同版本服务；重新选择 `hy3-preview` 并发送同一首轮提示，在线响应再次命中 `HY3_FIRST_TURN_V1`。OpenAI-compatible 地址和 Key 只从进程环境变量读取，界面没有录入或显示实际 Key。

## 实测失败与处理

1. `open-webui --version` 不是该版本支持的命令，安装命令因此曾以非零状态结束；包已正确安装，后续改用 uv 清单、包元数据和“关于”页交叉确认。
2. 离线启动时日志提示缺少 sentence-transformers 模型。Chat Completions 健康检查和两次在线对话不受影响；本次没有把检索能力写成已验证功能。
3. 为保护系统盘，本次没有复用现有 Docker VHDX，也没有拉取容器镜像。

## 媒体与脱敏检查

| 文件 | SHA-256 | 覆盖内容 |
| --- | --- | --- |
| `assets/open-webui/first-turn-online.jpg` | `134356510471db29cd9aac7bf73ee45624367dc39d0d60611fd5bb2ca7d99e45` | 产品界面、模型、首轮标记、真实响应 |
| `assets/open-webui/task-marker-online.jpg` | `45d2c068da5cb545c97362926683902b3fa627c624ae1cf0553b832b8a3eab25` | 模型、统一任务输入、任务标记 |
| `assets/open-webui/task-output-online.jpg` | `a0a0828906919ae929985a171f02ae0c2995a1a82b0580e9ffab84ea7e34d213` | 占位符配置、两个根因、验证步骤 |
| `assets/open-webui/version-0.10.1.jpg` | `0eccb96b39a15cf094ba836fd9eec272367fc93038209e76ceb98c7258d23320` | 产品身份与版本 |
| `assets/open-webui/clean-reverification-online.jpg` | `4f8c12d7c01551ed750f1590d22999e6f65586721bf49f6b59ea370cc5e8ad18` | 第二个全新数据目录中的模型、首轮标记与在线响应 |

逐张检查未发现 API Key、账号、Cookie、个人路径、请求 ID、通知或私有仓库内容。图片来自真实 Open WebUI 运行界面，没有脚本绘制或手工填充响应。
