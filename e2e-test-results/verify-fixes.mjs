/** Verify E2E bug fixes: category filter + AI validate with unsaved form */
import { chromium } from "playwright"
import path from "path"

const BASE = "http://localhost:5173"
const SHOT = path.join(import.meta.dirname, "screenshots")

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage()

  // Fix 1: shareholder category filter
  await page.goto(`${BASE}/`)
  await page.getByRole("button", { name: "新建项目" }).click()
  await page.getByPlaceholder("例如：某某公司 IPO 签字页").fill("Fix验证-分类筛选")
  await page.getByRole("button", { name: "创建" }).click()
  await page.waitForTimeout(1000)
  await page.getByRole("row", { name: /Fix验证-分类筛选/ }).click()
  await page.waitForTimeout(1000)

  await page.getByRole("button", { name: "股东" }).click()
  await page.waitForTimeout(1000)
  const shareholderCards = await page.locator("h3").filter({ hasText: /股东签字页/ }).count()
  await page.screenshot({ path: path.join(SHOT, "fix-2.3-shareholder-filter.png"), fullPage: true })
  console.log("Fix1 shareholder filter cards:", shareholderCards, shareholderCards === 2 ? "PASS" : "FAIL")

  // select all 3 templates for variable step
  await page.getByRole("button", { name: "全部" }).click()
  for (const name of ["律所签字页", "自然人股东签字页", "机构股东签字页"]) {
    await page.locator("h3", { hasText: name }).locator("xpath=ancestor::div[contains(@class,'flex-col')]//input[@type='checkbox']").check()
  }
  await page.getByRole("button", { name: "下一步" }).click()
  await page.waitForSelector("label:has-text('目标公司名称')")

  // fill one field, AI validate without clicking 下一步
  await page.locator("label").filter({ hasText: "目标公司名称" }).first().locator("xpath=following::input[1]").fill("测试科技股份有限公司")
  await page.locator("label").filter({ hasText: "签署日期" }).first().locator("xpath=following::input[1]").fill("2026-06-09")
  await page.locator("label").filter({ hasText: "律师事务所名称" }).first().locator("xpath=following::input[1]").fill("君合律师事务所")
  await page.getByRole("button", { name: "AI 校验" }).click()
  await page.waitForTimeout(8000)
  await page.screenshot({ path: path.join(SHOT, "fix-3.4-ai-validate-saved.png"), fullPage: true })

  const body = await page.locator("body").innerText()
  const falseMissing = body.includes("必填变量 target_company_name 未填写")
  console.log("Fix2 no false missing target_company_name:", !falseMissing, !falseMissing ? "PASS" : "FAIL")

  // cleanup
  await page.getByRole("link", { name: "返回列表" }).click()
  await page.getByRole("row", { name: /Fix验证-分类筛选/ }).getByRole("button", { name: "删除" }).click()
  await page.getByRole("button", { name: "确认删除" }).click()

  await browser.close()
}

main()
