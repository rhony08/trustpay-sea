"use client";

import type { ReportForensics } from "@/lib/api";
import { categoryKey } from "@/lib/risk";
import { useI18n } from "./LocaleProvider";

/** Renders the public-safe subset of the pipeline's AI forensics (Doc 12). */
export function AiForensics({
  forensics,
  compact = false,
}: {
  forensics?: ReportForensics | null;
  compact?: boolean;
}) {
  const { t } = useI18n();
  if (!forensics) return null;

  const typology = forensics.typology;
  const ner = forensics.ner;
  const ocr = forensics.ocr;
  const hasNer =
    ner &&
    (ner.phone_hints.length ||
      ner.url_hosts.length ||
      ner.amount_hints.length ||
      ner.handles.length);

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-bold uppercase tracking-wide text-blue-900">
          {t("ai.title")}
        </span>
        <span className="rounded bg-blue-100 px-2 py-0.5 text-[10px] font-bold text-blue-800">
          {forensics.provider === "mock" ? t("ai.engineMock") : t("ai.engineModel")}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {typology && (
          <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs">
            <span className="block font-bold uppercase text-slate-500">{t("ai.typology")}</span>
            <p className="mt-0.5 font-semibold text-slate-800">
              {t(categoryKey(typology.predicted))}
            </p>
            <p className="mt-0.5 text-slate-500">
              {t("ai.confidence")}: {Math.round((typology.confidence || 0) * 100)}% ·{" "}
              <span className={typology.matches_submitted ? "text-emerald-600" : "text-amber-600"}>
                {typology.matches_submitted ? t("ai.matches") : t("ai.mismatch")}
              </span>
            </p>
          </div>
        )}

        <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs">
          <span className="block font-bold uppercase text-slate-500">{t("ai.tamper")}</span>
          {forensics.tampering_detected ? (
            <p className="mt-0.5 font-semibold text-rose-600">
              {t("ai.tamperDetected")}
              {forensics.tamper_signals.length > 0
                ? ` (${forensics.tamper_signals.join(", ")})`
                : ""}
            </p>
          ) : (
            <p className="mt-0.5 font-semibold text-emerald-600">{t("ai.noTamper")}</p>
          )}
        </div>
      </div>

      {!compact && (ocr?.recipient || ocr?.amount || ocr?.ref_id) && (
        <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs">
          <span className="block font-bold uppercase text-slate-500">{t("ai.ocr")}</span>
          <dl className="mt-1 space-y-0.5 text-slate-700">
            {ocr.recipient && <Field k={t("ai.recipient")} v={ocr.recipient} />}
            {ocr.amount && <Field k={t("ai.amount")} v={ocr.amount} />}
            {ocr.ref_id && <Field k={t("ai.ref")} v={ocr.ref_id} />}
          </dl>
        </div>
      )}

      {!compact && hasNer && ner && (
        <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs">
          <span className="block font-bold uppercase text-slate-500">{t("ai.ner")}</span>
          <dl className="mt-1 space-y-0.5 text-slate-700">
            {ner.phone_hints.length > 0 && (
              <Field k={t("ai.phoneHints")} v={ner.phone_hints.join(", ")} />
            )}
            {ner.url_hosts.length > 0 && (
              <Field k={t("ai.urlHosts")} v={ner.url_hosts.join(", ")} />
            )}
            {ner.handles.length > 0 && <Field k={t("ai.handles")} v={ner.handles.join(", ")} />}
          </dl>
          {ner.injection_suspected && (
            <p className="mt-1 font-semibold text-amber-600">{t("ai.injection")}</p>
          )}
        </div>
      )}

      {forensics.duplicate_evidence_of.length > 0 && (
        <p className="text-[11px] font-semibold text-rose-600">{t("ai.duplicate")}</p>
      )}
    </div>
  );
}

function Field({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-slate-500">{k}</dt>
      <dd className="text-right font-medium text-slate-800">{v}</dd>
    </div>
  );
}
