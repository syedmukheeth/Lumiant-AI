"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Copy, KeyRound, Trash2, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { api } from "@/lib/api";
import { formatTimestamp, humanize } from "@/lib/format";

import { AlertsPanel } from "./alerts-panel";

type Key = {
  id: string;
  name: string;
  permissions: string[];
  warehouses: "all" | string[];
  created_by: string;
  created_at: string;
  last_used_at: string | null;
  revoked: boolean;
};

const LABEL: Record<string, string> = {
  "dashboard:read": "Dashboards",
  "inventory:read": "Inventory",
  "cost:read": "Costs and values",
  "query:run": "Queries",
  "chat:use": "Analyst",
  "export:data": "Exports",
};

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <Button
      size="sm"
      variant="ghost"
      onClick={() => {
        void navigator.clipboard?.writeText(text);
        setDone(true);
      }}
    >
      <Copy size={13} aria-hidden /> {done ? "Copied" : "Copy"}
    </Button>
  );
}

/** Admin › Integrations: API keys for service accounts and how to connect an AI assistant over MCP (V3). */
export function IntegrationsPanel() {
  const qc = useQueryClient();
  const keys = useQuery({ queryKey: ["api-keys"], queryFn: () => api.get<{ keys: Key[]; grantable: string[] }>("/api/admin/api-keys") });
  const [name, setName] = useState("");
  const [perms, setPerms] = useState<string[]>(["dashboard:read", "inventory:read", "chat:use"]);
  const create = useMutation({
    mutationFn: () => api.post<{ key: string; record: Key; note: string }>("/api/admin/api-keys", { name, permissions: perms }),
    onSuccess: () => {
      setName("");
      void qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });
  const revoke = useMutation({
    mutationFn: (id: string) => api.delete<{ revoked: string }>(`/api/admin/api-keys/${id}`),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["api-keys"] }),
  });
  const origin = typeof window === "undefined" ? "https://your-lumiant-host" : window.location.origin;
  const mcpConfig = JSON.stringify(
    { mcpServers: { lumiant: { type: "http", url: `${origin}/mcp`, headers: { Authorization: "Bearer <your lmk_ key>" } } } },
    null,
    2,
  );

  return (
    <div className="space-y-6">
      <Panel
        title="API keys"
        subtitle="For the public API, the MCP server and other integrations. A key can never do more than you: no administration, your warehouses at most. It is shown once and stored only as a hash."
      >
        <form
          className="grid gap-4 lg:grid-cols-[minmax(0,18rem)_1fr_auto] lg:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim() && perms.length) create.mutate();
          }}
        >
          <Field label="Key name">
            <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="e.g. Claude for planners" data-testid="key-name" />
          </Field>
          <fieldset className="min-w-0">
            <legend className="mb-1.5 text-xs font-medium text-ink-2">What it may do</legend>
            <div className="flex flex-wrap gap-x-4 gap-y-2">
              {(keys.data?.grantable ?? []).map((p) => (
                <label key={p} className="flex items-center gap-1.5 text-sm text-ink-2">
                  <input
                    type="checkbox"
                    checked={perms.includes(p)}
                    onChange={(e) => setPerms((cur) => (e.target.checked ? [...cur, p] : cur.filter((x) => x !== p)))}
                    className="accent-accent"
                  />
                  {LABEL[p] ?? humanize(p)}
                </label>
              ))}
            </div>
          </fieldset>
          <Button type="submit" variant="primary" disabled={!name.trim() || !perms.length || create.isPending} data-testid="key-create">
            <KeyRound size={15} aria-hidden /> Create key
          </Button>
        </form>

        {create.error && (
          <div className="mt-4">
            <ErrorState error={create.error} />
          </div>
        )}
        {create.data && (
          <div role="status" className="mt-5 rounded-panel border border-signal/40 bg-signal-soft p-4" data-testid="key-created">
            <p className="flex items-center gap-2 text-sm font-medium text-ink">
              <TriangleAlert size={15} className="text-signal" aria-hidden /> Copy this key now. It is shown once and cannot be recovered.
            </p>
            <div className="mt-3 flex items-center gap-2">
              <code className="code min-w-0 flex-1 truncate rounded-control border border-line bg-surface px-3 py-2 text-xs text-ink">{create.data.key}</code>
              <CopyButton text={create.data.key} />
            </div>
          </div>
        )}

        <div className="mt-6">
          {keys.isPending ? (
            <Skeleton className="h-24 w-full" />
          ) : keys.error ? (
            <ErrorState error={keys.error} />
          ) : keys.data.keys.length === 0 ? (
            <p className="text-sm text-ink-3">No keys yet.</p>
          ) : (
            <ul className="divide-y divide-line rounded-panel border border-line" data-testid="key-list">
              {keys.data.keys.map((k) => (
                <li key={k.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3">
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-ink">{k.name}</span>
                    <span className="block text-xs text-ink-3">
                      <span className="code">lmk_{k.id}_…</span> · {k.permissions.map((p) => LABEL[p] ?? p).join(", ")} ·{" "}
                      {k.warehouses === "all" ? "all warehouses" : `warehouses ${k.warehouses.join(", ")}`}
                    </span>
                    <span className="block text-caption text-ink-3">
                      Created {formatTimestamp(k.created_at)} · last used {k.last_used_at ? formatTimestamp(k.last_used_at) : "never"}
                    </span>
                  </span>
                  {k.revoked ? (
                    <Badge>Revoked</Badge>
                  ) : (
                    <Button size="sm" variant="ghost" onClick={() => revoke.mutate(k.id)} disabled={revoke.isPending}>
                      <Trash2 size={13} aria-hidden /> Revoke
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </Panel>

      <AlertsPanel />

      <Panel
        title="Connect an AI assistant (MCP)"
        subtitle="Claude, ChatGPT, Microsoft Copilot, Gemini or any MCP client can ask Lumiant inventory questions with a key. The assistant picks a tool; Lumiant runs the validated query and returns exact figures with their sources."
      >
        <div className="space-y-4 text-sm text-ink-2">
          <ol className="list-decimal space-y-1 pl-5">
            <li>Create a key above with the rights the assistant should have (for example Dashboards, Inventory and Analyst).</li>
            <li>Add Lumiant as a remote MCP server in the assistant, with this address and the key as a bearer token.</li>
            <li>Ask a question; every answer is audited under the key&apos;s name.</li>
          </ol>
          <div className="relative rounded-panel border border-line bg-surface-2">
            <div className="absolute top-2 right-2">
              <CopyButton text={mcpConfig} />
            </div>
            <pre className="code overflow-auto p-4 text-xs text-ink-2" tabIndex={0} aria-label="MCP client configuration">
              {mcpConfig}
            </pre>
          </div>
          <p className="flex items-center gap-2 text-xs text-ink-3">
            <Bot size={13} aria-hidden /> Tools offered: every analysis the key may run, plus <span className="code">ask_lumiant</span> for plain-language questions.
          </p>
        </div>
      </Panel>
    </div>
  );
}
