import { Check, Loader2, X } from "lucide-react"
import { useMemo, useState } from "react"

import { AiBadge, TrustLevelBadge } from "@/components/ai/AiBadge"
import { AiDegradedBanner } from "@/components/ai/AiDegradedBanner"
import { Button } from "@/components/ui/button"
import { GoldPanel } from "@/components/layout/GoldPanel"
import type { AiDedupResponse, DedupSuggestion } from "@/types/ai"
import { cn } from "@/lib/utils"

interface DedupSuggestionsPanelProps {
  result: AiDedupResponse
  applyingKey: string | null
  onAccept: (suggestion: DedupSuggestion) => Promise<void>
  onDismiss: () => void
}

function suggestionId(suggestion: DedupSuggestion, prefix: string) {
  return `${prefix}:${suggestion.keep_key}:${suggestion.merge_keys.join(",")}`
}

function SuggestionCard({
  suggestion,
  sourceLabel,
  applying,
  rejected,
  onAccept,
  onReject,
}: {
  suggestion: DedupSuggestion
  sourceLabel: string
  applying: boolean
  rejected: boolean
  onAccept: () => void
  onReject: () => void
}) {
  if (rejected) return null

  return (
    <GoldPanel
      className={cn(
        "space-y-3 p-4",
        suggestion.trust_level === "low" && "border-destructive/25",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs tracking-wider text-primary/70 uppercase">{sourceLabel}</span>
        <TrustLevelBadge level={suggestion.trust_level} />
        {suggestion.source === "alias" ? (
          <span className="text-xs text-muted-foreground">规则匹配</span>
        ) : null}
        <span className="text-xs text-muted-foreground">
          置信度 {(suggestion.confidence * 100).toFixed(0)}%
        </span>
      </div>

      <p className="text-sm">
        保留 <code className="text-primary">{suggestion.keep_key}</code>
        ，合并{" "}
        {suggestion.merge_keys.map((key) => (
          <code key={key} className="mr-1 text-muted-foreground">
            {key}
          </code>
        ))}
      </p>
      <p className="text-sm text-muted-foreground">{suggestion.reason}</p>

      {suggestion.warnings?.length ? (
        <ul className="space-y-1 text-xs text-muted-foreground">
          {suggestion.warnings.map((warning, index) => (
            <li key={index}>· {warning}</li>
          ))}
        </ul>
      ) : null}

      <div className="flex gap-2">
        <Button
          size="sm"
          className="border border-primary/30"
          disabled={applying}
          onClick={onAccept}
        >
          {applying ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
          采纳
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="border-primary/25"
          disabled={applying}
          onClick={onReject}
        >
          <X className="size-3.5" />
          拒绝
        </Button>
      </div>
    </GoldPanel>
  )
}

export function DedupSuggestionsPanel({
  result,
  applyingKey,
  onAccept,
  onDismiss,
}: DedupSuggestionsPanelProps) {
  const [rejectedIds, setRejectedIds] = useState<Set<string>>(new Set())

  const allSuggestions = useMemo(
    () => [
      ...result.alias_suggestions.map((s) => ({ suggestion: s, prefix: "alias" as const })),
      ...result.ai_suggestions.map((s) => ({ suggestion: s, prefix: "ai" as const })),
    ],
    [result],
  )

  const visibleCount = allSuggestions.filter(
    ({ suggestion, prefix }) => !rejectedIds.has(suggestionId(suggestion, prefix)),
  ).length

  if (!result.ai_used && result.alias_suggestions.length === 0) {
    return (
      <div className="space-y-3">
        <AiDegradedBanner message={result.message} />
        <Button variant="outline" size="sm" className="border-primary/25" onClick={onDismiss}>
          关闭
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <AiBadge />
          <span className="font-heading text-base">智能去重建议</span>
        </div>
        <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={onDismiss}>
          关闭
        </Button>
      </div>

      {!result.ai_used ? <AiDegradedBanner message={result.message} /> : null}

      {visibleCount === 0 ? (
        <GoldPanel dashed className="p-8 text-center text-sm text-muted-foreground">
          暂无待处理的去重建议
        </GoldPanel>
      ) : (
        <div className="space-y-3">
          {allSuggestions.map(({ suggestion, prefix }) => {
            const id = suggestionId(suggestion, prefix)
            return (
              <SuggestionCard
                key={id}
                suggestion={suggestion}
                sourceLabel={prefix === "alias" ? "规则建议" : "AI 建议"}
                applying={applyingKey === id}
                rejected={rejectedIds.has(id)}
                onAccept={() => void onAccept(suggestion)}
                onReject={() => setRejectedIds((prev) => new Set(prev).add(id))}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
