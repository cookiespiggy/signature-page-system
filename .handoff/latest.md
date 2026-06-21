# Session Handoff: Phase 2 - Temporal 系统迁移

## 已完成

### Task 2.1: Temporal 基础设施搭建
- 添加 `temporalio>=1.9.0` 依赖（实际安装 1.29.0）
- 创建 `backend/app/temporal/` 完整目录结构
- 实现 `config.py`（环境变量连接配置）、`task_queues.py`（3 个队列常量）、`client.py`（Client 单例）
- 实现 `worker.py` 启动脚本，可同时监听 `document-generation` 和 `ai-calls` 两个 Task Queue

### Task 2.2: DocumentGenerationWorkflow（替代 ThreadPoolExecutor + threading.Event）
- 实现 `workflows/generation.py`：`DocumentGenerationWorkflow` 类
  - Signal: `cancel()` — 取消生成
  - Query: `progress()` — 查询进度（completed_count / total_count / status / files）
  - 逐模板渲染 Activity，每个失败后跳过继续
  - 支持 `asyncio.CancelledError` 清理
- 实现 `activities/generation.py`：7 个 Activity
  - `initialize_generation`: 设置 processing 状态、加载变量上下文
  - `render_template`: 单模板渲染（复用 docxtpl 逻辑）
  - `update_progress`: 更新 DB 进度计数
  - `finalize_generation`: 完成状态更新
  - `fail_generation`: 失败状态更新
  - `cancel_generation_in_db`: 取消状态更新
  - `cleanup_partial_files`: 清理临时文件

### Task 2.3: AI Activity 迁移
- 实现 `workflows/ai.py`：`AIActivityWorkflow` 类
  - 声明式重试：3 次 + 指数退避（1s → 2s → 4s）
- 实现 `activities/ai.py`：`call_llm` Activity
  - 复用现有 `ai_service.call_llm_structured()` 逻辑

### Task 2.5: 前端适配与 API 层调整
- 改造 `routers/generation.py`：
  - `USE_TEMPORAL` 环境变量 feature flag 控制双模式
  - `start_generation`: Temporal 模式下通过 `client.start_workflow()` 启动
  - `cancel_generation`: Temporal 模式下通过 Signal 取消
  - `get_generation_status`: 保持从 DB 查询（Workflow 更新 DB 状态）
- 更新 `main.py` lifespan：
  - Temporal 模式下自动初始化 Client 连接
  - Worker 仍作为独立进程运行

### 验证结果
- `temporal server start-dev` 启动成功（本地 SQLite backend）
- Worker 注册到 Server：两个 Task Queue 均有 Poller
- **端到端测试通过**：创建项目 → 选模板 → `POST /generate` → Workflow 执行 → 生成 Word → `status=completed`
- Temporal Web UI 可见 Workflow 执行记录
- 全部 16 个 pytest 通过（legacy 模式不受影响）

## 文件变更

### 新增文件
- `backend/app/temporal/__init__.py` — 模块入口
- `backend/app/temporal/__main__.py` — 允许 `python -m app.temporal.worker`
- `backend/app/temporal/config.py` — 连接配置（TEMPORAL_HOST/PORT/NAMESPACE）
- `backend/app/temporal/task_queues.py` — Task Queue 常量
- `backend/app/temporal/client.py` — Client 单例管理
- `backend/app/temporal/worker.py` — Worker 启动脚本
- `backend/app/temporal/workflows/__init__.py`
- `backend/app/temporal/workflows/generation.py` — DocumentGenerationWorkflow
- `backend/app/temporal/workflows/ai.py` — AIActivityWorkflow
- `backend/app/temporal/activities/__init__.py`
- `backend/app/temporal/activities/generation.py` — 文档生成 Activities（7 个）
- `backend/app/temporal/activities/ai.py` — AI 调用 Activity

### 修改文件
- `backend/requirements.txt` — 添加 `temporalio>=1.9.0`
- `backend/app/routers/generation.py` — 双模式 feature flag + Temporal 路径
- `backend/app/main.py` — lifespan 增加 Temporal Client 初始化/清理

## 当前状态

### 启动命令
```bash
# 1. Temporal Server（如未启动）
temporal server start-dev --db-filename /tmp/temporal-dev.db

# 2. Temporal Worker（独立进程）
cd backend && uv run python -m app.temporal.worker

# 3. FastAPI（Temporal 模式）
cd backend && USE_TEMPORAL=true uv run uvicorn app.main:app --port 8000

# 4. FastAPI（Legacy 模式，默认）
cd backend && uv run uvicorn app.main:app --port 8000
```

### 环境变量
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `USE_TEMPORAL` | `false` | 启用 Temporal Workflow 模式 |
| `TEMPORAL_HOST` | `localhost` | Temporal Server 地址 |
| `TEMPORAL_PORT` | `7233` | Temporal Server gRPC 端口 |
| `TEMPORAL_NAMESPACE` | `default` | Temporal Namespace |

## 遗留问题
- AI 场景（去重/校验/解析）的 Workflow 路径已定义但未在 router 层切换（当前仍走 ai_service.py 同步调用），可按需在 V2 中切换
- Task 2.4（Project Lifecycle Workflow）按计划暂不执行，需评估 ROI
- 迁移期间双跑通过 `USE_TEMPORAL` feature flag 控制，生产切换时改为默认 `true`

## 下一个 Session
- Phase 2 核心（Task 2.1-2.3, 2.5）已完成
- 后续可继续 Phase 3（DDD 渐进拆分 + 生产加固），或进行 V2 功能开发
# Session Handoff: 7 - AI 参与环节说明报告

## 已完成
- 编写 `docs/AI参与环节说明报告.md`：开发过程 AI 工具（Cursor Agent 实现 + Claude Code Session Review/修复、AGENTS.md/Handoff、OpenCode/Mock）+ 系统内置三场景 AI 能力（解析/去重/校验）
- 报告涵盖：LLM 抽象层、ai_guardrail 交叉验证、AILog 审计、前端 AI 组件、测试验证结果
- `AGENTS.md` 知识索引新增「交付报告」条目

## 文件变更
- `docs/AI参与环节说明报告.md` — **[新增]** Session 7 交付报告
- `AGENTS.md` — 知识索引增加报告链接

## 当前状态
- **MVP 全部 7 个 Session 已完成**
- 报告引用知识库文档（AI可信机制、结构化输出、OpenCode-Server）与方案文档
- Session 6b 验收状态保持：16 pytest passed、`npm run build` 成功

## 遗留问题
- 套表组一键选包仍属 V2（当前用多模板多选 + category 分组浏览替代）
- PDF 输出 V2
- 用户登录 V2
- 删除项目进行中的生成任务时 worker 竞态（V2 优雅等待）

## 下一个 Session
**MVP 开发计划已全部完成。** 后续可按 V2 路线图推进（登录、PDF、套表组），或进入生产部署阶段。
