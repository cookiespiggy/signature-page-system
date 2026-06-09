const EAST_8 = "Asia/Shanghai"

/** 后端存 UTC 无时区后缀，按 UTC 解析后格式化为东八区 */
export function parseApiDateTime(value: string): Date {
  const trimmed = value.trim()
  if (!trimmed) return new Date(Number.NaN)

  if (trimmed.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(trimmed)) {
    return new Date(trimmed)
  }

  return new Date(`${trimmed}Z`)
}

export function formatDateTime(value: string): string {
  const date = parseApiDateTime(value)
  if (Number.isNaN(date.getTime())) return value

  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: EAST_8,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date)
}
