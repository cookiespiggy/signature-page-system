import {
  ChevronDown,
  ChevronUp,
  Loader2,
  RefreshCw,
  Search,
  Trash2,
  Upload,
} from "lucide-react"
import { useMemo, useRef, useState } from "react"
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
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { ParsedVariablesEditor } from "@/components/ai/ParsedVariablesEditor"
import { GoldPanel } from "@/components/layout/GoldPanel"
import { getErrorMessage, templatesApi } from "@/services/api"
import type { ParsedVariable, ProjectTemplate, Template } from "@/types/template"
import { cn } from "@/lib/utils"

interface TemplateStepProps {
  projectId: number
  templates: Template[]
  projectTemplates: ProjectTemplate[]
  selectedIds: Set<number>
  loading: boolean
  onSelectionChange: (ids: Set<number>) => void
  onProjectTemplatesChange: (pts: ProjectTemplate[]) => void
  onTemplatesReload: () => Promise<void>
}

const CATEGORY_OPTIONS = ["全部", "lawyer", "shareholder", "company", "document", "other"]

const CATEGORY_LABELS: Record<string, string> = {
  lawyer: "律师",
  shareholder: "股东",
  company: "公司",
  document: "文件",
  other: "其他",
}

function TemplateCardSkeleton() {
  return (
    <div className="space-y-3 rounded-lg border border-primary/15 p-4">
      <Skeleton className="h-5 w-2/3 bg-primary/5" />
      <Skeleton className="h-4 w-full bg-primary/5" />
      <Skeleton className="h-4 w-1/2 bg-primary/5" />
    </div>
  )
}

