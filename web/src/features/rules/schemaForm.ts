// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

export type JsonSchema = {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  required?: readonly string[];
  properties?: Readonly<Record<string, JsonSchema>>;
  items?: JsonSchema;
  anyOf?: JsonSchema[];
};

export type FormValues = Record<string, unknown>;

function primarySchema(schema: JsonSchema): JsonSchema {
  if (schema.anyOf?.length) {
    return schema.anyOf.find((item) => item.type !== "null") ?? schema.anyOf[0];
  }
  return schema;
}

function schemaType(schema: JsonSchema) {
  return primarySchema(schema).type ?? (schema.properties ? "object" : "string");
}

export function defaultValuesFromSchema(schema: JsonSchema): FormValues {
  const values: FormValues = {};
  for (const [key, property] of Object.entries(schema.properties ?? {})) {
    values[key] = defaultFieldValue(property);
  }
  return values;
}

export function defaultFieldValue(schema: JsonSchema): unknown {
  const type = schemaType(schema);
  if (type === "boolean") {
    return typeof schema.default === "boolean" ? schema.default : false;
  }
  if (type === "array") {
    const itemSchema = schema.items ?? { type: "string" };
    if (schemaType(itemSchema) !== "object") {
      return "";
    }
    return Array.isArray(schema.default) ? schema.default : [];
  }
  if (type === "object") {
    return defaultValuesFromSchema(schema);
  }
  return schema.default === undefined ? "" : String(schema.default);
}

export function serializeValuesBySchema(schema: JsonSchema, values: FormValues) {
  const result: Record<string, unknown> = {};
  const required = new Set(schema.required ?? []);

  for (const [key, property] of Object.entries(schema.properties ?? {})) {
    const value = serializeFieldValue(property, values[key], key, required.has(key));
    if (value !== undefined) {
      result[key] = value;
    }
  }
  return result;
}

function serializeFieldValue(
  schema: JsonSchema,
  value: unknown,
  path: string,
  required: boolean,
): unknown {
  const type = schemaType(schema);

  if (type === "string") {
    const text = String(value ?? "").trim();
    if (!text) {
      if (required) {
        throw new Error(`${path} 不能为空`);
      }
      return undefined;
    }
    return text;
  }

  if (type === "integer" || type === "number") {
    const text = String(value ?? "").trim();
    if (!text) {
      if (required) {
        throw new Error(`${path} 不能为空`);
      }
      return undefined;
    }
    const parsed = Number(text);
    if (!Number.isFinite(parsed) || (type === "integer" && !Number.isInteger(parsed))) {
      throw new Error(`${path} 必须是${type === "integer" ? "整数" : "数字"}`);
    }
    return parsed;
  }

  if (type === "boolean") {
    return Boolean(value);
  }

  if (type === "array") {
    const itemSchema = schema.items ?? { type: "string" };
    const itemType = schemaType(itemSchema);
    if (itemType === "object") {
      const rows = Array.isArray(value) ? value : [];
      if (required && rows.length === 0) {
        throw new Error(`${path} 至少需要一条记录`);
      }
      const serialized = rows.map((row) =>
        serializeValuesBySchema(itemSchema, (row ?? {}) as FormValues),
      );
      return serialized.length ? serialized : undefined;
    }

    const items = String(value ?? "")
      .split(/[，,\n]/)
      .map((item) => item.trim())
      .filter(Boolean);
    if (required && items.length === 0) {
      throw new Error(`${path} 至少需要一个值`);
    }
    return items.length ? items : undefined;
  }

  if (type === "object") {
    const serialized = serializeValuesBySchema(schema, (value ?? {}) as FormValues);
    return Object.keys(serialized).length ? serialized : undefined;
  }

  return String(value ?? "");
}
