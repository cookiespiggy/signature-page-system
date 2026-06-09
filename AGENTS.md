# 签字页管理系统 MVP — Agent 开发指南

> 这是项目的**唯一入口文档**。每次开始新的 Cursor session 时，先读此文件。
> 打开新 session → `@AGENTS.md` → 说"开始开发"即可。

---

## 一、项目概述

为律师事务所生成签字页 Word (.docx) 文件。MVP 核心流程：

```
创建项目 → 选择模板(多选) → 填写变量(去重) → 异步生成 → 下载
```

- 后端: Python FastAPI + SQLite + SQLAlchemy + Alembic
- 前端: React + TypeScript + Vite + Tailwind CSS + shadcn/ui
- 模板渲染: docxtpl (Jinja2)
- LLM: LLMProvider 抽象层（默认 MockProvider，可切换 OpenCode/OpenAI）

---

## 二、Session 状态机

当前 Session 记录在 `.handoff/latest.md` 中。每个 session 完成一个 Task，写一次 handoff。

### Session 依赖关系

```
Session 1a (后端初始化+数据层)
  └─> Session 1b (后端 API + LLM 抽象层)
        ├─> Session 2 (模板管理 + AI 解析)
        ├─> Session 3 (变量填写 + AI 去重校验)
        └─> Session 4 (文档生成 + 异步下载)
              └─> Session 5a-1 (前端初始化 + 列表页)
                    └─> Session 5a-2 (前端详情页)
                          └─> Session 5b (前端 AI 集成)
                                └─> Session 6 (联调测试)
                                      └─> Session 7 (报告)
```

### Session 清单

