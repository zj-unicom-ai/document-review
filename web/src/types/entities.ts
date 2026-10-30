// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import type { components } from "./api";

export type SchemaName = keyof components["schemas"];

export type Entity<S extends SchemaName> = components["schemas"][S];

export type PageResult<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};
