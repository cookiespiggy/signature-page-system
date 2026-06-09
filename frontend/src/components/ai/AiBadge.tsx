import { Badge } from "@/components/ui/badge"
import type { TrustLevel } from "@/types/ai"
import { cn } from "@/lib/utils"

const TRUST_LABELS: Record<TrustLevel, string> = {
  high: "高可信",
  medium: "待确认",
  low: "需审核",
}

const TRUST_STYLES: Record<TrustLevel, string> = {
  high: "border-primary/35 bg-primary/15 text-primary",
  medium: "border-primary/25 bg-primary/5 text-primary/90",
  low: "border-destructive/35 bg-destructive/10 text-destructive",
}

export function AiBadge({ className }: { className?: string }) {
  return (
    <Badge className={cn("border-primary/40 bg-primary/10 text-primary", className)}>AI</Badge>
  )
}

export function TrustLevelBadge({
  level,
  className,
}: {
  level: TrustLevel | string | null | undefined
  className?: string
}) {
  if (!level || !(level in TRUST_LABELS)) return null
  const trust = level as TrustLevel
  return (
    <Badge variant="outline" className={cn(TRUST_STYLES[trust], className)}>
      {TRUST_LABELS[trust]}
    </Badge>
  )
}
