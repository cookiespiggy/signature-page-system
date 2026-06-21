# 签字页管理系统 — 架构推演（不只是偏执，是体系）

> **一句话定性**：这不是一个 CRUD + 异步任务的应用。这是一个**面向合规的文档生命周期管理平台**，核心诉求是：可审计、可恢复、可演进。

---

## 一、当前架构的核心问题：隐式状态机散落一地

```
当前状态管理：
┌─ Project.status (draft → generating → completed)
├─ GenerationTask.status (pending → processing → completed/failed/cancelled)
├─ GeneratedFile.status
├─ Variable.updated_at (乐观锁版本)
├─ AILog (手动记录)
└─ ThreadPoolExecutor + threading.Event (进程内，不可持久化)

问题：同一个"生成"行为的语义拆分在 5 个地方，手动保持同步。
      进程挂了，状态全部丢失。
```

作为架构师，你真正在解决的是：**状态的持久化、恢复、审计**。当前方案把所有复杂度压在了数据库表设计 + 业务代码里。Temporal 的本质不是"把生成换成 Workflow"，而是**把整个系统的状态机交给 Durable Execution 引擎**。

---

## 二、Temporal 视角下的系统重构

### 2.1 不是"一个 Workflow"，是整个系统就是 Workflow

| 当前 | Temporal 映射 |
|------|-------------|
| 用户创建项目 | `CreateProjectWorkflow` 启动 |
| 选择模板（多选） | `SelectTemplatesActivity` → 触发 `TemplateSelected` Signal |
| 填写变量 | `UpdateVariablesActivity`（带版本控制） |
| AI 解析/去重/校验 | 三个 Child Workflow，每个有独立重试策略 + 补偿 |
| 点击生成 | Signal → `DocumentGenerationWorkflow` 开始 |
| 生成中取消 | Signal → `CancelGeneration` → 补偿（清理部分文件）|
| 下载文件 | Query（查 Event History 中的文件路径） |
| 删除项目 | `DeleteProjectWorkflow` → 补偿（清理文件 + 通知） |

**关键区别**：当前系统里"状态"是 DB 表的列；Temporal 里"状态"是 Event History——**天然不可篡改、天然可审计、天然可恢复**。

### 2.2 三个 AI 场景从"API 调用"变成"Durable Activity"

> **修正**：三个 AI 场景（解析/去重/校验）彼此独立，不存在"做一半要回滚"的连锁依赖。不是 Saga，是 **Durable Activity with Retry & Fallback**。

当前：
```
用户点 "AI 去重" → API 调用 → await ai_service → 返回结果 → 前端展示
如果 LLM 超时 → 降级 → 用户只看到 "AI 不可用"
```

Temporal Activity 模式：
```
用户点 "AI 去重" → Signal 触发 DedupWorkflow
  └─ Activity: GetAIDedupSuggestions(retry=3, timeout=30s)
       ├─ 成功 → CrossValidateWithGuardrail → 返回前端
       └─ 全部重试失败 → 自动降级（返回 FallbackResult，不抛异常）
```

优势：
- **重试策略统一管理**：当前 `ai_service.py` 手写 `for attempt in range(MAX_RETRIES)` → Temporal 声明式配置 `retry_policy`
- **调用即记录**：Activity 的开始/结束/失败/重试都在 Event History 中，不需要手动 `AILog` 表
- **超时精确控制**：当前 `LLM_TIMEOUT_SECONDS = 30.0` 是硬编码 → Temporal 支持 `start_to_close_timeout` + `schedule_to_close_timeout` 两层控制
- **各 Activity 独立伸缩**：AI 调用限流（API Key quota）和文件渲染（CPU 密集）可以分到不同 Task Queue

### 2.3 审计不再需要 AILog 表

当前：`AILog` 手写插入，project 删除时 `SET NULL`，查询用 ORM。

Temporal：Event History 本身就是审计日志。每条记录包含：
- 谁触发了（用户 ID）
- 什么 Workflow（ai_dedup）
- 什么 Activity（call_llm、cross_validate）
- 输入输出（prompt、response、validation_result）
- 耗时（Activity 开始-结束时间戳）
- 重试次数（attempt）

**AILog 表变成了 Materialized View**——从 Temporal 导出到 OLAP 库做分析用，不再是权威源。

### 2.4 并发和伸缩

