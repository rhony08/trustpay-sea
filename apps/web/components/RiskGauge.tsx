"use client";

import { useState } from "react";
import { riskBand } from "@/lib/risk";
import { useI18n } from "./LocaleProvider";

export type RiskFactor = { label: string; weight: number; dampened?: boolean };

export function RiskGauge({
  score,
  factors,
  compact = false,
}: {
  score: number;
  factors?: RiskFactor[];
  compact?: boolean;
}) {
  const { t } = useI18n();
  const band = riskBand(score);
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
      <div className="mb-4 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wide text-slate-600">
              {t("risk.assessed")}
            </span>
            <span className="rounded border border-red-200 bg-red-50 px-2 py-0.5 text-[10px] font-bold text-red-700">
              {t("risk.higherDanger")}
            </span>
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className={`text-4xl font-extrabold ${band.scoreText}`}>{score}</span>
            <span className="text-sm font-bold text-slate-400">/ 100</span>
            <span className={`ml-2 text-sm font-bold ${band.scoreText}`}>{t(band.labelKey)}</span>
          </div>
        </div>

        {!compact && (
          <div className="max-w-xs text-left text-xs text-slate-500 sm:text-right">
            <p className="font-bold text-slate-700">{t("risk.direction")}</p>
            <p className="mt-0.5 text-[11px] leading-tight text-slate-500">
              {t("risk.unlikeCredit")}
            </p>
          </div>
        )}
      </div>

      <div className="flex h-3 w-full overflow-hidden rounded-full bg-slate-200">
        <div className="w-1/4 bg-emerald-500" title={t("risk.low")} />
        <div className="w-1/4 bg-amber-400" title={t("risk.caution")} />
        <div className="w-1/4 bg-orange-500" title={t("risk.high")} />
        <div className="w-1/4 bg-red-600" title={t("risk.critical")} />
      </div>
      <div className="mt-1.5 flex justify-between text-[11px] font-medium text-slate-500">
        <span>{t("risk.safe")}</span>
        <span>20</span>
        <span>{t("risk.cautionMid")}</span>
        <span>80</span>
        <span>{t("risk.criticalMax")}</span>
      </div>

      {factors && factors.length > 0 && (
        <div className="mt-4 border-t border-slate-200 pt-3">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-1.5 text-xs font-bold text-blue-700 hover:text-blue-900"
          >
            <span>{t("risk.factorBreakdown")}</span>
            <span>{open ? "↑" : "↓"}</span>
          </button>
          {open && (
            <div className="mt-2.5 space-y-1.5 text-xs text-slate-700">
              {factors.map((f) => (
                <div
                  key={f.label}
                  className="flex justify-between rounded-lg border border-slate-200 bg-white px-3 py-1.5"
                >
                  <span>
                    {f.label.replaceAll("_", " ")}
                    {f.dampened ? " (dampened)" : ""}
                  </span>
                  <span className="font-bold text-red-600">
                    {f.weight > 0 ? `+${f.weight}` : f.weight}
                  </span>
                </div>
              ))}
              <div className="flex justify-between rounded-lg bg-slate-100 px-3 py-1.5 font-bold text-slate-800">
                <span>{t("risk.calculated")}</span>
                <span className={band.scoreText}>= {score} / 100</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
