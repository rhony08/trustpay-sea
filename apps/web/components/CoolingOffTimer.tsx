"use client";

import { useEffect, useState } from "react";
import { useI18n } from "./LocaleProvider";

/** Mandatory cooling-off interstitial (Doc 12 §4B.1). */
export function CoolingOffTimer({
  seconds = 10,
  onAcknowledged,
}: {
  seconds?: number;
  onAcknowledged?: () => void;
}) {
  const { t } = useI18n();
  const [remaining, setRemaining] = useState(seconds);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (done || remaining <= 0) return;
    const timer = setTimeout(() => setRemaining((r) => r - 1), 1000);
    return () => clearTimeout(timer);
  }, [remaining, done]);

  if (done) return null;

  const ready = remaining <= 0;

  return (
    <div className="flex flex-col items-center justify-between gap-4 rounded-xl border border-amber-300 bg-amber-50 p-4 sm:flex-row">
      <div className="flex items-center gap-3">
        <span className="text-2xl">⏳</span>
        <div>
          <p className="text-xs font-bold text-amber-900">{t("check.coolingTitle")}</p>
          <p className="text-xs text-amber-800">{t("check.coolingMsg")}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className="rounded-lg border border-amber-200 bg-amber-100 px-3 py-1.5 font-mono text-xs font-bold text-amber-900">
          {ready ? t("check.ready") : t("check.pause", { n: remaining })}
        </span>
        <button
          type="button"
          disabled={!ready}
          onClick={() => {
            setDone(true);
            onAcknowledged?.();
          }}
          className={
            ready
              ? "rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-bold text-white shadow-xs hover:bg-amber-700"
              : "cursor-not-allowed rounded-lg bg-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-400"
          }
        >
          {t("check.understandRisk")}
        </button>
      </div>
    </div>
  );
}
