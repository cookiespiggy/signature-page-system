import { ChevronDown, ChevronRight } from "lucide-react"
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
    <div className="flex items-start gap-1.5 rounded border border-amber-200/40 bg-amber-50/40 p-2 text-xs text-amber-800 dark:border-amber-800/30 dark:bg-amber-950/20 dark:text-amber-300">
      <span className="mt-px shrink-0">⚠</span>
      <span>{note}</span>
    </div>
  )
}
