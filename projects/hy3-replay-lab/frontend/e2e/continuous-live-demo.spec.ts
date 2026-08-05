import { createHash } from "node:crypto";
import { constants } from "node:fs";
import { access, copyFile, mkdir, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";

import { expect, type Page, test } from "@playwright/test";

const MINIMUM_DURATION_MS = 45_000;
const MAXIMUM_DURATION_MS = 75_000;

type ExportedReport = {
  finding: { first_divergence_step_id: string | null };
  metadata: {
    actual_model?: string | null;
    http_status?: number | null;
    mode: "fake" | "live";
    requested_model?: string;
  };
};

async function exportJson(page: Page): Promise<ExportedReport> {
  const downloadStarted = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 JSON" }).click();
  const download = await downloadStarted;
  const downloadPath = await download.path();
  expect(downloadPath).not.toBeNull();
  return JSON.parse(await readFile(downloadPath!, "utf-8")) as ExportedReport;
}

function assertLiveIdentity(report: ExportedReport, expectedModel: string): void {
  expect(report.metadata.mode).toBe("live");
  expect(report.metadata.requested_model).toBe(expectedModel);
  expect(report.metadata.actual_model).toMatch(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,79}$/);
  expect(report.metadata.http_status).toBe(200);
}

async function requireFreshOutput(filePath: string): Promise<void> {
  try {
    await access(filePath);
  } catch (error) {
    if (
      typeof error === "object" &&
      error !== null &&
      "code" in error &&
      error.code === "ENOENT"
    ) {
      return;
    }
    throw error;
  }
  throw new Error(
    `Reviewed output ${path.basename(filePath)} already exists; choose a fresh REPLAYLAB_DEMO_OUTPUT_TAG.`,
  );
}

