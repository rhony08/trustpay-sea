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
import { ShieldMark } from "@/components/Brand";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useI18n } from "@/components/LocaleProvider";

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-100";
const btn = "rounded-lg px-3 py-1.5 text-sm font-semibold";

const CARDS: { key: keyof AdminDashboard; labelKey: string; accent?: boolean }[] = [
  { key: "pending_reports", labelKey: "admin.card.pendingReports" },
  { key: "open_disputes", labelKey: "admin.card.openDisputes" },
  { key: "pending_approvals", labelKey: "admin.card.pendingApprovals", accent: true },
  { key: "pending_flags", labelKey: "admin.card.pendingFlags" },
  { key: "processing_reports", labelKey: "admin.card.processingReports" },
];

type Tab = "overview" | "flags" | "disputes" | "approvals" | "tools";

export default function AdminPage() {
  const { t } = useI18n();

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

  const [bank, setBank] = useState("MBB");
  const [account, setAccount] = useState("");
  const [smResult, setSmResult] = useState<Record<string, unknown> | null>(null);
  const [apAction, setApAction] = useState("gov_override");
  const [apSubject, setApSubject] = useState("");
  const [apSource, setApSource] = useState("cekrekening.id");

  useEffect(() => setTokenState(getToken()), []);

  const guard = useCallback((e: unknown) => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) setDenied(true);
    else setMsg(e instanceof ApiError ? e.message : t("common.errorRequest"));
  }, [t]);

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
      setAuthError(err instanceof ApiError ? err.message : t("common.errorAuth"));
    }
  }

  if (!token) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-12">
        <div className="flex w-full max-w-md flex-col gap-4">
          <Link href="/" className="text-xs font-medium text-slate-500 hover:text-blue-600">
            {t("admin.back")}
          </Link>
          <h1 className="text-2xl font-bold text-slate-900">{t("admin.signInTitle")}</h1>
          <p className="text-sm text-slate-500">{t("admin.signInHint")}</p>
          <form className="flex flex-col gap-3" onSubmit={authenticate}>
            <input className={inputCls} type="email" placeholder={t("common.email")} value={email} onChange={(e) => setEmail(e.target.value)} required />
            <input className={inputCls} type="password" placeholder={t("common.password")} value={password} onChange={(e) => setPassword(e.target.value)} required />
            <button className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white">
              {mode === "login" ? t("common.signIn") : t("common.createAccount")}
            </button>
          </form>
          {authError && <p className="text-sm text-rose-600">{authError}</p>}
          <button className="text-sm text-slate-500 underline" onClick={() => setMode(mode === "login" ? "signup" : "login")}>
            {mode === "login" ? t("common.switchAuthLogin") : t("common.switchAuthSignup")}
          </button>
        </div>
      </main>
    );
  }

  const TABS: Tab[] = ["overview", "flags", "disputes", "approvals", "tools"];

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="sticky top-0 z-40 flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3 shadow-xs">
        <div className="flex items-center gap-4">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 text-white shadow-xs">
              <ShieldMark className="h-5 w-5" />
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-base font-bold text-slate-900">TrustPay</span>
              <span className="rounded border border-blue-200 bg-blue-100 px-1.5 py-0.5 text-[10px] font-bold text-blue-800">
                SEA
              </span>
            </span>
          </Link>
          <span className="hidden h-5 w-px bg-slate-200 sm:block" />
          <span className="hidden rounded-md border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-bold text-blue-800 sm:inline">
            {t("admin.portal")}
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs font-medium">
          {audit && (
            <span
              className={`hidden items-center gap-1.5 rounded-md border px-2.5 py-1 font-semibold sm:flex ${
                audit.chain_ok
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-rose-200 bg-rose-50 text-rose-700"
              }`}
            >
              <span className={`h-2 w-2 rounded-full ${audit.chain_ok ? "bg-emerald-600" : "bg-rose-600"}`} />
              {audit.chain_ok ? t("admin.auditValid") : t("admin.auditBroken")}
            </span>
          )}
          <LanguageSwitcher compact />
          <button
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1 font-bold text-slate-600 hover:bg-slate-100"
            onClick={() => {
              setToken(null);
              setTokenState(null);
            }}
          >
            {t("admin.exit")}
          </button>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 p-6">
        {denied && (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {t("admin.accessRequired")}
          </p>
        )}
        {msg && (
          <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">{msg}</p>
        )}

        {dashboard && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            {CARDS.map((c) => (
              <div
                key={c.key}
                className={`rounded-xl border p-3.5 shadow-xs ${
                  c.accent ? "border-rose-200 bg-rose-50" : "border-slate-200 bg-white"
                }`}
              >
                <span className={`text-[11px] font-bold uppercase ${c.accent ? "text-rose-800" : "text-slate-500"}`}>
                  {t(c.labelKey)}
                </span>
                <p className={`mt-0.5 text-2xl font-extrabold ${c.accent ? "text-rose-700" : "text-slate-900"}`}>
                  {dashboard[c.key]}
                </p>
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-2 text-sm font-bold">
          {TABS.map((tabKey) => (
            <button
              key={tabKey}
              onClick={() => {
                setTab(tabKey);
                setMsg(null);
              }}
              className={`${btn} ${tab === tabKey ? "bg-blue-600 text-white shadow-xs" : "text-slate-600 hover:text-slate-900"}`}
            >
              {t(`admin.tab.${tabKey}`)}
            </button>
          ))}
          <button className={`${btn} ml-auto bg-slate-800 text-white`} onClick={() => refresh(token)}>
            {t("admin.refresh")}
          </button>
        </div>

        {tab === "overview" && audit && (
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
            <div className="flex items-center justify-between">
              <p className="font-semibold text-slate-800">{t("admin.auditTitle")}</p>
              <span
                className={`rounded-full border px-3 py-1 text-xs ${
                  audit.chain_ok ? "border-emerald-200 text-emerald-700" : "border-rose-200 text-rose-700"
                }`}
              >
                {audit.chain_ok ? t("admin.chainIntactShort") : t("admin.chainBroken")}
              </span>
            </div>
            <ul className="mt-2 space-y-1 text-xs text-slate-600">
              {audit.entries.slice(0, 20).map((e) => (
                <li key={e.id} className="flex justify-between gap-4">
                  <span className="font-mono">{e.action}</span>
                  <span className="text-slate-400">{e.created_at}</span>
                </li>
              ))}
              {audit.entries.length === 0 && <li className="text-slate-400">{t("admin.noAudit")}</li>}
            </ul>
          </div>
        )}

        {tab === "flags" && (
          <div className="space-y-3">
            <InfoBanner>{t("admin.flagsInfo")}</InfoBanner>
            {flags.length === 0 && <Empty>{t("admin.noFlags")}</Empty>}
            {flags.map((f) => (
              <div key={f.id} className="space-y-2 rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="rounded border border-rose-200 bg-rose-50 px-2 py-0.5 text-xs font-bold text-rose-800">
                    {f.reason}
                  </span>
                  <span className="text-xs text-slate-400">{f.status}</span>
                </div>
                {f.entity && (
                  <p className="font-mono text-xs text-slate-600">
                    {f.entity.account_masked} · {f.entity.country}
                    {f.entity.institution ? ` · ${f.entity.institution}` : ""}
                  </p>
                )}
                {f.report && (
                  <p className="text-sm text-slate-700">
                    {t("admin.reportLine")} {f.report.category} ({t("admin.severityShort", { n: f.report.severity })}) — {f.report.description}
                  </p>
                )}
                {f.details && <p className="text-xs text-slate-500">{t("admin.flagDetail")} {f.details}</p>}
                <input
                  className={inputCls}
                  placeholder={t("admin.notes")}
                  value={notes[f.id] ?? ""}
                  onChange={(e) => setNotes({ ...notes, [f.id]: e.target.value })}
                />
                <div className="flex gap-2">
                  <button
                    className={`${btn} bg-rose-600 text-white`}
                    onClick={async () => {
                      await resolveFlag(token, f.id, "UPHELD", notes[f.id]);
                      await refresh(token);
                    }}
                  >
                    {t("admin.uphold")}
                  </button>
                  <button
                    className={`${btn} bg-slate-100 text-slate-700`}
                    onClick={async () => {
                      await resolveFlag(token, f.id, "DISMISSED", notes[f.id]);
                      await refresh(token);
                    }}
                  >
                    {t("admin.dismiss")}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === "disputes" && (
          <div className="space-y-3">
            <InfoBanner>{t("admin.disputesInfo")}</InfoBanner>
            {disputes.length === 0 && <Empty>{t("admin.noDisputes")}</Empty>}
            {disputes.map((d) => (
              <div key={d.id} className="space-y-2 rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-bold text-amber-800">
                    {d.dispute_reason ?? d.claim_stage}
                  </span>
                  <span className="text-xs text-slate-400">
                    {d.status} · {d.proof_type}
                  </span>
                </div>
                {d.entity && (
                  <p className="font-mono text-xs text-slate-600">
                    {d.entity.account_masked} · {d.entity.country}
                  </p>
                )}
                {d.justification && <p className="text-sm text-slate-700">{d.justification}</p>}
                {d.counter_evidence_urls && d.counter_evidence_urls.length > 0 && (
                  <p className="text-xs text-slate-500">{t("admin.evidence")} {d.counter_evidence_urls.join(", ")}</p>
                )}
                <input
                  className={inputCls}
                  placeholder={t("admin.decisionNotes")}
                  value={notes[d.id] ?? ""}
                  onChange={(e) => setNotes({ ...notes, [d.id]: e.target.value })}
                />
                <div className="flex flex-wrap gap-2">
                  <button
                    className={`${btn} bg-rose-600 text-white`}
                    onClick={async () => {
                      await resolveDispute(token, d.id, "APPROVED_REMOVED", notes[d.id]);
                      await refresh(token);
                    }}
                  >
                    {t("admin.approveRemoval")}
                  </button>
                  <button
                    className={`${btn} bg-slate-100 text-slate-700`}
                    onClick={async () => {
                      await resolveDispute(token, d.id, "REJECTED_UPHELD", notes[d.id]);
                      await refresh(token);
                    }}
                  >
                    {t("admin.rejectUphold")}
                  </button>
                  <button
                    className={`${btn} bg-emerald-600 text-white`}
                    onClick={async () => {
                      await resolveDispute(token, d.id, "SETTLEMENT", notes[d.id]);
                      await refresh(token);
                    }}
                  >
                    {t("admin.settlement")}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === "approvals" && (
          <div className="space-y-3">
            <InfoBanner>{t("admin.approvalsInfo")}</InfoBanner>

            <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
              <p className="text-sm font-semibold text-slate-800">{t("admin.requestAction")}</p>
              <div className="grid gap-2 sm:grid-cols-3">
                <select className={inputCls} value={apAction} onChange={(e) => setApAction(e.target.value)}>
                  <option value="gov_override">gov_override (force score 100)</option>
                  <option value="ban_user">ban_user</option>
                </select>
                <input className={inputCls} placeholder={t("admin.subjectId")} value={apSubject} onChange={(e) => setApSubject(e.target.value)} />
                {apAction === "gov_override" && (
                  <input className={inputCls} placeholder={t("admin.govSource")} value={apSource} onChange={(e) => setApSource(e.target.value)} />
                )}
              </div>
              <button
                className={`${btn} bg-blue-600 text-white`}
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
                {t("admin.requestApproval")}
              </button>
            </div>

            {approvals.length === 0 && <Empty>{t("admin.noApprovals")}</Empty>}
            {approvals.map((a) => (
              <div
                key={a.id}
                className="flex flex-col items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white p-5 shadow-xs sm:flex-row sm:items-center"
              >
                <div>
                  <span className="rounded border border-blue-200 bg-blue-50 px-2 py-0.5 text-xs font-bold text-blue-800">
                    {a.action}
                  </span>
                  <p className="mt-1 font-mono text-xs text-slate-500">
                    {a.subject_type}:{a.subject_id}
                  </p>
                  <p className="text-[11px] text-slate-400">
                    {t("admin.requestedBy", { who: a.requested_by.replace(/^.*\//, "") })}
                  </p>
                </div>
                <button
                  className={`${btn} bg-emerald-600 text-white`}
                  onClick={async () => {
                    await approveApproval(token, a.id);
                    await refresh(token);
                  }}
                >
                  {t("admin.approveExecute")}
                </button>
              </div>
            ))}
          </div>
        )}

        {tab === "tools" && (
          <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
            <p className="text-sm font-semibold text-slate-800">{t("admin.toolsTitle")}</p>
            <div className="flex flex-wrap gap-2">
              <input className={`${inputCls} sm:w-40`} placeholder={t("admin.bankCode")} value={bank} onChange={(e) => setBank(e.target.value)} />
              <input className={`${inputCls} sm:w-60`} placeholder={t("admin.accountPhone")} value={account} onChange={(e) => setAccount(e.target.value)} />
              <button
                className={`${btn} bg-blue-600 text-white`}
                onClick={async () => {
                  try {
                    setSmResult(await semakmuleCheck(token, bank, account));
                  } catch (e) {
                    guard(e);
                  }
                }}
              >
                {t("admin.check")}
              </button>
            </div>
            {smResult && (
              <pre className="mt-3 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs text-slate-200">
                {JSON.stringify(smResult, null, 2)}
              </pre>
            )}
          </div>
        )}
      </main>

      <footer className="mt-auto border-t border-slate-200 bg-slate-100 py-6 text-[11px] text-slate-500">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-6 sm:flex-row">
          <span className="flex items-center gap-2">
            <span className="font-bold text-slate-800">{t("admin.footerTitle")}</span>·
            <span>{t("admin.footerSub")}</span>
          </span>
          <span>{t("admin.footerCopy")}</span>
        </div>
      </footer>
    </div>
  );
}

function InfoBanner({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-xs leading-relaxed text-blue-900">
      {children}
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-slate-400">{children}</p>;
}
