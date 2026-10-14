"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  BANKS,
  COUNTRIES,
  REPORT_CATEGORIES,
  createReport,
  getReport,
  getToken,
  listBanks,
  login,
  setToken,
  signup,
  uploadEvidence,
  type Bank,
} from "@/lib/api";

const input =
  "w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 outline-none focus:border-emerald-400";

const STATUS_STYLES: Record<string, string> = {
  PROCESSING: "border-amber-500/40 bg-amber-500/10 text-amber-200",
  PUBLISHED: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
  FAILED: "border-rose-500/40 bg-rose-500/10 text-rose-200",
};

function fallbackBanks(country: string): Bank[] {
  return (BANKS[country] ?? []).map((b) => ({
    country,
    code: b.code,
    name: b.name,
    short_name: b.name,
    bank_type: "COMMERCIAL",
    bic: null,
    national_id: null,
  }));
}

export default function ReportPage() {
  const [token, setTokenState] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authMode, setAuthMode] = useState<"login" | "signup">("signup");
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const [country, setCountry] = useState("ID");
  const [banks, setBanks] = useState<Bank[]>([]);
  const [bank, setBank] = useState("014");
  const [account, setAccount] = useState("");
  const [category, setCategory] = useState(REPORT_CATEGORIES[0].value);
  const [severity, setSeverity] = useState(3);
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [consent, setConsent] = useState(false);
  const [file, setFile] = useState<File | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportId, setReportId] = useState<string | null>(null);
  const [reportStatus, setReportStatus] = useState<string | null>(null);
  const [evidenceUrl, setEvidenceUrl] = useState<string | null>(null);

  useEffect(() => setTokenState(getToken()), []);

  const loadBanks = useCallback(async (c: string) => {
    try {
      const rows = await listBanks(c);
      setBanks(rows.length ? rows : fallbackBanks(c));
    } catch {
      setBanks(fallbackBanks(c));
    }
  }, []);

  useEffect(() => {
    void loadBanks(country);
  }, [country, loadBanks]);

  useEffect(() => {
    if (banks.length && !banks.some((b) => b.code === bank)) {
      setBank(banks[0].code);
    }
  }, [banks, bank]);

  async function authenticate(e: React.FormEvent) {
    e.preventDefault();
    setAuthBusy(true);
    setAuthError(null);
    try {
      const t = authMode === "login" ? await login(email, password) : await signup(email, password);
      setTokenState(t);
    } catch (err) {
      setAuthError(err instanceof ApiError ? err.message : "Authentication failed");
    } finally {
      setAuthBusy(false);
    }
  }

  async function poll(reportId: string) {
    for (let i = 0; i < 20; i += 1) {
      await new Promise((r) => setTimeout(r, 1500));
      const view = await getReport(reportId);
      setReportStatus(view.processing_status);
      setEvidenceUrl(view.evidence?.[0]?.media_url ?? null);
      if (view.processing_status !== "PROCESSING") return;
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setBusy(true);
    setError(null);
    setReportStatus(null);
    setEvidenceUrl(null);
    try {
      const created = await createReport(token, {
        target: { kind: "ACCOUNT", country, bank, account },
        category,
        severity,
        description,
        currency: "IDR",
        loss_amount: amount ? Number(amount) : null,
        consent,
      });
      if (file) await uploadEvidence(token, created.report_id, file);
      setReportId(created.report_id);
      setReportStatus(created.processing_status);
      void poll(created.report_id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Submission failed");
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col gap-4 px-6 py-12">
        <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
          ← TrustPay SEA
        </Link>
        <h1 className="text-2xl font-bold">Report a scam</h1>
        <p className="text-sm text-slate-400">
          {authMode === "signup"
            ? "Create an account to submit a fraud report."
            : "Sign in to submit a fraud report."}
        </p>
        <form className="flex flex-col gap-3" onSubmit={authenticate}>
          <input
            className={input}
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            className={input}
            type="password"
            placeholder="Password (min 8 chars)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
          <button
            type="submit"
            disabled={authBusy}
            className="rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-950 disabled:opacity-50"
          >
            {authBusy ? "Please wait…" : authMode === "signup" ? "Create account" : "Sign in"}
          </button>
        </form>
        {authError && <p className="text-sm text-rose-300">{authError}</p>}
        <button
          className="text-sm text-slate-400 underline"
          onClick={() => setAuthMode(authMode === "signup" ? "login" : "signup")}
        >
          {authMode === "signup" ? "Already have an account? Sign in" : "Need an account? Sign up"}
        </button>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-4 px-6 py-12">
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
      <h1 className="text-2xl font-bold">Report a scam</h1>

      <form className="flex flex-col gap-3" onSubmit={submit}>
        <div className="grid grid-cols-2 gap-3">
          <select className={input} value={country} onChange={(e) => setCountry(e.target.value)}>
            {COUNTRIES.map((c) => (
              <option key={c.code} value={c.code}>
                {c.label}
              </option>
            ))}
          </select>
          <select className={input} value={bank} onChange={(e) => setBank(e.target.value)}>
            {banks.map((b) => (
              <option key={b.code} value={b.code}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
        <input
          className={input}
          placeholder="Recipient account number"
          value={account}
          onChange={(e) => setAccount(e.target.value)}
          required
        />
        <div className="grid grid-cols-2 gap-3">
          <select
            className={input}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            {REPORT_CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
          <select
            className={input}
            value={severity}
            onChange={(e) => setSeverity(Number(e.target.value))}
          >
            {[1, 2, 3, 4, 5].map((s) => (
              <option key={s} value={s}>
                Severity {s}
              </option>
            ))}
          </select>
        </div>
        <input
          className={input}
          placeholder="Loss amount (IDR, optional)"
          value={amount}
          onChange={(e) => setAmount(e.target.value.replace(/[^\d]/g, ""))}
          inputMode="numeric"
        />
        <textarea
          className={input}
          rows={4}
          placeholder="What happened? (min 20 characters)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          minLength={20}
          required
        />
        <label className="rounded-lg border border-dashed border-slate-700 px-4 py-3 text-center text-sm text-slate-400 hover:border-emerald-400">
          {file ? file.name : "Attach transfer slip / chat screenshot (optional)"}
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <label className="flex items-start gap-2 text-xs text-slate-400">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-0.5"
          />
          I confirm this report is truthful and consent to publishing redacted evidence. False
          reports may be removed and penalised.
        </label>
        <button
          type="submit"
          disabled={busy || !consent || description.length < 20}
          className="rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-950 disabled:opacity-50"
        >
          {busy ? "Submitting…" : "Submit report"}
        </button>
      </form>

      {error && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
          {error}
        </div>
      )}

      {reportStatus && (
        <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-5">
          <div className="flex items-center justify-between">
            <p className="font-semibold">Report status</p>
            <span
              className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                STATUS_STYLES[reportStatus] ?? STATUS_STYLES.PROCESSING
              }`}
            >
              {reportStatus}
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-400">
            {reportStatus === "PROCESSING"
              ? "Our AI is redacting evidence and running forensics — this usually takes a few seconds."
              : reportStatus === "PUBLISHED"
                ? "Published. Anyone who checks this account will now see your report."
                : "Evidence could not be safely redacted; a moderator will review it."}
          </p>
          <p className="mt-1 text-xs text-slate-500">Report ID: {reportId}</p>
          {reportStatus === "PUBLISHED" && evidenceUrl && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={evidenceUrl}
              alt="Redacted evidence"
              className="mt-3 max-h-64 rounded-lg border border-slate-700"
            />
          )}
        </div>
      )}
    </main>
  );
}
