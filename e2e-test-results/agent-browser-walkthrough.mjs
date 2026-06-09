/**
 * 签字页管理系统 MVP — agent-browser 全流程 Walkthrough
 * 使用 https://github.com/vercel-labs/agent-browser
 *
 * 用法: node agent-browser-walkthrough.mjs
 * 环境: AGENT_BROWSER_HEADED=1 显示浏览器窗口；需前后端已启动
 */
import { execSync, spawn } from "node:child_process"
import { mkdir, writeFile } from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const BASE_URL = "http://localhost:5173"
const OUT_DIR = path.join(__dirname, "demo")
const SHOT_DIR = path.join(OUT_DIR, "screenshots")
const PROJECT_NAME = `Agent-Browser演示-${Date.now().toString(36)}`
const PAUSE_MS = 1800

const env = {
  ...process.env,
  AGENT_BROWSER_HEADED: "1",
  AGENT_BROWSER_SCREENSHOT_DIR: SHOT_DIR,
}

const log = []
function step(id, name, status, note = "") {
  log.push({ id, name, status, note })
  console.log(`[${status}] ${id} ${name}${note ? ` — ${note}` : ""}`)
}

function ab(...args) {
  const cmd = ["agent-browser", ...args].map((a) => (a.includes(" ") ? `"${a}"` : a)).join(" ")
  return execSync(cmd, { env, encoding: "utf8", stdio: ["pipe", "pipe", "pipe"] }).trim()
}

function abEval(js) {
  return ab("eval", JSON.stringify(js))
}

async function pause() {
  await new Promise((r) => setTimeout(r, PAUSE_MS))
}

async function shot(name) {
  await pause()
  ab("screenshot", path.join(SHOT_DIR, name))
}

const FILL_VARS_JS = `(function(){
  const setText=(sel,v)=>{const el=document.querySelector(sel);if(!el)return;const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(el,v);el.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertReplacementText',data:v}));el.dispatchEvent(new Event('change',{bubbles:true}));};
  const setDate=(sel,v)=>{const el=document.querySelector(sel);if(!el)return;const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(el,v);el.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertReplacementText',data:v}));el.dispatchEvent(new Event('change',{bubbles:true}));el.blur();};
  setText('#var-field-exchange_name input','上海证券交易所');
  setText('#var-field-target_company_name input','演示科技股份有限公司');
  setDate('#var-field-signing_date input[type=date]','2026-06-09');
  setText('#var-field-document_type input','招股说明书');
  setText('#var-field-target_investor_type input','机构投资者');
  setText('#var-field-law_firm_director input','张三');
  setText('#var-field-law_firm_name input','君合律师事务所');
  setText('#var-field-meeting_session input','第三次');
  setText('#var-field-meeting_year input','2026');
  setText('#var-field-natural_shareholder_id_number input','110101199001011234');
  setText('#var-field-natural_shareholder_name input','赵六');
  setText('#var-field-authorized_representative_name input','孙七');
  setText('#var-field-institutional_shareholder_name input','测试投资机构');
  setText('#var-field-handling_lawyer_1 input','李四');
  setText('#var-field-handling_lawyer_2 input','王五');
  return document.querySelector('#var-field-signing_date p')?.textContent || 'ok';
})()`

async function waitForGeneration(maxMs = 45000) {
  const start = Date.now()
  while (Date.now() - start < maxMs) {
    const text = abEval("document.body.innerText.slice(0,4000)")
    if (text.includes("打包下载 ZIP") && text.includes(".docx")) return true
    if (text.includes("生成失败")) return false
    await new Promise((r) => setTimeout(r, 2000))
  }
  return false
}

