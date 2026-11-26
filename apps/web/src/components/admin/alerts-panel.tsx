"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, Send, Trash2, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { ErrorState, Panel, Skeleton } from "@/components/data/widget";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { api } from "@/lib/api";
import { formatTimestamp, humanize } from "@/lib/format";

type Rule = {
  id: string;
  name: string;
  url: string;
  min_severity: "info" | "warning" | "critical";
  created_by: string;
  created_at: string;
  last_sent_at: string | null;
  last_status: string | null;
};

/** Admin › Integrations: push findings to a webhook, signed so the receiver can verify them (V3). */
export function AlertsPanel() {
  const qc = useQueryClient();
  const rules = useQuery({ queryKey: ["alert-rules"], queryFn: () => api.get<{ rules: Rule[] }>("/api/admin/alerts") });
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [severity, setSeverity] = useState("warning");
  const refresh = () => void qc.invalidateQueries({ queryKey: ["alert-rules"] });
  const create = useMutation({
    mutationFn: () => api.post<{ secret: string; record: Rule }>("/api/admin/alerts", { name, url, min_severity: severity }),
    onSuccess: () => {
      setName("");
      setUrl("");
      refresh();
    },
  });
  const send = useMutation({ mutationFn: (id: string) => api.post<{ ok: boolean; status: string; findings: number }>(`/api/admin/alerts/${id}/send`), onSettled: refresh });
  const remove = useMutation({ mutationFn: (id: string) => api.delete(`/api/admin/alerts/${id}`), onSuccess: refresh });

  return (
    <Panel
      title="Alert rules"
      subtitle="Send findings at or above a severity to your ticketing, chat or workflow tool. Each delivery is signed (X-Lumiant-Signature, HMAC-SHA256) and computed with your warehouse scope."
    >
      <form
        className="grid gap-4 lg:grid-cols-[minmax(0,14rem)_minmax(0,1fr)_10rem_auto] lg:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim() && url.trim()) create.mutate();
        }}
      >
        <Field label="Rule name">
          <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="e.g. Expired lots to ops" />
        </Field>
        <Field label="Webhook address">
          <Input value={url} onChange={(e) => setUrl(e.target.value)} maxLength={500} placeholder="https://hooks.example.com/lumiant" spellCheck={false} />
        </Field>
        <Field label="Send from">
          <Select value={severity} onChange={(e) => setSeverity(e.target.value)}>
            <option value="critical">Critical only</option>
            <option value="warning">Watch and critical</option>
            <option value="info">Everything</option>
          </Select>
        </Field>
        <Button type="submit" variant="primary" disabled={!name.trim() || !url.trim() || create.isPending}>
          <BellRing size={15} aria-hidden /> Add rule
        </Button>
      </form>
      {create.error && (
        <div className="mt-4">
          <ErrorState error={create.error} />
        </div>
      )}
      {create.data && (
        <div role="status" className="mt-5 rounded-panel border border-signal/40 bg-signal-soft p-4 text-sm text-ink">
          <p className="flex items-center gap-2 font-medium">
            <TriangleAlert size={15} className="text-signal" aria-hidden /> Copy the signing secret now. It is shown once.
          </p>
          <code className="code mt-2 block truncate rounded-control border border-line bg-surface px-3 py-2 text-xs">{create.data.secret}</code>
        </div>
      )}
      <div className="mt-6">
        {rules.isPending ? (
          <Skeleton className="h-20 w-full" />
        ) : rules.error ? (
          <ErrorState error={rules.error} />
        ) : rules.data.rules.length === 0 ? (
          <p className="text-sm text-ink-3">No alert rules yet.</p>
        ) : (
          <ul className="divide-y divide-line rounded-panel border border-line">
            {rules.data.rules.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3">
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2 text-sm font-medium text-ink">
                    {r.name} <Badge tone={r.min_severity === "critical" ? "signal" : "neutral"}>{humanize(r.min_severity)}+</Badge>
                  </span>
                  <span className="code block truncate text-xs text-ink-3">{r.url}</span>
                  <span className="block text-caption text-ink-3">
                    {r.last_sent_at ? `Last sent ${formatTimestamp(r.last_sent_at)}: ${r.last_status}` : "Not sent yet"}
                  </span>
                </span>
                <Button size="sm" onClick={() => send.mutate(r.id)} disabled={send.isPending}>
                  <Send size={13} aria-hidden /> Send now
                </Button>
                <Button size="sm" variant="ghost" onClick={() => remove.mutate(r.id)} disabled={remove.isPending}>
                  <Trash2 size={13} aria-hidden /> Delete
                </Button>
              </li>
            ))}
          </ul>
        )}
        {send.data && (
          <p role="status" className="mt-3 text-sm text-ink-2">
            {send.data.ok ? "Delivered" : "Not delivered"}: {send.data.status}, {send.data.findings} finding{send.data.findings === 1 ? "" : "s"}.
          </p>
        )}
      </div>
    </Panel>
  );
}
