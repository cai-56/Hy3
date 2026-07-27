# 统一验证任务：Hy3 客户端配置诊断 v1

所有计数产品必须逐字使用下面的任务提示，不得针对不同客户端改写。

```text
请诊断下面这段公开、脱敏的 Hy3 客户端配置。不要读取文件、调用工具、执行命令，也不要补充未给出的事实。

错误配置：
base_url: <HY3_BASE_URL>
model: hy3-tokenhub
api_key: <HY3_API_KEY>
protocol: openai-compatible-chat-completions

已知约束：
- `<HY3_BASE_URL>` 表示 TokenHub 的公开服务根地址，但当前配置缺少 API 版本路径。
- 本轮真实探针确认可调用的模型 ID 是 `hy3-preview`。
- API Key 必须继续使用占位符，不能猜测或输出真实值。

请只按以下顺序输出：
1. 第一行写 `HY3_TASK_V1`。
2. `修正配置`：给出四行配置，只允许使用 `<HY3_BASE_URL>` 和 `<HY3_API_KEY>` 占位符。
3. `根因 1`：说明 Base URL 的问题。
4. `根因 2`：说明模型 ID 的问题。
5. `验证步骤`：给出一个最小、不会打印 Key 的验证动作。
```

首次对话使用独立固定提示：

```text
HY3_FIRST_TURN_V1
只回复两行：第一行原样回复上面的标记；第二行用一句简体中文说明你能协助诊断客户端配置问题。
```
