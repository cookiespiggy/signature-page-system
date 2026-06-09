# Session Handoff: 4 - 文档生成 + 异步下载

## 已完成
- 实现 `backend/app/services/generation_service.py`
  - `ThreadPoolExecutor(max_workers=2)` 异步生成，全局 `_cancel_events` 取消机制
  - `_build_render_context` — 组装 docxtpl 上下文（multiple 列表 `{key}s`、alias_map 合并键）
  - `_render_one_template` — 分步渲染 + 取消检查点 + 临时文件原子重命名
  - `start_generation` / `cancel_generation` / `get_generation_status`
  - `list_generated_files` / `get_generated_file` / `resolve_download_path`
  - `build_download_all_zip` — ZIP 打包下载
  - `shutdown_executor` — lifespan 关闭线程池
  - `cancel_generation_task` — 供项目删除时通知线程取消
- 实现 `backend/app/routers/generation.py` — 全部生成/下载 API
  - `POST /api/projects/{id}/generate` (202)
  - `POST /api/projects/{id}/generate/cancel`
  - `GET /api/projects/{id}/generate/status`
  - `GET /api/projects/{id}/files`
  - `GET /api/files/{id}/download`
  - `GET /api/projects/{id}/download-all`
- 扩展 `backend/app/schemas.py` — GenerationStartResponse、GenerationStatusResponse、GeneratedFileResponse
- 更新 `backend/app/main.py` — 注册 generation 路由 + lifespan shutdown 线程池
- 更新 `backend/app/services/project_service.py` — 删除项目时接入线程级取消

## 文件变更
- `backend/app/services/generation_service.py` — **[新增]** 异步生成与下载业务逻辑
- `backend/app/routers/generation.py` — **[新增]** 生成/下载 API 路由
- `backend/app/schemas.py` — **[修改]** 新增生成相关 Schema
- `backend/app/main.py` — **[修改]** 注册路由 + shutdown executor
- `backend/app/services/project_service.py` — **[修改]** 删除项目时触发 cancel_event

## 当前状态
- 在 OrbStack VM（oh-agent）中启动成功
- **DoD 全部验证通过**：
  - 选模板 + 填变量 → `POST generate` → 异步生成 2 个 .docx（completed 2/2）
  - `GET files` → 返回文件列表（含 template_name）
  - `GET /api/files/{id}/download` → 200 下载 .docx
  - `GET download-all` → 200 下载 ZIP
  - 无模板时 generate → 400
  - 有进行中任务时重复 generate → 409
- 取消机制已实现（generation 太快时难以手动测到 mid-flight cancel，逻辑已覆盖 Event + DB 双重检查）

## 遗留问题
- 预置模板 `{{handling_lawyer}}` 使用重复占位符而非 Jinja2 循环，multiple 变量两律师同名显示（MVP 模板设计限制）
- OpenAI Provider 未联调（需 OPENAI_API_KEY）

## 下一个 Session
继续 Session 5a-1: 前端初始化 + 项目列表页
需要读取此 handoff + AGENTS.md 中 Session 5a-1 章节
