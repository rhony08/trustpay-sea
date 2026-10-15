/**
 * i18n core: locale catalog registry + interpolation (docs/11, docs/12).
 * Full catalogs live in ./locales/<code>.ts and share an identical key set.
 */

import en from "./locales/en";
import id from "./locales/id";
import ms from "./locales/ms";
import th from "./locales/th";
import vi from "./locales/vi";
import fil from "./locales/fil";

export type Locale = "en" | "id" | "ms" | "th" | "vi" | "fil";

export interface LocaleOption {
  code: Locale;
  flag: string;
  label: string;
}

/** Country language switcher dropdown order (Doc 12 §4). */
export const LOCALES: LocaleOption[] = [
  { code: "en", flag: "🇺🇸", label: "English" },
  { code: "id", flag: "🇮🇩", label: "Bahasa Indonesia" },
  { code: "ms", flag: "🇲🇾", label: "Bahasa Melayu" },
  { code: "th", flag: "🇹🇭", label: "ภาษาไทย" },
  { code: "vi", flag: "🇻🇳", label: "Tiếng Việt" },
  { code: "fil", flag: "🇵🇭", label: "Filipino" },
];

export const dictionaries: Record<Locale, Record<string, string>> = {
  en,
  id,
  ms,
  th,
  vi,
  fil,
};

export type Vars = Record<string, string | number>;

/** Resolve a key for a locale, interpolating `{var}` placeholders. */
export function translate(locale: Locale, key: string, vars?: Vars): string {
  const raw = dictionaries[locale]?.[key] ?? dictionaries.en[key] ?? key;
  if (!vars) return raw;
  return raw.replace(/\{(\w+)\}/g, (_, name: string) =>
    name in vars ? String(vars[name]) : `{${name}}`,
  );
}

export const LOCALE_STORAGE_KEY = "trustpay_locale";

export function isLocale(value: string | null | undefined): value is Locale {
  return !!value && LOCALES.some((l) => l.code === value);
}
