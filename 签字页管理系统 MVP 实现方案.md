# 签字页管理系统 MVP 实现方案

## 设计决策与理由

### 1. 输出格式: Word (.docx)
- 理由: 律师在实际工作中习惯用 Word 编辑和审阅文档，签字前可能还需要微调。docxtpl 库（基于 python-docx 的 Jinja2 模板引擎）成熟稳定，MVP 阶段优先保证实用性。PDF 可作为后续增强。

### 2. 用户认证: 无登录
- 理由: MVP 阶段聚焦核心业务流程闭环，省去认证复杂度。界面顶部显示当前用户名称(mock)即可。

### 3. 变量去重策略
- 理由: 多个模板中出现相同变量(如"张三"既是律师又是股东)只填一次。系统维护一个全局变量注册表，按变量 key 去重，自动填充到所有引用位置。

#### Variable Key 设计规范

变量采用**双层标识**体系，将标准化 key 与中文显示名分离：

- **key（标准化标识）**: 英文 snake_case 格式，用于系统内部去重和模板占位符。例如：`law_firm_director`、`handling_lawyer_1`、`natural_shareholder_name`
- **label（中文显示名）**: 面向用户的中文名称，用于前端表单展示。例如："律所负责人"、"经办律师1"、"自然人股东姓名"

**模板占位符规则**:
- Word 模板中统一使用 `{{key}}` 格式（如 `{{law_firm_director}}`），而非中文原文
- 预置模板的 key 在创建时手工定义，确保语义明确且不冲突
- 上传自定义模板时，AI 解析需同时输出 key（AI 根据语义生成标准化 key）和 label（中文原文）

**去重逻辑**:
- 精确匹配: 相同 key 的变量自动合并（如两个模板都引用 `law_firm_director`）
- AI 语义去重: AI 识别语义相同但 key 不同的变量（如 `firm_director` vs `law_firm_director`），建议合并为统一 key
- 合并后，系统维护 `alias_map`（别名映射表），确保原模板中的旧 key 也能正确替换为合并后的值

### 4. Multiple 类型变量的存储策略

`multiple=True` 的变量（如经办律师）在数据库中**存为多行**，key 采用序号后缀：
- `handling_lawyer_1`、`handling_lawyer_2`、`handling_lawyer_3` ...

**Key 双层标识说明**:
- `VARIABLE_REGISTRY` 中定义的是**基础 key**（不带序号），如 `handling_lawyer`，用于变量定义、去重和模板占位符设计
- Variable 表中实际存储的是**展开 key**（带序号后缀），如 `handling_lawyer_1`、`handling_lawyer_2`，每行对应一个具体值
- 后端在生成时，通过基础 key 查找所有匹配的展开 key，组装为列表传入 docxtpl 模板

- 前端表单中支持动态添加/删除行，默认显示 2 行
- docxtpl 模板中使用 Jinja2 循环语法，后端生成时将多行变量组装为列表传入：
  ```
  {% for lawyer in handling_lawyers %}
  {{ lawyer }}    签字：____________
  {% endfor %}
  ```

### 5. 文件存储策略

- 生成的文件存储在 `{GENERATED_DIR}/{project_id}/` 目录下（通过环境变量 `GENERATED_DIR` 配置，默认值: `data/generated`）
- 文件命名规则: `{template_name}_{uuid4_short}.docx`，避免并发时文件名冲突
- ZIP 打包文件存储在 `{GENERATED_DIR}/{project_id}/zip/` 下，命名: `{project_name}_all_{timestamp}.zip`
- 删除项目时级联清理对应目录下的所有生成文件
- 已知限制: MVP 阶段不做文件定期清理，V2 可增加过期文件自动清理

### 5.5 异步生成的线程模型与取消机制

`BackgroundTasks` 本质是在请求返回后执行的同步回调，直接在其中执行 docxtpl 的同步 IO 会阻塞事件循环。MVP 采用以下方案：

**线程模型**:
- `POST /generate` 接口中，不使用 FastAPI `BackgroundTasks`，改为手动提交任务到 `concurrent.futures.ThreadPoolExecutor(max_workers=2)`
- 每个生成任务在独立线程中执行，避免阻塞主事件循环
- `generation_service.py` 中维护一个全局 `ThreadPoolExecutor` 实例，应用关闭时通过 `lifespan` 事件调用 `shutdown(wait=False)`

**取消机制（基于 threading.Event）**:
- 每个 `GenerationTask` 在创建时关联一个 `threading.Event` 对象，存储在内存字典 `_cancel_events: dict[int, threading.Event]` 中
- 生成线程在每完成一个文件后检查 `cancel_event.is_set()`，若为 True 则：
  1. 将 GenerationTask 状态置为 `cancelled`
  2. 记录已完成的文件数到 `completed_count`
  3. 清理已生成但未完成的部分文件
  4. 线程正常退出（不抛异常）
- **`_render_one_template` 内部的检查点**: 每个模板渲染可能包含多个步骤（docxtpl 渲染 → 写临时文件 → 移动至目标路径），每一步之后都检查 `cancel_event.is_set()`，避免在长耗时操作中间无法响应取消。若检测到取消信号，丢弃当前正在生成的临时文件，不写入目标目录
- 部分文件清理: `_cleanup_partial_files()` 遍历 `GenerationTask` 关联的 `GeneratedFile` 记录，删除其 `file_path` 所指向的物理文件，然后删除这些 DB 记录。取消成功后，已完成的文件保留（用户可能仍有部分可用），仅在用户主动点击「删除项目」时才级联全部清理
- `POST /generate/cancel` 接口：将数据库状态置为 cancelled + 调用 `_cancel_events[task_id].set()` 通知后台线程
- 线程退出后（无论正常完成、取消或失败），从 `_cancel_events` 字典中移除对应条目，防止内存泄漏

**进度更新频率**:
- 每完成 1 个文件更新一次 `completed_count`（MVP 场景单项目文件数通常 < 20，频繁写库可接受）
- 若后续模板数量增多，可改为每完成 20% 或每 5 个文件更新一次

```python
# app/services/generation_service.py 核心结构示意
import threading
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=2)
# 注意: CPython GIL 保护了 dict 的基本操作（get/set/pop 为原子操作），
# MVP 阶段不额外加锁。若后续换用非 GIL Python 实现（如 PyPy/free-threaded 3.13+），
# 需改用 threading.Lock 保护 _cancel_events 的读写。
_cancel_events: dict[int, threading.Event] = {}

def start_generation(task_id: int, project_id: int, ...):
    cancel_event = threading.Event()
    _cancel_events[task_id] = cancel_event
    _executor.submit(_run_generation, task_id, project_id, cancel_event, ...)

def cancel_generation(task_id: int):
    event = _cancel_events.get(task_id)
    if event:
        event.set()  # 通知后台线程停止

def _render_one_template(db, task, template, cancel_event, context, output_dir):
    """分步执行 docxtpl 渲染，每步后检查取消信号"""
    doc = DocxTemplate(template.file_path)

    if cancel_event.is_set():
        return  # 丢弃临时文件，不写入

    doc.render(context)  # Jinja2 替换占位符

    if cancel_event.is_set():
        return

    # 写临时文件，完成后原子重命名
    tmp_path = output_dir / f".tmp_{template.id}_{uuid4().hex}"
    doc.save(str(tmp_path))

    if cancel_event.is_set():
        tmp_path.unlink(missing_ok=True)  # 删除临时文件
        return

    final_path = output_dir / f"{template.name}_{uuid4().hex[:8]}.docx"
    tmp_path.rename(final_path)  # 原子操作

    # 写入 GeneratedFile 记录
    db.add(GeneratedFile(
        project_id=task.project_id, template_id=template.id,
        file_path=str(final_path), status="completed"
    ))
    db.commit()

def _run_generation(task_id, project_id, cancel_event, ...):
    # 注意: SQLAlchemy Session 非线程安全，每个 worker 线程必须创建独立 session
    db = SessionLocal()
    try:
        # 从数据库重新加载任务（获取最新的 cancelled 状态）
        task = db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
        templates = _get_templates_for_project(db, project_id)

        for i, template in enumerate(templates):
            # 双重检查：既检查 threading.Event，也检查 DB 状态
            if cancel_event.is_set():
                _cleanup_partial_files(task_id, db)
                task.status = "cancelled"
                task.completed_count = i
                db.commit()
                return

            context = _build_context(db, task, template)  # 组装变量上下文
            output_dir = ...  # 从配置计算输出目录
            _render_one_template(db, task, template, cancel_event, context, output_dir)
            task.completed_count = i + 1
            db.commit()

        task.status = "completed"
        db.commit()

    except Exception as e:
        db.rollback()
        task = db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
        if task:
            task.status = "failed"
            task.error_message = str(e)
            db.commit()
    finally:
        _cancel_events.pop(task_id, None)
        db.close()  # 每个线程用完 session 后必须关闭
```

### 6. 签字页模板库

模板库是系统的核心资产，采用「预置模板 + 自定义模板」双层架构：

**模板分类体系**:

