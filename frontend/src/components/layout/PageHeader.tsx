import type { ReactNode } from "react"

interface PageHeaderProps {
  title: string
  description?: string
  /** 页眉上方英文小标签，如 Project Management */
  englishLabel?: string
  action?: ReactNode
}

/** 页面标题区标准结构，保持黑金律所风一致 */
export function PageHeader({ title, description, englishLabel, action }: PageHeaderProps) {
  return (
    <div className="flex items-end justify-between gap-4 border-b border-primary/15 pb-6">
      <div>
        {englishLabel ? (
          <p className="mb-2 text-[11px] tracking-[0.25em] text-primary/70 uppercase">
            {englishLabel}
          </p>
        ) : null}
        <h1 className="text-3xl font-semibold tracking-wide text-foreground">{title}</h1>
        {description ? (
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      {action}
    </div>
  )
}
