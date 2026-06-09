# Session Handoff: 2 - 模板管理 + AI 解析

## 已完成
- 创建 3 个预置 Word 模板（`backend/app/templates/*.docx`），含 `{{key}}` 占位符
  - 律所签字页 / 自然人股东签字页 / 机构股东签字页
  - 生成脚本：`backend/scripts/create_preset_templates.py`
- 实现 `backend/app/services/template_service.py` 完整业务逻辑
  - 预置模板种子数据（应用启动时 `seed_preset_templates`）
  - 模板 CRUD + 文件存储（自定义模板存 `data/templates/custom/`）
  - AI 解析编排（`parse_template_file` → `ai_service.parse_template_variables` + `is_registered` 标记）
  - 自定义变量注册（写入 `CustomVariable` + `_runtime_registry`）
  - 项目-模板关联（`add_templates_to_project` / `remove_template_from_project`）
  - 精确 key 去重 + multiple 变量展开（`handling_lawyer_1/2` 默认 2 行）
  - 模板刷新 diff 算法（`refresh_project_template`：added/removed/kept，保留已填值）
  - 运行时注册表加载（`load_runtime_registry`）
- 实现 `backend/app/routers/templates.py` — 全部模板 API
  - `GET/POST /api/templates`、`GET/PUT/DELETE /api/templates/{id}`
  - `POST /api/templates/parse`
  - `GET/POST /api/projects/{id}/templates`
  - `DELETE /api/projects/{id}/templates/{template_id}`
  - `POST /api/projects/{id}/templates/{template_id}/refresh`
- 扩展 `backend/app/schemas.py` — 模板相关 Pydantic 模型
- 更新 `backend/app/main.py` — 注册 templates 路由 + lifespan 种子数据/注册表加载

## 文件变更
- `backend/app/templates/*.docx` — **[新增]** 3 个预置 Word 模板
- `backend/scripts/create_preset_templates.py` — **[新增]** 预置模板生成脚本
- `backend/app/services/template_service.py` — **[扩展]** 完整模板业务逻辑
- `backend/app/routers/templates.py` — **[新增]** 模板 API 路由
- `backend/app/schemas.py` — **[修改]** 新增模板相关 Schema
- `backend/app/main.py` — **[修改]** 注册路由 + lifespan 初始化

## 当前状态
- 在 OrbStack VM（oh-agent）中启动成功，预置模板自动种子入库
- **DoD 全部验证通过**：
  - `GET /api/templates` → 3 个预置模板
  - `GET /api/templates/{id}` → 含 variables_json 和元数据
  - `DELETE /api/templates/1`（预置）→ 403
  - `POST /api/templates/parse` → Mock AI 解析返回变量 + is_registered
  - `POST /api/projects/{id}/templates` → 创建关联 + 变量去重（共享 key 合并 source_template_ids）
  - `PUT /api/templates/{id}` → version 自增（v1→v2）
  - `POST /api/projects/{id}/templates/{id}/refresh` → diff 正确（added=1 新增变量）
  - `DELETE /api/projects/{id}/templates/{id}` → 204 + Variable 清理
- 变量 API、文档生成 API 尚未实现

## 遗留问题
- 删除项目时生成任务取消仅更新 DB 状态，线程级取消待 Session 4 接入
- OpenAI Provider 未联调（需 OPENAI_API_KEY）
- 预置模板 PUT 更新会自增 version（符合设计），但预置模板 file_path 不会被替换（仅 variables_json 可更新）

## 下一个 Session
继续 Session 3: 变量填写 + AI 去重 + 校验
需要读取此 handoff + AGENTS.md 中 Session 3 章节
