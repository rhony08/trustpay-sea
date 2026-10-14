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

const input =
  "w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 outline-none focus:border-emerald-400";

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
      <main className="mx-auto flex min-h-screen max-w-md flex-col gap-4 px-6 py-12">
        <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
          ← TrustPay SEA
        </Link>
        <h1 className="text-2xl font-bold">Claim an account</h1>
        <form className="flex flex-col gap-3" onSubmit={authenticate}>
          <input className={input} type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <input className={input} type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
          <button className="rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-950">
            {mode === "signup" ? "Create account" : "Sign in"}
          </button>
        </form>
        {error && <p className="text-sm text-rose-300">{error}</p>}
        <button className="text-sm text-slate-400 underline" onClick={() => setMode(mode === "signup" ? "login" : "signup")}>
          {mode === "signup" ? "Have an account? Sign in" : "Need an account? Sign up"}
        </button>
      </main>
    );
  }

  const verified = dispute?.claim_stage === "UNDER_REVIEW";

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-4 px-6 py-12">
      <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
        ← TrustPay SEA
      </Link>
      <h1 className="text-2xl font-bold">Claim &amp; dispute</h1>
      {!entityId && <p className="text-sm text-rose-300">Open this from an entity page (missing id).</p>}
      {message && <p className="text-sm text-emerald-300">{message}</p>}

      <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-5">
        <p className="font-semibold">Step 1 — prove ownership</p>
        <p className="mt-1 text-xs text-slate-400">
          We never ask for your OTP by link or email. Only start a claim from inside the app.
        </p>
        <div className="mt-3 flex flex-col gap-2">
          <select className={input} value={proofType} onChange={(e) => setProofType(e.target.value)}>
            {PROOF_TYPES.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
          {proofType !== "MICRO_DEPOSIT_OTP" && (
            <input className={input} placeholder="Proof document reference/URL" value={docUrl} onChange={(e) => setDocUrl(e.target.value)} />
          )}
          {proofType === "MERCHANT_PORTAL_NMID" && (
            <input className={input} placeholder="NMID from your merchant portal" value={reference} onChange={(e) => setReference(e.target.value)} />
          )}
          <button
            className="rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-950 disabled:opacity-50"
            disabled={!entityId}
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
            Submit claim
          </button>
          {proofType === "MICRO_DEPOSIT_OTP" && (
            <div className="flex flex-col gap-2">
              <button
                className="rounded-lg bg-slate-800 px-4 py-2 text-sm"
                onClick={async () => {
                  const r = await startMicroDeposit(token, entityId);
                  setDevCode(r.dev_code ?? "(sent)");
                  setMessage(r.note);
                }}
              >
                Send micro-deposit
              </button>
              {devCode && <p className="text-xs text-amber-300">Dev code: {devCode}</p>}
              {devCode && (
                <>
                  <input className={input} placeholder="Reference code" value={code} onChange={(e) => setCode(e.target.value)} />
                  <button
                    className="rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-950"
                    onClick={async () => {
                      const d = await verifyMicroDeposit(token, entityId, code);
                      setDispute(d);
                      setMessage(`Claim stage: ${d.claim_stage}`);
                    }}
                  >
                    Verify
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {verified && (
        <>
          <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-5">
            <p className="font-semibold text-amber-200">Step 2 — dispute a review</p>
            <div className="mt-3 flex flex-col gap-2">
              <select className={input} value={reason} onChange={(e) => setReason(e.target.value)}>
                {DISPUTE_REASONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
              <textarea className={input} rows={3} placeholder="Why is this review wrong?" value={justification} onChange={(e) => setJustification(e.target.value)} />
              <button
                className="rounded-lg bg-amber-500 px-4 py-2 font-semibold text-slate-950 disabled:opacity-50"
                disabled={justification.length < 10}
                onClick={async () => {
                  const d = await submitDispute(token, entityId, { reason, justification });
                  setMessage(`Dispute ${d.status} — admin will review.`);
                }}
              >
                Submit dispute
              </button>
            </div>
          </div>

          <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-5">
            <p className="font-semibold">Pin a public response</p>
            <textarea className={input} rows={3} placeholder="Your response will appear on the profile." value={response} onChange={(e) => setResponse(e.target.value)} />
            <button
              className="mt-2 rounded-lg bg-slate-800 px-4 py-2 text-sm disabled:opacity-50"
              disabled={!response}
              onClick={async () => {
                await setOwnerResponse(token, entityId, response);
                setMessage("Response pinned.");
              }}
            >
              Publish response
            </button>
          </div>
        </>
      )}
    </main>
  );
}

export default function ClaimPage() {
  return (
    <Suspense fallback={null}>
      <ClaimInner />
    </Suspense>
  );
}
