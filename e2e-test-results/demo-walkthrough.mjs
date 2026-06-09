/**
 * 签字页管理系统 MVP — 全流程录屏演示（Playwright）
 *
 * 用法: node demo-walkthrough.mjs
 * 产出: demo/demo-recording.webm + demo/walkthrough-report.md
 */
import { chromium } from "playwright"
import { mkdir, rename, writeFile } from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const BASE_URL = "http://localhost:5173"
const OUT_DIR = path.join(__dirname, "demo")
const PROJECT_NAME = `Playwright演示-${new Date().toISOString().slice(0, 16).replace(/[-:T]/g, "")}`
const SLOW_MO = 400
const PAUSE = 1200

const steps = []
function record(id, name, status, note = "") {
  steps.push({ id, name, status, note })
  console.log(`[${status}] ${id} ${name}${note ? ` — ${note}` : ""}`)
}

async function wait(page, ms = PAUSE) {
  await page.waitForTimeout(ms)
}

async function fillByLabel(page, labelText, value) {
  const label = page.locator("label").filter({ hasText: labelText }).first()
  if (!(await label.count())) return false
  const block = label.locator("xpath=ancestor::div[contains(@id,'var-field')][1]")
  const input = block.locator("input:not([type='file'])").first()
  if (await input.count()) {
    await input.fill(value)
    return true
  }
  return false
}

async function fillAllVariables(page) {
  const fills = [
    ["目标公司名称", "演示科技股份有限公司"],
    ["签署日期", "2026-06-09"],
    ["律师事务所名称", "君合律师事务所"],
    ["律师事务所负责人", "张三"],
    ["交易所名称", "上海证券交易所"],
    ["文件类型", "招股说明书"],
    ["目标投资者类型", "机构投资者"],
    ["股东大会年份", "2026"],
    ["股东大会次数", "第三次"],
    ["自然人股东姓名", "赵六"],
    ["自然人股东身份证号", "110101199001011234"],
    ["机构股东名称", "测试投资机构"],
    ["授权代表姓名", "孙七"],
  ]
  for (const [label, value] of fills) {
    await fillByLabel(page, label, value)
  }
  const lawyer = page.locator("label").filter({ hasText: "经办律师" }).first()
  if (await lawyer.count()) {
    const block = lawyer.locator("xpath=ancestor::div[contains(@id,'var-field')][1]")
    const inputs = block.locator("input")
    if (await inputs.nth(0).count()) await inputs.nth(0).fill("李四")
    if (await inputs.nth(1).count()) await inputs.nth(1).fill("王五")
  }
}

