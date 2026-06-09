import { getCategoryLabel } from "@/lib/variable-utils"
import type { GeneratedFile } from "@/types/generation"

const CATEGORY_ORDER = [
  "lawyer",
  "shareholder",
  "company",
  "document",
  "meeting",
  "date",
  "other",
]

export function getTemplateCategoryLabel(category: string | null | undefined): string {
  return getCategoryLabel(category ?? "other")
}

export function groupFilesByCategory(
  files: GeneratedFile[],
): Array<{ category: string; label: string; files: GeneratedFile[] }> {
  const groups = new Map<string, GeneratedFile[]>()
  for (const file of files) {
    const category = file.template_category ?? "other"
    const list = groups.get(category) ?? []
    list.push(file)
    groups.set(category, list)
  }

  const ordered = [...groups.entries()].sort(([left], [right]) => {
    const leftIndex = CATEGORY_ORDER.indexOf(left)
    const rightIndex = CATEGORY_ORDER.indexOf(right)
    const safeLeft = leftIndex === -1 ? CATEGORY_ORDER.length : leftIndex
    const safeRight = rightIndex === -1 ? CATEGORY_ORDER.length : rightIndex
    return safeLeft - safeRight
  })

  return ordered.map(([category, categoryFiles]) => ({
    category,
    label: getTemplateCategoryLabel(category),
    files: categoryFiles,
  }))
}