| # | 内容 | 产出文件 | 估计行数 |
|---|------|---------|---------|
| 1a | 后端脚手架 + 数据模型 + Alembic + variable_registry | database.py, models.py, alembic/, variable_registry.py | ~200 |
| 1b | LLMProvider 抽象层 + 项目 CRUD API + health check | llm/, routers/, schemas.py, main.py, ai_service.py | ~300 |
| 2 | 3 个 Word 模板 + 模板管理 API + AI 解析 | templates/*.docx, routers/templates.py, template_service.py | ~400 |
| 3 | 变量去重/保存/Excel/AI 去重校验 API | routers/variables.py, variable_service.py | ~400 |
| 4 | 异步生成 ThreadPoolExecutor + 取消 + 下载 | generation_service.py, routers/generation.py | ~300 |
| 5a-1 | 前端初始化 + 项目列表页 | frontend/ 脚手架, src/pages/ListPage.tsx | ~300 |
| 5a-2 | 前端三步流程详情页 | src/pages/DetailPage.tsx + components/ | ~500 |
| 5b | 前端 AI 功能集成 | AI 相关组件 | ~200 |
| 6 | 联调 + pytest | tests/ | ~200 |
| 7 | 报告 | 报告文件 | ~50 |

---

## 三、每 Session 开始时的指令

当你读到这条消息时，请按以下顺序执行：

```markdown
1. 先读取 `.handoff/latest.md` 了解当前状态
2. 读取 AGENTS.md 中对应 Session 的详细要求
3. 读取 `.cursor/rules/` 下的规则文件
4. **检查环境就绪**（参见「九、知识索引」→ 环境配置）
   - 确认 `.venv` 存在且与当前 OS 匹配（macOS vs Linux VM）
   - 如果后端需要 LLM，检查 OpenCode Server / Mock 配置
5. 根据最新方案文档 `docs/specs/签字页管理系统 MVP 实现方案.md` 中的详细设计实现
6. 实现完毕后：
   a. 验证 DoD（完成标准）
   b. 更新 `.handoff/latest.md`（写入完成内容、文件变更、当前状态）
   c. 告知用户"Session X 已完成，可以开始下一个 Session"
```

---

## 四、每个 Session 的详细要求

### Session 1a: 后端初始化与数据层

**产物**：
- `backend/app/database.py` — SQLite + WAL 模式，DATABASE_URL 环境变量
- `backend/app/models.py` — 所有 SQLAlchemy 模型
- `backend/alembic/` — Alembic 迁移（render_as_batch=True）
- `backend/app/services/variable_registry.py` — 变量映射表

**models.py 需包含以下 Entity**（参考方案文档「数据模型」章节）：
- Project: id, name, status, created_at, updated_at
- Template: id, name, description, category, tags(JSON), applicable_scenarios, is_preset, file_path, variables_json(JSON), version, preview_image, created_at, updated_at
- ProjectTemplate: id, project_id, template_id, template_version, variables_snapshot_json(JSON)
- Variable: id, project_id, key, label, value, data_type, category, is_multiple, required, sort_order, source_template_ids(JSON), is_merged, merged_from_keys(JSON), updated_at
- CustomVariable: id, key, label, category, data_type, aliases(JSON), created_by_template_id, created_at
- GenerationTask: id, project_id, status, total_count, completed_count, error_message, created_at, updated_at, completed_at, cancelled_at
- GeneratedFile: id, project_id, template_id, file_path, status, created_at
- AILog: id, project_id, ai_type, prompt, response, duration_ms, validation_result, user_action, created_at

**variable_registry.py 需包含**（参考方案「策略1」章节的数据）：
- VARIABLE_REGISTRY 字典
- VALIDATION_RULES 字典
- TEMPLATE_VARIABLE_MAP 字典

**DoD**：
- `alembic upgrade head` 成功创建所有表
- database.py 连接 SQLite 正常
- variable_registry.py 可 import 无报错

---

### Session 1b: LLM 抽象层 + 项目 API

**产物**：
- `backend/app/services/llm/` — LLMProvider 抽象层
- `backend/app/services/ai_service.py` — AI 编排服务
- `backend/app/schemas.py` — Pydantic schemas
- `backend/app/routers/projects.py` — 项目 CRUD
- `backend/app/main.py` — FastAPI 入口 + CORS

**llm/ 目录结构**：
- base.py: LLMProvider 抽象基类（send_message）
- opencode_provider.py: OpenCode Server 实现
- openai_provider.py: OpenAI API 实现
- mock_provider.py: Mock 实现
- mock_responses.py: Mock 预设数据
- factory.py: 环境变量创建 Provider

**API 路由**（参考方案「核心 API」章节）：
- GET/POST /api/projects
- GET/PUT/DELETE /api/projects/{id}
- GET /api/health

**schemas.py 需包含**：
- 请求/响应的 Pydantic 模型
- 统一错误响应格式（success/errors/summary）

**ai_service.py 需包含**：
- call_llm_structured() 封装（超时 + 重试 3 次 + 降级）
- 三个 AI 场景占位方法

**DoD**：
- `uv run uvicorn app.main:app --reload` 启动成功
- GET /api/health 返回 200
- 项目 CRUD 全部可调用

---

### Session 2: 模板管理 + AI 解析

**产物**：
- `backend/app/templates/*.docx` — 3 个预置 Word 模板
- `backend/app/routers/templates.py` — 模板 API
- `backend/app/services/template_service.py` — 模板业务逻辑

**API 路由**：
- GET /api/templates
- GET /api/templates/{id}
- POST /api/templates — 创建自定义模板
- PUT /api/templates/{id} — 更新模板（AI 重新解析 + version++）
- DELETE /api/templates/{id}（预置返回 403）
- POST /api/templates/parse — AI 解析模板
- POST /api/projects/{id}/templates — 为项目选模板
- DELETE /api/projects/{id}/templates/{template_id} — 移除模板（清理 Variable）
- POST /api/projects/{id}/templates/{template_id}/refresh — 刷新模板版本

**预置模板变量**（参考方案「策略1」TEMPLATE_VARIABLE_MAP）：
- 模板1 "律所签字页": target_company_name, law_firm_name, law_firm_director, handling_lawyer, signing_date, exchange_name, document_type, target_investor_type
- 模板2 "自然人股东签字页": natural_shareholder_name, natural_shareholder_id_number, target_company_name, meeting_year, meeting_session, signing_date
- 模板3 "机构股东签字页": institutional_shareholder_name, authorized_representative_name, target_company_name, meeting_year, meeting_session, signing_date

**key 设计要点**：
- 模板内占位符使用 `{{key}}`（如 `{{law_firm_director}}`）
- 预置模板的 key 已定义，直接使用即可
- 自定义模板的 key 由 AI 解析时生成

**项目-模板关联关键逻辑**：
- 选模板时创建 ProjectTemplate 记录 + variables_snapshot_json 快照
- 自动触发变量去重：按 key 精确匹配合并
- 移除模板时清理 source_template_ids，为空时删除变量
- 刷新模板时 diff 算法：新增变量创建行、删除变量清理、保留变量不动

**DoD**：
- 3 个预置模板可列表查看
- 上传 + AI 解析流程可走通
- 模板刷新后变量 diff 正确

---

### Session 3: 变量填写 + AI 去重 + 校验

**产物**：
- `backend/app/routers/variables.py` — 变量 API
- `backend/app/services/variable_service.py` — 变量业务逻辑

**API 路由**：
- GET /api/projects/{id}/variables
- PUT /api/projects/{id}/variables（逐行乐观锁）
- POST /api/projects/{id}/variables/ai-dedup
- POST /api/projects/{id}/variables/ai-validate
- POST /api/projects/{id}/variables/import-preview
- POST /api/projects/{id}/variables/import
- GET /api/projects/{id}/variables/export-template
- GET /api/projects/{id}/variables/export

**乐观锁实现要点**：
- 每行变量携带 updated_at，后端逐行比对
- 成功的行写入，冲突的行返回错误报告
- 不整体回滚，复用统一错误响应格式

**多值变量处理**：
- multiple=True 的变量存为多行 key_1, key_2, ...
- 前端动态添加/删除行，默认 2 行
- 生成时组装为列表传入 docxtpl

**DoD**：
- 变量保存逐行校验可验证
- Excel 导入预览→确认导入可走通
- AI 去重/校验可调用或降级

---

### Session 4: 文档生成 + 异步下载

**产物**：
- `backend/app/services/generation_service.py` — 异步生成服务
- `backend/app/routers/generation.py` — 生成 API

**异步模型**（参考方案「5.5 异步生成的线程模型」）：
- ThreadPoolExecutor(max_workers=2)，全局实例
- 每个任务关联 threading.Event 用于取消
- 每个 worker 线程用独立 SQLAlchemy Session
- 每完成一个文件检查 cancel_event + DB 状态
- 取消时清理部分文件、更新状态、正常退出

**API 路由**：
- POST /api/projects/{id}/generate
- POST /api/projects/{id}/generate/cancel
- GET /api/projects/{id}/generate/status
- GET /api/projects/{id}/files
- GET /api/files/{id}/download
- GET /api/projects/{id}/download-all

**文件存储**（参考方案「5. 文件存储策略」）：
- `{GENERATED_DIR}/{project_id}/` 目录下
- 命名: `{template_name}_{uuid4_short}.docx`
- ZIP: `{GENERATED_DIR}/{project_id}/zip/{project_name}_all_{timestamp}.zip`

**DoD**：
- 选择模板 + 填变量后可成功生成 Word
- 取消生成可中止任务
- 单文件/ZIP 下载可用

---

### Session 5a-1: 前端初始化 + 项目列表页

**产物**：
- `frontend/` — React + TS + Vite 项目
- 配置 Tailwind CSS + shadcn/ui
- 配置 Vite 代理 /api → :8000
- 配置 react-router-dom 路由
- 封装 services/api.ts（统一 Loading/Error/Success）
- 配置 React Error Boundary
- 实现项目列表页（新建、列表、删除）

**前后端对接策略**：
- 后端未 ready 时使用 mock 数据开发 UI
- 后端 ready 后切换为真实 API

**DoD**：
- 项目列表 CRUD 可走通
- Error Boundary 正常
- API 层封装正确

---

### Session 5a-2: 前端详情页（三步流程）

**产物**：
- `frontend/src/pages/DetailPage.tsx` — 项目详情页
- `frontend/src/components/` — 业务组件

**Step 1: 模板选择**
- 卡片网格展示模板库（名称、分类、适用场景、变量数）
- 支持多选、搜索、分类筛选
- 预置/自定义徽标
- 上传自定义模板（触发 AI 解析）
- 移除模板 + 模板更新刷新按钮
- 详情展开（变量列表 + 元数据）

**Step 2: 变量填写**
- 按 category 分组，组内 sort_order 排序
- 相同 key 只显示一个输入框（去重）
- multiple 变量：动态增删行，默认 2 行
- 基础正则实时校验（身份证号、公司名、日期）
- Excel 导入/导出按钮
- AI 去重按钮 + 校验按钮
- beforeunload 防丢策略

**Step 3: 生成下载**
- 生成前变量确认弹窗（key→value 对照表）
- 生成按钮 + 指数退避进度轮询（2s→4s→8s→max 10s）
- 取消按钮
- 文件列表 + 单个/ZIP 下载

**步骤流转**：
- Step 1 → Step 2: 选模板后调用 API 保存，自动去重
- Step 2 → Step 3: 填写变量后调用 API 保存
- 回退不丢数据

**DoD**：
- 三步流程可走通
- 回退不丢数据
- multiple 变量可动态增减

---

### Session 5b: 前端 AI 功能

**产物**：
- AI 解析结果展示（AI 标签 + 确认/修正/删除）
- AI 去重建议卡片（逐条采纳/拒绝）
- AI 校验报告（error/warning 分级）
- AI 加载动画与降级提示

**DoD**：
- 三个 AI 场景均可展示
- 降级提示正常
- AI 结果可采纳/拒绝

---

### Session 6: 联调测试

- 启动前后端
- 完整流程测试
- 后端 pytest 集成测试
- 验证乐观锁、模板刷新、删除级联
- 修复所有 P0/P1
- **联调结束后清理 dev 进程**（uvicorn + Vite，避免端口占用）

**DoD**：
- 端到端流程可走通
- 所有 pytest 通过
- 联调临时进程已 kill，:8000 / :5173 无残留

---

### Session 7: 报告

- 编写 AI 参与环节说明报告

---

## 五、Handoff 规范

每个 Session 结束时，**必须更新 `.handoff/latest.md`**，格式如下：

```markdown
# Session Handoff: [Session 编号] - [名称]

## 已完成
- [具体完成的内容]

## 文件变更
- `backend/app/models.py` — 新增了 [内容]
- `backend/app/database.py` — 修改了 [内容]

## 当前状态
- 启动命令正常工作
- 已验证的功能
- 未完成的点

## 遗留问题
- [问题描述]

## 下一个 Session
继续 Session [编号]: [名称]
需要读取此 handoff + AGENTS.md 中对应章节
```

---

## 六、关键设计决策（沿用不讨论）

以下决策已在方案中确定，实现时直接遵循，**不需要重新讨论**：

- 变量 key 为英文 snake_case，label 为中文显示名
- 多值变量存为多行（key_1, key_2, ...）
- 异步生成用 ThreadPoolExecutor + threading.Event，不用 BackgroundTasks
- SQLAlchemy Session 每个 worker 线程独立创建
- 预置模板不可删除（403），自定义模板可删除
- OpenCode Provider 为默认 LLM Provider（`LLM_PROVIDER=mock` 可切回 Mock）
- 文件存在 `GENERATED_DIR/{project_id}/` 下
- Alembic 迁移使用 render_as_batch=True
- 前端仅用 React 内置状态管理，不引入 Redux/Zustand

---

## 七、快速参考

### 启动命令
```bash
# 0. 若 uv run 报 ModuleNotFoundError: No module named 'python'，说明 .venv 在 macOS 创建，需在 VM 内重建：
orb -m oh-agent bash -lc 'cd backend && rm -rf .venv && uv sync'

# 1. 先确保 OpenCode Server 在运行（仅在首次启动或重启 VM 时需要）
orb -m oh-agent bash -lc 'nohup /home/jimmy/.opencode/bin/opencode serve --port 4096 > /dev/null 2>&1 &'

# 2. 后端（在 oh-agent VM 内运行，--host 0.0.0.0 供宿主机 Vite 代理访问）
orb -m oh-agent bash -lc 'cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000'

# 3. 前端（宿主机直接运行；.env.development 中 VITE_API_PROXY_TARGET 指向 VM IP）
cd frontend && npm run dev

# 如需切回 Mock（如离线环境）
# orb -m oh-agent bash -lc 'cd backend && LLM_PROVIDER=mock uv run uvicorn app.main:app --host 0.0.0.0 --port 8000'

# 4. 联调结束后清理（避免残留进程占用端口，详见 docs/knowledge-base/环境配置.md）
orb -m oh-agent bash -lc 'pkill -f "uvicorn app.main:app"'
pkill -f "vite" 2>/dev/null
```

### 数据库
```bash
orb -m oh-agent bash -lc 'cd backend && uv run alembic upgrade head'    # 执行迁移
orb -m oh-agent bash -lc 'cd backend && uv run alembic revision --autogenerate -m "描述"'  # 生成新迁移
```

### 环境变量
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:///./data/junhe.db` | 数据库连接 |
| `LLM_PROVIDER` | `opencode` | LLM 提供方：`opencode`/`mock`/`openai` |
| `GENERATED_DIR` | `data/generated` | 生成文件目录 |

---

## 八、知识索引

> 项目文档统一存放在 `docs/` 下：
> - `docs/specs/` — 产品/设计文档（方案、PRD、模板样例）
> - `docs/knowledge-base/` — 开发经验沉淀（踩坑、配置、最佳实践）

### 环境与部署
| 文件 | 内容 | 何时查阅 |
|------|------|---------|
| [`docs/knowledge-base/环境配置.md`](docs/knowledge-base/环境配置.md) | `.venv` 跨平台、场景矩阵、环境变量 | session 开始时检查环境 |
| [`docs/knowledge-base/OpenCode-Server.md`](docs/knowledge-base/OpenCode-Server.md) | OpenCode 安装、API 要点、启动/验证/端到端测试 | LLM 相关 session |

### 架构与设计
| 文件 | 内容 | 何时查阅 |
|------|------|---------|
| [`docs/knowledge-base/结构化输出.md`](docs/knowledge-base/结构化输出.md) | JSON Schema 策略、mimo-v2.5-free 原生支持 | 涉及 AI 解析的 session |
| [`docs/knowledge-base/UI设计规范.md`](docs/knowledge-base/UI设计规范.md) | 黑金律所 UI Token、布局组件、Agent Checklist | **任何前端 Session（5a-2 / 5b 及后续）** |

### 产品规格（`docs/specs/`）
| 文件 | 内容 | 何时查阅 |
|------|------|---------|
| [`docs/specs/签字页管理系统 MVP 实现方案.md`](docs/specs/签字页管理系统%20MVP%20实现方案.md) | 详细技术方案、数据模型、API 路由 | Session 实现时参考 |
| [`docs/specs/签字页 PRD.md`](docs/specs/签字页%20PRD.md) | 产品需求与功能描述 | 理解业务背景 |
| [`docs/specs/签字页模版样例.md`](docs/specs/签字页模版样例.md) | 模板示例变量说明 | 模板管理相关 session |
