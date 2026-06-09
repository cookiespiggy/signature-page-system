# 签字页管理系统 MVP — AI 参与环节说明报告

> Session 7 交付物。涵盖**开发过程**中使用的 AI 工具（含 E2E UI 自动化测试实践），以及**系统内置**的 AI 能力设计。

---

## 一、开发过程中的 AI 工具使用

### 1.1 主要工具

| 工具 | 用途 | 参与环节 |
|------|------|---------|
| **Cursor Agent** | 按 Session 分阶段实现全栈功能、联调与修复 | 后端 API、前端 UI、pytest、Playwright E2E、README 演示录屏、文档 |
| **agent-browser** | AI Agent 探索式 UI 操控（Vercel Labs CLI） | 演示方案调研、DOM 结构摸底（见 §1.6） |
| **Claude Code** | 每个 Session 交付后的代码 Review + 问题修复 | 质量把关、补漏、重构、验收补强 |
| **AGENTS.md + Handoff** | 定义 Session 边界、DoD、技术决策，跨 Session 传递上下文 | 全部 7 个 Session 的编排与验收 |
| **OpenCode Server** | 开发/联调时调用真实 LLM（`github-copilot/gpt-5-mini` 等） | AI 场景端到端验证 |
| **MockProvider** | 离线开发与 CI 测试，不依赖外部 LLM | pytest、无网络环境 |

### 1.2 开发模式

采用 **Session 状态机**（见 `AGENTS.md`）：每个 Session 聚焦单一交付物，完成后写入 `.handoff/latest.md`。AI Agent 在每个 Session 开始时读取 handoff + 方案文档 + 知识库，避免重复讨论已确定的设计决策。

每个 Session 的完整 AI 协作闭环：

```
Cursor Agent 实现 → DoD 自验（pytest / build）→ 写入 Handoff
        ↓
Claude Code Review（对照方案/PRD/DoD 审查 diff）
        ↓
发现问题 → Claude Code 修复 → 复验 → 更新 Handoff（如 Session 6b 验收补强）
```

**Cursor Agent** 与 **Claude Code** 分工不同、前后衔接：

| 阶段 | 执行者 | 典型工作 |
|------|--------|---------|
| 实现 | Cursor Agent | 按 Session 范围写代码、跑测试、写 handoff |
| Review | Claude Code | 对照方案审查实现缺口、边界条件、一致性、可维护性 |
| 修复 | Claude Code | 直接改代码修复 Review 发现的问题，必要时补充测试 |
| 验收补强 | Claude Code | PRD/DoD 严格项未覆盖时追加实现（如 Session 6b：生成日志、子集分组、校验联动） |

AI 在开发中的典型分工：

- **代码生成**（Cursor Agent）：按方案文档实现模型、API、前端组件
- **联调排错**（Cursor Agent / Claude Code）：根据 pytest 失败与 API 响应定位问题
- **质量 Review**（Claude Code）：Session 收尾时独立审视本轮 diff，避免实现 Agent 的自确认盲区
- **知识沉淀**：将踩坑经验写入 `docs/knowledge-base/`（环境配置、结构化输出、AI 可信机制等），并同步沉淀为项目级 **Cursor Skills**（见 §1.5）
- **E2E UI 自动化**（Cursor Agent + Playwright）：见 §1.4
- **README 演示录屏**（Cursor Agent + Playwright + agent-browser 调研）：见 §1.6

### 1.3 人工决策保留项

以下由人类（或 Agent 在 handoff 中记录的共识）拍板，AI 不自行变更：

- V2 延后：登录鉴权、PDF 输出、套表组 TemplatePack
- 子集小组用 `template.category` 轻量分组，不引入新数据模型
- 生成日志扩展 `GET /generate/status`，无需 DB 迁移
- 实时校验：正则 + 必填内联；AI 校验手动触发

### 1.4 AI 驱动的 E2E UI 自动化测试实践

Session 6 联调以 **pytest 集成测试 + 手工点验** 为主；Session 7 补充由 Cursor Agent **自主编写并执行** Playwright 全流程 UI 自动化，覆盖从创建项目到删除的完整用户旅程，并产出截图证据与结构化报告。

