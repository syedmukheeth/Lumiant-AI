"use client";

import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Loader2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { api, ApiError } from "@/lib/api";

type Form = { name: string; email: string; company: string; role: string; systems: string; message: string; website: string; consent: boolean };
const EMPTY: Form = { name: "", email: "", company: "", role: "", systems: "", message: "", website: "", consent: false };

/** Demo request: stored by the API for a platform administrator to follow up. No tracking, no third party. */
export function DemoRequestForm() {
  const [form, setForm] = useState<Form>(EMPTY);
  const send = useMutation({
    mutationFn: (f: Form) =>
      api.post("/api/public/demo-requests", {
        name: f.name,
        email: f.email,
        company: f.company,
        role: f.role || null,
        systems: f.systems || null,
        message: f.message || null,
        website: f.website || null,
        consent: f.consent,
      }),
  });
  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value }));

  if (send.isSuccess) {
    return (
      <div className="flex flex-col items-start justify-center gap-3 rounded-panel border border-line bg-surface-2 p-6" role="status" data-testid="demo-request-sent">
        <CheckCircle2 className="size-6 text-ok" aria-hidden />
        <p className="text-title font-semibold text-ink">Thank you, we have your request.</p>
        <p className="text-sm text-ink-2">We will contact you at {form.email} to arrange the demo.</p>
      </div>
    );
  }

  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        send.mutate(form);
      }}
      aria-label="Request a demo"
    >
      <Field label="Name">
        <Input required maxLength={120} autoComplete="name" value={form.name} onChange={set("name")} />
      </Field>
      <Field label="Work email">
        <Input required type="email" maxLength={254} autoComplete="email" value={form.email} onChange={set("email")} />
      </Field>
      <Field label="Company">
        <Input required maxLength={160} autoComplete="organization" value={form.company} onChange={set("company")} />
      </Field>
      <Field label="Role (optional)">
        <Input maxLength={120} autoComplete="organization-title" value={form.role} onChange={set("role")} />
      </Field>
      <Field label="ERP or data warehouse (optional)" className="sm:col-span-2">
        <Input maxLength={200} placeholder="For example SAP S/4HANA, Odoo, Snowflake" value={form.systems} onChange={set("systems")} />
      </Field>
      <Field label="What would you like to see? (optional)" className="sm:col-span-2">
        <Textarea rows={3} maxLength={1000} value={form.message} onChange={set("message")} />
      </Field>
      {/* Hidden from people (and from assistive technology); simple bots fill it. */}
      <div aria-hidden className="absolute -left-[9999px] h-0 w-0 overflow-hidden">
        <label>
          Website
          <input tabIndex={-1} autoComplete="off" value={form.website} onChange={set("website")} />
        </label>
      </div>
      <label className="flex items-start gap-2.5 text-sm text-ink-2 sm:col-span-2">
        <input type="checkbox" required checked={form.consent} onChange={set("consent")} className="mt-0.5 size-4 accent-[var(--accent)]" />
        <span>I agree that Lumiant may contact me about this demo request.</span>
      </label>
      <div className="flex items-center gap-3 sm:col-span-2">
        <Button type="submit" variant="primary" size="lg" disabled={send.isPending}>
          {send.isPending && <Loader2 className="size-4 animate-spin" aria-hidden />}
          Request a demo
        </Button>
        {send.error && (
          <p className="text-sm text-signal" role="alert">
            {send.error instanceof ApiError ? send.error.message : "Could not send the request. Please try again."}
          </p>
        )}
      </div>
    </form>
  );
}
