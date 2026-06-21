export interface TemplateVariableDefinition {
  key: string
  label: string
  category: string
  data_type: string
  required: boolean
  is_multiple: boolean
}

export interface Template {
  id: number
  name: string
  description: string | null
  category: string
  tags: string[] | null
  applicable_scenarios: string | null
  variable_count: number
  is_preset: boolean
  file_path: string | null
  variables_json: TemplateVariableDefinition[] | null
  version: number
  preview_image: string | null
  created_at: string
  updated_at: string
}

export interface ParsedVariable {
  key: string
  label: string
  category: string
  data_type: string
  required: boolean
  is_multiple: boolean
  is_registered?: boolean
  trust_level?: string | null
  suggested_key?: string | null
  warnings?: string[] | null
  confidence?: number | null
  evidence_list?: string[] | null
  risk_note?: string | null
}

export interface TemplateParseResponse {
  variables: ParsedVariable[]
  ai_used: boolean
  parse_duration_ms: number
  message: string | null
}

export interface ProjectTemplate {
  id: number
  project_id: number
  template_id: number
  template_version: number
  variables_snapshot_json: TemplateVariableDefinition[] | null
  needs_refresh: boolean
  latest_template_version: number | null
}

export interface TemplateRefreshResponse {
  added: number
  removed: number
  kept: number
}
