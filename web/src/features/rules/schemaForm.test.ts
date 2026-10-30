// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { expect, test } from "vitest";
import {
  defaultValuesFromSchema,
  serializeValuesBySchema,
} from "./schemaForm";

const schema = {
  type: "object",
  required: ["field_aliases", "min"],
  properties: {
    field_aliases: { type: "array", items: { type: "string" } },
    min: { type: "integer" },
    enabled: { type: "boolean" },
    pattern: { type: "string" },
  },
} as const;

test("根据 Schema 生成默认值并序列化字符串数组与数字", () => {
  const defaults = defaultValuesFromSchema(schema);

  expect(defaults).toEqual({
    field_aliases: "",
    min: "",
    enabled: false,
    pattern: "",
  });

  expect(
    serializeValuesBySchema(schema, {
      ...defaults,
      field_aliases: "企业名称，\n地址",
      min: "2",
    }),
  ).toEqual({
    field_aliases: ["企业名称", "地址"],
    min: 2,
    enabled: false,
  });
});

test("对象数组按条目 Schema 序列化", () => {
  const objectSchema = {
    type: "object",
    required: ["sections"],
    properties: {
      sections: {
        type: "array",
        items: {
          type: "object",
          properties: {
            name: { type: "string" },
            ordinal: { type: "integer" },
          },
          required: ["name"],
        },
      },
    },
  } as const;

  expect(
    serializeValuesBySchema(objectSchema, {
      sections: [
        { name: "基本信息", ordinal: "1" },
        { name: "服务总结", ordinal: "" },
      ],
    }),
  ).toEqual({
    sections: [
      { name: "基本信息", ordinal: 1 },
      { name: "服务总结" },
    ],
  });
});

test("必填数组为空和数字非法时返回字段错误", () => {
  expect(() =>
    serializeValuesBySchema(schema, {
      field_aliases: "",
      min: "1",
      enabled: false,
      pattern: "",
    }),
  ).toThrow(/field_aliases/);
  expect(() =>
    serializeValuesBySchema(schema, {
      field_aliases: "企业名称",
      min: "abc",
      enabled: false,
      pattern: "",
    }),
  ).toThrow(/min/);
});
