"use client";

import Link from "next/link";
import { useState } from "react";
import { checkDeal, type DealCheckResult } from "@/lib/api";

export default function DealCheckPage() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<DealCheckResult | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-4 px-6 py-12">
      <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
        ← TrustPay SEA
      </Link>
      <h1 className="text-2xl font-bold">Too good to be true?</h1>
      <p className="text-sm text-slate-400">
        Paste a deal, offer, or message and we&apos;ll flag common scam tactics.
      </p>
      <form
        className="flex flex-col gap-3"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            setResult(await checkDeal(text));
          } finally {
            setBusy(false);
          }
        }}
      >
        <textarea
          className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 outline-none focus:border-emerald-400"
          rows={4}
          placeholder="e.g. Guaranteed profit, deposit today and double your money!"
          value={text}
          onChange={(e) => setText(e.target.value)}
          required
        />
        <button
          disabled={busy}
          className="rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-950 disabled:opacity-50"
        >
          {busy ? "Checking…" : "Check the deal"}
        </button>
      </form>

      {result && (
        <div
          className={`rounded-xl border p-5 ${
            result.suspicious
              ? "border-rose-500/40 bg-rose-500/10 text-rose-100"
              : "border-emerald-500/40 bg-emerald-500/10 text-emerald-100"
          }`}
        >
          <p className="font-semibold">
            {result.suspicious ? "Red flags found" : "No obvious red flags"}
          </p>
          {result.suspicious && (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {result.tips.map((tip) => (
                <li key={tip}>{tip}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </main>
  );
}