| 分类 | 说明 | MVP 预置 | 自定义 |
|------|------|---------|--------|
| 律所签字页 | 律所名称、负责人、经办律师签字 | ✅ 模板1 | 支持上传变体 |
| 自然人股东签字页 | 自然人股东签字（股东大会决议） | ✅ 模板2 | 支持上传变体 |
| 机构股东签字页 | 机构股东公章 + 授权代表签字 | ✅ 模板3 | 支持上传变体 |
| 其他签字页 | 董监高、保荐人等其他类型 | — | 支持上传 |

**MVP 预置模板（3 个）**:

- **模板1: 律所签字页** — 对应签字页样例1：律所名称、负责人、经办律师（多个）、日期、目标公司、交易所、文件类型
- **模板2: 自然人股东签字页** — 对应签字页样例2：自然人股东姓名、身份证号、目标公司、会议年份/次数、日期
- **模板3: 机构股东签字页** — 对应签字页样例2：机构股东名称（公章）、授权代表姓名、目标公司、会议年份/次数、日期

**模板元数据结构**:

每个模板携带以下元数据，用于模板库的浏览、筛选和选择：

```python
# Template 模型扩展字段
class Template:
    id: int
    name: str                    # 模板名称，如“律所签字页”
    description: str             # 模板描述，如“适用于律所出具法律意见书的签字页”
    category: str                # 分类标签: lawyer_signing / natural_shareholder / institutional_shareholder / other
    tags: list[str]              # JSON 存储，如 ["IPO", "法律意见书", "律所"]
    applicable_scenarios: str    # 适用场景说明，如“IPO 上市项目法律意见书”
    variable_count: int           # 变量数量（API 层从 variables_json 自动计算，不存储到数据库；便于用户评估模板复杂度）
    is_preset: bool              # 是否为预置模板（预置模板不可删除，仅可更新）
    version: int                 # 版本号
    file_path: str               # Word 模板文件路径
    variables_json: dict         # 变量定义
    preview_image: str | None    # 模板预览截图路径（可选，V2 可自动生成）
```

**自定义模板上传流程**:
1. 用户在模板库页面点击「上传新模板」，选择 Word 文件
2. 系统触发 AI 解析（`POST /api/templates/parse`），自动识别变量
3. 用户填写模板元数据（名称、分类、适用场景、标签）
4. 用户确认/修正 AI 解析的变量列表（「待确认」变量转正流程）
5. 模板入库，可在后续项目中选用

**模板库前端展示**:
- Step 1 模板选择页以卡片网格形式展示模板库，每张卡片显示：模板名称、分类标签、适用场景、变量数量
- 支持按分类筛选、按名称搜索
- 预置模板卡片带「系统预置」徽标，自定义模板带「自定义」徽标
- 点击卡片可展开模板详情：变量列表预览、模板内容 HTML 预览

**V2 套表组规划**:

PRD 中提到的「套表组」概念在 MVP 阶段以“多模板多选”替代。V2 可引入套表组（TemplatePack）：
- 将多个模板打包为一组（如“IPO 法律意见书全套 = 律所签字页 + 自然人股东签字页 + 机构股东签字页”）
- 一键选择套表组，自动勾选组内所有模板
- 套表组级别可定义变量预填规则（如目标公司名称在组内自动共享）

### 7. AI 能力集成 (通过 LLMProvider 抽象层调用真实 LLM)

系统通过 **LLMProvider 抽象层** 调用 LLM，实现 AI 能力与具体 LLM 服务的解耦：

**LLMProvider 抽象层设计**:

```
app/services/llm/
├── base.py              # LLMProvider 抽象基类（定义 send_message / create_session 接口）
├── opencode_provider.py # OpenCode Server 实现（通过 OrbStack VM HTTP 调用）
├── openai_provider.py   # OpenAI API 直连实现（备用/生产环境）
├── mock_provider.py     # Mock 实现（开发/测试用，返回预设 JSON）
└── factory.py           # 根据环境变量 LLM_PROVIDER 创建对应 Provider 实例
```

- 接口定义: `LLMProvider` 基类声明 `async def send_message(prompt: str, system: str) -> str` 等方法
- MVP 默认实现: `MockProvider`，返回预设的结构化 JSON，确保开发初期不依赖 LLM 服务即可启动和联调
- 生产实现: `OpenCodeProvider`，通过本机 OrbStack VM 中运行的 OpenCode Server（`opencode serve`）调用 GPT-5-mini
- 备用实现: `OpenAIProvider` 直连 OpenAI API，方便后续切换或部署到云端
- 切换方式: 通过环境变量 `LLM_PROVIDER=mock|opencode|openai` 选择，无需改动业务代码（默认为 `mock`，确保新开发者 clone 即可运行）

**OpenCode Server 调用方式**（生产环境 Provider）:
1. `POST /session` 创建会话
2. `POST /session/:id/message` 发送 prompt 并等待 LLM 响应
3. 解析响应中的结构化 JSON 数据

**AI-1: 智能模板解析 (AI Template Parser)**
- 场景: 上传新的 Word 模板时，AI 阅读文档内容，自动识别占位符并提取结构化变量定义（变量名、类型、角色分类）
- LLM Prompt: 将模板文本发送给 LLM，要求其以 JSON 格式返回变量列表（含 key/label/category）
- API: `POST /api/templates/parse` 上传模板文件，返回 AI 解析出的变量列表
- 前端展示: 解析结果带 AI 标签，用户可确认/修正 AI 的解析结果
- AI 价值: 真实语义理解，能识别上下文含义（如“经办律师”是人名类型，而非单纯正则匹配）

Prompt 模板骨架（AI-1）：
```text
你是一个签字页文档解析专家。请阅读以下 Word 模板内容，识别所有需要填写的占位符/变量，并为每个变量生成结构化定义。

<rules>
1. 先识别文档结构和签字页类型（律所/股东/其他）
2. 再逐个提取变量，为每个变量生成：key（英文 snake_case）、label（中文原名）、category（lawyer/shareholder/company/date/document/meeting）、data_type（text/number/date/id_number/company_name）、multiple（是否多值）
3. 只返回 JSON，不要其他内容
</rules>

<example>
输入: "{{law_firm_name}} 负责人：{{law_firm_director}} 经办律师：{{handling_lawyer}}"
        输出: {"variables": [{"key": "law_firm_name", "label": "律师事务所名称", "category": "company", "data_type": "company_name", "is_multiple": false}, ...]}
</example>

<document>
{template_text}
</document>

请返回符合以下 Pydantic Schema 的 JSON：{pydantic_schema}
```

**AI-2: 变量智能去重 (AI Variable Dedup)**
- 场景: 多个模板的变量名不完全一致（如“律所负责人” vs “律师事务所负责人”、“股东签字” vs “自然人股东签字”），AI 判断语义相同并建议合并
- LLM Prompt: 将所有变量列表发送给 LLM，要求其识别语义相同的变量对并给出合并建议（JSON）
- API: `POST /api/projects/{id}/variables/ai-dedup` 返回 AI 建议的合并方案
- 前端展示: 以「AI 建议」卡片形式展示合并建议（含相似度说明），用户可逐条采纳或拒绝
- AI 价值: 语义级别的理解，而非简单的字符串相似度

Prompt 模板骨架（AI-2）：
```text
你是一个签字页变量管理专家。以下是多个签字页模板中的所有变量列表，请识别语义相同的变量并建议合并。

<rules>
1. 先列出每个变量的语义含义
2. 再判断哪些变量语义相同（考虑上下文和领域知识）
3. 对于语义相同的变量对，建议保留哪个 key、合并哪些 key，并说明理由
4. 只返回 JSON，不要其他内容
</rules>

<variables>
{variables_json}
</variables>

请返回符合以下 Pydantic Schema 的 JSON：{pydantic_schema}
```

**AI-3: 智能数据校验 (AI Data Validator)**
- 场景: 填写变量后，AI 校验数据的合理性和一致性（如同一人在不同角色中的信息是否矛盾、公司名称是否合理、日期逻辑是否正确）
- LLM Prompt: 将变量列表和项目上下文发送给 LLM，要求其返回校验报告（JSON，含 error/warning 级别）
- API: `POST /api/projects/{id}/variables/ai-validate` 返回校验报告
- 前端展示: 校验结果以警告/错误列表展示，标注「AI 校验」标签
- AI 价值: 能理解业务上下文进行校验（如检测“张三同时是经办律师和发行人”是否合理）

Prompt 模板骨架（AI-3）：
```text
你是一个签字页数据校验专家。请校验以下已填写的变量数据，检查其合理性和一致性。

<rules>
1. 先列出所有校验规则（身份一致性、公司名称合理性、日期逻辑、角色冲突等）
2. 再逐条检查每个变量
3. 问题分为 error（必须修正）和 warning（建议确认）两个级别
4. 只返回 JSON，不要其他内容
</rules>

<variables>
{filled_variables_json}
</variables>

<validation_rules>
{validation_rules_json}
</validation_rules>

请返回符合以下 Pydantic Schema 的 JSON：{pydantic_schema}
```

**Mock Provider 响应定义**（开发/测试用）:

`MockProvider` 为每个 AI 场景返回预设的结构化 JSON，确保前后端在 AI 服务不可用时仍可正常开发和联调：

