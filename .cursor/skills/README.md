# 项目级 Skills

将 `docs/knowledge-base/` 中的开发经验沉淀为 [Cursor Agent Skills](https://cursor.com/docs/context/skills)，供 Agent 按场景自动发现与加载。

## 与 knowledge-base 的关系

| Skill | 源文档 | 触发场景 |
|-------|--------|---------|
| `dev-environment` | `docs/knowledge-base/环境配置.md` | Session 启动、环境排错、联调清理 |
| `opencode-server` | `docs/knowledge-base/OpenCode-Server.md` | LLM 配置、OpenCode 联调 |
| `structured-output` | `docs/knowledge-base/结构化输出.md` | AI Service / Provider 开发 |
| `ai-trust-guardrail` | `docs/knowledge-base/AI可信机制.md` | AI 场景、Guardrail、前端 AI 组件 |
| `ui-design-system` | `docs/knowledge-base/UI设计规范.md` | 任何 `frontend/` 修改 |

## 结构约定

```
.cursor/skills/<skill-name>/
├── SKILL.md        # 精简指令 + YAML frontmatter（Agent 自动发现）
└── reference.md    # 详细参考（按需读取）
```

- **SKILL.md**：可执行检查清单、命令、关键决策（<500 行）
- **reference.md**：完整踩坑与示例，对应 knowledge-base 原文
- **源文档保留**：`docs/knowledge-base/` 仍为人类可读的长文归档；更新知识时同步改 Skill + 源文档

## 使用方式

- Agent 根据 `description` 字段自动匹配场景并读取 SKILL.md
- 用户可显式引用：`@dev-environment`、`@ui-design-system` 等
- Session 开始时仍读 `AGENTS.md` + `.handoff/latest.md`，Skills 补充领域细节
