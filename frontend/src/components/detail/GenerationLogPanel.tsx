import { AlertCircle, CheckCircle2, Info, Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { GoldPanel } from "@/components/layout/GoldPanel"
import { getTemplateCategoryLabel } from "@/lib/generation-utils"
import { formatDateTime } from "@/lib/datetime"
import type {
  GenerationLogEntry,
  GenerationLogLevel,
  TemplateProgressItem,
} from "@/types/generation"
import { cn } from "@/lib/utils"

interface GenerationLogPanelProps {
  templateProgress: TemplateProgressItem[]
  logs: GenerationLogEntry[]
  active?: boolean
}

const LOG_LEVEL_STYLES: Record<
  GenerationLogLevel,
  { icon: typeof Info; className: string; label: string }
> = {
  info: {
    icon: Info,
    className: "text-muted-foreground",
    label: "信息",
  },
  success: {
    icon: CheckCircle2,
    className: "text-primary",
    label: "完成",
  },
  error: {
    icon: AlertCircle,
    className: "text-destructive",
    label: "错误",
  },
  warning: {
    icon: AlertCircle,
    className: "text-primary",
    label: "警告",
  },
}

const PROGRESS_STATUS_LABELS: Record<string, string> = {
  pending: "等待中",
  processing: "生成中",
  completed: "已完成",
  failed: "失败",
  skipped: "已跳过",
}

function ProgressStatusBadge({ status }: { status: string }) {
  if (status === "processing") {
    return (
      <Badge className="border-primary/50 bg-primary/10 text-primary">
        <Loader2 className="mr-1 size-3 animate-spin" />
        {PROGRESS_STATUS_LABELS[status]}
      </Badge>
    )
  }
  if (status === "completed") {
    return (
      <Badge className="border-primary/35 bg-primary/15 text-primary">
        {PROGRESS_STATUS_LABELS[status]}
      </Badge>
    )
  }
  if (status === "failed") {
    return (
      <Badge className="border-destructive/35 bg-destructive/10 text-destructive">
        {PROGRESS_STATUS_LABELS[status]}
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="border-muted-foreground/25 text-muted-foreground">
      {PROGRESS_STATUS_LABELS[status] ?? status}
    </Badge>
  )
}

export function GenerationLogPanel({
  templateProgress,
  logs,
  active = false,
}: GenerationLogPanelProps) {
  if (templateProgress.length === 0 && logs.length === 0) {
    return null
  }

  return (
    <div className="mt-6 space-y-4">
      {templateProgress.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs tracking-wider text-primary/70 uppercase">模板进度</p>
          <div className="space-y-2">
            {templateProgress.map((item) => (
              <GoldPanel
                key={item.template_id}
                className={cn(
                  "flex flex-wrap items-center justify-between gap-3 p-3",
                  item.status === "processing" && "border-primary/35",
                )}
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{item.template_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {getTemplateCategoryLabel(item.template_category)}
                  </p>
                </div>
                <ProgressStatusBadge status={item.status} />
              </GoldPanel>
            ))}
          </div>
        </div>
      ) : null}

      {logs.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs tracking-wider text-primary/70 uppercase">
            生成日志{active ? "（实时更新）" : ""}
          </p>
          <GoldPanel className="max-h-56 overflow-y-auto p-3">
            <ul className="space-y-3">
              {logs.map((entry, index) => {
                const style = LOG_LEVEL_STYLES[entry.level]
                const Icon = style.icon
                return (
                  <li
                    key={`${entry.timestamp}-${index}`}
                    className="flex gap-3 border-b border-primary/10 pb-3 last:border-0 last:pb-0"
                  >
                    <Icon className={cn("mt-0.5 size-4 shrink-0", style.className)} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs text-muted-foreground">
                          {formatDateTime(entry.timestamp)}
                        </span>
                        <Badge
                          variant="outline"
                          className="border-muted-foreground/25 text-muted-foreground"
                        >
                          {style.label}
                        </Badge>
                      </div>
                      <p className="mt-1 text-sm">{entry.message}</p>
                    </div>
                  </li>
                )
              })}
            </ul>
          </GoldPanel>
        </div>
      ) : null}
    </div>
  )
}
