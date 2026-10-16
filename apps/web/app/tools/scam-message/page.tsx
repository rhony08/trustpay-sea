"use client";

import { useState } from "react";
import { analyzeMessage, ApiError, type MessageAnalysis } from "@/lib/api";
import { categoryKey } from "@/lib/risk";
import { useI18n } from "@/components/LocaleProvider";

const RISK: Record<string, { labelKey: string; cls: string }> = {
  LOW: { labelKey: "risk.low", cls: "border-emerald-200 bg-emerald-50 text-emerald-800" },
  CAUTION: { labelKey: "risk.caution", cls: "border-amber-200 bg-amber-50 text-amber-800" },
  HIGH: { labelKey: "risk.high", cls: "border-orange-200 bg-orange-50 text-orange-800" },
  CRITICAL: { labelKey: "risk.critical", cls: "border-red-200 bg-red-50 text-red-800" },
};

export default function ScamMessagePage() {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const [result, setResult] = useState<MessageAnalysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const risk = result ? RISK[result.risk_level] ?? RISK.CAUTION : null;

  return (
    <main className="mx-auto flex max-w-xl flex-1 flex-col gap-4 px-6 py-12">
      <h1 className="text-2xl font-bold text-slate-900">{t("tools.message.title")}</h1>
      <p className="text-sm text-slate-500">{t("tools.message.subtitle")}</p>

      <form
        className="flex flex-col gap-3"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            setResult(await analyzeMessage(text));
          } catch (err) {
            setError(err instanceof ApiError ? err.message : t("common.errorRequest"));
          } finally {
            setBusy(false);
          }
        }}
      >
        <textarea
          className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-slate-800 outline-none focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-100"
          rows={5}
          placeholder={t("tools.message.placeholder")}
          value={text}
          onChange={(e) => setText(e.target.value)}
          required
        />
        <button
          disabled={busy}
          className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white shadow-xs hover:bg-blue-700 disabled:opacity-50"
        >
          {busy ? t("tools.message.analyzing") : t("tools.message.analyze")}
        </button>
      </form>

      {error && <p className="text-sm text-rose-600">{error}</p>}

      {result && risk && (
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className={`rounded-lg border px-3 py-1 text-xs font-extrabold uppercase ${risk.cls}`}>
              {t(risk.labelKey)}
            </span>
            <span className="rounded bg-blue-100 px-2 py-0.5 text-[10px] font-bold text-blue-800">
              {result.engine === "mock" ? t("ai.engineMock") : t("ai.engineModel")}
            </span>
          </div>

          {result.summary && <p className="text-sm leading-relaxed text-slate-700">{result.summary}</p>}

          {result.signals.length > 0 && (
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                {t("tools.message.signals")}
              </p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-rose-700">
                {result.signals.map((s) => (
                  <li key={s.code}>{s.label || s.code.replaceAll("_", " ")}</li>
                ))}
              </ul>
            </div>
          )}

          {(result.extracted.account ||
            result.extracted.phone ||
            result.extracted.claimed_identity) && (
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                {t("tools.message.extracted")}
              </p>
              <dl className="mt-1 space-y-0.5 text-sm text-slate-700">
                {result.extracted.account && (
                  <Row k={t("tools.message.account")} v={result.extracted.account} />
                )}
                {result.extracted.phone && (
                  <Row k={t("tools.message.phone")} v={result.extracted.phone} />
                )}
                {result.extracted.claimed_identity && (
                  <Row k={t("tools.message.identity")} v={result.extracted.claimed_identity} />
                )}
              </dl>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs">
            <span className="font-semibold text-slate-600">
              {t("tools.message.suggestedCategory")}
            </span>
            <span className="rounded border border-rose-200 bg-rose-50 px-2 py-0.5 font-bold uppercase text-rose-800">
              {t(categoryKey(result.suggested_category))}
            </span>
          </div>

          {result.tips.length > 0 && (
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                {t("tools.message.tips")}
              </p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-600">
                {result.tips.map((tip, i) => (
                  <li key={i}>{tip}</li>
                ))}
              </ul>
            </div>
          )}

          <p className="text-[11px] text-slate-400">{t("tools.message.disclaimer")}</p>
        </div>
      )}
    </main>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-slate-500">{k}</dt>
      <dd className="text-right font-mono font-medium text-slate-800">{v}</dd>
    </div>
  );
}
