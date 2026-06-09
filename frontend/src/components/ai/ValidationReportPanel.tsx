import { AlertCircle, Info } from "lucide-react"

import { AiBadge } from "@/components/ai/AiBadge"
import { AiDegradedBanner } from "@/components/ai/AiDegradedBanner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { GoldPanel } from "@/components/layout/GoldPanel"
import type { AiValidateResponse, ValidationIssue } from "@/types/ai"
import { cn } from "@/lib/utils"

interface ValidationReportPanelProps {
  result: AiValidateResponse
  onDismiss: () => void
  onIssueClick?: (variableKey: string) => void
}

function SourceBadge({ issue }: { issue: ValidationIssue }) {
  if (issue.cross_validated) {
    return (
      <Badge variant="outline" className="border-primary/35 text-primary">
        交叉验证
      </Badge>
    )
  }
  if (issue.source === "ai_only") {
    return <AiBadge />
  }
  if (issue.source === "regex") {
    return (
      <Badge variant="outline" className="border-muted-foreground/30 text-muted-foreground">
        正则
      </Badge>
    )
  }
  return null
}

function IssueCard({
  issue,
  onIssueClick,
}: {
  issue: ValidationIssue
  onIssueClick?: (variableKey: string) => void
}) {
  const isError = issue.level === "error"

  return (
    <GoldPanel
      className={cn(
        "space-y-2 p-4",
        isError ? "border-destructive/30" : "border-primary/20",
        onIssueClick && "cursor-pointer transition-colors hover:bg-primary/5",
      )}
    >
      <button
        type="button"
        className="w-full space-y-2 text-left"
        onClick={() => onIssueClick?.(issue.variable_key)}
      >
      <div className="flex flex-wrap items-center gap-2">
        {isError ? (
          <AlertCircle className="size-4 text-destructive" />
        ) : (
          <Info className="size-4 text-primary" />
        )}
        <Badge
          variant="outline"
          className={
            isError
              ? "border-destructive/35 bg-destructive/10 text-destructive"
              : "border-primary/35 bg-primary/10 text-primary"
          }
        >
          {isError ? "错误" : "警告"}
        </Badge>
        <SourceBadge issue={issue} />
        <code className="text-xs text-muted-foreground">{issue.variable_key}</code>
      </div>
      <p className="text-sm">{issue.message}</p>
      {issue.suggestion ? (
        <p className="text-xs text-muted-foreground">建议：{issue.suggestion}</p>
      ) : null}
      </button>
    </GoldPanel>
  )
}

export function ValidationReportPanel({
  result,
  onDismiss,
  onIssueClick,
}: ValidationReportPanelProps) {
  const errorCount = result.issues.filter((item) => item.level === "error").length
  const warningCount = result.issues.filter((item) => item.level === "warning").length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <AiBadge />
          <span className="font-heading text-base">校验报告</span>
        </div>
        <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={onDismiss}>
          关闭
        </Button>
      </div>

      {!result.ai_used ? <AiDegradedBanner message={result.message} /> : null}

      <p className="text-sm text-muted-foreground">
        共 {result.issues.length} 项
        {errorCount > 0 ? (
          <>
            ，<span className="text-destructive">{errorCount} 个错误</span>
          </>
        ) : null}
        {warningCount > 0 ? (
          <>
            ，<span className="text-primary">{warningCount} 个警告</span>
          </>
        ) : null}
      </p>

      {result.issues.length === 0 ? (
        <GoldPanel dashed className="p-8 text-center text-sm text-muted-foreground">
          未发现格式或一致性问题
        </GoldPanel>
      ) : (
        <div className="space-y-3">
          {result.issues.map((issue, index) => (
            <IssueCard
              key={`${issue.variable_key}-${index}`}
              issue={issue}
              onIssueClick={onIssueClick}
            />
          ))}
        </div>
      )}
    </div>
  )
}
