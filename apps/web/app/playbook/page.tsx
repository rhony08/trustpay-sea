"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getPlaybooks, type PlaybookEntry } from "@/lib/api";

export default function PlaybookIndex() {
  const [entries, setEntries] = useState<PlaybookEntry[]>([]);

  useEffect(() => {
    void getPlaybooks()
      .then(setEntries)
      .catch(() => undefined);
  }, []);

  return (
    <main className="mx-auto flex max-w-2xl flex-1 flex-col gap-4 px-6 py-12">
      <h1 className="text-2xl font-bold text-slate-900">Scam Playbooks</h1>
      <p className="text-sm text-slate-500">
        Know the red flags and the checklist for each common scam type.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {entries.map((e) => (
          <Link
            key={e.category}
            href={`/playbook/${e.category}`}
            className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs transition-colors hover:border-blue-400"
          >
            <p className="font-semibold text-slate-900">{e.title}</p>
            <p className="mt-1 text-xs text-slate-500">{e.summary}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
