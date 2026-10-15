"use client";

import { useState } from "react";

export interface SlipFields {
  date?: string;
  victimName?: string;
  victimAccount?: string;
  victimBalance?: string;
  targetBank?: string;
  accountNumber?: string;
  holderName?: string;
  amount?: string;
}

/** Asymmetric PII redaction evidence viewer (Doc 12 §3). */
export function RedactedSlipViewer({
  fields = {},
  allowAnalystView = false,
}: {
  fields?: SlipFields;
  allowAnalystView?: boolean;
}) {
  const [redacted, setRedacted] = useState(true);
  const f: Required<SlipFields> = {
    date: fields.date ?? "12 Oct 2026, 14:22:09 WIB · Success",
    victimName: fields.victimName ?? "Rina Andriani",
    victimAccount: fields.victimAccount ?? "521-0982-192",
    victimBalance: fields.victimBalance ?? "Rp 8,421,900",
    targetBank: fields.targetBank ?? "Bank Central Asia (BCA)",
    accountNumber: fields.accountNumber ?? "8831924831",
    holderName: fields.holderName ?? "BAMBANG SUJARWO",
    amount: fields.amount ?? "Rp 1,500,000",
  };

  const blur = (extra = "") =>
    `${redacted ? "censored-blur " : ""}bg-slate-200 px-1.5 py-0.5 rounded text-slate-900 ${extra}`;

  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
            Payment slip forensics · asymmetric redaction
          </h3>
          <p className="text-xs text-slate-500">
            Victim personal info is blurred; scammer destination account and name are kept clear.
          </p>
        </div>
        {allowAnalystView && (
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-100 p-1 text-xs">
            <span className="text-[11px] font-medium text-slate-600">View mode:</span>
            <button
              type="button"
              onClick={() => setRedacted((v) => !v)}
              className={`rounded-md px-2.5 py-1 text-[11px] font-bold shadow-xs ${
                redacted ? "bg-blue-600 text-white" : "bg-rose-600 text-white"
              }`}
            >
              {redacted ? "Public (victim protected)" : "Analyst view (unredacted)"}
            </button>
          </div>
        )}
      </div>

      <div className="mx-auto max-w-md rounded-xl border border-slate-300 bg-slate-50 p-5 font-mono text-xs text-slate-800 shadow-xs">
        <div className="mb-3 border-b border-dashed border-slate-300 pb-3 text-center">
          <p className="text-sm font-extrabold text-slate-900">BANK TRANSFER RECEIPT</p>
          <p className="font-sans text-[10px] text-slate-500">{f.date}</p>
        </div>

        <div className="mb-3 space-y-1.5 rounded-lg border border-slate-200 bg-white p-3">
          <span className="block text-[10px] font-bold uppercase text-slate-400">
            Sender (victim — protected by system):
          </span>
          <Row label="Sender name" valueClass={blur("font-bold")}>
            {f.victimName}
          </Row>
          <Row label="Sender account" valueClass={blur()}>
            {f.victimAccount}
          </Row>
          <Row label="Account balance" valueClass={blur()}>
            {f.victimBalance}
          </Row>
          <p className="mt-1 font-sans text-[10px] font-medium text-emerald-700">
            🔒 Redacted by AI to prevent victim doxing &amp; harassment.
          </p>
        </div>

        <div className="space-y-1.5 rounded-lg border border-red-200 bg-red-50/60 p-3">
          <span className="block text-[10px] font-bold uppercase text-red-800">
            Destination (scammer / mule — kept clear):
          </span>
          <Row label="Target bank">{f.targetBank}</Row>
          <Row label="Account number" valueClass="rounded border border-red-200 bg-red-100 px-1.5 py-0.5 font-bold text-red-700">
            {f.accountNumber}
          </Row>
          <Row label="Holder name" valueClass="bg-amber-50 px-1 font-extrabold text-slate-900">
            {f.holderName}
          </Row>
          <Row label="Transferred sum" valueClass="font-bold">
            {f.amount}
          </Row>
          <p className="mt-1 font-sans text-[10px] text-slate-600">
            ✓ Kept visible so future payers can verify the exact recipient.
          </p>
        </div>
      </div>
    </div>
  );
}

function Row({
  label,
  children,
  valueClass = "",
}: {
  label: string;
  children: React.ReactNode;
  valueClass?: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="font-sans text-slate-500">{label}:</span>
      <span className={valueClass}>{children}</span>
    </div>
  );
}
