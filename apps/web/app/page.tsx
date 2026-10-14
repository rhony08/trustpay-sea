"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { t, type Locale } from "@/lib/i18n";

type ApiState = "checking" | "up" | "down";

export default function HomePage() {
  const [locale, setLocale] = useState<Locale>("en");
  const [api, setApi] = useState<ApiState>("checking");

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    fetch(`${base}/healthz`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("bad status"))))
      .then((body) => setApi(body?.status === "ok" ? "up" : "down"))
      .catch(() => setApi("down"));
  }, []);

  const dot =
    api === "up" ? "bg-emerald-400" : api === "down" ? "bg-rose-400" : "bg-amber-400 animate-pulse";

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 px-6 py-16">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">{t(locale, "appName")}</h1>
        <div className="flex gap-1 rounded-full border border-slate-700 p-1 text-sm">
          {(["en", "id"] as Locale[]).map((l) => (
            <button
              key={l}
              onClick={() => setLocale(l)}
              className={`rounded-full px-3 py-1 ${
                locale === l ? "bg-slate-100 text-slate-900" : "text-slate-300"
              }`}
            >
              {l.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      <p className="text-lg font-medium text-emerald-300">{t(locale, "tagline")}</p>
      <p className="leading-relaxed text-slate-300">{t(locale, "subtitle")}</p>

      <div className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
        <span className={`h-2.5 w-2.5 rounded-full ${dot}`} />
        <span className="text-sm text-slate-300">
          {t(locale, "apiStatus")}:{" "}
          {api === "checking" ? t(locale, "checking") : api === "up" ? t(locale, "apiUp") : t(locale, "apiDown")}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Link
          href="/check"
          className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-left text-sm text-emerald-200 hover:bg-emerald-500/20"
        >
          <span className="block font-semibold">{t(locale, "checkAccount")}</span>
          <span className="text-xs text-emerald-300/80">Phase 1 — live</span>
        </Link>
        <Link
          href="/report"
          className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-left text-sm text-rose-200 hover:bg-rose-500/20"
        >
          <span className="block font-semibold">Report a scam</span>
          <span className="text-xs text-rose-300/80">Phase 2 — live</span>
        </Link>
      </div>

      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/playbook" className="rounded-full border border-slate-700 px-4 py-1.5 text-slate-300 hover:border-emerald-400">
          Scam playbooks
        </Link>
        <Link href="/simulator" className="rounded-full border border-slate-700 px-4 py-1.5 text-slate-300 hover:border-emerald-400">
          Scam simulator
        </Link>
        <Link href="/receipt" className="rounded-full border border-slate-700 px-4 py-1.5 text-slate-300 hover:border-emerald-400">
          Diligence receipt
        </Link>
        <Link href="/tools/deal-check" className="rounded-full border border-slate-700 px-4 py-1.5 text-slate-300 hover:border-emerald-400">
          Too good to be true?
        </Link>
        <Link href="/recovery" className="rounded-full border border-slate-700 px-4 py-1.5 text-slate-300 hover:border-emerald-400">
          I got scammed
        </Link>
        <Link href="/profile" className="rounded-full border border-slate-700 px-4 py-1.5 text-slate-300 hover:border-emerald-400">
          My profile
        </Link>
      </div>

      <p className="text-xs text-slate-500">{t(locale, "phase")}</p>
    </main>
  );
}
