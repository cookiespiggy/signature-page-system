import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

interface GoldPanelProps {
  children: ReactNode
  className?: string
  /** 空状态等场景使用虚线边框 */
  dashed?: boolean
}

/** 黑金主题标准内容面板，新页面优先复用而非手写 border/bg */
export function GoldPanel({ children, className, dashed = false }: GoldPanelProps) {
  return (
    <div className={cn("gold-panel", dashed && "border-dashed", className)}>
      {children}
    </div>
  )
}
