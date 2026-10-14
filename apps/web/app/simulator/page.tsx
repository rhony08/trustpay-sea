"use client";

import Link from "next/link";
import { useState } from "react";

const STEPS = [
  {
    title: "You found a great deal",
    body: "An Instagram seller offers a phone at 40% below market and asks for a deposit.",
  },
  {
    title: "They rush you",
    body: '"Only one left, pay in the next 10 minutes or I sell to someone else."',
  },
  {
    title: "They send an account",
    body: "A personal bank account. The name on it doesn't match the shop's name.",
  },
  {
    title: "Intercept!",
    body: "Before paying you check the account on TrustPay — it already has 3 fraud reports for non-delivery. You don't pay.",
  },
];

export default function SimulatorPage() {
  const [step, setStep] = useState(0);
  const last = step >= STEPS.length - 1;

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-4 px-6 py-12">
      <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
        ← TrustPay SEA
      </Link>
      <h1 className="text-2xl font-bold">Scam Simulator</h1>
      <p className="text-sm text-slate-400">
        Walk through a typical online-shopping scam and see where checking saves you.
      </p>

      <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-6">
        <p className="text-xs uppercase tracking-wide text-slate-400">
          Step {step + 1} / {STEPS.length}
        </p>
        <p className="mt-2 text-lg font-semibold text-slate-100">{STEPS[step].title}</p>
        <p className="mt-2 text-slate-300">{STEPS[step].body}</p>
      </div>

      <div className="flex gap-3">
        <button
          className="flex-1 rounded-lg bg-slate-800 px-4 py-2 text-sm disabled:opacity-40"
          disabled={step === 0}
          onClick={() => setStep((s) => Math.max(0, s - 1))}
        >
          Back
        </button>
        {last ? (
          <Link
            href="/check"
            className="flex-1 rounded-lg bg-emerald-500 px-4 py-2 text-center font-semibold text-slate-950"
          >
            Check an account
          </Link>
        ) : (
          <button
            className="flex-1 rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-950"
            onClick={() => setStep((s) => s + 1)}
          >
            Next
          </button>
        )}
      </div>

      <Link href="/playbook" className="text-sm text-slate-400 underline">
        Browse scam playbooks →
      </Link>
    </main>
  );
}
