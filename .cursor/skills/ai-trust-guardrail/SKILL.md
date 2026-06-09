---
name: ai-trust-guardrail
description: >-
  Implements the three-layer AI trust model for the 签字页管理系统: rule
  constraints, cross-validation guardrails, and human confirmation. Covers
  TrustLevel (HIGH/MEDIUM/LOW), ai_guardrail.py logic for template parse,
  variable dedup, and data validation. Use when modifying AI scenarios,
  trust badges, suggestion panels, or ai_guardrail cross_validate functions.
---

# AI 可信机制

## 核心原则

**AI 不产生数据，只产生建议。** 建议经三层防御后才落地：

```
AI 输出 → ① 规则层 → ② 交叉验证层 → ③ 人类确认层 → 数据
```

| 层级 | 实现 | 可绕过 |
|------|------|--------|
| ① 规则层 | Pydantic Schema、VARIABLE_REGISTRY、VALIDATION_RULES | 否 |
| ② 交叉验证 | `ai_guardrail.py` cross_validate 函数 | 否 |
| ③ 人类确认 | MEDIUM 待确认、LOW 强制逐条审核 | 是（设计上鼓励遵守） |

## Guardrail 模块

```
backend/app/services/ai_guardrail.py
├── TrustLevel (HIGH / MEDIUM / LOW)
├── cross_validate_parsed_variables()   # AI-1
├── cross_validate_dedup_suggestions()  # AI-2
└── cross_validate_issues()             # AI-3
```

纯函数：接收 AI 输出 + 规则基线 → 输出带 trust_level 的增强数据，无副作用。

## 三场景评级逻辑

### AI-1 模板解析
- 已注册 + category 一致 → **HIGH**
- 未注册但 label 匹配别名 → **MEDIUM**（建议标准 key）
- 未注册且别名不匹配 → **LOW**
- 已注册但 category 错误 → 降一级

### AI-2 变量去重
- AI 合并对与 alias 规则一致 → **HIGH**
- 无矛盾 + confidence≥0.5 → **MEDIUM**
- 无矛盾 + confidence<0.5 → **LOW**
- 与 alias 规则矛盾 → **LOW**（强制审查）
- 规则建议（`get_alias_dedup_suggestions`）固定 **HIGH**

### AI-3 数据校验
- 正则 + AI 同时标记 → 保留，`cross_validated=true`
- 仅正则标记 → 保留（规则优先）
- 仅 AI 标记 → 保留，`source=ai_only`

## 关键设计决策

1. **trust_level 不入库** — 运行时计算，API 响应附加，前端控制 UI
2. **规则优先级 > AI** — 规则漏报由 AI 补充，AI 漏报由规则兜底
3. **confidence 只向下用** — <0.5 强制 LOW；≥0.9 不自动升 HIGH，还需 rules_match
4. **不改变 AI 原始结构** — 只附加 trust_level、warnings、suggested_key 等字段

## 详细参考

完整对比表与未来改进方向见 [reference.md](reference.md)。
