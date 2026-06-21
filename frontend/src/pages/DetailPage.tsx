import { ArrowLeft, ArrowRight, Loader2 } from "lucide-react"
import { useCallback, useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { GenerationStep } from "@/components/detail/GenerationStep"
import { StepNav, type DetailStep } from "@/components/detail/StepNav"
import { TemplateStep } from "@/components/detail/TemplateStep"
import {
  fieldsToSaveItems,
  validateAllFields,
  VariableStep,
} from "@/components/detail/VariableStep"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { GoldPanel } from "@/components/layout/GoldPanel"
import { PageHeader } from "@/components/layout/PageHeader"
import { buildVariableFields, type VariableField } from "@/lib/variable-utils"
import {
  getErrorMessage,
  projectsApi,
  templatesApi,
  variablesApi,
  type ApiRequestState,
} from "@/services/api"
import type { ValidationIssue } from "@/types/ai"
import type { Project } from "@/types/project"
import type { ProjectTemplate, Template } from "@/types/template"

export function DetailPage() {
  const { id } = useParams<{ id: string }>()
  const projectId = Number(id)
  const navigate = useNavigate()

  const [project, setProject] = useState<Project | null>(null)
  const [projectState, setProjectState] = useState<ApiRequestState>("idle")
  const [step, setStep] = useState<DetailStep>(1)
  const [maxReachable, setMaxReachable] = useState<DetailStep>(1)

  const [templates, setTemplates] = useState<Template[]>([])
  const [projectTemplates, setProjectTemplates] = useState<ProjectTemplate[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [templatesLoading, setTemplatesLoading] = useState(true)

  const [variableFields, setVariableFields] = useState<VariableField[]>([])
  const [variablesLoading, setVariablesLoading] = useState(false)
  const [variablesDirty, setVariablesDirty] = useState(false)

  const [stepTransitioning, setStepTransitioning] = useState(false)
  const [transitionMessage, setTransitionMessage] = useState<string | null>(null)
  const [aiValidateRunCount, setAiValidateRunCount] = useState(0)
  const [aiValidationIssues, setAiValidationIssues] = useState<ValidationIssue[]>([])
  const [showForceOverride, setShowForceOverride] = useState(false)

  const loadProject = useCallback(async () => {
    if (!projectId || Number.isNaN(projectId)) return
    setProjectState("loading")
    try {
      const data = await projectsApi.get(projectId)
      setProject(data)
      setProjectState("success")
    } catch (error) {
      setProjectState("error")
      toast.error(getErrorMessage(error))
    }
  }, [projectId])

  const loadTemplates = useCallback(async () => {
    setTemplatesLoading(true)
    try {
      const [allTemplates, pts] = await Promise.all([
        templatesApi.list(),
        templatesApi.listProjectTemplates(projectId),
      ])
      setTemplates(allTemplates)
      setProjectTemplates(pts)
      setSelectedIds(new Set(pts.map((pt) => pt.template_id)))
      if (pts.length > 0) {
        setMaxReachable((prev) => (prev < 2 ? 2 : prev))
      }
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setTemplatesLoading(false)
    }
  }, [projectId])

  const loadVariables = useCallback(async () => {
    setVariablesLoading(true)
    try {
      const result = await variablesApi.list(projectId)
      const fields = buildVariableFields(result.variables)
      setVariableFields(fields)
      setVariablesDirty(false)
      if (fields.length > 0) {
        setMaxReachable((prev) => (prev < 3 ? 3 : prev))
      }
      return fields
    } catch (error) {
      toast.error(getErrorMessage(error))
      return []
    } finally {
      setVariablesLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    if (!projectId || Number.isNaN(projectId)) {
      navigate("/")
      return
    }
    void loadProject()
    void loadTemplates()
  }, [projectId, navigate, loadProject, loadTemplates])

  const syncTemplates = async () => {
    const currentIds = new Set(projectTemplates.map((pt) => pt.template_id))
    const toRemove = [...currentIds].filter((tid) => !selectedIds.has(tid))
    const toAdd = [...selectedIds].filter((tid) => !currentIds.has(tid))

    for (const templateId of toRemove) {
      await templatesApi.removeFromProject(projectId, templateId)
    }
    if (toAdd.length > 0) {
      await templatesApi.addToProject(projectId, toAdd)
    }

    const pts = await templatesApi.listProjectTemplates(projectId)
    setProjectTemplates(pts)
    setSelectedIds(new Set(pts.map((pt) => pt.template_id)))
  }

  const saveVariables = async (): Promise<boolean> => {
    const errors = validateAllFields(variableFields)
    if (Object.keys(errors).length > 0) {
      toast.error("请修正表单中的校验错误后再继续")
      return false
    }

    try {
      const items = fieldsToSaveItems(variableFields)
      const result = await variablesApi.save(projectId, items)

      if (result.summary.failed > 0) {
        const firstError = result.errors[0]?.message ?? "部分变量保存失败"
        toast.error(firstError)
        if (result.summary.succeeded > 0) {
          await loadVariables()
        }
        return false
      }

      const updated = await loadVariables()
      if (updated.length > 0) {
        setMaxReachable(3)
      }
      return true
    } catch (error) {
      toast.error(getErrorMessage(error))
      return false
    }
  }

  const handleNext = async () => {
    if (step === 1) {
      if (selectedIds.size === 0) {
        toast.error("请至少选择一个模板")
        return
      }
      setStepTransitioning(true)
      setTransitionMessage("正在保存模板选择...")
      try {
        await syncTemplates()
        setTransitionMessage("正在加载变量...")
        await loadVariables()
        setMaxReachable(2)
        setStep(2)
      } catch (error) {
        toast.error(getErrorMessage(error))
      } finally {
        setStepTransitioning(false)
        setTransitionMessage(null)
      }
      return
    }

    if (step === 2) {
      if (aiValidateRunCount > 0) {
        const errors = aiValidationIssues.filter((i) => i.level === "error")
        if (errors.length > 0) {
          setShowForceOverride(true)
          return
        }
      } else if (aiValidateRunCount === 0 && variableFields.some((f) => f.isMerged)) {
          toast.info("建议先运行「AI 校验」检查变量值格式，再生成文档")
          setAiValidateRunCount(-1)
          return
        }

      setStepTransitioning(true)
      try {
        const saved = await saveVariables()
        if (saved) {
          setStep(3)
        }
      } finally {
        setStepTransitioning(false)
      }
    }
  }

  const handleForceOverride = async () => {
    setShowForceOverride(false)
    const errors = aiValidationIssues.filter((i) => i.level === "error")
    toast.warning(`已忽略 ${errors.length} 个 AI 校验错误，请确认变量值正确`)
    setStepTransitioning(true)
    try {
      const saved = await saveVariables()
      if (saved) {
        setStep(3)
      }
    } finally {
      setStepTransitioning(false)
    }
  }

  const handleBack = async () => {
    if (step === 2 && variablesDirty) {
      const saved = await saveVariables()
      if (!saved) return
    }
    if (step === 3) {
      setStep(2)
      void loadVariables()
      return
    }
    if (step === 2) {
      setStep(1)
      void loadTemplates()
    }
  }

  const handleStepClick = async (target: DetailStep) => {
    if (target === step) return
    if (target < step) {
      if (step === 2 && variablesDirty) {
        const saved = await saveVariables()
        if (!saved) return
      }
      setStep(target)
      if (target === 1) void loadTemplates()
      if (target === 2) void loadVariables()
      return
    }

    if (step === 1 && target >= 2) {
      await handleNext()
      if (target === 3 && maxReachable >= 3) {
        const saved = await saveVariables()
        if (saved) setStep(3)
      }
    } else if (step === 2 && target === 3) {
      await handleNext()
    }
  }

  if (!projectId || Number.isNaN(projectId)) {
    return null
  }

  if (projectState === "loading") {
    return (
      <div className="space-y-8">
        <Skeleton className="h-10 w-64 bg-primary/5" />
        <Skeleton className="h-32 w-full bg-primary/5" />
      </div>
    )
  }

  if (projectState === "error" || !project) {
    return (
      <GoldPanel dashed className="p-12 text-center">
        <p className="text-muted-foreground">项目加载失败</p>
        <Link to="/" className="mt-4 inline-block">
          <Button variant="outline" className="border-primary/25">
            返回列表
          </Button>
        </Link>
      </GoldPanel>
    )
  }

  const stepDescriptions: Record<DetailStep, string> = {
    1: "从模板库中选择一个或多个签字页模板",
    2: "填写合并去重后的变量，支持 Excel 导入导出",
    3: "确认变量并生成 Word 文档，支持单文件与 ZIP 下载",
  }

  return (
    <div className="space-y-8">
      <PageHeader
        englishLabel="Project Workflow"
        title={project.name}
        description={stepDescriptions[step]}
        action={
          <Link to="/">
            <Button variant="outline" className="border-primary/25">
              <ArrowLeft className="size-4" />
              返回列表
            </Button>
          </Link>
        }
      />

      <StepNav
        current={step}
        maxReachable={maxReachable}
        onStepClick={(target) => void handleStepClick(target)}
      />

      {step === 1 ? (
        <TemplateStep
          projectId={projectId}
          templates={templates}
          projectTemplates={projectTemplates}
          selectedIds={selectedIds}
          loading={templatesLoading}
          onSelectionChange={setSelectedIds}
          onProjectTemplatesChange={setProjectTemplates}
          onTemplatesReload={loadTemplates}
        />
      ) : null}

      {step === 2 && stepTransitioning && transitionMessage ? (
        <GoldPanel className="flex items-center justify-center gap-3 p-12">
          <Loader2 className="size-5 animate-spin text-primary" />
          <span className="text-muted-foreground">{transitionMessage}</span>
        </GoldPanel>
      ) : null}

      {step === 2 && !stepTransitioning ? (
        <VariableStep
          projectId={projectId}
          fields={variableFields}
          loading={variablesLoading}
          dirty={variablesDirty}
          aiValidateRunCount={aiValidateRunCount}
          templates={templates}
          projectTemplates={projectTemplates}
          onFieldsChange={setVariableFields}
          onDirtyChange={setVariablesDirty}
          onValidationResult={(issues) => {
            setAiValidationIssues(issues)
            setAiValidateRunCount((c) => c + 1)
          }}
          onReload={async () => {
            await loadVariables()
          }}
        />
      ) : null}

      {step === 3 ? (
        <GenerationStep
          projectId={projectId}
          fields={variableFields}
          projectStatus={project.status}
        />
      ) : null}

      {step < 3 ? (
        <div className="flex items-center justify-between border-t border-primary/15 pt-6">
          <Button
            variant="outline"
            className="border-primary/25"
            disabled={step === 1 || stepTransitioning}
            onClick={() => void handleBack()}
          >
            <ArrowLeft className="size-4" />
            上一步
          </Button>
          <Button
            className="border border-primary/30 bg-primary text-primary-foreground hover:bg-primary/90"
            disabled={stepTransitioning}
            onClick={() => void handleNext()}
          >
            {stepTransitioning ? <Loader2 className="size-4 animate-spin" /> : null}
            下一步
            <ArrowRight className="size-4" />
          </Button>
        </div>
      ) : (
        <div className="flex justify-start border-t border-primary/15 pt-6">
          <Button
            variant="outline"
            className="border-primary/25"
            onClick={() => void handleBack()}
          >
            <ArrowLeft className="size-4" />
            返回修改变量
          </Button>
        </div>
      )}

      <AlertDialog open={showForceOverride} onOpenChange={setShowForceOverride}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>AI 校验存在错误</AlertDialogTitle>
            <AlertDialogDescription>
              AI 校验发现 {aiValidationIssues.filter((i) => i.level === "error").length} 个错误，
              建议返回修正后再生成文档。忽略错误可能导致生成的 Word 文件内容有误。
            </AlertDialogDescription>
          </AlertDialogHeader>
          {aiValidationIssues.filter((i) => i.level === "error").length > 0 ? (
            <div className="max-h-32 space-y-1 overflow-y-auto rounded border border-destructive/20 bg-destructive/5 p-3 text-sm">
              {aiValidationIssues
                .filter((i) => i.level === "error")
                .map((issue, idx) => (
                  <p key={idx} className="text-destructive">
                    {issue.variable_key}：{issue.message}
                  </p>
                ))}
            </div>
          ) : null}
          <AlertDialogFooter>
            <AlertDialogCancel>返回修改</AlertDialogCancel>
            <AlertDialogAction onClick={() => void handleForceOverride()}>
              忽略错误，继续生成
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
