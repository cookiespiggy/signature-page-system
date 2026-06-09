---
name: structured-output
description: >-
  Implements LLM structured JSON output for template parsing, variable dedup,
  and data validation in the 签字页管理系统. Covers native json_schema via
  OpenCode, prompt-embedded schema fallback, multi-model fallback, and models
  that fail structured output. Use when modifying ai_service, LLM providers,
  Pydantic schemas, or debugging JSON parse/timeout issues in AI scenarios.
---

# LLM 结构化输出

## 策略选择

| 优先级 | 策略 | 适用 |
|--------|------|------|
| 1 | 原生 `format/json_schema` | OpenCode + gpt-5-mini / mimo-v2.5-free |
| 2 | Prompt 嵌入 Schema | MockProvider、OpenAI、不支持 tool calling 的模型 |

## 默认模型链

```
主: github-copilot / gpt-5-mini   (~14s, info.structured 有值)
备: opencode / mimo-v2.5-free     (免费限额有限，耗尽后无限超时)
```

由 `opencode_provider.py` 多候选逻辑自动 fallback。

## 调用模式

```python
# 原生结构化（推荐）
provider.send_message(
    prompt="...",
    format={"type": "json_schema", "schema": schema.model_json_schema()}
)
# 从 info.structured 提取，finish="tool-calls"

# 回退：Prompt 嵌入 Schema
# ai_service._build_structured_system() → retry 3 次
```

## 不支持原生结构化的模型（勿用）

| Model | 原因 |
|-------|------|
| `big-pickle` / `deepseek-v4-flash-free` | Thinking mode 不支持 tool_choice |
| `mimo-v2-omni-free` 等 | HTTP 500 |

## 免费模型限额

`*-free` 耗尽表现：请求挂起不报错，直到客户端超时。排查用 `curl -m 30` 限时测试。

## 实现位置

| 文件 | 职责 |
|------|------|
| `backend/app/services/ai_service.py` | `call_llm_structured()` 统一入口 |
| `backend/app/services/llm/opencode_provider.py` | fallback + 响应解析 |
| `backend/app/schemas.py` | `TemplateParseResult` / `VariableDedupResult` / `DataValidateResult` |

## 详细参考

验证 curl 命令与完整模型列表见 [reference.md](reference.md)。
