export type GenerationTaskStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"

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
}

export interface GeneratedFile {
  id: number
  project_id: number
  template_id: number
  template_name: string | null
  file_path: string
  status: string
  created_at: string
}

export interface GeneratedFileListResponse {
  files: GeneratedFile[]
}