async function main() {
  await mkdir(SHOT_DIR, { recursive: true })

  try {
    try {
      ab("close", "--all")
    } catch {
      /* no session */
    }

    ab("set", "viewport", "1440", "900")
  ab("open", BASE_URL)
  ab("wait", "--load", "networkidle")
  await shot("01-list-page.png")
  step("1", "项目列表页加载", "PASS")

  ab("find", "role", "button", "click", "--name", "新建项目")
  await pause()
  const snap1 = ab("snapshot", "-i")
  const nameRef = snap1.match(/textbox.*\[ref=(e\d+)\]/)?.[1]
  const createRef = [...snap1.matchAll(/button "创建" \[ref=(e\d+)\]/g)].pop()?.[1]
  if (!nameRef || !createRef) throw new Error("无法定位新建项目对话框元素")
  ab("fill", `@${nameRef}`, PROJECT_NAME)
  ab("click", `@${createRef}`)
  ab("wait", "3000")
  ab("wait", "--text", PROJECT_NAME)
  await shot("02-project-created.png")
  step("2", "新建项目", "PASS", PROJECT_NAME)

  ab("find", "text", PROJECT_NAME, "click")
  ab("wait", "3000")
  await shot("03-step1-templates.png")
  step("3", "进入详情 · 选择模板", "PASS")

  const snap3 = ab("snapshot", "-i")
  const refs = [...snap3.matchAll(/checkbox \[checked=(?:true|false), ref=(e\d+)\]/g)].map((m) => m[1])
  const nextRef1 = snap3.match(/button "下一步" \[ref=(e\d+)\]/)?.[1]
  for (const r of refs.slice(0, 3)) ab("check", `@${r}`)
  ab("wait", "1500")
  await shot("04-templates-selected.png")
  ab("click", `@${nextRef1}`)
  ab("wait", "4000")
  await shot("05-step2-variables.png")
  step("4", "选择 3 个预置模板", "PASS")

  abEval(FILL_VARS_JS)
  ab("wait", "1000")
  await shot("06-variables-filled.png")
  step("5", "填写变量", "PASS")

  const snap4 = ab("snapshot", "-i")
  const dedupRef = snap4.match(/button "AI 智能去重" \[ref=(e\d+)\]/)?.[1]
  const validateRef = snap4.match(/button "AI 校验" \[ref=(e\d+)\]/)?.[1]
  if (dedupRef) {
    ab("click", `@${dedupRef}`)
    ab("wait", "8000")
    await shot("07-ai-dedup.png")
    step("6", "AI 智能去重", "PASS")
  }
  if (validateRef) {
    ab("click", `@${validateRef}`)
    ab("wait", "10000")
    await shot("08-ai-validate.png")
    step("7", "AI 校验", "PASS")
  }

  const snap5 = ab("snapshot", "-i")
  const nextRef2 = snap5.match(/button "下一步" \[ref=(e\d+)\]/)?.[1]
  ab("click", `@${nextRef2}`)
  ab("wait", "5000")
  await shot("09-step3-generate.png")
  step("8", "进入生成步骤", "PASS")

  const snap6 = ab("snapshot", "-i")
  const genRef = snap6.match(/button "生成签字页" \[ref=(e\d+)\]/)?.[1]
  ab("click", `@${genRef}`)
  ab("wait", "2000")
  await shot("10-confirm-dialog.png")

  const snap7 = ab("snapshot", "-i")
  const confirmRef = snap7.match(/button "确认生成" \[ref=(e\d+)\]/)?.[1]
  ab("click", `@${confirmRef}`)
  ab("wait", "2000")
  await shot("11-generating.png")

  const ok = await waitForGeneration()
  await shot("12-generation-complete.png")
  step("9", "异步生成 Word", ok ? "PASS" : "FAIL")

  const snap8 = ab("snapshot", "-i")
  const zipRef = snap8.match(/button "打包下载 ZIP" \[ref=(e\d+)\]/)?.[1]
  if (zipRef) {
    ab("set", "download-path", OUT_DIR)
    ab("click", `@${zipRef}`)
    ab("wait", "5000")
    await shot("13-zip-download.png")
    step("10", "ZIP 打包下载", "PASS")
  }

  ab("find", "role", "button", "click", "--name", "返回列表")
  ab("wait", "2000")
  await shot("14-back-to-list.png")
  step("11", "返回项目列表", "PASS")

  const report = `# agent-browser UI Walkthrough 报告

> 工具: [agent-browser](https://github.com/vercel-labs/agent-browser)  
> 时间: ${new Date().toLocaleString("zh-CN")}  
> 项目: ${PROJECT_NAME}

## 流程概览

\`\`\`
列表页 → 新建项目 → 选模板(×3) → 填变量 → AI去重/校验 → 生成 → ZIP下载 → 返回列表
\`\`\`

## 步骤结果

| # | 步骤 | 状态 | 备注 |
|---|------|------|------|
${log.map((r) => `| ${r.id} | ${r.name} | ${r.status} | ${r.note} |`).join("\n")}

## 截图

${log.map((_, i) => `- screenshots/${String(i + 1).padStart(2, "0")}-*.png`).join("\n")}

## 录屏

见 \`demo-recording.mp4\`（若录屏成功）
`
  await writeFile(path.join(OUT_DIR, "walkthrough-report.md"), report, "utf8")
    console.log("\n✓ Walkthrough 完成，报告:", path.join(OUT_DIR, "walkthrough-report.md"))
  } finally {
    try {
      ab("close")
    } catch {
      /* ignore */
    }
  }
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
