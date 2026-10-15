"use client";

import { useEffect, useState } from "react";
import { LOCALES, type Locale } from "@/lib/i18n";

const KEY = "trustpay_locale";

export function LanguageSwitcher({ compact = false }: { compact?: boolean }) {
  const [locale, setLocale] = useState<Locale>("en");

  useEffect(() => {
    const saved = window.localStorage.getItem(KEY) as Locale | null;
    if (saved && LOCALES.some((l) => l.code === saved)) setLocale(saved);
  }, []);

  return (
    <select
      aria-label="Language"
      value={locale}
      onChange={(e) => {
        const next = e.target.value as Locale;
        setLocale(next);
        window.localStorage.setItem(KEY, next);
      }}
      className={
        compact
          ? "cursor-pointer rounded-lg border border-slate-300 bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 outline-none hover:bg-slate-200"
          : "cursor-pointer rounded-lg border border-slate-300 bg-slate-100 px-2.5 py-1.5 text-xs font-semibold text-slate-700 outline-none hover:bg-slate-200"
      }
    >
      {LOCALES.map((l) => (
        <option key={l.code} value={l.code}>
          {l.flag} {l.label}
        </option>
      ))}
    </select>
  );
}
