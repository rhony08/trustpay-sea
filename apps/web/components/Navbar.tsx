"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brand } from "./Brand";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { AuthMenu } from "./AuthMenu";
import { useI18n } from "./LocaleProvider";

const LINKS: { href: string; key: string; accent?: "rose" }[] = [
  { href: "/check", key: "nav.check" },
  { href: "/report", key: "nav.report", accent: "rose" },
  { href: "/claim", key: "nav.claim" },
  { href: "/recovery", key: "nav.recovery", accent: "rose" },
  { href: "/receipt", key: "nav.receipt" },
];

export function Navbar() {
  const pathname = usePathname();
  const { t } = useI18n();
  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <header className="no-print sticky top-0 z-40 border-b border-slate-200 bg-white shadow-xs">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Brand />

        <nav className="hidden items-center gap-1 text-sm font-medium md:flex">
          {LINKS.map((l) => {
            const active = isActive(l.href);
            const base = "rounded-lg px-3.5 py-2 transition-colors";
            const activeCls =
              l.accent === "rose"
                ? "border border-rose-200 bg-rose-50 font-semibold text-rose-700"
                : "border border-blue-100 bg-blue-50 font-semibold text-blue-700";
            const idle = "text-slate-700 hover:bg-slate-100 hover:text-slate-900";
            return (
              <Link key={l.href} href={l.href} className={`${base} ${active ? activeCls : idle}`}>
                {t(l.key)}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          <Link
            href="/report"
            className="hidden items-center gap-1 rounded-lg bg-rose-600 px-3.5 py-2 text-xs font-bold text-white shadow-xs transition-colors hover:bg-rose-700 sm:inline-flex"
          >
            {t("nav.reportBtn")}
          </Link>
          <AuthMenu />
        </div>
      </div>
    </header>
  );
}
