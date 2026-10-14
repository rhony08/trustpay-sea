"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { getReceipt, type Receipt } from "@/lib/api";

function WarningInner() {
  const search = useSearchParams();
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = search.get("token");
    if (!token) {
      setError("Missing receipt token");
      return;
    }
    void getReceipt(token).then(setReceipt).catch(() => setError("Invalid or tampered card"));
  }, [search]);

  const canonical =
    typeof window !== "undefined" && search.get("token")
      ? `${window.location.origin}/warning?token=${search.get("token")}`
      : "";

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-4 px-6 py-12">
      <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
        ← TrustPay SEA
      </Link>
      <h1 className="text-2xl font-bold">Warning card</h1>
      {error && <p className="text-sm text-rose-300">{error}</p>}
      {receipt && (
        <>
          <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-6 text-center">
            <p className="text-xs uppercase tracking-wide text-rose-300">Payment warning</p>
            <p className="mt-2 font-mono text-2xl text-rose-100">{receipt.account_masked}</p>
            <p className="mt-2 text-sm text-rose-200">
              Risk {receipt.risk_score} · {receipt.risk_level.replaceAll("_", " ")} · higher =
              riskier
            </p>
            <p className="mt-1 text-xs text-rose-300">
              {receipt.institution ?? receipt.entity_type} · {receipt.country}
            </p>
          </div>
          <a href={canonical} className="break-all text-xs text-slate-400 underline">
            {canonical}
          </a>
          <button
            className="rounded-lg bg-slate-800 px-4 py-2 text-sm"
            onClick={() => window.print()}
          >
            Print / share
          </button>
          <Link href="/check" className="text-sm text-slate-400 underline">
            Re-check live risk →
          </Link>
        </>
      )}
    </main>
  );
}

export default function WarningPage() {
  return (
    <Suspense fallback={null}>
      <WarningInner />
    </Suspense>
  );
}
