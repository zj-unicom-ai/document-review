// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import type { FormValues, JsonSchema } from "./schemaForm";
import { defaultFieldValue } from "./schemaForm";

export function SchemaField({
  schema,
  label,
  value,
  onChange,
  placeholder,
  required,
}: {
  schema: JsonSchema;
  label: string;
  value: unknown;
  onChange: (value: unknown) => void;
  placeholder?: string;
  required?: boolean;
}) {
  const requiredClass = required ? " is-required" : "";
  const type = schema.anyOf?.length
    ? (schema.anyOf.find((item) => item.type !== "null")?.type ?? "string")
    : schema.type ?? (schema.properties ? "object" : "string");

  if (type === "boolean") {
    return (
      <label className="checkbox">
        <input type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} />
        <span className={`field-label${requiredClass}`}>{label}</span>
      </label>
    );
  }

  if (type === "array" && schema.items?.type !== "object" && !schema.items?.properties) {
    return (
      <label className="field">
        <span className={`field-label${requiredClass}`}>{label}</span>
        <textarea
          className="text-area compact"
          value={String(value ?? "")}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder ?? "多个值用逗号或换行分隔"}
        />
      </label>
    );
  }

  if (type === "array") {
    const itemSchema = schema.items ?? {};
    const rows = Array.isArray(value) ? (value as FormValues[]) : [];
    return (
      <div className="schema-array">
        <div className="schema-array-header">
          <span>{label}</span>
          <button
            type="button"
            className="button button-secondary"
            onClick={() => onChange([...rows, defaultFieldValue(itemSchema)])}
          >
            添加
          </button>
        </div>
        {rows.map((row, index) => (
          <div className="schema-row" key={index}>
            {Object.entries(itemSchema.properties ?? {}).map(([key, property]) => (
              <SchemaField
                key={key}
                schema={property}
                label={property.title ?? key}
                value={row[key]}
                onChange={(nextValue) => {
                  const next = [...rows];
                  next[index] = { ...row, [key]: nextValue };
                  onChange(next);
                }}
              />
            ))}
            <button type="button" className="button button-ghost" onClick={() => onChange(rows.filter((_, i) => i !== index))}>
              删除
            </button>
          </div>
        ))}
      </div>
    );
  }

  if (type === "integer" || type === "number") {
    return (
      <label className="field">
        <span className={`field-label${requiredClass}`}>{label}</span>
        <input
          className="text-input"
          type="number"
          step={type === "integer" ? 1 : "any"}
          value={String(value ?? "")}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
    );
  }

  return (
    <label className="field">
      <span className={`field-label${requiredClass}`}>{label}</span>
      <input
        className="text-input"
        value={String(value ?? "")}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}
