import { AlertTriangle, RefreshCw } from "lucide-react"
import { Component, type ErrorInfo, type ReactNode } from "react"

import { Button } from "@/components/ui/button"

interface ErrorBoundaryProps {
  children: ReactNode
  fallbackTitle?: string
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = {
    hasError: false,
    error: null,
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info)
  }

  private handleReload = () => {
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 px-6 py-16 text-center">
          <div className="flex size-12 items-center justify-center rounded-sm border border-primary/30 bg-primary/10 text-primary">
            <AlertTriangle className="size-6" />
          </div>
          <div className="space-y-2">
            <h2 className="font-heading text-xl font-semibold">
              {this.props.fallbackTitle ?? "页面出错，请刷新"}
            </h2>
            <p className="max-w-md text-sm text-muted-foreground">
              {this.state.error?.message ?? "发生了意外错误，请刷新页面后重试。"}
            </p>
          </div>
          <Button onClick={this.handleReload}>
            <RefreshCw className="size-4" />
            刷新页面
          </Button>
        </div>
      )
    }

    return this.props.children
  }
}
