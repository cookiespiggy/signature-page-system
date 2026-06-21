import type {
  GeneratedFileListResponse,
  GenerationStartResponse,
  GenerationStatus,
  ProjectFileBatchesResponse,
} from "@/types/generation"
import type { HealthResponse, Project } from "@/types/project"
import type {
  ProjectTemplate,
  Template,
  TemplateParseResponse,
  TemplateRefreshResponse,
  TemplateVariableDefinition,
} from "@/types/template"
import type {
  AiDedupResponse,
  AiValidateResponse,
  ApplyDedupResponse,
  DedupSuggestion,
} from "@/types/ai"
import type {
  BatchOperationResponse,
  VariableListResponse,
  VariableSaveItem,
} from "@/types/variable"

const API_BASE = "/api"

export type ApiRequestState = "idle" | "loading" | "success" | "error"

export interface ApiState<T> {
  data: T | null
  state: ApiRequestState
  error: string | null
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string | null

  constructor(message: string, status: number, code: string | null = null) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.code = code
  }
}

interface FastAPIErrorBody {
  detail?: string | { msg?: string; loc?: unknown[] }[]
  code?: string
}

async function parseErrorBody(response: Response): Promise<{ message: string; code: string | null }> {
  let message = response.statusText || "请求失败"
  let code: string | null = null
  try {
    const body = (await response.json()) as FastAPIErrorBody
    if (typeof body.detail === "string") {
      message = body.detail
    } else if (Array.isArray(body.detail) && body.detail.length > 0) {
      message = body.detail.map((item) => item.msg ?? "请求参数错误").join("；")
    }
    code = body.code ?? null
  } catch {
    // ignore JSON parse errors
  }
  return { message, code }
}

function mapErrorMessage(error: ApiError): string {
  if (error.status === 0) {
    return "网络连接失败，请检查网络后重试"
  }
  if (error.status === 409) {
    return error.message || "数据已被修改，请刷新后重试"
  }
  if (error.status >= 500) {
    return "服务异常，请稍后重试"
  }
  return error.message
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    })
  } catch {
    throw new ApiError("网络连接失败", 0)
  }

  if (response.status === 204) {
    return undefined as T
  }

  if (!response.ok) {
    const { message, code } = await parseErrorBody(response)
    throw new ApiError(message, response.status, code)
  }

  return (await response.json()) as T
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return mapErrorMessage(error)
  }
  if (error instanceof Error) {
    return error.message
  }
  return "未知错误"
}

export const healthApi = {
  check: () => request<HealthResponse>("/health"),
}

export const projectsApi = {
  list: () => request<Project[]>("/projects"),
  get: (id: number) => request<Project>(`/projects/${id}`),
  create: (name: string) =>
    request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  delete: (id: number) =>
    request<void>(`/projects/${id}`, {
      method: "DELETE",
    }),
}

async function requestForm<T>(path: string, formData: FormData, method = "POST"): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      body: formData,
    })
  } catch {
    throw new ApiError("网络连接失败", 0)
  }

  if (!response.ok) {
    const { message, code } = await parseErrorBody(response)
    throw new ApiError(message, response.status, code)
  }

  return (await response.json()) as T
}

