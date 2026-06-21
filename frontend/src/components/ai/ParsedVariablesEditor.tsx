import { Plus, Trash2, Wand2 } from "lucide-react"

import { AiBadge, TrustLevelBadge } from "@/components/ai/AiBadge"
import { AiDegradedBanner } from "@/components/ai/AiDegradedBanner"
import { ConfidenceMeter, EvidenceSection, RiskNote } from "@/components/ai/AiReasoning"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { GoldPanel } from "@/components/layout/GoldPanel"
import type { ParsedVariable } from "@/types/template"
import { cn } from "@/lib/utils"

interface ParsedVariablesEditorProps {
  variables: ParsedVariable[]
  aiUsed: boolean
  parseDurationMs?: number
  degradedMessage?: string | null
  onChange: (variables: ParsedVariable[]) => void
}

function emptyVariable(): ParsedVariable {
  return {
    key: "",
    label: "",
    category: "other",
    data_type: "text",
    required: false,
    is_multiple: false,
  }
}

export function ParsedVariablesEditor({
  variables,
  aiUsed,
  parseDurationMs,
  degradedMessage,
  onChange,
}: ParsedVariablesEditorProps) {
  const updateVariable = (index: number, patch: Partial<ParsedVariable>) => {
    onChange(
      variables.map((item, i) => {
        if (i !== index) return item
        const next = { ...item, ...patch }
        if (
          ("key" in patch || "label" in patch) &&
          item.trust_level === "low"
        ) {
          next.trust_level = "medium"
          next.warnings = []
          next.suggested_key = null
        }
        return next
      }),
    )
  }

  const removeVariable = (index: number) => {
    onChange(variables.filter((_, i) => i !== index))
  }

  const adoptSuggestedKey = (index: number) => {
    const variable = variables[index]
    if (!variable.suggested_key) return
    updateVariable(index, {
      key: variable.suggested_key,
      trust_level: "high",
      warnings: [],
      suggested_key: null,
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <AiBadge />
        <span className="text-xs tracking-wider text-primary/70 uppercase">
          {aiUsed
            ? `解析到 ${variables.length} 个变量${parseDurationMs ? ` · ${parseDurationMs}ms` : ""}`
            : "手工定义变量"}
        </span>
      </div>

      {!aiUsed ? <AiDegradedBanner message={degradedMessage} /> : null}

      {variables.length === 0 ? (
        <GoldPanel dashed className="p-8 text-center text-sm text-muted-foreground">
          暂无变量，请手动添加或重新上传模板
        </GoldPanel>
      ) : (
        <ul className="space-y-3">
          {variables.map((variable, index) => (
            <GoldPanel
              key={`${variable.key}-${index}`}
              className={cn(
                "space-y-3 p-4",
                variable.trust_level === "low" && "border-destructive/25",
                variable.trust_level === "medium" && "border-primary/30",
              )}
            >
              {/* 行1: 可信度 + LLM 自信度 */}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <TrustLevelBadge level={variable.trust_level} />
                  {variable.is_registered ? (
                    <span className="text-xs text-muted-foreground">已注册</span>
                  ) : null}
                </div>
                <ConfidenceMeter confidence={variable.confidence} />
              </div>

              {/* 行2: 编辑区 */}
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs text-muted-foreground">中文名称</label>
                  <Input
                    value={variable.label}
                    onChange={(event) => updateVariable(index, { label: event.target.value })}
                    className="border-primary/25"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-muted-foreground">变量 key</label>
                  <Input
                    value={variable.key}
                    onChange={(event) => updateVariable(index, { key: event.target.value })}
                    className="border-primary/25 font-mono text-sm"
                  />
                </div>
              </div>

              {/* 行3: 元数据 */}
              <p className="text-xs text-muted-foreground">
                {variable.category} · {variable.data_type}
                {variable.is_multiple ? " · 多值" : ""}
                {variable.required ? " · 必填" : ""}
              </p>

              {/* 行4: 提取依据（可折叠） */}
              <EvidenceSection evidence={variable.evidence_list} />

              {/* 行5: 风险提示 */}
              <RiskNote note={variable.risk_note} />

              {/* 行6: AI 建议 key */}
              {variable.suggested_key ? (
                <div className="flex flex-wrap items-center gap-2 rounded border border-primary/20 bg-primary/5 p-2 text-sm">
                  <span className="text-muted-foreground">
                    建议使用标准 key：
                    <code className="ml-1 text-primary">{variable.suggested_key}</code>
                  </span>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-7 border-primary/25"
                    onClick={() => adoptSuggestedKey(index)}
                  >
                    <Wand2 className="size-3.5" />
                    采纳建议
                  </Button>
                </div>
              ) : null}

              {/* 行7: 系统警告 */}
              {variable.warnings?.length ? (
                <ul className="space-y-1 text-xs text-muted-foreground">
                  {variable.warnings.map((warning, warningIndex) => (
                    <li key={warningIndex}>· {warning}</li>
                  ))}
                </ul>
              ) : null}

              {/* 行8: 操作区 */}
              <div className="flex justify-end">
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="text-destructive hover:text-destructive"
                  onClick={() => removeVariable(index)}
                >
                  <Trash2 className="size-3.5" />
                  删除
                </Button>
              </div>
            </GoldPanel>
          ))}
        </ul>
      )}

      <Button
        type="button"
        variant="outline"
        size="sm"
        className="border-primary/25"
        onClick={() => onChange([...variables, emptyVariable()])}
      >
        <Plus className="size-4" />
        添加变量
      </Button>
    </div>
  )
}
