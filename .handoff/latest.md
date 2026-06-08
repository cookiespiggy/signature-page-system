# Session Handoff: 1b - LLM 抽象层 + 项目 API

## 已完成
- 实现 `backend/app/services/llm/` LLM Provider 抽象层
  - `base.py` — LLMProvider 抽象基类（create_session / send_message / health_check + format + supports_structured_output）
  - `mock_provider.py` + `mock_responses.py` — Mock 实现及三个 AI 场景预设数据
  - `opencode_provider.py` — OpenCode Server HTTP 实现
  - `openai_provider.py` — OpenAI API 直连实现
  - `factory.py` — 按 `LLM_PROVIDER` 环境变量创建 Provider（默认 mock）
- 实现 `backend/app/services/ai_service.py`
  - `call_llm_structured()` — 超时 30s + 重试 3 次 + Pydantic Schema 校验 + 降级 + **原生结构化输出支持**
  - 三个 AI 场景方法：`parse_template_variables` / `suggest_variable_dedup` / `validate_variable_data`
- 实现 `backend/app/schemas.py` — 项目 CRUD + 批量操作 + 健康检查 + AI 结构化 Schema
- 实现 `backend/app/services/project_service.py` — 项目 CRUD + 删除时取消生成任务 + 清理生成文件
- 实现 `backend/app/routers/projects.py` — 项目 CRUD API
- 实现 `backend/app/routers/health.py` — 健康检查 API
- 实现 `backend/app/main.py` — FastAPI 入口 + CORS（localhost:5173）
- 实现 `backend/app/services/template_service.py`
  - `extract_text_from_docx()` — 从 .docx 提取纯文本（段落 + 表格），供 AI 解析
  - Session 2 上传模板后先调用此函数提取文本，再传给 `ai_service.parse_template_variables()`
- 在 oh-agent VM 内安装 OpenCode Server v1.16.2（`/home/jimmy/.opencode/bin/opencode`）
  - 启动 `opencode serve --port 4096`，作为后端 LLM 后端
- 更新 `opencode_provider.py` 以匹配 OpenCode Server v1.16.2 实际 API
  - 健康检查：`GET /global/health` → `{healthy: true}`
  - 发消息：`POST /session/{sid}/message` → body `{parts: [{type: "text", text: ...}]}`
  - 同步 `system` 参数到 API payload（之前遗漏了）
  - 解析响应：从 `response.parts[].text` 提取 LLM 回复
  - 超时从 30s 提到 120s（LLM 推理需要足够时间）
- **发现并启用原生结构化输出**：
  - 测试 OpenCode 所有免费模型 → 仅 `mimo-v2.5-free` 支持 `format/json_schema`
  - 响应中 `info.structured` 返回验证后的 JSON，`finish: "tool-calls"` 确认 tool calling
  - DeepSeek 系列（big-pickle）不支持 tool_choice
  - `opencode_provider.send_message()` 传入 `format` 时自动切换模型到 `mimo-v2.5-free`
  - `ai_service.call_llm_structured()` 优先使用原生结构化输出（provider.supports_structured_output）
  - 回退方案：prompt 嵌入 Schema（用于 Mock/DeepSeek 等不支持的结构化输出场景）
- **端到端验证全部通过**（见「当前状态」）
- 重新在 oh-agent VM 内创建 `.venv`（之前的 .venv 是 macOS 的，不兼容 Linux VM）
- 更新 `docs/knowledge-base/结构化输出.md` 记录 `mimo-v2.5-free` 发现

## 文件变更
- `backend/app/services/template_service.py` — **[新增]** 模板业务逻辑（DOCX 文本提取）
- `backend/app/services/__init__.py` — **[修改]** 导出 `extract_text_from_docx`
- `backend/app/services/llm/opencode_provider.py` — **[修改]** 适配 OpenCode v1.16.2 实际 API
- `backend/pyproject.toml` — **[修改]** 新增 `python-docx` 依赖
- `backend/.venv/` — **[重建]** 在 oh-agent VM 内用 Linux Python 重建
- `backend/app/main.py` — FastAPI 应用入口
- `backend/app/schemas.py` — Pydantic 模型
- `backend/app/services/ai_service.py` — AI 编排服务
- `backend/app/services/project_service.py` — 项目业务逻辑
- `backend/app/services/llm/__init__.py` — LLM 包导出
- `backend/app/services/llm/base.py` — 抽象基类
- `backend/app/services/llm/mock_responses.py` — Mock 预设数据
- `backend/app/services/llm/mock_provider.py` — Mock Provider
- `backend/app/services/llm/opencode_provider.py` — OpenCode Provider
- `backend/app/services/llm/openai_provider.py` — OpenAI Provider
- `backend/app/services/llm/factory.py` — Provider 工厂
- `backend/app/routers/__init__.py` — 路由包
- `backend/app/routers/projects.py` — 项目 API
- `backend/app/routers/health.py` — 健康检查 API

## 当前状态
- 在 OrbStack VM（oh-agent）中 `uv sync` + `uv run uvicorn app.main:app` 启动成功
- `GET /api/health` 返回 200
  - `LLM_PROVIDER=mock`: `llm_provider=mock`，`llm_available=true`
  - `LLM_PROVIDER=opencode`: `llm_provider=opencode`，`llm_available=true`
- 项目 CRUD 全部可调用（创建/列表/详情/更新/删除 204 + 删除后 404）
- MockProvider + `call_llm_structured()` 解析验证通过（3 个模板变量）
- **OpenCodeProvider 端到端验证通过**：
  - `health_check()` → `True`
  - `create_session()` → `ses_...`
  - `send_message()` → 正确返回文本
  - `send_message(format=json_schema)` → 正确返回 JSON（`mimo-v2.5-free`）
  - `call_llm_structured()` 三个 AI 场景全部通过：
    - 模板解析 ✅ → 检测到 `company_name`, `sign_date`
    - 变量去重 ✅ → 建议律师变量合并 + 公司变量合并
    - 数据校验 ✅ → 检测空值 + 日期格式错误
- **JSON 结构化输出方案升级**：详见 `docs/knowledge-base/结构化输出.md`
  - 原生 `format/json_schema`（mimo-v2.5-free）已启用
  - prompt 嵌入 Schema 作为回退方案
- **经验沉淀结构重建**：
  - 建 `docs/knowledge-base/` 目录，拆分 AGENTS.md 中的详细经验
  - AGENTS.md 改为「知识索引」式引用，按需查阅
  - 当前 3 个知识文件：环境配置 / OpenCode Server / 结构化输出
- OpenCode Server v1.16.2 已在 oh-agent VM 中运行（`opencode serve --port 4096`）
- 模板管理 API、变量 API、文档生成 API 尚未实现

## ⚠️ 注意
- `.venv` 已在 oh-agent VM 中用 Linux Python 3.12.3 重建，**在 macOS 宿主机上不可用**
  - 如果需要在宿主机运行后端，需在宿主机重新 `uv sync`
  - 开发时统一在 VM 内 `orb -m oh-agent uv run uvicorn app.main:app`

## 遗留问题
- 删除项目时生成任务取消仅更新 DB 状态，线程级取消（`threading.Event`）待 Session 4 接入
- OpenAI Provider 未联调（需 OPENAI_API_KEY）

## 下一个 Session
继续 Session 2: 模板管理 + AI 解析
需要读取此 handoff + AGENTS.md 中 Session 2 章节
