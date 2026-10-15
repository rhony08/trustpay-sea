"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { getReceipt, type Receipt } from "@/lib/api";
import { levelKey } from "@/lib/risk";
import { useI18n } from "@/components/LocaleProvider";

function WarningInner() {
  const { t } = useI18n();
  const search = useSearchParams();
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = search.get("token");
    if (!token) {
      setError(t("warning.missing"));
      return;
    }
    void getReceipt(token)
      .then(setReceipt)
      .catch(() => setError(t("warning.invalid")));
  }, [search, t]);

  const canonical =
    typeof window !== "undefined" && search.get("token")
      ? `${window.location.origin}/warning?token=${search.get("token")}`
      : "";

  return (
    <main className="mx-auto flex max-w-xl flex-1 flex-col gap-4 px-6 py-12">
      <h1 className="text-2xl font-bold text-slate-900">{t("warning.title")}</h1>
      {error && <p className="text-sm text-rose-600">{error}</p>}
      {receipt && (
        <>
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-center">
            <p className="text-xs uppercase tracking-wide text-rose-700">
              {t("warning.paymentWarning")}
            </p>
            <p className="mt-2 font-mono text-2xl text-rose-900">{receipt.account_masked}</p>
            <p className="mt-2 text-sm text-rose-800">
              {t("warning.riskPrefix", {
                score: receipt.risk_score,
                level: t(levelKey(receipt.risk_level)),
              })}
            </p>
            <p className="mt-1 text-xs text-rose-700">
              {receipt.institution ?? receipt.entity_type} · {receipt.country}
            </p>
          </div>
          <a href={canonical} className="break-all text-xs text-slate-500 underline">
            {canonical}
          </a>
          <button
            className="rounded-lg border border-slate-300 bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-200"
            onClick={() => window.print()}
          >
            {t("warning.print")}
          </button>
          <Link href="/check" className="text-sm text-slate-500 underline">
            {t("warning.recheck")}
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