```python
# app/services/llm/mock_responses.py

# AI-1: 模板解析 Mock 响应
TEMPLATE_PARSE_MOCK = {
    "variables": [
        {"key": "law_firm_name", "label": "律师事务所名称", "category": "company", "data_type": "company_name"},
        {"key": "law_firm_director", "label": "律师事务所负责人", "category": "lawyer", "data_type": "text"},
        {"key": "handling_lawyer", "label": "经办律师", "category": "lawyer", "data_type": "text", "is_multiple": True},
    ]
}

# AI-2: 变量去重 Mock 响应
VARIABLE_DEDUP_MOCK = {
    "suggestions": [
        {
            "keep_key": "law_firm_director",
            "merge_keys": ["firm_director"],
            "reason": "语义相同，均指律师事务所负责人",
            "confidence": 0.95
        }
    ]
}

# AI-3: 数据校验 Mock 响应
DATA_VALIDATE_MOCK = {
    "issues": [
        {
            "level": "warning",
            "variable_key": "handling_lawyer_1",
            "message": "经办律师与自然人股东姓名相同，请确认是否为同一人",
            "suggestion": "若为同一人，建议合并角色"
        }
    ]
}
```

**AI 调用超时与降级策略**:
- 超时设置: 单次 LLM 调用超时 30s（OpenCode Server 经 VM 转发可能有额外延迟）
- 重试机制: Pydantic Schema 校验失败或超时，最多重试 3 次，重试时在 prompt 中追加错误提示
- 降级策略: 重试耗尽后返回「AI 服务不可用」错误，前端显示降级提示，用户可继续使用基础功能（手工去重、正则校验）不受影响
- 实现: 在 `ai_service.py` 中的 `call_llm_structured()` 方法统一封装超时 + 重试 + 降级逻辑

**Mock Provider 适用范围**:
- Mock 响应仅覆盖**预置模板场景**（3 个预置模板的已知变量），用于前后端联调和 LLM 服务中断时的保底
- 自定义模板上传时若 AI 服务不可用，Mock 无法提供有效的解析结果。此时走降级路径：返回空变量列表 + 提示用户手工定义变量（调用 `POST /api/templates` 直接创建，跳过 AI 解析步骤）

### 8. AI 可靠性保障策略（基于 2025-2026 工业界最佳实践）

参考 Anthropic 工程博客、Zylos Research 2026、Keymakr 2026、MEGA-RAG (PubMed 2025) 等研究，采用多层防御策略：

**策略 1: 领域变量映射表（MVP）→ 领域本体 Ontology（V2）**

> **MVP 阶段**: 使用轻量级的**变量映射表**（`app/services/variable_registry.py`）替代完整 Ontology，快速覆盖 3 个预置模板的已知变量类型。完整 Ontology 作为 **V2 功能**规划，待模板数量和变量复杂度增长后再引入。

**MVP 变量映射表设计**:

```python
# app/services/variable_registry.py
# === 模板1: 律所签字页 ===
# 对应签字页样例1: 律所名称、负责人、经办律师(多个)、日期、目标公司、交易所、文件类型
#
# === 模板2: 自然人股东签字页 ===
# 对应签字页样例2: 自然人股东姓名、目标公司、会议年份/次数、日期
#
# === 模板3: 机构股东签字页 ===
# 对应签字页样例2: 机构股东名称(公章)、授权代表姓名、目标公司、会议年份/次数、日期

VARIABLE_REGISTRY = {
    # --- 通用变量（跨模板共享）---
    "target_company_name": {
        "label": "目标公司名称",
        "category": "company",
        "aliases": ["目标公司名称", "发行人名称", "公司名称", "股份有限公司"],
        "required": True,
    },
    "signing_date": {
        "label": "签署日期",
        "category": "date",
        "aliases": ["签署日期", "日期", "年月日"],
        "required": True,
    },

    # --- 模板1: 律所签字页专用变量 ---
    "law_firm_name": {
        "label": "律师事务所名称",
        "category": "lawyer",
        "aliases": ["律师事务所名称", "律所名称"],
        "required": True,
    },
    "law_firm_director": {
        "label": "律师事务所负责人",
        "category": "lawyer",
        "aliases": ["律师事务所负责人", "律所负责人", "负责人"],
        "required": True,
    },
    "handling_lawyer": {
        "label": "经办律师",
        "category": "lawyer",
        "aliases": ["经办律师", "签字律师"],
        "required": True,
        "is_multiple": True,  # 可有多个经办律师
    },
    "exchange_name": {
        "label": "交易所名称",
        "category": "company",
        "aliases": ["交易所名称", "交易所", "上市交易所"],
        "required": False,
    },
    "document_type": {
        "label": "文件类型",
        "category": "document",
        "aliases": ["文件类型", "文书类型", "意见书类型"],
        "required": False,
    },
    "target_investor_type": {
        "label": "投资者类型",
        "category": "document",
        "aliases": ["投资者类型", "发行对象", "合格投资者"],
        "required": False,
    },

    # --- 模板2: 自然人股东签字页专用变量 ---
    "natural_shareholder_name": {
        "label": "自然人股东姓名",
        "category": "shareholder",
        "aliases": ["自然人股东", "股东姓名", "自然人股东姓名"],
        "required": True,
    },
    "natural_shareholder_id_number": {
        "label": "自然人股东身份证号",
        "category": "shareholder",
        "aliases": ["身份证号", "自然人股东身份证号", "身份证号码"],
        "required": False,
    },
    "meeting_year": {
        "label": "股东大会年份",
        "category": "meeting",
        "aliases": ["会议年份", "股东大会年份", "年份"],
        "required": True,
    },
    "meeting_session": {
        "label": "股东大会次数",
        "category": "meeting",
        "aliases": ["会议次数", "股东大会次数", "第几次"],
        "required": True,
    },

    # --- 模板3: 机构股东签字页专用变量 ---
    "institutional_shareholder_name": {
        "label": "机构股东名称",
        "category": "shareholder",
        "aliases": ["机构股东名称", "机构名称", "法人股东名称"],
        "required": True,
    },
    "authorized_representative_name": {
        "label": "授权代表姓名",
        "category": "shareholder",
        "aliases": ["授权代表", "执行事务合伙人委派代表", "授权代表姓名"],
        "required": True,
    },
}

VALIDATION_RULES = {
    "natural_shareholder_id_number": r"^\d{17}[\dXx]$",  # 身份证号正则
    "target_company_name": r".+股份有限公司|.+有限责任公司",  # 公司名称基本校验
    "institutional_shareholder_name": r".+",  # 机构名称非空即可
    "signing_date": r"^\d{4}年\d{1,2}月\d{1,2}日$",  # 日期格式: 2026年6月8日
}

# 预置模板与变量的对应关系（用于前端按模板筛选变量）
TEMPLATE_VARIABLE_MAP = {
    "law_firm_signing_page": [  # 模板1: 律所签字页
        "target_company_name", "law_firm_name", "law_firm_director",
        "handling_lawyer", "signing_date", "exchange_name",
        "document_type", "target_investor_type",
    ],
    "natural_shareholder_signing_page": [  # 模板2: 自然人股东签字页
        "natural_shareholder_name", "natural_shareholder_id_number",
        "target_company_name", "meeting_year", "meeting_session", "signing_date",
    ],
    "institutional_shareholder_signing_page": [  # 模板3: 机构股东签字页
        "institutional_shareholder_name", "authorized_representative_name",
        "target_company_name", "meeting_year", "meeting_session", "signing_date",
    ],
}
```

MVP 映射表的作用:
- **变量去重**: 通过 `aliases` 列表精确匹配中文别名，合并为统一 key
- **数据校验**: 通过 `VALIDATION_RULES` 正则校验基本格式（如身份证号、公司名）
- **模板解析**: AI 解析出的变量 key 必须在映射表中注册，否则标记为「待确认」

**「待确认」变量转正流程**:

AI 解析自定义模板时，可能识别出映射表中未注册的变量。这些变量按以下流程处理：

1. **标记阶段**: AI 返回的变量若 key 不在 `VARIABLE_REGISTRY` 中，前端标记为「待确认」（橙色标签），与已注册变量（绿色标签）区分
2. **用户确认**: 用户在模板创建确认页面可以：
   - **采纳**: 确认 AI 生成的 key/label/category 合理，点击「确认注册」→ 变量写入该模板的 `variables_json`，同时**自动追加到运行时注册表**（内存中的 `_runtime_registry` 字典，应用重启后从数据库重新加载）
   - **修正**: 修改 AI 生成的 key/label/category 后确认 → 同采纳流程
   - **删除**: 判断该变量不需要，直接移除
3. **持久化**: 用户确认后的新变量写入 `CustomVariable` 表（`id, key, label, category, data_type, created_by_template_id`），应用启动时加载到 `_runtime_registry`
4. **跨模板复用**: 后续上传的其他模板若引用相同的自定义变量 key，系统从 `_runtime_registry` 中匹配，不再标记为「待确认」

> **MVP 简化**: 不引入管理员审批流程，用户确认即生效。V2 可增加团队级共享变量库，支持跨项目复用自定义变量。

**别名匹配优先级规则**（预置映射表 vs 自定义注册表）:

去重时，按以下优先级依次匹配：
1. **精确 key 匹配**: 先按 key 精确匹配，命中则跳过后续步骤
2. **`VARIABLE_REGISTRY.aliases` 别名匹配**: 搜索预置映射表的 aliases 列表
3. **`CustomVariable.aliases` 别名匹配**: 搜索自定义变量注册表的 aliases 列表
4. **AI 语义匹配**: 前述均未命中时，走 AI 语义分析

