// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/dom";

// 并行测试在低配环境可能显著变慢；统一放宽异步查找等待，减少假失败。
configure({ asyncUtilTimeout: 5000 });
