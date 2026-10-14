"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getPlaybooks, type PlaybookEntry } from "@/lib/api";

export default function PlaybookIndex() {
  const [entries, setEntries] = useState<PlaybookEntry[]>([]);

  useEffect(() => {
    void getPlaybooks().then(setEntries).catch(() => undefined);
  }, []);

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-4 px-6 py-12">
      <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
        ← TrustPay SEA
      </Link>
      <h1 className="text-2xl font-bold">Scam Playbooks</h1>
      <p className="text-sm text-slate-400">
        Know the red flags and the checklist for each common scam type.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {entries.map((e) => (
          <Link
            key={e.category}
            href={`/playbook/${e.category}`}
            className="rounded-xl border border-slate-700 bg-slate-900/60 p-4 hover:border-emerald-400"
          >
            <p className="font-semibold text-slate-100">{e.title}</p>
            <p className="mt-1 text-xs text-slate-400">{e.summary}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
