"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { COUNTRIES, getHotlines, getRecovery, type Hotline, type RecoveryPlan } from "@/lib/api";

export default function RecoveryPage() {
  const [country, setCountry] = useState("ID");
  const [hotlines, setHotlines] = useState<Hotline[]>([]);
  const [plan, setPlan] = useState<RecoveryPlan | null>(null);

  useEffect(() => {
    void getHotlines(country).then(setHotlines).catch(() => undefined);
    void getRecovery(country).then(setPlan).catch(() => undefined);
  }, [country]);

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-4 px-6 py-12">
      <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
        ← TrustPay SEA
      </Link>
      <h1 className="text-2xl font-bold">I just got scammed</h1>
      <p className="text-sm text-slate-400">
        Act fast: freeze, report, and gather evidence.
      </p>

      <select
        className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100"
        value={country}
        onChange={(e) => setCountry(e.target.value)}
      >
        {COUNTRIES.map((c) => (
          <option key={c.code} value={c.code}>
            {c.label}
          </option>
        ))}
      </select>

      {hotlines.length > 0 && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4">
          <p className="text-sm font-semibold text-rose-200">Emergency hotlines</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {hotlines.map((h) =>
              h.number ? (
                <a
                  key={h.name}
                  href={`tel:${h.number}`}
                  className="rounded-lg bg-rose-500/20 px-3 py-1.5 text-sm text-rose-100"
                >
                  {h.name}: {h.number}
                </a>
              ) : (
                <a
                  key={h.name}
                  href={h.url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-lg bg-rose-500/20 px-3 py-1.5 text-sm text-rose-100 underline"
                >
                  {h.name}
                </a>
              ),
            )}
          </div>
        </div>
      )}

      {plan && (
        <>
          <section className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
            <p className="text-sm font-semibold text-slate-200">Do this immediately</p>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-300">
              {plan.immediate_steps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
          </section>

          <section className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
            <p className="text-sm font-semibold text-slate-200">Freeze steps</p>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-300">
              {plan.freeze_steps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
          </section>

          <a
            href={plan.referral.url}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg bg-emerald-500 px-4 py-2 text-center font-semibold text-slate-950"
          >
            File a report with {plan.referral.name}
          </a>
          <p className="text-xs text-slate-500">{plan.dossier_hint}</p>
        </>
      )}
    </main>
  );
}
