"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getPlaybook, type PlaybookEntry } from "@/lib/api";

export default function PlaybookDetail() {
  const params = useParams<{ category: string }>();
  const category = params?.category;
  const [entry, setEntry] = useState<PlaybookEntry | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!category) return;
    void getPlaybook(category)
      .then(setEntry)
      .catch(() => setNotFound(true));
  }, [category]);

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-4 px-6 py-12">
      <Link href="/playbook" className="text-sm text-slate-400 hover:text-slate-200">
        ← Scam Playbooks
      </Link>
      {notFound && <p className="text-rose-300">Unknown category.</p>}
      {entry && (
        <>
          <h1 className="text-2xl font-bold">{entry.title}</h1>
          <p className="text-slate-300">{entry.summary}</p>

          <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4">
            <p className="text-sm font-semibold text-rose-200">Red flags</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-rose-100">
              {entry.red_flags.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          </div>

          <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-4">
            <p className="text-sm font-semibold text-emerald-200">Before you pay</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-emerald-100">
              {entry.checklist.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>

          <Link
            href="/check"
            className="rounded-lg bg-emerald-500 px-4 py-2 text-center font-semibold text-slate-950"
          >
            Check an account now
          </Link>
        </>
      )}
    </main>
  );
}