预置映射表优先级高于自定义注册表，确保系统升级时不会因自定义变量覆盖预置定义。若预置和自定义的 key 冲突（极少发生），以预置为准，冲突的自定义变量标记为「待确认」。

**V2 Ontology 规划（当前不实现）**:

2026 年工业界趋势: Ontology 成为企业 AI Agent 的语义基础层。研究表明，基于 Ontology 的结构化知识上下文可减少幻觉 40%+（MEGA-RAG, PubMed 2025）。

V2 阶段为签字页领域定义轻量级 Ontology：

```
实体类 (Classes):
  - Person (自然人): 属性(name, id_number, role)
  - Company (公司): 属性(name, legal_representative, seal)
  - Lawyer (律师): 继承 Person, 属性(lawyer_license, firm)
  - Shareholder (股东): 可以是 Person 或 Company
    - NaturalShareholder: 继承 Person + Shareholder
    - InstitutionalShareholder: 继承 Company + Shareholder
  - Document (文档): 属性(title, type, signing_date)

关系 (Relations):
  - belongs_to(Shareholder, Company)
  - signs(Lawyer, Document)
  - represents(LegalRepresentative, Company)

约束 (Constraints):
  - NaturalShareholder 必须有 id_number
  - InstitutionalShareholder 必须有 seal
  - Lawyer 必须有 lawyer_license
  - signing_date 不能早于 document 创建日期
```

实现: V2 阶段 `app/services/ontology.py` 定义轻量级本体，提供 `validate_entity()`、`check_constraints()`、`resolve_alias()` 等方法。

**策略 2: 确定性边界优先于模型层防御（Anthropic "Containment First"）**
- 核心原则: 环境层的硬边界永远比模型层的概率性防御可靠
- AI 输出仅作为「建议」，必须经变量映射表规则校验 + 用户确认后才写入数据库
- AI 不能直接修改项目数据，只能返回建议对象，由业务层执行（权限隔离）
- 三层防御: 映射表硬规则 → AI 软理解 → Human 最终确认

**策略 3: 结构化输出 + Pydantic Schema 校验（解决概率输出问题）**
- LLM 必须返回符合预定义 JSON Schema 的结构化数据
- 后端使用 Pydantic 模型解析 AI 返回，校验失败则自动重试（最多 3 次）
- 重试时在 prompt 中追加错误提示，引导 LLM 修正输出格式
- 实现: `app/services/ai_service.py` 中封装 `call_llm_structured()` 方法

**策略 4: Think-Before-Act 推理步骤（Anthropic "Think Tool" 模式）**
- 复杂 AI 调用前，Prompt 中引导 LLM 先进行结构化推理：
  - 模板解析: 先识别文档结构，再提取变量
  - 变量去重: 先列出所有变量的语义含义，再判断哪些相同
  - 数据校验: 先列出所有校验规则，再逐条检查
- Prompt 中包含领域示例（few-shot），展示正确的推理过程
- 实测效果: Anthropic τ-Bench 上准确率提升 54%

**策略 5: 上下文工程——精简高信号 Token（Anthropic "Context Engineering"）**
- 核心原则: 最小化高信号 token 集合，context 是有限资源，边际收益递减
- 模板解析: 只发送模板文本，不发送无关上下文
- 变量去重: 将变量列表按模板分组发送，而非一次性全部塞入
- 数据校验: 只发送已填写的变量，附带明确的校验规则说明
- 关键指令放在 prompt 开头和结尾，中间放数据（缓解 Lost-in-the-Middle）
- 使用 XML 标签或 Markdown 分隔不同区块（指令/数据/示例）

**策略 6: 低温度 + 确定性生成（解决概率输出不稳定）**
- 所有 AI 调用使用低温度 (temperature=0.1)，减少随机性
- Prompt 中明确要求「只返回 JSON，不要其他内容」

**策略 7: 后校验 Guardrails 层（映射表规则 + 正则引擎多层防御）**
- AI 输出后，依次进行：
  1. 变量映射表校验（硬规则: key 是否已注册、category 是否匹配、必填项检查）
  2. 正则引擎补充检查（软规则: 身份证号格式、公司名称格式、日期合理性）
  3. 与映射表别名列表交叉验证
- 若 AI 结果与规则引擎结果冲突，标记为「需人工确认」

**策略 8: AI 调用日志与可追溯性**
- 记录每次 AI 调用的 prompt、response、duration_ms（调用耗时）、Ontology 校验结果、用户操作
- AILog 表包含 `duration_ms` 字段，记录 LLM 调用实际耗时
- 支持事后分析 AI 出错的模式，为优化 prompt 和 Ontology 提供数据
- 可通过 duration_ms 统计平均响应时间，辅助判断是否需要切换 Provider 或优化 prompt 长度

**策略 9: 审批疲劳防御（Anthropic "Approval Fatigue" 发现）**
- Anthropic 发现: 用户对权限提示的审批率高达 93%，审批越多越不认真
- 应对: AI 建议按风险分级展示：
  - 低风险（如变量类型分类，映射表已注册且 category 匹配）: 默认采纳，用户可修改
  - 中风险（如变量合并建议，LLM 语义判断 + 映射表 aliases 交叉验证一致）: 高亮展示，需明确确认
  - 高风险（如映射表规则校验冲突、AI 结果与正则校验矛盾）: 强制逐条审核

> **MVP 简化**: 无 Ontology，风险分级依据改为映射表规则匹配程度。V2 引入 Ontology 后可进一步提升分级精度。

**策略 10: 并发安全（逐行乐观锁）**
- Variable 表包含 `updated_at` 字段作为版本号
- PUT 批量保存变量时，后端逐行比对客户端提交的 updated_at 与数据库当前值
- 每行独立校验：成功的行写入，冲突的行返回错误报告（含当前 `updated_at`），不整体回滚
- 前端针对冲突行可局部刷新后重新提交，用户体验更友好
- MVP 阶段不实现完整的冲突合并，仅防覆盖丢失

---

## 技术架构

```
前端 (React + TS + Vite + Tailwind CSS + shadcn/ui)
    |
    | REST API
    v
后端 (Python FastAPI + SQLite)
    |
    |--- docxtpl (Jinja2) / openpyxl ---> 文件生成 (Word .docx)
    |
    |--- LLMProvider 抽象层 ---> [OpenCode Server | OpenAI API | Mock]
                                       |
                                       v
                                   LLM (GPT-5-mini / GPT-4o / ...)
```

### 开发环境配置

**后端 CORS 配置**:
- `main.py` 中添加 `CORSMiddleware`，允许前端开发服务器（默认 `http://localhost:5173`）跨域访问
- 配置 `allow_origins`、`allow_methods=["*"]`、`allow_headers=["*"]`

**前端 Vite 代理**:
- `vite.config.ts` 中配置 `server.proxy`，将 `/api` 请求转发到后端（默认 `http://localhost:8000`）
- 生产环境通过 Nginx 反向代理解决，无需 CORS

**SQLite 数据库路径**:
- 通过环境变量 `DATABASE_URL` 配置，默认值: `sqlite:///./data/junhe.db`
- `database.py` 读取该环境变量创建 engine，避免路径硬编码

**文件下载响应头**:
- `GET /api/files/{id}/download`: 设置 `Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document` + `Content-Disposition: attachment; filename="{filename}"`
- `GET /api/projects/{id}/download-all`: 设置 `Content-Type: application/zip` + `Content-Disposition: attachment; filename="{zip_filename}"`

### 目录结构
```
junhe-mvp/
├── frontend/               # React 前端
│   ├── src/
│   │   ├── components/     # shadcn/ui 组件 + 业务组件
│   │   ├── pages/          # 页面组件
│   │   ├── services/       # API 调用
│   │   ├── lib/            # utils
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── backend/                # Python 后端
│   ├── app/
│   │   ├── main.py         # FastAPI 入口
│   │   ├── models.py       # SQLAlchemy 模型
│   │   ├── schemas.py      # Pydantic schemas
│   │   ├── routers/        # API 路由
│   │   ├── services/       # 业务逻辑
│   │   │   ├── llm/        # LLMProvider 抽象层
│   │   │   │   ├── base.py
│   │   │   │   ├── opencode_provider.py
│   │   │   │   ├── openai_provider.py
│   │   │   │   ├── mock_provider.py
│   │   │   │   ├── mock_responses.py   # Mock 响应预设数据
│   │   │   │   └── factory.py
│   │   │   ├── variable_registry.py  # MVP 变量映射表
│   │   │   ├── template_service.py
│   │   │   ├── generation_service.py
│   │   │   └── ai_service.py         # AI 能力编排（调用 LLMProvider）
│   │   ├── templates/      # Word 模板文件(.docx)
│   │   └── database.py     # 数据库配置
│   └── requirements.txt
└── data/                   # SQLite 数据库文件 + 生成文件（默认 GENERATED_DIR）
    ├── junhe.db            # SQLite 数据库
    └── generated/          # 生成的文件，路径由环境变量 GENERATED_DIR 配置
        └── {project_id}/
            ├── *.docx
            └── zip/
```

