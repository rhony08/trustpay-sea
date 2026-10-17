"use client";

import Link from "next/link";
import { ShieldMark } from "./Brand";
import { useI18n } from "./LocaleProvider";

const SERVICES = [
  { href: "/check", key: "nav.check" },
  { href: "/report", key: "nav.report" },
  { href: "/claim", key: "nav.claim" },
  { href: "/recovery", key: "nav.recovery" },
  { href: "/tools/scam-message", key: "nav.scamMessage" },
];

export function Footer() {
  const { t } = useI18n();
  return (
    <footer className="no-print border-t border-slate-200 bg-slate-100 py-12 text-xs text-slate-600">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mb-8 grid grid-cols-2 gap-8 md:grid-cols-4">
          <div>
            <span className="mb-3 flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded bg-blue-600 text-white">
                <ShieldMark className="h-4 w-4" />
              </span>
              <span className="text-sm font-bold text-slate-900">TrustPay SEA</span>
            </span>
            <p className="leading-relaxed text-slate-500">{t("footer.tagline")}</p>
          </div>

          <div>
            <h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-900">
              {t("footer.services")}
            </h4>
            <ul className="space-y-1.5 text-slate-600">
              {SERVICES.map((s) => (
                <li key={s.href}>
                  <Link href={s.href} className="hover:text-blue-600">
                    {t(s.key)}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-900">
              {t("footer.hotlines")}
            </h4>
            <ul className="space-y-1 text-[11px] text-slate-600">
              <li>{t("footer.hotId")}</li>
              <li>{t("footer.hotMy")}</li>
              <li>{t("footer.hotSg")}</li>
              <li>{t("footer.hotTh")}</li>
            </ul>
          </div>

          <div>
            <h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-900">
              {t("footer.legal")}
            </h4>
            <p className="text-[11px] leading-relaxed text-slate-500">{t("footer.legalBody")}</p>
          </div>
        </div>

        <div className="flex flex-col items-center justify-between gap-2 border-t border-slate-200 pt-6 text-[11px] text-slate-500 sm:flex-row">
          <p>{t("footer.statutory")}</p>
          <span className="shrink-0">{t("footer.copyright")}</span>
        </div>
      </div>
    </footer>
  );
}
