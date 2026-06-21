export type TrustLevel = "high" | "medium" | "low"

export interface DedupSuggestion {
  keep_key: string
  merge_keys: string[]
  reason: string
  confidence: number
  evidence_list?: string[] | null
  risk_note?: string | null
  source?: string | null
  trust_level?: TrustLevel | null
  rules_match?: boolean | null
  warnings?: string[] | null
}

export interface AiDedupResponse {
  alias_suggestions: DedupSuggestion[]
  ai_suggestions: DedupSuggestion[]
  ai_used: boolean
  message: string | null
}

export interface ValidationIssue {
  level: "error" | "warning"
  variable_key: string
  message: string
  suggestion?: string | null
  confidence?: number | null
  evidence_list?: string[] | null
  risk_note?: string | null
  source?: string | null
  cross_validated?: boolean | null
}

export interface AiValidateResponse {
  regex_issues: ValidationIssue[]
  ai_issues: ValidationIssue[]
  issues: ValidationIssue[]
  ai_used: boolean
  message: string | null
}

export interface ApplyDedupResponse {
  merged_rows: number
}
