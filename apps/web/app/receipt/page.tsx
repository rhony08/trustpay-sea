"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { BANKS, COUNTRIES, createReceipt, getReceipt, type Receipt } from "@/lib/api";
import { riskBand } from "@/lib/risk";
import { ShieldMark } from "@/components/Brand";
import { useI18n } from "@/components/LocaleProvider";

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-100";

function ReceiptInner() {
  const { t } = useI18n();
  const search = useSearchParams();
  const [country, setCountry] = useState(search.get("country") ?? "ID");
  const [bank, setBank] = useState(search.get("bank") ?? "014");
  const [account, setAccount] = useState(search.get("account") ?? "");
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = search.get("token");
    if (token) {
      void getReceipt(token)
        .then(setReceipt)
        .catch(() => setError(t("receipt.expired")));
    }
  }, [search, t]);

  return (
    <main className="flex-1 px-4 py-10">
      <div className="mx-auto max-w-md space-y-6">
        <div className="no-print text-center">
          <h1 className="text-xl font-extrabold text-slate-900">{t("receipt.title")}</h1>
          <p className="mt-1 text-xs text-slate-500">
            {t("receipt.subtitle")}
          </p>
        </div>

        {!receipt && (
          <form
            className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-xs"
            onSubmit={async (e) => {
              e.preventDefault();
              setError(null);
              try {
                setReceipt(await createReceipt({ country, bank, account }));
              } catch {
                setError(t("receipt.invalid"));
              }
            }}
          >
            <div className="grid grid-cols-2 gap-3">
              <select
                className={inputCls}
                value={country}
                onChange={(e) => {
                  setCountry(e.target.value);
                  setBank(BANKS[e.target.value]?.[0]?.code ?? bank);
                }}
              >
                {COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.label}
                  </option>
                ))}
              </select>
              <select className={inputCls} value={bank} onChange={(e) => setBank(e.target.value)}>
                {(BANKS[country] ?? []).map((b) => (
                  <option key={b.code} value={b.code}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
            <input
              className={`${inputCls} font-mono`}
              placeholder={t("receipt.placeholder")}
              value={account}
              onChange={(e) => setAccount(e.target.value)}
              required
            />
            <button className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white">
              {t("receipt.generate")}
            </button>
            {error && <p className="text-sm text-rose-600">{error}</p>}
          </form>
        )}

        {receipt && <Certificate receipt={receipt} />}

        <div className="no-print flex justify-center gap-3">
          <button
            onClick={() => window.print()}
            className="flex items-center gap-1.5 rounded-xl bg-blue-600 px-5 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-blue-700"
          >
            {t("receipt.print")}
          </button>
          <Link
            href="/check"
            className="rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-100"
          >
            {t("receipt.backToCheck")}
          </Link>
        </div>
      </div>
    </main>
  );
}

function Certificate({ receipt }: { receipt: Receipt }) {
  const { t } = useI18n();
  const band = riskBand(receipt.risk_score);
  const certId = `TP-REC-${new Date(receipt.at * 1000).getFullYear()}-${receipt.account_masked.replace(/\W/g, "").slice(-5) || "00000"}`;
  return (
    <div className="print-box space-y-4 rounded-2xl border-2 border-slate-300 bg-white p-6 font-mono text-xs shadow-sm sm:p-8">
      <div className="border-b-2 border-slate-200 pb-4 text-center">
        <span className="mb-1 flex items-center justify-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded bg-blue-600 text-white">
            <ShieldMark className="h-4 w-4" />
          </span>
          <span className="font-sans text-base font-extrabold tracking-wider text-slate-900">
            TRUSTPAY SEA
          </span>
        </span>
        <p className="font-sans text-[10px] font-bold uppercase tracking-wider text-slate-500">
          {t("receipt.certTitle")}
        </p>
        <p className="mt-1 font-mono text-[10px] font-bold text-blue-700">
          {t("receipt.certId")} {certId}
        </p>
      </div>

      <div className="space-y-2 font-sans text-slate-700">
        <CertRow k={t("receipt.timestamp")} v={new Date(receipt.at * 1000).toLocaleString()} />
        <CertRow k={t("receipt.institutionRow")} v={receipt.institution ?? receipt.scheme ?? "—"} />
        <CertRow k={t("receipt.country")} v={receipt.country} />
        <CertRow k={t("receipt.accountMasked")} v={receipt.account_masked} mono />
        <CertRow k={t("receipt.entityType")} v={receipt.entity_type} />
      </div>

      <div className={`space-y-1 rounded-xl border p-3.5 font-sans ${band.badge}`}>
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold">{t("receipt.riskScore")}</span>
          <span className={`font-mono text-base font-extrabold ${band.scoreText}`}>
            {receipt.risk_score} / 100
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold">{t("receipt.classification")}</span>
          <span className="text-xs font-black uppercase">{t(band.labelKey)}</span>
        </div>
        <p className="border-t border-slate-200 pt-1 text-[10px]">
          {t("receipt.higherDanger")}
        </p>
      </div>

      <div className="border-t border-slate-200 pt-3 text-center font-sans">
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-lg border border-slate-200 bg-slate-100 p-1.5">
          <svg className="h-full w-full text-slate-800" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M2 2h8v8H2V2zm2 2v4h4V4H4zm10-2h8v8h-8V2zm2 2v4h4V4h-4zM2 14h8v8H2v-8zm2 2v4h4v-4H4zm14-2h4v4h-4v-4zm-4 4h4v4h-4v-4zm4 0h4v4h-4v-4zm-4-4h4v4h-4v-4z" />
          </svg>
        </div>
        <p className="mt-2 text-[9px] font-semibold uppercase text-slate-500">
          {t("receipt.scanVerify")}
        </p>
      </div>

      <p className="text-center font-sans text-[10px] leading-relaxed text-slate-500">
        {t("receipt.legal")}
      </p>
    </div>
  );
}

function CertRow({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex justify-between border-b border-slate-100 pb-1">
      <span className="text-xs text-slate-500">{k}:</span>
      <span className={`text-xs font-bold text-slate-900 ${mono ? "font-mono" : ""}`}>{v}</span>
    </div>
  );
}

export default function ReceiptPage() {
  return (
    <Suspense fallback={null}>
      <ReceiptInner />
    </Suspense>
  );
}