#### 1.4.1 工具链与环境

```
Cursor Agent 设计用例 → 生成 Playwright 脚本 (.mjs)
        ↓
宿主机 Chromium headless 访问 localhost:5173（Vite 前端）
        ↓
API 代理至 oh-agent VM :8000（FastAPI 后端 + SQLite）
        ↓
每步全页截图 → 合并结果 → 自动生成 e2e-test-results/report.md
```

| 组件 | 说明 |
|------|------|
| **Playwright** | `e2e-test-results/package.json`，headless Chromium，viewport 1440×900 |
| **脚本** | `continue-e2e.mjs`（Phase 3 续跑至 Phase 6）、`continue-e2e-phase4.mjs`（Phase 4 独立续跑） |
| **截图** | `e2e-test-results/screenshots/`，25 张全页 PNG，按测试编号命名 |
| **报告** | `e2e-test-results/report.md`，脚本末尾自动写入 PASS/FAIL/DEGRADED 汇总表 |

#### 1.4.2 AI Agent 的分工

与传统「人工写用例、人工点页面」不同，本轮 E2E 中 AI 承担了完整闭环：

| 环节 | AI 所做 | 人工介入 |
|------|---------|---------|
| 用例设计 | 对照 PRD 三步流程，拆分为 6 个 Phase、23 项检查点 | 无 |
| 脚本编写 | 生成 Playwright 选择器、填表逻辑、异步轮询、下载断言 | 无 |
| 执行调试 | 启动浏览器、处理步骤跳转失败、调整等待策略 | 确认前后端已启动 |
| 跨 Session 接力 | 前序 agent 完成 Phase 1–2 后，续跑脚本从 `PROJECT_ID=8` 断点恢复 | 无 |
| 缺陷记录 | 根据截图与页面文本自动标注 FAIL / DEGRADED 并写入报告 | 评审是否修 bug |

#### 1.4.3 测试覆盖矩阵

| Phase | 范围 | 关键断言 |
|-------|------|---------|
| 1 项目列表 | 页面加载、新建项目、进入详情 | 黑金 UI、三步导航 Step1 高亮 |
| 2 模板选择 | 列表渲染、搜索、分类筛选、多选、详情展开、进入 Step 2 | 3 个预置模板可选中；搜索「律所」仅 1 条 |
| 3 变量填写 | 分组渲染、填表、AI 去重、AI 校验、进入 Step 3 | 同 key 去重；AI 降级 Banner；校验报告展示 |
| 4 生成下载 | 确认弹窗、异步生成、文件列表、ZIP 下载 | 3/3 完成；预览/下载按钮；ZIP 文件名 |
| 5 步骤回退 | 回退 Step 2 / Step 1 | 变量值保留；模板 checkbox 仍选中 |
| 6 清理 | 返回列表、删除项目 | 确认对话框；列表行消失 |

#### 1.4.4 脚本实现要点（AI 自行摸索的策略）

前端未预埋 `data-testid`，Agent 采用了以下**可读 DOM 驱动**策略：

- **按钮**：`page.getByRole("button", { name: "生成签字页" })` 等语义化 role
- **填表**：`label` 中文文本定位 → `following::input` 或 `ancestor::div` 找输入框；多值变量（经办律师）按行 `nth()` 填写
- **异步生成**：`waitForGeneration()` 轮询 body 文本（`3 / 3`、`文档生成完成`）或下载按钮数量，最长 35s
- **AI 场景**：单独状态 `DEGRADED`（LLM 不可用时降级 Banner），与功能 `FAIL` 区分
- **报告合并**：续跑脚本将前序 agent 的 Phase 1–2 结果硬编码合并，避免重复执行（类 Handoff 模式）

#### 1.4.5 执行结果与发现

| 指标 | 数值 |
|------|------|
| 通过 | 21 / 23 |
| 失败 | 1（Test 2.3 分类筛选「股东」无结果） |
| AI 降级 | 1（Test 3.3 AI 去重，OpenCode 不可用） |
| 执行时间 | 2026-06-09 |

AI 自动化**额外发现**的两处问题（pytest 未覆盖的 UI 层）：

