/** 与后端 variable_registry.VALIDATION_RULES 保持一致的前端实时校验 */

const VALIDATION_RULES: Record<string, RegExp> = {
  natural_shareholder_id_number: /^\d{17}[\dXx]$/,
  target_company_name: /.+股份有限公司|.+有限责任公司/,
  signing_date: /^\d{4}年\d{1,2}月\d{1,2}日$/,
}

const MULTIPLE_KEY_PATTERN = /^(.+)_(\d+)$/

function baseKey(key: string): string {
  const match = MULTIPLE_KEY_PATTERN.exec(key)
  return match ? match[1] : key
}

export function validateVariableValue(key: string, value: string): string | null {
  const trimmed = value.trim()
  if (!trimmed) return null

  const base = baseKey(key)
  const pattern = VALIDATION_RULES[base] ?? VALIDATION_RULES[key]
  if (pattern && !pattern.test(trimmed)) {
    if (base === "natural_shareholder_id_number") {
      return "请输入 18 位身份证号"
    }
    if (base === "target_company_name") {
      return "公司名称需包含「股份有限公司」或「有限责任公司」"
    }
    if (base === "signing_date") {
      return "日期格式应为「YYYY年M月D日」"
    }
    return "格式不符合要求"
  }
  return null
}
