import { AlertTriangle } from "lucide-react"

import { GoldPanel } from "@/components/layout/GoldPanel"

interface AiDegradedBannerProps {
  message?: string | null
}

export function AiDegradedBanner({ message }: AiDegradedBannerProps) {
  return (
    <GoldPanel className="flex items-start gap-3 border-primary/20 bg-primary/5 p-4">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-primary" />
      <div className="space-y-1 text-sm">
        <p className="font-medium text-foreground">AI 服务暂不可用</p>
        <p className="text-muted-foreground">
          {message ?? "请使用手工操作继续，基础功能（正则校验、规则去重）不受影响。"}
        </p>
      </div>
    </GoldPanel>
  )
}
