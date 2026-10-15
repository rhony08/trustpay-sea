"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { COUNTRIES, getHotlines, getRecovery, type Hotline, type RecoveryPlan } from "@/lib/api";
import { EmergencyHotlinesGrid } from "@/components/EmergencyHotlinesGrid";

const BANK_DIALS = [
  { label: "HaloBCA: 1500888", dial: "1500888" },
  { label: "Mandiri: 14000", dial: "14000" },
  { label: "BRI: 14017", dial: "14017" },
  { label: "BNI: 1500046", dial: "1500046" },
  { label: "Maybank: 1300-88-6688", dial: "1300886688" },
];

export default function RecoveryPage() {
  const [country, setCountry] = useState("ID");
  const [hotlines, setHotlines] = useState<Hotline[]>([]);
  const [plan, setPlan] = useState<RecoveryPlan | null>(null);

  useEffect(() => {
    void getHotlines(country).then(setHotlines).catch(() => undefined);
    void getRecovery(country).then(setPlan).catch(() => undefined);
  }, [country]);

  return (
    <main className="flex-1 py-10">
      <div className="mx-auto max-w-4xl space-y-8 px-4 sm:px-6">
        <div className="rounded-2xl border-2 border-rose-200 bg-rose-50/80 p-6 shadow-xs sm:p-8">
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-rose-600 text-xl font-bold text-white">
              !
            </div>
            <div>
              <span className="rounded border border-rose-200 bg-rose-100 px-2.5 py-0.5 text-xs font-bold uppercase text-rose-800">
                0–24 hour critical rapid response
              </span>
              <h1 className="mt-2 text-2xl font-black text-slate-900 sm:text-3xl">
                Just transferred money to a scammer? Take action immediately.
              </h1>
              <p className="mt-2 text-xs leading-relaxed text-slate-600 sm:text-sm">
                Perpetrators systematically transfer stolen funds into secondary mule accounts within{" "}
                <b>15 to 60 minutes</b>. Follow these statutory steps immediately to freeze the
                recipient account and maximise fund interception chances.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between border-b border-slate-200 pb-3">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-900">
              National anti-scam command hotlines
            </h2>
            <p className="text-xs text-slate-500">
              Official government emergency lines for instant inter-bank freezes
            </p>
          </div>
          <select
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-bold text-slate-800 shadow-xs outline-none focus:border-blue-600"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
          >
            {COUNTRIES.map((c) => (
              <option key={c.code} value={c.code}>
                {c.label}
              </option>
            ))}
          </select>
        </div>

        <EmergencyHotlinesGrid country={country} apiHotlines={hotlines} />

        <div className="space-y-4">
          <h2 className="text-base font-bold text-slate-900">3 crucial emergency recovery steps</h2>

          <Step n={1} tone="rose" title="Contact your bank's fraud department right now">
            <p className="text-xs leading-relaxed text-slate-600">
              Ask to be connected directly to the <b>Fraud / Dispute Operations Team</b>. State
              clearly: <i>&ldquo;I have just made an erroneous transfer to a confirmed scammer.
              Please create an emergency incident report and initiate inter-bank communication to
              freeze the destination account at the recipient bank.&rdquo;</i>
            </p>
            <div className="flex flex-wrap gap-2 pt-2 font-mono text-xs">
              {BANK_DIALS.map((b) => (
                <a
                  key={b.dial}
                  href={`tel:${b.dial}`}
                  className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 font-bold text-slate-800 hover:border-blue-400"
                >
                  {b.label}
                </a>
              ))}
            </div>
          </Step>

          <Step n={2} tone="amber" title="File an official police report (SPKT / cybercrime division)">
            <p className="text-xs leading-relaxed text-slate-600">
              Financial institutions legally require an official police incident report (Surat Tanda
              Penerimaan Laporan Polisi or national equivalent) to permanently lock the recipient
              mule account and preserve remaining funds for judicial restitution.
            </p>
          </Step>

          <Step n={3} tone="blue" title="Index the scammer's account on TrustPay SEA">
            <p className="text-xs leading-relaxed text-slate-600">
              Ensure this bank account is stamped with a <b>CRITICAL FRAUD</b> alert in our public
              registry so no subsequent victims transfer money to the same perpetrator.
            </p>
            <Link
              href="/report"
              className="mt-2 inline-block rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-blue-700"
            >
              Report this fraudulent account now &rarr;
            </Link>
          </Step>
        </div>

        {plan && (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-900">
              Action plan · {plan.country}
              {plan.bank ? ` · ${plan.bank}` : ""}
            </h2>
            <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <p className="text-xs font-bold text-slate-700">Immediate steps</p>
                <ol className="mt-2 list-decimal space-y-1 pl-5 text-xs text-slate-600">
                  {plan.immediate_steps.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ol>
              </div>
              <div>
                <p className="text-xs font-bold text-slate-700">Account freeze steps</p>
                <ol className="mt-2 list-decimal space-y-1 pl-5 text-xs text-slate-600">
                  {plan.freeze_steps.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ol>
              </div>
            </div>
            <p className="mt-3 text-[11px] text-slate-500">{plan.dossier_hint}</p>
          </div>
        )}
      </div>
    </main>
  );
}

const TONES = {
  rose: "border-rose-200 bg-rose-100 text-rose-700",
  amber: "border-amber-200 bg-amber-100 text-amber-800",
  blue: "border-blue-200 bg-blue-100 text-blue-700",
} as const;

function Step({
  n,
  tone,
  title,
  children,
}: {
  n: number;
  tone: keyof typeof TONES;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
      <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border font-bold ${TONES[tone]}`}>
        {n}
      </div>
      <div className="flex-1 space-y-2">
        <h3 className="text-sm font-bold text-slate-900">{title}</h3>
        {children}
      </div>
    </div>
  );
}
