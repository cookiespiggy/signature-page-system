import { Check } from "lucide-react"

import { cn } from "@/lib/utils"

export type DetailStep = 1 | 2 | 3

const STEPS: Array<{ step: DetailStep; label: string; english: string }> = [
  { step: 1, label: "选择模板", english: "Templates" },
  { step: 2, label: "填写变量", english: "Variables" },
  { step: 3, label: "生成下载", english: "Generate" },
]

interface StepNavProps {
  current: DetailStep
  onStepClick?: (step: DetailStep) => void
  maxReachable?: DetailStep
}

export function StepNav({ current, onStepClick, maxReachable = 3 }: StepNavProps) {
  return (
    <nav aria-label="项目流程步骤" className="w-full">
      <ol className="flex w-full items-center">
        {STEPS.map(({ step, label, english }, index) => {
          const isActive = step === current
          const isDone = step < current
          const isReachable = step <= maxReachable
          const clickable = isReachable && onStepClick && step !== current
          const connectorDone = step <= current

          return (
            <li key={step} className="contents">
              {index > 0 ? (
                <div
                  aria-hidden
                  className="mx-3 flex min-w-8 flex-1 items-center sm:mx-4"
                >
                  <div
                    className={cn(
                      "h-px w-full transition-colors",
                      connectorDone ? "bg-primary/45" : "bg-primary/15",
                    )}
                  />
                </div>
              ) : null}

              <div className="flex shrink-0">
                <button
                  type="button"
                  disabled={!clickable}
                  onClick={() => clickable && onStepClick?.(step)}
                  className={cn(
                    "flex min-w-[9.5rem] items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors sm:min-w-[10.5rem]",
                    isActive
                      ? "border-primary/45 bg-primary/10 shadow-[0_0_20px_oklch(0.74_0.1_85_/_8%)]"
                      : isDone
                        ? "border-primary/30 bg-card hover:bg-primary/5"
                        : "border-primary/15 bg-card/50",
                    clickable && "cursor-pointer hover:border-primary/35",
                    !clickable && "cursor-default",
                    !isReachable && "opacity-40",
                  )}
                >
                  <span
                    className={cn(
                      "flex size-8 shrink-0 items-center justify-center rounded-full border text-xs font-medium",
                      isActive
                        ? "border-primary/60 bg-primary/20 text-primary"
                        : isDone
                          ? "border-primary/50 bg-primary/15 text-primary"
                          : "border-muted-foreground/30 text-muted-foreground",
                    )}
                  >
                    {isDone ? <Check className="size-4" /> : step}
                  </span>
                  <span className="min-w-0">
                    <span
                      className={cn(
                        "block text-[10px] tracking-[0.2em] uppercase",
                        isActive ? "text-primary/80" : "text-primary/55",
                      )}
                    >
                      {english}
                    </span>
                    <span
                      className={cn(
                        "block text-sm font-medium",
                        isActive ? "text-foreground" : "text-foreground/80",
                      )}
                    >
                      {label}
                    </span>
                  </span>
                </button>
              </div>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