### 数据库迁移
- 使用 **Alembic** 管理数据库版本迁移，即使 MVP 阶段也保留迁移能力
- 初始化时生成首个 migration 脚本，后续模型变更通过新增 migration 脚本演进
- **SQLite 兼容性配置**: Alembic 的 `env.py` 中设置 `render_as_batch=True`，因为 SQLite 对 ALTER TABLE 支持有限（不支持 DROP COLUMN 等），batch 模式会通过创建临时表 + 数据迁移 + 重命名的方式实现 DDL 操作。若不设置，autogenerate 可能生成 SQLite 不支持的迁移脚本

### 已知限制：SQLite 并发
- SQLite 写操作是串行的，多个项目同时生成并写入 GenerationTask 进度时可能遇到 `database is locked`
- MVP 阶段可接受（单用户使用场景），通过设置 `journal_mode=WAL` 缓解（在 `database.py` 中创建 engine 后执行 `PRAGMA journal_mode=WAL`）
- V2 阶段若需多用户并发，可切换至 PostgreSQL，仅需修改 database.py 连接字符串

### 测试策略

MVP 阶段采用轻量级测试策略，确保核心流程可验证：

**后端集成测试**（pytest + httpx.AsyncClient）:
- 项目 CRUD 流程: 创建 → 查询 → 更新 → 删除（含级联清理）
- 模板选择 + 变量去重: 选择多个模板后验证 Variable 表去重逻辑、`source_template_ids` 正确性
- 变量保存 + 乐观锁: 验证逐行校验、冲突行正确返回错误报告
- 文档生成流程: 触发异步生成 → 轮询状态 → 验证文件生成成功
- Excel 导入/导出: 验证 import-preview 无状态、导入部分成功策略

**AI Prompt 回归测试**（使用 Mock Provider）:
- 固定输入验证输出格式: 确保 AI-1/AI-2/AI-3 的 Prompt 返回符合 Pydantic Schema 的结构
- 降级路径测试: 模拟 LLM 超时/失败，验证降级逻辑和前端提示

**不纳入 MVP 的测试**:
- 前端 E2E 测试（手动验证即可）
- 性能测试（单用户场景无必要）
- 真实 LLM 输出的断言测试（LLM 输出不确定性高，用 Prompt 回归测试替代）

---

## 数据模型

### Project (签字页项目)
- id, name, created_at, updated_at, status(draft/generating/completed)

### Template (签字页模板)
- id, name, description, category(分类标签: lawyer_signing/natural_shareholder/institutional_shareholder/other), tags(JSON，如 ["IPO","法律意见书"]), applicable_scenarios(适用场景说明), variable_count(变量数量，自动生成), is_preset(是否预置模板，预置不可删除仅可更新), file_path(Word模板路径), variables_json(模板所需变量定义), version(模板版本号，每次更新自增), preview_image(模板预览截图路径，可选), created_at, updated_at

### ProjectTemplate (项目-模板关联)
- id, project_id, template_id, template_version(关联时的模板版本号), variables_snapshot_json(选择时模板变量定义的快照，防止模板更新后影响已有项目)
  - 快照格式示例: `[{"key": "law_firm_director", "label": "律所负责人", "category": "lawyer", "data_type": "text", "required": true}, ...]`，完整拷贝模板变量定义，确保后续模板修改不影响已有项目

> **快照与 Variable 表的关系**: `variables_snapshot_json` 仅用于「展示模板原始定义」和「判断是否需要刷新」（通过对比 `template_version`），Variable 表是唯一的实际数据源。快照不参与生成时的变量取值。
  - 当 `template_version < Template.version` 时，前端提示「模板已更新，可刷新」

### Variable (项目变量 - 去重后的变量注册表)
- id, project_id, key(标准化英文标识，如 `law_firm_director`), label(中文显示名), value, data_type(text/number/date/id_number/company_name), category(lawyer/shareholder/company/date等), is_multiple(是否多值变量，来自 VARIABLE_REGISTRY 或 AI 解析的 multiple 标志，前端据此渲染动态增减行), required(是否必填，由来源模板的 required 合并而来：任一来源标记为 required 即为 True，用于前端表单校验), sort_order(组内排序), source_template_ids(JSON array of int，如 `[1, 2]`，来源模板ID列表，移除模板时同步清理，为空数组时删除该行), is_merged(是否由AI合并), merged_from_keys(JSON，AI合并前的原始key列表), updated_at(乐观锁版本号)

### CustomVariable (自定义变量注册表 - 用户确认的 AI 解析变量)
- id, key(标准化英文标识), label(中文显示名), category, data_type, aliases(JSON array of string，同义词列表，如 `["经办律师", "签字律师"]`，用于别名匹配去重), created_by_template_id(来源模板ID), created_at
- 用于存储用户确认注册的 AI 解析变量（映射表之外的自定义变量）
- 应用启动时加载到内存中的 `_runtime_registry`，与预置 `VARIABLE_REGISTRY` 合并使用
- 用户确认注册变量时，可将 AI 解析出的中文名称连同常见同义词填入 aliases 字段，后续自定义模板解析时可通过 aliases 匹配去重

### GenerationTask (生成任务 - 异步生成支持)
- id, project_id, status(pending/processing/completed/failed/cancelled), total_count(总文件数), completed_count(已完成数), error_message, created_at, updated_at, completed_at(完成时间，用于计算生成耗时), cancelled_at(取消时间，用于统计取消率和分析取消原因)

### GeneratedFile (生成的文件)
- id, project_id, template_id, file_path, created_at, status

### AILog (AI 调用日志)
- id, project_id, ai_type(template_parse/variable_dedup/data_validate), prompt, response, duration_ms(LLM 调用耗时，毫秒), validation_result, user_action(accepted/rejected/modified), created_at

---

## 核心 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | /api/projects | 项目列表/创建 |
| GET/PUT/DELETE | /api/projects/{id} | 项目详情/更新/删除（删除前先取消进行中的生成任务，再级联清理生成文件和数据库记录） |
| GET | /api/templates | 模板列表 |
| POST | /api/templates | 上传自定义模板（触发 AI 解析提取变量） |
| POST | /api/templates/parse | AI 解析上传的模板文件，返回变量列表 |
| GET | /api/templates/{id} | 模板详情（含变量定义列表和模板元数据） |
| PUT | /api/templates/{id} | 更新模板（重新上传 Word 文件，自增 version，触发 AI 重新解析变量） |
| DELETE | /api/templates/{id} | 删除自定义模板（预置模板返回 `403 Forbidden`；若模板仍被项目引用，返回 `409 Conflict` 并提示先移除关联项目）。**已知限制**: 无查询引用项目的 API，用户需手动排查。V2 可增加 `GET /api/templates/{id}/referenced-projects` |
| POST | /api/projects/{id}/templates/{template_id}/refresh | 刷新项目中的模板版本（更新 variables_snapshot_json + 同步 Variable 表，保留已填值） |
| POST | /api/projects/{id}/templates | 为项目选择模板(支持多选) |
| DELETE | /api/projects/{id}/templates/{template_id} | 移除项目已选模板（可撤销误操作，触发 Variable 清理） |
| GET | /api/projects/{id}/variables | 获取去重后的变量列表 |
| PUT | /api/projects/{id}/variables | 批量保存变量值（逐行乐观锁校验：每行携带 updated_at，成功的行写入，冲突的行返回错误报告，复用统一错误响应结构） |
| POST | /api/projects/{id}/variables/import-preview | Excel 导入预览（无状态）：解析 + 校验，返回成功行和错误行报告，不写入数据库。每次调用均为独立解析，多次预览之间无状态关联，用户确认后再调用 import 正式导入 |
| POST | /api/projects/{id}/variables/import | 确认导入变量（部分成功策略：成功的行写入，失败的行返回错误报告） |
| GET | /api/projects/{id}/variables/export-template | 下载 Excel 变量模板（空白） |
| GET | /api/projects/{id}/variables/export | 导出已填写的变量数据（Excel） |
| POST | /api/projects/{id}/generate | 触发生成签字页（异步，返回 task_id） |
| POST | /api/projects/{id}/generate/cancel | 取消生成任务（状态置为 cancelled） |
| GET | /api/projects/{id}/generate/status | 轮询生成任务状态（进度、已完成数） |
| GET | /api/projects/{id}/files | 获取生成文件列表 |
| GET | /api/files/{id}/download | 下载单个文件 |
| GET | /api/projects/{id}/download-all | 打包下载 ZIP |
| GET | /api/health | 健康检查（返回数据库连接状态、LLM Provider 可用性、当前 Provider 类型） |

### 关键 API 请求/响应格式

**`POST /api/templates/parse`** — AI 解析模板
- 请求: `multipart/form-data`，字段名 `file`（Word .docx 文件）
- 响应:
```json
{
  "variables": [
    {"key": "law_firm_name", "label": "律师事务所名称", "category": "company", "data_type": "company_name", "required": true, "is_multiple": false, "is_registered": true},
    {"key": "handling_lawyer", "label": "经办律师", "category": "lawyer", "data_type": "text", "required": true, "is_multiple": true, "is_registered": true},
    {"key": "custom_field", "label": "自定义字段", "category": "other", "data_type": "text", "required": false, "is_multiple": false, "is_registered": false}
  ],
  "ai_used": true,
  "parse_duration_ms": 1250
}
```
- `is_registered`: 该 key 是否已在 `VARIABLE_REGISTRY` 或 `_runtime_registry` 中注册，false 时前端标记为「待确认」

