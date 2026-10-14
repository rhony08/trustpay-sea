/** MVP locale catalog: en + id (G-10, confirmed 2026-10-14). */

export type Locale = "en" | "id";

export const dictionaries: Record<Locale, Record<string, string>> = {
  en: {
    appName: "TrustPay SEA",
    tagline: "Check who you're paying — before you pay.",
    subtitle:
      "Community-driven payment-risk & reputation registry for Southeast Asia. Look up a bank account or scan a QRIS/DuitNow/PromptPay/PayNow code before you transfer.",
    checkAccount: "Check an account",
    scanQr: "Scan QR",
    apiStatus: "API status",
    checking: "Checking…",
    apiUp: "API is up",
    apiDown: "API unreachable",
    phase: "Phase 0 scaffold — resolver, reporting & scoring land in later phases.",
  },
  id: {
    appName: "TrustPay SEA",
    tagline: "Cek dulu penerimanya — sebelum kamu bayar.",
    subtitle:
      "Registry risiko & reputasi pembayaran berbasis komunitas untuk Asia Tenggara. Periksa rekening bank atau pindai kode QRIS/DuitNow/PromptPay/PayNow sebelum transfer.",
    checkAccount: "Periksa rekening",
    scanQr: "Pindai QR",
    apiStatus: "Status API",
    checking: "Memeriksa…",
    apiUp: "API aktif",
    apiDown: "API tidak terjangkau",
    phase: "Fondasi Fase 0 — resolver, pelaporan & skor menyusul di fase berikutnya.",
  },
};

export function t(locale: Locale, key: keyof (typeof dictionaries)["en"]): string {
  return dictionaries[locale][key] ?? dictionaries.en[key] ?? key;
}
