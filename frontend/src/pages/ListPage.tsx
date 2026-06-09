import { Loader2, Plus, Trash2, ChevronRight } from "lucide-react"
import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatDateTime } from "@/lib/datetime"
import { getErrorMessage, projectsApi, type ApiRequestState } from "@/services/api"
import { GoldPanel } from "@/components/layout/GoldPanel"
import { PageHeader } from "@/components/layout/PageHeader"
import type { Project, ProjectStatus } from "@/types/project"

const STATUS_LABELS: Record<ProjectStatus, string> = {
  draft: "草稿",
  generating: "生成中",
  completed: "已完成",
}

function StatusBadge({ status }: { status: ProjectStatus }) {
  if (status === "completed") {
    return (
      <Badge className="border-primary/35 bg-primary/15 text-primary">
        {STATUS_LABELS[status]}
      </Badge>
    )
  }
  if (status === "generating") {
    return (
      <Badge className="border-primary/50 bg-primary/10 text-primary">
        <span className="mr-1 inline-block size-1.5 animate-pulse rounded-full bg-primary" />
        {STATUS_LABELS[status]}
      </Badge>
    )
  }
  return (
    <Badge
      variant="outline"
      className="border-muted-foreground/25 text-muted-foreground"
    >
      {STATUS_LABELS[status]}
    </Badge>
  )
}

function TableSkeleton() {
  return (
    <GoldPanel className="space-y-3 p-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <Skeleton key={index} className="h-12 w-full bg-primary/5" />
      ))}
    </GoldPanel>
  )
}

async function loadProjects(
  setProjects: (data: Project[]) => void,
  setListState: (state: ApiRequestState) => void,
) {
  setListState("loading")
  try {
    const data = await projectsApi.list()
    setProjects(data)
    setListState("success")
  } catch (error) {
    setListState("error")
    toast.error(getErrorMessage(error))
  }
}

export function ListPage() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<Project[]>([])
  const [listState, setListState] = useState<ApiRequestState>("idle")
  const [createOpen, setCreateOpen] = useState(false)
  const [newProjectName, setNewProjectName] = useState("")
  const [creating, setCreating] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    void loadProjects(setProjects, setListState)
  }, [])

  const handleCreate = async () => {
    const name = newProjectName.trim()
    if (!name) {
      toast.error("请输入项目名称")
      return
    }

    setCreating(true)
    try {
      const project = await projectsApi.create(name)
      setProjects((prev) => [project, ...prev])
      setCreateOpen(false)
      setNewProjectName("")
      toast.success("项目创建成功")
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return

    setDeleting(true)
    try {
      await projectsApi.delete(deleteTarget.id)
      setProjects((prev) => prev.filter((item) => item.id !== deleteTarget.id))
      setDeleteTarget(null)
      toast.success("项目已删除")
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        englishLabel="Project Management"
        title="项目列表"
        description="管理签字页生成项目，创建后可进入详情配置模板与变量。"
        action={
          <Button
            className="border border-primary/30 bg-primary text-primary-foreground shadow-[0_0_20px_oklch(0.74_0.1_85_/_15%)] hover:bg-primary/90"
            onClick={() => setCreateOpen(true)}
          >
            <Plus className="size-4" />
            新建项目
          </Button>
        }
      />

      {listState === "loading" ? (
        <TableSkeleton />
      ) : listState === "error" ? (
        <GoldPanel dashed className="p-12 text-center">
          <p className="text-sm text-muted-foreground">加载失败，请重试</p>
          <Button
            className="mt-4 border-primary/25"
            variant="outline"
            onClick={() => void loadProjects(setProjects, setListState)}
          >
            重新加载
          </Button>
        </GoldPanel>
      ) : projects.length === 0 ? (
        <GoldPanel dashed className="p-12 text-center">
          <p className="font-heading text-lg text-foreground/80">暂无项目</p>
          <p className="mt-2 text-sm text-muted-foreground">
            点击「新建项目」开始第一份签字页
          </p>
        </GoldPanel>
      ) : (
        <GoldPanel className="overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="border-primary/15 hover:bg-transparent">
                <TableHead className="text-xs tracking-wider text-primary/80 uppercase">
                  项目名称
                </TableHead>
                <TableHead className="text-xs tracking-wider text-primary/80 uppercase">
                  状态
                </TableHead>
                <TableHead className="text-xs tracking-wider text-primary/80 uppercase">
                  创建时间
                </TableHead>
                <TableHead className="text-xs tracking-wider text-primary/80 uppercase">
                  更新时间
                </TableHead>
                <TableHead className="text-right text-xs tracking-wider text-primary/80 uppercase">
                  操作
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {projects.map((project) => (
                <TableRow
                  key={project.id}
                  className="group cursor-pointer border-primary/10 transition-colors hover:bg-primary/5"
                  onClick={() => navigate(`/projects/${project.id}`)}
                >
                  <TableCell className="font-medium">
                    <span className="inline-flex items-center gap-2 text-primary underline-offset-4 group-hover:underline">
                      {project.name}
                      <ChevronRight className="size-4 shrink-0 text-primary/50 transition-transform group-hover:translate-x-0.5 group-hover:text-primary/80" />
                    </span>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={project.status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDateTime(project.created_at)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDateTime(project.updated_at)}
                  </TableCell>
                  <TableCell
                    className="text-right"
                    onClick={(event) => event.stopPropagation()}
                  >
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => setDeleteTarget(project)}
                    >
                      <Trash2 className="size-4" />
                      删除
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </GoldPanel>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建项目</DialogTitle>
            <DialogDescription>输入项目名称，创建后可选择模板并填写变量。</DialogDescription>
          </DialogHeader>
          <Input
            placeholder="例如：某某公司 IPO 签字页"
            value={newProjectName}
            onChange={(event) => setNewProjectName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !creating) {
                void handleCreate()
              }
            }}
            autoFocus
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={creating}>
              取消
            </Button>
            <Button onClick={() => void handleCreate()} disabled={creating}>
              {creating ? <Loader2 className="size-4 animate-spin" /> : null}
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除项目？</AlertDialogTitle>
            <AlertDialogDescription>
              将删除项目「{deleteTarget?.name}」及其关联的模板、变量与生成文件，此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deleting}
              onClick={(event) => {
                event.preventDefault()
                void handleDelete()
              }}
            >
              {deleting ? <Loader2 className="size-4 animate-spin" /> : null}
              确认删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
