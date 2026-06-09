import { Loader2, Minus, Plus, Upload } from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { VariableFieldInput } from "@/components/detail/VariableFieldInput"
import { GoldPanel } from "@/components/layout/GoldPanel"
import {
  fieldsToSaveItems,
  getCategoryLabel,
  groupFieldsByCategory,
  nextMultipleRowKey,
  type VariableField,
} from "@/lib/variable-utils"
import { validateVariableValue } from "@/lib/validation"
import { getErrorMessage, variablesApi } from "@/services/api"
import type { BatchOperationResponse } from "@/types/variable"

interface VariableStepProps {
  projectId: number
  fields: VariableField[]
  loading: boolean
  dirty: boolean
  onFieldsChange: (fields: VariableField[]) => void
  onDirtyChange: (dirty: boolean) => void
  onReload: () => Promise<void>
}

function VariableSkeleton() {
  return (
    <GoldPanel className="space-y-4 p-6">
      {Array.from({ length: 4 }).map((_, index) => (
        <Skeleton key={index} className="h-10 w-full bg-primary/5" />
      ))}
    </GoldPanel>
  )
}

export function VariableStep({
  projectId,
  fields,
  loading,
  dirty,
  onFieldsChange,
  onDirtyChange,
  onReload,
}: VariableStepProps) {
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [importOpen, setImportOpen] = useState(false)
  const [importPreview, setImportPreview] = useState<BatchOperationResponse | null>(null)
  const [importing, setImporting] = useState(false)
  const [exporting, setExporting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const grouped = useMemo(() => groupFieldsByCategory(fields), [fields])

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (dirty) {
        event.preventDefault()
        event.returnValue = ""
      }
    }
    window.addEventListener("beforeunload", handler)
    return () => window.removeEventListener("beforeunload", handler)
  }, [dirty])

  const updateRowValue = useCallback(
    (baseKey: string, rowKey: string, value: string) => {
      const next = fields.map((field) => {
        if (field.baseKey !== baseKey) return field
        return {
          ...field,
          rows: field.rows.map((row) => (row.key === rowKey ? { ...row, value } : row)),
        }
      })
      onFieldsChange(next)
      onDirtyChange(true)

      const error = validateVariableValue(rowKey, value)
      setFieldErrors((prev) => {
        const updated = { ...prev }
        if (error) updated[rowKey] = error
        else delete updated[rowKey]
        return updated
      })
    },
    [fields, onFieldsChange, onDirtyChange],
  )

  const addMultipleRow = (baseKey: string) => {
    const next = fields.map((field) => {
      if (field.baseKey !== baseKey || !field.isMultiple) return field
      const newKey = nextMultipleRowKey(field)
      return {
        ...field,
        rows: [...field.rows, { key: newKey, value: "", updated_at: "" }],
      }
    })
    onFieldsChange(next)
    onDirtyChange(true)
  }

  const removeMultipleRow = (baseKey: string, rowKey: string) => {
    const field = fields.find((item) => item.baseKey === baseKey)
    if (!field || field.rows.length <= 1) return

    const next = fields.map((item) => {
      if (item.baseKey !== baseKey) return item
      return { ...item, rows: item.rows.filter((row) => row.key !== rowKey) }
    })
    onFieldsChange(next)
    onDirtyChange(true)
    setFieldErrors((prev) => {
      const updated = { ...prev }
      delete updated[rowKey]
      return updated
    })
  }

  const handleExportTemplate = async () => {
    setExporting(true)
    try {
      await variablesApi.exportTemplate(projectId)
      toast.success("模板已下载")
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setExporting(false)
    }
  }

  const handleExportData = async () => {
    setExporting(true)
    try {
      await variablesApi.export(projectId)
      toast.success("变量数据已导出")
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setExporting(false)
    }
  }

  const handleImportFile = async (file: File) => {
    try {
      const preview = await variablesApi.importPreview(projectId, file)
      setImportPreview(preview)
      setImportOpen(true)
    } catch (error) {
      toast.error(getErrorMessage(error))
    }
  }

  const handleConfirmImport = async () => {
    if (!importPreview) return
    setImporting(true)
    try {
      const result = await variablesApi.import(
        projectId,
        importPreview.success as Array<Record<string, unknown>>,
      )
      setImportOpen(false)
      setImportPreview(null)
      await onReload()
      onDirtyChange(false)
      toast.success(
        `导入完成：成功 ${result.summary.succeeded} 行，失败 ${result.summary.failed} 行`,
      )
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setImporting(false)
    }
  }

  const downloadErrorReport = () => {
    if (!importPreview?.errors.length) return
    const lines = importPreview.errors.map(
      (item) => `行 ${item.row ?? "-"} | ${item.key ?? "-"} | ${item.message}`,
    )
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `import_errors_project_${projectId}.txt`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return <VariableSkeleton />
  }

  if (fields.length === 0) {
    return (
      <GoldPanel dashed className="p-12 text-center">
        <p className="text-muted-foreground">请先选择至少一个模板以生成变量表单</p>
      </GoldPanel>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          className="border-primary/25"
          disabled={exporting}
          onClick={() => void handleExportTemplate()}
        >
          下载 Excel 模板
        </Button>
        <Button
          variant="outline"
          className="border-primary/25"
          disabled={exporting}
          onClick={() => void handleExportData()}
        >
          导出已填数据
        </Button>
        <Button
          variant="outline"
          className="border-primary/25"
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload className="size-4" />
          Excel 导入
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) void handleImportFile(file)
            event.target.value = ""
          }}
        />
      </div>

      {Array.from(grouped.entries()).map(([category, categoryFields]) => (
        <GoldPanel key={category} className="p-6">
          <h3 className="mb-4 font-heading text-lg">{getCategoryLabel(category)}</h3>
          <div className="space-y-5">
            {categoryFields.map((field) => (
              <div key={field.baseKey}>
                <label className="mb-2 block text-sm font-medium">
                  {field.label}
                  {field.required ? <span className="ml-1 text-destructive">*</span> : null}
                  <span className="ml-2 text-xs text-muted-foreground">{field.baseKey}</span>
                </label>

                {field.isMultiple ? (
                  <div className="space-y-2">
                    {field.rows.map((row, index) => (
                      <div key={row.key} className="flex items-start gap-2">
                        <span className="mt-2.5 w-6 shrink-0 text-xs text-muted-foreground">
                          {index + 1}
                        </span>
                        <div className="min-w-0 flex-1">
                          <VariableFieldInput
                            field={field}
                            value={row.value}
                            error={fieldErrors[row.key]}
                            placeholder={`${field.label} ${index + 1}`}
                            onValueChange={(next) => updateRowValue(field.baseKey, row.key, next)}
                          />
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          className="shrink-0 text-muted-foreground"
                          disabled={field.rows.length <= 1}
                          onClick={() => removeMultipleRow(field.baseKey, row.key)}
                        >
                          <Minus className="size-4" />
                        </Button>
                      </div>
                    ))}
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="border-primary/25"
                      onClick={() => addMultipleRow(field.baseKey)}
                    >
                      <Plus className="size-4" />
                      添加一行
                    </Button>
                  </div>
                ) : (
                  <VariableFieldInput
                    field={field}
                    value={field.rows[0]?.value ?? ""}
                    error={fieldErrors[field.rows[0]?.key]}
                    onValueChange={(next) =>
                      updateRowValue(field.baseKey, field.rows[0].key, next)
                    }
                  />
                )}
              </div>
            ))}
          </div>
        </GoldPanel>
      ))}

      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Excel 导入预览</DialogTitle>
            <DialogDescription>确认后将写入可导入的行，错误行需修正后重新上传。</DialogDescription>
          </DialogHeader>
          {importPreview ? (
            <div className="space-y-3 text-sm">
              <p>
                成功 <span className="text-primary">{importPreview.summary.succeeded}</span> 行， 失败{" "}
                <span className="text-destructive">{importPreview.summary.failed}</span> 行
              </p>
              {importPreview.errors.length > 0 ? (
                <div className="max-h-40 overflow-y-auto rounded border border-primary/15 p-3">
                  {importPreview.errors.map((item, index) => (
                    <p key={index} className="text-destructive">
                      行 {item.row ?? "-"} · {item.key ?? "-"}：{item.message}
                    </p>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
          <DialogFooter>
            {importPreview?.errors.length ? (
              <Button variant="outline" onClick={downloadErrorReport}>
                下载错误报告
              </Button>
            ) : null}
            <Button variant="outline" onClick={() => setImportOpen(false)} disabled={importing}>
              取消
            </Button>
            <Button
              onClick={() => void handleConfirmImport()}
              disabled={importing || !importPreview?.success.length}
            >
              {importing ? <Loader2 className="size-4 animate-spin" /> : null}
              确认导入
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export function validateAllFields(fields: VariableField[]): Record<string, string> {
  const errors: Record<string, string> = {}
  for (const field of fields) {
    for (const row of field.rows) {
      const error = validateVariableValue(row.key, row.value)
      if (error) errors[row.key] = error
      if (field.required && !row.value.trim()) {
        errors[row.key] = "此项为必填"
      }
    }
  }
  return errors
}

export { fieldsToSaveItems }
