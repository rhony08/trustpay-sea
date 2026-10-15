"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import {
  ApiError,
  DISPUTE_REASONS,
  PROOF_TYPES,
  claimEntity,
  getToken,
  login,
  setOwnerResponse,
  setToken,
  signup,
  startMicroDeposit,
  submitDispute,
  verifyMicroDeposit,
  type DisputeView,
} from "@/lib/api";

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-100";

function ClaimInner() {
  const search = useSearchParams();
  const entityId = search.get("entity") ?? "";

  const [token, setTokenState] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"signup" | "login">("signup");
  const [error, setError] = useState<string | null>(null);

  const [proofType, setProofType] = useState(PROOF_TYPES[0].value);
  const [docUrl, setDocUrl] = useState("s3://proofs/passbook.jpg");
  const [reference, setReference] = useState("");
  const [dispute, setDispute] = useState<DisputeView | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [reason, setReason] = useState(DISPUTE_REASONS[0].value);
  const [justification, setJustification] = useState("");
  const [response, setResponse] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => setTokenState(getToken()), []);

  async function authenticate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const t = mode === "login" ? await login(email, password) : await signup(email, password);
      setTokenState(t);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Authentication failed");
    }
  }

  if (!token) {
    return (
      <main className="flex-1 py-12">
        <div className="mx-auto flex max-w-md flex-col gap-4 px-6">
          <h1 className="text-2xl font-bold text-slate-900">Merchant Shield — sign in</h1>
          <form className="flex flex-col gap-3" onSubmit={authenticate}>
            <input className={inputCls} type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <input className={inputCls} type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
            <button className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white">
              {mode === "signup" ? "Create account" : "Sign in"}
            </button>
          </form>
          {error && <p className="text-sm text-rose-600">{error}</p>}
          <button className="text-sm text-slate-500 underline" onClick={() => setMode(mode === "signup" ? "login" : "signup")}>
            {mode === "signup" ? "Have an account? Sign in" : "Need an account? Sign up"}
          </button>
        </div>
      </main>
    );
  }

  const verified = dispute?.claim_stage === "UNDER_REVIEW";

  return (
    <main className="flex-1 py-10">
      <div className="mx-auto max-w-3xl px-4 sm:px-6">
        <div className="mx-auto mb-8 max-w-2xl text-center">
          <span className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-100 px-3 py-1 text-xs font-bold text-blue-800">
            🛡️ Protecting legitimate merchants from extortion and smears
          </span>
          <h1 className="text-2xl font-extrabold text-slate-900 sm:text-3xl">
            Merchant Shield: name-clearing &amp; dispute portal
          </h1>
          <p className="mt-2 text-xs leading-relaxed text-slate-600 sm:text-sm">
            Your business reputation should never be damaged by bad-faith competitor reviews or false
            accusations. Submit verified KYC ownership to activate an immediate{" "}
            <b>Safe-Harbor Score Freeze</b>.
          </p>
        </div>

        <div className="mb-8 rounded-2xl border border-blue-200 bg-blue-50/70 p-5 shadow-xs">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wide text-blue-900">
              ⚖ Statutory safe-harbor protection mechanism (ADR-004 &amp; ADR-014)
            </h3>
            <span className="rounded bg-blue-200 px-2 py-0.5 text-[10px] font-bold text-blue-900">
              Anti-extortion protocol
            </span>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 text-xs text-slate-700 sm:grid-cols-3">
            <div className="rounded-xl border border-blue-100 bg-white p-3.5 shadow-xs">
              <b className="mb-1 block text-slate-900">1. Mandatory proof of identity</b>
              Business registration (NIB/SSM/ACRA) or official banking KYC is strictly required.
            </div>
            <div className="rounded-xl border border-blue-100 bg-white p-3.5 shadow-xs">
              <b className="mb-1 block text-blue-700">2. Instant safe-harbor freeze</b>
              Upon submission, risk-score penalties are capped at <b>45 / 100 max</b>.
            </div>
            <div className="rounded-xl border border-blue-100 bg-white p-3.5 shadow-xs">
              <b className="mb-1 block text-slate-900">3. Dual-control adjudication</b>
              Analysts audit refund slips and evidence; bad-faith smears are expunged.
            </div>
          </div>
        </div>

        {!entityId && (
          <p className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Open this from an account profile (&ldquo;Are you the owner?&rdquo;) — missing entity id.
          </p>
        )}
        {message && (
          <p className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            {message}
          </p>
        )}

        <div className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs sm:p-8">
          <section className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
              1. Prove you are the legitimate owner (KYC)
            </h3>
            <div>
              <Label>Verification tier</Label>
              <select className={inputCls} value={proofType} onChange={(e) => setProofType(e.target.value)}>
                {PROOF_TYPES.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            {proofType !== "MICRO_DEPOSIT_OTP" && (
              <div>
                <Label>Proof document reference / URL</Label>
                <input className={inputCls} value={docUrl} onChange={(e) => setDocUrl(e.target.value)} />
              </div>
            )}
            {proofType === "MERCHANT_PORTAL_NMID" && (
              <div>
                <Label>NMID from your merchant portal</Label>
                <input className={inputCls} value={reference} onChange={(e) => setReference(e.target.value)} />
              </div>
            )}
            <button
              disabled={!entityId}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              onClick={async () => {
                const d = await claimEntity(token, entityId, {
                  proof_type: proofType,
                  proof_document_url: proofType === "MICRO_DEPOSIT_OTP" ? "pending" : docUrl,
                  declared_reference: reference || undefined,
                });
                setDispute(d);
                setMessage(d.note ?? `Claim stage: ${d.claim_stage}`);
              }}
            >
              Submit ownership claim
            </button>

            {proofType === "MICRO_DEPOSIT_OTP" && (
              <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
                <button
                  className="rounded-lg bg-slate-800 px-4 py-2 text-sm text-white"
                  onClick={async () => {
                    const r = await startMicroDeposit(token, entityId);
                    setDevCode(r.dev_code ?? "(sent)");
                    setMessage(r.note);
                  }}
                >
                  Send micro-deposit
                </button>
                {devCode && <p className="text-xs text-amber-600">Dev code: {devCode}</p>}
                {devCode && (
                  <>
                    <input className={inputCls} placeholder="Reference code" value={code} onChange={(e) => setCode(e.target.value)} />
                    <button
                      className="rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-white"
                      onClick={async () => {
                        const d = await verifyMicroDeposit(token, entityId, code);
                        setDispute(d);
                        setMessage(`Claim stage: ${d.claim_stage}`);
                      }}
                    >
                      Verify micro-deposit
                    </button>
                  </>
                )}
              </div>
            )}
          </section>

          {verified && (
            <>
              <section className="space-y-3 border-t border-slate-100 pt-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                  2. Official clarification &amp; counter-evidence
                </h3>
                <div>
                  <Label>Dispute reason</Label>
                  <select className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)}>
                    {DISPUTE_REASONS.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <Label>Justification (why the reports are false or misjudged)</Label>
                  <textarea className={inputCls} rows={3} value={justification} onChange={(e) => setJustification(e.target.value)} />
                </div>
                <button
                  className="rounded-lg bg-amber-500 px-4 py-2 font-semibold text-white disabled:opacity-50"
                  disabled={justification.length < 10}
                  onClick={async () => {
                    const d = await submitDispute(token, entityId, { reason, justification });
                    setMessage(`Dispute ${d.status} — analysts will review under dual-control.`);
                  }}
                >
                  Submit dispute &amp; activate safe-harbor freeze
                </button>
              </section>

              <section className="space-y-3 border-t border-slate-100 pt-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                  3. Official response pinned to public profile
                </h3>
                <textarea
                  className={inputCls}
                  rows={3}
                  placeholder="This clarification will be pinned beneath contested reports…"
                  value={response}
                  onChange={(e) => setResponse(e.target.value)}
                />
                <button
                  className="rounded-lg bg-slate-800 px-4 py-2 text-sm text-white disabled:opacity-50"
                  disabled={!response}
                  onClick={async () => {
                    await setOwnerResponse(token, entityId, response);
                    setMessage("Response pinned to public profile.");
                  }}
                >
                  Publish pinned response
                </button>
              </section>
            </>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-slate-400">
          Need help? See the{" "}
          <Link href="/playbook" className="underline">
            scam playbooks
          </Link>{" "}
          or{" "}
          <Link href="/recovery" className="underline">
            emergency recovery guide
          </Link>
          .
        </p>
      </div>
    </main>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <label className="mb-1 block text-xs font-bold text-slate-700">{children}</label>;
}

export default function ClaimPage() {
  return (
    <Suspense fallback={null}>
      <ClaimInner />
    </Suspense>
  );
}
