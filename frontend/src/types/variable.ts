export interface Variable {
  key: string
  label: string
  value: string
  category: string
  data_type: string
  required: boolean
  is_multiple: boolean
  sort_order: number
  source_template_ids: number[]
  is_merged: boolean
  merged_from_keys: string[] | null
  updated_at: string
}

export interface VariableListResponse {
  variables: Variable[]
}

export interface VariableSaveItem {
  key: string
  value: string
  updated_at?: string | null
}

export interface BatchErrorItem {
  row: number | null
  key: string | null
  message: string
}

export interface BatchSummary {
  total: number
  succeeded: number
  failed: number
}

export interface BatchOperationResponse {
  success: Array<Record<string, unknown>>
  errors: BatchErrorItem[]
  summary: BatchSummary
}
