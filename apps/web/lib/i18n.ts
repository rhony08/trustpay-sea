/** Locale catalog: en + id full; ms, th, vi, fil scaffolded (fall back to en). */

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

type Dictionary = Record<string, string>;

const en: Dictionary = {
  appName: "TrustPay SEA",
  tagline: "Know who you are paying — before sending money.",
  subtitle:
    "Search any bank account, phone number, or scan a QRIS/DuitNow/PromptPay/PayNow code. Prevent mule scams and verify legitimate sellers.",
  checkAccount: "Check an account",
  scanQr: "Scan QR",
  apiStatus: "API status",
  checking: "Checking…",
  apiUp: "API is up",
  apiDown: "API unreachable",
  phase: "Informational reputation registry — not financial advice.",
};

const id: Dictionary = {
  appName: "TrustPay SEA",
  tagline: "Cek dulu penerimanya — sebelum kamu bayar.",
  subtitle:
    "Periksa rekening bank, nomor telepon, atau pindai kode QRIS/DuitNow/PromptPay/PayNow sebelum transfer.",
  checkAccount: "Periksa rekening",
  scanQr: "Pindai QR",
  apiStatus: "Status API",
  checking: "Memeriksa…",
  apiUp: "API aktif",
  apiDown: "API tidak terjangkau",
  phase: "Registry reputasi informasi — bukan nasihat keuangan.",
};

/** Non-en/id locales fall back to English until catalogs land. */
export const dictionaries: Record<Locale, Dictionary> = {
  en,
  id,
  ms: en,
  th: en,
  vi: en,
  fil: en,
};

export function t(locale: Locale, key: string): string {
  return dictionaries[locale]?.[key] ?? en[key] ?? key;
}