1. **分类筛选 bug**：点击「股东」显示「未找到匹配的模板」，但「自然人股东签字页」「机构股东签字页」应可见（`category` 字段与前端筛选逻辑不一致）
2. **AI 校验误报**：表单已填值，校验报告仍报 11 条「必填变量未填写」；不影响保存与生成，属 AI-3 与表单状态同步问题

完整报告与截图见 `e2e-test-results/report.md`。

#### 1.4.6 与 pytest E2E 的关系

| 维度 | pytest `test_e2e_flow.py` | Playwright UI E2E |
|------|---------------------------|-------------------|
| 层次 | API + 业务逻辑 | 真实浏览器 DOM 交互 |
| 运行环境 | VM 内 `uv run pytest` | 宿主机 Node + Playwright |
| AI 参与 | Mock Provider 测 AI API | Agent 写脚本 + 点「AI 去重/校验」按钮 |
| 证据 | 断言通过/失败 | 每步全页截图 + Markdown 报告 |
| 价值 | CI 可重复、无 UI 依赖 | 验证黑金 UI、弹窗、toast、降级 Banner 等视觉/交互层 |

两者互补：pytest 保证后端契约稳定；Playwright E2E 由 AI 快速补齐**前端真实用户路径**的回归能力，且无需人工逐页点击。

### 1.6 README 操作流程演示录屏（AI 驱动交付）

MVP 交付后，需让访问 GitHub 仓库的用户**无需本地启动**即可直观了解产品流程。Cursor Agent 自主完成「工具选型 → UI 走查 → 录屏 → 格式适配 → 推送 README」闭环。

#### 1.6.1 背景与目标

| 目标 | 说明 |
|------|------|
| 受众 | 仓库访客、评审方、新成员 |
| 载体 | `README.md` 首页「操作流程演示」区块 |
| 内容 | MVP 全流程：列表 → 新建 → 选模板 → 填变量 → AI 去重/校验 → 生成 → ZIP 下载 |
| 约束 | 视频需在 GitHub 首页稳定可见；不污染宿主机环境（后端仍在 oh-agent VM） |

#### 1.6.2 agent-browser 探索 vs Playwright 录屏（AI 决策）

