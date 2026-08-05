# 演示来源说明

`replaylab-live-demo.gif` 是 12 秒快速预览，由五张真实在线界面帧串联而成。Playwright 启动实际 FastAPI 与 Vite 服务，界面明确选择“在线 Hy3”，两条公开案例均由 TokenHub `hy3-preview` 返回并通过本地确定性校验。它不是连续录屏。

[`replaylab-live-walkthrough-2026-08-05.webm`](replaylab-live-walkthrough-2026-08-05.webm) 是 52.160 秒连续在线实录。研究案例先在录像外完成一次真实调用，录像从该在线结果开始；随后从点击开始完整记录编程案例的新 Hy3 调用、等待、偏航定位、证据抽屉、最小重放计划和 JSON 导出。两个导出报告均记录请求模型 `hy3-preview`、实际模型 `hy3-preview` 和 HTTP 200。

`replaylab-offline-demo.gif` 保留为无需 Key 即可复现的离线演示，页面始终显示“离线演示”，不会与在线证据混用。

## 连续在线录制流程

1. 选择“在线 Hy3”，在录像外运行 `research-grounding`，导出 JSON 并核对 `mode=live`、请求/实际模型和 HTTP 状态。
2. 开始连续录制，展示研究案例的首个偏航、证据和最小重放计划。
3. 点击 `coding-loop`，完整保留真实在线等待过程。
4. 展示 `step-006-repeat-patch`、`ev-repeat-failure`、最小重放计划并导出 JSON。
5. 只有持续时间、连续帧跨度、在线身份、两个偏航编号和文件大小均通过后，才把临时 WebM 提升到 `docs/demo/`。

浏览器记录的墙钟时长为 51.778 秒，WebM 容器时长为 52.160 秒、25 fps。2026-08-05 录制时，原始录制器把 720×450 活动画面放在 1440×900 画布左上角；审阅成片只做左上角 720×450 的空间裁剪，未做时间剪切或内容替换。裁剪后重新核对容器时长、分辨率和 SHA-256，并把 `media_duration_ms`、`post_processing` 与最终摘要写回结构化台账。该次裁剪的原始精确命令没有保留，不能声称可重建相同二进制哈希；固定提交中的成片及其摘要是本次证据真值。等价的视觉变换是 `crop=720:450:0:0`，不同 FFmpeg 构建或编码参数可能产生不同哈希。SHA-256 和结构化记录见[连续在线演示记录](../../evals/results/stage1-2026-08-05/live-ui/continuous-live-demo-2026-08-05.md)。

当前录制脚本已经把浏览器视口和输出都固定为 720×450，新录制会写入 `post_processing=none`，不再复现上述历史留白或裁剪，也不会重建 2026-08-05 成片的固定哈希。脚本要求显式设置录制日期和新的输出标签，并在任何 Hosted 调用前检查 WebM、JSON、Markdown 三个目标均不存在。

## 旧五帧在线流程

1. 选择“在线 Hy3”，运行 `coding-loop`。
2. 定位 `step-006-repeat-patch`，查看 `ev-repeat-failure`，下载 JSON。
3. 运行 `research-grounding`。
4. 定位 `step-006-unsupported-causal-leap`，查看 `ev-source-a`，下载 Markdown。

2026-07-22 的两次在线分析合计 64,719 毫秒，低于两分钟门禁。五张在线界面帧是：

- [场景选择](live-frames/01-case-picker.png)
- [编程偏航](live-frames/02-coding-divergence.png)
- [编程证据](live-frames/03-coding-evidence.png)
- [研究偏航](live-frames/04-research-divergence.png)
- [研究证据](live-frames/05-research-evidence.png)

对应的离线帧保存在 [`frames/`](frames/)。

## 复现

在线录制要求后端进程环境已经配置 `HY3_API_KEY`、`HY3_BASE_URL` 和可用的 `HY3_MODEL`。连续 WebM 还需要 Playwright 官方 FFmpeg 组件。在 `frontend/` 中运行：

```console
npx playwright install ffmpeg
```

连续在线实录会消耗两条 Hosted 调用；脚本使用独占输出路径，失败不会覆盖已审阅媒体：

```powershell
$env:HY3_MODEL = "hy3-preview"
$env:REPLAYLAB_CAPTURE_CONTINUOUS_DEMO = "1"
$env:REPLAYLAB_DEMO_DATE = Get-Date -Format "yyyy-MM-dd"
$env:REPLAYLAB_DEMO_OUTPUT_TAG = "2026-08-05-review-1"
npx playwright test e2e/continuous-live-demo.spec.ts --project=chromium
```

`REPLAYLAB_DEMO_OUTPUT_TAG` 只用于新文件名，应改成尚未使用的小写标签；若任一目标已存在，用例会在在线请求之前退出。现有 `2026-08-05` 证据是只读审阅产物，不要删除或覆盖。

旧五帧在线素材的复现命令是：

```powershell
$env:REPLAYLAB_CAPTURE_LIVE_DEMO = "1"
npx playwright test e2e/live-demo-capture.spec.ts --project=chromium
```

离线录制不消耗 Hosted 配额：

```powershell
$env:REPLAYLAB_CAPTURE_DEMO = "1"
npx playwright test e2e/demo-capture.spec.ts --project=chromium
```

然后在 `backend/` 中组装对应 GIF：

```console
uv run python ../scripts/build_demo_gif.py --mode live
uv run python ../scripts/build_demo_gif.py --mode offline
```

截图用例通过与普通浏览器测试相同的 Playwright 配置驱动真实应用。[`build_demo_gif.py`](../../scripts/build_demo_gif.py) 只用 Pillow 缩放并串联截图，不绘制或伪造产品界面。

## 隐私与真实性检查

- 在线帧的模式按钮和结果元数据都显示“在线 Hy3”；离线帧保留原标签。
- 截图和 WebM 只包含公开合成案例和本地生成的 ReplayLab 报告编号。
- 对连续实录抽取 1、6、16、28、40、50 秒关键帧做视觉复核；没有桌面外框、通知、账号、API Key、端点、个人路径、TokenHub 请求编号或私有轨迹。
- 两个 GIF 均为 12 秒；连续 WebM 为 52.160 秒。旧在线调用合计 64,719 毫秒，当前连续演示对应的两个导出报告均为 HTTP 200。
- 当前 2/2 完整标注结果见[2026-08-05 fixture 报告](../../evals/results/stage1-2026-08-05/live-fixtures/live-fixtures-2026-08-05T020537Z.md)；旧完整门禁和浏览器记录分别见[2026-07-22 fixture 报告](../../evals/results/live-fixtures-hy3-preview-2026-07-22.md)与[旧在线界面门禁](../../evals/results/live-ui-demo-2026-07-22.md)。
