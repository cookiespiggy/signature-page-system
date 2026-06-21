# 签字页管理系统 MVP

为律师事务所智能聚合签字页变量、批量生成待签 Word (.docx) 文件的信息化系统。面向 IPO 上市等项目的律师及法务团队，将传统手工整理流程转变为标准化、批量化生产模式，显著降低错误率并缩短交付周期。

## 核心流程

```
创建项目 → 选择模板(多选) → 填写变量(去重) → 异步生成 → 下载
```

- **重复劳动**：股东 / 董监高 / 律师等信息在数十份模板中重复出现，系统按 key 去重合并，相同变量只填一次。
- **错误率高**：身份证号、公司名、日期等关键信息内置正则校验 + AI 交叉校验。
- **缺乏标准化**：模板库 + 变量映射表沉淀最佳实践，新人可快速上手。

## 操作流程演示

Playwright 自动录制的 MVP 全流程（列表 → 新建项目 → 选模板 → 填变量 → AI 去重/校验 → 生成 → ZIP 下载）：

![操作流程演示](docs/assets/demo-walkthrough.gif)

<details>
<summary>播放 MP4 高清版</summary>

<video src="https://raw.githubusercontent.com/cookiespiggy/signature-page-system/main/docs/assets/demo-walkthrough.mp4" width="960" controls></video>

</details>

也可 [下载 MP4](https://github.com/cookiespiggy/signature-page-system/releases/download/demo-walkthrough/demo-walkthrough.mp4)（[Releases · demo-walkthrough](https://github.com/cookiespiggy/signature-page-system/releases/tag/demo-walkthrough)）。

本地复现录屏：`cd e2e-test-results && node demo-walkthrough.mjs`（需前后端已启动）。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11+、FastAPI、SQLAlchemy 2.0、Alembic、SQLite (WAL) |
| 模板渲染 | docxtpl (Jinja2)、python-docx、openpyxl |
| 前端 | React 19 + TypeScript、Vite、Tailwind CSS v4、shadcn/ui |
| LLM | LLMProvider 抽象层（OpenCode / OpenAI / Mock 可切换） |
| 异步生成 | Temporal Workflow + Activity（支持取消、声明式重试、进程崩溃恢复）<br>Legacy: ThreadPoolExecutor + threading.Event |

## 项目结构

```
junhe-mvp/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 应用入口 + CORS
│   │   ├── models.py        # SQLAlchemy 数据模型
│   │   ├── database.py      # SQLite 连接 (WAL)
│   │   ├── schemas.py       # Pydantic schemas
│   │   ├── routers/         # projects / templates / variables / generation / health
│   │   ├── services/        # 业务逻辑
│   │   │   ├── llm/         # LLMProvider 抽象层 (opencode / openai / mock)
│   │   │   ├── ai_service.py        # AI 编排（解析 / 去重 / 校验）
│   │   │   ├── ai_guardrail.py      # AI 交叉验证护栏
│   │   │   ├── generation_service.py # 文档生成（Legacy ThreadPool 模式）
│   │   │   ├── variable_registry.py  # 变量映射表
│   │   │   └── ...
│   │   ├── temporal/        # Temporal Workflow 集成
│   │   │   ├── workflows/   # DocumentGenerationWorkflow / AIActivityWorkflow
│   │   │   ├── activities/  # 文档渲染 / 状态更新 / LLM 调用
│   │   │   ├── worker.py    # Worker 启动脚本
│   │   │   ├── client.py    # Temporal Client 单例
│   │   │   └── config.py    # 连接配置
│   │   └── templates/       # 3 个预置 Word 模板
│   ├── alembic/             # 数据库迁移
│   └── tests/               # pytest 集成测试
├── frontend/                # React + TS 前端
│   └── src/
│       ├── pages/           # ListPage（列表）/ DetailPage（三步流程）
│       ├── components/       # detail / ai / layout / ui
│       └── services/api.ts  # 统一 API 封装
├── docs/                    # 规格、知识库、交付报告
└── AGENTS.md                # 开发指南（开发者唯一入口）
```

## 主要功能

- **项目管理**：项目 CRUD。
- **模板管理**：3 个预置模板（律所 / 自然人股东 / 机构股东签字页），支持上传自定义模板并 AI 解析变量、模板更新刷新与变量 diff。
- **变量填写**：按 category 分组、去重展示，多值变量动态增减行，实时正则校验，Excel 导入 / 导出，逐行乐观锁保存。
- **AI 能力**：模板解析、变量去重建议、变量校验报告，均带降级提示与 AILog 审计。
- **异步生成与下载**：后台批量生成、进度轮询、任务取消、单文件 / ZIP 打包下载。

## 快速开始

### 后端环境准备

```bash
cd backend
uv sync                           # 安装 Python 依赖
uv run alembic upgrade head       # 初始化数据库
```

### 启动后端

```bash
# Legacy 模式（ThreadPoolExecutor，默认）
cd backend
uv run uvicorn app.main:app --port 8000

# Temporal 模式（推荐，需先启动 Temporal Server 和 Worker）
# 终端 1: Temporal Server
temporal server start-dev --db-filename /tmp/temporal-dev.db

# 终端 2: Temporal Worker
cd backend && uv run python -m app.temporal.worker

# 终端 3: FastAPI (Temporal 模式)
cd backend && USE_TEMPORAL=true uv run uvicorn app.main:app --port 8000

# 离线 / 无 LLM 环境可切 Mock
# LLM_PROVIDER=mock uv run uvicorn app.main:app --port 8000
```

健康检查：`GET http://localhost:8000/api/health`，API 文档：`http://localhost:8000/docs`。Temporal Web UI：`http://localhost:8233`。

### 启动前端

```bash
cd frontend
npm install
npm run dev    # 默认 http://localhost:5173
```

### 运行测试

```bash
cd backend && uv run pytest         # 后端集成测试
cd frontend && npm run build        # 前端类型检查 + 构建
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:///./data/junhe.db` | 数据库连接 |
| `LLM_PROVIDER` | `opencode` | LLM 提供方：`opencode` / `mock` / `openai` |
| `GENERATED_DIR` | `data/generated` | 生成文件目录 |
| `USE_TEMPORAL` | `false` | 启用 Temporal Workflow 模式（`true`/`false`） |
| `TEMPORAL_HOST` | `localhost` | Temporal Server 地址 |
| `TEMPORAL_PORT` | `7233` | Temporal Server gRPC 端口 |

## 文档索引

- `AGENTS.md` — 开发指南与 Session 状态机（开发者唯一入口）
- `docs/specs/` — 产品 PRD、实现方案、模板样例
- `docs/knowledge-base/` — 环境配置、OpenCode Server、结构化输出、UI 设计规范、AI 可信机制
- `docs/AI参与环节说明报告.md` — AI 参与环节说明报告
- `docs/签字页管理系统MVP项目报告.html` — 项目总报告

## 状态与路线图

MVP 已全部完成（项目 / 模板 / 变量 / AI / 异步生成下载全流程打通，后端 pytest 通过、前端构建通过）。Phase 2 Temporal 迁移已完成（DocumentGenerationWorkflow + AIActivityWorkflow 端到端验证通过）。

V2 规划：用户登录、PDF 输出、套表组一键选包、删除进行中生成任务的优雅等待。
