"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ApiError,
  BANKS,
  COUNTRIES,
  decodeQrImage,
  screenAccount,
  screenQr,
  type ScreenResult,
} from "@/lib/api";

type Tab = "account" | "qr";

const BADGE_STYLES: Record<string, string> = {
  GREEN: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  AMBER: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  RED: "bg-rose-500/15 text-rose-300 border-rose-500/40",
};

const LEVEL_LABELS: Record<string, string> = {
  LOW_RISK: "Low risk",
  CAUTION: "Caution",
  HIGH_RISK: "High risk",
  CRITICAL_FRAUD: "Critical fraud",
};

export default function CheckPage() {
  const [tab, setTab] = useState<Tab>("account");
  const [country, setCountry] = useState("ID");
  const [bank, setBank] = useState("014");
  const [account, setAccount] = useState("");
  const [payload, setPayload] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScreenResult | null>(null);

  async function run(fn: () => Promise<ScreenResult>) {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await fn());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  const input =
    "w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 outline-none focus:border-emerald-400";

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-4 px-6 py-12">
      <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
        ← TrustPay SEA
      </Link>
      <h1 className="text-2xl font-bold">Check before you pay</h1>

      <div className="flex gap-2">
        {(["account", "qr"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium ${
              tab === t ? "bg-emerald-500 text-slate-950" : "bg-slate-800 text-slate-300"
            }`}
          >
            {t === "account" ? "Bank account / e-wallet" : "Scan / paste QR"}
          </button>
        ))}
      </div>

      {tab === "account" ? (
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            void run(() => screenAccount({ country, bank, account }));
          }}
        >
          <div className="grid grid-cols-2 gap-3">
            <select className={input} value={country} onChange={(e) => {
              setCountry(e.target.value);
              setBank(BANKS[e.target.value][0].code);
            }}>
              {COUNTRIES.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.label}
                </option>
              ))}
            </select>
            <select className={input} value={bank} onChange={(e) => setBank(e.target.value)}>
              {BANKS[country].map((b) => (
                <option key={b.code} value={b.code}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
          <input
            className={input}
            placeholder="Full account number (we never store it in clear)"
            value={account}
            onChange={(e) => setAccount(e.target.value)}
            inputMode="numeric"
            required
          />
          <button
            type="submit"
            disabled={busy || !account}
            className="rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-950 disabled:opacity-50"
          >
            {busy ? "Checking…" : "Check account"}
          </button>
        </form>
      ) : (
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            void run(() => screenQr(payload));
          }}
        >
          <textarea
            className={input}
            rows={3}
            placeholder="Paste EMVCo QR payload (from camera scan elsewhere)"
            value={payload}
            onChange={(e) => setPayload(e.target.value)}
          />
          <label className="rounded-lg border border-dashed border-slate-700 px-4 py-4 text-center text-sm text-slate-400 hover:border-emerald-400 hover:text-slate-200">
            or upload QR image
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                setBusy(true);
                setError(null);
                setResult(null);
                try {
                  const decoded = await decodeQrImage(file);
                  setResult(await screenQr(decoded));
                } catch (err) {
                  setError(err instanceof ApiError ? err.message : "Decode failed");
                } finally {
                  setBusy(false);
                }
              }}
            />
          </label>
          <button
            type="submit"
            disabled={busy || !payload}
            className="rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-950 disabled:opacity-50"
          >
            {busy ? "Screening…" : "Screen QR"}
          </button>
        </form>
      )}

      {error && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
          {error}
        </div>
      )}

      {result && <ResultCard result={result} />}
    </main>
  );
}

function ResultCard({ result }: { result: ScreenResult }) {
  if (result.status === "not_found") {
    const meta = result.data.qr_metadata;
    return (
      <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-5">
        <p className="font-semibold text-amber-300">Not yet reviewed</p>
        <p className="mt-1 text-sm text-slate-300">{result.data.message}</p>
        {meta && (
          <dl className="mt-3 space-y-1 text-sm text-slate-300">
            <Row k="Merchant" v={meta.merchant_name} />
            <Row k="City" v={meta.merchant_city} />
            <Row k="Scheme" v={meta.scheme} />
            <Row k="NMID" v={meta.national_merchant_id} />
            {meta.homoglyph_warning && (
              <p className="text-amber-300">⚠ Lookalike characters detected in merchant name</p>
            )}
          </dl>
        )}
      </div>
    );
  }

  const { entity, risk_assessment: risk, community_signals: community, qr_metadata: meta } =
    result.data;
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-5">
      <div className="flex items-center justify-between">
        <p className="font-mono text-lg">{entity.account_masked}</p>
        <span
          className={`rounded-full border px-3 py-1 text-xs font-semibold ${
            BADGE_STYLES[risk.badge.color] ?? BADGE_STYLES.AMBER
          }`}
        >
          {risk.badge.label}
        </span>
      </div>
      <p className="mt-1 text-sm text-slate-400">
        {entity.institution ?? entity.scheme} · {entity.country}
        {entity.merchant_city ? ` · ${entity.merchant_city}` : ""}
      </p>

      {entity.holder && (
        <div
          className={`mt-3 rounded-lg border px-3 py-2 text-sm ${
            entity.holder.confidence === "VERIFIED"
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
              : "border-amber-500/40 bg-amber-500/10 text-amber-200"
          }`}
        >
          <span className="font-semibold">{entity.holder.name}</span>
          <span className="mt-0.5 block text-xs opacity-90">{entity.holder.label}</span>
        </div>
      )}

      <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
        <div className="rounded-lg bg-slate-800/60 p-3">
          <p className="text-xs text-slate-400">Risk score</p>
          <p className="text-xl font-bold">
            {risk.risk_score}
            <span className="ml-2 text-sm font-medium text-slate-300">
              {LEVEL_LABELS[risk.risk_level] ?? risk.risk_level}
            </span>
          </p>
        </div>
        <div className="rounded-lg bg-slate-800/60 p-3">
          <p className="text-xs text-slate-400">Reports</p>
          <p className="text-xl font-bold">{community.total_reports}</p>
        </div>
      </div>

      {(entity.merchant_name || meta?.merchant_name) && (
        <dl className="mt-3 space-y-1 text-sm text-slate-300">
          <Row k="Merchant" v={entity.merchant_name ?? meta?.merchant_name ?? null} />
          {entity.nmid && <Row k="NMID" v={entity.nmid} />}
          {entity.mcc && <Row k="MCC" v={entity.mcc} />}
        </dl>
      )}

      {meta?.homoglyph_warning && (
        <p className="mt-3 text-sm text-amber-300">
          ⚠ Lookalike characters detected in merchant name — verify carefully
        </p>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string | null }) {
  if (!v) return null;
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-400">{k}</dt>
      <dd className="text-right font-medium">{v}</dd>
    </div>
  );
}
