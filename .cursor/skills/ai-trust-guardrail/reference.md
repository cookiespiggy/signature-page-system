# AI 可信机制 — 完整参考

> 源文档：`docs/knowledge-base/AI可信机制.md`

## 可信 vs 幻觉检测

| 传统做法 | 本系统做法 |
|---------|-----------|
| AI 直接写库 | AI 只出建议，交叉验证 + 人类确认后写库 |
| 依赖 AI 准确率 | 依赖规则层确定性约束 |
| 事后检测幻觉 | 事前消除幻觉影响范围 |
| 一条 AI 结论 | 规则 / AI / 人类 三线制衡 |

## 前端对应组件

| 组件 | 场景 |
|------|------|
| `TrustLevelBadge` | 可信等级展示 |
| `ParsedVariablesEditor` | AI-1 解析确认 |
| `DedupSuggestionsPanel` | AI-2 去重采纳/拒绝 |
| `ValidationReportPanel` | AI-3 校验报告 |
| `AiDegradedBanner` | LLM 不可用降级 |

## 未来改进（V2+）

- Ontology 升级 VARIABLE_REGISTRY
- Guardrail 日志统计一致率
- 动态 confidence 阈值
- 用户确认后自动补充 aliases
