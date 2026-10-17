"use client";

import { LOCALES, type Locale } from "@/lib/i18n";
import { useI18n } from "./LocaleProvider";

export function LanguageSwitcher({ compact = false }: { compact?: boolean }) {
  const { locale, setLocale } = useI18n();

  return (
    <select
      aria-label="Language"
      value={locale}
      onChange={(e) => setLocale(e.target.value as Locale)}
      className={
        compact
          ? "cursor-pointer rounded-lg border border-slate-300 bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 outline-none hover:bg-slate-200"
          : "cursor-pointer rounded-lg border border-slate-300 bg-slate-100 px-0 py-1.5 text-xs font-semibold text-slate-700 outline-none hover:bg-slate-200 md:px-2.5"
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
