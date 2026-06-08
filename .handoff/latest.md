# Session Handoff: 000 - 初始状态

## 已完成
- 无（项目尚未开始开发）

## 文件变更
- `.cursor/rules/000-project-context.mdc` — 项目全局规则
- `.cursor/rules/001-backend.mdc` — 后端规则
- `.cursor/rules/002-frontend.mdc` — 前端规则
- `.handoff/000-session-plan.md` — 整体 Session 计划
- 签字页管理系统 MVP 实现方案.md — 完整设计方案

## 当前状态
- 项目目录只有文档，无代码
- 后端 `backend/` 和前端 `frontend/` 均不存在
- 本机 OrbStack VM 可用，环境变量 `LLM_PROVIDER` 默认为 mock

## 下一个 Session 任务
**Session 1a: 后端项目初始化与数据层**
对应方案中的 Task 1a，完成以下内容：
1. 创建 `backend/` 目录结构，初始化 Python 项目
2. 安装 FastAPI/SQLAlchemy/Alembic/docxtpl/openpyxl 等依赖
3. 创建 `database.py`（SQLite + WAL 模式）
4. 创建所有 SQLAlchemy 模型（Project/Template/ProjectTemplate/Variable/CustomVariable/GenerationTask/GeneratedFile/AILog）
5. 初始化 Alembic（render_as_batch=True），生成首个 migration
6. 创建 `variable_registry.py`（包含 VARIABLE_REGISTRY + VALIDATION_RULES + TEMPLATE_VARIABLE_MAP）
7. DoD: `alembic upgrade head` 成功创建表结构，database.py 连接 SQLite 正常

## 关键设计决策（来自 MVP 方案）
- 变量双层标识：key（英文 snake_case）+ label（中文显示名）
- 多值变量存储为多行，key 带序号后缀（handling_lawyer_1）
- 异步生成使用 ThreadPoolExecutor + threading.Event 取消
- 预置模板不可删除，自定义模板可上传
- LLMProvider 抽象层默认 MockProvider
- SQLAlchemy Session 非线程安全，每个线程用独立 session