**`PUT /api/projects/{id}/variables`** — 批量保存变量值
- 请求:
```json
{
  "variables": [
    {"key": "law_firm_director", "value": "张三", "updated_at": "2026-06-08T10:00:00Z"},
    {"key": "handling_lawyer_1", "value": "李四", "updated_at": "2026-06-08T10:00:00Z"},
    {"key": "handling_lawyer_2", "value": "王五", "updated_at": "2026-06-08T10:00:00Z"}
  ]
}
```
- 响应: 统一错误响应格式（见下方）
- 乐观锁（逐行校验）: 每行变量独立校验 `updated_at`，成功的行写入，冲突的行返回错误报告。不再整体回滚，而是部分成功，复用统一错误响应结构。例如用户填了 20 个变量，其中 2 个并发冲突，则 18 个成功写入、2 个返回冲突错误及当前 `updated_at`，前端可针对性刷新冲突行

**`GET /api/projects/{id}/variables`** — 获取去重后的变量列表
- 响应:
```json
{
  "variables": [
    {"key": "law_firm_director", "label": "律师事务所负责人", "value": "张三", "category": "lawyer", "data_type": "text", "required": true, "is_multiple": false, "sort_order": 1, "source_template_ids": [1, 2], "updated_at": "2026-06-08T10:00:00Z"},
    {"key": "handling_lawyer_1", "label": "经办律师", "value": "李四", "category": "lawyer", "data_type": "text", "required": true, "is_multiple": true, "sort_order": 2, "source_template_ids": [1], "updated_at": "2026-06-08T10:00:00Z"}
  ]
}
```
- `required`: 由来源模板合并而来（任一来源标记为 required 即为 True），前端据此渲染必填标记与表单校验

**`GET /api/templates/{id}`** — 模板详情
- 响应包含 `variables_json`（变量定义列表）和模板元数据（名称、描述、分类、标签、适用场景、变量数量）。MVP 阶段不做 Word 内容 HTML 预览（Word 转 HTML 在 Python 生态中效果有限），以变量列表预览 + 元数据展示替代

### 统一错误响应格式

批量操作（变量保存、Excel 导入等）使用统一的错误响应结构：

```json
{
  "success": [{"key": "law_firm_director", "value": "张三"}],
  "errors": [
    {"row": 3, "key": "id_number", "message": "身份证号格式错误"},
    {"row": 5, "key": "company_name", "message": "公司名称不合法"}
  ],
  "summary": {"total": 10, "succeeded": 8, "failed": 2}
}
```

单项操作的错误响应：
```json
{"detail": "错误描述", "code": "CONFLICT", "current_updated_at": "2026-06-08T10:00:00Z"}
```

### 模板上传与解析流程

`POST /api/templates` 和 `POST /api/templates/parse` 的关系：
1. 用户上传 Word 文件 → 调用 `POST /api/templates/parse` 触发 AI 解析，返回变量列表预览
2. 用户确认/修正解析结果 → 调用 `POST /api/templates` 正式创建模板记录（携带确认后的变量定义）
3. 若 AI 服务不可用，用户可手工定义变量列表后直接调用 `POST /api/templates` 创建

### 模板更新与项目刷新流程

**场景**: 律师查看生成的 Word 后发现措辞/格式不对，需要修改模板文件本身，然后重新生成。

**Step 1: 更新模板** (`PUT /api/templates/{id}`)
1. 用户重新上传修改后的 Word 文件（同一模板的新版本）
2. 系统触发 AI 重新解析变量（与创建时相同的 `POST /api/templates/parse` 流程）
3. 用户确认变量变更后，系统：
   - 替换 `file_path` 指向新文件
   - 更新 `variables_json` 为新版本的变量定义
   - `version` 自增（如 v1 → v2）

**Step 2: 项目刷新模板** (`POST /api/projects/{id}/templates/{template_id}/refresh`)
1. 前端检测到 `ProjectTemplate.template_version < Template.version`，在 Step 1 模板列表中显示「模板已更新」徽标和「刷新」按钮
2. 用户点击「刷新」后，系统：
   - 更新 `ProjectTemplate.template_version` 为最新值
   - 更新 `variables_snapshot_json` 为新版本快照
   - **同步 Variable 表**（保留已填值）：
     - 新增变量: 在新版本中新增的变量 → 创建 Variable 行（value 为空，待用户填写）
     - 删除变量: 在新版本中移除的变量 → 从 `source_template_ids` 中移除该 template_id（遵循已有的清理逻辑）
     - 保留变量: key 相同的变量保留原值不丢失
3. 用户可返回 Step 2 填写新增变量，然后重新生成

```python
# 伪代码：模板刷新时的变量 diff 算法
def refresh_template_variables(project_id, template_id, new_variables_json):
    pt = db.query(ProjectTemplate).filter(project_id, template_id).first()
    old_snapshot = pt.variables_snapshot_json  # 旧版本快照
    new_snapshot = new_variables_json          # 新版本变量定义

    old_keys = {v["key"] for v in old_snapshot}
    new_keys = {v["key"] for v in new_snapshot}

    added_keys = new_keys - old_keys      # 新增的变量 key
    removed_keys = old_keys - new_keys    # 删除的变量 key
    kept_keys = old_keys & new_keys       # 保留的变量 key

    # 1. 处理新增变量：创建 Variable 行（value 为空）
    for key in added_keys:
        var_def = next(v for v in new_snapshot if v["key"] == key)
        db.add(Variable(
            project_id=project_id, key=key, label=var_def["label"],
            value="", is_multiple=var_def.get("is_multiple", False),
            required=var_def.get("required", False),
            source_template_ids=[template_id], ...
        ))

    # 2. 处理删除变量：从 source_template_ids 中移除该 template_id
    for key in removed_keys:
        var = db.query(Variable).filter(project_id=project_id, key=key).first()
        if var:
            var.source_template_ids = [tid for tid in var.source_template_ids if tid != template_id]
            if not var.source_template_ids:
                db.delete(var)  # 无其他来源 → 删除

    # 3. 保留变量：key 相同的变量保留原值不丢失，但重新计算 required
    # （任一来源模板标记为 required，该变量即为必填）
    for key in kept_keys:
        var = db.query(Variable).filter(project_id=project_id, key=key).first()
        # 从所有来源模板的 variables_snapshot_json 中合并 required
        source_templates = db.query(ProjectTemplate).filter(
            ProjectTemplate.project_id == project_id,
            ProjectTemplate.template_id.in_(var.source_template_ids)
        ).all()
        var.required = any(
            v_def.get("required", False)
            for pt in source_templates
            for v_def in pt.variables_snapshot_json
            if v_def["key"] == key
        )

    # 4. 更新快照和版本号
    pt.variables_snapshot_json = new_snapshot
    pt.template_version = db.query(Template).get(template_id).version

    # 5. 重算 sort_order
    remaining = db.query(Variable).filter(project_id=project_id).order_by("category", "sort_order").all()
    for i, var in enumerate(remaining):
        var.sort_order = i + 1

    db.commit()
    return {"added": len(added_keys), "removed": len(removed_keys), "kept": len(kept_keys)}
```

**关键设计点**:
- 模板更新不影响已选该模板的项目，必须用户主动点击「刷新」才生效（避免静默变更）
- 刷新时已填写的变量值全部保留，仅同步变量结构（新增/删除）
- 刷新后已生成的文件不自动删除，用户可手动重新生成

### 移除模板后的 Variable 清理逻辑

当用户通过 `DELETE /api/projects/{id}/templates/{template_id}` 移除已选模板时，需同步清理 Variable 表：

1. **删除 ProjectTemplate 记录**: 移除项目与该模板的关联
2. **更新 source_template_ids**: 遍历该项目下所有 Variable，将被移除的 `template_id` 从其 `source_template_ids` 列表中移除
3. **删除孤立变量**: 若某 Variable 的 `source_template_ids` 变为空列表（即该变量仅来源于被移除的模板），则删除该 Variable 行
4. **保留共享变量**: 若 Variable 的 `source_template_ids` 仍包含其他模板 ID（即该变量被多个模板共享），仅移除被删模板的 ID，变量行保留，用户已填写的 value 不丢失
5. **重算 sort_order**: 清理后重新编排剩余变量的 `sort_order`，确保前端展示连续

```python
# 伪代码：移除模板后的变量清理
def remove_template_from_project(project_id, template_id):
    # 1. 删除 ProjectTemplate 关联
    db.delete(ProjectTemplate.filter(project_id, template_id))

    # 2. 获取项目所有变量
    variables = db.query(Variable).filter(project_id=project_id).all()

    for var in variables:
        # 3. 从 source_template_ids 中移除该 template_id
        var.source_template_ids = [tid for tid in var.source_template_ids if tid != template_id]

        if not var.source_template_ids:
            # 4. 无任何来源模板 → 删除该变量
            db.delete(var)
        # 5. 仍有其他来源 → 保留，SQLAlchemy 自动追踪修改，无需 db.add()

    # 6. 重算 sort_order
    remaining = db.query(Variable).filter(project_id=project_id).order_by("category", "sort_order").all()
    for i, var in enumerate(remaining):
        var.sort_order = i + 1

    db.commit()
```

---

## 前端页面

