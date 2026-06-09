import { Download, Eye, FileText, Loader2, Package } from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { DocxPreviewDialog } from "@/components/detail/DocxPreviewDialog"
import { GenerationLogPanel } from "@/components/detail/GenerationLogPanel"
import { groupFilesByCategory } from "@/lib/generation-utils"
import { GoldPanel } from "@/components/layout/GoldPanel"
import { getCategoryLabel } from "@/lib/variable-utils"
import { formatDateTime } from "@/lib/datetime"
import { getErrorMessage, generationApi } from "@/services/api"
import type { GeneratedFile, GenerationStatus } from "@/types/generation"
import type { VariableField } from "@/lib/variable-utils"

interface GenerationStepProps {
  projectId: number
  fields: VariableField[]
  projectStatus: string
}

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"])
const ACTIVE_STATUSES = new Set(["pending", "processing"])

function extractFilename(path: string): string {
  const parts = path.split("/")
  return parts[parts.length - 1] ?? path
}

export function GenerationStep({ projectId, fields, projectStatus }: GenerationStepProps) {
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [task, setTask] = useState<GenerationStatus | null>(null)
  const [files, setFiles] = useState<GeneratedFile[]>([])
  const [loadingFiles, setLoadingFiles] = useState(true)
  const [previewFile, setPreviewFile] = useState<GeneratedFile | null>(null)
  const pollDelayRef = useRef(2000)
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadFiles = useCallback(async () => {
    try {
      const result = await generationApi.listFiles(projectId)
      setFiles(result.files)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setLoadingFiles(false)
    }
  }, [projectId])

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  const pollStatus = useCallback(async () => {
    try {
      const status = await generationApi.status(projectId)
      setTask(status)
      if (status && TERMINAL_STATUSES.has(status.status)) {
        setGenerating(false)
        pollDelayRef.current = 2000
        stopPolling()
        await loadFiles()
        if (status.status === "completed") {
          toast.success("文档生成完成")
        } else if (status.status === "failed") {
          toast.error(status.error_message ?? "生成失败")
        } else if (status.status === "cancelled") {
          toast.info("生成已取消")
        }
        return
      }
      pollDelayRef.current = Math.min(pollDelayRef.current * 2, 10000)
      pollTimerRef.current = setTimeout(() => void pollStatus(), pollDelayRef.current)
    } catch (error) {
      setGenerating(false)
      stopPolling()
      toast.error(getErrorMessage(error))
    }
  }, [projectId, loadFiles, stopPolling])

  useEffect(() => {
    void loadFiles()
    void generationApi.status(projectId).then((status) => {
      if (status && !TERMINAL_STATUSES.has(status.status)) {
        setTask(status)
        setGenerating(true)
        pollDelayRef.current = 2000
        void pollStatus()
      } else if (status) {
        setTask(status)
      }
    })
    return stopPolling
  }, [projectId, loadFiles, pollStatus, stopPolling])

  const handleStartGenerate = async () => {
    setConfirmOpen(false)
    setGenerating(true)
    pollDelayRef.current = 2000
    try {
      await generationApi.start(projectId)
      void pollStatus()
    } catch (error) {
      setGenerating(false)
      toast.error(getErrorMessage(error))
    }
  }

  const handleCancel = async () => {
    setCancelling(true)
    try {
      const status = await generationApi.cancel(projectId)
      setTask(status)
      setGenerating(false)
      stopPolling()
      pollDelayRef.current = 2000
      toast.info("已发送取消请求")
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setCancelling(false)
    }
  }

  const handleDownload = async (file: GeneratedFile) => {
    try {
      await generationApi.downloadFile(file.id, extractFilename(file.file_path))
    } catch (error) {
      toast.error(getErrorMessage(error))
    }
  }

  const handleDownloadAll = async () => {
    try {
      await generationApi.downloadAll(projectId)
    } catch (error) {
      toast.error(getErrorMessage(error))
    }
  }

  const progressPercent =
    task && task.total_count > 0
      ? Math.round((task.completed_count / task.total_count) * 100)
      : 0

  const isTaskActive = Boolean(task && ACTIVE_STATUSES.has(task.status))
  const groupedFiles = useMemo(() => groupFilesByCategory(files), [files])

  const groupedConfirm = fields.reduce<Map<string, VariableField[]>>((acc, field) => {
    const list = acc.get(field.category) ?? []
    list.push(field)
    acc.set(field.category, list)
    return acc
  }, new Map())

  return (
    <div className="space-y-6">
      <GoldPanel className="p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="font-heading text-lg">生成签字页</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              确认变量无误后生成 Word 文档，支持异步进度与取消。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {generating || projectStatus === "generating" ? (
              <Button
                variant="outline"
                className="border-primary/25"
                disabled={cancelling}
                onClick={() => void handleCancel()}
              >
                {cancelling ? <Loader2 className="size-4 animate-spin" /> : null}
                取消生成
              </Button>
            ) : (
              <Button
                className="border border-primary/30 bg-primary text-primary-foreground hover:bg-primary/90"
                onClick={() => setConfirmOpen(true)}
              >
                生成签字页
              </Button>
            )}
            {files.length > 0 ? (
              <Button
                variant="outline"
                className="border-primary/25"
                onClick={() => void handleDownloadAll()}
              >
                <Package className="size-4" />
                打包下载 ZIP
              </Button>
            ) : null}
          </div>
        </div>

        {task && (generating || isTaskActive || task.logs.length > 0) ? (
          <div className="mt-6 space-y-2">
            {(generating || isTaskActive) && task.total_count > 0 ? (
              <>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">
                    进度 {task.completed_count} / {task.total_count}
                  </span>
                  <Badge className="border-primary/50 bg-primary/10 text-primary">
                    <span className="mr-1 inline-block size-1.5 animate-pulse rounded-full bg-primary" />
                    生成中
                  </Badge>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full bg-primary transition-all duration-500"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              </>
            ) : null}
            <GenerationLogPanel
              templateProgress={task.template_progress}
              logs={task.logs}
              active={generating || isTaskActive}
            />
          </div>
        ) : null}

        {task?.status === "failed" && task.error_message ? (
          <p className="mt-4 text-sm text-destructive">{task.error_message}</p>
        ) : null}
      </GoldPanel>

      <GoldPanel className="overflow-hidden">
        <div className="border-b border-primary/10 px-4 py-3">
          <h3 className="font-heading text-base">已生成文件</h3>
          <p className="mt-1 text-xs text-muted-foreground">按子集小组（模板分类）浏览与下载</p>
        </div>
        {loadingFiles ? (
          <p className="p-6 text-sm text-muted-foreground">加载中…</p>
        ) : files.length === 0 ? (
          <p className="p-6 text-sm text-muted-foreground">暂无生成文件</p>
        ) : (
          <div className="divide-y divide-primary/10">
            {groupedFiles.map((group) => (
              <div key={group.category}>
                <div className="flex items-center justify-between border-b border-primary/10 bg-primary/5 px-4 py-3">
                  <div>
                    <p className="font-heading text-sm">{group.label}</p>
                    <p className="text-xs text-muted-foreground">{group.files.length} 个文件</p>
                  </div>
                  <Badge variant="outline" className="border-primary/25 text-primary">
                    子集小组
                  </Badge>
                </div>
                <Table>
                  <TableHeader>
                    <TableRow className="border-primary/15 hover:bg-transparent">
                      <TableHead className="text-xs tracking-wider text-primary/80 uppercase">
                        模板
                      </TableHead>
                      <TableHead className="text-xs tracking-wider text-primary/80 uppercase">
                        文件名
                      </TableHead>
                      <TableHead className="text-xs tracking-wider text-primary/80 uppercase">
                        生成时间
                      </TableHead>
                      <TableHead className="text-right text-xs tracking-wider text-primary/80 uppercase">
                        操作
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {group.files.map((file) => (
                      <TableRow
                        key={file.id}
                        className="border-primary/10 transition-colors hover:bg-primary/5"
                      >
                        <TableCell>{file.template_name ?? "—"}</TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">
                          {extractFilename(file.file_path)}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {formatDateTime(file.created_at)}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-primary"
                              onClick={() => setPreviewFile(file)}
                            >
                              <Eye className="size-4" />
                              预览
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-primary"
                              onClick={() => void handleDownload(file)}
                            >
                              <Download className="size-4" />
                              下载
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ))}
          </div>
        )}
      </GoldPanel>

      <DocxPreviewDialog
        open={previewFile !== null}
        onOpenChange={(open) => {
          if (!open) setPreviewFile(null)
        }}
        fileId={previewFile?.id ?? null}
        filename={previewFile ? extractFilename(previewFile.file_path) : ""}
      />

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>确认生成变量</DialogTitle>
            <DialogDescription>
              请审阅以下变量值，确认无误后开始生成 Word 文档。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {Array.from(groupedConfirm.entries()).map(([category, categoryFields]) => (
              <div key={category}>
                <p className="mb-2 text-xs tracking-wider text-primary/70 uppercase">
                  {getCategoryLabel(category)}
                </p>
                <ul className="space-y-1 rounded border border-primary/15 p-3 text-sm">
                  {categoryFields.flatMap((field) =>
                    field.rows.map((row) => (
                      <li key={row.key} className="flex justify-between gap-4">
                        <span className="text-muted-foreground">
                          {field.label}
                          {field.isMultiple ? ` (${row.key.split("_").pop()})` : ""}
                        </span>
                        <span className="max-w-[50%] truncate text-right">
                          {row.value.trim() || (
                            <span className="text-destructive">（空）</span>
                          )}
                        </span>
                      </li>
                    )),
                  )}
                </ul>
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              返回修改
            </Button>
            <Button onClick={() => void handleStartGenerate()}>
              <FileText className="size-4" />
              确认生成
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
