import type { Variable } from "@/types/variable"

const MULTIPLE_KEY_PATTERN = /^(.+)_(\d+)$/

export function baseKey(key: string): string {
  const match = MULTIPLE_KEY_PATTERN.exec(key)
  return match ? match[1] : key
}

export function rowIndex(key: string): number {
  const match = MULTIPLE_KEY_PATTERN.exec(key)
  return match ? Number.parseInt(match[2], 10) : 0
}

export interface VariableRow {
  key: string
  value: string
  updated_at: string
}

export interface VariableField {
  baseKey: string
  label: string
  category: string
  data_type: string
  required: boolean
  isMultiple: boolean
  sort_order: number
  rows: VariableRow[]
}

const CATEGORY_LABELS: Record<string, string> = {
  company: "公司信息",
  lawyer: "律师信息",
  shareholder: "股东信息",
  meeting: "会议信息",
  document: "文件信息",
  date: "日期信息",
  other: "其他",
}

export function getCategoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category
}

/** 将 API 变量列表整理为表单字段（multiple 合并为行组） */
export function buildVariableFields(variables: Variable[]): VariableField[] {
  const singles = new Map<string, VariableField>()
  const multiples = new Map<string, VariableField>()

  for (const variable of variables) {
    const base = baseKey(variable.key)
    const isIndexedMultiple = MULTIPLE_KEY_PATTERN.test(variable.key)

    if (variable.is_multiple || isIndexedMultiple) {
      let field = multiples.get(base)
      if (!field) {
        field = {
          baseKey: base,
          label: variable.label,
          category: variable.category,
          data_type: variable.data_type,
          required: variable.required,
          isMultiple: true,
          sort_order: variable.sort_order,
          rows: [],
        }
        multiples.set(base, field)
      }
      field.rows.push({
        key: variable.key,
        value: variable.value,
        updated_at: variable.updated_at,
      })
    } else {
      singles.set(variable.key, {
        baseKey: variable.key,
        label: variable.label,
        category: variable.category,
        data_type: variable.data_type,
        required: variable.required,
        isMultiple: false,
        sort_order: variable.sort_order,
        rows: [
          {
            key: variable.key,
            value: variable.value,
            updated_at: variable.updated_at,
          },
        ],
      })
    }
  }

  for (const field of multiples.values()) {
    field.rows.sort((a, b) => rowIndex(a.key) - rowIndex(b.key))
  }

  const all = [...singles.values(), ...multiples.values()]
  all.sort((a, b) => {
    if (a.category !== b.category) return a.category.localeCompare(b.category)
    return a.sort_order - b.sort_order || a.baseKey.localeCompare(b.baseKey)
  })
  return all
}

export function groupFieldsByCategory(fields: VariableField[]): Map<string, VariableField[]> {
  const groups = new Map<string, VariableField[]>()
  for (const field of fields) {
    const list = groups.get(field.category) ?? []
    list.push(field)
    groups.set(field.category, list)
  }
  return groups
}

export function fieldsToSaveItems(fields: VariableField[]): Array<{
  key: string
  value: string
  updated_at: string | null
}> {
  const items: Array<{ key: string; value: string; updated_at: string | null }> = []
  for (const field of fields) {
    for (const row of field.rows) {
      items.push({
        key: row.key,
        value: row.value,
        updated_at: row.updated_at || null,
      })
    }
  }
  return items
}

export function nextMultipleRowKey(field: VariableField): string {
  const maxIndex = field.rows.reduce((max, row) => Math.max(max, rowIndex(row.key)), 0)
  return `${field.baseKey}_${maxIndex + 1}`
}