### 技术栈补充
- 路由: react-router-dom v6（客户端路由）
- 全局错误处理: React Error Boundary 包裹页面级组件，防止局部错误导致白屏
- 状态管理: React 内置 useState/useReducer，MVP 不引入 Redux/Zustand

### 页面 1: 项目列表页 `/`
- 显示所有项目，支持新建、删除项目

### 页面 2: 项目详情页 `/projects/:id`

**Step 间状态流转**:
- Step 1 → Step 2: 用户勾选至少 1 个模板后，点击「下一步」进入 Step 2。此时前端调用 `POST /api/projects/{id}/templates` 保存模板选择，后端自动完成变量去重并创建 Variable 表行。Step 2 加载时调用 `GET /api/projects/{id}/variables` 获取去重后的变量列表渲染表单
- Step 2 → Step 3: 用户填写变量后可点击「下一步」进入 Step 3。此时前端调用 `PUT /api/projects/{id}/variables` 保存变量值。Step 3 显示生成与下载界面
- 回退: 用户可自由回退到前一步，已保存的数据不会丢失。回退 Step 1 时可修改模板选择，触发 Variable 表重新同步：
  - **移除模板**: 遵循第 967 行的清理逻辑（从 `source_template_ids` 移除，孤立变量自动删除）
  - **添加模板**: 对新模板的变量执行 diff 算法——仅为该模板**新增**的 key 创建 Variable 行（value 为空），已在 Variable 表中存在的 key（被其他模板共享）仅追加 `source_template_ids`，保留已填值不覆盖。与"模板刷新增加变量"逻辑一致
  - 冲突处理: 若新模板的变量 key 与已有变量相同但 label 不同，以 Variable 中已存在的 label 为准（首次落地时的 label 不变），不覆盖用户的已填值
- 变量去重时机: 在 Step 1 保存模板选择时自动触发精确 key 去重；AI 语义去重为 Step 2 中手动触发的可选操作

分步骤(Tabs/Steps):
- Step 1: 选择模板(多选 checkbox)
  - 模板库以卡片网格形式展示，每张卡片显示：模板名称、分类标签、适用场景、变量数量
  - 支持按分类筛选、按名称搜索
  - 预置模板卡片带「系统预置」徽标，自定义模板带「自定义」徽标
  - 点击卡片可展开模板详情：变量列表预览（含 key/label/category/required 等属性）、模板元数据展示（名称、分类、适用场景、标签、变量数量）
  - 支持上传自定义模板，触发「AI 模板解析」自动提取变量
  - 支持移除已选模板（可撤销误操作）
  - 已选模板若检测到 `template_version < Template.version`，显示「模板已更新」徽标 + 「刷新」按钮，点击后同步变量结构（保留已填值）
- Step 2: 填写变量(表单 + Excel导入/导出按钮)
  - 变量按 category 分组显示，组内按 sort_order 排序
  - 相同 key 的变量只显示一个输入框(去重)
  - multiple 类型变量（如经办律师）: 支持动态添加/删除行，默认显示 2 行
  - 基础格式校验（正则，如身份证号、公司名）: 实时内联校验，输入时即时反馈
  - AI 语义校验: 手动按钮触发，展示校验报告（区分基础校验和 AI 校验）
  - 「AI 智能去重」按钮: 点击后展示 AI 建议的合并方案，用户确认
- Excel 导入: 先调用 import-preview 预览解析结果和错误行，用户确认后再正式导入；错误行支持「下载错误报告」，用户修改后重新上传
  - Excel 列头约定: 第一列为「变量标识(key)」，第二列为「变量名称(label)」（仅展示，不参与解析），第三列为「值(value)」。导出模板时自动生成列头，导入时按 key 列匹配变量
- Step 3: 生成与下载
  - **生成前变量确认**: 点击「生成签字页」按钮后，先弹出确认面板，按模板维度展示每个变量将填入的值（key → value 对照表），用户审阅无误后点击「确认生成」。理由: 律师签字前可能在 Word 中手动微调格式/措辞，若变量值本身填错，手动编辑无法发现，需在生成前拦截
  - 确认后显示进度条，异步轮询生成状态
  - 生成进度: 显示 `已完成/总数`，支持 cancelled/failed 状态提示
  - “取消生成”按钮: 可中止正在进行的生成任务
  - 生成文件列表，支持单个下载和 ZIP 打包下载
- AI 功能区域: 页面右侧或底部以卡片形式展示 AI 分析结果，带明显的「AI」标签
- AI 服务降级: 若 AI 服务不可用，显示降级提示，基础功能（手工去重、正则校验）不受影响

### UI 风格: 企业级设计
- 整体风格: 简洁、专业、克制的企业级 UI，类似 Ant Design Pro / Salesforce Lightning 风格
- 色彩: 主色调采用深蓝/灰色系，避免花哨的渐变色
- 布局: 顶部导航栏 + 面包屑 + 内容区域（MVP 页面较少，无需左侧导航栏，V2 功能扩展后再引入）
- 组件风格: shadcn/ui 默认风格，保持简洁、一致的交互
- 表格: 支持排序、筛选、分页的标准企业表格
- 表单: 清晰的标签、内联校验提示、分组展示
- AI 区域: 用蓝色边框 + AI 图标区分，建议卡片带「采纳/拒绝」按钮
- 状态反馈: Loading skeleton、空状态、操作成功/失败 toast

### API 调用状态处理规范

前端 `services/api.ts` 层统一封装每个 API 调用的三种状态，确保所有页面有一致的交互体验：

- **Loading 状态**: 每个异步请求触发时显示 loading 状态（按钮 disabled + spinner、列表 skeleton、AI 卡片 loading 动画）。多个并发请求独立管理 loading 状态，不互相干扰
- **Error 状态**: 统一拦截 HTTP 错误响应，按错误类型分类处理：
  - 网络错误: 显示「网络连接失败，请检查网络后重试」toast
  - 4xx 业务错误: 显示服务端返回的 `detail` 消息（如乐观锁冲突、格式校验失败）
  - 409 冲突: 显示「数据已被修改，请刷新后重试」并附带冲突详情
  - 5xx 服务端错误: 显示「服务异常，请稍后重试」toast
- **Success 状态**: 写操作（创建/更新/删除）成功后显示 toast 提示；读操作成功后静默更新 UI
- **React Error Boundary**: 包裹页面级组件，捕获渲染层错误，展示「页面出错，请刷新」降级页面，防止局部错误导致白屏

---

## 模板渲染方案

Word 模板中使用 `{{key}}` 占位符（标准化英文 key，如 `{{law_firm_director}}`）。后端使用 **docxtpl** 库（基于 python-docx 的 Jinja2 模板引擎）读取模板并替换占位符，保存为新文件。

**选型理由**:
- 手写 python-docx 替换占位符有已知坑：Word 可能将 `{{key}}` 拆分为多个 Run（如 `{{` 在一个 Run、`key` 在另一个 Run、`}}` 在又一个 Run），直接按段落文本替换会失败
- docxtpl 内部已处理 Run 合并问题，并支持 Jinja2 模板语法（循环、条件等），更稳健
- 签字页对排版（缩进、对齐、空行、字体格式）要求很高，docxtpl 替换占位符时会保留原有 Run 的字体样式和段落格式

**排版保持策略**:
- 占位符替换不会改变段落格式（字体、字号、缩进、对齐方式均保留）
- 模板中的空行、分页符等结构元素在生成后保持不变
- 对于多个经办律师等 multiple 类型变量，使用 Jinja2 循环语法 `{% for lawyer in handling_lawyers %}...{% endfor %}` 动态生成重复行

### 变量去重逻辑
1. 项目选择多个模板后，收集所有模板的变量定义
2. 先按精确 key 匹配去重，再通过 AI 语义分析识别别名并建议合并
3. 合并后维护 `alias_map`，确保原模板中所有 key（含被合并的旧 key）在生成时统一替换
4. 用户填写变量值后，生成时对所有选中模板统一替换

---

## PRD 差异说明

以下列出 MVP 实现与 PRD 原始需求的差异，作为后续迭代的规划依据：

| PRD 原始需求 | MVP 实现 | 后续规划 |
|------|------|------|
| 生成 PDF/docx 附件 | 仅生成 Word (.docx) | V2 增加 PDF 输出（基于 python-docx2pdf 或 libreoffice 转换） |
| 系统实时校验 | 基础格式校验（正则）实时内联 + AI 语义校验手动触发 | V2 增加更丰富的实时校验规则 |
| 部分成功可回写（Excel 导入） | 通过 import-preview 先预览错误行，确认后部分成功写入 | MVP 已覆盖，确保容错体验 |
| 登录系统 | 无登录，mock 当前用户 | V2 增加用户认证（JWT / OAuth） |
| 套表组概念 | 以“多模板多选”替代，未引入套表组抽象 | V2 可引入套表组模板包概念 |

---

## Task 分解

### Task 0: 环境准备
- **优先确保真实 LLM 可用**: 在 OrbStack VM 中安装并启动 OpenCode Server（`opencode serve`）
- 验证 LLM API 可调用：发送测试 prompt，确认后端可通过 HTTP 访问 OpenCode Server
- 验证三个 AI 场景的端到端调用（模板解析/变量去重/数据校验）：用真实 LLM 输出验证 Prompt 工程 + Pydantic Schema 校验 + 重试机制是否工作正常
- **并行配置 Mock Provider**: 编写三个 AI 场景的 Mock 响应，确保返回结构符合 Pydantic Schema，作为 LLM 服务不可用时的降级保底

