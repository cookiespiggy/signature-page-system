import { baseKey } from "@/lib/variable-utils"
import type { VariableField } from "@/lib/variable-utils"
import type { ValidationIssue } from "@/types/ai"

export interface FieldValidationHighlight {
  errors: string[]
  warnings: string[]
}

export function buildValidationHighlights(
  fields: VariableField[],
  issues: ValidationIssue[],
): Record<string, FieldValidationHighlight> {
  const highlights: Record<string, FieldValidationHighlight> = {}

  const ensure = (key: string): FieldValidationHighlight => {
    if (!highlights[key]) {
      highlights[key] = { errors: [], warnings: [] }
    }
    return highlights[key]
  }

  for (const issue of issues) {
    const matchedKeys = resolveIssueRowKeys(fields, issue.variable_key)
    for (const rowKey of matchedKeys) {
      const bucket = ensure(rowKey)
      if (issue.level === "error") {
        if (!bucket.errors.includes(issue.message)) {
          bucket.errors.push(issue.message)
        }
      } else if (!bucket.warnings.includes(issue.message)) {
        bucket.warnings.push(issue.message)
      }
    }
  }

  return highlights
}

export function resolveIssueRowKeys(fields: VariableField[], variableKey: string): string[] {
  const exactField = fields.find((field) =>
    field.rows.some((row) => row.key === variableKey),
  )
  if (exactField) {
    return exactField.rows
      .filter((row) => row.key === variableKey)
      .map((row) => row.key)
  }

  const base = baseKey(variableKey)
  const field = fields.find((item) => item.baseKey === base || item.baseKey === variableKey)
  if (!field) return [variableKey]
  return field.rows.map((row) => row.key)
}

export function scrollToVariableField(variableKey: string) {
  const base = baseKey(variableKey)
  const target =
    document.getElementById(`var-field-${variableKey}`) ??
    document.getElementById(`var-field-${base}`)
  target?.scrollIntoView({ behavior: "smooth", block: "center" })
}
