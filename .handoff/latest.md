# Session Handoff: 3 - 变量填写 + AI 去重 + 校验

## 已完成
- 实现 `backend/app/services/variable_service.py`
  - `list_variables` — 获取去重后的变量列表
  - `save_variables` — 逐行乐观锁保存（部分成功，`updated_at` 冲突检测）
  - `validate_value` — 基于 `VALIDATION_RULES` 的基础正则校验
  - `get_alias_dedup_suggestions` — 注册表 aliases 规则去重建议
  - `ai_dedup_suggestions` — AI 去重 + 别名建议（写入 AILog）
  - `apply_dedup_suggestions` — 应用合并建议（合并 source_template_ids、保留 value）
  - `ai_validate_variables` — 正则校验 + AI 语义校验
  - Excel 导出空白模板 / 已填数据（openpyxl，三列：key/label/value）
  - `import_preview` — 无状态导入预览（部分成功报告）
  - `import_variables` — 确认导入（部分成功写入）
- 实现 `backend/app/routers/variables.py` — 全部变量 API
  - `GET/PUT /api/projects/{id}/variables`
  - `POST /api/projects/{id}/variables/ai-dedup`
  - `POST /api/projects/{id}/variables/apply-dedup`（供前端采纳合并建议）
  - `POST /api/projects/{id}/variables/ai-validate`
  - `POST /api/projects/{id}/variables/import-preview`
  - `POST /api/projects/{id}/variables/import`
  - `GET /api/projects/{id}/variables/export-template`
  - `GET /api/projects/{id}/variables/export`
- 扩展 `backend/app/schemas.py` — 变量相关 Pydantic 模型
- 更新 `backend/app/main.py` — 注册 variables 路由

## 文件变更
- `backend/app/services/variable_service.py` — **[新增]** 变量业务逻辑
- `backend/app/routers/variables.py` — **[新增]** 变量 API 路由
- `backend/app/schemas.py` — **[修改]** 新增变量相关 Schema
- `backend/app/main.py` — **[修改]** 注册 variables 路由

## 当前状态
- 在 OrbStack VM（oh-agent）中启动成功
- **DoD 全部验证通过**：
  - `GET /api/projects/{id}/variables` → 返回去重变量列表（含 sort_order、source_template_ids）
  - `PUT /api/projects/{id}/variables` → 逐行保存成功
  - 乐观锁冲突 → errors 返回 CONFLICT 消息，success 为空
  - `POST ai-dedup` → Mock AI 返回合并建议
  - `POST ai-validate` → 正则 issues + AI issues
  - Excel export-template / export → 200 下载 .xlsx
  - import-preview → 解析 + 校验，返回 success/errors
  - import → 部分成功写入
- 文档生成 API 尚未实现

## 遗留问题
- 删除项目时生成任务取消仅更新 DB 状态，线程级取消待 Session 4 接入
- OpenAI Provider 未联调（需 OPENAI_API_KEY）
- `apply-dedup` 为 Session 5b 前端采纳建议预留，AGENTS.md 未单独列出

## Session 3 Review 变更（2026-06-09）
- 默认 LLM Provider 从 `mock` 切换为 `opencode`
- 修改文件：
  - `backend/app/services/llm/factory.py` — 默认值 `mock` → `opencode`
  - `AGENTS.md` — 启动命令、环境变量表、设计决策说明
  - `docs/knowledge-base/环境配置.md` — 场景矩阵、启动命令、环境变量表
- `import_variables` 添加 `get_project()` 项目存在性校验

## 下一个 Session
继续 Session 4: 文档生成 + 异步下载
需要读取此 handoff + AGENTS.md 中 Session 4 章节