> **优先级说明**: 开发初期使用 Mock Provider 确保前后端联调不阻塞。Mock 通过后切换到真实 LLM（`LLM_PROVIDER=opencode`）验证 Prompt 工程、结构化输出校验、重试降级等 AI 可靠性策略，这些策略只有用真实 LLM 才能充分验证。

### Task 1a: 后端项目初始化与数据层
- 初始化 Python 项目，安装依赖(FastAPI, SQLAlchemy, Alembic, docxtpl, openpyxl, httpx)
- 创建数据库模型和 SQLite 配置（含 GenerationTask、AILog、CustomVariable 模型，启用 WAL 模式）
- 初始化 Alembic 迁移环境（`render_as_batch=True`），生成首个 migration 脚本
- 实现 MVP 变量映射表（app/services/variable_registry.py）
- **DoD**: `alembic upgrade head` 成功创建表结构，`database.py` 连接 SQLite 正常（可读/写测试表）

### Task 1b: 后端 API 基础 + LLM 抽象层
- 创建 LLMProvider 抽象层（app/services/llm/ 目录，含 base、opencode、openai、mock 四个实现 + factory + mock_responses）
- 实现项目 CRUD API（含删除时先取消生成任务 + 级联清理生成文件）
- 实现健康检查 API (`GET /api/health`，含 LLM Provider 可用性、当前 Provider 类型）
- **DoD**: 项目 CRUD API 全部可调用，删除项目时级联清理验证通过，健康检查返回 LLM 状态

### Task 2: 模板管理与 AI 解析
- 创建 3 个 Word 模板文件(含 `{{key}}` 占位符，使用 docxtpl 兼容语法)
- 实现模板列表/详情/删除 API（含预置模板不可删除的 403 保护）
- 实现模板更新 API (`PUT /api/templates/{id}`：重新上传 Word、AI 重新解析、version 自增)
- 实现项目-模板关联 API（含 variables_snapshot_json 快照 + template_version + 移除模板 API + Variable 表清理逻辑：source_template_ids 为空时删除变量）
- 实现项目模板刷新 API (`POST /api/projects/{id}/templates/{template_id}/refresh`：更新快照 + diff 算法同步 Variable 表保留已填值)
- 实现 AI 模板解析服务（通过 LLM 调用，Prompt 工程）
- 实现模板上传与 AI 解析 API
- **DoD**: 3 个预置模板可列表/详情查看，自定义模板上传 + AI 解析流程可走通，模板刷新后变量 diff 正确

### Task 3: 变量填写、AI 去重与校验
- 实现变量去重合并逻辑（精确 key 匹配 + 映射表 aliases 别名匹配 + AI 语义分析）
- 实现变量保存 API（含逐行乐观锁并发控制，部分成功响应）
- 实现 AI 变量智能去重服务（LLM 语义分析 + 映射表规则校验）
- 实现 AI 智能校验服务（LLM 业务理解 + 映射表/正则硬规则校验）
- 实现 Excel 模板导出(空白模板，供用户填写)
- 实现已填写变量数据导出（Excel）
- 实现 Excel 导入预览 API（import-preview：无状态解析 + 校验，返回成功行和错误行）
- 实现 Excel 确认导入 API（部分成功策略：成功行写入，失败行返回错误报告）
- **DoD**: 变量保存逐行校验可验证，Excel 导入预览→确认导入流程可走通，AI 去重/校验服务可调用（或降级）

### Task 4: 文档生成与下载（含异步生成）
- 实现 Word 模板渲染(使用 docxtpl，支持 alias_map 别名替换 + Jinja2 循环语法)
- 实现异步生成任务: `POST /generate` 创建 GenerationTask，使用 `ThreadPoolExecutor(max_workers=2)` 在独立线程中执行（不使用 FastAPI BackgroundTasks，避免阻塞事件循环）
- 实现基于 `threading.Event` 的取消机制: 每个任务关联一个 Event 对象，生成线程每完成一个文件后检查 `cancel_event.is_set()`，为 True 则状态置为 cancelled 并退出
- 实现生成任务取消: `POST /generate/cancel`（数据库状态置为 cancelled + 调用 `cancel_event.set()` 通知后台线程终止）
- 实现生成状态轮询 API: `GET /generate/status` 返回进度（completed_count/total_count/status）
- 前端轮询策略: 采用**指数退避**策略（2s → 4s → 8s → 最大可配置，默认 10s），减少长时间生成任务对服务器的请求压力，completed/failed/cancelled 时停止
- 应用关闭时通过 lifespan 事件调用 `executor.shutdown(wait=False)` 清理线程池
- 实现单文件下载
- 实现 ZIP 打包下载
- **DoD**: 选择模板 + 填写变量后可成功生成 Word 文件，取消生成可中止任务，单文件/ZIP 下载可用

### Task 5a-1: 前端基础搭建 - 项目初始化与列表页
- 初始化 React + TS + Vite + Tailwind CSS + shadcn/ui 项目
- 配置 Vite 开发代理（`/api` → 后端）
- 配置 react-router-dom 路由（/ 和 /projects/:id）
- 配置 React Error Boundary（包裹页面级组件）
- 封装 API 调用层（services/api.ts，统一 fetch + 错误处理，含 Loading/Error/Success 三态封装）
- 实现项目列表页（新建、列表、删除）
- **前后端对接策略**: 此阶段仅依赖后端 Task 1b 的基础 API（项目 CRUD、健康检查）。若后端未 ready，前端使用 mock 数据开发 UI，后端 ready 后切换为真实 API 调用
- **DoD**: 项目列表页 mock 数据下 CRUD 流程可走通，Error Boundary 捕获渲染错误，API 层统一封装（含 Loading/Error/Success 三态）正确

### Task 5a-2: 前端基础搭建 - 项目详情页
- 实现项目详情页基础框架（Steps 导航 + 步骤切换 + Step 间状态流转逻辑）
- Step 1: 模板选择（多选 checkbox + 模板元数据展示 + 自定义模板上传 + 移除模板 + 模板更新徽标与刷新按钮）
- Step 2: 变量填写表单（按 category 分组、去重显示、multiple 变量动态增减、基础正则实时校验、Excel 导入预览/导出按钮、错误行下载与重新上传）
- 变量表单防丢策略: 监听 `beforeunload` 事件，当表单有未保存变更时提示用户；可选用 `sessionStorage` 做草稿缓存
- Step 3: 生成与下载（生成前变量确认弹窗 + 生成按钮 + 指数退避进度轮询 + 取消按钮 + 文件列表 + 单个/ZIP 下载）
- 对接后端 API（项目 CRUD、模板、变量、生成）
- **DoD**: 三步流程可走通（模板选择 → 变量填写 → 生成下载），Step 间回退不丢数据，multiple 变量可动态增减

### Task 5b: 前端 AI 功能集成
- 模板上传后的 AI 解析结果展示（带「AI」标签，支持确认/修正）
- 「AI 智能去重」按钮与合并建议卡片（逐条采纳/拒绝，低风险默认采纳）
- 「AI 校验」按钮与校验报告展示（error/warning 分级，标注「AI 校验」标签，区分基础校验和 AI 校验）
- AI 加载状态（skeleton/loading 动画）与错误处理
- AI 服务降级提示（当 AI 不可用时显示友好提示，基础功能不受影响）
- 对接 AI 相关后端 API（解析/去重/校验）
- **DoD**: AI 解析/去重/校验三个场景前端均可展示，降级提示正常，AI 结果可采纳/拒绝

### Task 6: 联调测试
- 启动前后端服务
- 完整流程测试: 创建项目 -> 选模板(含AI解析) -> 填变量 -> AI去重 -> AI校验 -> 生成下载
- 验证健康检查 API、错误响应格式、Excel 导入错误行修正流程
- 验证乐观锁逐行校验（模拟并发冲突）
- 验证模板刷新 diff 算法（新增/删除/保留变量）
- 验证删除项目时先取消生成任务的竞态处理
- 运行后端集成测试（pytest）
- 修复问题
- **DoD**: 端到端流程可完整走通，所有后端集成测试通过，无未修复的 P0/P1 问题

### Task 7: AI 工具使用记录报告
- 编写 AI 参与环节说明报告（包括开发过程中使用的 AI 工具 + 系统内置的 AI 能力说明）

### Task 依赖关系

```
Task 0 (环境准备)
  └─> Task 1a (后端初始化与数据层)
        └─> Task 1b (后端 API + LLM 抽象层)
              ├─> Task 2 (模板管理)      ──┐
              ├─> Task 3 (变量填写)      ──┤── 可并行
              └─> Task 4 (文档生成)      ──┘
                    └─> Task 5a-1 (前端初始化，可用 mock 数据先行)
                          └─> Task 5a-2 (前端详情页，依赖 Task 2/3/4 后端 API)
                                └─> Task 5b (前端 AI 集成，依赖 Task 2/3 的 AI API)
                                      └─> Task 6 (联调测试)
                                            └─> Task 7 (报告)
```

Task 2/3/4 后端 API 可并行开发，Task 5a-1 仅需后端基础 API 即可启动（可用 mock 数据先行开发）。