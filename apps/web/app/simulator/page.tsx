"use client";

import Link from "next/link";
import { useState } from "react";
import { useI18n } from "@/components/LocaleProvider";

const STEPS = [
  { title: "simulator.s1Title", body: "simulator.s1Body" },
  { title: "simulator.s2Title", body: "simulator.s2Body" },
  { title: "simulator.s3Title", body: "simulator.s3Body" },
  { title: "simulator.s4Title", body: "simulator.s4Body" },
];

export default function SimulatorPage() {
  const { t } = useI18n();
  const [step, setStep] = useState(0);
  const last = step >= STEPS.length - 1;

  return (
    <main className="mx-auto flex max-w-xl flex-1 flex-col gap-4 px-6 py-12">
      <h1 className="text-2xl font-bold text-slate-900">{t("simulator.title")}</h1>
      <p className="text-sm text-slate-500">{t("simulator.subtitle")}</p>

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs">
        <p className="text-xs uppercase tracking-wide text-slate-400">
          {t("simulator.step", { n: step + 1, total: STEPS.length })}
        </p>
        <p className="mt-2 text-lg font-semibold text-slate-900">{t(STEPS[step].title)}</p>
        <p className="mt-2 text-slate-600">{t(STEPS[step].body)}</p>
      </div>

      <div className="flex gap-3">
        <button
          className="flex-1 rounded-lg border border-slate-300 bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-40"
          disabled={step === 0}
          onClick={() => setStep((s) => Math.max(0, s - 1))}
        >
          {t("simulator.back")}
        </button>
        {last ? (
          <Link
            href="/check"
            className="flex-1 rounded-lg bg-blue-600 px-4 py-2 text-center font-semibold text-white shadow-xs hover:bg-blue-700"
          >
            {t("simulator.checkAccount")}
          </Link>
        ) : (
          <button
            className="flex-1 rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white shadow-xs hover:bg-blue-700"
            onClick={() => setStep((s) => s + 1)}
          >
            {t("simulator.next")}
          </button>
        )}
      </div>

      <Link href="/playbook" className="text-sm text-slate-500 underline">
        {t("simulator.browse")}
      </Link>
    </main>
  );
}
