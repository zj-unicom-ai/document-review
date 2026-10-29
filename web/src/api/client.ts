// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly payload: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type JsonRecord = Record<string, unknown>;

type RequestOptions = {
  method?: string;
  body?: unknown;
  tenantId?: string;
  signal?: AbortSignal;
};

let currentTenantId = "";

export function setDefaultTenantId(tenantId: string) {
  currentTenantId = tenantId;
}

async function readPayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function errorMessage(payload: unknown): string {
  if (typeof payload === "string" && payload.trim()) {
    return payload;
  }
  if (payload && typeof payload === "object") {
    const record = payload as JsonRecord;
    if (typeof record.message === "string" && record.message) {
      return record.message;
    }
    if (typeof record.detail === "string" && record.detail) {
      return record.detail;
    }
    if (Array.isArray(record.detail)) {
      const messages = record.detail
        .map((item) => (item && typeof item === "object" ? (item as JsonRecord).msg : item))
        .filter(Boolean);
      if (messages.length) {
        return messages.join("；");
      }
    }
  }
  return "请求失败，请检查后端服务状态";
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    "X-Tenant-Id": options.tenantId ?? currentTenantId,
  };
  let body: BodyInit | undefined;

  if (options.body instanceof FormData) {
    body = options.body;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  const response = await fetch(path, {
    method: options.method ?? "GET",
    headers,
    body,
    signal: options.signal,
  });
  if (!response.ok) {
    const payload = await readPayload(response);
    throw new ApiError(response.status, errorMessage(payload), payload);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  if (response.headers.get("content-type")?.includes("application/json")) {
    return (await response.json()) as T;
  }
  return (await response.text()) as T;
}

export const apiClient = {
  get<T>(path: string, options?: RequestOptions) {
    return request<T>(path, { ...options, method: "GET" });
  },
  post<T>(path: string, body?: unknown, options?: RequestOptions) {
    return request<T>(path, { ...options, method: "POST", body });
  },
  patch<T>(path: string, body?: unknown, options?: RequestOptions) {
    return request<T>(path, { ...options, method: "PATCH", body });
  },
  put<T>(path: string, body?: unknown, options?: RequestOptions) {
    return request<T>(path, { ...options, method: "PUT", body });
  },
  delete<T>(path: string, options?: RequestOptions) {
    return request<T>(path, { ...options, method: "DELETE" });
  },
  upload<T>(path: string, form: FormData, options?: RequestOptions) {
    return request<T>(path, { ...options, method: "POST", body: form });
  },
  async blob(path: string, options?: RequestOptions) {
    const headers: Record<string, string> = {
      "X-Tenant-Id": options?.tenantId ?? currentTenantId,
    };
    const response = await fetch(path, {
      method: "GET",
      headers,
      signal: options?.signal,
    });
    if (!response.ok) {
      const payload = await readPayload(response);
      throw new ApiError(response.status, errorMessage(payload), payload);
    }
    return response.blob();
  },
};
