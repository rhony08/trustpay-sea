"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  LOCALE_STORAGE_KEY,
  isLocale,
  translate,
  type Locale,
  type Vars,
} from "@/lib/i18n";

interface I18nValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, vars?: Vars) => string;
}

const I18nContext = createContext<I18nValue>({
  locale: "en",
  setLocale: () => undefined,
  t: (key, vars) => translate("en", key, vars),
});

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    const saved = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (isLocale(saved)) setLocaleState(saved);
  }, []);

  useEffect(() => {
    if (typeof document !== "undefined") document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    window.localStorage.setItem(LOCALE_STORAGE_KEY, next);
  }, []);

  const value = useMemo<I18nValue>(
    () => ({ locale, setLocale, t: (key, vars) => translate(locale, key, vars) }),
    [locale, setLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  return useContext(I18nContext);
}
