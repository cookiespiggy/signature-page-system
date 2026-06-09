import type { VariableField } from "@/lib/variable-utils"

const CN_DATE_PATTERN = /^(\d{4})年(\d{1,2})月(\d{1,2})日$/

export type VariableInputKind = "text" | "date" | "datetime" | "time"

export function getVariableInputKind(field: VariableField): VariableInputKind {
  if (field.data_type === "datetime") return "datetime"
  if (field.data_type === "time") return "time"
  if (field.data_type === "date" || field.baseKey === "signing_date" || field.category === "date") {
    return "date"
  }
  return "text"
}

/** 中文日期「2026年6月9日」→ HTML date value「2026-06-09」 */
export function chineseDateToIso(value: string): string {
  const match = CN_DATE_PATTERN.exec(value.trim())
  if (!match) return ""
  const year = match[1]
  const month = match[2].padStart(2, "0")
  const day = match[3].padStart(2, "0")
  return `${year}-${month}-${day}`
}

/** HTML date value「2026-06-09」→ 中文日期「2026年6月9日」 */
export function isoDateToChinese(iso: string): string {
  const [year, month, day] = iso.split("-")
  if (!year || !month || !day) return ""
  return `${year}年${Number(month)}月${Number(day)}日`
}

/** datetime-local value ↔ 存储值「YYYY-MM-DD HH:mm」 */
export function datetimeLocalToStored(value: string): string {
  if (!value) return ""
  const [datePart, timePart] = value.split("T")
  if (!datePart || !timePart) return value
  return `${datePart} ${timePart}`
}

export function storedToDatetimeLocal(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) return ""
  if (trimmed.includes("T")) return trimmed.slice(0, 16)
  const normalized = trimmed.replace(" ", "T")
  return normalized.length >= 16 ? normalized.slice(0, 16) : normalized
}