当前：`ThreadPoolExecutor(max_workers=2)`。两个律师同时生成就排队。

Temporal：Task Queue + Worker Pool。一个 Worker 进程可以注册处理所有 Activity。水平扩展只需再加一个 Worker 进程。

```
Temporal Cluster
  ├─ Task Queue: document-generation
  │   ├─ Worker 1 (macOS dev)
  │   └─ Worker 2 (another machine)
  ├─ Task Queue: ai-calls
  │   ├─ Worker 1
  │   └─ Worker 2
  └─ Task Queue: file-cleanup
      └─ Worker 1
```

每个 Task Queue 可以独立配置 `max_concurrent_activities`，AI 调用要限流（API Key 有 quota），文件清理可以放开。

---

## 三、DDD 重新建模：领域事件驱动

当前的 package 结构是按"层"划分的（routers / services / models），架构师视角应该按"限界上下文"划分。

### 3.1 有界上下文（Bounded Context）

```
signature-page-system/
├── context/
│   ├── template-management/     # 模板库 + 预置模板 + 注册表
│   │   ├── TemplateAggregate
│   │   ├── VariableDefinition  # Value Object
│   │   └── TemplateRepository
│   ├── variable-filling/        # 变量编辑 + 乐观锁 + EXCEL
│   │   ├── ProjectVariableAggregate
│   │   ├── VariableValue        # Value Object
│   │   └── ProjectTemplateRepository
│   ├── document-generation/     # 异步生成 + 下载 + ZIP
│   │   ├── GenerationWorkflow  # Temporal Workflow
│   │   ├── RenderActivity
│   │   └── FileStorageService  # 策略模式：本地/S3/MinIO
│   ├── ai-services/             # AI 编排 + Guardrail
│   │   ├── ParsingWorkflow     # Temporal Child Workflow
│   │   ├── DedupWorkflow
│   │   ├── ValidationWorkflow
│   │   └── GuardrailService
│   ├── audit/                   # 审计日志
│   │   └── EventExporter       # Temporal → 分析系统
│   └── iam/                     # 认证 + 授权 (V2)
│       ├── User
│       ├── Role
│       └── Permission
├── shared/                      # 共享内核
│   ├── kernel/
│   │   ├── ValueObject
│   │   ├── DomainEvent
│   │   └── AggregateRoot
│   └── temporal/
│       ├── WorkflowClient
│       └── WorkerBootstrap
└── api/                         # REST 层（薄薄的翻译层）
    ├── routers/
    └── schemas/
```

### 3.2 领域事件

```
template-selected        { projectId, templateId, variableKeys[] }
template-removed         { projectId, templateId }
variables-bulk-updated   { projectId, updates[], conflictKeys[] }
ai-dedup-completed       { projectId, suggestions[], resolvedConflicts }
ai-validation-completed  { projectId, issues[] }
generation-requested     { projectId, taskId }
file-generated           { projectId, templateId, filePath }
generation-completed     { projectId, summary }
generation-cancelled     { projectId, completedCount }
project-deleted          { projectId }
```

事件驱动的好处：
- **解耦**：`document-generation` 不需要知道 `ai-services` 的内部逻辑，只需要订阅 `variables-bulk-updated` 事件
- **可插拔**：未来加 Slack 通知，只需加一个 `SlackNotifier` 订阅相关事件，一行代码不改
- **重放**：Temporal Event History 本身就是事件流，重放等于从头执行一遍

---

## 四、"现在就要改"的事（不是 V2，是接下来）

即使在 Temporal 落地前，架构师现在就应该改的：

### 4.1 把隐式状态机变成显式状态机

当前 `_run_generation` 里有 3 处 `db.commit()`，状态散落。应该先用一个 `GenerationStateMachine` 封装：

```python
class GenerationStateMachine:
    """显式状态机，不是散落的 if-else"""
    
    transitions = {
        "pending": ["processing", "cancelled"],
        "processing": ["completed", "failed", "cancelled"],
        "completed": [],
        "failed": [],
        "cancelled": [],
    }
    
    def transition_to(self, new_status: str) -> None:
        if new_status not in self.transitions[self._task.status]:
            raise InvalidTransition(...)
        self._task.status = new_status
```

这不是过度设计。当前代码的"隐式复杂性"。

### 4.2 变量注册表问题：Schema Registry vs Runtime Cache