export function TemplateStep({
  projectId,
  templates,
  projectTemplates,
  selectedIds,
  loading,
  onSelectionChange,
  onProjectTemplatesChange,
  onTemplatesReload,
}: TemplateStepProps) {
  const [search, setSearch] = useState("")
  const [category, setCategory] = useState("全部")
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadName, setUploadName] = useState("")
  const [parsedVars, setParsedVars] = useState<ParsedVariable[]>([])
  const [parseAiUsed, setParseAiUsed] = useState(true)
  const [parseMessage, setParseMessage] = useState<string | null>(null)
  const [parseDurationMs, setParseDurationMs] = useState(0)
  const [parsing, setParsing] = useState(false)
  const [creating, setCreating] = useState(false)
  const [refreshingId, setRefreshingId] = useState<number | null>(null)
  const [removingId, setRemovingId] = useState<number | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const projectTemplateMap = useMemo(() => {
    const map = new Map<number, ProjectTemplate>()
    for (const pt of projectTemplates) {
      map.set(pt.template_id, pt)
    }
    return map
  }, [projectTemplates])

  const filteredTemplates = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    return templates.filter((template) => {
      if (category !== "全部" && template.category !== category) return false
      if (!keyword) return true
      return (
        template.name.toLowerCase().includes(keyword) ||
        (template.applicable_scenarios ?? "").toLowerCase().includes(keyword)
      )
    })
  }, [templates, search, category])

  const toggleSelect = (templateId: number) => {
    const next = new Set(selectedIds)
    if (next.has(templateId)) {
      next.delete(templateId)
    } else {
      next.add(templateId)
    }
    onSelectionChange(next)
  }

  const handleFileSelect = async (file: File) => {
    setUploadFile(file)
    setUploadName(file.name.replace(/\.docx$/i, ""))
    setParsing(true)
    try {
      const result = await templatesApi.parse(file)
      setParsedVars(result.variables)
      setParseAiUsed(result.ai_used)
      setParseMessage(result.message)
      setParseDurationMs(result.parse_duration_ms)
      setUploadOpen(true)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setParsing(false)
    }
  }

  const handleCreateTemplate = async () => {
    if (!uploadFile || !uploadName.trim()) {
      toast.error("请填写模板名称")
      return
    }
    const validVars = parsedVars.filter((item) => item.key.trim() && item.label.trim())
    if (validVars.length === 0) {
      toast.error("请至少保留一个有效变量")
      return
    }
    if (validVars.some((item) => item.trust_level === "low")) {
      toast.error("存在需审核的变量，请修正 key、采纳建议或删除后再创建")
      return
    }
    setCreating(true)
    try {
      const created = await templatesApi.create({
        file: uploadFile,
        name: uploadName.trim(),
        variables_json: validVars.map((item) => ({
          key: item.key.trim(),
          label: item.label.trim(),
          category: item.category,
          data_type: item.data_type,
          required: item.required,
          is_multiple: item.is_multiple,
        })),
      })
      await onTemplatesReload()
      const next = new Set(selectedIds)
      next.add(created.id)
      onSelectionChange(next)
      setUploadOpen(false)
      setUploadFile(null)
      setParsedVars([])
      setParseMessage(null)
      toast.success("自定义模板已创建")
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setCreating(false)
    }
  }

  const handleRefresh = async (templateId: number) => {
    setRefreshingId(templateId)
    try {
      const result = await templatesApi.refreshProjectTemplate(projectId, templateId)
      const pts = await templatesApi.listProjectTemplates(projectId)
      onProjectTemplatesChange(pts)
      toast.success(`模板已刷新（新增 ${result.added}，移除 ${result.removed}，保留 ${result.kept}）`)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setRefreshingId(null)
    }
  }

  const handleRemoveFromProject = async (templateId: number) => {
    setRemovingId(templateId)
    try {
      await templatesApi.removeFromProject(projectId, templateId)
      const pts = await templatesApi.listProjectTemplates(projectId)
      onProjectTemplatesChange(pts)
      const next = new Set(selectedIds)
      next.delete(templateId)
      onSelectionChange(next)
      toast.success("已移除模板")
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setRemovingId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[200px] flex-1">
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="搜索模板名称或适用场景…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="border-primary/25 pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {CATEGORY_OPTIONS.map((option) => (
            <Button
              key={option}
              size="sm"
              variant={category === option ? "default" : "outline"}
              className={category === option ? "" : "border-primary/25"}
              onClick={() => setCategory(option)}
            >
              {option === "全部" ? option : (CATEGORY_LABELS[option] ?? option)}
            </Button>
          ))}
        </div>
        <Button
          variant="outline"
          className="border-primary/25"
          disabled={parsing}
          onClick={() => fileInputRef.current?.click()}
        >
          {parsing ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />}
          上传自定义模板
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".docx"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) void handleFileSelect(file)
            event.target.value = ""
          }}
        />
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <TemplateCardSkeleton key={index} />
          ))}
        </div>
      ) : filteredTemplates.length === 0 ? (
        <GoldPanel dashed className="p-12 text-center">
          <p className="text-muted-foreground">未找到匹配的模板</p>
        </GoldPanel>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredTemplates.map((template) => {
            const selected = selectedIds.has(template.id)
            const pt = projectTemplateMap.get(template.id)
            const expanded = expandedId === template.id

            return (
              <GoldPanel
                key={template.id}
                className={cn(
                  "flex flex-col p-4 transition-colors",
                  selected && "border-primary/35 bg-primary/5",
                )}
              >
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => toggleSelect(template.id)}
                    className="mt-1 size-4 shrink-0 accent-[var(--primary)]"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-heading text-base font-medium">{template.name}</h3>
                      <Badge
                        variant="outline"
                        className={
                          template.is_preset
                            ? "border-primary/35 text-primary"
                            : "border-muted-foreground/30 text-muted-foreground"
                        }
                      >
                        {template.is_preset ? "系统预置" : "自定义"}
                      </Badge>
                      {pt?.needs_refresh ? (
                        <Badge className="border-primary/50 bg-primary/10 text-primary">
                          模板已更新
                        </Badge>
                      ) : null}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {CATEGORY_LABELS[template.category] ?? template.category}
                      {" · "}
                      {template.variable_count} 个变量
                    </p>
                    {template.applicable_scenarios ? (
                      <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                        {template.applicable_scenarios}
                      </p>
                    ) : null}
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-8 px-2 text-muted-foreground"
                    onClick={() => setExpandedId(expanded ? null : template.id)}
                  >
                    {expanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                    详情
                  </Button>
                  {pt?.needs_refresh ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 border-primary/25"
                      disabled={refreshingId === template.id}
                      onClick={() => void handleRefresh(template.id)}
                    >
                      {refreshingId === template.id ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <RefreshCw className="size-3.5" />
                      )}
                      刷新
                    </Button>
                  ) : null}
                  {selected && pt ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8 text-destructive hover:text-destructive"
                      disabled={removingId === template.id}
                      onClick={() => void handleRemoveFromProject(template.id)}
                    >
                      {removingId === template.id ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="size-3.5" />
                      )}
                      移除
                    </Button>
                  ) : null}
                </div>

                {expanded ? (
                  <div className="mt-3 border-t border-primary/10 pt-3">
                    <p className="mb-2 text-xs tracking-wider text-primary/70 uppercase">变量列表</p>
                    <ul className="max-h-40 space-y-1 overflow-y-auto text-sm">
                      {(template.variables_json ?? []).map((variable) => (
                        <li key={variable.key} className="flex justify-between gap-2">
                          <span className="text-muted-foreground">{variable.label}</span>
                          <code className="text-xs text-primary/80">{variable.key}</code>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </GoldPanel>
            )
          })}
        </div>
      )}

      <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>创建自定义模板</DialogTitle>
            <DialogDescription>
              请确认或修正 AI 解析的变量列表，低可信变量需审核后方可创建。
            </DialogDescription>
          </DialogHeader>
          <Input
            placeholder="模板名称"
            value={uploadName}
            onChange={(event) => setUploadName(event.target.value)}
          />
          <ParsedVariablesEditor
            variables={parsedVars}
            aiUsed={parseAiUsed}
            parseDurationMs={parseDurationMs}
            degradedMessage={parseMessage}
            onChange={setParsedVars}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setUploadOpen(false)} disabled={creating}>
              取消
            </Button>
            <Button onClick={() => void handleCreateTemplate()} disabled={creating}>
              {creating ? <Loader2 className="size-4 animate-spin" /> : null}
              确认创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