test("录制 45 至 75 秒的真实 Hy3 连续复盘流程", async ({ page }, testInfo) => {
  test.skip(
    process.env.REPLAYLAB_CAPTURE_CONTINUOUS_DEMO !== "1",
    "Set REPLAYLAB_CAPTURE_CONTINUOUS_DEMO=1 to record the reviewed live walkthrough.",
  );
  test.setTimeout(180_000);

  const demoDate = process.env.REPLAYLAB_DEMO_DATE?.trim();
  if (!demoDate || !/^\d{4}-\d{2}-\d{2}$/.test(demoDate)) {
    throw new Error("Set REPLAYLAB_DEMO_DATE to the YYYY-MM-DD recording date.");
  }
  const outputTag = process.env.REPLAYLAB_DEMO_OUTPUT_TAG?.trim();
  if (!outputTag || !/^[a-z0-9][a-z0-9-]{0,39}$/.test(outputTag)) {
    throw new Error("Set REPLAYLAB_DEMO_OUTPUT_TAG to a fresh lowercase output tag.");
  }
  const expectedModel = process.env.HY3_MODEL?.trim();
  expect(expectedModel).toBeTruthy();
  const temporaryVideo = testInfo.outputPath("replaylab-live-walkthrough.webm");
  const reviewedVideo = path.resolve(
    "..",
    "docs",
    "demo",
    `replaylab-live-walkthrough-${outputTag}.webm`,
  );
  const resultDirectory = path.resolve(
    "..",
    "evals",
    "results",
    `stage1-${outputTag}`,
    "live-ui",
  );
  const resultStem = `continuous-live-demo-${outputTag}`;
  const resultJson = path.join(resultDirectory, `${resultStem}.json`);
  const resultMarkdown = path.join(resultDirectory, `${resultStem}.md`);

  await Promise.all(
    [reviewedVideo, resultJson, resultMarkdown].map(requireFreshOutput),
  );

  await page.setViewportSize({ width: 720, height: 450 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "选择一个复盘场景" })).toBeVisible();
  const liveMode = page.getByRole("button", { name: "在线 Hy3" });
  await expect(liveMode).toBeEnabled();
  await liveMode.click();

  await page.getByRole("button", { name: "分析研究证据漂移" }).click();
  const researchFinding = page.getByRole("heading", {
    name: "step-006-unsupported-causal-leap",
  });
  await expect(researchFinding).toBeVisible({ timeout: 90_000 });
  await expect(page.locator(".mode-badge")).toHaveText("在线 Hy3");
  const researchReport = await exportJson(page);
  assertLiveIdentity(researchReport, expectedModel!);
  expect(researchReport.finding.first_divergence_step_id).toBe(
    "step-006-unsupported-causal-leap",
  );
  await researchFinding.scrollIntoViewIfNeeded();

  const frameTimestamps: number[] = [];
  const recordingStartedAt = Date.now();
  await page.screencast.start({
    path: temporaryVideo,
    quality: 85,
    size: { width: 720, height: 450 },
    onFrame: ({ timestamp }) => frameTimestamps.push(timestamp),
  });
  const actions = await page.screencast.showActions({
    duration: 700,
    fontSize: 22,
    position: "top-right",
  });
  let codingReport: ExportedReport | undefined;

  try {
    await page.screencast.showChapter("案例一：研究证据漂移", {
      description: "Hy3 已完成真实在线分析，先核对首个偏航点与证据闭包。",
      duration: 2_400,
    });
    await page.getByRole("button", { name: "ev-source-a" }).first().click();
    await expect(page.getByRole("dialog", { name: "ev-source-a" })).toBeVisible();
    await page.waitForTimeout(1_800);
    await page.getByRole("button", { name: "关闭证据" }).click();
    await page.locator('[aria-label="最小重放计划"]').scrollIntoViewIfNeeded();
    await page.waitForTimeout(1_200);

    await page.screencast.showChapter("案例二：编程循环", {
      description: "从点击开始完整记录新的 Hy3 在线调用、等待、定位与最小重放计划。",
      duration: 2_400,
    });
    const codingButton = page.getByRole("button", { name: "分析编程循环" });
    await codingButton.scrollIntoViewIfNeeded();
    await codingButton.click();
    await expect(page.getByText("正在追踪证据边界")).toBeVisible();

    const codingFinding = page.getByRole("heading", { name: "step-006-repeat-patch" });
    const remainingResultBudget = Math.max(
      1,
      68_000 - (Date.now() - recordingStartedAt),
    );
    await expect(codingFinding).toBeVisible({ timeout: remainingResultBudget });
    await expect(page.locator(".mode-badge")).toHaveText("在线 Hy3");
    await codingFinding.scrollIntoViewIfNeeded();
    await page.screencast.showChapter("首个偏航点已定位", {
      description: "证据、验收覆盖和最小重放计划均已通过本地确定性校验。",
      duration: 1_800,
    });
    await page.getByRole("button", { name: "ev-repeat-failure" }).first().click();
    await expect(page.getByRole("dialog", { name: "ev-repeat-failure" })).toBeVisible();
    await page.waitForTimeout(1_200);
    await page.getByRole("button", { name: "关闭证据" }).click();
    await page.locator('[aria-label="最小重放计划"]').scrollIntoViewIfNeeded();

    codingReport = await exportJson(page);
    assertLiveIdentity(codingReport, expectedModel!);
    expect(codingReport.finding.first_divergence_step_id).toBe("step-006-repeat-patch");

    const elapsed = Date.now() - recordingStartedAt;
    if (elapsed < MINIMUM_DURATION_MS + 1_000) {
      await page.waitForTimeout(MINIMUM_DURATION_MS + 1_000 - elapsed);
    }
  } finally {
    await actions.dispose();
    await page.screencast.stop();
  }

  const recordingDurationMs = Date.now() - recordingStartedAt;
  const frameSpanMs =
    frameTimestamps.length > 1
      ? frameTimestamps.at(-1)! - frameTimestamps[0]
      : 0;
  const videoStat = await stat(temporaryVideo);
  expect(recordingDurationMs).toBeGreaterThanOrEqual(MINIMUM_DURATION_MS);
  expect(recordingDurationMs).toBeLessThanOrEqual(MAXIMUM_DURATION_MS);
  expect(frameSpanMs).toBeGreaterThanOrEqual(MINIMUM_DURATION_MS - 2_000);
  expect(videoStat.size).toBeGreaterThan(250_000);

  const videoBytes = await readFile(temporaryVideo);
  const sha256 = createHash("sha256").update(videoBytes).digest("hex");
  expect(codingReport).toBeDefined();
  const result = {
    date: demoDate,
    media: path.basename(reviewedVideo),
    sha256,
    continuous: true,
    resolution: { width: 720, height: 450 },
    recording_wall_duration_ms: recordingDurationMs,
    frame_span_ms: frameSpanMs,
    observed_frames: frameTimestamps.length,
    requested_model: expectedModel,
    actual_models: [
      ...new Set([
        researchReport.metadata.actual_model,
        codingReport!.metadata.actual_model,
      ]),
    ],
    http_statuses: [
      researchReport.metadata.http_status,
      codingReport!.metadata.http_status,
    ],
    fixtures: [
      {
        fixture_id: "research-grounding",
        first_divergence_step_id: researchReport.finding.first_divergence_step_id,
        placement: "result shown at recording start after a real pre-recording call",
      },
      {
        fixture_id: "coding-loop",
        first_divergence_step_id: "step-006-repeat-patch",
        placement: "complete real call recorded from click through result",
      },
    ],
    post_processing: "none; capture viewport and output are both 720x450",
    privacy: "public synthetic fixtures only; no key, endpoint, request ID, account, or local path",
  };
  const markdown = [
    "# ReplayLab continuous live demo",
    "",
    `- Date: ${demoDate}`,
    `- Media: \`${result.media}\``,
    `- SHA-256: \`${sha256}\``,
    `- Continuous duration: ${(recordingDurationMs / 1_000).toFixed(3)} seconds`,
    "- Resolution: 720 × 450",
    `- Requested / actual model: \`${expectedModel}\` / \`${researchReport.metadata.actual_model}\``,
    "- HTTP status: 200 for both displayed live reports",
    "- Research case: a real online result is shown first after its pre-recording call.",
    "- Coding case: the real online call is recorded continuously from click through result.",
    `- Post-processing: ${result.post_processing}.`,
    "- Privacy: public synthetic fixtures only; no key, endpoint, request ID, account, or local path.",
    "",
  ].join("\n");

  await mkdir(path.dirname(reviewedVideo), { recursive: true });
  await mkdir(resultDirectory, { recursive: true });
  await copyFile(temporaryVideo, reviewedVideo, constants.COPYFILE_EXCL);
  await writeFile(
    resultJson,
    `${JSON.stringify(result, null, 2)}\n`,
    { encoding: "utf-8", flag: "wx" },
  );
  await writeFile(resultMarkdown, markdown, {
    encoding: "utf-8",
    flag: "wx",
  });
});
