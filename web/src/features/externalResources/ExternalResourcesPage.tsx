// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createExternalResource, listExternalResources } from "../../api/endpoints";
import { Button } from "../../components/Button";
import { DataTable } from "../../components/DataTable";
import { Field, Select, TextArea, TextInput } from "../../components/Field";
import { PageHeader } from "../../components/PageHeader";
import { ErrorBanner } from "../../components/StateBlocks";
import { parseJsonDraft } from "../../utils/json";

export function ExternalResourcesPage() {
  const queryClient = useQueryClient();
  const [resourceKey, setResourceKey] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState<"db_table" | "file_csv" | "file_xlsx" | "http">("db_table");
  const [configDraft, setConfigDraft] = useState("{}");
  const [error, setError] = useState("");

  const resources = useQuery({
    queryKey: ["external-resources"],
    queryFn: () => listExternalResources({ pageSize: 200 }),
  });
  const create = useMutation({
    mutationFn: () =>
      createExternalResource({
        resource_key: resourceKey.trim(),
        name: name.trim(),
        description: null,
        resource_type: type,
        config: parseJsonDraft<Record<string, unknown>>(configDraft || "{}"),
        schema_desc: null,
      }),
    onSuccess: async () => {
      setResourceKey("");
      setName("");
      setConfigDraft("{}");
      setError("");
      await queryClient.invalidateQueries({ queryKey: ["external-resources"] });
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : String(mutationError)),
  });

  return (
    <div className="page-stack">
      <PageHeader eyebrow="SYSTEM" title="外部资源" description="登记专家库、检查项库等外部数据来源。" />
      <ErrorBanner error={resources.error} title="资源读取失败" />
      <DataTable
        columns={[
          { key: "key", title: "Key", render: (row) => row.resource_key },
          { key: "name", title: "名称", render: (row) => row.name },
          { key: "type", title: "类型", render: (row) => row.resource_type },
        ]}
        rows={resources.data?.items ?? []}
        rowKey={(row) => row.id}
        empty="暂无外部资源"
      />
      <form
        className="editor-panel"
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate();
        }}
      >
        <h3>新建资源</h3>
        <div className="form-grid">
          <Field label="资源 Key">
            <TextInput value={resourceKey} onChange={(event) => setResourceKey(event.target.value)} />
          </Field>
          <Field label="资源名称">
            <TextInput value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
          <Field label="资源类型">
            <Select value={type} onChange={(event) => setType(event.target.value as typeof type)}>
              <option value="db_table">db_table</option>
              <option value="file_csv">file_csv</option>
              <option value="file_xlsx">file_xlsx</option>
              <option value="http">http</option>
            </Select>
          </Field>
        </div>
        <Field label="配置 JSON">
          <TextArea value={configDraft} onChange={(event) => setConfigDraft(event.target.value)} />
        </Field>
        <div className="form-actions">
          <Button type="submit" variant="primary" disabled={!resourceKey.trim() || !name.trim() || create.isPending}>
            创建资源
          </Button>
        </div>
      </form>
      <ErrorBanner error={error} title="资源保存失败" />
    </div>
  );
}
