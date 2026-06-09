import { Input } from "@/components/ui/input"
import {
  chineseDateToIso,
  datetimeLocalToStored,
  getVariableInputKind,
  isoDateToChinese,
  storedToDatetimeLocal,
  type VariableInputKind,
} from "@/lib/variable-input"
import type { VariableField } from "@/lib/variable-utils"
import { cn } from "@/lib/utils"

interface VariableFieldInputProps {
  field: VariableField
  value: string
  error?: string
  warning?: string
  highlighted?: boolean
  placeholder?: string
  onValueChange: (value: string) => void
}

function pickerClassName(error?: string, warning?: string, highlighted?: boolean) {
  return cn(
    "border-primary/25 [color-scheme:dark]",
    error && "border-destructive",
    !error && warning && "border-primary/50",
    highlighted && !error && "ring-1 ring-primary/40",
  )
}

function handlePickerChange(
  kind: VariableInputKind,
  raw: string,
  onValueChange: (value: string) => void,
) {
  if (kind === "date") {
    onValueChange(raw ? isoDateToChinese(raw) : "")
    return
  }
  if (kind === "datetime") {
    onValueChange(raw ? datetimeLocalToStored(raw) : "")
    return
  }
  onValueChange(raw)
}

function pickerValue(kind: VariableInputKind, value: string): string {
  if (kind === "date") return chineseDateToIso(value)
  if (kind === "datetime") return storedToDatetimeLocal(value)
  return value
}

export function VariableFieldInput({
  field,
  value,
  error,
  warning,
  highlighted,
  placeholder,
  onValueChange,
}: VariableFieldInputProps) {
  const kind = getVariableInputKind(field)

  if (kind === "date") {
    return (
      <div>
        <Input
          type="date"
          value={pickerValue(kind, value)}
          onChange={(event) => handlePickerChange(kind, event.target.value, onValueChange)}
          className={pickerClassName(error, warning, highlighted)}
          aria-invalid={Boolean(error)}
        />
        {value ? (
          <p className="mt-1 text-xs text-muted-foreground">将填入：{value}</p>
        ) : (
          <p className="mt-1 text-xs text-muted-foreground">格式：YYYY年M月D日</p>
        )}
        {error ? <p className="mt-1 text-xs text-destructive">{error}</p> : null}
        {!error && warning ? <p className="mt-1 text-xs text-primary">{warning}</p> : null}
      </div>
    )
  }

  if (kind === "datetime") {
    return (
      <div>
        <Input
          type="datetime-local"
          value={pickerValue(kind, value)}
          onChange={(event) => handlePickerChange(kind, event.target.value, onValueChange)}
          className={pickerClassName(error, warning, highlighted)}
          aria-invalid={Boolean(error)}
        />
        {error ? <p className="mt-1 text-xs text-destructive">{error}</p> : null}
        {!error && warning ? <p className="mt-1 text-xs text-primary">{warning}</p> : null}
      </div>
    )
  }

  if (kind === "time") {
    return (
      <div>
        <Input
          type="time"
          value={value}
          onChange={(event) => onValueChange(event.target.value)}
          className={pickerClassName(error, warning, highlighted)}
          aria-invalid={Boolean(error)}
        />
        {error ? <p className="mt-1 text-xs text-destructive">{error}</p> : null}
        {!error && warning ? <p className="mt-1 text-xs text-primary">{warning}</p> : null}
      </div>
    )
  }

  return (
    <div>
      <Input
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        className={cn(
          "border-primary/25",
          error && "border-destructive",
          !error && warning && "border-primary/50",
          highlighted && !error && "ring-1 ring-primary/40",
        )}
        placeholder={placeholder}
        aria-invalid={Boolean(error)}
      />
      {error ? <p className="mt-1 text-xs text-destructive">{error}</p> : null}
      {!error && warning ? <p className="mt-1 text-xs text-primary">{warning}</p> : null}
    </div>
  )
}
