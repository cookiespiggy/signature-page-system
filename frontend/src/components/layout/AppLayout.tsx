import { Scale } from "lucide-react"
import { Link, Outlet } from "react-router-dom"

export function AppLayout() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-primary/15 bg-card/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Link
            to="/"
            className="group flex items-center gap-3 transition-opacity hover:opacity-90"
          >
            <div className="flex size-9 items-center justify-center rounded-sm border border-primary/30 bg-primary/10">
              <Scale className="size-4.5 text-primary" strokeWidth={1.5} />
            </div>
            <div className="flex flex-col">
              <span className="font-heading text-lg leading-tight tracking-wide text-foreground">
                签字页管理系统
              </span>
              <span className="text-[10px] tracking-[0.2em] text-primary/70 uppercase">
                Signature Page Suite
              </span>
            </div>
          </Link>
          <span className="hidden rounded-sm border border-primary/25 px-2.5 py-1 text-[10px] tracking-[0.15em] text-primary/80 uppercase sm:inline-block">
            JunHe MVP
          </span>
        </div>
        <div className="gold-divider" />
      </header>
      <main className="mx-auto max-w-6xl px-6 py-10">
        <Outlet />
      </main>
    </div>
  )
}