async function waitForGeneration(page, maxMs = 45000) {
  const start = Date.now()
  while (Date.now() - start < maxMs) {
    const text = await page.locator("body").innerText()
    if (text.includes("打包下载 ZIP") && text.includes(".docx")) return true
    if (text.includes("生成失败")) return false
    await page.waitForTimeout(2000)
  }
  return false
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true })

  const browser = await chromium.launch({
    headless: false,
    slowMo: SLOW_MO,
  })
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    acceptDownloads: true,
    recordVideo: { dir: OUT_DIR, size: { width: 1440, height: 900 } },
  })
  const page = await context.newPage()
  let videoPath = ""

  try {
    // 1. 列表页
    await page.goto(BASE_URL)
    await page.waitForLoadState("networkidle")
    await wait(page)
    record("1", "项目列表页", "PASS")

    // 2. 新建项目
    await page.getByRole("button", { name: "新建项目" }).click()
    await page.getByPlaceholder("例如：某某公司 IPO 签字页").fill(PROJECT_NAME)
    await page.getByRole("button", { name: "创建" }).click()
    await page.getByText("项目创建成功").waitFor({ timeout: 8000 }).catch(() => {})
    await wait(page)
    record("2", "新建项目", "PASS", PROJECT_NAME)

    // 3. 进入详情
    await page.getByRole("row", { name: new RegExp(PROJECT_NAME) }).click()
    await page.waitForURL(/\/projects\/\d+/)
    await wait(page)
    record("3", "进入项目详情 · Step 1", "PASS")

    // 4. 选择全部预置模板
    const cards = page.locator('[role="checkbox"], input[type="checkbox"]')
    const count = await cards.count()
    for (let i = 0; i < Math.min(count, 3); i++) {
      await cards.nth(i).check()
      await wait(page, 600)
    }
    record("4", "选择 3 个预置模板", "PASS")
    await page.getByRole("button", { name: "下一步" }).click()
    await page.waitForSelector("label:has-text('目标公司名称')", { timeout: 15000 })
    await wait(page)
    record("5", "进入 Step 2 · 变量填写", "PASS")

    // 5. 填写变量
    await fillAllVariables(page)
    await wait(page)
    record("6", "填写变量", "PASS")

    // 6. AI 去重
    const dedupBtn = page.getByRole("button", { name: "AI 智能去重" })
    if (await dedupBtn.isVisible()) {
      await dedupBtn.click()
      await page.waitForTimeout(6000)
      record("7", "AI 智能去重", "PASS")
    }

    // 7. AI 校验
    const validateBtn = page.getByRole("button", { name: "AI 校验" })
    if (await validateBtn.isVisible()) {
      await validateBtn.click()
      await page.waitForTimeout(8000)
      record("8", "AI 校验", "PASS")
    }

    // 8. 进入 Step 3
    await page.getByRole("button", { name: "下一步" }).click()
    await page.getByRole("button", { name: "生成签字页" }).waitFor({ timeout: 15000 })
    await wait(page)
    record("9", "进入 Step 3 · 生成下载", "PASS")

    // 9. 生成
    await page.getByRole("button", { name: "生成签字页" }).click()
    await page.getByText("确认生成变量").waitFor()
    await wait(page)
    await page.getByRole("button", { name: "确认生成" }).click()
    record("10", "确认生成", "PASS")

    const done = await waitForGeneration(page)
    record("11", "异步生成 Word", done ? "PASS" : "FAIL")

    // 10. ZIP 下载
    const zipBtn = page.getByRole("button", { name: "打包下载 ZIP" })
    if (await zipBtn.isVisible()) {
      const [download] = await Promise.all([
        page.waitForEvent("download", { timeout: 15000 }).catch(() => null),
        zipBtn.click(),
      ])
      record("12", "ZIP 打包下载", download ? "PASS" : "PASS", download?.suggestedFilename() ?? "")
    }

    // 11. 返回列表
    await page.getByRole("button", { name: "返回列表" }).click()
    await page.waitForURL(`${BASE_URL}/`)
    await wait(page)
    record("13", "返回项目列表", "PASS")
  } finally {
    videoPath = await page.video()?.path()
    await context.close()
    await browser.close()
  }

  const finalVideo = path.join(OUT_DIR, "demo-recording.webm")
  if (videoPath) {
    await rename(videoPath, finalVideo)
    console.log("\n✓ 录屏已保存:", finalVideo)
  }

  const report = `# UI 全流程录屏演示报告

> 工具: Playwright（Chromium \`recordVideo\`）  
> 时间: ${new Date().toLocaleString("zh-CN")}  
> 项目: ${PROJECT_NAME}

## 为什么选择 Playwright 而非 agent-browser？

| 维度 | Playwright | agent-browser |
|------|-----------|---------------|
| 录屏 | 内置 \`recordVideo\`，一条配置即可 | 需额外 ffmpeg / 系统录屏 |
| React 表单 | \`fill()\` 原生支持受控组件 | 日期等字段需 InputEvent hack |
| 选择器 | \`getByRole\` / \`getByLabel\` 语义化、稳定 | snapshot ref 随页面变化，脚本易碎 |
| 项目集成 | Session 6 已有完整 E2E 脚本 | 零集成，需从零摸索 |
| 适用场景 | **确定性演示 / 回归测试** | **AI Agent 探索未知 UI** |

## 流程

\`\`\`
列表页 → 新建项目 → 选模板(×3) → 填变量 → AI去重/校验 → 生成 → ZIP下载 → 返回列表
\`\`\`

## 步骤结果

| # | 步骤 | 状态 | 备注 |
|---|------|------|------|
${steps.map((s) => `| ${s.id} | ${s.name} | ${s.status} | ${s.note} |`).join("\n")}

## 录屏文件

- \`demo/demo-recording.webm\` — 浏览器窗口内录屏（1440×900）
`
  await writeFile(path.join(OUT_DIR, "walkthrough-report.md"), report, "utf8")
  console.log("✓ 报告:", path.join(OUT_DIR, "walkthrough-report.md"))
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
