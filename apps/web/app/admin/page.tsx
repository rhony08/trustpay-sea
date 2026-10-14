"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  getAdminAudit,
  getAdminDashboard,
  getToken,
  type AdminDashboard,
} from "@/lib/api";

const CARDS: { key: keyof AdminDashboard; label: string }[] = [
  { key: "pending_reports", label: "Reports awaiting review" },
  { key: "processing_reports", label: "Reports processing" },
  { key: "pending_flags", label: "Flags pending" },
  { key: "open_disputes", label: "Open disputes" },
  { key: "pending_approvals", label: "Approvals pending" },
];

export default function AdminPage() {
  const token = typeof window !== "undefined" ? getToken() : null;
  const [dashboard, setDashboard] = useState<AdminDashboard | null>(null);
  const [audit, setAudit] = useState<{ chain_ok: boolean; entries: { id: number; action: string; created_at: string | null }[] } | null>(null);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    if (!token) return;
    void getAdminDashboard(token)
      .then(setDashboard)
      .catch(() => setDenied(true));
    void getAdminAudit(token).then(setAudit).catch(() => undefined);
  }, [token]);

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-4 px-6 py-12">
      <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
        ← TrustPay SEA
      </Link>
      <h1 className="text-2xl font-bold">Admin</h1>

      {!token && <p className="text-sm text-slate-400">Sign in as an analyst to use the admin portal.</p>}
      {denied && <p className="text-sm text-rose-300">Admin access required.</p>}

      {dashboard && (
        <div className="grid grid-cols-2 gap-3">
          {CARDS.map((c) => (
            <div key={c.key} className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
              <p className="text-xs text-slate-400">{c.label}</p>
              <p className="text-2xl font-bold">{dashboard[c.key]}</p>
            </div>
          ))}
        </div>
      )}

      {audit && (
        <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <p className="font-semibold">Audit log</p>
            <span
              className={`rounded-full border px-3 py-1 text-xs ${
                audit.chain_ok
                  ? "border-emerald-500/40 text-emerald-300"
                  : "border-rose-500/40 text-rose-300"
              }`}
            >
              {audit.chain_ok ? "chain intact" : "chain broken"}
            </span>
          </div>
          <ul className="mt-2 space-y-1 text-xs text-slate-300">
            {audit.entries.slice(0, 20).map((e) => (
              <li key={e.id} className="flex justify-between gap-4">
                <span className="font-mono">{e.action}</span>
                <span className="text-slate-500">{e.created_at}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </main>
  );
}
