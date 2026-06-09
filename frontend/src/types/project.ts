export type ProjectStatus = "draft" | "generating" | "completed"

export interface Project {
  id: number
  name: string
  status: ProjectStatus
  created_at: string
  updated_at: string
}

export interface HealthResponse {
  status: string
  database: string
  llm_provider: string
  llm_available: boolean
}
