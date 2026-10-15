"use client";

import { useState } from "react";
import { checkDeal, type DealCheckResult } from "@/lib/api";
import { useI18n } from "@/components/LocaleProvider";

export default function DealCheckPage() {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const [result, setResult] = useState<DealCheckResult | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <main className="mx-auto flex max-w-xl flex-1 flex-col gap-4 px-6 py-12">
      <h1 className="text-2xl font-bold text-slate-900">{t("dealCheck.title")}</h1>
      <p className="text-sm text-slate-500">{t("dealCheck.subtitle")}</p>
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
          className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-slate-800 outline-none focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-100"
          rows={4}
          placeholder={t("dealCheck.placeholder")}
          value={text}
          onChange={(e) => setText(e.target.value)}
          required
        />
        <button
          disabled={busy}
          className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white shadow-xs hover:bg-blue-700 disabled:opacity-50"
        >
          {busy ? t("common.checking") : t("dealCheck.check")}
        </button>
      </form>

      {result && (
        <div
          className={`rounded-xl border p-5 ${
            result.suspicious
              ? "border-rose-200 bg-rose-50 text-rose-800"
              : "border-emerald-200 bg-emerald-50 text-emerald-800"
          }`}
        >
          <p className="font-semibold">
            {result.suspicious ? t("dealCheck.redFlags") : t("dealCheck.noFlags")}
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
