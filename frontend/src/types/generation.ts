export type GenerationTaskStatus =
  | "pending"
  | "processing"
  | "completed"
  | "failed"
  | "cancelled"

export type TemplateProgressStatus =
  | "pending"
  | "processing"
  | "completed"
  | "failed"
  | "skipped"

export type GenerationLogLevel = "info" | "success" | "error" | "warning"

export interface TemplateProgressItem {
  template_id: number
  template_name: string
  template_category: string
  status: TemplateProgressStatus
  file_id: number | null
}

export interface GenerationLogEntry {
  timestamp: string
  level: GenerationLogLevel
  message: string
  template_name: string | null
}

export interface GenerationStartResponse {
  task_id: number
  status: string
}

export interface GenerationStatus {
  id: number
  project_id: number
  status: GenerationTaskStatus
  total_count: number
  completed_count: number
  error_message: string | null
  created_at: string
  updated_at: string
  completed_at: string | null
  cancelled_at: string | null
  template_progress: TemplateProgressItem[]
  logs: GenerationLogEntry[]
}

export interface GeneratedFile {
  id: number
  project_id: number
  template_id: number
  template_name: string | null
  template_category: string | null
  file_path: string
  status: string
  created_at: string
}

export interface GeneratedFileListResponse {
  files: GeneratedFile[]
}
