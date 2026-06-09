# AI 输出可信机制

> 如何让 LLM 在业务系统中既提效又可信。不是"检测幻觉"，而是"让 AI 无法产生幻觉"。

## 核心原则

**AI 不产生数据，只产生建议。** 建议经过三层防御后才能落地为数据：

```
AI 输出 → ① 规则层 → ② 交叉验证层 → ③ 人类确认层 → 数据
```

| 层级 | 作用 | 实现 | 能否被绕过 |
|------|------|------|-----------|
| ① 规则层 | 确定性约束，AI 不可违反 | Pydantic Schema、VARIABLE_REGISTRY、VALIDATION_RULES | 否（失败即重试/降级） |
| ② 交叉验证层 | AI 输出与规则基线比对 | `ai_guardrail.py` 中三个场景的 cross_validate 函数 | 否（硬编码在业务流中） |
| ③ 人类确认层 | 最终决策权 | MEDIUM 标记待确认、LOW 强制逐条审核 | 是（但系统设计上鼓励遵守） |

## Guardrail 模块架构

```
backend/app/services/ai_guardrail.py
├── TrustLevel          # HIGH / MEDIUM / LOW 枚举
├── cross_validate_parsed_variables()   # AI-1 模板解析
├── cross_validate_dedup_suggestions()  # AI-2 变量去重
└── cross_validate_issues()             # AI-3 数据校验
```

每个函数遵循相同的模式：**接收 AI 原始输出 + 规则基线 → 输出可信评级后的增强数据**。不修改数据库、不产生副作用，是纯函数。

## 三个场景的交叉验证逻辑

### AI-1: 模板解析

```
变量已注册 + category 一致                → HIGH  信任
变量未注册，但 label 匹配注册表别名        → MEDIUM 建议标准 key
变量未注册，别名也匹配不上                → LOW   人工确认
变量已注册但 AI 给错了 category          → 降一级
```

### AI-2: 变量去重

```
AI 建议的合并对 (keep, merge) 与 alias 规则全部一致 → HIGH  信任
AI 建议与规则无矛盾但无规则确认 + confidence>=0.5  → MEDIUM 待确认
AI 建议与规则无矛盾但 confidence<0.5               → LOW   人工判断
AI 建议与规则 alias 关系矛盾                       → LOW   强制审查
```

注：规则建议（`get_alias_dedup_suggestions`）固定为 HIGH，不因 AI 未提及而降级。

### AI-3: 数据校验

```
正则和 AI 同时标记的变量   → 保留，cross_validated=true
正则标记但 AI 未发现       → 保留（确定性规则优先）
AI 标记但正则未发现        → 保留，source=ai_only
```

## 为什么这是"可信"而非"检测"？

传统"幻觉检测"是**事后**的——先让 AI 输出，再判断它是不是幻觉。这种方法的问题是：

1. 如果不能检测所有幻觉（统计模型的概率性缺陷），就仍然不可信
2. 检测本身也可能误报
3. 用户无法区分"AI 说的"和"系统确认的"

本系统的做法是**事前防御**：

| 传统做法 | 本系统做法 |
|---------|-----------|
| AI 直接写库 | AI 只输出建议，经交叉验证 + 人类确认后才写库 |
| 依赖 AI 准确率 | 依赖规则层确定性约束（100% 正确） |
| 检测幻觉 | 消除幻觉的影响范围（不信任 -> 不产生不良影响） |
| 一条 AI 结论 | 三条线（规则 / AI / 人类）相互制衡 |

## 关键设计决策

### 1. trust_level 不入库

trust_level 是运行时计算值，附加在 API 响应中。不增加数据库字段，不影响已有数据模型。前端根据 trust_level 控制 UI 交互。

### 2. 规则优先级 > AI 优先级

规则发现的问题即使 AI 漏报了也保留。AI 发现的问题如果规则没发现则标记 `ai_only`。规则作为"最低可信线"，AI 作为"补充视野"。

### 3. confidence 阈值只在下行方向使用

confidence < 0.5 强制降级到 LOW。但 confidence >= 0.9 不自动升到 HIGH——还需要 `rules_match=true`。这是为了**防止 high-confidence 幻觉**（LLM 以高置信度输出错误信息是其典型失败模式）。

### 4. 交叉验证不改变 AI 原始输出结构

只是在原始数据上附加 `trust_level`、`warnings`、`suggested_key`、`rules_match`、`cross_validated` 等字段。前端可以据此控制展示，而无需理解复杂的交叉验证逻辑。

## 未来的改进方向

- **V2 引入 Ontology**：将 VARIABLE_REGISTRY 升级为完整领域本体，交叉验证规则更精细
- **Guardrail 日志**：记录每次交叉验证结果，统计 AI 与规则的一致率，发现 prompt 薄弱环节
- **动态阈值**：根据历史一致率自动调整 confidence 阈值
- **规则自动学习**：将用户确认后的 AI 有效建议自动补充到注册表 aliases 中
