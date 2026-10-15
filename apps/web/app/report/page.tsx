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
import { RedactedSlipViewer } from "@/components/RedactedSlipViewer";

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-100";

const STATUS_STYLES: Record<string, string> = {
  PROCESSING: "border-amber-200 bg-amber-50 text-amber-800",
  PUBLISHED: "border-emerald-200 bg-emerald-50 text-emerald-800",
  FAILED: "border-rose-200 bg-rose-50 text-rose-800",
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

const STEPS = ["Recipient account", "Loss & timeline", "Proof & AI redaction", "Declaration"];

export default function ReportPage() {
  const [token, setTokenState] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authMode, setAuthMode] = useState<"login" | "signup">("signup");
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const [step, setStep] = useState(1);
  const [country, setCountry] = useState("ID");
  const [banks, setBanks] = useState<Bank[]>([]);
  const [bank, setBank] = useState("014");
  const [account, setAccount] = useState("");
  const [claimedName, setClaimedName] = useState("");
  const [category, setCategory] = useState(REPORT_CATEGORIES[0].value);
  const [severity, setSeverity] = useState(3);
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("IDR");
  const [incidentDate, setIncidentDate] = useState("");
  const [description, setDescription] = useState("");
  const [consent, setConsent] = useState(false);
  const [policeRef, setPoliceRef] = useState("");
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
    if (banks.length && !banks.some((b) => b.code === bank)) setBank(banks[0].code);
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

  async function poll(id: string) {
    for (let i = 0; i < 20; i += 1) {
      await new Promise((r) => setTimeout(r, 1500));
      const view = await getReport(id);
      setReportStatus(view.processing_status);
      setEvidenceUrl(view.evidence?.[0]?.media_url ?? null);
      if (view.processing_status !== "PROCESSING") return;
    }
  }

  async function submit() {
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
        currency,
        loss_amount: amount ? Number(amount) : null,
        incident_date: incidentDate || null,
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
      <main className="flex-1 py-12">
        <div className="mx-auto flex max-w-md flex-col gap-4 px-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Report a scam</h1>
            <p className="mt-1 text-sm text-slate-500">
              {authMode === "signup"
                ? "Create an account to submit a fraud report."
                : "Sign in to submit a fraud report."}
            </p>
          </div>
          <form className="flex flex-col gap-3" onSubmit={authenticate}>
            <input className={inputCls} type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <input className={inputCls} type="password" placeholder="Password (min 8 chars)" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
            <button type="submit" disabled={authBusy} className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-50">
              {authBusy ? "Please wait…" : authMode === "signup" ? "Create account" : "Sign in"}
            </button>
          </form>
          {authError && <p className="text-sm text-rose-600">{authError}</p>}
          <button className="text-sm text-slate-500 underline" onClick={() => setAuthMode(authMode === "signup" ? "login" : "signup")}>
            {authMode === "signup" ? "Already have an account? Sign in" : "Need an account? Sign up"}
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="flex-1 py-10">
      <div className="mx-auto max-w-2xl px-4 sm:px-6">
        <div className="mb-6 flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-900 sm:text-3xl">Report fraudulent account or scam</h1>
            <p className="mt-1 text-xs text-slate-600 sm:text-sm">
              Your verified report helps protect millions across Southeast Asia from payment scams.
            </p>
          </div>
          <button
            onClick={() => {
              setToken(null);
              setTokenState(null);
            }}
            className="text-sm text-slate-400 underline"
          >
            Sign out
          </button>
        </div>

        {!reportStatus && (
          <div className="mb-8 flex items-center justify-between border-b border-slate-200 pb-4 text-xs font-bold text-slate-500">
            {STEPS.map((label, i) => {
              const n = i + 1;
              const done = step > n;
              const active = step === n;
              return (
                <div key={label} className="flex flex-1 items-center gap-2">
                  <span
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                      active || done
                        ? "border border-blue-400 bg-blue-100 text-blue-800"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {n}
                  </span>
                  <span className={`hidden sm:inline ${active ? "text-blue-700" : ""}`}>{label}</span>
                  {n < STEPS.length && <span className="hidden h-0.5 flex-1 bg-slate-200 sm:block" />}
                </div>
              );
            })}
          </div>
        )}

        <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs sm:p-8">
          {reportStatus ? (
            <SuccessPanel status={reportStatus} reportId={reportId} evidenceUrl={evidenceUrl} />
          ) : step === 1 ? (
            <>
              <h2 className="text-base font-bold text-slate-900">Step 1: Which account received your funds?</h2>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <Label>Destination country</Label>
                  <select className={inputCls} value={country} onChange={(e) => setCountry(e.target.value)}>
                    {COUNTRIES.map((c) => (
                      <option key={c.code} value={c.code}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <Label>Bank / e-wallet entity</Label>
                  <select className={inputCls} value={bank} onChange={(e) => setBank(e.target.value)}>
                    {banks.map((b) => (
                      <option key={b.code} value={b.code}>
                        {b.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <Label>Destination account number or phone</Label>
                <input
                  className={`${inputCls} font-mono font-bold`}
                  value={account}
                  onChange={(e) => setAccount(e.target.value)}
                  placeholder="e.g. 8831924831"
                />
                <p className="mt-1 text-[11px] text-slate-500">
                  Must match the exact recipient account number on your bank transfer slip.
                </p>
              </div>
              <div>
                <Label>Seller / scammer claimed name or alias</Label>
                <input
                  className={inputCls}
                  value={claimedName}
                  onChange={(e) => setClaimedName(e.target.value)}
                  placeholder="e.g. 'Admin Siti' or 'Toko Jaya Mandiri'"
                />
                <p className="mt-1 text-[11px] text-slate-500">
                  Helps our Name-Matching Radar detect mule accounts when the real holder name differs.
                </p>
              </div>
              <div className="flex justify-end pt-2">
                <NextButton disabled={!account} onClick={() => setStep(2)}>
                  Continue to loss &amp; timeline &rarr;
                </NextButton>
              </div>
            </>
          ) : step === 2 ? (
            <>
              <h2 className="text-base font-bold text-slate-900">Step 2: Financial loss &amp; timeline</h2>
              <div>
                <Label>Scam modus operandi category</Label>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {REPORT_CATEGORIES.map((c) => (
                    <label
                      key={c.value}
                      className={`flex cursor-pointer items-center gap-2.5 rounded-xl border p-3 text-xs ${
                        category === c.value
                          ? "border-blue-400 bg-blue-50"
                          : "border-slate-200 bg-slate-50 hover:border-blue-300 hover:bg-white"
                      }`}
                    >
                      <input
                        type="radio"
                        name="cat"
                        className="accent-blue-600"
                        checked={category === c.value}
                        onChange={() => setCategory(c.value)}
                      />
                      <span>{c.label}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div>
                  <Label>Loss amount</Label>
                  <div className="flex">
                    <select
                      className="rounded-l-lg border border-r-0 border-slate-300 bg-slate-100 px-2 text-xs font-bold text-slate-600"
                      value={currency}
                      onChange={(e) => setCurrency(e.target.value)}
                    >
                      {["IDR", "MYR", "SGD", "THB", "VND", "PHP"].map((c) => (
                        <option key={c}>{c}</option>
                      ))}
                    </select>
                    <input
                      type="number"
                      className="flex-1 rounded-r-lg border border-slate-300 bg-slate-50 px-3 py-2 font-mono text-sm font-bold"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      placeholder="1500000"
                    />
                  </div>
                </div>
                <div>
                  <Label>Transaction date</Label>
                  <input type="date" className={inputCls} value={incidentDate} onChange={(e) => setIncidentDate(e.target.value)} />
                </div>
                <div>
                  <Label>Severity (1–5)</Label>
                  <select className={inputCls} value={severity} onChange={(e) => setSeverity(Number(e.target.value))}>
                    {[1, 2, 3, 4, 5].map((s) => (
                      <option key={s} value={s}>
                        Severity {s}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <Label>Incident narrative</Label>
                <textarea
                  rows={3}
                  className={inputCls}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe how the perpetrator approached you and what promises were made. Never share passwords, PINs or OTPs. (min 20 characters)"
                />
              </div>
              <div className="flex justify-between pt-2">
                <BackButton onClick={() => setStep(1)} />
                <NextButton disabled={description.length < 20} onClick={() => setStep(3)}>
                  Continue to transfer-slip proof &rarr;
                </NextButton>
              </div>
            </>
          ) : step === 3 ? (
            <>
              <div className="flex items-center justify-between">
                <h2 className="text-base font-bold text-slate-900">Step 3: Transfer slip &amp; asymmetric AI redaction</h2>
                <span className="rounded border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                  🔒 Fail-closed privacy
                </span>
              </div>
              <label className="block cursor-pointer rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-6 text-center hover:border-blue-500">
                <span className="mb-1 block text-3xl">🧾</span>
                <p className="text-sm font-bold text-slate-800">
                  {file ? file.name : "Click to select bank transfer slip or screenshot"}
                </p>
                <p className="mt-1 text-xs text-slate-500">Supports JPG, PNG, or PDF (max 10MB)</p>
                <input type="file" accept="image/*" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              </label>
              <div className="space-y-3 rounded-xl border border-blue-200 bg-blue-50/60 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wide text-blue-900">
                    How we protect your identity (asymmetric redaction standard):
                  </span>
                  <span className="rounded bg-blue-200 px-1.5 py-0.5 text-[10px] font-bold text-blue-900">ADR-016</span>
                </div>
                <p className="text-xs leading-relaxed text-slate-600">
                  Your sensitive personal information is automatically blurred before public display.
                  The destination scammer&rsquo;s bank account and verified holder name remain{" "}
                  <b>100% unredacted</b> so other citizens can identify the perpetrator.
                </p>
              </div>
              <RedactedSlipViewer allowAnalystView />
              <div className="flex justify-between pt-2">
                <BackButton onClick={() => setStep(2)} />
                <NextButton onClick={() => setStep(4)}>Continue to declaration &rarr;</NextButton>
              </div>
            </>
          ) : (
            <>
              <h2 className="text-base font-bold text-slate-900">Step 4: Statutory declaration &amp; submission</h2>
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs leading-relaxed text-slate-700">
                <label className="flex cursor-pointer items-start gap-2.5">
                  <input type="checkbox" className="mt-0.5 h-4 w-4 shrink-0 accent-blue-600" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                  <span>
                    <b>Statutory anti-perjury declaration:</b> I declare that this report is true and
                    accurately reflects an actual transaction in which I suffered financial harm. I
                    understand intentional false reports are subject to legal prosecution.
                  </span>
                </label>
              </div>
              <div>
                <Label>Official police report reference (optional)</Label>
                <input className={inputCls} value={policeRef} onChange={(e) => setPoliceRef(e.target.value)} placeholder="e.g. LP/B/921/X/2026/SPKT" />
              </div>
              {error && <p className="text-sm text-rose-600">{error}</p>}
              <div className="flex justify-between pt-2">
                <BackButton onClick={() => setStep(3)} />
                <button
                  disabled={busy || !consent}
                  onClick={() => void submit()}
                  className="rounded-xl bg-rose-600 px-6 py-2.5 text-sm font-bold text-white shadow-xs hover:bg-rose-700 disabled:opacity-50"
                >
                  {busy ? "Submitting…" : "Submit scam incident report"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </main>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <label className="mb-1 block text-xs font-bold text-slate-700">{children}</label>;
}

function NextButton({ children, onClick, disabled }: { children: React.ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-bold text-white shadow-xs transition-colors hover:bg-blue-700 disabled:opacity-50"
    >
      {children}
    </button>
  );
}

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button onClick={onClick} className="rounded-xl border border-slate-300 bg-slate-50 px-4 py-2 text-xs font-bold text-slate-700 hover:bg-slate-100">
      &larr; Back
    </button>
  );
}

function SuccessPanel({
  status,
  reportId,
  evidenceUrl,
}: {
  status: string;
  reportId: string | null;
  evidenceUrl: string | null;
}) {
  return (
    <div className="space-y-4 py-4 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-emerald-200 bg-emerald-100 text-2xl font-bold text-emerald-700">
        ✓
      </div>
      <h2 className="text-xl font-bold text-slate-900">
        {status === "PUBLISHED"
          ? "Scam incident report published"
          : status === "PROCESSING"
            ? "Report received — processing"
            : "Report submitted"}
      </h2>
      <p className="mx-auto max-w-md text-xs text-slate-600">
        {status === "PROCESSING"
          ? "Our AI is redacting evidence and running forensics — this usually takes a few seconds."
          : status === "PUBLISHED"
            ? "Published. Anyone who checks this account will now see your report."
            : "Evidence could not be safely redacted; a moderator will review it. The report is not published unredacted."}
      </p>
      <p className="text-xs text-slate-500">
        Report reference: <span className="font-mono font-bold text-slate-800">{reportId}</span>
      </p>
      <span className={`inline-block rounded-full border px-3 py-1 text-xs font-semibold ${STATUS_STYLES[status] ?? STATUS_STYLES.PROCESSING}`}>
        {status}
      </span>
      {status === "PUBLISHED" && evidenceUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={evidenceUrl} alt="Redacted evidence" className="mx-auto mt-3 max-h-64 rounded-lg border border-slate-200" />
      )}
      <div className="flex flex-wrap justify-center gap-3 pt-2">
        <Link href="/check" className="rounded-xl bg-blue-600 px-5 py-2 text-xs font-bold text-white shadow-xs hover:bg-blue-700">
          View risk verification result &rarr;
        </Link>
        <Link href="/recovery" className="rounded-xl border border-slate-200 bg-slate-100 px-5 py-2 text-xs font-bold text-slate-700 hover:bg-slate-200">
          Open bank freeze guide
        </Link>
      </div>
    </div>
  );
}