Agent 首先按用户要求使用 [agent-browser](https://github.com/vercel-labs/agent-browser)（Vercel Labs 出品的 AI 向浏览器 CLI）进行**探索式走查**：

```
agent-browser open → snapshot -i（获取 @e1 @e2 可交互 ref）
        ↓
click / fill / check / eval（逐步摸清三步流程 DOM）
        ↓
发现：React 受控组件（签署日期）、ref 随页面变化、无内置录屏
```

| 维度 | agent-browser | Playwright（最终选用） |
|------|---------------|------------------------|
| 定位方式 | snapshot `@eN` ref，页面一变即失效 | `getByRole` / `label` 中文文本，与 §1.4 E2E 一致 |
| React 表单 | 日期等需 `InputEvent` hack | `fill()` 原生触发 onChange |
| 录屏 | 需额外 ffmpeg 系统录屏 | `recordVideo` 内置，输出 `.webm` |
| 适用场景 | **AI 未知 UI 时现场探索** | **确定性演示 / 可重复脚本** |
| 项目集成 | 零依赖，全局 `npm i -g` | `e2e-test-results` 已有 Playwright |

**AI 结论**：演示录屏属于固定流程、需稳定复现 → 选用 Playwright；agent-browser 的探索结论（如 `#var-field-signing_date` 需 `InputEvent`）反哺了脚本中对日期字段的处理策略。

#### 1.6.3 交付物与 GitHub 展示策略

| 产物 | 路径 | 说明 |
|------|------|------|
| 录屏脚本 | `e2e-test-results/demo-walkthrough.mjs` | headed + `slowMo`，13 步全流程，内置 `recordVideo` |
| WebM 源片 | `e2e-test-results/demo/demo-recording.webm` | Playwright 原始输出（本地，未入库） |
| H.264 MP4 | `docs/assets/demo-walkthrough.mp4` | ffmpeg 转码，GitHub 兼容性最佳 |
| GIF 预览 | `docs/assets/demo-walkthrough.gif` | README **相对路径**引用，首页稳定自动播放 |
| 步骤报告 | `e2e-test-results/demo/walkthrough-report.md` | 13/13 PASS 记录 |
| Release | [demo-walkthrough](https://github.com/cookiespiggy/signature-page-system/releases/tag/demo-walkthrough) | MP4 下载兜底 |
| README | 根目录 `README.md` §操作流程演示 | GIF 主展示 + 折叠区 MP4 + Release 链接 |

GitHub README **不支持**仓库内相对路径的 `<video>` 内嵌播放；Agent 实测 `media.githubusercontent.com` 404 后，采用 **GIF 相对路径 + MP4 Release** 双轨策略，确保首页访客必能看到动图演示。

#### 1.6.4 AI Agent 分工

| 环节 | AI 所做 | 人工介入 |
|------|---------|---------|
| 工具调研 | 阅读 agent-browser 文档，安装 CLI，headed 模式逐步 snapshot | 确认使用本机 OrbStack 环境 |
| 走查摸底 | agent-browser 走完创建→生成全流程，记录卡点 | 无 |
| 方案决策 | 对比 agent-browser / Playwright，输出选型理由 | 确认「录屏演示用 Playwright」 |
| 脚本编写 | `demo-walkthrough.mjs`：填表、AI 按钮、生成轮询、ZIP 下载 | 无 |
| 格式转换 | webm → H.264 mp4 → 8fps GIF（`@ffmpeg-installer/ffmpeg`，仅 e2e 目录） | 无 |
| 推送发布 | 更新 README、创建 Release、`git push` 至 `main` | 无 |

#### 1.6.5 执行结果

| 指标 | 数值 |
|------|------|
| 演示步骤 | 13 / 13 PASS |
| 录屏时长 | 约 42s（GIF 与 MP4 同源） |
| MP4 体积 | 1.1 MB（H.264） |
| GIF 体积 | 4.2 MB（960px 宽，8fps） |
| 仓库 | `cookiespiggy/signature-page-system` |

复现命令（需前后端已启动）：

```bash
cd e2e-test-results && npm install
node demo-walkthrough.mjs
# 产出 demo/demo-recording.webm；转 MP4/GIF 见 README
```

#### 1.6.6 与 §1.4 E2E 测试的关系

| 维度 | §1.4 Playwright E2E | §1.6 演示录屏 |
|------|---------------------|---------------|
| 目的 | 回归测试、缺陷发现、截图证据 | 对外展示、README 首页演示 |
| 浏览器 | headless | headed + slowMo（可读节奏） |
| 断言 | PASS/FAIL/DEGRADED 报告 | 无硬性断言，侧重录屏完整性 |
| 终点 | 删除测试项目 | 保留项目，返回列表 |
| 共享能力 | 同一套 `getByRole` / `fillByLabel` 填表策略 | 复用 E2E 经验，降低脚本编写成本 |

### 1.5 项目级 Skills 知识沉淀

除 `docs/knowledge-base/` 长文归档外，本项目将关键领域知识进一步沉淀为 **Cursor Agent Skills**（`.cursor/skills/`），遵循 Cursor Skills 标准结构（`SKILL.md` + 可选 `reference.md`），使 Agent 能按场景**自动发现**并加载精简指令，而非每次全文检索 Markdown 文档。

#### 1.5.1 为什么从 knowledge-base 升级为 Skills

| 维度 | `docs/knowledge-base/*.md` | `.cursor/skills/*/SKILL.md` |
|------|---------------------------|----------------------------|
| 受众 | 人类阅读 + Agent 被动引用 | Agent 主动发现（`description` 触发词） |
| 粒度 | 完整踩坑叙事、较长 | 检查清单 + 可执行命令 + 关键决策 |
| 加载时机 | 需 Agent 记得去读 | 匹配场景时自动注入上下文 |
| 维护 | 单一源文档 | Skill 精简版 + knowledge-base 归档双轨同步 |

#### 1.5.2 Skills 清单

| Skill 名称 | 源文档 | 触发场景 |
|------------|--------|---------|
| `dev-environment` | `环境配置.md` | Session 启动、OrbStack VM、端口冲突、联调清理 |
| `opencode-server` | `OpenCode-Server.md` | LLM Provider 配置、OpenCode API 联调 |
| `structured-output` | `结构化输出.md` | `ai_service` / Provider 结构化 JSON |
| `ai-trust-guardrail` | `AI可信机制.md` | AI 三场景、Guardrail、可信等级 UI |
| `ui-design-system` | `UI设计规范.md` | 任何 `frontend/` 页面与组件开发 |

目录索引见 `.cursor/skills/README.md`。

#### 1.5.3 与 AGENTS.md / Handoff 的协作

```
Session 开始
    ↓
AGENTS.md（Session 边界 + DoD）+ .handoff/latest.md（上轮状态）
    ↓
Agent 按任务类型自动匹配 Skills（环境 / LLM / UI / Guardrail …）
    ↓
需要细节时读取 reference.md 或 docs/knowledge-base/ 原文
    ↓
Session 结束：新知识写入 knowledge-base → 同步更新对应 Skill
```

**维护约定**：踩坑或最佳实践变更时，先更新 `docs/knowledge-base/`，再精简同步到 `.cursor/skills/<name>/SKILL.md`（必要时更新 `reference.md`），保持双轨一致。

---

## 二、系统内置 AI 能力

### 2.1 架构总览

```
用户操作 → API 路由 → 业务 Service → ai_service.call_llm_structured()
                                              ↓
                                    LLMProvider（OpenCode / OpenAI / Mock）
                                              ↓
                                    ai_guardrail 交叉验证（trust_level）
                                              ↓
                                    前端展示建议 → 用户确认 → 写入数据库
```

**核心原则**：AI 不产生数据，只产生建议；经规则层、交叉验证层、人类确认层后才落地。（详见 `docs/knowledge-base/AI可信机制.md`）

### 2.2 三个 AI 场景

| 编号 | 场景 | 触发方式 | API | 降级策略 |
|------|------|---------|-----|---------|
| AI-1 | 自定义模板解析 | 上传 .docx 后自动调用 | `POST /api/templates/parse` | 返回空变量 + `ai_used=false`，用户手工录入 |
| AI-2 | 变量去重建议 | 用户点击「AI 去重」 | `POST /api/projects/{id}/variables/ai-dedup` | 仅展示规则别名建议（`alias_suggestions`） |
| AI-3 | 数据语义校验 | 用户点击「AI 校验」 | `POST /api/projects/{id}/variables/ai-validate` | 仅展示正则校验结果（`regex_issues`） |

#### AI-1：模板解析

- 从 docx 提取文本 → LLM 识别 `{{key}}` 占位符 → 输出 `key/label/category/data_type/required/is_multiple`
- 与 `VARIABLE_REGISTRY` 交叉验证，附加 `trust_level`（high/medium/low）
- 前端 `ParsedVariablesEditor`：AI 标签、可信等级徽标、逐条确认/修正/删除

#### AI-2：变量去重

- 规则层：`get_alias_dedup_suggestions()` 基于注册表别名，固定 HIGH 可信
- AI 层：语义合并建议（`keep_key` + `merge_keys` + `confidence`）
- 交叉验证：规则矛盾 → LOW；confidence < 0.5 → LOW
- 前端 `DedupSuggestionsPanel`：规则建议与 AI 建议分开展示，逐条采纳/拒绝

#### AI-3：数据校验

- 基础层：必填 + `VALIDATION_RULES` 正则，实时内联高亮
- AI 层：语义一致性（如角色冲突、名称重复）
- 合并策略：正则优先保留；AI 独有标记 `source=ai`；双方一致标记 `cross_validated=true`
- 前端 `ValidationReportPanel`：error/warning 分级，点击跳转字段高亮

### 2.3 LLM 抽象层

| 组件 | 路径 | 说明 |
|------|------|------|
| 抽象基类 | `backend/app/services/llm/base.py` | `send_message()` + `supports_structured_output` |
| OpenCode | `opencode_provider.py` | 默认 Provider；多模型 fallback（gpt-5-mini → mimo-v2.5-free） |
| OpenAI | `openai_provider.py` | 生产可选，Prompt 嵌入 Schema |
| Mock | `mock_provider.py` + `mock_responses.py` | 三场景预设 JSON |
| 工厂 | `factory.py` | `LLM_PROVIDER=opencode/mock/openai` |
| 编排 | `ai_service.py` | 超时 30s、重试 3 次、Pydantic 校验、降级抛 `AIServiceUnavailableError` |

结构化输出策略见 `docs/knowledge-base/结构化输出.md`：优先原生 `json_schema`；不支持时 Prompt 嵌入 Schema。

### 2.4 审计与日志

- **AILog 表**：记录 `ai_type`（`template_parse` / `variable_dedup` / `data_validate`）、prompt、response、validation_result
- **生成日志**：`GET /api/projects/{id}/generate/status` 返回 `template_progress` + `logs` 时间线（非 AI，但满足 PRD 可追溯要求）

### 2.5 前端 AI 交互组件

| 组件 | 职责 |
|------|------|
| `AiBadge` / `TrustLevelBadge` | 标注 AI 来源与可信等级 |
| `AiDegradedBanner` | LLM 不可用时的降级提示 |
| `ParsedVariablesEditor` | AI-1 解析结果编辑 |
| `DedupSuggestionsPanel` | AI-2 去重建议卡片 |
| `ValidationReportPanel` | AI-3 校验报告 + 字段定位 |

---

## 三、测试与验证

| 验证项 | 方式 | 结果 |
|--------|------|------|
| 后端集成测试 | `orb -m oh-agent bash -lc 'cd backend && uv run pytest tests/'` | 16 passed |
| Mock 模式 AI 场景 | `LLM_PROVIDER=mock` 跑 pytest | 三场景 API 可调用 |
| 前端构建 | `npm run build` | 成功 |
| API 端到端流程 | pytest `test_e2e_flow.py` | Session 6 已验收 |
| **UI 端到端（Playwright）** | Cursor Agent 编写 `e2e-test-results/*.mjs` 自动执行 | **21/23 PASS**，详见 §1.4 |
| **README 演示录屏** | Playwright `demo-walkthrough.mjs` + agent-browser 探索 | **13/13 PASS**，详见 §1.6；GIF/MP4 已嵌入 README |

复现 UI E2E（需前后端已启动，详见 `AGENTS.md` 快速参考）：

```bash
cd e2e-test-results && npm install
node continue-e2e-phase4.mjs   # 从已有项目断点续跑 Phase 4–6
node demo-walkthrough.mjs      # 全流程演示录屏（§1.6）
```

---

## 四、相关文档索引

| 文档 | 内容 |
|------|------|
| `.cursor/skills/README.md` | 项目级 Skills 索引与维护约定 |
| `.cursor/skills/*/SKILL.md` | Agent 可自动发现的精简领域指令 |
| `docs/knowledge-base/AI可信机制.md` | 三层防御、交叉验证逻辑 |
| `docs/knowledge-base/结构化输出.md` | LLM JSON Schema 策略与模型选型 |
| `docs/knowledge-base/OpenCode-Server.md` | OpenCode 安装与 API |
| `docs/knowledge-base/环境配置.md` | OrbStack VM、.venv 跨平台 |
| `docs/knowledge-base/UI设计规范.md` | 黑金律所 UI Token 与组件 |
| `docs/specs/签字页管理系统 MVP 实现方案.md` | 完整技术方案 |
| `e2e-test-results/report.md` | Playwright UI E2E 测试结果与截图索引 |
| `e2e-test-results/demo-walkthrough.mjs` | README 演示录屏脚本（§1.6） |
| `e2e-test-results/demo/walkthrough-report.md` | 演示录屏步骤报告 |
| `docs/assets/demo-walkthrough.gif` | README 首页 GIF 演示 |
| `docs/assets/demo-walkthrough.mp4` | H.264 高清演示视频 |
| `README.md` §操作流程演示 | GitHub 首页展示入口 |

---

*报告生成：Session 7 | 2026-06-09 | 含 Playwright E2E 自动化实践与 README 演示录屏（agent-browser 探索 + Playwright 交付）* 
