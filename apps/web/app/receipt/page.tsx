"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { BANKS, COUNTRIES, createReceipt, getReceipt, type Receipt } from "@/lib/api";

const input =
  "w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 outline-none focus:border-emerald-400";

function ReceiptView({ receipt }: { receipt: Receipt }) {
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
        Diligence Receipt
      </p>
      <p className="mt-2 font-mono text-lg">{receipt.account_masked}</p>
      <dl className="mt-2 space-y-1 text-sm text-slate-300">
        <Row k="Country" v={receipt.country} />
        <Row k="Institution" v={receipt.institution} />
        <Row k="Risk at check time" v={`${receipt.risk_score} (${receipt.risk_level}) · higher = riskier`} />
        <Row k="Checked at" v={new Date(receipt.at * 1000).toLocaleString()} />
      </dl>
      <p className="mt-3 text-xs text-slate-500">
        Point-in-time artifact — re-run the check for current risk.
      </p>
      <button
        className="mt-3 rounded-lg bg-slate-800 px-4 py-2 text-sm"
        onClick={() => window.print()}
      >
        Print / save PDF
      </button>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string | null }) {
  if (!v) return null;
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-400">{k}</dt>
      <dd className="text-right font-medium">{v}</dd>
    </div>
  );
}

function ReceiptInner() {
  const search = useSearchParams();
  const [country, setCountry] = useState("ID");
  const [bank, setBank] = useState("014");
  const [account, setAccount] = useState("");
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = search.get("token");
    if (token) void getReceipt(token).then(setReceipt).catch(() => setError("Invalid receipt"));
  }, [search]);

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-4 px-6 py-12">
      <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
        ← TrustPay SEA
      </Link>
      <h1 className="text-2xl font-bold">Diligence Receipt</h1>
      <p className="text-sm text-slate-400">
        Generate a timestamped proof that you checked an account before paying.
      </p>

      {!receipt && (
        <form
          className="flex flex-col gap-3"
          onSubmit={async (e) => {
            e.preventDefault();
            setError(null);
            try {
              setReceipt(await createReceipt({ country, bank, account }));
            } catch {
              setError("No registry entry to certify for this identifier.");
            }
          }}
        >
          <div className="grid grid-cols-2 gap-3">
            <select
              className={input}
              value={country}
              onChange={(e) => {
                setCountry(e.target.value);
                setBank(BANKS[e.target.value][0].code);
              }}
            >
              {COUNTRIES.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.label}
                </option>
              ))}
            </select>
            <select className={input} value={bank} onChange={(e) => setBank(e.target.value)}>
              {BANKS[country].map((b) => (
                <option key={b.code} value={b.code}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
          <input
            className={input}
            placeholder="Account number"
            value={account}
            onChange={(e) => setAccount(e.target.value)}
            required
          />
          <button className="rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-950">
            Generate receipt
          </button>
        </form>
      )}

      {error && <p className="text-sm text-rose-300">{error}</p>}
      {receipt && <ReceiptView receipt={receipt} />}
    </main>
  );
}

export default function ReceiptPage() {
  return (
    <Suspense fallback={null}>
      <ReceiptInner />
    </Suspense>
  );
}
