"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  approveApproval,
  createApproval,
  getAdminApprovals,
  getAdminAudit,
  getAdminDashboard,
  getAdminDisputes,
  getAdminFlags,
  getToken,
  login,
  resolveDispute,
  resolveFlag,
  semakmuleCheck,
  setToken,
  signup,
  type AdminApproval,
  type AdminDashboard,
  type AdminDispute,
  type AdminFlag,
} from "@/lib/api";

const input =
  "w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 outline-none focus:border-emerald-400";
const btn = "rounded-lg px-3 py-1.5 text-sm font-medium";
const CARDS: { key: keyof AdminDashboard; label: string }[] = [
  { key: "pending_reports", label: "Reports awaiting review" },
  { key: "processing_reports", label: "Reports processing" },
  { key: "pending_flags", label: "Flags pending" },
  { key: "open_disputes", label: "Open disputes" },
  { key: "pending_approvals", label: "Approvals pending" },
];

type Tab = "overview" | "flags" | "disputes" | "approvals" | "tools";

export default function AdminPage() {
  const [token, setTokenState] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"signup" | "login">("login");
  const [authError, setAuthError] = useState<string | null>(null);
  const [denied, setDenied] = useState(false);

  const [tab, setTab] = useState<Tab>("overview");
  const [dashboard, setDashboard] = useState<AdminDashboard | null>(null);
  const [audit, setAudit] = useState<{ chain_ok: boolean; entries: { id: number; action: string; created_at: string | null }[] } | null>(null);
  const [flags, setFlags] = useState<AdminFlag[]>([]);
  const [disputes, setDisputes] = useState<AdminDispute[]>([]);
  const [approvals, setApprovals] = useState<AdminApproval[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);

  // tools
  const [bank, setBank] = useState("MBB");
  const [account, setAccount] = useState("");
  const [smResult, setSmResult] = useState<Record<string, unknown> | null>(null);
  // approvals form
  const [apAction, setApAction] = useState("gov_override");
  const [apSubject, setApSubject] = useState("");
  const [apSource, setApSource] = useState("cekrekening.id");

  useEffect(() => setTokenState(getToken()), []);

  const guard = useCallback((e: unknown) => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) setDenied(true);
    else setMsg(e instanceof ApiError ? e.message : "Request failed");
  }, []);

  const refresh = useCallback(
    async (t: string) => {
      try {
        setDashboard(await getAdminDashboard(t));
        if (tab === "overview") setAudit(await getAdminAudit(t));
        if (tab === "flags") setFlags(await getAdminFlags(t));
        if (tab === "disputes") setDisputes(await getAdminDisputes(t));
        if (tab === "approvals") setApprovals(await getAdminApprovals(t));
        setDenied(false);
      } catch (e) {
        guard(e);
      }
    },
    [tab, guard],
  );

  useEffect(() => {
    if (token) void refresh(token);
  }, [token, refresh]);

  async function authenticate(e: React.FormEvent) {
    e.preventDefault();
    setAuthError(null);
    try {
      const t = mode === "login" ? await login(email, password) : await signup(email, password);
      setTokenState(t);
    } catch (err) {
      setAuthError(err instanceof ApiError ? err.message : "Authentication failed");
    }
  }

  if (!token) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col gap-4 px-6 py-12">
        <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
          ← TrustPay SEA
        </Link>
        <h1 className="text-2xl font-bold">Admin sign-in</h1>
        <p className="text-sm text-slate-400">Use an ANALYST account (e.g. analyst@trustpay.dev).</p>
        <form className="flex flex-col gap-3" onSubmit={authenticate}>
          <input className={input} type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <input className={input} type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          <button className={`${btn} bg-emerald-500 text-slate-950`}>
            {mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
        {authError && <p className="text-sm text-rose-300">{authError}</p>}
        <button className="text-sm text-slate-400 underline" onClick={() => setMode(mode === "login" ? "signup" : "login")}>
          {mode === "login" ? "Need an account? Sign up" : "Have an account? Sign in"}
        </button>
      </main>
    );
  }

  const TABS: Tab[] = ["overview", "flags", "disputes", "approvals", "tools"];

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-4 px-6 py-10">
      <div className="flex items-center justify-between">
        <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
          ← TrustPay SEA
        </Link>
        <button
          className="text-sm text-slate-400 underline"
          onClick={() => {
            setToken(null);
            setTokenState(null);
          }}
        >
          Sign out
        </button>
      </div>
      <h1 className="text-2xl font-bold">Admin portal</h1>

      {denied && <p className="text-sm text-rose-300">Admin access required (ANALYST+).</p>}
      {msg && <p className="text-sm text-amber-300">{msg}</p>}

      <div className="flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => {
              setTab(t);
              setMsg(null);
            }}
            className={`${btn} ${tab === t ? "bg-emerald-500 text-slate-950" : "bg-slate-800 text-slate-300"}`}
          >
            {t}
          </button>
        ))}
        <button className={`${btn} ml-auto bg-slate-800 text-slate-300`} onClick={() => refresh(token)}>
          Refresh
        </button>
      </div>

      {dashboard && tab === "overview" && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            {CARDS.map((c) => (
              <div key={c.key} className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
                <p className="text-xs text-slate-400">{c.label}</p>
                <p className="text-2xl font-bold">{dashboard[c.key]}</p>
              </div>
            ))}
          </div>
          {audit && (
            <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
              <div className="flex items-center justify-between">
                <p className="font-semibold">Audit log</p>
                <span className={`rounded-full border px-3 py-1 text-xs ${audit.chain_ok ? "border-emerald-500/40 text-emerald-300" : "border-rose-500/40 text-rose-300"}`}>
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
        </>
      )}

      {tab === "flags" && (
        <div className="space-y-3">
          {flags.length === 0 && <p className="text-sm text-slate-400">No pending flags.</p>}
          {flags.map((f) => (
            <div key={f.id} className="rounded-xl border border-slate-700 bg-slate-900/60 p-4 text-sm">
              <div className="flex justify-between">
                <span className="font-semibold text-slate-100">{f.reason}</span>
                <span className="text-xs text-slate-500">{f.status}</span>
              </div>
              {f.entity && <p className="mt-1 font-mono text-xs text-slate-300">{f.entity.account_masked} · {f.entity.country}{f.entity.institution ? ` · ${f.entity.institution}` : ""}</p>}
              {f.report && <p className="mt-1 text-slate-300">Report: {f.report.category} (sev {f.report.severity}) — {f.report.description}</p>}
              {f.details && <p className="mt-1 text-xs text-slate-400">Flag detail: {f.details}</p>}
              <input className={`${input} mt-2`} placeholder="Resolution notes (optional)" value={notes[f.id] ?? ""} onChange={(e) => setNotes({ ...notes, [f.id]: e.target.value })} />
              <div className="mt-2 flex gap-2">
                <button className={`${btn} bg-rose-500 text-slate-950`} onClick={async () => { await resolveFlag(token, f.id, "UPHELD", notes[f.id]); await refresh(token); }}>
                  Uphold (hide review)
                </button>
                <button className={`${btn} bg-slate-700 text-slate-100`} onClick={async () => { await resolveFlag(token, f.id, "DISMISSED", notes[f.id]); await refresh(token); }}>
                  Dismiss
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "disputes" && (
        <div className="space-y-3">
          {disputes.length === 0 && <p className="text-sm text-slate-400">No open disputes.</p>}
          {disputes.map((d) => (
            <div key={d.id} className="rounded-xl border border-slate-700 bg-slate-900/60 p-4 text-sm">
              <div className="flex justify-between">
                <span className="font-semibold text-slate-100">{d.dispute_reason ?? d.claim_stage}</span>
                <span className="text-xs text-slate-500">{d.status} · {d.proof_type}</span>
              </div>
              {d.entity && <p className="mt-1 font-mono text-xs text-slate-300">{d.entity.account_masked} · {d.entity.country}</p>}
              {d.justification && <p className="mt-1 text-slate-300">{d.justification}</p>}
              <input className={`${input} mt-2`} placeholder="Decision notes (optional)" value={notes[d.id] ?? ""} onChange={(e) => setNotes({ ...notes, [d.id]: e.target.value })} />
              <div className="mt-2 flex flex-wrap gap-2">
                <button className={`${btn} bg-rose-500 text-slate-950`} onClick={async () => { await resolveDispute(token, d.id, "APPROVED_REMOVED", notes[d.id]); await refresh(token); }}>
                  Approve removal
                </button>
                <button className={`${btn} bg-slate-700 text-slate-100`} onClick={async () => { await resolveDispute(token, d.id, "REJECTED_UPHELD", notes[d.id]); await refresh(token); }}>
                  Reject (uphold)
                </button>
                <button className={`${btn} bg-emerald-600 text-slate-950`} onClick={async () => { await resolveDispute(token, d.id, "SETTLEMENT", notes[d.id]); await refresh(token); }}>
                  Settlement
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "approvals" && (
        <div className="space-y-3">
          <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-4 text-sm">
            <p className="font-semibold">Request a destructive action (four-eyes)</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              <select className={input} value={apAction} onChange={(e) => setApAction(e.target.value)}>
                <option value="gov_override">gov_override (force score 100)</option>
                <option value="ban_user">ban_user</option>
              </select>
              <input className={input} placeholder="subject id (entity/user UUID)" value={apSubject} onChange={(e) => setApSubject(e.target.value)} />
              {apAction === "gov_override" && <input className={input} placeholder="gov source" value={apSource} onChange={(e) => setApSource(e.target.value)} />}
            </div>
            <button
              className={`${btn} mt-2 bg-emerald-500 text-slate-950`}
              onClick={async () => {
                await createApproval(token, {
                  action: apAction,
                  subject_type: apAction === "ban_user" ? "user" : "payment_entity",
                  subject_id: apSubject,
                  payload: apAction === "gov_override" ? { source: apSource } : {},
                });
                await refresh(token);
              }}
            >
              Request approval
            </button>
          </div>
          {approvals.length === 0 && <p className="text-sm text-slate-400">No pending approvals.</p>}
          {approvals.map((a) => (
            <div key={a.id} className="flex items-center justify-between rounded-xl border border-slate-700 bg-slate-900/60 p-4 text-sm">
              <div>
                <p className="font-semibold">{a.action}</p>
                <p className="font-mono text-xs text-slate-400">{a.subject_type}:{a.subject_id}</p>
              </div>
              <button className={`${btn} bg-amber-500 text-slate-950`} onClick={async () => { await approveApproval(token, a.id); await refresh(token); }}>
                Approve (2nd admin)
              </button>
            </div>
          ))}
        </div>
      )}

      {tab === "tools" && (
        <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-4 text-sm">
          <p className="font-semibold">PDRM Semak Mule check (Malaysia)</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <input className={`${input} sm:w-40`} placeholder="Bank code (MBB)" value={bank} onChange={(e) => setBank(e.target.value)} />
            <input className={`${input} sm:w-60`} placeholder="Account / phone" value={account} onChange={(e) => setAccount(e.target.value)} />
            <button
              className={`${btn} bg-emerald-500 text-slate-950`}
              onClick={async () => {
                try {
                  setSmResult(await semakmuleCheck(token, bank, account));
                } catch (e) {
                  guard(e);
                }
              }}
            >
              Check
            </button>
          </div>
          {smResult && (
            <pre className="mt-3 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-300">
              {JSON.stringify(smResult, null, 2)}
            </pre>
          )}
        </div>
      )}
    </main>
  );
}
