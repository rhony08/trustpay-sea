"use client";

import { useState } from "react";
import { castVote, flagReport, FLAG_REASONS, getToken, type ReportView } from "@/lib/api";
import { categoryKey } from "@/lib/risk";
import { AiForensics } from "./AiForensics";
import { useI18n } from "./LocaleProvider";

function relativeTime(createdAt: string | null, t: (k: string, v?: Record<string, string | number>) => string): string {
  if (!createdAt) return t("time.recently");
  const days = Math.floor((Date.now() - Date.parse(createdAt)) / 86_400_000);
  if (days <= 0) return t("time.today");
  if (days === 1) return t("time.dayAgo");
  if (days < 30) return t("time.daysAgo", { n: days });
  const months = Math.floor(days / 30);
  return months === 1 ? t("time.monthAgo") : t("time.monthsAgo", { n: months });
}

export function ReportCard({
  report,
  onFlag,
}: {
  report: ReportView;
  onFlag?: (reportId: string) => void;
}) {
  const { t } = useI18n();
  const [up, setUp] = useState(report.upvotes);
  const [voted, setVoted] = useState(false);
  const [flagState, setFlagState] = useState<string | null>(null);
  const [showFlag, setShowFlag] = useState(false);
  const [reason, setReason] = useState(FLAG_REASONS[0].value);
  const token = getToken();

  async function vote() {
    if (!token) return;
    try {
      const r = await castVote(token, report.id, 1);
      setUp(r.upvotes);
      setVoted(true);
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
      <div className="flex items-center justify-between text-xs">
        <span className="rounded border border-rose-200 bg-rose-50 px-2 py-0.5 font-bold uppercase text-rose-800">
          {t(categoryKey(report.category))}
        </span>
        <span className="font-medium text-slate-400">
          {relativeTime(report.created_at, t)} · {t("report.severity")} {report.severity}
        </span>
      </div>

      {report.description && (
        <p className="text-xs leading-relaxed text-slate-700">&ldquo;{report.description}&rdquo;</p>
      )}

      {report.ai_tampering_detected && (
        <p className="text-xs font-semibold text-rose-600">{t("report.tamper")}</p>
      )}

      {report.forensics && <AiForensics forensics={report.forensics} compact />}

      <div className="flex items-center justify-between border-t border-slate-100 pt-2 text-xs">
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={!token || voted}
            onClick={() => void vote()}
            className="flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-100 px-2.5 py-1 font-semibold text-slate-700 transition-colors hover:bg-slate-200 disabled:opacity-60"
          >
            <span>{t("check.helpful")}</span> <span className="font-bold text-blue-700">{up}</span>
          </button>
          {!token ? (
            <span className="text-slate-400">{t("check.signInToVote")}</span>
          ) : flagState ? (
            <span className="font-semibold text-amber-600">
              {t("check.flagged")} ({flagState})
            </span>
          ) : showFlag ? (
            <span className="flex items-center gap-1">
              <select
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="rounded border border-slate-300 bg-white px-1 py-0.5"
              >
                {FLAG_REASONS.map((fr) => (
                  <option key={fr.value} value={fr.value}>
                    {t(`flag.${fr.value}`)}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="rounded border border-rose-300 px-2 py-0.5 text-rose-700"
                onClick={async () => {
                  if (onFlag) {
                    onFlag(report.id);
                    return;
                  }
                  const flag = await flagReport(token, report.id, reason);
                  setFlagState(flag.status);
                }}
              >
                {t("common.submit")}
              </button>
            </span>
          ) : (
            <button
              type="button"
              onClick={() => (onFlag ? onFlag(report.id) : setShowFlag(true))}
              className="flex items-center gap-1 rounded px-2 py-1 font-semibold text-slate-500 transition-colors hover:bg-red-50 hover:text-red-700"
            >
              {t("check.flagFalse")}
            </button>
          )}
        </div>
        {report.loss_amount != null && (
          <span className="font-mono font-bold text-slate-800">
            {t("check.loss")} {report.currency} {report.loss_amount.toLocaleString()}
          </span>
        )}
      </div>
    </div>
  );
}
