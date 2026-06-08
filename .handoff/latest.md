# Session Handoff: 1a - 后端初始化与数据层

## 已完成
- 创建 `backend/` Python 项目（pyproject.toml + requirements.txt，使用 uv 管理依赖）
- 实现 `backend/app/database.py`（SQLite + WAL 模式，DATABASE_URL 环境变量）
- 实现 `backend/app/models.py`（8 个 Entity：Project/Template/ProjectTemplate/Variable/CustomVariable/GenerationTask/GeneratedFile/AILog）
- 实现 `backend/app/services/variable_registry.py`（VARIABLE_REGISTRY + VALIDATION_RULES + TEMPLATE_VARIABLE_MAP + 运行时注册表辅助函数）
- 初始化 Alembic（`render_as_batch=True`），生成并执行首个 migration `a83ec3548e76_initial_schema`

## 文件变更
- `backend/pyproject.toml` — Python 项目配置与依赖
- `backend/requirements.txt` — 依赖清单
- `backend/app/__init__.py` — 应用包
- `backend/app/database.py` — SQLite 连接 + WAL + SessionLocal
- `backend/app/models.py` — 全部 SQLAlchemy 模型
- `backend/app/services/__init__.py` — 服务层包
- `backend/app/services/variable_registry.py` — 预置变量注册表
- `backend/alembic.ini` — Alembic 配置
- `backend/alembic/env.py` — 迁移环境（render_as_batch=True）
- `backend/alembic/script.py.mako` — 迁移模板
- `backend/alembic/versions/a83ec3548e76_initial_schema.py` — 首个迁移脚本
- `data/.gitkeep` — 数据目录占位

## 当前状态
- 在 OrbStack VM（oh-agent）中执行 `uv sync` 成功
- `alembic upgrade head` 成功，9 张业务表 + alembic_version 已创建
- `PRAGMA journal_mode` 返回 `wal`
- `variable_registry.py` import 正常（14 个预置变量、4 条校验规则、3 个模板映射）
- 数据库文件位于 `backend/data/junhe.db`（从 backend/ 目录运行时 `./data` 相对路径）
- 后端 API（main.py、routers）尚未实现

## 遗留问题
- 无

## 下一个 Session
继续 Session 1b: LLM 抽象层 + 项目 API
需要读取此 handoff + AGENTS.md 中 Session 1b 章节
