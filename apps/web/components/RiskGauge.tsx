"use client";

import { useState } from "react";
import { DIRECTION_NOTE, riskBand } from "@/lib/risk";

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
  const band = riskBand(score);
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
      <div className="mb-4 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wide text-slate-600">
              Assessed fraud risk score
            </span>
            <span className="rounded border border-red-200 bg-red-50 px-2 py-0.5 text-[10px] font-bold text-red-700">
              Higher score = higher danger
            </span>
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className={`text-4xl font-extrabold ${band.scoreText}`}>{score}</span>
            <span className="text-sm font-bold text-slate-400">/ 100</span>
            <span className={`ml-2 text-sm font-bold ${band.scoreText}`}>{band.label}</span>
          </div>
        </div>

        {!compact && (
          <div className="max-w-xs text-left text-xs text-slate-500 sm:text-right">
            <p className="font-bold text-slate-700">{DIRECTION_NOTE}</p>
            <p className="mt-0.5 text-[11px] leading-tight text-slate-500">
              Unlike credit scores, high numbers represent extreme fraudulent activity.
            </p>
          </div>
        )}
      </div>

      <div className="flex h-3 w-full overflow-hidden rounded-full bg-slate-200">
        <div className="w-1/4 bg-emerald-500" title="0-20 Safe" />
        <div className="w-1/4 bg-amber-400" title="21-50 Caution" />
        <div className="w-1/4 bg-orange-500" title="51-79 High" />
        <div className="w-1/4 bg-red-600" title="80-100 Critical" />
      </div>
      <div className="mt-1.5 flex justify-between text-[11px] font-medium text-slate-500">
        <span>0 (Safe)</span>
        <span>20</span>
        <span>50 (Caution)</span>
        <span>80</span>
        <span>100 (Critical)</span>
      </div>

      {factors && factors.length > 0 && (
        <div className="mt-4 border-t border-slate-200 pt-3">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-1.5 text-xs font-bold text-blue-700 hover:text-blue-900"
          >
            <span>View mathematical factor breakdown</span>
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
                <span>Calculated risk score:</span>
                <span className={band.scoreText}>= {score} / 100</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
