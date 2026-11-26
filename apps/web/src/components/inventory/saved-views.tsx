"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button, IconButton } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/field";
import { api } from "@/lib/api";

type View = { id: string; name: string; query: string };

/** Saved views for a page: name the current filters and sort, reopen them later. Private to the user. */
export function SavedViews({ page, current, onOpen }: { page: string; current: string; onOpen: (query: string) => void }) {
  const qc = useQueryClient();
  const key = ["views", page];
  const views = useQuery({ queryKey: key, queryFn: () => api.get<{ views: View[] }>("/api/views", { page }) });
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState("");
  const save = useMutation({
    mutationFn: () => api.post<View>("/api/views", { page, name, query: current }),
    onSuccess: (v) => {
      setNaming(false);
      setName("");
      setSelected(v.id);
      void qc.invalidateQueries({ queryKey: key });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/api/views/${id}`),
    onSuccess: () => {
      setSelected("");
      void qc.invalidateQueries({ queryKey: key });
    },
  });
  const list = views.data?.views ?? [];

  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="saved-views">
      {list.length > 0 && (
        <Select
          size="sm"
          aria-label="Saved views"
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value);
            const v = list.find((x) => x.id === e.target.value);
            if (v) onOpen(v.query);
          }}
        >
          <option value="">Saved views…</option>
          {list.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
            </option>
          ))}
        </Select>
      )}
      {selected && (
        <IconButton aria-label="Delete this saved view" onClick={() => remove.mutate(selected)}>
          <Trash2 size={14} aria-hidden />
        </IconButton>
      )}
      {naming ? (
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) save.mutate();
          }}
        >
          <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="View name" aria-label="View name" className="w-44" />
          <Button size="sm" type="submit" variant="primary" disabled={!name.trim() || save.isPending}>
            Save
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setNaming(false)}>
            Cancel
          </Button>
        </form>
      ) : (
        <Button size="sm" onClick={() => setNaming(true)}>
          <Bookmark size={14} aria-hidden /> Save view
        </Button>
      )}
    </div>
  );
}