async function downloadFile(path: string, fallbackFilename: string): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`)
  } catch {
    throw new ApiError("网络连接失败", 0)
  }

  if (!response.ok) {
    const { message, code } = await parseErrorBody(response)
    throw new ApiError(message, response.status, code)
  }

  const blob = await response.blob()
  const disposition = response.headers.get("Content-Disposition")
  const match = disposition?.match(/filename="?([^";\n]+)"?/)
  const filename = match?.[1] ?? fallbackFilename

  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export const templatesApi = {
  list: () => request<Template[]>("/templates"),
  get: (id: number) => request<Template>(`/templates/${id}`),
  parse: (file: File) => {
    const form = new FormData()
    form.append("file", file)
    return requestForm<TemplateParseResponse>("/templates/parse", form)
  },
  create: (params: {
    file: File
    name: string
    description?: string
    category?: string
    variables_json: TemplateVariableDefinition[]
  }) => {
    const form = new FormData()
    form.append("file", params.file)
    form.append("name", params.name)
    if (params.description) form.append("description", params.description)
    form.append("category", params.category ?? "other")
    form.append("tags", "[]")
    form.append("variables_json", JSON.stringify(params.variables_json))
    return requestForm<Template>("/templates", form)
  },
  delete: (id: number) =>
    request<void>(`/templates/${id}`, {
      method: "DELETE",
    }),
  listProjectTemplates: (projectId: number) =>
    request<ProjectTemplate[]>(`/projects/${projectId}/templates`),
  addToProject: (projectId: number, templateIds: number[]) =>
    request<ProjectTemplate[]>(`/projects/${projectId}/templates`, {
      method: "POST",
      body: JSON.stringify({ template_ids: templateIds }),
    }),
  removeFromProject: (projectId: number, templateId: number) =>
    request<void>(`/projects/${projectId}/templates/${templateId}`, {
      method: "DELETE",
    }),
  refreshProjectTemplate: (projectId: number, templateId: number) =>
    request<TemplateRefreshResponse>(
      `/projects/${projectId}/templates/${templateId}/refresh`,
      { method: "POST" },
    ),
}

export const variablesApi = {
  list: (projectId: number) =>
    request<VariableListResponse>(`/projects/${projectId}/variables`),
  save: (projectId: number, variables: VariableSaveItem[]) =>
    request<BatchOperationResponse>(`/projects/${projectId}/variables`, {
      method: "PUT",
      body: JSON.stringify({ variables }),
    }),
  importPreview: (projectId: number, file: File) => {
    const form = new FormData()
    form.append("file", file)
    return requestForm<BatchOperationResponse>(
      `/projects/${projectId}/variables/import-preview`,
      form,
    )
  },
  import: (projectId: number, rows: Array<Record<string, unknown>>) =>
    request<BatchOperationResponse>(`/projects/${projectId}/variables/import`, {
      method: "POST",
      body: JSON.stringify({ rows }),
    }),
  exportTemplate: (projectId: number) =>
    downloadFile(
      `/projects/${projectId}/variables/export-template`,
      `project_${projectId}_template.xlsx`,
    ),
  export: (projectId: number) =>
    downloadFile(
      `/projects/${projectId}/variables/export`,
      `project_${projectId}_variables.xlsx`,
    ),
  aiDedup: (projectId: number) =>
    request<AiDedupResponse>(`/projects/${projectId}/variables/ai-dedup`, {
      method: "POST",
    }),
  applyDedup: (projectId: number, suggestions: DedupSuggestion[]) =>
    request<ApplyDedupResponse>(`/projects/${projectId}/variables/apply-dedup`, {
      method: "POST",
      body: JSON.stringify({ suggestions }),
    }),
  aiValidate: (projectId: number) =>
    request<AiValidateResponse>(`/projects/${projectId}/variables/ai-validate`, {
      method: "POST",
    }),
}

export const generationApi = {
  start: (projectId: number) =>
    request<GenerationStartResponse>(`/projects/${projectId}/generate`, {
      method: "POST",
    }),
  cancel: (projectId: number) =>
    request<GenerationStatus>(`/projects/${projectId}/generate/cancel`, {
      method: "POST",
    }),
  status: (projectId: number) =>
    request<GenerationStatus | null>(`/projects/${projectId}/generate/status`),
  listFiles: (projectId: number) =>
    request<GeneratedFileListResponse>(`/projects/${projectId}/files`),
  batches: (projectId: number) =>
    request<ProjectFileBatchesResponse>(`/projects/${projectId}/files/batches`),
  downloadFile: (fileId: number, filename: string) =>
    downloadFile(`/files/${fileId}/download`, filename),
  fetchFileBlob: async (fileId: number): Promise<Blob> => {
    let response: Response
    try {
      response = await fetch(`${API_BASE}/files/${fileId}/download`)
    } catch {
      throw new ApiError("网络连接失败", 0)
    }
    if (!response.ok) {
      const { message, code } = await parseErrorBody(response)
      throw new ApiError(message, response.status, code)
    }
    return response.blob()
  },
  downloadAll: (projectId: number) =>
    downloadFile(`/projects/${projectId}/download-all`, `project_${projectId}_all.zip`),
}

export function createInitialApiState<T>(data: T | null = null): ApiState<T> {
  return {
    data,
    state: "idle",
    error: null,
  }
}
