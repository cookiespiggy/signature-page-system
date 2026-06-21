import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react"
import { useState } from "react"

import { cn } from "@/lib/utils"

export function ConfidenceMeter({ confidence }: { confidence: number | null | undefined }) {
  if (confidence == null) return null
  const pct = Math.round(confidence * 100)
  const color =
    pct >= 80
      ? "bg-emerald-500"
      : pct >= 50
        ? "bg-amber-500"
        : "bg-destructive"
  return (
    <div className="flex items-center gap-1.5" title={`LLM 置信度: ${pct}%`}>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full transition-all duration-500", color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[11px] tabular-nums text-muted-foreground">{pct}%</span>
    </div>
  )
}

export function EvidenceSection({ evidence }: { evidence: string[] | null | undefined }) {
  const [open, setOpen] = useState(false)
  if (!evidence?.length) return null
  return (
    <div className="rounded border border-primary/10 bg-primary/[0.02] p-2">
      <button
        type="button"
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        onClick={() => setOpen(!open)}
      >
        {open ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        <span>依据（{evidence.length} 条）</span>
      </button>
      {open && (
        <ul className="mt-1.5 space-y-0.5 pl-4">
          {evidence.map((item, i) => (
            <li key={i} className="font-mono text-[11px] leading-relaxed text-muted-foreground">
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function RiskNote({ note }: { note: string | null | undefined }) {
  if (!note) return null
  return (
    <div className="flex items-start gap-2 rounded border-l-2 border-destructive/35 bg-destructive/[0.04] p-2.5">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
      <div className="space-y-0.5">
        <p className="text-xs font-medium text-destructive">风险</p>
        <p className="text-xs leading-relaxed text-foreground">{note}</p>
      </div>
    </div>
  )
}
