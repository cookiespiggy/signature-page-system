import { Loader2, Sparkles } from "lucide-react"

import { GoldPanel } from "@/components/layout/GoldPanel"
import { AiBadge } from "@/components/ai/AiBadge"

interface AiLoadingPanelProps {
  label: string
}

export function AiLoadingPanel({ label }: AiLoadingPanelProps) {
  return (
    <GoldPanel className="flex items-center gap-4 border-primary/30 p-6">
      <div className="relative flex size-10 items-center justify-center">
        <Sparkles className="size-5 text-primary animate-pulse" />
        <Loader2 className="absolute size-10 animate-spin text-primary/30" />
      </div>
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <AiBadge />
          <span className="text-sm font-medium">{label}</span>
        </div>
        <p className="text-xs text-muted-foreground">正在分析，请稍候…</p>
      </div>
    </GoldPanel>
  )
}
