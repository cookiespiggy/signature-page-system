import mammoth from "mammoth"
import { Loader2 } from "lucide-react"
import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { getErrorMessage, generationApi } from "@/services/api"

interface DocxPreviewDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  fileId: number | null
  filename: string
}

export function DocxPreviewDialog({
  open,
  onOpenChange,
  fileId,
  filename,
}: DocxPreviewDialogProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [html, setHtml] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !fileId) {
      setHtml(null)
      setError(null)
      setLoading(false)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)
    setHtml(null)

    void (async () => {
      try {
        const blob = await generationApi.fetchFileBlob(fileId)
        if (cancelled) return

        const arrayBuffer = await blob.arrayBuffer()
        const result = await mammoth.convertToHtml({ arrayBuffer })
        if (cancelled) return

        if (!result.value.trim()) {
          setError("文档内容为空，请尝试下载后本地打开")
          return
        }

        setHtml(result.value)
      } catch (err) {
        if (!cancelled) {
          setError(getErrorMessage(err))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [open, fileId])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[90vh] w-[calc(100%-2rem)] max-w-4xl flex-col gap-3 sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle className="truncate pr-8">预览 — {filename}</DialogTitle>
          <DialogDescription>
            Word 文档在线预览，仅供审阅，下载请使用列表中的下载按钮。
          </DialogDescription>
        </DialogHeader>

        <div className="docx-preview-host relative min-h-[40vh] flex-1">
          {loading ? (
            <div className="flex min-h-[40vh] items-center justify-center">
              <Loader2 className="size-8 animate-spin text-primary" />
            </div>
          ) : error ? (
            <p className="p-6 text-center text-sm text-destructive">{error}</p>
          ) : html ? (
            <div
              className="docx-mammoth-preview"
              dangerouslySetInnerHTML={{ __html: html }}
            />
          ) : null}
        </div>

        <DialogFooter>
          <Button variant="outline" className="border-primary/25" onClick={() => onOpenChange(false)}>
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