当前 `variable_registry.py` 既管预置定义又管运行时注册，`get_merged_registry()` 每次合并。应该拆成：

```
VARIABLE_REGISTRY → 静态 Schema Registry（git 版本控制、代码级定义）
RuntimeVariableCache → 运行时动态注册（初始化时从 CustomVariable 表加载）
两个独立，查询时显式选来源
```

### 4.3 用 TypedDict 替换 `dict[str, Any]`

当前 30+ 处 `dict[str, Any]`，类型系统不发挥作用。引入 TypedDict 或 Pydantic 的 `InternalModel`：

```python
from typing import TypedDict

class VariableDict(TypedDict):
    key: str
    label: str
    value: str
    category: str
    data_type: str
    required: bool
    is_multiple: bool
    sort_order: int
```

看起来小改进，但 Pyright/mypy 能帮你拦住 30% 的 bug。

### 4.4 异常层次结构

当前：service 层直接抛 `HTTPException`，routers 层也抛 `HTTPException`。架构上这是**层污染**——service 不应该知道 HTTP 状态码。

```python
# 领域异常
class VariableNotFoundError(DomainError): ...
class OptimisticLockConflictError(DomainError): ...
class TemplateReferencedError(DomainError): ...

# API 层翻译
@router.post(...)
async def handle():
    try:
        service.do_stuff()
    except VariableNotFoundError as e:
        raise HTTPException(404, str(e))
```

---

## 五、Q&A

### 为什么选 ThreadPoolExecutor

**回答**：

> "作为 MVP，ThreadPoolExecutor 是正确的选择——零依赖、启动快、代码少。但作为架构师，我在第一天就知道它是一个**战术决策，不是战略决策**。ThreadPoolExecutor + threading.Event + DB 状态轮询本质上是在手写一个 Durable Execution 引擎的 MVP 子集。它缺失三样东西：持久化恢复、统一审计溯源、时间线无关的水平扩展。
> 
> 我设想的 V2 迁移路径是 Temporal，因为我需要的不是一个异步任务队列，我需要的是**整个系统在 Durable Execution 引擎上建模**。当前代码里散落在 7 个 service 文件中的状态机——Project, GenerationTask, Variable 的乐观锁, AI 调用日志——都会统一到 Workflow 的 Event History 中。AILog 表可能被消灭。当前 `_run_generation` 里的 3 处 `db.commit()` 被消灭。`
> 
> 但我不建议现在迁移。因为 Temporal 引入的运维成本（跑 Server、管理 Worker、处理版本兼容）需要团队准备。所以我现在做的：**把隐式状态机显式化**，先把 `GenerationStateMachine` 抽出来，把 `dict[str, Any]` 换成 TypedDict。这样以后切 Temporal 时，Activity 的边界天然就切好了。"

### 系统最大的技术债是什么

**回答**：

> "不是代码重复，不是缺少注释。最大的技术债是**没有领域模型**——代码按 '层' 组织（services / routers / models）而不是按 '业务上下文' 组织。这导致：修一个模板刷新的 bug 可能涉及到 template_service.py、variable_service.py、ai_guardrail.py 三个文件。
>
> 如果让我重来，我会按有界上下文拆分：template-management、variable-filling、document-generation、ai-services、audit。每个上下文有自己的状态机、自己的异常类型、自己的测试套件。这样 Temporal 引入时，每个上下文天然就是一个 Workflow 或一个 Activity 集合。"

---

## 六、总结

| 维度 | 阶段1 | 阶段2 |
|------|---------------|---------------|
| Temporal | "我考虑过，但当前 ThreadPoolExecutor 够了" | "Temporal 是整个系统的 Durable Execution 层，不是生成任务的替代品。当前没引入是因为运维成本，但我已经为迁移铺路了：显式状态机 + 有界上下文划分" |
| 代码问题 | "这里重复了，我下次会用 TypedDict" | "隐式状态机散落是架构问题，不是代码风格问题。不改 TypedDict 只是症状，治本是重新划分上下文边界" |
| 测试 | "覆盖率 16 个，没有 Todo" | "测试覆盖的是功能路径，不是架构契约。我需要 Contract Test 来验证上下文边界的隔离性" |
| 生产化 | "Docker + CI + PostgreSQL" | "第一优先级不是数据库，是让系统能从进程崩溃中恢复。Temporal 或手动实现 Durable Execution 才是核心生产化门槛" |
